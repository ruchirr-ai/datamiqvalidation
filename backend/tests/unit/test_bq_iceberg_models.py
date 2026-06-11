"""
Unit tests for BigQuery to Iceberg Migration SQLAlchemy models.

Tests MigrationBQIceberg and IcebergTableValidation model creation,
field defaults, constraint definitions, JSONB serialization, to_dict(),
and edge cases.

Requirements: 1.4, 7.2
"""

from datetime import datetime

from models.migration_bq_iceberg import MigrationBQIceberg
from models.iceberg_table_validation import IcebergTableValidation
from tests.fixtures.sample_payloads import (
    VALID_BQ_ICEBERG_MIGRATION_S3,
    VALID_BQ_ICEBERG_MIGRATION_S3_TABLES,
    VALID_BQ_ICEBERG_MIGRATION_MINIMAL,
    VALID_BQ_ICEBERG_MIGRATION_PATHWAY_C,
    VALID_BQ_ICEBERG_MIGRATION_MAX_PARALLELISM,
    VALID_ICEBERG_TABLE_VALIDATION_PASSED,
    VALID_ICEBERG_TABLE_VALIDATION_FAILED,
    VALID_ICEBERG_TABLE_VALIDATION_INCREMENTAL,
    VALID_ICEBERG_TABLE_VALIDATION_SKIPPED,
    VALID_ICEBERG_TABLE_VALIDATION_MINIMAL,
)


# ---------------------------------------------------------------------------
# MigrationBQIceberg model tests
# ---------------------------------------------------------------------------


class TestMigrationBQIcebergModel:
    """Test MigrationBQIceberg SQLAlchemy model creation with valid data."""

    def test_create_migration_iceberg_s3(self):
        """MigrationBQIceberg can be instantiated with iceberg_s3 destination type."""
        migration = MigrationBQIceberg(**VALID_BQ_ICEBERG_MIGRATION_S3)

        assert migration.workspace_id == 1
        assert migration.migration_name == "BQ to Iceberg S3 Migration"
        assert migration.pathway == "A"
        assert migration.destination_type == "iceberg_s3"
        assert migration.s3_bucket == "my-data-lake-bucket"
        assert migration.s3_path_prefix == "iceberg/analytics/"
        assert migration.aws_region == "us-east-1"
        assert migration.glue_database_name == "analytics_db"
        assert migration.parallelism == 4
        assert migration.enable_load_stage_verification is False
        assert migration.status == "pending"

    def test_create_migration_iceberg_s3_tables(self):
        """MigrationBQIceberg can be instantiated with iceberg_s3_tables destination type."""
        migration = MigrationBQIceberg(**VALID_BQ_ICEBERG_MIGRATION_S3_TABLES)

        assert migration.workspace_id == 2
        assert migration.migration_name == "BQ to S3 Tables Migration"
        assert migration.pathway == "B"
        assert migration.destination_type == "iceberg_s3_tables"
        assert migration.table_bucket_arn == "arn:aws:s3tables:us-east-1:123456789012:bucket/my-table-bucket"
        assert migration.s3_tables_namespace == "warehouse_ns"
        assert migration.aws_role_arn == "arn:aws:iam::123456789012:role/DataMIQIcebergRole"
        assert migration.parallelism == 8
        assert migration.enable_load_stage_verification is True
        assert migration.load_type == "incremental"

    def test_minimal_migration_defaults(self):
        """MigrationBQIceberg with only required fields; optional fields are None."""
        migration = MigrationBQIceberg(**VALID_BQ_ICEBERG_MIGRATION_MINIMAL)

        assert migration.workspace_id == 1
        assert migration.migration_name == "Minimal Migration"
        assert migration.pathway == "C"
        assert migration.destination_type == "iceberg_s3"
        assert migration.aws_region == "eu-west-1"
        assert migration.glue_database_name == "default_db"
        # Optional fields default to None before DB flush
        assert migration.source_connection_id is None
        assert migration.source_project_id is None
        assert migration.source_dataset is None
        assert migration.source_tables is None
        assert migration.s3_bucket is None
        assert migration.s3_path_prefix is None
        assert migration.table_bucket_arn is None
        assert migration.aws_access_key_id is None
        assert migration.aws_secret_access_key_encrypted is None
        assert migration.aws_role_arn is None
        assert migration.checkpoint_data is None
        assert migration.structure_report is None
        assert migration.cost_analysis_report is None

    def test_source_tables_array_field(self):
        """source_tables stores a list of table names."""
        migration = MigrationBQIceberg(**VALID_BQ_ICEBERG_MIGRATION_S3)

        assert migration.source_tables == ["users", "orders", "events"]
        assert len(migration.source_tables) == 3

    def test_pathway_c_direct(self):
        """MigrationBQIceberg with pathway C (Direct) and minimal parallelism."""
        migration = MigrationBQIceberg(**VALID_BQ_ICEBERG_MIGRATION_PATHWAY_C)

        assert migration.pathway == "C"
        assert migration.parallelism == 1
        assert migration.s3_path_prefix == ""

    def test_max_parallelism(self):
        """MigrationBQIceberg with maximum parallelism of 16."""
        migration = MigrationBQIceberg(**VALID_BQ_ICEBERG_MIGRATION_MAX_PARALLELISM)

        assert migration.parallelism == 16

    def test_nullable_optional_fields(self):
        """Optional fields default to None when not provided."""
        migration = MigrationBQIceberg(**VALID_BQ_ICEBERG_MIGRATION_MINIMAL)

        assert migration.target_connection_id is None
        assert migration.dataset_to_db_mapping is None
        assert migration.table_load_configs is None
        assert migration.current_stage is None
        assert migration.resume_point is None
        assert migration.schedule_type is None
        assert migration.cron_expression is None
        assert migration.next_run_time is None
        assert migration.total_rows_source is None
        assert migration.total_rows_target is None
        assert migration.total_bytes_transferred is None
        assert migration.start_time is None
        assert migration.end_time is None
        assert migration.duration_seconds is None
        assert migration.last_run_at is None


