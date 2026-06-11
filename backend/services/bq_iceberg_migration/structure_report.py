"""
Structure Report Generator

Generates the Iceberg Structure Design Report for user review before the load
stage begins. Supports system recommendations, user overrides, and user-defined
custom structures. Includes prerequisites checklist, warnings, and export
capabilities (Markdown and PDF).

Requirements: 4.1, 4.2, 4.3, 4.4, 4.7, 4.8, 4.9, 4.10, 4.13
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from .iceberg_types import (
    BinaryType,
    BooleanType,
    DateType,
    DecimalType,
    DoubleType,
    IcebergType,
    LongType,
    StringType,
    TimestampType,
    TimestamptzType,
    TimeType,
)
from .partition_mapper import PartitionSpecMapper
from .type_mapper import BQToIcebergTypeMapper

logger = logging.getLogger(__name__)


# Valid Iceberg type names for custom structure validation
VALID_ICEBERG_TYPES = {
    "boolean", "int", "integer", "long", "float", "double",
    "date", "time", "timestamp", "timestamptz", "string",
    "binary", "decimal",
}

# Compaction strategy descriptions for user display
COMPACTION_STRATEGY_DESCRIPTIONS = {
    "binpack": "Combines small files without reordering (best for append-heavy workloads)",
    "sort": "Reorders data by specified columns (best for range queries on specific columns)",
    "z-order": "Interleaves multiple columns (best for queries filtering on multiple columns simultaneously)",
}

# Default table properties for Iceberg tables
DEFAULT_TABLE_PROPERTIES = {
    "format-version": "2",
    "write.format.default": "parquet",
    "write.parquet.compression-codec": "zstd",
    "write.metadata.delete-after-commit.enabled": "true",
    "write.metadata.previous-versions-max": "3",
}

# Athena reserved words that may conflict with table names
ATHENA_RESERVED_WORDS = {
    "all", "alter", "and", "array", "as", "authorization", "between",
    "bigint", "binary", "boolean", "both", "by", "case", "cast", "char",
    "column", "conf", "create", "cross", "cube", "current", "database",
    "date", "decimal", "delete", "describe", "distinct", "double", "drop",
    "else", "end", "exchange", "exists", "extended", "external", "false",
    "fetch", "float", "following", "for", "from", "full", "function",
    "grant", "group", "grouping", "having", "if", "import", "in", "inner",
    "insert", "int", "integer", "intersect", "interval", "into", "is",
    "join", "lateral", "left", "less", "like", "local", "macro", "map",
    "more", "none", "not", "null", "of", "on", "or", "order", "out",
    "outer", "over", "partition", "percent", "preceding", "preserve",
    "procedure", "range", "reads", "reduce", "revoke", "right", "rollup",
    "row", "rows", "select", "set", "smallint", "table", "tablesample",
    "then", "timestamp", "to", "transform", "trigger", "true", "truncate",
    "unbounded", "union", "uniquejoin", "update", "user", "using", "values",
    "varchar", "when", "where", "window", "with",
}


# IAM permissions required for Iceberg migrations
REQUIRED_IAM_PERMISSIONS = {
    "s3": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:GetBucketLocation",
    ],
    "glue": [
        "glue:CreateDatabase",
        "glue:GetDatabase",
        "glue:CreateTable",
        "glue:GetTable",
        "glue:UpdateTable",
        "glue:DeleteTable",
    ],
    "athena": [
        "athena:StartQueryExecution",
        "athena:GetQueryExecution",
        "athena:GetQueryResults",
    ],
    "s3_tables": [
        "s3tables:CreateTable",
        "s3tables:GetTable",
        "s3tables:CreateNamespace",
        "s3tables:GetNamespace",
        "s3tables:ListNamespaces",
    ],
}


class StructureReportGenerator:
    """Generates the Iceberg Structure Design Report for user review.

    Supports system recommendations and user-defined custom structures.
    The report includes per-table design recommendations, a prerequisites
    checklist, and warnings/recommendations for potential issues.

    Usage:
        generator = StructureReportGenerator()
        report = generator.generate(
            migration=migration_obj,
            assessment_tables=assessment_data,
            type_mapper=BQToIcebergTypeMapper(),
            partition_mapper=PartitionSpecMapper(),
        )
        # Apply user overrides
        report = generator.apply_overrides(report, user_overrides)
        # Export as markdown
        md_content = generator.export_markdown(report)
    """

    def generate(
        self,
        migration: Any,
        assessment_tables: list[dict],
        type_mapper: BQToIcebergTypeMapper,
        partition_mapper: PartitionSpecMapper,
    ) -> dict:
        """Generate the full structure report as a JSON-serializable dict.

        Includes per-table recommendations, prerequisites checklist,
        and warnings/recommendations section.

        Args:
            migration: The MigrationBQIceberg model instance containing
                       destination configuration.
            assessment_tables: List of assessment table metadata dicts.
                Each dict should contain: table_name, columns (list of
                column dicts with name, type, mode, fields), partition_column,
                partition_type, partition_granularity, clustering_columns,
                estimated_rows, estimated_size_bytes, dataset.
            type_mapper: BQToIcebergTypeMapper instance for schema mapping.
            partition_mapper: PartitionSpecMapper instance for partition mapping.

        Returns:
            A JSON-serializable dict containing the full structure report.
        """
        destination_type = getattr(migration, "destination_type", "iceberg_s3")
        glue_database = getattr(migration, "glue_database_name", "default_db")
        migration_id = getattr(migration, "id", None)

        tables = []
        warnings = []
        total_size_bytes = 0

        for table_meta in assessment_tables:
            table_report = self._generate_table_report(
                table_meta, type_mapper, partition_mapper, glue_database
            )
            tables.append(table_report)
            total_size_bytes += table_meta.get("estimated_size_bytes", 0)
            warnings.extend(table_report.get("warnings", []))

        # Build dataset-to-db mapping from assessment data
        dataset_to_db = {}
        for table_meta in assessment_tables:
            dataset = table_meta.get("dataset", "")
            if dataset and dataset not in dataset_to_db:
                dataset_to_db[dataset] = glue_database

        prerequisites = self._generate_prerequisites(destination_type, migration)

        # Add global warnings
        global_warnings = self._generate_global_warnings(
            tables, total_size_bytes
        )
        warnings.extend(global_warnings)

        report = {
            "migration_id": migration_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "destination_type": destination_type,
            "tables": tables,
            "dataset_to_db_mapping": dataset_to_db,
            "s3_tables_namespace": getattr(
                migration, "s3_tables_namespace", None
            ),
            "prerequisites": prerequisites,
            "warnings": warnings,
            "total_estimated_size_bytes": total_size_bytes,
            "table_count": len(tables),
        }

        logger.info(
            "Generated structure report for migration %s: %d tables, %d warnings",
            migration_id,
            len(tables),
            len(warnings),
        )

        return report

    def _generate_table_report(
        self,
        table_meta: dict,
        type_mapper: BQToIcebergTypeMapper,
        partition_mapper: PartitionSpecMapper,
        glue_database: str,
    ) -> dict:
        """Generate the structure report for a single table.

        Args:
            table_meta: Assessment metadata for the table.
            type_mapper: Type mapper instance.
            partition_mapper: Partition mapper instance.
            glue_database: Default Glue database name.

        Returns:
            Dict with table-level structure recommendation.
        """
        source_table = table_meta.get("table_name", "unknown")
        proposed_name = self._derive_iceberg_name(source_table)
        columns = table_meta.get("columns", [])
        warnings: list[str] = []

        # Map columns
        mapped_columns = []
        for col in columns:
            col_name = col.get("name", "unknown")
            bq_type = col.get("type", "STRING")
            bq_mode = col.get("mode", "NULLABLE")
            iceberg_type_str = self._bq_type_to_iceberg_str(bq_type)
            nullable = type_mapper.is_nullable(bq_mode)

            # Check for fallback types
            upper_type = bq_type.strip().upper()
            if upper_type not in type_mapper.TYPE_MAP and upper_type not in (
                "STRUCT", "RECORD", "ARRAY"
            ):
                warnings.append(
                    f"Column '{col_name}' has unrecognized type '{bq_type}' "
                    f"— mapped to string (fallback)"
                )

            mapped_columns.append({
                "name": col_name,
                "bq_type": bq_type,
                "iceberg_type": iceberg_type_str,
                "nullable": nullable,
            })

        # Map partition spec
        partition_column = table_meta.get("partition_column")
        partition_type = table_meta.get("partition_type", "DATE")
        partition_granularity = table_meta.get("partition_granularity")
        partition_spec = None
        partition_rationale = None

        if partition_column:
            spec = partition_mapper.map_partition_spec(
                partition_column, partition_type, partition_granularity
            )
            transform = spec.fields[0].transform if spec.fields else "day"
            partition_spec = {
                "column": partition_column,
                "transform": transform,
            }
            partition_rationale = (
                f"Partitioned by `{transform}({partition_column})` "
                f"based on BQ {partition_type} partitioning"
            )
        else:
            # Warn for large tables without partitioning
            estimated_size = table_meta.get("estimated_size_bytes", 0)
            if estimated_size > 1_073_741_824:  # > 1GB
                warnings.append(
                    f"Table '{source_table}' has no partitioning but is "
                    f"estimated at {estimated_size / (1024**3):.1f} GB. "
                    f"Consider adding a partition for query performance."
                )

        # Map sort order from clustering columns
        clustering_columns = table_meta.get("clustering_columns", [])
        sort_order = clustering_columns if clustering_columns else []

        # Generate compaction config with recommendation
        compaction_config: dict[str, Any] = {
            "strategy": "binpack",
            "sort_columns": [],
        }
        if clustering_columns:
            compaction_config["recommended_strategy"] = "sort"
            compaction_config["recommended_sort_columns"] = list(
                clustering_columns
            )

        # Check for naming conflicts
        if proposed_name.lower() in ATHENA_RESERVED_WORDS:
            warnings.append(
                f"Proposed table name '{proposed_name}' conflicts with "
                f"an Athena reserved word. Consider renaming."
            )

        # Check for deeply nested structs
        for col in columns:
            if col.get("type", "").upper() in ("STRUCT", "RECORD"):
                max_depth = self._get_max_struct_depth(col.get("fields", []))
                if max_depth > 15:
                    warnings.append(
                        f"Column '{col.get('name')}' has STRUCT nesting "
                        f"depth {max_depth} (exceeds 15). Levels beyond "
                        f"15 will be flattened to JSON string."
                    )

        return {
            "source_table": source_table,
            "proposed_name": proposed_name,
            "database": glue_database,
            "structure_mode": "recommended",
            "columns": mapped_columns,
            "partition_spec": partition_spec,
            "partition_rationale": partition_rationale,
            "sort_order": sort_order,
            "compaction_config": compaction_config,
            "estimated_rows": table_meta.get("estimated_rows", 0),
            "estimated_size_mb": table_meta.get("estimated_size_bytes", 0)
            / (1024 * 1024),
            "table_properties": dict(DEFAULT_TABLE_PROPERTIES),
            "warnings": warnings,
        }

    def _derive_iceberg_name(self, bq_table_name: str) -> str:
        """Derive Iceberg table name from BQ table name.

        Lowercases the name and replaces special characters with underscores.

        Args:
            bq_table_name: Original BigQuery table name.

        Returns:
            A valid Iceberg table name.
        """
        name = bq_table_name.lower()
        name = re.sub(r"[^a-z0-9_]", "_", name)
        # Remove leading/trailing underscores and collapse multiples
        name = re.sub(r"_+", "_", name).strip("_")
        return name if name else "unnamed_table"

    def _bq_type_to_iceberg_str(self, bq_type: str) -> str:
        """Convert a BQ type name to a human-readable Iceberg type string.

        Args:
            bq_type: BigQuery type name.

        Returns:
            String representation of the Iceberg type.
        """
        type_str_map = {
            "STRING": "string",
            "BYTES": "binary",
            "INT64": "long",
            "INTEGER": "long",
            "FLOAT64": "double",
            "FLOAT": "double",
            "NUMERIC": "decimal(38,9)",
            "BIGNUMERIC": "decimal(38,18)",
            "BOOLEAN": "boolean",
            "BOOL": "boolean",
            "DATE": "date",
            "DATETIME": "timestamp",
            "TIMESTAMP": "timestamptz",
            "TIME": "time",
            "GEOGRAPHY": "string",
            "JSON": "string",
            "STRUCT": "struct",
            "RECORD": "struct",
            "ARRAY": "list",
        }
        return type_str_map.get(bq_type.strip().upper(), "string")

    def _get_max_struct_depth(
        self, fields: list[dict], current_depth: int = 1
    ) -> int:
        """Recursively determine the maximum nesting depth of STRUCT fields.

        Args:
            fields: List of nested field definitions.
            current_depth: Current recursion depth.

        Returns:
            Maximum nesting depth found.
        """
        max_depth = current_depth
        for field in fields:
            if field.get("type", "").upper() in ("STRUCT", "RECORD"):
                sub_fields = field.get("fields", [])
                if sub_fields:
                    depth = self._get_max_struct_depth(
                        sub_fields, current_depth + 1
                    )
                    max_depth = max(max_depth, depth)
        return max_depth

    def _generate_prerequisites(
        self, destination_type: str, migration: Any = None
    ) -> dict:
        """Generate the prerequisites checklist based on destination type.

        Args:
            destination_type: Either 'iceberg_s3' or 'iceberg_s3_tables'.
            migration: The MigrationBQIceberg model instance (optional).

        Returns:
            Dict containing categorized prerequisite items.
        """
        prerequisites = {
            "iam_permissions": REQUIRED_IAM_PERMISSIONS["s3"]
            + REQUIRED_IAM_PERMISSIONS["glue"]
            + REQUIRED_IAM_PERMISSIONS["athena"],
            "s3_bucket_access": (
                "Verify S3 bucket exists and write access is confirmed"
            ),
            "glue_database": (
                "Glue Data Catalog database exists or permission to create it"
            ),
            "athena_workgroup": (
                "Athena workgroup configured for verification queries"
            ),
            "network": (
                "VPC endpoints for S3 and Glue configured if applicable"
            ),
        }

        if destination_type == "iceberg_s3_tables":
            prerequisites["s3_tables"] = {
                "table_bucket": "S3 table bucket created",
                "namespace": "Namespace setup (user-provided name required)",
                "permissions": REQUIRED_IAM_PERMISSIONS["s3_tables"],
            }

            # Add Lake Formation prerequisites for S3 Tables destinations
            table_bucket_arn = getattr(migration, "table_bucket_arn", None) or ""
            glue_database = getattr(migration, "glue_database_name", "default_db")
            aws_region = getattr(migration, "aws_region", "us-east-1")
            account_id = ""

            # Derive account_id and glue.id from table bucket ARN
            glue_id = None
            if table_bucket_arn:
                try:
                    from .s3_tables_adapter import S3TablesAdapter

                    glue_id = S3TablesAdapter.derive_glue_id(table_bucket_arn)
                    # Extract account_id from ARN
                    arn_match = re.match(
                        r"^arn:aws:s3tables:[a-z0-9-]+:(\d{12}):bucket/.+$",
                        table_bucket_arn,
                    )
                    if arn_match:
                        account_id = arn_match.group(1)
                except (ValueError, ImportError):
                    logger.warning(
                        "Could not derive glue.id from table bucket ARN: %s",
                        table_bucket_arn,
                    )

            prerequisites["lake_formation"] = (
                self._generate_lake_formation_prerequisites(
                    table_bucket_arn=table_bucket_arn,
                    glue_database=glue_database,
                    aws_region=aws_region,
                    account_id=account_id,
                )
            )

            if glue_id:
                prerequisites["glue_id"] = glue_id

        return prerequisites

    def _generate_lake_formation_prerequisites(
        self,
        table_bucket_arn: str,
        glue_database: str,
        aws_region: str,
        account_id: str,
    ) -> list[dict]:
        """Generate Lake Formation prerequisite checklist items.

        Each item is an actionable checklist entry with the specific
        ARN or permission string the user needs to configure.

        Args:
            table_bucket_arn: The S3 Tables bucket ARN.
            glue_database: The Glue catalog database name.
            aws_region: The AWS region for the deployment.
            account_id: The 12-digit AWS account ID.

        Returns:
            List of dicts with keys: description, arn_or_permission, action_type
        """
        items: list[dict] = []

        # 1. Data location permission on the S3 Tables bucket ARN
        items.append({
            "description": (
                "Grant Lake Formation DATA_LOCATION_ACCESS on the S3 Tables "
                "bucket ARN (note: this uses the bucket ARN, not an s3:// path)"
            ),
            "arn_or_permission": table_bucket_arn or "<table-bucket-arn>",
            "action_type": "data_location_permission",
        })

        # 2. DESCRIBE permission on the Glue catalog database
        glue_db_arn = (
            f"arn:aws:glue:{aws_region}:{account_id}:database/{glue_database}"
            if account_id and aws_region
            else f"arn:aws:glue:<region>:<account-id>:database/{glue_database}"
        )
        items.append({
            "description": (
                "Grant Lake Formation DESCRIBE permission on the Glue "
                "catalog database"
            ),
            "arn_or_permission": glue_db_arn,
            "action_type": "DESCRIBE",
        })

        # 3. SELECT permission on the Glue catalog tables
        glue_tables_arn = (
            f"arn:aws:glue:{aws_region}:{account_id}:table/{glue_database}/*"
            if account_id and aws_region
            else f"arn:aws:glue:<region>:<account-id>:table/{glue_database}/*"
        )
        items.append({
            "description": (
                "Grant Lake Formation SELECT permission on all Glue catalog "
                "tables within the database"
            ),
            "arn_or_permission": glue_tables_arn,
            "action_type": "SELECT",
        })

        # 4. lakeformation:GetDataAccess IAM permission on execution role
        items.append({
            "description": (
                "Add lakeformation:GetDataAccess IAM permission to the "
                "execution role that performs the migration"
            ),
            "arn_or_permission": "lakeformation:GetDataAccess",
            "action_type": "iam_permission",
        })

        # 5. Lake Formation permissions granted to the Glue execution role
        items.append({
            "description": (
                "Grant Lake Formation permissions to the Glue execution role "
                "(the role used by the Glue catalog to access S3 Tables data)"
            ),
            "arn_or_permission": (
                f"arn:aws:iam::{account_id}:role/<glue-execution-role>"
                if account_id
                else "arn:aws:iam::<account-id>:role/<glue-execution-role>"
            ),
            "action_type": "glue_execution_role",
        })

        return items

    def _generate_global_warnings(
        self, tables: list[dict], total_size_bytes: int
    ) -> list[str]:
        """Generate global-level warnings for the report.

        Args:
            tables: List of per-table report dicts.
            total_size_bytes: Total estimated data size in bytes.

        Returns:
            List of global warning strings.
        """
        warnings = []

        # Estimated total storage footprint
        total_gb = total_size_bytes / (1024**3)
        if total_gb > 100:
            warnings.append(
                f"Total estimated storage footprint is {total_gb:.1f} GB. "
                f"Consider phased migration for large datasets."
            )

        # Check for tables with no partitioning
        unpartitioned = [
            t["source_table"]
            for t in tables
            if t.get("partition_spec") is None
        ]
        if unpartitioned and len(unpartitioned) > 3:
            warnings.append(
                f"{len(unpartitioned)} tables have no partitioning. "
                f"Consider adding partitions for query performance."
            )

        return warnings

    def apply_overrides(self, report: dict, overrides: dict) -> dict:
        """Apply user overrides to the structure report.

        Supports partition changes, table exclusions, and custom properties.

        Args:
            report: The generated structure report dict.
            overrides: Dict containing override specifications:
                - excluded_tables: list of table names to exclude
                - table overrides keyed by source_table name, each containing:
                  - partition_spec: {column, transform}
                  - sort_order: list of column names
                  - custom_properties: dict of key-value pairs

        Returns:
            Updated report dict with overrides applied.
        """
        if not overrides:
            return report

        # Handle table exclusions
        excluded_tables = overrides.get("excluded_tables", [])
        if excluded_tables:
            report["tables"] = [
                t
                for t in report["tables"]
                if t["source_table"] not in excluded_tables
            ]
            report["table_count"] = len(report["tables"])
            logger.info(
                "Excluded %d tables from structure report: %s",
                len(excluded_tables),
                excluded_tables,
            )

        # Apply per-table overrides
        for table in report["tables"]:
            table_name = table["source_table"]
            table_overrides = overrides.get(table_name, {})

            if not table_overrides:
                continue

            # Override partition spec
            if "partition_spec" in table_overrides:
                table["partition_spec"] = table_overrides["partition_spec"]
                table["partition_rationale"] = "User-defined override"
                table["structure_mode"] = "overridden"

            # Override sort order
            if "sort_order" in table_overrides:
                table["sort_order"] = table_overrides["sort_order"]
                table["structure_mode"] = "overridden"

            # Add custom properties
            if "custom_properties" in table_overrides:
                table["table_properties"].update(
                    table_overrides["custom_properties"]
                )
                table["structure_mode"] = "overridden"

            logger.info(
                "Applied overrides to table '%s': %s",
                table_name,
                list(table_overrides.keys()),
            )

        return report

    def apply_custom_structure(
        self, report: dict, table_name: str, custom_def: dict
    ) -> dict:
        """Replace system recommendation with user-defined custom structure.

        Args:
            report: The structure report dict.
            table_name: Source table name to replace.
            custom_def: Custom structure definition containing:
                - iceberg_table_name: str
                - columns: list of {name, type, nullable}
                - partition_spec: {column, transform}
                - sort_order: list of {column, direction}
                - table_properties: dict of key-value pairs

        Returns:
            Updated report with custom structure applied.
        """
        for table in report["tables"]:
            if table["source_table"] == table_name:
                # Replace with custom definition
                table["proposed_name"] = custom_def.get(
                    "iceberg_table_name", table["proposed_name"]
                )
                table["structure_mode"] = "custom"

                # Map custom columns
                if "columns" in custom_def:
                    table["columns"] = [
                        {
                            "name": col["name"],
                            "bq_type": "CUSTOM",
                            "iceberg_type": col["type"],
                            "nullable": col.get("nullable", True),
                        }
                        for col in custom_def["columns"]
                    ]

                # Custom partition spec
                if "partition_spec" in custom_def:
                    table["partition_spec"] = custom_def["partition_spec"]
                    table["partition_rationale"] = "User-defined custom structure"

                # Custom sort order
                if "sort_order" in custom_def:
                    table["sort_order"] = [
                        s if isinstance(s, str) else s.get("column", "")
                        for s in custom_def["sort_order"]
                    ]

                # Custom table properties
                if "table_properties" in custom_def:
                    table["table_properties"] = custom_def["table_properties"]

                logger.info(
                    "Applied custom structure for table '%s'", table_name
                )
                break
        else:
            logger.warning(
                "Table '%s' not found in report for custom structure",
                table_name,
            )

        return report

    def validate_custom_structure(
        self, custom_def: dict, source_columns: list[dict]
    ) -> list[str]:
        """Validate user-defined structure against source data.

        Checks for type compatibility, missing columns, and invalid
        Iceberg type names.

        Args:
            custom_def: Custom structure definition with columns list.
            source_columns: Source table column definitions from assessment.

        Returns:
            List of warning strings for any detected incompatibilities.
        """
        warnings: list[str] = []
        custom_columns = custom_def.get("columns", [])

        if not custom_columns:
            warnings.append("Custom structure has no columns defined")
            return warnings

        # Check for invalid Iceberg types
        for col in custom_columns:
            col_type = col.get("type", "").lower()
            # Handle decimal with precision/scale
            base_type = col_type.split("(")[0].strip()
            if base_type not in VALID_ICEBERG_TYPES:
                warnings.append(
                    f"Column '{col.get('name')}' has invalid Iceberg type "
                    f"'{col_type}'. Valid types: {sorted(VALID_ICEBERG_TYPES)}"
                )

        # Check column count mismatch
        source_count = len(source_columns)
        custom_count = len(custom_columns)
        if custom_count < source_count:
            warnings.append(
                f"Custom structure has {custom_count} columns but source "
                f"has {source_count}. Some source data may be lost."
            )

        # Check for source columns not present in custom definition
        source_names = {col.get("name", "").lower() for col in source_columns}
        custom_names = {col.get("name", "").lower() for col in custom_columns}
        missing = source_names - custom_names
        if missing:
            warnings.append(
                f"Source columns not in custom structure: "
                f"{sorted(missing)}. Data in these columns will be lost."
            )

        # Validate partition spec references valid column
        partition_spec = custom_def.get("partition_spec")
        if partition_spec:
            part_col = partition_spec.get("column", "")
            if part_col.lower() not in custom_names:
                warnings.append(
                    f"Partition column '{part_col}' not found in "
                    f"custom column definitions."
                )

        # Validate sort order references valid columns
        sort_order = custom_def.get("sort_order", [])
        for sort_item in sort_order:
            sort_col = (
                sort_item if isinstance(sort_item, str)
                else sort_item.get("column", "")
            )
            if sort_col.lower() not in custom_names:
                warnings.append(
                    f"Sort order column '{sort_col}' not found in "
                    f"custom column definitions."
                )

        return warnings

    def apply_dataset_to_db_mapping(
        self, report: dict, mapping: dict[str, str]
    ) -> dict:
        """Apply BQ dataset → Glue database name mapping.

        Updates the report's dataset_to_db_mapping and assigns each table
        to the appropriate Glue database based on its source dataset.

        Args:
            report: The structure report dict.
            mapping: Dict mapping BQ dataset names to Glue database names.

        Returns:
            Updated report with database assignments applied.
        """
        if not mapping:
            return report

        report["dataset_to_db_mapping"] = mapping

        # Update each table's database assignment
        for table in report["tables"]:
            # Try to find the dataset for this table from the mapping
            source_table = table.get("source_table", "")
            # Check if any dataset key matches (tables may have dataset info)
            for dataset, db_name in mapping.items():
                # Tables from this dataset get assigned to the mapped DB
                if table.get("dataset") == dataset:
                    table["database"] = db_name
                    break

        logger.info(
            "Applied dataset-to-DB mapping: %s",
            mapping,
        )

        return report

    def export_markdown(self, report: dict) -> str:
        """Export the structure report as Markdown for download.

        Args:
            report: The structure report dict.

        Returns:
            Markdown-formatted string of the report.
        """
        lines: list[str] = []
        lines.append("# Iceberg Structure Design Report")
        lines.append("")
        lines.append(f"**Generated:** {report.get('generated_at', 'N/A')}")
        lines.append(
            f"**Destination Type:** {report.get('destination_type', 'N/A')}"
        )
        lines.append(f"**Total Tables:** {report.get('table_count', 0)}")
        total_gb = report.get("total_estimated_size_bytes", 0) / (1024**3)
        lines.append(f"**Estimated Total Size:** {total_gb:.2f} GB")
        lines.append("")

        # Prerequisites section
        lines.append("## Prerequisites Checklist")
        lines.append("")
        prereqs = report.get("prerequisites", {})
        if "iam_permissions" in prereqs:
            lines.append("### IAM Permissions Required")
            lines.append("")
            for perm in prereqs["iam_permissions"]:
                lines.append(f"- `{perm}`")
            lines.append("")
        lines.append(
            f"- {prereqs.get('s3_bucket_access', 'S3 bucket access')}"
        )
        lines.append(f"- {prereqs.get('glue_database', 'Glue database')}")
        lines.append(
            f"- {prereqs.get('athena_workgroup', 'Athena workgroup')}"
        )
        lines.append(f"- {prereqs.get('network', 'Network config')}")
        lines.append("")

        # Tables section
        lines.append("## Table Structures")
        lines.append("")
        for table in report.get("tables", []):
            lines.append(f"### {table['source_table']}")
            lines.append("")
            lines.append(
                f"- **Proposed Name:** `{table.get('proposed_name', '')}`"
            )
            lines.append(
                f"- **Structure Mode:** {table.get('structure_mode', '')}"
            )
            lines.append(
                f"- **Estimated Rows:** "
                f"{table.get('estimated_rows', 0):,}"
            )
            lines.append(
                f"- **Estimated Size:** "
                f"{table.get('estimated_size_mb', 0):.1f} MB"
            )
            lines.append("")

            # Columns table
            columns = table.get("columns", [])
            if columns:
                lines.append("| Column | BQ Type | Iceberg Type | Nullable |")
                lines.append("|--------|---------|--------------|----------|")
                for col in columns:
                    lines.append(
                        f"| {col['name']} | {col['bq_type']} | "
                        f"{col['iceberg_type']} | "
                        f"{'Yes' if col['nullable'] else 'No'} |"
                    )
                lines.append("")

            # Partition spec
            part_spec = table.get("partition_spec")
            if part_spec:
                lines.append(
                    f"**Partition:** `{part_spec.get('transform', '')}("
                    f"{part_spec.get('column', '')})`"
                )
                if table.get("partition_rationale"):
                    lines.append(
                        f"  - Rationale: {table['partition_rationale']}"
                    )
                lines.append("")

            # Sort order
            sort_order = table.get("sort_order", [])
            if sort_order:
                lines.append(f"**Sort Order:** {', '.join(sort_order)}")
                lines.append("")

            # Table properties
            props = table.get("table_properties", {})
            if props:
                lines.append("**Table Properties:**")
                for k, v in props.items():
                    lines.append(f"- `{k}` = `{v}`")
                lines.append("")

            # Warnings
            table_warnings = table.get("warnings", [])
            if table_warnings:
                lines.append("**Warnings:**")
                for w in table_warnings:
                    lines.append(f"- ⚠️ {w}")
                lines.append("")

        # Global warnings section
        global_warnings = report.get("warnings", [])
        if global_warnings:
            lines.append("## Warnings and Recommendations")
            lines.append("")
            for w in global_warnings:
                lines.append(f"- ⚠️ {w}")
            lines.append("")

        # Dataset to DB mapping
        mapping = report.get("dataset_to_db_mapping", {})
        if mapping:
            lines.append("## Dataset to Database Mapping")
            lines.append("")
            lines.append("| BQ Dataset | Glue Database |")
            lines.append("|------------|---------------|")
            for dataset, db in mapping.items():
                lines.append(f"| {dataset} | {db} |")
            lines.append("")

        return "\n".join(lines)

    def export_pdf(self, report: dict) -> bytes:
        """Export the structure report as PDF for download.

        Generates a simple PDF from the markdown content. Uses a basic
        text-based PDF generation approach without external dependencies.

        Args:
            report: The structure report dict.

        Returns:
            PDF file content as bytes.
        """
        # Generate markdown first, then convert to a simple PDF
        markdown_content = self.export_markdown(report)

        # Simple PDF generation using basic PDF structure
        # In production, this would use a library like reportlab or weasyprint
        pdf_content = self._generate_simple_pdf(markdown_content)

        logger.info(
            "Exported structure report as PDF (%d bytes)",
            len(pdf_content),
        )

        return pdf_content

    def _generate_simple_pdf(self, text_content: str) -> bytes:
        """Generate a minimal PDF from text content.

        Creates a valid PDF 1.4 document with the text content rendered
        as plain text. For production use, replace with reportlab or
        weasyprint for proper formatting.

        Args:
            text_content: Plain text or markdown content.

        Returns:
            Valid PDF file bytes.
        """
        # Minimal PDF structure
        # Strip markdown formatting for plain text PDF
        clean_text = text_content.replace("**", "").replace("`", "")
        clean_text = re.sub(r"^#+\s*", "", clean_text, flags=re.MULTILINE)
        clean_text = re.sub(r"\|.*\|", "", clean_text)
        clean_text = re.sub(r"^-+$", "", clean_text, flags=re.MULTILINE)

        # Escape special PDF characters
        clean_text = (
            clean_text.replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )

        # Truncate to reasonable PDF size
        lines = [
            line for line in clean_text.split("\n") if line.strip()
        ][:200]

        # Build PDF content
        content_lines = []
        y_pos = 750
        for line in lines:
            if y_pos < 50:
                break
            content_lines.append(f"BT /F1 10 Tf {50} {y_pos} Td ({line}) Tj ET")
            y_pos -= 14

        stream_content = "\n".join(content_lines)
        stream_length = len(stream_content)

        pdf = (
            "%PDF-1.4\n"
            "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            "3 0 obj\n<< /Type /Page /Parent 2 0 R "
            "/MediaBox [0 0 612 792] "
            "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\n"
            "endobj\n"
            f"4 0 obj\n<< /Length {stream_length} >>\nstream\n"
            f"{stream_content}\n"
            "endstream\nendobj\n"
            "5 0 obj\n<< /Type /Font /Subtype /Type1 "
            "/BaseFont /Helvetica >>\nendobj\n"
            "xref\n0 6\n"
            "trailer\n<< /Size 6 /Root 1 0 R >>\n"
            "startxref\n0\n%%EOF"
        )

        return pdf.encode("latin-1")
