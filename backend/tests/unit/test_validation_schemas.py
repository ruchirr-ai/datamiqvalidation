"""
Unit tests for Data Validation Pydantic schemas.

Tests CreateValidationRunRequest validation (valid, invalid, edge cases),
ValidationRunStatus and ValidationStepStatus enum validation,
batch_size bounds, and response schema construction.

Requirements: 16.1, 16.11
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from models.validation_schemas import (
    ValidationRunStatus,
    ValidationStepStatus,
    CreateValidationRunRequest,
    ValidationRunResponse,
    ValidationTableResultResponse,
    ValidationTableDetailResponse,
    ValidationReportResponse,
    PaginatedValidationRunsResponse,
)
from tests.fixtures.sample_payloads import (
    VALID_CREATE_VALIDATION_RUN_REQUEST,
    VALID_CREATE_VALIDATION_RUN_MINIMAL,
    INVALID_CREATE_VALIDATION_RUN_MISSING_MIGRATION,
    INVALID_CREATE_VALIDATION_RUN_MISSING_CONNECTION,
    INVALID_CREATE_VALIDATION_RUN_WRONG_TYPES,
)


# ---------------------------------------------------------------------------
# ValidationRunStatus enum tests
# ---------------------------------------------------------------------------


class TestValidationRunStatusEnum:
    """Test ValidationRunStatus enum values and validation."""

    def test_all_valid_statuses(self):
        """All expected run statuses are defined."""
        expected = ["pending", "running", "completed", "failed"]
        for s in expected:
            assert ValidationRunStatus(s) == s

    def test_invalid_status_raises(self):
        """Invalid status strings are rejected."""
        for bad in ["cancelled", "PENDING", "paused", ""]:
            with pytest.raises(ValueError):
                ValidationRunStatus(bad)

    def test_is_str_enum(self):
        """ValidationRunStatus members are usable as plain strings."""
        assert ValidationRunStatus.PENDING == "pending"
        assert isinstance(ValidationRunStatus.RUNNING, str)


# ---------------------------------------------------------------------------
# ValidationStepStatus enum tests
# ---------------------------------------------------------------------------


class TestValidationStepStatusEnum:
    """Test ValidationStepStatus enum values and validation."""

    def test_all_valid_step_statuses(self):
        """All expected step statuses are defined."""
        expected = ["passed", "failed", "error"]
        for s in expected:
            assert ValidationStepStatus(s) == s

    def test_invalid_step_status_raises(self):
        """Invalid step status strings are rejected."""
        for bad in ["pending", "completed", "PASSED", ""]:
            with pytest.raises(ValueError):
                ValidationStepStatus(bad)

    def test_is_str_enum(self):
        """ValidationStepStatus members are usable as plain strings."""
        assert ValidationStepStatus.PASSED == "passed"
        assert isinstance(ValidationStepStatus.ERROR, str)


# ---------------------------------------------------------------------------
# CreateValidationRunRequest — valid payloads
# ---------------------------------------------------------------------------


class TestCreateValidationRunRequestValid:
    """Test CreateValidationRunRequest with valid payloads."""

    def test_full_payload(self):
        """Full payload with all fields passes validation."""
        req = CreateValidationRunRequest(**VALID_CREATE_VALIDATION_RUN_REQUEST)

        assert req.migration_id == 10
        assert req.source_connection_id == 100
        assert req.target_connection_id == 200
        assert req.tables == ["users", "orders"]
        assert req.bedrock_model == "anthropic.claude-3-sonnet-20240229-v1:0"
        assert req.batch_size == 10000
        assert req.type_mapping_overrides == {"STRING": "TEXT"}

    def test_minimal_payload_defaults(self):
        """Minimal payload applies correct defaults."""
        req = CreateValidationRunRequest(**VALID_CREATE_VALIDATION_RUN_MINIMAL)

        assert req.migration_id == 10
        assert req.tables is None
        assert req.bedrock_model is None
        assert req.batch_size == 10000  # default
        assert req.type_mapping_overrides is None

    def test_single_table(self):
        """Single table in list passes validation."""
        req = CreateValidationRunRequest(
            migration_id=1,
            source_connection_id=1,
            target_connection_id=2,
            tables=["only_table"],
        )
        assert req.tables == ["only_table"]

    def test_empty_table_list(self):
        """Empty table list passes validation (service retrieves from migration)."""
        req = CreateValidationRunRequest(
            migration_id=1,
            source_connection_id=1,
            target_connection_id=2,
            tables=[],
        )
        assert req.tables == []

    def test_100_tables(self):
        """100 tables in list passes validation."""
        tables = [f"table_{i}" for i in range(100)]
        req = CreateValidationRunRequest(
            migration_id=1,
            source_connection_id=1,
            target_connection_id=2,
            tables=tables,
        )
        assert len(req.tables) == 100


# ---------------------------------------------------------------------------
# CreateValidationRunRequest — invalid payloads
# ---------------------------------------------------------------------------


class TestCreateValidationRunRequestInvalid:
    """Test CreateValidationRunRequest with invalid payloads."""

    def test_missing_migration_id_raises(self):
        """Missing migration_id raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            CreateValidationRunRequest(**INVALID_CREATE_VALIDATION_RUN_MISSING_MIGRATION)
        assert "migration_id" in str(exc_info.value)

    def test_missing_source_connection_accepted(self):
        """Missing source_connection_id is accepted (auto-filled from migration)."""
        payload = {"migration_id": 10, "target_connection_id": 200}
        req = CreateValidationRunRequest(**payload)
        assert req.source_connection_id is None

    def test_missing_target_connection_accepted(self):
        """Missing target_connection_id is accepted (auto-filled from migration)."""
        payload = {"migration_id": 10, "source_connection_id": 100}
        req = CreateValidationRunRequest(**payload)
        assert req.target_connection_id is None

    def test_wrong_type_migration_id_raises(self):
        """Non-integer migration_id raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            CreateValidationRunRequest(**INVALID_CREATE_VALIDATION_RUN_WRONG_TYPES)
        assert "migration_id" in str(exc_info.value)

    def test_wrong_type_tables_raises(self):
        """Non-list tables value raises ValidationError."""
        payload = {**VALID_CREATE_VALIDATION_RUN_MINIMAL, "tables": "not_a_list"}
        with pytest.raises(ValidationError) as exc_info:
            CreateValidationRunRequest(**payload)
        assert "tables" in str(exc_info.value)

    def test_wrong_type_batch_size_raises(self):
        """Non-integer batch_size raises ValidationError."""
        payload = {**VALID_CREATE_VALIDATION_RUN_MINIMAL, "batch_size": "big"}
        with pytest.raises(ValidationError) as exc_info:
            CreateValidationRunRequest(**payload)
        assert "batch_size" in str(exc_info.value)


# ---------------------------------------------------------------------------
# CreateValidationRunRequest — batch_size bounds
# ---------------------------------------------------------------------------


class TestCreateValidationRunBatchSizeBounds:
    """Test batch_size field validation bounds (ge=100, le=100000)."""

    def test_batch_size_at_lower_bound(self):
        """batch_size=100 (minimum) passes validation."""
        req = CreateValidationRunRequest(
            **{**VALID_CREATE_VALIDATION_RUN_MINIMAL, "batch_size": 100}
        )
        assert req.batch_size == 100

    def test_batch_size_below_lower_bound_raises(self):
        """batch_size=99 (below minimum) raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            CreateValidationRunRequest(
                **{**VALID_CREATE_VALIDATION_RUN_MINIMAL, "batch_size": 99}
            )
        assert "batch_size" in str(exc_info.value)

    def test_batch_size_at_upper_bound(self):
        """batch_size=100000 (maximum) passes validation."""
        req = CreateValidationRunRequest(
            **{**VALID_CREATE_VALIDATION_RUN_MINIMAL, "batch_size": 100000}
        )
        assert req.batch_size == 100000

    def test_batch_size_above_upper_bound_raises(self):
        """batch_size=100001 (above maximum) raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            CreateValidationRunRequest(
                **{**VALID_CREATE_VALIDATION_RUN_MINIMAL, "batch_size": 100001}
            )
        assert "batch_size" in str(exc_info.value)

    def test_batch_size_zero_raises(self):
        """batch_size=0 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            CreateValidationRunRequest(
                **{**VALID_CREATE_VALIDATION_RUN_MINIMAL, "batch_size": 0}
            )
        assert "batch_size" in str(exc_info.value)

    def test_batch_size_negative_raises(self):
        """Negative batch_size raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            CreateValidationRunRequest(
                **{**VALID_CREATE_VALIDATION_RUN_MINIMAL, "batch_size": -1}
            )
        assert "batch_size" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Response schema tests
# ---------------------------------------------------------------------------


class TestValidationRunResponse:
    """Test ValidationRunResponse Pydantic schema."""

    def test_valid_response(self):
        """Valid response payload passes."""
        now = datetime.now(timezone.utc)
        resp = ValidationRunResponse(
            id=1,
            workspace_id=1,
            migration_id=10,
            source_connection_id=100,
            target_connection_id=200,
            status="completed",
            progress_percentage=100,
            tables_total=3,
            tables_passed=2,
            tables_failed=1,
            tables_error=0,
            created_by="testuser",
            created_at=now,
            updated_at=now,
        )
        assert resp.id == 1
        assert resp.started_at is None
        assert resp.duration_seconds is None

    def test_missing_required_field_raises(self):
        """Missing required field raises ValidationError."""
        with pytest.raises(ValidationError):
            ValidationRunResponse(id=1)


class TestValidationTableResultResponse:
    """Test ValidationTableResultResponse Pydantic schema."""

    def test_valid_response(self):
        """Valid table result response passes."""
        resp = ValidationTableResultResponse(
            id=1,
            run_id=1,
            table_name="users",
            status="completed",
        )
        assert resp.table_name == "users"
        assert resp.ddl_status is None
        assert resp.dataset_name is None

    def test_missing_required_field_raises(self):
        """Missing required field raises ValidationError."""
        with pytest.raises(ValidationError):
            ValidationTableResultResponse(id=1)


class TestValidationTableDetailResponse:
    """Test ValidationTableDetailResponse inherits and adds JSONB fields."""

    def test_valid_detail_response(self):
        """Detail response with JSONB fields passes."""
        resp = ValidationTableDetailResponse(
            id=1,
            run_id=1,
            table_name="orders",
            status="failed",
            ddl_comparison_result={"discrepancies": [], "source_column_count": 5},
            row_count_result={"source_count": 1000, "target_count": 999},
            data_match_result={"total_compared": 1000, "matched_count": 998},
            ai_analysis={"root_cause": "Precision loss"},
        )
        assert resp.ddl_comparison_result["source_column_count"] == 5
        assert resp.ai_analysis["root_cause"] == "Precision loss"

    def test_jsonb_fields_default_to_none(self):
        """JSONB detail fields default to None."""
        resp = ValidationTableDetailResponse(
            id=1, run_id=1, table_name="t", status="pending"
        )
        assert resp.ddl_comparison_result is None
        assert resp.row_count_result is None
        assert resp.data_match_result is None
        assert resp.ai_analysis is None


class TestValidationReportResponse:
    """Test ValidationReportResponse Pydantic schema."""

    def test_valid_report(self):
        """Valid report with table details passes."""
        table = ValidationTableDetailResponse(
            id=1, run_id=1, table_name="users", status="completed"
        )
        report = ValidationReportResponse(
            run_id=1,
            migration_id=10,
            source_connection_name="BigQuery Prod",
            target_connection_name="Redshift Prod",
            overall_status="completed",
            total_tables=1,
            tables_passed=1,
            tables_failed=0,
            tables_error=0,
            tables=[table],
        )
        assert report.total_tables == 1
        assert len(report.tables) == 1

    def test_empty_tables_list(self):
        """Report with empty tables list passes."""
        report = ValidationReportResponse(
            run_id=1,
            migration_id=10,
            source_connection_name="src",
            target_connection_name="tgt",
            overall_status="completed",
            total_tables=0,
            tables_passed=0,
            tables_failed=0,
            tables_error=0,
            tables=[],
        )
        assert report.tables == []

    def test_missing_required_field_raises(self):
        """Missing required field raises ValidationError."""
        with pytest.raises(ValidationError):
            ValidationReportResponse(run_id=1)


class TestPaginatedValidationRunsResponse:
    """Test PaginatedValidationRunsResponse Pydantic schema."""

    def test_empty_page(self):
        """Empty runs list with pagination metadata passes."""
        resp = PaginatedValidationRunsResponse(
            runs=[], total=0, page=1, page_size=20
        )
        assert resp.runs == []
        assert resp.total == 0

    def test_with_runs(self):
        """Paginated response with run entries passes."""
        now = datetime.now(timezone.utc)
        run = ValidationRunResponse(
            id=1,
            workspace_id=1,
            migration_id=10,
            source_connection_id=100,
            target_connection_id=200,
            status="pending",
            progress_percentage=0,
            tables_total=0,
            tables_passed=0,
            tables_failed=0,
            tables_error=0,
            created_by="testuser",
            created_at=now,
            updated_at=now,
        )
        resp = PaginatedValidationRunsResponse(
            runs=[run], total=1, page=1, page_size=20
        )
        assert len(resp.runs) == 1
        assert resp.total == 1


# ---------------------------------------------------------------------------
# Imports for run_name tests
# ---------------------------------------------------------------------------
from tests.fixtures.sample_payloads import (
    VALID_CREATE_VALIDATION_RUN_WITH_RUN_NAME,
    VALID_CREATE_VALIDATION_RUN_RUN_NAME_MAX_LENGTH,
    VALID_CREATE_VALIDATION_RUN_RUN_NAME_NONE,
    INVALID_CREATE_VALIDATION_RUN_RUN_NAME_TOO_LONG,
)


# ---------------------------------------------------------------------------
# CreateValidationRunRequest — run_name validation
# Requirements: 1.1, 1.2
# ---------------------------------------------------------------------------


class TestCreateValidationRunRequestRunName:
    """Test CreateValidationRunRequest run_name field validation."""

    def test_valid_run_name(self):
        """run_name with a short descriptive string passes validation."""
        # Arrange
        payload = VALID_CREATE_VALIDATION_RUN_WITH_RUN_NAME

        # Act
        req = CreateValidationRunRequest(**payload)

        # Assert
        assert req.run_name == "Pre-release check"

    def test_run_name_at_max_length(self):
        """run_name at exactly 255 characters passes validation."""
        # Arrange
        payload = VALID_CREATE_VALIDATION_RUN_RUN_NAME_MAX_LENGTH

        # Act
        req = CreateValidationRunRequest(**payload)

        # Assert
        assert req.run_name == "A" * 255
        assert len(req.run_name) == 255

    def test_run_name_single_char(self):
        """run_name with a single character passes validation."""
        # Arrange
        payload = {**VALID_CREATE_VALIDATION_RUN_WITH_RUN_NAME, "run_name": "X"}

        # Act
        req = CreateValidationRunRequest(**payload)

        # Assert
        assert req.run_name == "X"

    def test_run_name_none_explicit(self):
        """Explicitly passing run_name=None passes validation."""
        # Arrange
        payload = VALID_CREATE_VALIDATION_RUN_RUN_NAME_NONE

        # Act
        req = CreateValidationRunRequest(**payload)

        # Assert
        assert req.run_name is None

    def test_run_name_omitted(self):
        """Omitting run_name entirely defaults to None."""
        # Arrange
        payload = VALID_CREATE_VALIDATION_RUN_MINIMAL

        # Act
        req = CreateValidationRunRequest(**payload)

        # Assert
        assert req.run_name is None

    def test_run_name_exceeds_max_length_raises(self):
        """run_name exceeding 255 characters raises ValidationError."""
        # Arrange
        payload = INVALID_CREATE_VALIDATION_RUN_RUN_NAME_TOO_LONG

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            CreateValidationRunRequest(**payload)
        assert "run_name" in str(exc_info.value)

    def test_run_name_empty_string(self):
        """run_name as empty string passes validation (optional field)."""
        # Arrange
        payload = {**VALID_CREATE_VALIDATION_RUN_WITH_RUN_NAME, "run_name": ""}

        # Act
        req = CreateValidationRunRequest(**payload)

        # Assert
        assert req.run_name == ""


# ---------------------------------------------------------------------------
# ValidationRunResponse — run_name and table_results serialization
# Requirements: 1.2, 6.4
# ---------------------------------------------------------------------------


class TestValidationRunResponseRunNameAndTableResults:
    """Test ValidationRunResponse serializes run_name and table_results correctly."""

    def _build_run_response(self, **overrides):
        """Helper to build a valid ValidationRunResponse with sensible defaults."""
        now = datetime.now(timezone.utc)
        defaults = dict(
            id=1,
            workspace_id=1,
            migration_id=10,
            source_connection_id=100,
            target_connection_id=200,
            status="completed",
            progress_percentage=100,
            tables_total=2,
            tables_passed=2,
            tables_failed=0,
            tables_error=0,
            created_by="testuser",
            created_at=now,
            updated_at=now,
        )
        defaults.update(overrides)
        return ValidationRunResponse(**defaults)

    def test_run_name_present(self):
        """ValidationRunResponse includes run_name when provided."""
        # Arrange & Act
        resp = self._build_run_response(run_name="Nightly validation")

        # Assert
        assert resp.run_name == "Nightly validation"

    def test_run_name_defaults_to_none(self):
        """ValidationRunResponse defaults run_name to None when omitted."""
        # Arrange & Act
        resp = self._build_run_response()

        # Assert
        assert resp.run_name is None

    def test_table_results_present(self):
        """ValidationRunResponse includes table_results when provided."""
        # Arrange
        table_results = [
            ValidationTableResultResponse(
                id=1,
                run_id=1,
                table_name="users",
                status="completed",
                ddl_status="passed",
                row_count_status="passed",
                data_match_status="passed",
            ),
            ValidationTableResultResponse(
                id=2,
                run_id=1,
                table_name="orders",
                status="failed",
                ddl_status="passed",
                row_count_status="failed",
                data_match_status="error",
            ),
        ]

        # Act
        resp = self._build_run_response(table_results=table_results)

        # Assert
        assert resp.table_results is not None
        assert len(resp.table_results) == 2
        assert resp.table_results[0].table_name == "users"
        assert resp.table_results[0].ddl_status == "passed"
        assert resp.table_results[1].table_name == "orders"
        assert resp.table_results[1].data_match_status == "error"

    def test_table_results_defaults_to_none(self):
        """ValidationRunResponse defaults table_results to None when omitted."""
        # Arrange & Act
        resp = self._build_run_response()

        # Assert
        assert resp.table_results is None

    def test_table_results_empty_list(self):
        """ValidationRunResponse accepts empty table_results list."""
        # Arrange & Act
        resp = self._build_run_response(table_results=[])

        # Assert
        assert resp.table_results == []

    def test_run_name_and_table_results_together(self):
        """ValidationRunResponse serializes both run_name and table_results."""
        # Arrange
        table_results = [
            ValidationTableResultResponse(
                id=1,
                run_id=1,
                table_name="products",
                status="completed",
                ddl_status="passed",
                row_count_status="passed",
                data_match_status="passed",
            ),
        ]

        # Act
        resp = self._build_run_response(
            run_name="Pre-release check",
            table_results=table_results,
        )

        # Assert
        assert resp.run_name == "Pre-release check"
        assert len(resp.table_results) == 1
        assert resp.table_results[0].table_name == "products"

    def test_model_dump_includes_run_name_and_table_results(self):
        """model_dump() output includes run_name and table_results keys."""
        # Arrange
        table_results = [
            ValidationTableResultResponse(
                id=1,
                run_id=1,
                table_name="users",
                status="completed",
            ),
        ]

        # Act
        resp = self._build_run_response(
            run_name="Smoke test",
            table_results=table_results,
        )
        data = resp.model_dump()

        # Assert
        assert "run_name" in data
        assert data["run_name"] == "Smoke test"
        assert "table_results" in data
        assert len(data["table_results"]) == 1
        assert data["table_results"][0]["table_name"] == "users"