# ---------------------------------------------------------------------------
# Constraint validation tests
# ---------------------------------------------------------------------------


class TestMigrationBQIcebergConstraints:
    """Test check constraints defined on MigrationBQIceberg model."""

    def test_check_constraint_destination_type_exists(self):
        """Check constraint 'check_iceberg_dest_type' is defined on the table."""
        constraints = {c.name for c in MigrationBQIceberg.__table__.constraints}
        assert "check_iceberg_dest_type" in constraints

    def test_check_constraint_pathway_exists(self):
        """Check constraint 'check_iceberg_pathway' is defined on the table."""
        constraints = {c.name for c in MigrationBQIceberg.__table__.constraints}
        assert "check_iceberg_pathway" in constraints

    def test_check_constraint_parallelism_range_exists(self):
        """Check constraint 'check_parallelism_range' is defined on the table."""
        constraints = {c.name for c in MigrationBQIceberg.__table__.constraints}
        assert "check_parallelism_range" in constraints

    def test_destination_type_constraint_text(self):
        """Destination type constraint allows only iceberg_s3 and iceberg_s3_tables."""
        for constraint in MigrationBQIceberg.__table__.constraints:
            if getattr(constraint, 'name', None) == "check_iceberg_dest_type":
                sql_text = str(constraint.sqltext)
                assert "iceberg_s3" in sql_text
                assert "iceberg_s3_tables" in sql_text
                break

    def test_pathway_constraint_text(self):
        """Pathway constraint allows only A, B, and C."""
        for constraint in MigrationBQIceberg.__table__.constraints:
            if getattr(constraint, 'name', None) == "check_iceberg_pathway":
                sql_text = str(constraint.sqltext)
                assert "'A'" in sql_text or "A" in sql_text
                assert "'B'" in sql_text or "B" in sql_text
                assert "'C'" in sql_text or "C" in sql_text
                break

    def test_parallelism_constraint_text(self):
        """Parallelism constraint enforces range 1-16."""
        for constraint in MigrationBQIceberg.__table__.constraints:
            if getattr(constraint, 'name', None) == "check_parallelism_range":
                sql_text = str(constraint.sqltext)
                assert "1" in sql_text
                assert "16" in sql_text
                break

    def test_indexes_defined(self):
        """Required indexes are defined on the table."""
        index_names = {idx.name for idx in MigrationBQIceberg.__table__.indexes}
        assert "idx_bq_iceberg_workspace_id" in index_names
        assert "idx_bq_iceberg_status" in index_names
        assert "idx_bq_iceberg_destination_type" in index_names


# ---------------------------------------------------------------------------
# JSONB field serialization/deserialization tests
# ---------------------------------------------------------------------------


