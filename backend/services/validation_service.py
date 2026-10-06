"""
Validation Service

Core orchestration logic for post-migration data validation across
supported source and target database types. Manages validation run lifecycle, delegates to
repository for persistence and cache for Redis caching.
"""

import hashlib
import json
import logging
import os
import re
import time
import traceback
from decimal import Decimal, InvalidOperation
from datetime import datetime
from typing import Optional, List, Dict, Any

import psycopg2
from pymongo import MongoClient
import clickhouse_connect
import pyodbc
import pymysql
from google.cloud import bigquery
from google.oauth2 import service_account
from sqlalchemy.orm import Session

from models.assessment import AssessmentTable, AssessmentColumn
from models.connection import Connection
from models.bq_redshift_migration import MigrationBQRedshift
from models.validation_run import ValidationRun
from models.validation_table_result import ValidationTableResult
from repositories.validation_repository import ValidationRepository
from services.validation_cache import ValidationCache
from services.data_type_mapper import DataTypeMapper
from services.bedrock_client import BedrockClient

logger = logging.getLogger(__name__)


class ValidationService:
    """Service for creating and managing validation runs.

    Orchestrates DDL comparison, row count checks, and record-level
    matching for migrated tables. Integrates with Redis cache and
    PostgreSQL via the repository layer.

    Args:
        db: SQLAlchemy database session.
        cache: ValidationCache instance for Redis caching.
    """

    def __init__(self, db: Session, cache: ValidationCache):
        self.db = db
        self.repo = ValidationRepository(db)
        self.cache = cache
        self.type_mapper = DataTypeMapper()
        self.bedrock = BedrockClient()

    # ------------------------------------------------------------------
    # Error sanitization & sensitive data masking
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize_error_message(error_msg: str) -> str:
        """Strip credentials, hostnames, IPs, and port numbers from error messages.

        Removes:
        - IPv4 addresses (e.g. 10.0.1.42)
        - Hostnames like *.amazonaws.com or *.redshift.amazonaws.com
        - Connection credentials (password=..., username=...)
        - Port numbers in connection strings (host:port patterns)

        Args:
            error_msg: Raw error message string.

        Returns:
            Sanitized error message safe for client responses.
        """
        if not error_msg:
            return error_msg

        # IPv4 addresses
        sanitized = re.sub(
            r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
            "[REDACTED_IP]",
            error_msg,
        )
        # Hostnames (e.g. my-cluster.abc123.us-east-1.redshift.amazonaws.com)
        sanitized = re.sub(
            r"\b[\w.-]+\.amazonaws\.com\b",
            "[REDACTED_HOST]",
            sanitized,
        )
        # Generic hostnames with dots (host:port patterns)
        sanitized = re.sub(
            r"\b[\w.-]+:\d{2,5}\b",
            "[REDACTED_ENDPOINT]",
            sanitized,
        )
        # password=... (up to next whitespace, comma, or quote)
        sanitized = re.sub(
            r"password\s*=\s*[^\s,;'\"]+",
            "password=[REDACTED]",
            sanitized,
            flags=re.IGNORECASE,
        )
        # username=... (up to next whitespace, comma, or quote)
        sanitized = re.sub(
            r"username\s*=\s*[^\s,;'\"]+",
            "username=[REDACTED]",
            sanitized,
            flags=re.IGNORECASE,
        )
        # user=... (psycopg2 style)
        sanitized = re.sub(
            r"\buser\s*=\s*[^\s,;'\"]+",
            "user=[REDACTED]",
            sanitized,
            flags=re.IGNORECASE,
        )
        return sanitized

    # ------------------------------------------------------------------
    # Run creation
    # ------------------------------------------------------------------

    MAX_CONCURRENT_RUNS_PER_WORKSPACE = 10
    
    def get_migration_info(self, migration_id: int, workspace_id: int) -> Optional[Dict[str, Any]]:
        """Get migration details for auto-filling the validation form.

        Returns migration name, source/target connection IDs and names, and table list.
        """
        migration = (
            self.db.query(MigrationBQRedshift)
            .filter(
                MigrationBQRedshift.id == migration_id,
                MigrationBQRedshift.workspace_id == workspace_id,
            )
            .first()
        )
        if not migration:
            return None

        source_name = None
        target_name = None
        if migration.source_connection_id:
            src = self.db.query(Connection).filter(Connection.id == migration.source_connection_id).first()
            if src:
                source_name = src.name
        if migration.target_connection_id:
            tgt = self.db.query(Connection).filter(Connection.id == migration.target_connection_id).first()
            if tgt:
                target_name = tgt.name

        # Extract per-table row counts from checkpoint_data export_results
        table_row_counts: Dict[str, Optional[int]] = {}
        tables = migration.source_tables or []
        # Build a case-insensitive lookup for source_tables
        tables_lower_map = {t.lower(): t for t in tables}

        if migration.checkpoint_data and isinstance(migration.checkpoint_data, dict):
            # Primary source: export_results list (populated after export stage)
            export_results = migration.checkpoint_data.get("export_results", [])
            if isinstance(export_results, list):
                for result in export_results:
                    if isinstance(result, dict) and result.get("success"):
                        table_ref = result.get("table", "")
                        # Extract last segment from fully-qualified refs (project.dataset.table)
                        extracted = table_ref.rsplit(".", 1)[-1] if "." in table_ref else table_ref
                        # Case-insensitive match against source_tables
                        matched_name = tables_lower_map.get(extracted.lower(), extracted)
                        # Try num_rows first, then total_rows_exported as fallback
                        num_rows = result.get("num_rows")
                        if num_rows is None:
                            num_rows = result.get("total_rows_exported")
                        if matched_name:
                            table_row_counts[matched_name] = num_rows
            # Fallback: check per-table keys in checkpoint_data
            for t in tables:
                if t not in table_row_counts:
                    tdata = migration.checkpoint_data.get(t, {})
                    if isinstance(tdata, dict) and "row_count" in tdata:
                        table_row_counts[t] = tdata["row_count"]
                    elif isinstance(tdata, dict) and "total_rows" in tdata:
                        table_row_counts[t] = tdata["total_rows"]
                    else:
                        table_row_counts[t] = None
        else:
            for t in tables:
                table_row_counts[t] = None

        # Final fallback: query AssessmentTable for any tables still missing counts
        tables_needing_counts = [t for t in tables if table_row_counts.get(t) is None]
        if tables_needing_counts and migration.source_connection_id:
            try:
                from models.assessment import Assessment
                assessment = (
                    self.db.query(Assessment)
                    .filter(
                        Assessment.source_connection_id == migration.source_connection_id,
                        Assessment.workspace_id == workspace_id,
                        Assessment.status == "completed",
                    )
                    .order_by(Assessment.id.desc())
                    .first()
                )
                if assessment:
                    assessment_tables = (
                        self.db.query(AssessmentTable)
                        .filter(
                            AssessmentTable.assessment_id == assessment.id,
                            AssessmentTable.table_name.in_(tables_needing_counts),
                        )
                        .all()
                    )
                    for at in assessment_tables:
                        if at.row_count is not None:
                            table_row_counts[at.table_name] = at.row_count
            except Exception as exc:
                logger.warning(
                    "Failed to fetch row counts from assessment metadata",
                    extra={
                        "migration_id": migration_id,
                        "error": str(exc),
                    },
                )

        return {
            "migration_id": migration.id,
            "migration_name": migration.migration_name,
            "source_connection_id": migration.source_connection_id,
            "target_connection_id": migration.target_connection_id,
            "source_connection_name": source_name,
            "target_connection_name": target_name,
            "tables": tables,
            "table_row_counts": table_row_counts,
        }
    def get_migration_table_columns(
        self,
        migration_id: int,
        table_name: str,
        workspace_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Get source and target columns for a selected migration table."""

        migration = (
            self.db.query(MigrationBQRedshift)
            .filter(
                MigrationBQRedshift.id == migration_id,
                MigrationBQRedshift.workspace_id == workspace_id,
            )
            .first()
        )

        if not migration:
            return None

        tables = migration.source_tables or []

        matched_table = next(
            (
                table
                for table in tables
                if str(table).lower() == table_name.lower()
            ),
            None,
        )

        if not matched_table:
            return None

        source_columns: List[Dict[str, Any]] = []
        target_columns: List[Dict[str, Any]] = []

        # --------------------------------------------------------------
        # Source: BigQuery column metadata
        # --------------------------------------------------------------
        if migration.source_connection_id:
            try:
                from models.assessment import Assessment

                assessment = (
                    self.db.query(Assessment)
                    .filter(
                        Assessment.source_connection_id
                        == migration.source_connection_id,
                        Assessment.workspace_id == workspace_id,
                        Assessment.status == "completed",
                    )
                    .order_by(Assessment.id.desc())
                    .first()
                )

                if assessment:
                    source_columns = self._get_source_columns(
                        assessment_id=assessment.id,
                        dataset_name=migration.source_dataset,
                        table_name=matched_table,
                        workspace_id=workspace_id,
                    )

            except Exception as exc:
                logger.warning(
                    "Failed to retrieve source columns",
                    extra={
                        "migration_id": migration_id,
                        "table_name": matched_table,
                        "error": str(exc),
                    },
                )

        # --------------------------------------------------------------
        # Target: Redshift column metadata
        # --------------------------------------------------------------
        if migration.target_connection_id:
            try:
                target_connection = (
                    self.db.query(Connection)
                    .filter(
                        Connection.id == migration.target_connection_id
                    )
                    .first()
                )

                if target_connection:
                    target_conn_params = (
                        self.decrypt_connection_credentials(
                            target_connection
                        )
                    )

                    target_columns = self._get_target_columns(
                        conn_params=target_conn_params,
                        schema_name=migration.target_schema,
                        table_name=matched_table,
                    )

            except Exception as exc:
                logger.warning(
                    "Failed to retrieve target columns",
                    extra={
                        "migration_id": migration_id,
                        "table_name": matched_table,
                        "error": self._sanitize_error_message(str(exc)),
                    },
                )

        return {
            "migration_id": migration_id,
            "table_name": matched_table,
            "source_columns": source_columns,
            "target_columns": target_columns,
        }
    def create_validation_run(
        self,
        workspace_id: int,
        migration_id: int,
        source_connection_id: int,
        target_connection_id: int,
        tables: Optional[List[str]] = None,
        table_configs: Optional[List[Dict[str, Any]]] = None,
        bedrock_model: Optional[str] = None,
        batch_size: int = 10000,
        sampling_mode: str = "all",
        sample_limit: Optional[int] = None,
        type_mapping_overrides: Optional[Dict[str, str]] = None,
        created_by: str = "",
        run_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a validation run for a completed migration.

        Verifies the migration is completed and both connections are active
        before creating the run and one ValidationTableResult per table.

        Args:
            workspace_id: Tenant isolation identifier.
            migration_id: ID of the completed migration to validate.
            source_connection_id: BigQuery source connection ID.
            target_connection_id: Redshift target connection ID.
            tables: Optional explicit list of table names. If None, tables
                    are retrieved from the migration record's source_tables.
            bedrock_model: Optional Bedrock model ID for AI analysis.
            batch_size: Row batch size for record-level matching.
            type_mapping_overrides: Optional BQâ†’Redshift type overrides.
            created_by: Username or identifier of the requesting user.

        Returns:
            Dict representation of the created ValidationRun.

        Raises:
            ValueError: If migration is not completed, connections are
                        invalid/inactive, or no tables can be determined.
            RuntimeError: If the workspace has reached the maximum number
                          of concurrent validation runs.
        """
        # 0. Rate limiting â€” enforce max concurrent runs per workspace
        active_count = self.repo.count_active_runs(workspace_id)
        if active_count >= self.MAX_CONCURRENT_RUNS_PER_WORKSPACE:
            logger.warning(
                "Rate limit exceeded for workspace",
                extra={
                    "workspace_id": workspace_id,
                    "active_runs": active_count,
                    "max_concurrent": self.MAX_CONCURRENT_RUNS_PER_WORKSPACE,
                },
            )
            raise RuntimeError(
                f"Workspace {workspace_id} has reached the maximum of "
                f"{self.MAX_CONCURRENT_RUNS_PER_WORKSPACE} concurrent validation runs. "
                "Please wait for existing runs to complete before starting a new one."
            )

        # 1. Verify migration exists and is completed
        migration = (
            self.db.query(MigrationBQRedshift)
            .filter(
                MigrationBQRedshift.id == migration_id,
                MigrationBQRedshift.workspace_id == workspace_id,
            )
            .first()
        )
        if not migration:
            raise ValueError(
                f"Migration with id={migration_id} not found in workspace {workspace_id}"
            )
        if migration.status != "completed":
            raise ValueError(
                f"Migration {migration_id} has status '{migration.status}'. "
                "Validation requires a completed migration."
            )

        # 2. Verify source connection exists and is active
        source_conn = (
            self.db.query(Connection)
            .filter(Connection.id == source_connection_id)
            .first()
        )
        if not source_conn or not source_conn.is_active:
            raise ValueError(
                f"Source connection with id={source_connection_id} "
                "is missing or inactive."
            )

        # 3. Verify target connection exists and is active
        target_conn = (
            self.db.query(Connection)
            .filter(Connection.id == target_connection_id)
            .first()
        )
        if not target_conn or not target_conn.is_active:
            raise ValueError(
                f"Target connection with id={target_connection_id} "
                "is missing or inactive."
            )

        # 4. Resolve table list
        resolved_tables = tables
        if not resolved_tables:
            resolved_tables = migration.source_tables
        if not resolved_tables:
            raise ValueError(
                f"No tables specified and migration {migration_id} "
                "has no source_tables configured."
            )

        # 5. Create ValidationRun
        run = self.repo.create_run(
            workspace_id=workspace_id,
            migration_id=migration_id,
            source_connection_id=source_connection_id,
            target_connection_id=target_connection_id,
            bedrock_model=bedrock_model,
            batch_size=batch_size,
             type_mapping_overrides=type_mapping_overrides,
            validation_config=table_configs,
            status="pending",           
            progress_percentage=0,
            tables_total=len(resolved_tables),
            tables_passed=0,
            tables_failed=0,
            tables_error=0,
            created_by=created_by,
            run_name=run_name,
        )

        
                # 6. Create one ValidationTableResult per table
        # Build a lookup for per-table check flags from table_configs
        config_lookup: Dict[str, Dict[str, Any]] = {}

        if table_configs:
            for tc in table_configs:
                tname = str(tc.get("table_name", "")).strip()
                if tname:
                    config_lookup[tname.lower()] = tc

        # Validate table-specific configuration before any background work starts.
        # This prevents a run from being created with silently unusable checks.
        for table_name in resolved_tables:
            tc = config_lookup.get(str(table_name).lower(), {})
            if tc.get("null_check") and not str(tc.get("null_column") or "").strip():
                raise ValueError(f"NULL Validation requires a column for table '{table_name}'")
            if tc.get("duplicate_check") and not str(tc.get("duplicate_match_key") or "").strip():
                raise ValueError(f"Duplicate Validation requires a match key for table '{table_name}'")
            if tc.get("sum_check") and not str(tc.get("sum_column") or "").strip():
                raise ValueError(f"SUM Validation requires a column for table '{table_name}'")
            if tc.get("average_check") and not str(tc.get("average_column") or "").strip():
                raise ValueError(f"AVERAGE Validation requires a column for table '{table_name}'")
            if tc.get("specific_row_check"):
                match_key = str(tc.get("specific_row_match_key") or "").strip()
                if not match_key:
                    raise ValueError(f"Specific Row Validation requires a match key for table '{table_name}'")
                start = tc.get("specific_row_start")
                end = tc.get("specific_row_end")
                if start is None or end is None:
                    raise ValueError(f"Specific Row Validation requires Start Row and End Row for table '{table_name}'")
                try:
                    start = int(start)
                    end = int(end)
                except (TypeError, ValueError):
                    raise ValueError(f"Specific Row Validation requires numeric Start Row and End Row for table '{table_name}'")
                if start < 1 or end < 1 or end < start:
                    raise ValueError(f"Specific Row Validation requires 1 <= Start Row <= End Row for table '{table_name}'")

        for table_name in resolved_tables:
            tc = config_lookup.get(str(table_name).lower(), {})

            self.repo.create_table_result(
                run_id=run.id,
                workspace_id=workspace_id,
                table_name=table_name,
                status="pending",
                ddl_check=tc.get("ddl_check", True),
                row_count_check=tc.get("row_count_check", True),
                data_match_check=tc.get("data_match_check", False),
                null_check=tc.get("null_check", False),
                duplicate_check=tc.get("duplicate_check", False),
                sum_check=tc.get("sum_check", False),
                average_check=tc.get("average_check", False),
                specific_row_check=tc.get("specific_row_check", False),
                
            )

        # 7. Cache the run in Redis (TTL 15 min)
        run_dict = run.to_dict()
        self.cache.set_run(run.id, workspace_id, run_dict)

        # 8. Log creation
        logger.info(
            "Validation run created",
            extra={
                "run_id": run.id,
                "migration_id": migration_id,
                "table_count": len(resolved_tables),
                "workspace_id": workspace_id,
            },
        )

        return run_dict

    # ------------------------------------------------------------------
    # Background orchestration
    # ------------------------------------------------------------------

    def run_validation_background(self, run_id: int, workspace_id: int) -> None:
        """Execute validation as a background task for all tables in a run.

        Processes tables sequentially: DDL comparison â†’ row count
        validation â†’ record-level matching. Updates progress, table
        results, and run summary after each table completes.

        Designed to be passed to ``BackgroundTasks.add_task()``.

        Args:
            run_id: The validation run primary key.
            workspace_id: Tenant isolation identifier.
        """
        run_start = datetime.utcnow()

        logger.info(
            "Validation run started",
            extra={"event": "run_started", "run_id": run_id, "workspace_id": workspace_id},
        )

        # 1. Fetch the run ------------------------------------------------
        run = self.repo.get_run(run_id, workspace_id)
        if run is None:
            logger.error(
                "Validation run not found for background execution",
                extra={"run_id": run_id, "workspace_id": workspace_id},
            )
            return

        # 2. Mark run as running ------------------------------------------
        self.repo.update_run(
            run_id, workspace_id,
            status="running",
            started_at=run_start,
        )
        self.cache.invalidate_run(run_id, workspace_id)

        # 3. Fetch table results ------------------------------------------
        table_results = self.repo.list_table_results(run_id, workspace_id)
        if not table_results:
            logger.warning(
                "No table results found for validation run",
                extra={"run_id": run_id, "workspace_id": workspace_id},
            )
            self.repo.update_run(
                run_id, workspace_id,
                status="completed",
                completed_at=datetime.utcnow(),
                duration_seconds=0,
            )
            self.cache.invalidate_run(run_id, workspace_id)
            return

        # 4. Look up migration for dataset_name --------------------------
        migration = (
            self.db.query(MigrationBQRedshift)
            .filter(
                MigrationBQRedshift.id == run.migration_id,
                MigrationBQRedshift.workspace_id == workspace_id,
            )
            .first()
        )
        dataset_name = migration.source_dataset if migration else None

        # 5. Find assessment_id from the most recent completed assessment
        #    matching the source connection and workspace -----------------
        from models.assessment import Assessment

        assessment = (
            self.db.query(Assessment)
            .filter(
                Assessment.source_connection_id == run.source_connection_id,
                Assessment.workspace_id == workspace_id,
                Assessment.status == "completed",
            )
            .order_by(Assessment.id.desc())
            .first()
        )
        assessment_id = assessment.id if assessment else None

        # 6. Decrypt connection credentials -------------------------------
        #    Use the MIGRATION's target connection (same creds the migration
        #    used) rather than the validation run's target_connection_id,
        #    which may point to a different or stale connection.
        source_conn = (
            self.db.query(Connection)
            .filter(Connection.id == run.source_connection_id)
            .first()
        )

        # Prefer migration's target_connection_id over the run's
        migration_target_conn_id = (
            migration.target_connection_id if migration else None
        )
        effective_target_conn_id = migration_target_conn_id or run.target_connection_id

        target_conn = (
            self.db.query(Connection)
            .filter(Connection.id == effective_target_conn_id)
            .first()
        )

        if effective_target_conn_id != run.target_connection_id:
            logger.info(
                "Using migration's target connection instead of run's",
                extra={
                    "run_target_connection_id": run.target_connection_id,
                    "migration_target_connection_id": effective_target_conn_id,
                    "run_id": run_id,
                },
            )

        source_conn_params = (
            self.decrypt_connection_credentials(source_conn)
            if source_conn
            else {}
        )
        target_conn_params = (
            self.decrypt_connection_credentials(target_conn)
            if target_conn
            else {}
        )

        # Override database/schema using the same naming convention as
        # pathway_c's _execute_load_stage:
        #   database = source_project_id.replace('-', '_').lower()
        #   schema   = source_dataset
        # The migration's target_database/target_schema fields are often
        # stale placeholders (e.g. "target_db" / "public") and do NOT
        # reflect the actual Redshift database created during migration.
        # Keep source and target namespaces separate.  A source dataset/schema
        # and target schema are not necessarily the same name, especially when
        # validating heterogeneous databases.
        source_conn_params["_validation_namespace"] = (
            migration.source_dataset if migration and migration.source_dataset else dataset_name
        )
        target_conn_params["_validation_namespace"] = (
            migration.target_schema if migration and migration.target_schema else dataset_name
        )

        if migration and self._get_database_type(target_conn_params) == "redshift":
            # First try checkpoint_data.load_summary (gold standard â€” set
            # by pathway_c after a successful load).
            load_summary = (migration.checkpoint_data or {}).get("load_summary", {})
            actual_db = load_summary.get("database_name")
            actual_schema = load_summary.get("schema_name")

            if not actual_db and migration.source_project_id:
                actual_db = migration.source_project_id.replace("-", "_").lower()
            if not actual_schema and migration.source_dataset:
                actual_schema = migration.source_dataset

            if actual_db:
                target_conn_params["database"] = actual_db
                logger.info(
                    f"Using computed Redshift database: {actual_db}",
                    extra={"run_id": run_id},
                )
            if actual_schema:
                dataset_name = actual_schema
                target_conn_params["_validation_namespace"] = actual_schema
                logger.info(
                    f"Using computed Redshift schema / BQ dataset: {actual_schema}",
                    extra={"run_id": run_id},
                )

        type_mapping_overrides = run.type_mapping_overrides or {}
        batch_size = run.batch_size or 10000
        total_tables = len(table_results)

        # Log connection details for debugging (no secrets)
        logger.info(
            "Validation connection details",
            extra={
                "run_id": run_id,
                "target_host": target_conn_params.get("host", "N/A"),
                "target_port": target_conn_params.get("port", "N/A"),
                "target_database": target_conn_params.get("database", "N/A"),
                "target_username": target_conn_params.get("username", "N/A"),
                "source_has_credentials": bool(
                    source_conn_params.get("credentials_json")
                    or source_conn_params.get("service_account_key")
                    or source_conn_params.get("credentials")
                ),
                "source_project_id": source_conn_params.get("project_id")
                    or source_conn_params.get("projectId")
                    or "N/A",
                "dataset_name": dataset_name,
            },
        )

        # 7. Process each table sequentially ------------------------------
        tables_passed = 0
        tables_failed = 0
        tables_error = 0

        for idx, table_result in enumerate(table_results):
            table_start = datetime.utcnow()
            table_name = table_result.table_name
            tbl_dataset = table_result.dataset_name or dataset_name or ""

            logger.info(
                "Table validation started",
                extra={
                    "event": "table_validation_started",
                    "run_id": run_id,
                    "table_name": table_name,
                    "workspace_id": workspace_id,
                    "table_index": idx + 1,
                    "total_tables": total_tables,
                },
            )

            # Mark table as running
            self.repo.update_table_result(
                table_result.id, workspace_id,
                status="running",
                started_at=table_start,
            )

            table_has_error = False
            table_has_failure = False

            try:
                # --- DDL comparison (skip if ddl_check is False) ------
                ddl_result = {"status": "skipped", "result": {}}
                if not getattr(table_result, 'ddl_check', True):
                    ddl_result = {"status": "skipped", "result": {}}
                elif assessment_id is not None:
                    ddl_result = self._validate_ddl(
                        run_id=run_id,
                        table_name=table_name,
                        dataset_name=tbl_dataset,
                        assessment_id=assessment_id,
                        target_conn_params=target_conn_params,
                        type_mapping_overrides=type_mapping_overrides,
                        workspace_id=workspace_id,
                    )
                else:
                    ddl_result = {
                        "status": "error",
                        "result": {
                            "discrepancies": [],
                            "source_column_count": 0,
                            "target_column_count": 0,
                            "columns_compared": 0,
                        },
                        "error_message": "No completed assessment found for source connection",
                    }

                ddl_status = ddl_result["status"]
                if ddl_status == "error":
                    table_has_error = True
                elif ddl_status == "failed":
                    table_has_failure = True

                # --- Row count validation (skip if row_count_check is False) ---
                row_count_result = {"status": "skipped", "result": {}}
                if getattr(table_result, 'row_count_check', True):
                    row_count_result = self._validate_row_count(
                        run_id=run_id,
                        table_name=table_name,
                        dataset_name=tbl_dataset,
                        source_conn_params=source_conn_params,
                        target_conn_params=target_conn_params,
                        workspace_id=workspace_id,
                    )

                rc_status = row_count_result["status"]
                if rc_status == "error":
                    table_has_error = True
                elif rc_status == "failed":
                    table_has_failure = True
                # --- NULL validation (skip if null_check is False) ---
                null_result = {"status": "skipped", "result": {}}

                if getattr(table_result, "null_check", False):
                    null_column = ""

                    for tc in (run.validation_config or []):
                        if (
                            isinstance(tc, dict)
                            and tc.get("table_name") == table_name
                        ):
                            null_column = tc.get("null_column") or ""
                            break

                    null_result = self._validate_nulls(
                        source_conn_params=source_conn_params,
                        target_conn_params=target_conn_params,
                        dataset_name=tbl_dataset,
                        table_name=table_name,
                        column_name=null_column,
                    )

                null_status = null_result["status"]

                if null_status == "error":
                    table_has_error = True
                elif null_status == "failed":
                    table_has_failure = True
                                # --- Duplicate validation (skip if duplicate_check is False) ---
                duplicate_result = {
                    "status": "skipped",
                    "result": {},
                }

                if getattr(table_result, "duplicate_check", False):
                    duplicate_match_key = ""

                    for tc in (run.validation_config or []):
                        if (
                            isinstance(tc, dict)
                            and tc.get("table_name") == table_name
                        ):
                            duplicate_match_key = (
                                tc.get("duplicate_match_key") or ""
                            )
                            break

                    duplicate_result = self._validate_duplicates(
                        source_conn_params=source_conn_params,
                        target_conn_params=target_conn_params,
                        dataset_name=tbl_dataset,
                        table_name=table_name,
                        match_key=duplicate_match_key,
                    )

                duplicate_status = duplicate_result["status"]

                if duplicate_status == "error":
                    table_has_error = True
                elif duplicate_status == "failed":
                    table_has_failure = True
                                # --- SUM validation ---
                sum_result = {
                    "status": "skipped",
                    "result": {},
                }

                sum_column = ""

                for tc in (run.validation_config or []):
                    if (
                        isinstance(tc, dict)
                        and tc.get("table_name") == table_name
                    ):
                        sum_column = tc.get("sum_column") or ""
                        break

                if getattr(table_result, "sum_check", False):
                    sum_result = self._validate_aggregate(
                        source_conn_params=source_conn_params,
                        target_conn_params=target_conn_params,
                        dataset_name=tbl_dataset,
                        table_name=table_name,
                        column_name=sum_column,
                        aggregate_type="SUM",
                    )

                sum_status = sum_result["status"]

                if sum_status == "error":
                    table_has_error = True
                elif sum_status == "failed":
                    table_has_failure = True


                # --- AVERAGE validation ---
                average_result = {
                    "status": "skipped",
                    "result": {},
                }

                average_column = ""

                for tc in (run.validation_config or []):
                    if (
                        isinstance(tc, dict)
                        and tc.get("table_name") == table_name
                    ):
                        average_column = tc.get("average_column") or ""
                        break

                if getattr(table_result, "average_check", False):
                    average_result = self._validate_aggregate(
                        source_conn_params=source_conn_params,
                        target_conn_params=target_conn_params,
                        dataset_name=tbl_dataset,
                        table_name=table_name,
                        column_name=average_column,
                        aggregate_type="AVERAGE",
                    )

                average_status = average_result["status"]

                if average_status == "error":
                    table_has_error = True
                elif average_status == "failed":
                    table_has_failure = True
                # --- Record-level matching (skip if data_match_check is False) ---
                                # --- Record-level / Specific Row validation -------------------
                records_result = {
                    "status": "skipped",
                    "result": {},
                }

                data_match_enabled = getattr(
                    table_result,
                    "data_match_check",
                    False,
                )

                specific_row_enabled = getattr(
                    table_result,
                    "specific_row_check",
                    False,
                )
                specific_row_match_key = None

                if specific_row_enabled:
                    for tc in (run.validation_config or []):
                        if (
                            isinstance(tc, dict)
                            and tc.get("table_name") == table_name
                        ):
                            specific_row_match_key = tc.get(
                                "specific_row_match_key"
                            )
                            break

                # Run record comparison only when the user explicitly selected
                # Data Match or Specific Row validation.
                if specific_row_enabled:
                    specific_row_match_key = str(specific_row_match_key or "").strip()
                    if not specific_row_match_key:
                        raise ValueError(
                            f"Specific Row Validation requires a match key for table '{table_name}'"
                        )
                    if specific_row_start is None or specific_row_end is None:
                        raise ValueError(
                            f"Specific Row Validation requires Start Row and End Row for table '{table_name}'"
                        )
                    try:
                        specific_row_start = int(specific_row_start)
                        specific_row_end = int(specific_row_end)
                    except (TypeError, ValueError):
                        raise ValueError(
                            f"Specific Row Validation requires numeric Start Row and End Row for table '{table_name}'"
                        )
                    if specific_row_start < 1 or specific_row_end < specific_row_start:
                        raise ValueError(
                            f"Specific Row Validation requires 1 <= Start Row <= End Row for table '{table_name}'"
                        )

                if data_match_enabled or specific_row_enabled:

                    # Determine primary key from AssessmentColumn metadata
                    primary_key = []

                    if assessment_id is not None and tbl_dataset:
                        try:
                            assessment_table = (
                                self.db.query(AssessmentTable)
                                .filter(
                                    AssessmentTable.assessment_id == assessment_id,
                                    AssessmentTable.dataset_name == tbl_dataset,
                                    AssessmentTable.table_name == table_name,
                                )
                                .first()
                            )

                            if assessment_table:
                                pk_columns = (
                                    self.db.query(AssessmentColumn)
                                    .filter(
                                        AssessmentColumn.table_id == assessment_table.id,
                                        AssessmentColumn.column_metadata.isnot(None),
                                    )
                                    .all()
                                )

                                for col in pk_columns:
                                    meta = col.column_metadata or {}

                                    if meta.get("is_primary_key"):
                                        primary_key.append(
                                            col.column_name
                                        )

                        except Exception as pk_exc:
                            logger.warning(
                                "Failed to determine primary key from assessment",
                                extra={
                                    "run_id": run_id,
                                    "table_name": table_name,
                                    "error": str(pk_exc),
                                },
                            )

                    # Read Specific Row configuration only when that check
                    # was explicitly selected.
                    specific_row_start = None
                    specific_row_end = None

                    if specific_row_enabled:
                        for tc in (run.validation_config or []):
                            if (
                                isinstance(tc, dict)
                                and tc.get("table_name") == table_name
                            ):
                                specific_row_start = tc.get(
                                    "specific_row_start"
                                )
                                specific_row_end = tc.get(
                                    "specific_row_end"
                                )
                                break

                    records_result = self._validate_records(
                        run_id=run_id,
                        table_name=table_name,
                        dataset_name=tbl_dataset,
                        source_conn_params=source_conn_params,
                        target_conn_params=target_conn_params,
                        primary_key=(
                            [specific_row_match_key]
                            if specific_row_enabled
                            else primary_key
                        ),
                        batch_size=batch_size,
                        type_mapping_overrides=type_mapping_overrides,
                        workspace_id=workspace_id,
                        specific_row_start=(
                            specific_row_start
                            if specific_row_enabled
                            else None
                        ),
                        specific_row_end=(
                            specific_row_end
                            if specific_row_enabled
                            else None
                        ),
                    )

                # Only an actually executed record validation can affect
                # the overall table status.
                rec_status = records_result["status"]

                if rec_status == "error":
                    table_has_error = True

                elif rec_status == "failed":
                    table_has_failure = True
                                # --- Determine overall table status -------------------
                # Filter out skipped checks for status determination
                active_statuses = [
                    s
                    for s in [
                        ddl_result["status"],
                        row_count_result["status"],
                        null_result["status"],
                        duplicate_result["status"],
                        sum_result["status"],
                        average_result["status"],
                        records_result["status"],
                    ]
                    if s != "skipped"
                ]

                if not active_statuses:
                    # All checks were skipped
                    table_status = "completed"
                elif table_has_error:
                    # Any check that actually errored takes priority over
                    # a failure — an infra/connection error is not the same
                    # thing as a genuine data discrepancy, and should never
                    # be masked by other checks that happened to pass.
                    table_status = "error"
                elif table_has_failure:
                    table_status = "failed"
                else:
                    table_status = "completed"

                # Build error message from any error steps
                error_messages = []

                if ddl_result.get("error_message"):
                    error_messages.append(
                        f"DDL: {ddl_result['error_message']}"
                    )

                if row_count_result.get("error_message"):
                    error_messages.append(
                        f"Row count: {row_count_result['error_message']}"
                    )

                if null_result.get("error_message"):
                    error_messages.append(
                        f"NULL: {null_result['error_message']}"
                    )
                if duplicate_result.get("error_message"):
                    error_messages.append(
                        f"Duplicate: {duplicate_result['error_message']}"
                    )
                if sum_result.get("error_message"):
                     error_messages.append(
                        f"SUM: {sum_result['error_message']}"
                    )

                if average_result.get("error_message"):
                   error_messages.append(
                        f"AVERAGE: {average_result['error_message']}"
                    )
                if records_result.get("error_message"):
                    error_messages.append(
                        f"Records: {records_result['error_message']}"
                    )
                table_end = datetime.utcnow()
                table_duration = int((table_end - table_start).total_seconds())

                # Update table result with all outcomes
                self.repo.update_table_result(
                    table_result.id, workspace_id,
                    ddl_status=ddl_result["status"],
                    ddl_comparison_result=ddl_result["result"],
                    row_count_status=row_count_result["status"],
                    row_count_result=row_count_result["result"],
                    null_status=null_result["status"],
                    null_result=null_result["result"],
                    duplicate_status=duplicate_result["status"],
                    duplicate_result=duplicate_result["result"],
                    sum_status=sum_result["status"],
                    sum_result=sum_result["result"],
                    average_status=average_result["status"],
                    average_result=average_result["result"],
                    specific_row_status=(
                        records_result["status"]
                        if getattr(table_result, "specific_row_check", False)
                        else "skipped"
                    ),
                    specific_row_result=(
                        records_result["result"]
                        if getattr(table_result, "specific_row_check", False)
                        else {}
                    ),
                    data_match_status=(
                        records_result["status"]
                        if data_match_enabled
                        else "skipped"
                    ),
                    data_match_result=(
                        records_result["result"]
                        if data_match_enabled
                        else {}
                    ),
                    status=table_status,
                    error_message="; ".join(error_messages) if error_messages else None,
                    completed_at=table_end,
                    duration_seconds=table_duration,
                )

            except Exception as exc:
                # Unrecoverable table error
                table_end = datetime.utcnow()
                table_duration = int((table_end - table_start).total_seconds())
                table_status = "error"

                logger.error(
                    "Unrecoverable table validation error",
                    extra={
                        "run_id": run_id,
                        "table_name": table_name,
                        "workspace_id": workspace_id,
                        "error": self._sanitize_error_message(str(exc)),
                        "traceback": traceback.format_exc(),
                    },
                )

                self.repo.update_table_result(
                    table_result.id, workspace_id,
                    status="error",
                    error_message=self._sanitize_error_message(str(exc)),
                    completed_at=table_end,
                    duration_seconds=table_duration,
                )

            # --- Update run counters ----------------------------------
            if table_status == "completed":
                tables_passed += 1
            elif table_status == "error":
                tables_error += 1
            else:
                tables_failed += 1

            completed_count = idx + 1
            progress = int(completed_count / total_tables * 100)

            self.repo.update_run(
                run_id, workspace_id,
                tables_passed=tables_passed,
                tables_failed=tables_failed,
                tables_error=tables_error,
                progress_percentage=progress,
            )

            # Invalidate cache so next read gets fresh data
            self.cache.invalidate_run(run_id, workspace_id)
            self.cache.invalidate_table_result(run_id, table_name, workspace_id)

            table_duration_ms = int(
                (datetime.utcnow() - table_start).total_seconds() * 1000
            )
            logger.info(
                "Table validation completed",
                extra={
                    "event": "table_validation_completed",
                    "run_id": run_id,
                    "table_name": table_name,
                    "workspace_id": workspace_id,
                    "table_status": table_status,
                    "duration_ms": table_duration_ms,
                },
            )

        # 8. AI analysis for failed tables ---------------------------------
        bedrock_model = run.bedrock_model
        if bedrock_model:
            # Re-fetch table results to get updated statuses
            updated_table_results = self.repo.list_table_results(run_id, workspace_id)
            for tr in updated_table_results:
                if tr.status == "failed":
                    logger.info(
                        "AI analysis started for failed table",
                        extra={
                            "event": "ai_analysis_started",
                            "run_id": run_id,
                            "table_name": tr.table_name,
                            "model_id": bedrock_model,
                            "workspace_id": workspace_id,
                        },
                    )
                    ai_start = time.time()
                    analysis_result = self._run_bedrock_analysis(
                        table_name=tr.table_name,
                        ddl_result=tr.ddl_comparison_result,
                        row_count_result=tr.row_count_result,
                        data_match_result=tr.data_match_result,
                        bedrock_model=bedrock_model,
                        workspace_id=workspace_id,
                    )
                    ai_duration_ms = int((time.time() - ai_start) * 1000)
                    logger.info(
                        "AI analysis completed for table",
                        extra={
                            "event": "ai_analysis_completed",
                            "run_id": run_id,
                            "table_name": tr.table_name,
                            "model_id": bedrock_model,
                            "workspace_id": workspace_id,
                            "duration_ms": ai_duration_ms,
                            "has_result": analysis_result is not None,
                        },
                    )
                    self.repo.update_table_result(
                        tr.id, workspace_id,
                        ai_analysis=analysis_result,
                    )
                    self.cache.invalidate_table_result(run_id, tr.table_name, workspace_id)
        else:
            logger.info(
                "Skipping Bedrock analysis â€” no bedrock_model configured on run",
                extra={"run_id": run_id, "workspace_id": workspace_id},
            )

        # 9. Finalize run -------------------------------------------------
        run_end = datetime.utcnow()
        run_duration = int((run_end - run_start).total_seconds())

        if tables_error > 0:
            final_status = "error"
        elif tables_failed > 0:
            final_status = "failed"
        else:
            final_status = "completed"

        self.repo.update_run(
            run_id, workspace_id,
            status=final_status,
            progress_percentage=100,
            tables_passed=tables_passed,
            tables_failed=tables_failed,
            tables_error=tables_error,
            completed_at=run_end,
            duration_seconds=run_duration,
        )
        self.cache.invalidate_all_for_run(run_id, workspace_id)

        logger.info(
            "Validation run completed",
            extra={
                "event": "run_completed",
                "run_id": run_id,
                "workspace_id": workspace_id,
                "status": final_status,
                "tables_passed": tables_passed,
                "tables_failed": tables_failed,
                "tables_error": tables_error,
                "total_duration_seconds": run_duration,
            },
        )

        # 10. Credential cleanup â€” discard decrypted credentials from memory
        if target_conn_params:
            target_conn_params.pop("password", None)
            target_conn_params.pop("username", None)
        if source_conn_params:
            source_conn_params.pop("password", None)
            source_conn_params.pop("username", None)
        del target_conn_params
        del source_conn_params

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def get_run(self, run_id: int, workspace_id: int) -> Optional[Dict[str, Any]]:
        """Get a validation run by ID, checking cache first.

        Args:
            run_id: The validation run primary key.
            workspace_id: Tenant isolation identifier.

        Returns:
            Dict representation of the ValidationRun, or None if not found.
        """
        # Try cache first
        cached = self.cache.get_run(run_id, workspace_id)
        if cached is not None:
            return cached

        # Fallback to database
        run = self.repo.get_run(run_id, workspace_id)
        if run is None:
            return None

        run_dict = run.to_dict()

        # Cache for next time
        self.cache.set_run(run_id, workspace_id, run_dict)

        return run_dict

    def list_runs(
        self,
        workspace_id: int,
        migration_id: Optional[int] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        include_table_results: bool = False,
    ) -> Dict[str, Any]:
        """List validation runs with pagination and optional filters.

        Args:
            workspace_id: Tenant isolation identifier.
            migration_id: Optional filter by migration ID.
            status: Optional filter by run status.
            page: 1-based page number.
            page_size: Results per page (default 20, max 100).
            include_table_results: When True, include summary-level
                table result fields in each run response.

        Returns:
            Dict with 'runs' list, 'total', 'page', and 'page_size'.
        """
        if include_table_results:
            runs, total = self.repo.list_runs_with_table_results(
                workspace_id=workspace_id,
                migration_id=migration_id,
                status=status,
                page=page,
                page_size=page_size,
            )
            run_dicts = []
            for r in runs:
                d = r.to_dict()
                table_results = getattr(r, "_table_results", None)
                if table_results is not None:
                    d["table_results"] = [
                        {
                            "id": tr.id,
                            "run_id": tr.run_id,
                            "table_name": tr.table_name,
                            "dataset_name": tr.dataset_name,
                            "ddl_status": tr.ddl_status,
                            "row_count_status": tr.row_count_status,
                            "data_match_status": tr.data_match_status,
                            "status": tr.status,
                        }
                        for tr in table_results
                    ]
                else:
                    d["table_results"] = []
                run_dicts.append(d)
        else:
            runs, total = self.repo.list_runs(
                workspace_id=workspace_id,
                migration_id=migration_id,
                status=status,
                page=page,
                page_size=page_size,
            )
            run_dicts = [r.to_dict() for r in runs]

        return {
            "runs": run_dicts,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_table_results(self, run_id: int, workspace_id: int) -> Optional[List[Dict[str, Any]]]:
        """Get all table results for a validation run.

        Args:
            run_id: The parent validation run ID.
            workspace_id: Tenant isolation identifier.

        Returns:
            List of table result dicts, or None if the run doesn't exist.
        """
        # Verify run exists in this workspace
        run = self.repo.get_run(run_id, workspace_id)
        if run is None:
            return None

        results = self.repo.list_table_results(run_id, workspace_id)
        return [r.to_dict() for r in results]

    def get_table_detail(
        self, run_id: int, table_name: str, workspace_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get detailed table result including JSONB fields.

        Checks cache first, falls back to database.

        Args:
            run_id: The parent validation run ID.
            table_name: Name of the table to retrieve.
            workspace_id: Tenant isolation identifier.

        Returns:
            Dict with full table result including ddl_comparison_result,
            row_count_result, data_match_result, and ai_analysis.
            None if not found.
        """
        # Try cache first
        cached = self.cache.get_table_result(run_id, table_name, workspace_id)
        if cached is not None:
            return cached

        result = self.repo.get_table_result(run_id, table_name, workspace_id)
        if result is None:
            return None

        result_dict = result.to_dict()

        # Cache for next time
        self.cache.set_table_result(run_id, table_name, workspace_id, result_dict)

        return result_dict

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def get_report(self, run_id: int, workspace_id: int) -> Optional[Dict[str, Any]]:
        """Generate a full validation report for a completed run.

        Builds a ValidationReportResponse with overall summary and
        per-table details including DDL discrepancies, row count stats,
        record match summary, and AI analysis. Caches the report in
        Redis with TTL 30 minutes.

        Args:
            run_id: The validation run primary key.
            workspace_id: Tenant isolation identifier.

        Returns:
            Dict matching ValidationReportResponse schema, or None if
            the run is not found.
        """
        # Try cache first
        cached = self.cache.get_report(run_id, workspace_id)
        if cached is not None:
            return cached

        # Fetch run from database
        run = self.repo.get_run(run_id, workspace_id)
        if run is None:
            return None

        # Fetch connection names for traceability
        source_conn = (
            self.db.query(Connection)
            .filter(Connection.id == run.source_connection_id)
            .first()
        )
        target_conn = (
            self.db.query(Connection)
            .filter(Connection.id == run.target_connection_id)
            .first()
        )
        source_connection_name = source_conn.name if source_conn else "Unknown"
        target_connection_name = target_conn.name if target_conn else "Unknown"

        # Fetch all table results
        table_results = self.repo.list_table_results(run_id, workspace_id)

        # Determine overall status
        overall_status = self._compute_overall_status(run)

        # Build per-table detail dicts
        tables_detail = [tr.to_dict() for tr in table_results]

        report = {
            "run_id": run.id,
            "migration_id": run.migration_id,
            "source_connection_name": source_connection_name,
            "target_connection_name": target_connection_name,
            "overall_status": overall_status,
            "total_tables": run.tables_total,
            "tables_passed": run.tables_passed,
            "tables_failed": run.tables_failed,
            "tables_error": run.tables_error,
            "started_at": (run.started_at.isoformat() + "Z") if run.started_at else None,
            "completed_at": (run.completed_at.isoformat() + "Z") if run.completed_at else None,
            "duration_seconds": run.duration_seconds,
            "tables": tables_detail,
        }

        # Cache the report (TTL 30 min)
        self.cache.set_report(run_id, workspace_id, report)

        logger.info(
            "Validation report generated",
            extra={
                "run_id": run_id,
                "workspace_id": workspace_id,
                "overall_status": overall_status,
                "total_tables": run.tables_total,
            },
        )

        return report

    @staticmethod
    def _compute_overall_status(run) -> str:
        """Determine overall report status from run summary counters.

        Returns 'passed' when all tables passed, otherwise 'failed'.
        """
        if run.tables_error > 0 or run.status == "error":
            return "error"
        if run.tables_failed > 0 or run.status == "failed":
            return "failed"
        if run.status == "completed" and run.tables_passed == run.tables_total:
            return "passed"
        # Still running or pending
        return run.status

    # ------------------------------------------------------------------
    # DDL schema comparison
    # ------------------------------------------------------------------

    def _validate_ddl(
        self,
        run_id: int,
        table_name: str,
        dataset_name: str,
        assessment_id: int,
        target_conn_params: dict,
        type_mapping_overrides: dict,
        workspace_id: int,
    ) -> dict:
        """Compare source schema metadata against target schema metadata.

        Retrieves source column metadata from AssessmentColumn records and
        queries the Redshift target to get actual column metadata, then
        compares each column for type equivalence, nullability, and
        presence using the DataTypeMapper.

        Args:
            run_id: Parent validation run ID (for logging).
            table_name: Name of the table to compare.
            dataset_name: BigQuery dataset name (used as Redshift schema).
            assessment_id: Assessment ID to look up source columns.
            target_conn_params: Decrypted Redshift connection parameters.
            type_mapping_overrides: Optional BQâ†’Redshift type overrides.
            workspace_id: Tenant isolation identifier.

        Returns:
            Dict with keys ``status`` ('passed', 'failed', or 'error')
            and ``result`` (the JSONB-ready comparison dict).
        """
        ddl_start = time.time()

        logger.info(
            "DDL comparison started",
            extra={
                "event": "ddl_comparison_started",
                "run_id": run_id,
                "table_name": table_name,
                "workspace_id": workspace_id,
            },
        )

        try:
            # --- 1. Retrieve source columns from Assessment ---------------
            source_columns = self._get_source_columns(
                assessment_id, dataset_name, table_name, workspace_id,
            )

            # --- 2. Retrieve target columns from Redshift -----------------
            target_schema = (
                target_conn_params.get("_validation_namespace")
                or dataset_name
            )
            target_columns = self._get_target_columns(
                target_conn_params, target_schema, table_name,
            )

            # --- 3. Build type mapper with overrides ----------------------
            mapper = DataTypeMapper(overrides=type_mapping_overrides or None)

            # --- 4. Compare columns ---------------------------------------
            discrepancies: List[Dict[str, Any]] = []

            source_by_name = {
                col["column_name"].lower(): col for col in source_columns
            }
            target_by_name = {
                col["column_name"].lower(): col for col in target_columns
            }

            all_column_names = set(source_by_name.keys()) | set(target_by_name.keys())

            for col_name in all_column_names:
                src = source_by_name.get(col_name)
                tgt = target_by_name.get(col_name)

                if src and not tgt:
                    discrepancies.append({
                        "type": "missing_column",
                        "column_name": src["column_name"],
                        "source_type": src["data_type"],
                        "target_type": None,
                        "expected_type": mapper.get_expected_redshift_type(src["data_type"]),
                    })
                    continue

                if tgt and not src:
                    discrepancies.append({
                        "type": "extra_column",
                        "column_name": tgt["column_name"],
                        "source_type": None,
                        "target_type": tgt["data_type"],
                        "expected_type": None,
                    })
                    continue

                # Both exist â€“ check type equivalence
                if not self._types_equivalent(src["data_type"], tgt["data_type"]):
                    discrepancies.append({
                        "type": "type_mismatch",
                        "column_name": src["column_name"],
                        "source_type": src["data_type"],
                        "target_type": tgt["data_type"],
                        "expected_type": None,
                    })

                # Check nullability
                src_nullable = src.get("is_nullable")
                tgt_nullable = tgt.get("is_nullable")
                if (
                    src_nullable is not None
                    and tgt_nullable is not None
                    and src_nullable != tgt_nullable
                ):
                    discrepancies.append({
                        "type": "nullability_mismatch",
                        "column_name": src["column_name"],
                        "source_type": str(src_nullable),
                        "target_type": str(tgt_nullable),
                        "expected_type": None,
                    })

            result = {
                "discrepancies": discrepancies,
                "source_column_count": len(source_columns),
                "target_column_count": len(target_columns),
                "columns_compared": len(all_column_names),
            }

            status = "passed" if len(discrepancies) == 0 else "failed"

            ddl_duration_ms = int((time.time() - ddl_start) * 1000)
            logger.info(
                "DDL comparison completed",
                extra={
                    "event": "ddl_comparison_completed",
                    "run_id": run_id,
                    "table_name": table_name,
                    "workspace_id": workspace_id,
                    "status": status,
                    "discrepancy_count": len(discrepancies),
                    "duration_ms": ddl_duration_ms,
                },
            )

            return {"status": status, "result": result}

        except Exception as exc:
            ddl_duration_ms = int((time.time() - ddl_start) * 1000)
            logger.error(
                "DDL comparison error",
                extra={
                    "event": "ddl_comparison_completed",
                    "run_id": run_id,
                    "table_name": table_name,
                    "workspace_id": workspace_id,
                    "error": self._sanitize_error_message(str(exc)),
                    "traceback": traceback.format_exc(),
                    "duration_ms": ddl_duration_ms,
                },
            )
            return {
                "status": "error",
                "result": {
                    "discrepancies": [],
                    "source_column_count": 0,
                    "target_column_count": 0,
                    "columns_compared": 0,
                },
                "error_message": self._sanitize_error_message(str(exc)),
            }
    # ------------------------------------------------------------------
    # Validation database type helper
    # ------------------------------------------------------------------


    # ------------------------------------------------------------------
    # Multi-database validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_database_type(conn_params: dict) -> str:
        """Normalize the database engine type from connection params.

        Resolution order (first match wins):
        1. An explicit engine key (database_type/db_type/connection_type/
           engine/service/type).
        2. The ``database`` field, if it names a known engine.
        3. Inference from telltale signals (endpoint hostname, port, param
           keys) — so a connection whose engine label is missing/mislabeled
           still resolves instead of raising "unsupported type".

        Returns a canonical engine key (e.g. "redshift", "postgresql",
        "sqlserver", ...) or "" if it genuinely cannot be determined.
        """
        # Canonical alias map, shared by every lookup below.
        alias = {
            "mongo": "mongodb",
            "mongodb": "mongodb",
            "documentdb": "documentdb",
            "amazon_documentdb": "documentdb",
            "amazon documentdb": "documentdb",
            "postgres": "postgresql",
            "postgresql": "postgresql",
            "mysql": "mysql",
            "mariadb": "mysql",
            "oracle": "oracle",
            "sql_server": "sqlserver",
            "sqlserver": "sqlserver",
            "sql server": "sqlserver",
            "mssql": "sqlserver",
            "microsoft sql server": "sqlserver",
            "bigquery": "bigquery",
            "big_query": "bigquery",
            "clickhouse": "clickhouse",
            "redshift": "redshift",
            "amazon redshift": "redshift",
            "sybase": "sybase",
            "sap_sybase": "sybase",
            "sap sybase": "sybase",
            "db2": "db2",
            "ibm_db2": "db2",
            "ibm db2": "db2",
        }

        def _canon(v) -> str:
            key = str(v or "").strip().lower()
            if key in alias:
                return alias[key]
            key2 = key.replace("-", "_").replace(" ", "_")
            return alias.get(key2, "")

        # 1. Explicit engine keys
        for field in (
            "database_type", "db_type", "connection_type",
            "engine", "service", "type",
        ):
            resolved = _canon(conn_params.get(field))
            if resolved:
                return resolved

        # 2. The 'database' field, only if it names a known engine
        resolved = _canon(conn_params.get("database"))
        if resolved:
            return resolved

        # 3. Inference from telltale signals (hostname / port / param keys)
        host = str(
            conn_params.get("host")
            or conn_params.get("server_name")
            or conn_params.get("cluster")
            or conn_params.get("endpoint")
            or ""
        ).lower()
        if ".redshift.amazonaws.com" in host or "redshift-serverless" in host:
            return "redshift"
        if ".rds.amazonaws.com" in host:
            # RDS covers several engines; disambiguate by port if possible.
            pass
        if ".docdb.amazonaws.com" in host:
            return "documentdb"

        # BigQuery is identified by service-account credentials + project id
        if (
            conn_params.get("credentials_json")
            or conn_params.get("service_account_key")
            or conn_params.get("serviceAccountKey")
            or conn_params.get("project_id")
            or conn_params.get("projectId")
        ):
            return "bigquery"

        # MongoDB-style URI
        uri = str(conn_params.get("uri") or conn_params.get("connection_string") or "").lower()
        if uri.startswith("mongodb://") or uri.startswith("mongodb+srv://"):
            return "mongodb"

        # Port-based inference (last resort)
        try:
            port = int(conn_params.get("port") or 0)
        except (TypeError, ValueError):
            port = 0
        port_map = {
            5439: "redshift",
            5432: "postgresql",
            3306: "mysql",
            1433: "sqlserver",
            1521: "oracle",
            27017: "mongodb",
            8123: "clickhouse",
            8443: "clickhouse",
            50000: "db2",
            5000: "sybase",
        }
        if port in port_map:
            return port_map[port]

        # Could not determine — return "" so callers can raise a clear error.
        return ""

    @staticmethod
    def _quote_identifier(name: str, database_type: str) -> str:
        if not name or not re.match(r"^[A-Za-z_][A-Za-z0-9_$]*$", str(name)):
            raise ValueError(f"Invalid identifier: {name}")
        if database_type == "mysql":
            return f"`{name}`"
        if database_type == "sqlserver":
            return f"[{name}]"
        return f'"{name}"'

    @classmethod
    def _qualified_table(cls, database_type: str, dataset_name: str, table_name: str) -> str:
        db = database_type
        table = cls._quote_identifier(table_name, db)
        if db == "mysql":
            return f"{cls._quote_identifier(dataset_name, db)}.{table}" if dataset_name else table
        schema = dataset_name or "public"
        return f"{cls._quote_identifier(schema, db)}.{table}"

    @staticmethod
    def _sql_connection(conn_params: dict, database_type: str, timeout: int = 30):
        db = database_type
        host = (
            conn_params.get("host")
            or conn_params.get("server_name")
            or conn_params.get("cluster")
            or conn_params.get("endpoint")
        )
        user = conn_params.get("username") or conn_params.get("user")
        password = conn_params.get("password")
        database = (
            conn_params.get("database_name")
            or conn_params.get("database")
            or conn_params.get("db_name")
        )
        default_ports = {
            "postgresql": 5432, "redshift": 5439, "mysql": 3306,
            "oracle": 1521, "sqlserver": 1433, "sybase": 5000, "db2": 50000,
        }
        port = int(conn_params.get("port") or default_ports.get(db, 0))

        if db in ("postgresql", "redshift"):
            return psycopg2.connect(
                host=host,
                port=port,
                database=database or ("dev" if db == "redshift" else None),
                user=user,
                password=password,
                connect_timeout=timeout,
                options=f"-c statement_timeout={timeout * 1000}",
            )
        if db == "mysql":
            return pymysql.connect(
                host=host, port=port, user=user, password=password,
                database=database or None, connect_timeout=timeout,
                read_timeout=timeout, write_timeout=timeout,
            )
        if db in ("oracle", "sqlserver", "sybase", "db2"):
            dsn = conn_params.get("dsn") or conn_params.get("data_source")
            driver = conn_params.get("driver") or conn_params.get("odbc_driver")
            if not dsn:
                driver = driver or {
                    "sqlserver": "ODBC Driver 18 for SQL Server",
                    "oracle": "Oracle in OraDB19Home1",
                    "sybase": "Adaptive Server Enterprise",
                    "db2": "IBM DB2 ODBC DRIVER",
                }[db]
                if not host:
                    raise ValueError(f"{db} host is missing")
                server = f"{host},{port}" if db == "sqlserver" else f"{host}:{port}"
                parts = [f"DRIVER={{{driver}}}", f"SERVER={server}"]
                if database:
                    parts.append(f"DATABASE={database}")

                windows_auth = bool(
                    conn_params.get("windows_auth")
                    or conn_params.get("windows_authentication")
                    or conn_params.get("trusted_connection")
                )
                if db == "sqlserver" and windows_auth and not user:
                    parts.append("Trusted_Connection=yes")
                else:
                    if user:
                        parts.append(f"UID={user}")
                    if password is not None:
                        parts.append(f"PWD={password}")

                if db == "sqlserver":
                    encrypt = conn_params.get("encrypt")
                    if encrypt is not None:
                        parts.append(f"Encrypt={'yes' if bool(encrypt) else 'no'}")
                    trust_server_certificate = conn_params.get("trust_server_certificate")
                    if trust_server_certificate is not None:
                        parts.append(
                            f"TrustServerCertificate={'yes' if bool(trust_server_certificate) else 'no'}"
                        )
                dsn = ";".join(parts)
            return pyodbc.connect(dsn, timeout=timeout)
        if not db:
            raise ValueError(
                "Could not determine the database engine for this connection. "
                "Ensure the connection's type is set (e.g. redshift, postgresql, "
                "sqlserver, mysql)."
            )
        raise ValueError(
            f"Unsupported SQL database type: '{db}'. Supported SQL engines: "
            "postgresql, redshift, mysql, sqlserver, oracle, sybase, db2."
        )

    @staticmethod
    def _mongo_client(conn_params: dict):
        uri = (
            conn_params.get("uri")
            or conn_params.get("connection_string")
            or conn_params.get("connectionString")
        )
        kwargs = {"serverSelectionTimeoutMS": 30000}
        tls = conn_params.get("tls", conn_params.get("ssl"))
        if tls is not None:
            kwargs["tls"] = bool(tls)
        ca_file = conn_params.get("tlsCAFile") or conn_params.get("tls_ca_file") or conn_params.get("ca_file")
        if ca_file:
            kwargs["tlsCAFile"] = ca_file
        if not uri:
            host = conn_params.get("host") or conn_params.get("server_name") or conn_params.get("endpoint")
            port = int(conn_params.get("port") or 27017)
            user = conn_params.get("username") or conn_params.get("user")
            password = conn_params.get("password")
            if not host:
                raise ValueError("MongoDB/DocumentDB host is missing")
            auth = f"{user}:{password}@" if user else ""
            uri = f"mongodb://{auth}{host}:{port}/"
        return MongoClient(uri, **kwargs)

    @staticmethod
    def _clickhouse_client(conn_params: dict):
        return clickhouse_connect.get_client(
            host=conn_params.get("host") or conn_params.get("server_name") or conn_params.get("endpoint"),
            port=int(conn_params.get("port") or 8123),
            username=conn_params.get("username") or conn_params.get("user") or "default",
            password=conn_params.get("password") or "",
            database=conn_params.get("database_name") or conn_params.get("database") or "default",
        )

    @staticmethod
    def _get_bigquery_client(conn_params: dict):
        credentials_json = (
            conn_params.get("credentials_json")
            or conn_params.get("service_account_key")
            or conn_params.get("serviceAccountKey")
            or conn_params.get("credentialsJson")
            or conn_params.get("credentials")
        )
        if isinstance(credentials_json, str):
            credentials_json = json.loads(credentials_json)
        project_id = (
            conn_params.get("project_id")
            or conn_params.get("projectId")
            or (credentials_json.get("project_id") if credentials_json else None)
        )
        if not credentials_json or not project_id:
            raise ValueError("BigQuery credentials/project_id not found in connection params")
        credentials = service_account.Credentials.from_service_account_info(credentials_json)
        return bigquery.Client(credentials=credentials, project=project_id), project_id

    def _get_database_row_count(
        self, conn_params: dict, database_type: str,
        dataset_name: str, table_name: str, timeout: int = 300,
    ) -> int:
        db = self._get_database_type({**conn_params, "database_type": database_type})
        dataset_name = conn_params.get("_validation_namespace") or dataset_name
        if db == "bigquery":
            client, project_id = self._get_bigquery_client(conn_params)
            rows = list(client.query(
                f"SELECT COUNT(*) FROM `{project_id}.{dataset_name}.{table_name}`"
            ).result(timeout=timeout))
            return int(rows[0][0]) if rows else 0
        if db in ("mongodb", "documentdb"):
            client = self._mongo_client(conn_params)
            try:
                db_name = conn_params.get("database_name") or conn_params.get("database") or dataset_name
                return int(client[db_name][table_name].count_documents({}))
            finally:
                client.close()
        if db == "clickhouse":
            client = self._clickhouse_client(conn_params)
            try:
                ref = self._qualified_table(db, dataset_name, table_name)
                rows = client.query(f"SELECT count() FROM {ref}").result_rows
                return int(rows[0][0]) if rows else 0
            finally:
                client.close()
        conn = self._sql_connection(conn_params, db, timeout=min(timeout, 60))
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {self._qualified_table(db, dataset_name, table_name)}")
                row = cur.fetchone()
                return int(row[0]) if row else 0
        finally:
            conn.close()

    @staticmethod
    def _normalize_data_type(value: Any) -> str:
        s = re.sub(r"\([^)]*\)", "", str(value or "").upper().strip())
        groups = {
            "STRING": ("CHAR", "CLOB", "TEXT", "STRING", "VARCHAR", "NVARCHAR"),
            "INTEGER": ("INT", "BIGINT", "SMALLINT", "TINYINT", "INTEGER"),
            "DECIMAL": ("DECIMAL", "NUMERIC", "NUMBER", "MONEY", "FLOAT", "DOUBLE", "REAL"),
            "BOOLEAN": ("BOOL", "BOOLEAN"),
            "DATE": ("DATE",),
            "DATETIME": ("TIMESTAMP", "DATETIME", "TIME"),
            "BINARY": ("BINARY", "BLOB", "VARBINARY", "BYTEA"),
        }
        for canonical, members in groups.items():
            if any(member in s for member in members):
                return canonical
        return s

    @classmethod
    def _types_equivalent(cls, source_type: Any, target_type: Any) -> bool:
        return cls._normalize_data_type(source_type) == cls._normalize_data_type(target_type)

    @classmethod
    def _get_database_columns(cls, conn_params: dict, database_type: str, dataset_name: str, table_name: str) -> List[Dict[str, Any]]:
        db = cls._get_database_type({**conn_params, "database_type": database_type})
        dataset_name = conn_params.get("_validation_namespace") or dataset_name
        if db == "bigquery":
            client, project_id = cls._get_bigquery_client(conn_params)
            table = client.get_table(f"{project_id}.{dataset_name}.{table_name}")
            return [
                {"column_name": f.name, "data_type": f.field_type,
                 "is_nullable": f.mode != "REQUIRED", "ordinal_position": i + 1}
                for i, f in enumerate(table.schema)
            ]
        if db in ("mongodb", "documentdb"):
            client = cls._mongo_client(conn_params)
            try:
                db_name = conn_params.get("database_name") or conn_params.get("database") or dataset_name
                docs = list(client[db_name][table_name].find({}).limit(200))
                fields = {}
                for doc in docs:
                    for key, value in doc.items():
                        if key not in fields:
                            fields[key] = {
                                "column_name": key,
                                "data_type": type(value).__name__.upper() if value is not None else "NULL",
                                "is_nullable": None,
                                "ordinal_position": len(fields) + 1,
                            }
                return list(fields.values())
            finally:
                client.close()
        if db == "clickhouse":
            client = cls._clickhouse_client(conn_params)
            try:
                result = client.query(
                    f"DESCRIBE TABLE {cls._qualified_table(db, dataset_name, table_name)}"
                )
                return [
                    {"column_name": r[0], "data_type": r[1],
                     "is_nullable": None, "ordinal_position": i + 1}
                    for i, r in enumerate(result.result_rows)
                ]
            finally:
                client.close()

        conn = cls._sql_connection(conn_params, db)
        try:
            with conn.cursor() as cur:
                if db == "oracle":
                    cur.execute(
                        "SELECT column_name, data_type, nullable, column_id "
                        "FROM all_tab_columns WHERE owner = ? AND table_name = ? ORDER BY column_id",
                        (str(dataset_name).upper(), str(table_name).upper()),
                    )
                elif db == "db2":
                    cur.execute(
                        "SELECT COLNAME, TYPENAME, NULLS, COLNO "
                        "FROM SYSCAT.COLUMNS WHERE TABSCHEMA = ? AND TABNAME = ? ORDER BY COLNO",
                        (str(dataset_name).upper(), str(table_name).upper()),
                    )
                elif db in ("postgresql", "redshift", "mysql"):
                    # psycopg2 and pymysql use %s as the parameter placeholder.
                    cur.execute(
                        "SELECT column_name, data_type, is_nullable, ordinal_position "
                        "FROM information_schema.columns "
                        "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
                        (dataset_name, table_name),
                    )
                else:
                    # pyodbc-based engines (sqlserver, sybase, etc.) use ? placeholders.
                    cur.execute(
                        "SELECT column_name, data_type, is_nullable, ordinal_position "
                        "FROM information_schema.columns "
                        "WHERE table_schema = ? AND table_name = ? ORDER BY ordinal_position",
                        (dataset_name, table_name),
                    )
                rows = cur.fetchall()
                result = []
                for i, row in enumerate(rows, 1):
                    nullable = row[2]
                    if isinstance(nullable, str):
                        nullable = nullable.upper() in ("YES", "Y", "TRUE")
                    result.append({
                        "column_name": row[0],
                        "data_type": str(row[1]).upper(),
                        "is_nullable": bool(nullable),
                        "ordinal_position": row[3] or i,
                    })
                return result
        finally:
            conn.close()

    @classmethod
    def _read_database_rows(
        cls, conn_params: dict, database_type: str,
        dataset_name: str, table_name: str, batch_size: int,
        order_by: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        db = cls._get_database_type({**conn_params, "database_type": database_type})
        dataset_name = conn_params.get("_validation_namespace") or dataset_name
        if db == "bigquery":
            client, project_id = cls._get_bigquery_client(conn_params)
            order_sql = ""
            if order_by:
                if not re.match(r"^[A-Za-z_][A-Za-z0-9_$]*$", str(order_by)):
                    raise ValueError(f"Invalid order-by column: {order_by}")
                order_sql = f" ORDER BY `{order_by}`"
            result = client.query(
                f"SELECT * FROM `{project_id}.{dataset_name}.{table_name}`{order_sql}"
            ).result(page_size=batch_size)
            return [{k.lower(): v for k, v in dict(row).items()} for row in result]
        if db in ("mongodb", "documentdb"):
            client = cls._mongo_client(conn_params)
            try:
                db_name = conn_params.get("database_name") or conn_params.get("database") or dataset_name
                cursor = client[db_name][table_name].find({})
                if order_by:
                    cursor = cursor.sort(order_by, 1)
                else:
                    cursor = cursor.sort("_id", 1)
                return [
                    {str(k).lower(): v for k, v in doc.items()}
                    for doc in cursor
                ]
            finally:
                client.close()
        if db == "clickhouse":
            client = cls._clickhouse_client(conn_params)
            try:
                order_sql = ""
                if order_by:
                    if not re.match(r"^[A-Za-z_][A-Za-z0-9_$]*$", str(order_by)):
                        raise ValueError(f"Invalid order-by column: {order_by}")
                    order_sql = f" ORDER BY {cls._quote_identifier(order_by, db)}"
                result = client.query(
                    f"SELECT * FROM {cls._qualified_table(db, dataset_name, table_name)}{order_sql}"
                )
                names = [c.lower() for c in result.column_names]
                return [dict(zip(names, row)) for row in result.result_rows]
            finally:
                client.close()
        conn = cls._sql_connection(conn_params, db)
        try:
            with conn.cursor() as cur:
                query = f"SELECT * FROM {cls._qualified_table(db, dataset_name, table_name)}"
                if order_by:
                    if not re.match(r"^[A-Za-z_][A-Za-z0-9_$]*$", str(order_by)):
                        raise ValueError(f"Invalid order-by column: {order_by}")
                    query += f" ORDER BY {cls._quote_identifier(order_by, db)}"
                cur.execute(query)
                names = [d[0].lower() for d in cur.description]
                rows = []
                while True:
                    batch = cur.fetchmany(batch_size)
                    if not batch:
                        break
                    rows.extend(dict(zip(names, row)) for row in batch)
                return rows
        finally:
            conn.close()
    def _validate_row_count(
        self,
        run_id: int,
        table_name: str,
        dataset_name: str,
        source_conn_params: dict,
        target_conn_params: dict,
        workspace_id: int,
    ) -> dict:
        """Compare row counts between the configured source and target databases.

        Queries both databases for the current row count of the given
        table, compares them, and returns a status with detailed results.

        Args:
            run_id: Parent validation run ID (for logging).
            table_name: Name of the table to validate.
            dataset_name: BigQuery dataset name (used as Redshift schema).
            source_conn_params: Decrypted BigQuery connection parameters
                containing credentials_json and project_id.
            target_conn_params: Decrypted Redshift connection parameters.
            workspace_id: Tenant isolation identifier.

        Returns:
            Dict with keys ``status`` ('passed', 'failed', or 'error')
            and ``result`` (the JSONB-ready row count dict).
        """
        ROW_COUNT_TIMEOUT = 300  # seconds
        rc_start = time.time()
        source_database_type = self._get_database_type(
        source_conn_params
        )

        target_database_type = self._get_database_type(
        target_conn_params
        )

        logger.info(
            "Row count validation started",
            extra={
                "event": "row_count_started",
                "run_id": run_id,
                "table_name": table_name,
                "workspace_id": workspace_id,
            },
        )

        # --- 1. Query source (BigQuery) row count ------------------------
        try:
            source_count = self._get_database_row_count(
                conn_params=source_conn_params,
                database_type=source_database_type,
                dataset_name=dataset_name,
                table_name=table_name,
                timeout=ROW_COUNT_TIMEOUT,
        )
        except Exception as exc:
            rc_duration_ms = int((time.time() - rc_start) * 1000)
            is_timeout = "timeout" in str(exc).lower()
            if is_timeout:
                logger.error(
                    "Row count source query timeout",
                    extra={
                        "event": "connection_timeout",
                        "run_id": run_id,
                        "table_name": table_name,
                        "workspace_id": workspace_id,
                        "query_type": "source_row_count",
                        "timeout_seconds": ROW_COUNT_TIMEOUT,
                    },
                )
            error_msg = (
                f"Source ({source_database_type}) "
                f"row count query failed: {exc}"
                )
            logger.error(
                "Row count source query error",
                extra={
                    "event": "row_count_completed",
                    "run_id": run_id,
                    "table_name": table_name,
                    "workspace_id": workspace_id,
                    "error": self._sanitize_error_message(str(exc)),
                    "traceback": traceback.format_exc(),
                    "duration_ms": rc_duration_ms,
                },
            )
            return {
                "status": "error",
                "result": {
                    "source_count": None,
                    "target_count": None,
                    "difference": None,
                    "percentage_difference": None,
                },
                "error_message": self._sanitize_error_message(error_msg),
            }

        # --- 2. Query target (Redshift) row count ------------------------
        try:
            target_count = self._get_database_row_count(
                conn_params=target_conn_params,
                database_type=target_database_type,
                dataset_name=dataset_name,
                table_name=table_name,
                timeout=ROW_COUNT_TIMEOUT,
            )
        except Exception as exc:
            rc_duration_ms = int((time.time() - rc_start) * 1000)
            is_timeout = "timeout" in str(exc).lower()
            if is_timeout:
                logger.error(
                    "Row count target query timeout",
                    extra={
                        "event": "connection_timeout",
                        "run_id": run_id,
                        "table_name": table_name,
                        "workspace_id": workspace_id,
                        "query_type": "target_row_count",
                        "timeout_seconds": ROW_COUNT_TIMEOUT,
                    },
                )
            error_msg = (
                f"Target ({target_database_type}) "
                f"row count query failed: {exc}"
                )
            logger.error(
                "Row count target query error",
                extra={
                    "event": "row_count_completed",
                    "run_id": run_id,
                    "table_name": table_name,
                    "workspace_id": workspace_id,
                    "error": self._sanitize_error_message(str(exc)),
                    "traceback": traceback.format_exc(),
                    "duration_ms": rc_duration_ms,
                },
            )
            return {
                "status": "error",
                "result": {
                    "source_count": source_count,
                    "target_count": None,
                    "difference": None,
                    "percentage_difference": None,
                },
                "error_message": self._sanitize_error_message(error_msg),
            }

        # --- 3. Compare counts -------------------------------------------
        difference = abs(source_count - target_count)

        if source_count > 0:
            percentage_difference = round(difference / source_count * 100, 5)
        elif target_count == 0:
            # Both are zero
            percentage_difference = 0.0
        else:
            # source is 0 but target is not
            percentage_difference = 100.0

        status = "passed" if source_count == target_count else "failed"

        result = {
            "source_count": source_count,
            "target_count": target_count,
            "difference": difference,
            "percentage_difference": percentage_difference,
        }

        logger.info(
            "Row count validation completed",
            extra={
                "event": "row_count_completed",
                "run_id": run_id,
                "table_name": table_name,
                "workspace_id": workspace_id,
                "status": status,
                "source_count": source_count,
                "target_count": target_count,
                "duration_ms": int((time.time() - rc_start) * 1000),
            },
        )

        return {"status": status, "result": result}

    # ------------------------------------------------------------------
    # Row count helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_bigquery_row_count(
        conn_params: dict,
        dataset_name: str,
        table_name: str,
        timeout: int = 300,
    ) -> int:
        """Query BigQuery for the row count of a table.

        Creates a short-lived BigQuery client using the service account
        credentials from the connection parameters.

        Args:
            conn_params: Dict with credentials_json (str or dict) and
                         project_id.
            dataset_name: BigQuery dataset name.
            table_name: BigQuery table name.
            timeout: Query timeout in seconds.

        Returns:
            Integer row count.
        """
        credentials_json = (
            conn_params.get("credentials_json")
            or conn_params.get("service_account_key")
            or conn_params.get("serviceAccountKey")
            or conn_params.get("credentialsJson")
            or conn_params.get("credentials")
        )
        if isinstance(credentials_json, str):
            credentials_json = json.loads(credentials_json)

        project_id = (
            conn_params.get("project_id")
            or conn_params.get("projectId")
            or (credentials_json.get("project_id") if credentials_json else None)
        )

        if not credentials_json:
            raise ValueError("BigQuery credentials not found in source connection params")
        if not project_id:
            raise ValueError("BigQuery project_id not found in source connection params")

        credentials = service_account.Credentials.from_service_account_info(credentials_json)
        client = bigquery.Client(credentials=credentials, project=project_id)

        query = f"SELECT COUNT(*) FROM `{project_id}.{dataset_name}.{table_name}`"
        job_config = bigquery.QueryJobConfig()
        job = client.query(query, job_config=job_config, timeout=timeout)
        rows = list(job.result(timeout=timeout))

        return rows[0][0] if rows else 0

    @staticmethod
    def _get_redshift_row_count(
        conn_params: dict,
        schema_name: str,
        table_name: str,
        timeout: int = 300,
    ) -> int:
        """Query Redshift for the row count of a table.

        Opens a short-lived psycopg2 connection using the provided
        (already-decrypted) connection parameters.

        Args:
            conn_params: Dict with host, port, database, username,
                         password keys.
            schema_name: Redshift schema name.
            table_name: Redshift table name.
            timeout: Query timeout in seconds.

        Returns:
            Integer row count.
        """
        host = (
            conn_params.get("host")
            or conn_params.get("server_name")
            or conn_params.get("cluster")
            or conn_params.get("endpoint")
        )
        port = int(conn_params.get("port", 5439))
        database = (
            conn_params.get("database")
            or conn_params.get("database_name")
            or "dev"
        )
        username = conn_params.get("username")
        password = conn_params.get("password")

        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=username,
            password=password,
            connect_timeout=30,
            options=f"-c statement_timeout={timeout * 1000}",
        )
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) FROM {schema_name}.{table_name}",
                )
                row = cur.fetchone()
        finally:
            conn.close()

        return row[0] if row else 0


    @staticmethod
    def _get_postgresql_row_count(
        conn_params: dict,
        schema_name: str,
        table_name: str,
        timeout: int = 300,
    ) -> int:
        """Return the row count for a PostgreSQL table."""

        host = (
            conn_params.get("host")
            or conn_params.get("server_name")
            or conn_params.get("endpoint")
        )

        port = int(conn_params.get("port", 5432))

        database = (
            conn_params.get("database")
            or conn_params.get("database_name")
        )

        username = (
            conn_params.get("username")
            or conn_params.get("user")
        )

        password = conn_params.get("password")

        if not host:
            raise ValueError("PostgreSQL host is missing")

        if not database:
            raise ValueError("PostgreSQL database is missing")

        if not username:
            raise ValueError("PostgreSQL username is missing")

        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=username,
            password=password,
            connect_timeout=30,
            options=f"-c statement_timeout={timeout * 1000}",
        )

        try:
            with conn.cursor() as cur:
                cur.execute(
                    f'SELECT COUNT(*) FROM "{schema_name}"."{table_name}"'
                )
                row = cur.fetchone()
        finally:
            conn.close()

        return int(row[0]) if row else 0
    # ------------------------------------------------------------------
    # DDL helpers
    # ------------------------------------------------------------------

    def _get_source_columns(
        self,
        assessment_id: int,
        dataset_name: str,
        table_name: str,
        workspace_id: int,
    ) -> List[Dict[str, Any]]:
        """Retrieve source column metadata from AssessmentColumn records.

        Joins AssessmentTable to locate the correct table within the
        assessment, then returns all columns for that table.

        Args:
            assessment_id: The assessment to query.
            dataset_name: BigQuery dataset name.
            table_name: BigQuery table name.
            workspace_id: Tenant isolation identifier.

        Returns:
            List of dicts with column_name, data_type, is_nullable,
            ordinal_position.

        Raises:
            ValueError: If the assessment table is not found.
        """
        assessment_table = (
            self.db.query(AssessmentTable)
            .filter(
                AssessmentTable.assessment_id == assessment_id,
                AssessmentTable.dataset_name == dataset_name,
                AssessmentTable.table_name == table_name,
            )
            .first()
        )
        if not assessment_table:
            raise ValueError(
                f"Assessment table not found for assessment_id={assessment_id}, "
                f"dataset={dataset_name}, table={table_name}"
            )

        columns = (
            self.db.query(AssessmentColumn)
            .filter(
                AssessmentColumn.assessment_id == assessment_id,
                AssessmentColumn.table_id == assessment_table.id,
            )
            .order_by(AssessmentColumn.ordinal_position)
            .all()
        )

        return [
            {
                "column_name": col.column_name,
                "data_type": col.data_type,
                "is_nullable": col.is_nullable if col.is_nullable is not None else True,
                "ordinal_position": col.ordinal_position,
            }
            for col in columns
        ]

    @classmethod
    def _get_target_columns(
        cls,
        conn_params: dict,
        schema_name: str,
        table_name: str,
    ) -> List[Dict[str, Any]]:
        """Return target column metadata for any supported validation database."""
        return cls._get_database_columns(
            conn_params,
            cls._get_database_type(conn_params),
            schema_name,
            table_name,
        )

    # ------------------------------------------------------------------
    # Record-level data matching
    # ------------------------------------------------------------------

    def _validate_records(
        self,
        run_id: int,
        table_name: str,
        dataset_name: str,
        source_conn_params: dict,
        target_conn_params: dict,
        primary_key: list,
        batch_size: int,
        type_mapping_overrides: dict,
        workspace_id: int,
        specific_row_start: Optional[int] = None,
        specific_row_end: Optional[int] = None,
    ) -> dict:
        """Compare source records against target records across supported databases.

        Reads data in configurable batches from both databases, matches
        rows by primary key (or hash of all columns when no PK is
        available), and detects missing, extra, and mismatched records.

        Args:
            run_id: Parent validation run ID (for logging).
            table_name: Name of the table to compare.
            dataset_name: Fallback namespace; source/target connection params may override it.
            source_conn_params: Decrypted source connection parameters.
            target_conn_params: Decrypted target connection parameters.
            primary_key: List of PK column names. If empty/None, a hash
                         of all column values is used as the row key.
            batch_size: Number of rows per batch (default 10000).
            type_mapping_overrides: Optional type comparison overrides for
                                    type-aware comparison.
            workspace_id: Tenant isolation identifier.

        Returns:
            Dict with keys ``status`` ('passed', 'failed', or 'error')
            and ``result`` (the JSONB-ready data match dict).
        """
        MAX_SAMPLE_DISCREPANCIES = 100
        rec_start = time.time()

        logger.info(
            "Record-level matching started",
            extra={
                "event": "record_match_started",
                "run_id": run_id,
                "table_name": table_name,
                "workspace_id": workspace_id,
                "batch_size": batch_size,
            },
        )

        use_hash_key = not primary_key
        if use_hash_key:
            logger.warning(
                "No primary key found for table, using hash of all columns",
                extra={
                    "run_id": run_id,
                    "table_name": table_name,
                    "workspace_id": workspace_id,
                },
            )

        try:
            # Specific Row means: select a deterministic range from the SOURCE,
            # then locate those same match keys anywhere in the TARGET.  The target
            # must not be sliced by physical position because source/target ordering
            # is not guaranteed to be identical.
            is_specific_row = (
                specific_row_start is not None or specific_row_end is not None
            )
            if is_specific_row:
                if specific_row_start is None or specific_row_end is None:
                    raise ValueError(
                        "Specific Row Start Row and End Row are both required"
                    )
                if specific_row_start < 1 or specific_row_end < specific_row_start:
                    raise ValueError(
                        "Specific Row requires 1 <= Start Row <= End Row"
                    )
                if not primary_key:
                    raise ValueError(
                        "Specific Row Validation requires a match key"
                    )
            # --- 1. Read source rows using its database adapter. For Specific Row,
            # order by the selected key so row ranges are deterministic.
            source_rows = self._read_database_rows(
                source_conn_params,
                self._get_database_type(source_conn_params),
                dataset_name,
                table_name,
                batch_size,
                order_by=(primary_key[0] if is_specific_row and primary_key else None),
            )

            # --- 2. Read all target rows. Target is never sliced by physical position.
            target_rows = self._read_database_rows(
                target_conn_params,
                self._get_database_type(target_conn_params),
                dataset_name,
                table_name,
                batch_size,
            )

            if is_specific_row:
                if specific_row_start > len(source_rows):
                    raise ValueError(
                        f"Specific Row Start Row {specific_row_start} is beyond the source row count ({len(source_rows)})"
                    )
                source_rows = source_rows[specific_row_start - 1:specific_row_end]

            # --- 3. Determine column names --------------------------------
            if source_rows:
                columns = list(source_rows[0].keys())
            elif target_rows:
                columns = list(target_rows[0].keys())
            else:
                columns = []

            pk_columns = primary_key if not use_hash_key else None

            if pk_columns:
                normalized_columns = {str(c).lower() for c in columns}
                missing_source_keys = [
                    key for key in pk_columns if str(key).lower() not in normalized_columns
                ]
                if missing_source_keys:
                    raise ValueError(
                        f"Match key column(s) not found in source table: {', '.join(missing_source_keys)}"
                    )

                target_columns = (
                    list(target_rows[0].keys()) if target_rows else []
                )
                normalized_target_columns = {str(c).lower() for c in target_columns}
                missing_target_keys = [
                    key for key in pk_columns if str(key).lower() not in normalized_target_columns
                ]
                if missing_target_keys:
                    raise ValueError(
                        f"Match key column(s) not found in target table: {', '.join(missing_target_keys)}"
                    )

                if is_specific_row:
                    source_key_count = self._count_duplicate_keys(source_rows, pk_columns)
                    if source_key_count > 0:
                        raise ValueError(
                            f"Specific Row match key '{pk_columns[0]}' is not unique in the selected source rows"
                        )
                    target_key_count = self._count_duplicate_keys(target_rows, pk_columns)
                    if target_key_count > 0:
                        raise ValueError(
                            f"Specific Row match key '{pk_columns[0]}' is not unique in the target table"
                        )

            # --- 4. Index rows by key -------------------------------------
            source_by_key = self._index_rows_by_key(
                source_rows, pk_columns, columns,
            )
            target_by_key = self._index_rows_by_key(
                target_rows, pk_columns, columns,
            )

            if is_specific_row:
                # Only target rows corresponding to the selected source keys
                # participate in Specific Row validation. Rows outside the
                # requested source range are not "extra" for this check.
                target_by_key = {
                    key: target_by_key[key]
                    for key in source_by_key
                    if key in target_by_key
                }

            # --- 5. Compare rows ------------------------------------------
            total_compared = len(source_by_key)
            matched_count = 0
            missing_count = 0
            extra_count = 0
            mismatch_count = 0
            sample_discrepancies: List[Dict[str, Any]] = []

            # Check source rows against target
            for key, src_row in source_by_key.items():
                tgt_row = target_by_key.get(key)
                if tgt_row is None:
                    missing_count += 1
                    if len(sample_discrepancies) < MAX_SAMPLE_DISCREPANCIES:
                        pk_dict = self._build_pk_dict(
                            src_row, pk_columns, key, use_hash_key,
                        )
                        sample_discrepancies.append({
                            "type": "missing_in_target",
                            "primary_key": pk_dict,
                            "details": None,
                        })
                    continue

                # Compare column values
                row_has_mismatch = False
                for col in columns:
                    src_val = src_row.get(col)
                    tgt_val = tgt_row.get(col)
                    if not self._values_equal(src_val, tgt_val, type_mapping_overrides):
                        if not row_has_mismatch:
                            mismatch_count += 1
                            row_has_mismatch = True
                        if len(sample_discrepancies) < MAX_SAMPLE_DISCREPANCIES:
                            pk_dict = self._build_pk_dict(
                                src_row, pk_columns, key, use_hash_key,
                            )
                            sample_discrepancies.append({
                                "type": "value_mismatch",
                                "primary_key": pk_dict,
                                "details": {
                                    "column": col,
                                    "source_value": str(src_val) if src_val is not None else None,
                                    "target_value": str(tgt_val) if tgt_val is not None else None,
                                },
                            })
                        break  # one mismatch per row is enough for counting

                if not row_has_mismatch:
                    matched_count += 1

            # Check for extra rows in target. For Specific Row validation,
            # extras outside the selected source range are intentionally ignored.
            target_keys_to_check = (
                target_by_key.keys() if not is_specific_row else []
            )
            for key in target_keys_to_check:
                if key not in source_by_key:
                    extra_count += 1
                    if len(sample_discrepancies) < MAX_SAMPLE_DISCREPANCIES:
                        tgt_row = target_by_key[key]
                        pk_dict = self._build_pk_dict(
                            tgt_row, pk_columns, key, use_hash_key,
                        )
                        sample_discrepancies.append({
                            "type": "extra_in_target",
                            "primary_key": pk_dict,
                            "details": None,
                        })

            result = {
                "total_compared": total_compared,
                "matched_count": matched_count,
                "missing_count": missing_count,
                "extra_count": extra_count,
                "mismatch_count": mismatch_count,
                "sample_discrepancies": sample_discrepancies[:MAX_SAMPLE_DISCREPANCIES],
            }

            has_discrepancies = (missing_count + extra_count + mismatch_count) > 0
            status = "failed" if has_discrepancies else "passed"

            rec_duration_ms = int((time.time() - rec_start) * 1000)
            logger.info(
                "Record-level matching completed",
                extra={
                    "event": "record_match_completed",
                    "run_id": run_id,
                    "table_name": table_name,
                    "workspace_id": workspace_id,
                    "status": status,
                    "total_compared": total_compared,
                    "matched_count": matched_count,
                    "missing_count": missing_count,
                    "extra_count": extra_count,
                    "mismatch_count": mismatch_count,
                    "duration_ms": rec_duration_ms,
                },
            )

            return {"status": status, "result": result}

        except Exception as exc:
            rec_duration_ms = int((time.time() - rec_start) * 1000)
            logger.error(
                "Record-level matching error",
                extra={
                    "event": "record_match_completed",
                    "run_id": run_id,
                    "table_name": table_name,
                    "workspace_id": workspace_id,
                    "error": self._sanitize_error_message(str(exc)),
                    "traceback": traceback.format_exc(),
                    "duration_ms": rec_duration_ms,
                },
            )
            return {
                "status": "error",
                "result": {
                    "total_compared": 0,
                    "matched_count": 0,
                    "missing_count": 0,
                    "extra_count": 0,
                    "mismatch_count": 0,
                    "sample_discrepancies": [],
                },
                "error_message": self._sanitize_error_message(str(exc)),
            }

    # ------------------------------------------------------------------
    # Record matching helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_bigquery_rows(
        conn_params: dict,
        dataset_name: str,
        table_name: str,
        batch_size: int,
    ) -> List[Dict[str, Any]]:
        """Backward-compatible BigQuery row reader."""
        return ValidationService._read_database_rows(
            conn_params, "bigquery", dataset_name, table_name, batch_size
        )

    @staticmethod
    def _read_redshift_rows(
        conn_params: dict,
        schema_name: str,
        table_name: str,
        batch_size: int,
    ) -> List[Dict[str, Any]]:
        """Backward-compatible Redshift row reader."""
        return ValidationService._read_database_rows(
            conn_params, "redshift", schema_name, table_name, batch_size
        )

    @staticmethod
    def _compute_row_hash(row: dict, columns: list) -> str:
        """Compute a deterministic hash of all column values in a row.

        Used as a surrogate key when no primary key is available.

        Args:
            row: Dict of column_name â†’ value.
            columns: Ordered list of column names.

        Returns:
            Hex digest string.
        """
        parts = []
        for col in columns:
            val = row.get(col)
            parts.append(str(val) if val is not None else "\\x00")
        combined = "|".join(parts)
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    @staticmethod
    def _count_duplicate_keys(
        rows: List[Dict[str, Any]],
        pk_columns: List[str],
    ) -> int:
        """Return the number of duplicate composite keys in a row set."""
        seen = set()
        duplicates = 0
        for row in rows:
            parts = []
            for pk_col in pk_columns:
                value = row.get(pk_col.lower(), row.get(pk_col))
                parts.append(str(value) if value is not None else "\x00")
            key = "|".join(parts)
            if key in seen:
                duplicates += 1
            else:
                seen.add(key)
        return duplicates

    @staticmethod
    def _index_rows_by_key(
        rows: List[Dict[str, Any]],
        pk_columns: Optional[List[str]],
        all_columns: list,
    ) -> Dict[str, Dict[str, Any]]:
        """Index a list of row dicts by primary key or hash.

        Args:
            rows: List of row dicts.
            pk_columns: PK column names, or None to use hash.
            all_columns: All column names (for hash computation).

        Returns:
            Dict mapping key string â†’ row dict.
        """
        indexed: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            if pk_columns:
                key_parts = []
                for pk_col in pk_columns:
                    val = row.get(pk_col.lower(), row.get(pk_col))
                    key_parts.append(str(val) if val is not None else "\\x00")
                key = "|".join(key_parts)
            else:
                key = ValidationService._compute_row_hash(row, all_columns)
            indexed[key] = row
        return indexed

    @staticmethod
    def _build_pk_dict(
        row: dict,
        pk_columns: Optional[List[str]],
        key: str,
        use_hash_key: bool,
    ) -> dict:
        """Build a primary key dict for discrepancy reporting.

        Args:
            row: The source or target row dict.
            pk_columns: PK column names, or None.
            key: The computed key string.
            use_hash_key: Whether hash-based keys are in use.

        Returns:
            Dict like {"id": 42} or {"_hash": "abc..."}.
        """
        if use_hash_key or not pk_columns:
            return {"_hash": key}
        return {
            pk_col: row.get(pk_col.lower(), row.get(pk_col))
            for pk_col in pk_columns
        }

    @staticmethod
    def _values_equal(
        source_val: Any,
        target_val: Any,
        type_mapping_overrides: Optional[dict] = None,
    ) -> bool:
        """Compare two values with type-aware logic.

        Handles NULL equivalence, TIMESTAMP precision truncation,
        and NUMERIC/DECIMAL scale comparison.

        Args:
            source_val: Value from BigQuery source.
            target_val: Value from Redshift target.
            type_mapping_overrides: Currently unused but reserved for
                                    future type-specific comparison rules.

        Returns:
            True if values are considered equal.
        """
        # NULL / None equivalence
        if source_val is None and target_val is None:
            return True
        if source_val is None or target_val is None:
            return False

        # TIMESTAMP precision: truncate to microsecond
        if isinstance(source_val, datetime) and isinstance(target_val, datetime):
            src_trunc = source_val.replace(microsecond=source_val.microsecond)
            tgt_trunc = target_val.replace(microsecond=target_val.microsecond)
            # Truncate to microsecond by removing sub-microsecond via string
            src_str = src_trunc.strftime("%Y-%m-%d %H:%M:%S.%f")
            tgt_str = tgt_trunc.strftime("%Y-%m-%d %H:%M:%S.%f")
            return src_str == tgt_str

        # NUMERIC / DECIMAL comparison
        try:
            src_dec = Decimal(str(source_val))
            tgt_dec = Decimal(str(target_val))
            # Both are valid decimals â€“ compare numerically
            return src_dec == tgt_dec
        except (InvalidOperation, ValueError, TypeError):
            pass

        # Fallback: string comparison
        return str(source_val) == str(target_val)

    # ------------------------------------------------------------------
    # AI-powered discrepancy analysis
    # ------------------------------------------------------------------

    def _run_bedrock_analysis(
        self,
        table_name: str,
        ddl_result: Optional[Dict[str, Any]],
        row_count_result: Optional[Dict[str, Any]],
        data_match_result: Optional[Dict[str, Any]],
        bedrock_model: str,
        workspace_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Invoke AWS Bedrock to analyse discrepancies for a failed table.

        Constructs a prompt containing table name, DDL discrepancies,
        row-count differences, and sample record-level mismatches, then
        calls BedrockClient.invoke_model.  The response is parsed as
        JSON to extract ``root_cause``, ``impact_assessment``, and
        ``recommended_workarounds``.

        If JSON parsing fails the raw text is stored as ``root_cause``
        with empty ``impact_assessment`` and ``recommended_workarounds``.

        On any Bedrock failure the error is logged and ``None`` is
        returned so the overall validation is not affected.

        Args:
            table_name: Name of the failed table.
            ddl_result: DDL comparison JSONB dict (may be None).
            row_count_result: Row count JSONB dict (may be None).
            data_match_result: Record-level match JSONB dict (may be None).
            bedrock_model: Bedrock model identifier (e.g. ``anthropic.claude-3-sonnet-...``).
            workspace_id: Tenant isolation identifier (for logging).

        Returns:
            Dict with ``root_cause``, ``impact_assessment``, and
            ``recommended_workarounds`` keys, or ``None`` on failure.
        """
        MAX_PROMPT_CHARS = 10000
        region = os.environ.get("AWS_REGION", "us-east-1")

        # -- Build prompt sections ----------------------------------------
        header = (
            "You are a database migration expert. Analyse the following "
            "validation discrepancies for a BigQuery-to-Redshift migration "
            "and provide a JSON response with exactly three keys:\n"
            '  "root_cause": a concise explanation of the likely root cause,\n'
            '  "impact_assessment": the potential impact on data integrity,\n'
            '  "recommended_workarounds": a list of actionable workaround strings.\n\n'
        )

        table_section = f"Table: {table_name}\n"
        table_section += "Source database type: BigQuery\n"
        table_section += "Target database type: Redshift\n\n"

        # DDL discrepancies
        ddl_section = "## DDL Discrepancies\n"
        if ddl_result and ddl_result.get("discrepancies"):
            for disc in ddl_result["discrepancies"]:
                ddl_section += (
                    f"- {disc.get('type', 'unknown')}: column={disc.get('column_name', '?')}, "
                    f"source_type={disc.get('source_type', '?')}, "
                    f"target_type={disc.get('target_type', '?')}, "
                    f"expected_type={disc.get('expected_type', '?')}\n"
                )
        else:
            ddl_section += "None\n"
        ddl_section += "\n"

        # Row count differences
        rc_section = "## Row Count Differences\n"
        if row_count_result:
            rc_section += (
                f"source_count={row_count_result.get('source_count', '?')}, "
                f"target_count={row_count_result.get('target_count', '?')}, "
                f"difference={row_count_result.get('difference', '?')}, "
                f"percentage_difference={row_count_result.get('percentage_difference', '?')}\n"
            )
        else:
            rc_section += "None\n"
        rc_section += "\n"

        # Sample record-level mismatches
        rec_section = "## Sample Record-Level Mismatches\n"
        if data_match_result and data_match_result.get("sample_discrepancies"):
            for sample in data_match_result["sample_discrepancies"]:
                rec_section += (
                    f"- type={sample.get('type', '?')}, "
                    f"primary_key={sample.get('primary_key', '?')}, "
                    f"details={sample.get('details', '?')}\n"
                )
        else:
            rec_section += "None\n"
        rec_section += "\n"

        # -- Assemble and truncate ----------------------------------------
        prompt = header + table_section + ddl_section + rc_section + rec_section

        if len(prompt) > MAX_PROMPT_CHARS:
            # Truncate sample record mismatches first to fit within limit
            available = MAX_PROMPT_CHARS - len(header) - len(table_section) - len(ddl_section) - len(rc_section)
            if available > 50:
                rec_section = rec_section[:available - 30] + "\n... (truncated)\n\n"
            else:
                rec_section = "## Sample Record-Level Mismatches\n(truncated)\n\n"
            prompt = header + table_section + ddl_section + rc_section
            # If still too long, truncate DDL section as well
            if len(prompt) > MAX_PROMPT_CHARS:
                prompt = prompt[:MAX_PROMPT_CHARS - 20] + "\n... (truncated)"

        prompt += (
            "Respond ONLY with valid JSON containing the three keys above. "
            "Do not include any other text."
        )

        # -- Invoke Bedrock -----------------------------------------------
        logger.info(
            "Bedrock analysis started",
            extra={
                "event": "ai_analysis_started",
                "table_name": table_name,
                "model_id": bedrock_model,
                "workspace_id": workspace_id,
                "prompt_length": len(prompt),
            },
        )

        start_time = time.time()
        try:
            raw_response = self.bedrock.invoke_model(
                prompt=prompt,
                model_id=bedrock_model,
                region=region,
            )
            duration_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "Bedrock analysis completed",
                extra={
                    "event": "ai_analysis_completed",
                    "table_name": table_name,
                    "model_id": bedrock_model,
                    "workspace_id": workspace_id,
                    "duration_ms": duration_ms,
                },
            )

            # -- Parse response -------------------------------------------
            try:
                parsed = json.loads(raw_response)
                analysis = {
                    "root_cause": parsed.get("root_cause", ""),
                    "impact_assessment": parsed.get("impact_assessment", ""),
                    "recommended_workarounds": parsed.get("recommended_workarounds", []),
                }
            except (json.JSONDecodeError, TypeError):
                logger.warning(
                    "Bedrock response is not valid JSON, storing raw text as root_cause",
                    extra={
                        "table_name": table_name,
                        "model_id": bedrock_model,
                        "workspace_id": workspace_id,
                    },
                )
                analysis = {
                    "root_cause": raw_response,
                    "impact_assessment": "",
                    "recommended_workarounds": [],
                }

            return analysis

        except Exception as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "Bedrock analysis failed",
                extra={
                    "event": "ai_analysis_completed",
                    "table_name": table_name,
                    "model_id": bedrock_model,
                    "workspace_id": workspace_id,
                    "duration_ms": duration_ms,
                    "error": self._sanitize_error_message(str(exc)),
                },
            )
            return None

    @staticmethod
    def decrypt_connection_credentials(connection: "Connection") -> dict:
        """Preserve database-specific connection parameters and decrypt password."""
        params = dict(connection.connection_params or {})
        password_encrypted = params.get("password_encrypted")
        if password_encrypted:
            from services.unified_kms_service import get_unified_kms_service
            kms = get_unified_kms_service()
            password = kms.decrypt_credential(
                ciphertext=password_encrypted,
                credential_type="connection_password",
                resource_type="connection",
                resource_id=connection.id,
                allow_plaintext_fallback=True,
            )
        else:
            password = params.get("password")

        params["password"] = password
        params.pop("password_encrypted", None)

        # Preserve the database engine/type from the Connection model so
        # validation never confuses the database name with the database type.
        connection_type = (
            getattr(connection, "database_type", None)
            or getattr(connection, "connection_type", None)
            or getattr(connection, "db_type", None)
            or getattr(connection, "type", None)
        )
        if connection_type:
            params["database_type"] = connection_type

        return params

        # ------------------------------------------------------------------
    # NULL validation
    # ------------------------------------------------------------------


    def _validate_nulls(
        self,
        source_conn_params: dict,
        target_conn_params: dict,
        dataset_name: str,
        table_name: str,
        column_name: str,
    ) -> dict:
        """Compare NULL counts for a selected column across supported databases."""
        start_time = time.time()
        try:
            if not column_name:
                raise ValueError("Column name is required for NULL validation")
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_$]*$", column_name):
                raise ValueError(f"Invalid column name: {column_name}")

            counts = []
            for params in (source_conn_params, target_conn_params):
                db = self._get_database_type(params)
                effective_dataset_name = (
                    params.get("_validation_namespace") or dataset_name
                )

                if db in ("mongodb", "documentdb"):
                    client = self._mongo_client(params)
                    try:
                        db_name = params.get("database_name") or params.get("database") or effective_dataset_name
                        count = client[db_name][table_name].count_documents(
                            {column_name: {"$type": 10}}
                        )
                    finally:
                        client.close()

                elif db == "bigquery":
                    client, project_id = self._get_bigquery_client(params)
                    rows = list(client.query(
                        f"SELECT COUNT(*) FROM `{project_id}.{effective_dataset_name}.{table_name}` "
                        f"WHERE `{column_name}` IS NULL"
                    ).result())
                    count = int(rows[0][0]) if rows else 0

                elif db == "clickhouse":
                    client = self._clickhouse_client(params)
                    try:
                        ref = self._qualified_table(db, effective_dataset_name, table_name)
                        col = self._quote_identifier(column_name, db)
                        rows = client.query(
                            f"SELECT countIf(isNull({col})) FROM {ref}"
                        ).result_rows
                        count = int(rows[0][0]) if rows else 0
                    finally:
                        client.close()

                else:
                    conn = self._sql_connection(params, db)
                    try:
                        ref = self._qualified_table(db, effective_dataset_name, table_name)
                        col = self._quote_identifier(column_name, db)
                        with conn.cursor() as cur:
                            cur.execute(
                                f"SELECT COUNT(*) FROM {ref} WHERE {col} IS NULL"
                            )
                            row = cur.fetchone()
                            count = int(row[0]) if row else 0
                    finally:
                        conn.close()

                counts.append(count)

            source_count, target_count = counts
            difference = source_count - target_count
            status = "passed" if source_count == target_count else "failed"
            result = {
                "column": column_name,
                "source_null_count": source_count,
                "target_null_count": target_count,
                "difference": difference,
                "status": status,
            }
            return {
                "status": status,
                "result": result,
                "duration_seconds": round(time.time() - start_time, 3),
            }

        except Exception as exc:
            logger.error(
                "NULL validation failed",
                extra={
                    "table_name": table_name,
                    "column_name": column_name,
                    "error": str(exc),
                },
            )
            return {
                "status": "error",
                "result": {},
                "error_message": self._sanitize_error_message(str(exc)),
                "duration_seconds": round(time.time() - start_time, 3),
            }

    def _validate_aggregate(
        self,
        source_conn_params: dict,
        target_conn_params: dict,
        dataset_name: str,
        table_name: str,
        column_name: str,
        aggregate_type: str,
    ) -> dict:
        """Compare SUM or AVERAGE for a selected column across databases."""
        start_time = time.time()
        try:
            if not column_name:
                raise ValueError(
                    f"Column name is required for {aggregate_type} validation"
                )
            if aggregate_type not in ("SUM", "AVERAGE"):
                raise ValueError(
                    f"Unsupported aggregate type: {aggregate_type}"
                )
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_$]*$", column_name):
                raise ValueError(f"Invalid column name: {column_name}")

            values = []
            for params in (source_conn_params, target_conn_params):
                db = self._get_database_type(params)
                effective_dataset_name = (
                    params.get("_validation_namespace") or dataset_name
                )

                if db in ("mongodb", "documentdb"):
                    client = self._mongo_client(params)
                    try:
                        db_name = params.get("database_name") or params.get("database") or effective_dataset_name
                        op = "$sum" if aggregate_type == "SUM" else "$avg"
                        rows = client[db_name][table_name].aggregate([
                            {"$group": {"_id": None, "value": {op: f"${column_name}"}}}
                        ])
                        row = next(iter(rows), None)
                        value = (
                            float(row["value"])
                            if row and row.get("value") is not None
                            else 0.0
                        )
                    finally:
                        client.close()

                elif db == "bigquery":
                    client, project_id = self._get_bigquery_client(params)
                    op = "SUM" if aggregate_type == "SUM" else "AVG"
                    rows = list(client.query(
                        f"SELECT {op}(`{column_name}`) "
                        f"FROM `{project_id}.{effective_dataset_name}.{table_name}`"
                    ).result())
                    value = (
                        float(rows[0][0])
                        if rows and rows[0][0] is not None
                        else 0.0
                    )

                elif db == "clickhouse":
                    client = self._clickhouse_client(params)
                    try:
                        op = "sum" if aggregate_type == "SUM" else "avg"
                        ref = self._qualified_table(db, effective_dataset_name, table_name)
                        col = self._quote_identifier(column_name, db)
                        rows = client.query(
                            f"SELECT {op}({col}) FROM {ref}"
                        ).result_rows
                        value = (
                            float(rows[0][0])
                            if rows and rows[0][0] is not None
                            else 0.0
                        )
                    finally:
                        client.close()

                else:
                    conn = self._sql_connection(params, db)
                    try:
                        op = "SUM" if aggregate_type == "SUM" else "AVG"
                        ref = self._qualified_table(db, effective_dataset_name, table_name)
                        col = self._quote_identifier(column_name, db)
                        with conn.cursor() as cur:
                            cur.execute(f"SELECT {op}({col}) FROM {ref}")
                            row = cur.fetchone()
                            value = (
                                float(row[0])
                                if row and row[0] is not None
                                else 0.0
                            )
                    finally:
                        conn.close()

                values.append(value)

            source_value, target_value = values
            difference = source_value - target_value
            passed = abs(difference) <= 0.000001
            result = {
                "column": column_name,
                "aggregate_type": aggregate_type,
                "source_value": source_value,
                "target_value": target_value,
                "difference": difference,
                "status": "passed" if passed else "failed",
            }
            return {
                "status": result["status"],
                "result": result,
                "duration_seconds": round(time.time() - start_time, 3),
            }

        except Exception as exc:
            logger.error(
                f"{aggregate_type} validation failed",
                extra={
                    "table_name": table_name,
                    "column_name": column_name,
                    "error": str(exc),
                },
            )
            return {
                "status": "error",
                "result": {},
                "error_message": self._sanitize_error_message(str(exc)),
                "duration_seconds": round(time.time() - start_time, 3),
            }

    def _validate_duplicates(
        self,
        source_conn_params: dict,
        target_conn_params: dict,
        dataset_name: str,
        table_name: str,
        match_key: str,
    ) -> dict:
        """Compare duplicate-key group counts across databases."""
        start_time = time.time()
        try:
            if not match_key:
                raise ValueError(
                    "Match key is required for Duplicate validation"
                )
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_$]*$", match_key):
                raise ValueError(f"Invalid match key: {match_key}")

            counts = []
            for params in (source_conn_params, target_conn_params):
                db = self._get_database_type(params)
                effective_dataset_name = (
                    params.get("_validation_namespace") or dataset_name
                )

                if db in ("mongodb", "documentdb"):
                    client = self._mongo_client(params)
                    try:
                        db_name = params.get("database_name") or params.get("database") or effective_dataset_name
                        pipeline = [
                            {"$group": {"_id": f"${match_key}", "n": {"$sum": 1}}},
                            {"$match": {"n": {"$gt": 1}}},
                            {"$count": "duplicate_groups"},
                        ]
                        row = next(
                            iter(client[db_name][table_name].aggregate(pipeline)),
                            None,
                        )
                        count = int(row["duplicate_groups"]) if row else 0
                    finally:
                        client.close()

                elif db == "bigquery":
                    client, project_id = self._get_bigquery_client(params)
                    rows = list(client.query(
                        f"SELECT COUNT(*) FROM ("
                        f"SELECT `{match_key}` "
                        f"FROM `{project_id}.{effective_dataset_name}.{table_name}` "
                        f"GROUP BY `{match_key}` HAVING COUNT(*) > 1)"
                    ).result())
                    count = int(rows[0][0]) if rows else 0

                elif db == "clickhouse":
                    client = self._clickhouse_client(params)
                    try:
                        ref = self._qualified_table(db, effective_dataset_name, table_name)
                        col = self._quote_identifier(match_key, db)
                        rows = client.query(
                            f"SELECT count() FROM ("
                            f"SELECT {col} FROM {ref} "
                            f"GROUP BY {col} HAVING count() > 1)"
                        ).result_rows
                        count = int(rows[0][0]) if rows else 0
                    finally:
                        client.close()

                else:
                    conn = self._sql_connection(params, db)
                    try:
                        ref = self._qualified_table(db, effective_dataset_name, table_name)
                        col = self._quote_identifier(match_key, db)
                        with conn.cursor() as cur:
                            cur.execute(
                                f"SELECT COUNT(*) FROM ("
                                f"SELECT {col} FROM {ref} "
                                f"GROUP BY {col} HAVING COUNT(*) > 1) duplicate_groups"
                            )
                            row = cur.fetchone()
                            count = int(row[0]) if row else 0
                    finally:
                        conn.close()

                counts.append(count)

            source_count, target_count = counts
            passed = source_count == target_count
            result = {
                "match_key": match_key,
                "source_duplicate_count": source_count,
                "target_duplicate_count": target_count,
                "difference": source_count - target_count,
                "status": "passed" if passed else "failed",
            }
            return {
                "status": result["status"],
                "result": result,
                "duration_seconds": round(time.time() - start_time, 3),
            }

        except Exception as exc:
            logger.error(
                "Duplicate validation failed",
                extra={
                    "table_name": table_name,
                    "match_key": match_key,
                    "error": str(exc),
                },
            )
            return {
                "status": "error",
                "result": {},
                "error_message": self._sanitize_error_message(str(exc)),
                "duration_seconds": round(time.time() - start_time, 3),
            }
    # ------------------------------------------------------------------
    # Direct validation (connection-to-connection, no migration required)
    # ------------------------------------------------------------------

    def _engine_for_connection(self, connection: "Connection") -> str:
        """Resolve the normalized engine key for a connection record.

        Uses the Connection.type column first, then the connection params
        (including endpoint/port inference) so Redshift and any future
        engine resolve reliably even if a label is missing.
        """
        params = dict(connection.connection_params or {})
        ctype = (
            getattr(connection, "type", None)
            or getattr(connection, "database_type", None)
        )
        if ctype:
            params["database_type"] = ctype
        engine = self._get_database_type(params)
        if engine:
            return engine
        # Fall back to the 'database' column as an engine hint, then raise clearly.
        engine = self._get_database_type({"database_type": getattr(connection, "database", None)})
        if engine:
            return engine
        raise ValueError(
            f"Could not determine the database engine for connection "
            f"'{getattr(connection, 'name', connection.id)}' "
            f"(type={getattr(connection, 'type', None)!r}, "
            f"database={getattr(connection, 'database', None)!r}). "
            "Set the connection's type to a supported engine."
        )

    def _direct_params(self, connection: "Connection", schema: str) -> dict:
        """Build decrypted conn params for a direct check, pinned to a schema.

        Reuses ``decrypt_connection_credentials`` (which preserves the engine
        type and all engine-specific keys) and sets ``_validation_namespace``
        so the generalized check helpers target the given schema/dataset.
        """
        params = self.decrypt_connection_credentials(connection)
        if schema:
            params["_validation_namespace"] = schema
        return params

    def list_connection_tables(self, connection_id: int) -> Dict[str, Any]:
        """List user tables (schema + table) for a connection via information_schema.

        Supported for SQL engines (postgresql/redshift/mysql/sqlserver/etc.).
        """
        conn = (
            self.db.query(Connection)
            .filter(Connection.id == connection_id)
            .first()
        )
        if not conn or not conn.is_active:
            raise ValueError(f"Connection id={connection_id} is missing or inactive.")

        engine = self._engine_for_connection(conn)
        params = self.decrypt_connection_credentials(conn)

        if engine in ("mongodb", "documentdb"):
            client = self._mongo_client(params)
            try:
                db_name = params.get("database_name") or params.get("database")
                tables = [
                    {"schema": db_name or "", "table": name}
                    for name in client[db_name].list_collection_names()
                ]
            finally:
                client.close()
        elif engine == "clickhouse":
            client = self._clickhouse_client(params)
            try:
                rows = client.query(
                    "SELECT database, name FROM system.tables "
                    "WHERE database NOT IN ('system','INFORMATION_SCHEMA','information_schema')"
                ).result_rows
                tables = [{"schema": r[0], "table": r[1]} for r in rows]
            finally:
                client.close()
        elif engine == "bigquery":
            client, project_id = self._get_bigquery_client(params)
            dataset = params.get("dataset") or params.get("_validation_namespace")
            tables = []
            datasets = [dataset] if dataset else [d.dataset_id for d in client.list_datasets()]
            for ds in datasets:
                for tbl in client.list_tables(f"{project_id}.{ds}"):
                    tables.append({"schema": ds, "table": tbl.table_id})
        else:
            conn_db = self._sql_connection(params, engine)
            try:
                with conn_db.cursor() as cur:
                    cur.execute(
                        "SELECT table_schema, table_name FROM information_schema.tables "
                        "WHERE table_type = 'BASE TABLE' ORDER BY table_schema, table_name"
                    )
                    rows = cur.fetchall()
                system = {
                    "information_schema", "sys", "pg_catalog", "pg_internal",
                }
                tables = [
                    {"schema": r[0], "table": r[1]}
                    for r in rows
                    if str(r[0]).lower() not in system
                ]
            finally:
                conn_db.close()

        return {
            "connection_id": connection_id,
            "connection_name": conn.name,
            "engine": engine,
            "tables": tables,
        }

    def list_connection_columns(
        self, connection_id: int, schema: str, table: str
    ) -> Dict[str, Any]:
        """List columns (name + data_type) for a table on a connection."""
        conn = (
            self.db.query(Connection)
            .filter(Connection.id == connection_id)
            .first()
        )
        if not conn or not conn.is_active:
            raise ValueError(f"Connection id={connection_id} is missing or inactive.")
        engine = self._engine_for_connection(conn)
        params = self.decrypt_connection_credentials(conn)
        columns = self._get_database_columns(params, engine, schema, table)
        return {
            "connection_id": connection_id,
            "engine": engine,
            "schema": schema,
            "table": table,
            "columns": columns,
        }

    def run_direct_validation(
        self,
        source_connection_id: int,
        target_connection_id: int,
        source_schema: str,
        target_schema: str,
        table_name: str,
        checks: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run validation checks directly between two connections (no migration).

        Reuses the generalized multi-engine check helpers so this works for any
        supported source/target engine pair (e.g. SQL Server -> Redshift).
        """
        source_conn = (
            self.db.query(Connection)
            .filter(Connection.id == source_connection_id)
            .first()
        )
        target_conn = (
            self.db.query(Connection)
            .filter(Connection.id == target_connection_id)
            .first()
        )
        if not source_conn or not source_conn.is_active:
            raise ValueError(
                f"Source connection id={source_connection_id} is missing or inactive."
            )
        if not target_conn or not target_conn.is_active:
            raise ValueError(
                f"Target connection id={target_connection_id} is missing or inactive."
            )

        source_engine = self._engine_for_connection(source_conn)
        target_engine = self._engine_for_connection(target_conn)

        source_params = self._direct_params(source_conn, source_schema)
        target_params = self._direct_params(target_conn, target_schema)

        results: Dict[str, Any] = {}

        def _record(check_name: str, check_result: dict, src_key: str, tgt_key: str):
            """Normalize a check helper result into the direct-test shape."""
            r = check_result.get("result", {}) or {}
            if check_result.get("status") == "error":
                results[check_name] = {
                    "status": "error",
                    "error_message": check_result.get("error_message", "check failed"),
                }
            else:
                results[check_name] = {
                    "status": check_result.get("status"),
                    "source_value": r.get(src_key),
                    "target_value": r.get(tgt_key),
                    "difference": r.get("difference"),
                }

        # Row count
        if checks.get("row_count"):
            res = self._validate_row_count(
                run_id=0,
                table_name=table_name,
                dataset_name=source_schema,
                source_conn_params=source_params,
                target_conn_params={**target_params, "_validation_namespace": target_schema},
                workspace_id=0,
            )
            _record("row_count", res, "source_count", "target_count")

        # Schema / DDL — compare live columns of source vs target
        if checks.get("ddl_check") or checks.get("schema_check"):
            try:
                src_cols = self._get_database_columns(
                    source_params, source_engine, source_schema, table_name,
                )
                tgt_cols = self._get_database_columns(
                    target_params, target_engine, target_schema, table_name,
                )
                src_map = {c["column_name"].lower(): c for c in src_cols}
                tgt_map = {c["column_name"].lower(): c for c in tgt_cols}

                missing_in_target = [c["column_name"] for k, c in src_map.items() if k not in tgt_map]
                extra_in_target = [c["column_name"] for k, c in tgt_map.items() if k not in src_map]
                type_mismatches = []
                for k, sc in src_map.items():
                    tc = tgt_map.get(k)
                    if tc and not self._types_equivalent(sc["data_type"], tc["data_type"]):
                        type_mismatches.append({
                            "column": sc["column_name"],
                            "source_type": sc["data_type"],
                            "target_type": tc["data_type"],
                        })

                passed = not missing_in_target and not extra_in_target and not type_mismatches
                results["schema_check"] = {
                    "status": "passed" if passed else "failed",
                    "source_value": len(src_cols),
                    "target_value": len(tgt_cols),
                    "difference": len(src_cols) - len(tgt_cols),
                    "details": {
                        "missing_in_target": missing_in_target,
                        "extra_in_target": extra_in_target,
                        "type_mismatches": type_mismatches,
                    },
                }
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Schema validation failed",
                    extra={"table_name": table_name, "error": str(exc)},
                )
                results["schema_check"] = {
                    "status": "error",
                    "error_message": self._sanitize_error_message(str(exc)),
                }

        # NULL
        if checks.get("null_check"):
            col = checks.get("null_column")
            if not col:
                results["null_check"] = {"status": "error", "error_message": "null_column is required"}
            else:
                res = self._validate_nulls(
                    source_params,
                    {**target_params, "_validation_namespace": target_schema},
                    source_schema, table_name, col,
                )
                _record("null_check", res, "source_null_count", "target_null_count")

        # Duplicate
        if checks.get("duplicate_check"):
            key = checks.get("duplicate_match_key")
            if not key:
                results["duplicate_check"] = {"status": "error", "error_message": "duplicate_match_key is required"}
            else:
                res = self._validate_duplicates(
                    source_params,
                    {**target_params, "_validation_namespace": target_schema},
                    source_schema, table_name, key,
                )
                _record("duplicate_check", res, "source_duplicate_count", "target_duplicate_count")

        # SUM
        if checks.get("sum_check"):
            col = checks.get("sum_column")
            if not col:
                results["sum_check"] = {"status": "error", "error_message": "sum_column is required"}
            else:
                res = self._validate_aggregate(
                    source_params,
                    {**target_params, "_validation_namespace": target_schema},
                    source_schema, table_name, col, "SUM",
                )
                _record("sum_check", res, "source_value", "target_value")

        # AVERAGE
        if checks.get("average_check"):
            col = checks.get("average_column")
            if not col:
                results["average_check"] = {"status": "error", "error_message": "average_column is required"}
            else:
                res = self._validate_aggregate(
                    source_params,
                    {**target_params, "_validation_namespace": target_schema},
                    source_schema, table_name, col, "AVERAGE",
                )
                _record("average_check", res, "source_value", "target_value")

        # Specific Row — compare a deterministic range of rows (by match key)
        if checks.get("specific_row_check"):
            key = checks.get("specific_row_match_key")
            start = checks.get("specific_row_start")
            end = checks.get("specific_row_end")
            if not key:
                results["specific_row_check"] = {"status": "error", "error_message": "specific_row_match_key is required"}
            elif start is None or end is None:
                results["specific_row_check"] = {"status": "error", "error_message": "specific_row_start and specific_row_end are required"}
            else:
                try:
                    res = self._validate_records(
                        run_id=0,
                        table_name=table_name,
                        dataset_name=source_schema,
                        source_conn_params=source_params,
                        target_conn_params={**target_params, "_validation_namespace": target_schema},
                        primary_key=[key],
                        batch_size=10000,
                        type_mapping_overrides={},
                        workspace_id=0,
                        specific_row_start=int(start),
                        specific_row_end=int(end),
                    )
                    r = res.get("result", {}) or {}
                    if res.get("status") == "error":
                        results["specific_row_check"] = {
                            "status": "error",
                            "error_message": res.get("error_message", "specific row check failed"),
                        }
                    else:
                        results["specific_row_check"] = {
                            "status": res.get("status"),
                            "source_value": r.get("total_compared"),
                            "target_value": r.get("matched_count"),
                            "difference": (r.get("missing_count", 0) + r.get("mismatch_count", 0)),
                            "details": {
                                "matched": r.get("matched_count"),
                                "missing": r.get("missing_count"),
                                "mismatched": r.get("mismatch_count"),
                            },
                        }
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "Specific row validation failed",
                        extra={"table_name": table_name, "error": str(exc)},
                    )
                    results["specific_row_check"] = {
                        "status": "error",
                        "error_message": self._sanitize_error_message(str(exc)),
                    }

        statuses = [r.get("status") for r in results.values()]
        if not statuses:
            overall = "no_checks"
        elif any(s == "error" for s in statuses):
            overall = "error"
        elif any(s == "failed" for s in statuses):
            overall = "failed"
        else:
            overall = "passed"

        return {
            "overall_status": overall,
            "source_engine": source_engine,
            "target_engine": target_engine,
            "source_connection": source_conn.name,
            "target_connection": target_conn.name,
            "table_name": table_name,
            "checks": results,
        }

    # ------------------------------------------------------------------
    # Deletion
    # ------------------------------------------------------------------

    def delete_run(self, run_id: int, workspace_id: int) -> bool:
        """Delete a validation run and all associated table results.

        Invalidates all related Redis cache entries.

        Args:
            run_id: The validation run primary key.
            workspace_id: Tenant isolation identifier.

        Returns:
            True if deleted, False if not found.
        """
        deleted = self.repo.delete_run(run_id, workspace_id)
        if deleted:
            self.cache.invalidate_all_for_run(run_id, workspace_id)
            logger.info(
                "Validation run deleted",
                extra={"run_id": run_id, "workspace_id": workspace_id},
            )
        return deleted

