"""
Unit tests for Data Validation SQLAlchemy models.

Tests ValidationRun and ValidationTableResult model creation,
field defaults, nullable fields, to_dict(), and __repr__().

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.9
"""

from datetime import datetime, timezone

from models.validation_run import ValidationRun
from models.validation_table_result import ValidationTableResult
from tests.fixtures.sample_payloads import (
    VALID_VALIDATION_RUN_DATA,
    VALID_VALIDATION_RUN_COMPLETED,
    VALID_VALIDATION_RUN_MINIMAL,
    VALID_VALIDATION_TABLE_RESULT_DATA,
    VALID_VALIDATION_TABLE_RESULT_FAILED,
    VALID_VALIDATION_TABLE_RESULT_MINIMAL,
    VALID_VALIDATION_TABLE_RESULT_ERROR,
)


# ---------------------------------------------------------------------------
# ValidationRun model tests
# ---------------------------------------------------------------------------


class TestValidationRunModel:
    """Test ValidationRun SQLAlchemy model creation with valid data."""

    def test_create_run_with_valid_data(self):
        """ValidationRun can be instantiated with all fields."""
        run = ValidationRun(**VALID_VALIDATION_RUN_DATA)

        assert run.workspace_id == 1
        assert run.migration_id == 10
        assert run.source_connection_id == 100
        assert run.target_connection_id == 200
        assert run.bedrock_model == "anthropic.claude-3-sonnet-20240229-v1:0"
        assert run.batch_size == 10000
        assert run.type_mapping_overrides == {"STRING": "TEXT"}
        assert run.status == "pending"
        assert run.progress_percentage == 0
        assert run.tables_total == 5
        assert run.tables_passed == 0
        assert run.tables_failed == 0
        assert run.tables_error == 0
        assert run.created_by == "testuser"

    def test_create_completed_run(self):
        """ValidationRun with completed status and summary stats."""
        run = ValidationRun(**VALID_VALIDATION_RUN_COMPLETED)

        assert run.status == "completed"
        assert run.progress_percentage == 100
        assert run.tables_total == 3
        assert run.tables_passed == 2
        assert run.tables_failed == 1
        assert run.tables_error == 0

    def test_minimal_run_defaults(self):
        """ValidationRun with only required fields; Column defaults apply on DB flush."""
        run = ValidationRun(**VALID_VALIDATION_RUN_MINIMAL)

        assert run.workspace_id == 1
        assert run.migration_id == 10
        assert run.created_by == "testuser"
        # Column-level defaults (default=) apply on DB flush, not in-memory.
        # Nullable optional fields are None before flush.
        assert run.bedrock_model is None
        assert run.type_mapping_overrides is None
        assert run.started_at is None
        assert run.completed_at is None
        assert run.duration_seconds is None

    def test_nullable_fields_default_to_none(self):
        """Optional fields default to None when not provided."""
        run = ValidationRun(**VALID_VALIDATION_RUN_MINIMAL)

        assert run.bedrock_model is None
        assert run.run_name is None
        assert run.type_mapping_overrides is None
        assert run.started_at is None
        assert run.completed_at is None
        assert run.duration_seconds is None

    def test_timestamps_can_be_set(self):
        """started_at, completed_at, and duration_seconds can be set."""
        now = datetime.now(timezone.utc)
        run = ValidationRun(
            **VALID_VALIDATION_RUN_MINIMAL,
            started_at=now,
            completed_at=now,
            duration_seconds=120,
        )

        assert run.started_at == now
        assert run.completed_at == now
        assert run.duration_seconds == 120

    def test_to_dict_returns_all_keys(self):
        """to_dict() includes every expected key."""
        run = ValidationRun(**VALID_VALIDATION_RUN_DATA)
        d = run.to_dict()

        expected_keys = {
            "id", "workspace_id", "migration_id",
            "source_connection_id", "target_connection_id",
            "bedrock_model", "batch_size", "type_mapping_overrides",
            "run_name", "status", "progress_percentage",
            "tables_total", "tables_passed", "tables_failed", "tables_error",
            "started_at", "completed_at", "duration_seconds",
            "created_by", "created_at", "updated_at",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_datetime_format(self):
        """to_dict() formats datetime fields as ISO 8601 with Z suffix."""
        now = datetime(2025, 1, 15, 10, 30, 0)
        run = ValidationRun(**VALID_VALIDATION_RUN_MINIMAL, started_at=now)
        d = run.to_dict()

        assert d["started_at"] == "2025-01-15T10:30:00Z"

    def test_to_dict_none_datetimes(self):
        """to_dict() returns None for unset datetime fields."""
        run = ValidationRun(**VALID_VALIDATION_RUN_MINIMAL)
        d = run.to_dict()

        assert d["started_at"] is None
        assert d["completed_at"] is None

    def test_repr_contains_key_info(self):
        """__repr__ includes id, workspace_id, migration_id, and status."""
        run = ValidationRun(**VALID_VALIDATION_RUN_DATA)
        r = repr(run)

        assert "ValidationRun" in r
        assert "workspace_id=1" in r
        assert "migration_id=10" in r
        assert "pending" in r

    def test_jsonb_type_mapping_overrides(self):
        """type_mapping_overrides stores and returns JSONB data correctly."""
        overrides = {"STRING": "TEXT", "INT64": "INTEGER"}
        run = ValidationRun(**VALID_VALIDATION_RUN_MINIMAL, type_mapping_overrides=overrides)

        assert run.type_mapping_overrides == overrides
        assert run.type_mapping_overrides["STRING"] == "TEXT"


# ---------------------------------------------------------------------------
# ValidationTableResult model tests
# ---------------------------------------------------------------------------


class TestValidationTableResultModel:
    """Test ValidationTableResult SQLAlchemy model creation with valid data."""

    def test_create_result_with_valid_data(self):
        """ValidationTableResult can be instantiated with all fields."""
        result = ValidationTableResult(**VALID_VALIDATION_TABLE_RESULT_DATA)

        assert result.run_id == 1
        assert result.workspace_id == 1
        assert result.table_name == "users"
        assert result.dataset_name == "my_dataset"
        assert result.ddl_status == "passed"
        assert result.row_count_status == "passed"
        assert result.data_match_status == "passed"
        assert result.status == "completed"

    def test_create_failed_result(self):
        """ValidationTableResult with failed status and discrepancies."""
        result = ValidationTableResult(**VALID_VALIDATION_TABLE_RESULT_FAILED)

        assert result.ddl_status == "failed"
        assert result.row_count_status == "failed"
        assert result.data_match_status == "failed"
        assert result.status == "failed"
        assert result.ai_analysis is not None
        assert "root_cause" in result.ai_analysis

    def test_create_error_result(self):
        """ValidationTableResult with error status and error message."""
        result = ValidationTableResult(**VALID_VALIDATION_TABLE_RESULT_ERROR)

        assert result.status == "error"
        assert result.error_message == "Connection timeout after 300 seconds"

    def test_minimal_result_defaults(self):
        """ValidationTableResult with only required fields uses correct defaults."""
        result = ValidationTableResult(**VALID_VALIDATION_TABLE_RESULT_MINIMAL)

        assert result.run_id == 1
        assert result.workspace_id == 1
        assert result.table_name == "products"
        assert result.status == "pending"

    def test_nullable_fields_default_to_none(self):
        """Optional fields default to None when not provided."""
        result = ValidationTableResult(**VALID_VALIDATION_TABLE_RESULT_MINIMAL)

        assert result.dataset_name is None
        assert result.ddl_status is None
        assert result.ddl_comparison_result is None
        assert result.row_count_status is None
        assert result.row_count_result is None
        assert result.data_match_status is None
        assert result.data_match_result is None
        assert result.ai_analysis is None
        assert result.error_message is None
        assert result.started_at is None
        assert result.completed_at is None
        assert result.duration_seconds is None

    def test_jsonb_ddl_comparison_result(self):
        """ddl_comparison_result stores JSONB data correctly."""
        result = ValidationTableResult(**VALID_VALIDATION_TABLE_RESULT_DATA)

        assert result.ddl_comparison_result["source_column_count"] == 5
        assert result.ddl_comparison_result["discrepancies"] == []

    def test_jsonb_row_count_result(self):
        """row_count_result stores JSONB data correctly."""
        result = ValidationTableResult(**VALID_VALIDATION_TABLE_RESULT_DATA)

        assert result.row_count_result["source_count"] == 1000
        assert result.row_count_result["difference"] == 0

    def test_jsonb_data_match_result(self):
        """data_match_result stores JSONB data correctly."""
        result = ValidationTableResult(**VALID_VALIDATION_TABLE_RESULT_DATA)

        assert result.data_match_result["total_compared"] == 1000
        assert result.data_match_result["matched_count"] == 1000
        assert result.data_match_result["sample_discrepancies"] == []

    def test_jsonb_ai_analysis(self):
        """ai_analysis stores JSONB data correctly."""
        result = ValidationTableResult(**VALID_VALIDATION_TABLE_RESULT_FAILED)

        assert "root_cause" in result.ai_analysis
        assert "impact_assessment" in result.ai_analysis
        assert "recommended_workarounds" in result.ai_analysis
        assert isinstance(result.ai_analysis["recommended_workarounds"], list)

    def test_to_dict_returns_all_keys(self):
        """to_dict() includes every expected key."""
        result = ValidationTableResult(**VALID_VALIDATION_TABLE_RESULT_DATA)
        d = result.to_dict()

        expected_keys = {
            "id", "run_id", "workspace_id", "table_name", "dataset_name",
            "ddl_status", "ddl_comparison_result",
            "row_count_status", "row_count_result",
            "data_match_status", "data_match_result",
            "ai_analysis", "status", "error_message",
            "started_at", "completed_at", "duration_seconds",
            "created_at", "updated_at",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_datetime_format(self):
        """to_dict() formats datetime fields as ISO 8601 with Z suffix."""
        now = datetime(2025, 1, 15, 10, 30, 0)
        result = ValidationTableResult(
            **VALID_VALIDATION_TABLE_RESULT_MINIMAL, started_at=now
        )
        d = result.to_dict()

        assert d["started_at"] == "2025-01-15T10:30:00Z"

    def test_repr_contains_key_info(self):
        """__repr__ includes id, run_id, table_name, and status."""
        result = ValidationTableResult(**VALID_VALIDATION_TABLE_RESULT_DATA)
        r = repr(result)

        assert "ValidationTableResult" in r
        assert "run_id=1" in r
        assert "users" in r
        assert "completed" in r

    def test_foreign_key_on_run_id(self):
        """run_id column has a foreign key to validation_runs.id."""
        col = ValidationTableResult.__table__.columns["run_id"]
        fk_targets = [fk.target_fullname for fk in col.foreign_keys]

        assert "validation_runs.id" in fk_targets

    def test_cascade_delete_on_foreign_key(self):
        """Foreign key on run_id has ON DELETE CASCADE."""
        col = ValidationTableResult.__table__.columns["run_id"]
        for fk in col.foreign_keys:
            if fk.target_fullname == "validation_runs.id":
                assert fk.ondelete == "CASCADE"