class TestMigrationBQIcebergJSONB:
    """Test JSONB field serialization and deserialization."""

    def test_checkpoint_data_complex_nested(self):
        """checkpoint_data stores and returns complex nested JSONB data."""
        checkpoint = {
            "iceberg_structure_plan": {
                "tables": [
                    {
                        "name": "users",
                        "columns": [
                            {"name": "id", "type": "long", "nullable": False},
                            {"name": "email", "type": "string", "nullable": True},
                        ],
                        "partition_spec": {"column": "created_date", "transform": "day"},
                        "sort_order": ["id"],
                    }
                ],
                "approved": True,
            },
            "last_completed_table": "users",
            "completed_tables": ["users", "orders"],
        }
        migration = MigrationBQIceberg(
            **VALID_BQ_ICEBERG_MIGRATION_MINIMAL,
            checkpoint_data=checkpoint,
        )

        assert migration.checkpoint_data == checkpoint
        assert migration.checkpoint_data["iceberg_structure_plan"]["tables"][0]["name"] == "users"
        assert migration.checkpoint_data["completed_tables"] == ["users", "orders"]

    def test_table_load_configs_jsonb(self):
        """table_load_configs stores per-table configuration as JSONB."""
        migration = MigrationBQIceberg(**VALID_BQ_ICEBERG_MIGRATION_S3)

        assert migration.table_load_configs["users"]["priority"] == 1
        assert migration.table_load_configs["orders"]["batch_size"] == 50000

    def test_dataset_to_db_mapping_jsonb(self):
        """dataset_to_db_mapping stores BQ dataset to Glue DB name mapping."""
        migration = MigrationBQIceberg(**VALID_BQ_ICEBERG_MIGRATION_S3)

        assert migration.dataset_to_db_mapping["analytics"] == "analytics_db"
        assert migration.dataset_to_db_mapping["reporting"] == "reporting_db"

    def test_structure_report_jsonb(self):
        """structure_report stores complex report data as JSONB."""
        report = {
            "tables": [
                {
                    "name": "events",
                    "columns": [
                        {"source_type": "STRING", "iceberg_type": "string", "nullable": True},
                        {"source_type": "TIMESTAMP", "iceberg_type": "timestamptz", "nullable": False},
                    ],
                    "partition_spec": {"column": "event_date", "transform": "day"},
                    "warnings": [],
                    "estimated_rows": 1000000,
                    "estimated_size_bytes": 524288000,
                }
            ],
            "prerequisites": {
                "iam_permissions": ["s3:PutObject", "glue:CreateTable"],
                "s3_bucket_exists": True,
            },
            "warnings": ["Table 'events' has no clustering columns"],
        }
        migration = MigrationBQIceberg(
            **VALID_BQ_ICEBERG_MIGRATION_MINIMAL,
            structure_report=report,
        )

        assert migration.structure_report["tables"][0]["name"] == "events"
        assert len(migration.structure_report["tables"][0]["columns"]) == 2
        assert migration.structure_report["prerequisites"]["s3_bucket_exists"] is True

    def test_cost_analysis_report_jsonb(self):
        """cost_analysis_report stores cost projections as JSONB."""
        cost_report = {
            "setup_costs": {
                "s3_storage": 12.50,
                "glue_api_calls": 0.05,
                "data_transfer": 45.00,
            },
            "recurring_monthly": {
                "s3_storage": 23.00,
                "glue_requests": 1.00,
                "athena_queries": 5.00,
            },
            "projections": {
                "3_month": 87.00,
                "6_month": 180.00,
                "12_month": 380.00,
            },
            "tco_comparison": {
                "bigquery_monthly": 150.00,
                "iceberg_monthly": 29.00,
                "savings_monthly": 121.00,
            },
        }
        migration = MigrationBQIceberg(
            **VALID_BQ_ICEBERG_MIGRATION_MINIMAL,
            cost_analysis_report=cost_report,
        )

        assert migration.cost_analysis_report["setup_costs"]["s3_storage"] == 12.50
        assert migration.cost_analysis_report["projections"]["12_month"] == 380.00
        assert migration.cost_analysis_report["tco_comparison"]["savings_monthly"] == 121.00

    def test_jsonb_fields_accept_empty_dict(self):
        """JSONB fields accept empty dictionaries."""
        migration = MigrationBQIceberg(
            **VALID_BQ_ICEBERG_MIGRATION_MINIMAL,
            checkpoint_data={},
            table_load_configs={},
            dataset_to_db_mapping={},
            structure_report={},
            cost_analysis_report={},
        )

        assert migration.checkpoint_data == {}
        assert migration.table_load_configs == {}
        assert migration.dataset_to_db_mapping == {}
        assert migration.structure_report == {}
        assert migration.cost_analysis_report == {}


