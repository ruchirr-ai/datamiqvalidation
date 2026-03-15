"""
Validation Service

Core orchestration logic for post-migration data validation between
BigQuery and Redshift. Manages validation run lifecycle, delegates to
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
            type_mapping_overrides: Optional BQ→Redshift type overrides.
            created_by: Username or identifier of the requesting user.

        Returns:
            Dict representation of the created ValidationRun.

        Raises:
            ValueError: If migration is not completed, connections are
                        invalid/inactive, or no tables can be determined.
            RuntimeError: If the workspace has reached the maximum number
                          of concurrent validation runs.
        """
        # 0. Rate limiting — enforce max concurrent runs per workspace
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
            status="pending",
            progress_percentage=0,
            tables_total=len(resolved_tables),
            tables_passed=0,
            tables_failed=0,
            tables_error=0,
            created_by=created_by,
        )

        # 6. Create one ValidationTableResult per table
        for table_name in resolved_tables:
            self.repo.create_table_result(
                run_id=run.id,
                workspace_id=workspace_id,
                table_name=table_name,
                status="pending",
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

        Processes tables sequentially: DDL comparison → row count
        validation → record-level matching. Updates progress, table
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
            source_conn.connection_params if source_conn else {}
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
        if migration:
            # First try checkpoint_data.load_summary (gold standard — set
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
                # --- DDL comparison -----------------------------------
                ddl_result = {"status": "error", "result": {}}
                if assessment_id is not None:
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

                # --- Row count validation -----------------------------
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

                # --- Record-level matching ----------------------------
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
                                    primary_key.append(col.column_name)
                    except Exception as pk_exc:
                        logger.warning(
                            "Failed to determine primary key from assessment",
                            extra={
                                "run_id": run_id,
                                "table_name": table_name,
                                "error": str(pk_exc),
                            },
                        )

                records_result = self._validate_records(
                    run_id=run_id,
                    table_name=table_name,
                    dataset_name=tbl_dataset,
                    source_conn_params=source_conn_params,
                    target_conn_params=target_conn_params,
                    primary_key=primary_key,
                    batch_size=batch_size,
                    type_mapping_overrides=type_mapping_overrides,
                    workspace_id=workspace_id,
                )

                rec_status = records_result["status"]
                if rec_status == "error":
                    table_has_error = True
                elif rec_status == "failed":
                    table_has_failure = True

                # --- Determine overall table status -------------------
                all_error = (
                    ddl_result["status"] == "error"
                    and row_count_result["status"] == "error"
                    and records_result["status"] == "error"
                )
                if all_error:
                    table_status = "error"
                elif table_has_failure or table_has_error:
                    table_status = "failed"
                else:
                    table_status = "completed"

                # Build error message from any error steps
                error_messages = []
                if ddl_result.get("error_message"):
                    error_messages.append(f"DDL: {ddl_result['error_message']}")
                if row_count_result.get("error_message"):
                    error_messages.append(f"Row count: {row_count_result['error_message']}")
                if records_result.get("error_message"):
                    error_messages.append(f"Records: {records_result['error_message']}")

                table_end = datetime.utcnow()
                table_duration = int((table_end - table_start).total_seconds())

                # Update table result with all outcomes
                self.repo.update_table_result(
                    table_result.id, workspace_id,
                    ddl_status=ddl_result["status"],
                    ddl_comparison_result=ddl_result["result"],
                    row_count_status=row_count_result["status"],
                    row_count_result=row_count_result["result"],
                    data_match_status=records_result["status"],
                    data_match_result=records_result["result"],
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
                "Skipping Bedrock analysis — no bedrock_model configured on run",
                extra={"run_id": run_id, "workspace_id": workspace_id},
            )

        # 9. Finalize run -------------------------------------------------
        run_end = datetime.utcnow()
        run_duration = int((run_end - run_start).total_seconds())

        if tables_error == total_tables:
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

        # 10. Credential cleanup — discard decrypted credentials from memory
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
    ) -> Dict[str, Any]:
        """List validation runs with pagination and optional filters.

        Args:
            workspace_id: Tenant isolation identifier.
            migration_id: Optional filter by migration ID.
            status: Optional filter by run status.
            page: 1-based page number.
            page_size: Results per page (default 20, max 100).

        Returns:
            Dict with 'runs' list, 'total', 'page', and 'page_size'.
        """
        runs, total = self.repo.list_runs(
            workspace_id=workspace_id,
            migration_id=migration_id,
            status=status,
            page=page,
            page_size=page_size,
        )

        return {
            "runs": [r.to_dict() for r in runs],
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
        if run.tables_failed > 0 or run.tables_error > 0:
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
        """Compare source BigQuery DDL against target Redshift DDL.

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
            type_mapping_overrides: Optional BQ→Redshift type overrides.
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
            target_columns = self._get_target_columns(
                target_conn_params, dataset_name, table_name,
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

                # Both exist – check type equivalence
                if not mapper.is_equivalent(src["data_type"], tgt["data_type"]):
                    discrepancies.append({
                        "type": "type_mismatch",
                        "column_name": src["column_name"],
                        "source_type": src["data_type"],
                        "target_type": tgt["data_type"],
                        "expected_type": mapper.get_expected_redshift_type(src["data_type"]),
                    })

                # Check nullability
                src_nullable = src.get("is_nullable", True)
                tgt_nullable = tgt.get("is_nullable", True)
                if src_nullable != tgt_nullable:
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
    # Row count validation
    # ------------------------------------------------------------------

    def _validate_row_count(
        self,
        run_id: int,
        table_name: str,
        dataset_name: str,
        source_conn_params: dict,
        target_conn_params: dict,
        workspace_id: int,
    ) -> dict:
        """Compare row counts between BigQuery source and Redshift target.

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
            source_count = self._get_bigquery_row_count(
                source_conn_params, dataset_name, table_name, ROW_COUNT_TIMEOUT,
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
            error_msg = f"Source (BigQuery) row count query failed: {exc}"
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
            target_count = self._get_redshift_row_count(
                target_conn_params, dataset_name, table_name, ROW_COUNT_TIMEOUT,
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
            error_msg = f"Target (Redshift) row count query failed: {exc}"
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

    @staticmethod
    def _get_target_columns(
        conn_params: dict,
        schema_name: str,
        table_name: str,
    ) -> List[Dict[str, Any]]:
        """Query Redshift information_schema for target column metadata.

        Opens a short-lived psycopg2 connection using the provided
        (already-decrypted) connection parameters.

        Args:
            conn_params: Dict with host, port, database, username,
                         password keys.
            schema_name: Redshift schema to query.
            table_name: Redshift table name.

        Returns:
            List of dicts with column_name, data_type, is_nullable,
            ordinal_position.
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
        )
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT column_name, data_type, is_nullable, ordinal_position
                    FROM information_schema.columns
                    WHERE table_schema = %s
                      AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (schema_name, table_name),
                )
                rows = cur.fetchall()
        finally:
            conn.close()

        return [
            {
                "column_name": row[0],
                "data_type": row[1].upper(),
                "is_nullable": row[2].upper() == "YES",
                "ordinal_position": row[3],
            }
            for row in rows
        ]

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
    ) -> dict:
        """Compare source BigQuery records against target Redshift records.

        Reads data in configurable batches from both databases, matches
        rows by primary key (or hash of all columns when no PK is
        available), and detects missing, extra, and mismatched records.

        Args:
            run_id: Parent validation run ID (for logging).
            table_name: Name of the table to compare.
            dataset_name: BigQuery dataset / Redshift schema name.
            source_conn_params: Decrypted BigQuery connection parameters.
            target_conn_params: Decrypted Redshift connection parameters.
            primary_key: List of PK column names. If empty/None, a hash
                         of all column values is used as the row key.
            batch_size: Number of rows per batch (default 10000).
            type_mapping_overrides: BQ→Redshift type overrides for
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
            # --- 1. Read all source rows from BigQuery --------------------
            source_rows = self._read_bigquery_rows(
                source_conn_params, dataset_name, table_name, batch_size,
            )

            # --- 2. Read all target rows from Redshift --------------------
            target_rows = self._read_redshift_rows(
                target_conn_params, dataset_name, table_name, batch_size,
            )

            # --- 3. Determine column names --------------------------------
            if source_rows:
                columns = list(source_rows[0].keys())
            elif target_rows:
                columns = list(target_rows[0].keys())
            else:
                columns = []

            pk_columns = primary_key if not use_hash_key else None

            # --- 4. Index rows by key -------------------------------------
            source_by_key = self._index_rows_by_key(
                source_rows, pk_columns, columns,
            )
            target_by_key = self._index_rows_by_key(
                target_rows, pk_columns, columns,
            )

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

            # Check for extra rows in target
            for key in target_by_key:
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
        """Read all rows from a BigQuery table in batches.

        Args:
            conn_params: Dict with credentials_json and project_id.
            dataset_name: BigQuery dataset name.
            table_name: BigQuery table name.
            batch_size: Page size for result iteration.

        Returns:
            List of row dicts with lowercase column names.
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

        query = f"SELECT * FROM `{project_id}.{dataset_name}.{table_name}` ORDER BY 1"
        job_config = bigquery.QueryJobConfig()
        job = client.query(query, job_config=job_config)

        rows: List[Dict[str, Any]] = []
        for page in job.result(page_size=batch_size).pages:
            for row in page:
                rows.append({k.lower(): v for k, v in dict(row).items()})

        return rows

    @staticmethod
    def _read_redshift_rows(
        conn_params: dict,
        schema_name: str,
        table_name: str,
        batch_size: int,
    ) -> List[Dict[str, Any]]:
        """Read all rows from a Redshift table in batches.

        Args:
            conn_params: Dict with host, port, database, username, password.
            schema_name: Redshift schema name.
            table_name: Redshift table name.
            batch_size: Fetch size for cursor iteration.

        Returns:
            List of row dicts with lowercase column names.
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
        )
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT * FROM {schema_name}.{table_name} ORDER BY 1",
                )
                col_names = [desc[0].lower() for desc in cur.description]
                rows: List[Dict[str, Any]] = []
                while True:
                    batch = cur.fetchmany(batch_size)
                    if not batch:
                        break
                    for row_tuple in batch:
                        rows.append(dict(zip(col_names, row_tuple)))
        finally:
            conn.close()

        return rows

    @staticmethod
    def _compute_row_hash(row: dict, columns: list) -> str:
        """Compute a deterministic hash of all column values in a row.

        Used as a surrogate key when no primary key is available.

        Args:
            row: Dict of column_name → value.
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
            Dict mapping key string → row dict.
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
            # Both are valid decimals – compare numerically
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
        """Decrypt connection credentials using KMS.

        Handles both encrypted and plain-text passwords for backward
        compatibility, following the pattern in pathway_c.

        Args:
            connection: A Connection model instance.

        Returns:
            Dict with host, port, database, username, password ready
            for psycopg2.connect().
        """
        conn_params = connection.connection_params or {}

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

        password_encrypted = conn_params.get("password_encrypted")
        password_plain = conn_params.get("password")

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
            password = password_plain

        return {
            "host": host,
            "port": port,
            "database": database,
            "username": username,
            "password": password,
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