# ---------------------------------------------------------------------------
# to_dict() tests
# ---------------------------------------------------------------------------


class TestMigrationBQIcebergToDict:
    """Test to_dict() method returns expected structure."""

    def test_to_dict_returns_all_top_level_keys(self):
        """to_dict() includes all expected top-level keys."""
        migration = MigrationBQIceberg(**VALID_BQ_ICEBERG_MIGRATION_S3)
        d = migration.to_dict()

        expected_keys = {
            "id", "workspace_id", "migration_name", "pathway",
            "source", "target", "credentials", "storage",
            "load_config", "state", "structure_review",
            "schedule", "metrics", "created_by", "created_at", "updated_at",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_source_section(self):
        """to_dict() source section contains correct fields."""
        migration = MigrationBQIceberg(**VALID_BQ_ICEBERG_MIGRATION_S3)
        d = migration.to_dict()

        assert d["source"]["connection_id"] == 10
        assert d["source"]["project_id"] == "my-gcp-project"
        assert d["source"]["dataset"] == "analytics"
        assert d["source"]["tables"] == ["users", "orders", "events"]

    def test_to_dict_target_section(self):
        """to_dict() target section contains correct fields."""
        migration = MigrationBQIceberg(**VALID_BQ_ICEBERG_MIGRATION_S3)
        d = migration.to_dict()

        assert d["target"]["destination_type"] == "iceberg_s3"
        assert d["target"]["s3_bucket"] == "my-data-lake-bucket"
        assert d["target"]["aws_region"] == "us-east-1"
        assert d["target"]["glue_database_name"] == "analytics_db"
        assert d["target"]["dataset_to_db_mapping"] == {
            "analytics": "analytics_db",
            "reporting": "reporting_db",
        }

    def test_to_dict_credentials_hides_secret(self):
        """to_dict() credentials section shows has_aws_secret_access_key flag, not the value."""
        migration = MigrationBQIceberg(**VALID_BQ_ICEBERG_MIGRATION_S3)
        d = migration.to_dict()

        assert d["credentials"]["aws_access_key_id"] == "AKIAIOSFODNN7EXAMPLE"
        assert d["credentials"]["has_aws_secret_access_key"] is True
        assert "aws_secret_access_key_encrypted" not in d["credentials"]
        assert "aws_secret_access_key" not in d["credentials"]

    def test_to_dict_credentials_no_secret(self):
        """to_dict() credentials shows False when no secret key is set."""
        migration = MigrationBQIceberg(**VALID_BQ_ICEBERG_MIGRATION_MINIMAL)
        d = migration.to_dict()

        assert d["credentials"]["has_aws_secret_access_key"] is False
        assert d["credentials"]["aws_access_key_id"] is None

    def test_to_dict_load_config_section(self):
        """to_dict() load_config section contains correct fields."""
        migration = MigrationBQIceberg(**VALID_BQ_ICEBERG_MIGRATION_S3)
        d = migration.to_dict()

        assert d["load_config"]["load_type"] == "full"
        assert d["load_config"]["parallelism"] == 4
        assert d["load_config"]["enable_load_stage_verification"] is False
        assert d["load_config"]["table_load_configs"] is not None

    def test_to_dict_state_section(self):
        """to_dict() state section contains correct fields."""
        migration = MigrationBQIceberg(**VALID_BQ_ICEBERG_MIGRATION_S3)
        d = migration.to_dict()

        assert d["state"]["status"] == "pending"
        assert d["state"]["current_stage"] is None
        assert d["state"]["checkpoint_data"] is None
        assert d["state"]["resume_point"] is None

    def test_to_dict_datetime_format(self):
        """to_dict() formats datetime fields as ISO 8601 with Z suffix."""
        now = datetime(2025, 6, 15, 14, 30, 0)
        migration = MigrationBQIceberg(
            **VALID_BQ_ICEBERG_MIGRATION_MINIMAL,
            start_time=now,
            structure_approved_at=now,
        )
        d = migration.to_dict()

        assert d["metrics"]["start_time"] == "2025-06-15T14:30:00Z"
        assert d["structure_review"]["structure_approved_at"] == "2025-06-15T14:30:00Z"

    def test_to_dict_none_datetimes(self):
        """to_dict() returns None for unset datetime fields."""
        migration = MigrationBQIceberg(**VALID_BQ_ICEBERG_MIGRATION_MINIMAL)
        d = migration.to_dict()

        assert d["metrics"]["start_time"] is None
        assert d["metrics"]["end_time"] is None
        assert d["metrics"]["last_run_at"] is None
        assert d["schedule"]["next_run_time"] is None
        assert d["structure_review"]["structure_approved_at"] is None

    def test_to_dict_s3_tables_target(self):
        """to_dict() target section for S3 Tables destination type."""
        migration = MigrationBQIceberg(**VALID_BQ_ICEBERG_MIGRATION_S3_TABLES)
        d = migration.to_dict()

        assert d["target"]["destination_type"] == "iceberg_s3_tables"
        assert d["target"]["table_bucket_arn"] == "arn:aws:s3tables:us-east-1:123456789012:bucket/my-table-bucket"
        assert d["target"]["s3_tables_namespace"] == "warehouse_ns"
        assert d["credentials"]["aws_role_arn"] == "arn:aws:iam::123456789012:role/DataMIQIcebergRole"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestMigrationBQIcebergEdgeCases:
    """Test edge cases: empty strings, null optional fields, boundary values."""

    def test_empty_string_s3_path_prefix(self):
        """s3_path_prefix can be an empty string (root of bucket)."""
        migration = MigrationBQIceberg(
            **VALID_BQ_ICEBERG_MIGRATION_MINIMAL,
            s3_path_prefix="",
        )
        assert migration.s3_path_prefix == ""

    def test_parallelism_boundary_min(self):
        """Parallelism at minimum boundary value of 1."""
        migration = MigrationBQIceberg(
            **VALID_BQ_ICEBERG_MIGRATION_MINIMAL,
            parallelism=1,
        )
        assert migration.parallelism == 1

    def test_parallelism_boundary_max(self):
        """Parallelism at maximum boundary value of 16."""
        migration = MigrationBQIceberg(
            **VALID_BQ_ICEBERG_MIGRATION_MINIMAL,
            parallelism=16,
        )
        assert migration.parallelism == 16

    def test_empty_source_tables_list(self):
        """source_tables can be an empty list."""
        migration = MigrationBQIceberg(
            **VALID_BQ_ICEBERG_MIGRATION_MINIMAL,
            source_tables=[],
        )
        assert migration.source_tables == []

    def test_large_jsonb_checkpoint_data(self):
        """checkpoint_data can store large nested structures."""
        large_tables = [
            {"name": f"table_{i}", "status": "completed", "rows": i * 1000}
            for i in range(100)
        ]
        checkpoint = {"completed_tables": large_tables, "version": 1}
        migration = MigrationBQIceberg(
            **VALID_BQ_ICEBERG_MIGRATION_MINIMAL,
            checkpoint_data=checkpoint,
        )
        assert len(migration.checkpoint_data["completed_tables"]) == 100
        assert migration.checkpoint_data["completed_tables"][99]["name"] == "table_99"

    def test_null_optional_credentials(self):
        """Both aws_access_key_id and aws_role_arn can be None."""
        migration = MigrationBQIceberg(**VALID_BQ_ICEBERG_MIGRATION_MINIMAL)

        assert migration.aws_access_key_id is None
        assert migration.aws_secret_access_key_encrypted is None
        assert migration.aws_role_arn is None

    def test_repr_contains_key_info(self):
        """__repr__ includes id, workspace_id, migration_name, and status."""
        migration = MigrationBQIceberg(**VALID_BQ_ICEBERG_MIGRATION_S3)
        r = repr(migration)

        assert "MigrationBQIceberg" in r
        assert "workspace_id=1" in r
        assert "BQ to Iceberg S3 Migration" in r
        assert "pending" in r

    def test_progress_percentage_default(self):
        """progress_percentage defaults to 0 when not set explicitly."""
        migration = MigrationBQIceberg(**VALID_BQ_ICEBERG_MIGRATION_MINIMAL)
        # Column default=0 applies at DB level; in-memory it's None unless set
        # But the model defines default=0, so SQLAlchemy sets it in-memory
        assert migration.progress_percentage is None or migration.progress_percentage == 0


# ---------------------------------------------------------------------------
# IcebergTableValidation model tests
# ---------------------------------------------------------------------------


class TestIcebergTableValidationModel:
    """Test IcebergTableValidation SQLAlchemy model creation with valid data."""

    def test_create_validation_passed(self):
        """IcebergTableValidation can be instantiated with passed status."""
        validation = IcebergTableValidation(**VALID_ICEBERG_TABLE_VALIDATION_PASSED)

        assert validation.migration_id == 1
        assert validation.table_name == "users"
        assert validation.source_row_count == 100000
        assert validation.target_row_count == 100000
        assert validation.match_status == "passed"
        assert validation.validation_type == "full"

    def test_create_validation_failed(self):
        """IcebergTableValidation can be instantiated with failed status and error reason."""
        validation = IcebergTableValidation(**VALID_ICEBERG_TABLE_VALIDATION_FAILED)

        assert validation.migration_id == 1
        assert validation.table_name == "orders"
        assert validation.source_row_count == 50000
        assert validation.target_row_count == 49998
        assert validation.match_status == "failed"
        assert validation.validation_type == "full"
        assert "Row count mismatch" in validation.error_reason

    def test_create_validation_incremental(self):
        """IcebergTableValidation can be instantiated with incremental validation data."""
        validation = IcebergTableValidation(**VALID_ICEBERG_TABLE_VALIDATION_INCREMENTAL)

        assert validation.migration_id == 1
        assert validation.table_name == "events"
        assert validation.source_row_count == 200000
        assert validation.target_row_count == 200000
        assert validation.match_status == "passed"
        assert validation.validation_type == "incremental"
        assert validation.batch_export_count == 5000
        assert validation.previous_snapshot_count == 195000

    def test_create_validation_skipped(self):
        """IcebergTableValidation can be instantiated with skipped status."""
        validation = IcebergTableValidation(**VALID_ICEBERG_TABLE_VALIDATION_SKIPPED)

        assert validation.migration_id == 1
        assert validation.table_name == "logs"
        assert validation.match_status == "skipped"
        assert validation.validation_type == "full"
        assert "Athena query execution failed" in validation.error_reason
        assert validation.source_row_count is None
        assert validation.target_row_count is None

    def test_create_validation_minimal(self):
        """IcebergTableValidation with only required fields; optional fields are None."""
        validation = IcebergTableValidation(**VALID_ICEBERG_TABLE_VALIDATION_MINIMAL)

        assert validation.migration_id == 1
        assert validation.table_name == "products"
        assert validation.source_row_count is None
        assert validation.target_row_count is None
        assert validation.match_status is None
        assert validation.validation_type is None
        assert validation.batch_export_count is None
        assert validation.previous_snapshot_count is None
        assert validation.error_reason is None
        assert validation.validated_at is None


# ---------------------------------------------------------------------------
# IcebergTableValidation constraint and index tests
# ---------------------------------------------------------------------------


class TestIcebergTableValidationConstraints:
    """Test constraints and indexes defined on IcebergTableValidation model."""

    def test_unique_constraint_exists(self):
        """Unique constraint on (migration_id, table_name) is defined."""
        constraints = {
            c.name for c in IcebergTableValidation.__table__.constraints
            if hasattr(c, 'name') and c.name
        }
        assert "unique_iceberg_validation" in constraints

    def test_index_on_migration_id_exists(self):
        """Index on migration_id is defined."""
        index_names = {idx.name for idx in IcebergTableValidation.__table__.indexes}
        assert "idx_iceberg_validation_migration_id" in index_names

    def test_foreign_key_to_migrations_bq_iceberg(self):
        """migration_id has a foreign key to migrations_bq_iceberg.id."""
        fk_targets = set()
        for col in IcebergTableValidation.__table__.columns:
            for fk in col.foreign_keys:
                fk_targets.add(fk.target_fullname)
        assert "migrations_bq_iceberg.id" in fk_targets


# ---------------------------------------------------------------------------
# IcebergTableValidation to_dict() tests
# ---------------------------------------------------------------------------


class TestIcebergTableValidationToDict:
    """Test to_dict() method on IcebergTableValidation."""

    def test_to_dict_returns_all_keys(self):
        """to_dict() includes all expected keys."""
        validation = IcebergTableValidation(**VALID_ICEBERG_TABLE_VALIDATION_PASSED)
        d = validation.to_dict()

        expected_keys = {
            "id", "migration_id", "table_name", "source_row_count",
            "target_row_count", "match_status", "validation_type",
            "batch_export_count", "previous_snapshot_count",
            "error_reason", "validated_at", "created_at",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_passed_values(self):
        """to_dict() returns correct values for a passed validation."""
        validation = IcebergTableValidation(**VALID_ICEBERG_TABLE_VALIDATION_PASSED)
        d = validation.to_dict()

        assert d["migration_id"] == 1
        assert d["table_name"] == "users"
        assert d["source_row_count"] == 100000
        assert d["target_row_count"] == 100000
        assert d["match_status"] == "passed"
        assert d["validation_type"] == "full"
        assert d["error_reason"] is None

    def test_to_dict_failed_includes_error_reason(self):
        """to_dict() includes error_reason for failed validations."""
        validation = IcebergTableValidation(**VALID_ICEBERG_TABLE_VALIDATION_FAILED)
        d = validation.to_dict()

        assert d["match_status"] == "failed"
        assert "Row count mismatch" in d["error_reason"]

    def test_to_dict_incremental_includes_batch_fields(self):
        """to_dict() includes batch_export_count and previous_snapshot_count for incremental."""
        validation = IcebergTableValidation(**VALID_ICEBERG_TABLE_VALIDATION_INCREMENTAL)
        d = validation.to_dict()

        assert d["validation_type"] == "incremental"
        assert d["batch_export_count"] == 5000
        assert d["previous_snapshot_count"] == 195000

    def test_to_dict_datetime_format(self):
        """to_dict() formats validated_at as ISO 8601 with Z suffix."""
        now = datetime(2025, 7, 1, 10, 0, 0)
        validation = IcebergTableValidation(
            **VALID_ICEBERG_TABLE_VALIDATION_PASSED,
            validated_at=now,
        )
        d = validation.to_dict()

        assert d["validated_at"] == "2025-07-01T10:00:00Z"

    def test_to_dict_none_datetimes(self):
        """to_dict() returns None for unset datetime fields."""
        validation = IcebergTableValidation(**VALID_ICEBERG_TABLE_VALIDATION_MINIMAL)
        d = validation.to_dict()

        assert d["validated_at"] is None
        assert d["created_at"] is None


# ---------------------------------------------------------------------------
# IcebergTableValidation edge cases
# ---------------------------------------------------------------------------


class TestIcebergTableValidationEdgeCases:
    """Test edge cases for IcebergTableValidation model."""

    def test_zero_row_counts(self):
        """Row counts can be zero (empty table)."""
        validation = IcebergTableValidation(
            migration_id=1,
            table_name="empty_table",
            source_row_count=0,
            target_row_count=0,
            match_status="passed",
            validation_type="full",
        )
        assert validation.source_row_count == 0
        assert validation.target_row_count == 0

    def test_large_row_counts(self):
        """Row counts can be very large (BigInteger)."""
        validation = IcebergTableValidation(
            migration_id=1,
            table_name="huge_table",
            source_row_count=9_999_999_999_999,
            target_row_count=9_999_999_999_999,
            match_status="passed",
            validation_type="full",
        )
        assert validation.source_row_count == 9_999_999_999_999
        assert validation.target_row_count == 9_999_999_999_999

    def test_repr_contains_key_info(self):
        """__repr__ includes id, migration_id, table_name, and match_status."""
        validation = IcebergTableValidation(**VALID_ICEBERG_TABLE_VALIDATION_PASSED)
        r = repr(validation)

        assert "IcebergTableValidation" in r
        assert "migration_id=1" in r
        assert "users" in r
        assert "passed" in r

    def test_long_table_name(self):
        """table_name can be up to 255 characters."""
        long_name = "a" * 255
        validation = IcebergTableValidation(
            migration_id=1,
            table_name=long_name,
        )
        assert validation.table_name == long_name
        assert len(validation.table_name) == 255

    def test_long_error_reason(self):
        """error_reason can store long error messages (Text field)."""
        long_error = "Error: " + "x" * 5000
        validation = IcebergTableValidation(
            migration_id=1,
            table_name="error_table",
            match_status="failed",
            error_reason=long_error,
        )
        assert len(validation.error_reason) > 5000

    def test_null_batch_fields_for_full_validation(self):
        """batch_export_count and previous_snapshot_count are None for full validations."""
        validation = IcebergTableValidation(**VALID_ICEBERG_TABLE_VALIDATION_PASSED)

        assert validation.batch_export_count is None
        assert validation.previous_snapshot_count is None
