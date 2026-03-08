"""
Unit tests for ConversionLog model, ConversionLogResponse schema,
updated AssetType enum (QUERY), BulkDeleteRequest schema,
additional_context validation, and dialect constants.

Requirements: 5.3, 5.4, 8.5, 9.7
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from models.conversion_log import ConversionLog, ConversionLogStepName
from models.conversion_schemas import (
    AssetType,
    StandaloneConversionRequest,
    ConversionLogResponse,
    BulkDeleteRequest,
    ALLOWED_SOURCE_DIALECTS,
    ALLOWED_TARGET_DIALECTS,
)
from tests.fixtures.sample_payloads import (
    VALID_CONVERSION_LOG_ENTRY,
    VALID_STANDALONE_WITH_CONTEXT,
    VALID_STANDALONE_CONVERSION,
    BULK_DELETE_PAYLOAD,
    CONTEXT_AT_BOUNDARY,
    CONTEXT_EXCEEDS_LIMIT,
)


# ---------------------------------------------------------------------------
# ConversionLog model tests
# ---------------------------------------------------------------------------

class TestConversionLogModel:
    """Test ConversionLog SQLAlchemy model instantiation."""

    def test_create_log_with_valid_fields(self):
        """ConversionLog can be instantiated with all required fields."""
        log = ConversionLog(**VALID_CONVERSION_LOG_ENTRY)

        assert log.job_id == 1
        assert log.workspace_id == 1
        assert log.log_level == "INFO"
        assert log.step_name == "template_loaded"
        assert log.message == "Prompt template loaded from S3"
        assert log.duration_ms == 120

    def test_nullable_duration_ms(self):
        """duration_ms can be None for steps without timing."""
        data = {**VALID_CONVERSION_LOG_ENTRY, "duration_ms": None}
        log = ConversionLog(**data)

        assert log.duration_ms is None

    def test_repr_contains_key_info(self):
        """__repr__ includes id, job_id, step_name, and log_level."""
        log = ConversionLog(**VALID_CONVERSION_LOG_ENTRY)
        r = repr(log)

        assert "ConversionLog" in r
        assert "job_id=1" in r
        assert "template_loaded" in r
        assert "INFO" in r

    def test_error_log_level(self):
        """ConversionLog accepts ERROR log level."""
        data = {
            **VALID_CONVERSION_LOG_ENTRY,
            "log_level": "ERROR",
            "step_name": "conversion_failed",
            "message": "Bedrock invocation timed out",
        }
        log = ConversionLog(**data)

        assert log.log_level == "ERROR"
        assert log.step_name == "conversion_failed"


# ---------------------------------------------------------------------------
# ConversionLogStepName enum tests
# ---------------------------------------------------------------------------

class TestConversionLogStepName:
    """Test ConversionLogStepName enum values."""

    def test_all_expected_steps_exist(self):
        """All required step names are defined in the enum."""
        expected = [
            "template_loaded",
            "sqlglot_parse_started",
            "sqlglot_parse_completed",
            "sqlglot_parse_failed",
            "bedrock_invocation_started",
            "bedrock_invocation_completed",
            "bedrock_invocation_failed",
            "retry_attempted",
            "conversion_completed",
            "conversion_failed",
        ]
        for step in expected:
            assert ConversionLogStepName(step) == step

    def test_invalid_step_raises(self):
        """Invalid step name string is rejected."""
        with pytest.raises(ValueError):
            ConversionLogStepName("unknown_step")

    def test_step_name_is_str_enum(self):
        """ConversionLogStepName members are usable as plain strings."""
        assert ConversionLogStepName.TEMPLATE_LOADED == "template_loaded"
        assert isinstance(ConversionLogStepName.BEDROCK_INVOCATION_STARTED, str)


# ---------------------------------------------------------------------------
# ConversionLogResponse schema tests
# ---------------------------------------------------------------------------

class TestConversionLogResponse:
    """Test ConversionLogResponse Pydantic schema."""

    def test_valid_serialization(self):
        """ConversionLogResponse accepts valid data and serializes correctly."""
        now = datetime.now(timezone.utc)
        resp = ConversionLogResponse(
            id=1,
            job_id=10,
            timestamp=now,
            log_level="INFO",
            step_name="template_loaded",
            message="Template loaded successfully",
            duration_ms=50,
        )

        assert resp.id == 1
        assert resp.job_id == 10
        assert resp.log_level == "INFO"
        assert resp.duration_ms == 50

    def test_nullable_duration_ms(self):
        """duration_ms can be None in the response."""
        now = datetime.now(timezone.utc)
        resp = ConversionLogResponse(
            id=2,
            job_id=10,
            timestamp=now,
            log_level="WARNING",
            step_name="retry_attempted",
            message="Retrying after transient failure",
            duration_ms=None,
        )

        assert resp.duration_ms is None

    def test_from_attributes_config(self):
        """model_config enables from_attributes for ORM compatibility."""
        assert ConversionLogResponse.model_config.get("from_attributes") is True

    def test_missing_required_field_raises(self):
        """Missing required field raises ValidationError."""
        with pytest.raises(ValidationError):
            ConversionLogResponse(id=1)


# ---------------------------------------------------------------------------
# additional_context validation tests
# ---------------------------------------------------------------------------

class TestAdditionalContextValidation:
    """Test additional_context field on StandaloneConversionRequest."""

    def test_valid_context_accepted(self):
        """Request with valid additional_context passes validation."""
        req = StandaloneConversionRequest(**VALID_STANDALONE_WITH_CONTEXT)

        assert req.additional_context == "Schema: users(id INT, name VARCHAR(255))"

    def test_none_context_accepted(self):
        """Request without additional_context defaults to None."""
        req = StandaloneConversionRequest(**VALID_STANDALONE_CONVERSION)

        assert req.additional_context is None

    def test_boundary_context_50000_chars_accepted(self):
        """additional_context at exactly 50,000 characters is accepted."""
        payload = {**VALID_STANDALONE_WITH_CONTEXT, "additional_context": CONTEXT_AT_BOUNDARY}
        req = StandaloneConversionRequest(**payload)

        assert len(req.additional_context) == 50000

    def test_context_exceeding_50000_chars_rejected(self):
        """additional_context exceeding 50,000 characters raises ValidationError."""
        payload = {**VALID_STANDALONE_WITH_CONTEXT, "additional_context": CONTEXT_EXCEEDS_LIMIT}
        with pytest.raises(ValidationError) as exc_info:
            StandaloneConversionRequest(**payload)

        assert "50,000" in str(exc_info.value)

    def test_empty_string_context_accepted(self):
        """Empty string additional_context is accepted (not None)."""
        payload = {**VALID_STANDALONE_WITH_CONTEXT, "additional_context": ""}
        req = StandaloneConversionRequest(**payload)

        assert req.additional_context == ""


# ---------------------------------------------------------------------------
# AssetType QUERY enum tests
# ---------------------------------------------------------------------------

class TestAssetTypeQuery:
    """Test QUERY and SCHEDULED_QUERY both accepted in AssetType enum."""

    def test_query_accepted(self):
        """QUERY is a valid AssetType value."""
        assert AssetType("QUERY") == AssetType.QUERY

    def test_scheduled_query_still_accepted(self):
        """SCHEDULED_QUERY remains valid for backward compatibility."""
        assert AssetType("SCHEDULED_QUERY") == AssetType.SCHEDULED_QUERY

    def test_query_in_standalone_request(self):
        """StandaloneConversionRequest accepts QUERY asset_type."""
        req = StandaloneConversionRequest(**VALID_STANDALONE_WITH_CONTEXT)

        assert req.asset_type == AssetType.QUERY

    def test_scheduled_query_in_standalone_request(self):
        """StandaloneConversionRequest accepts SCHEDULED_QUERY asset_type."""
        payload = {**VALID_STANDALONE_WITH_CONTEXT, "asset_type": "SCHEDULED_QUERY"}
        req = StandaloneConversionRequest(**payload)

        assert req.asset_type == AssetType.SCHEDULED_QUERY


# ---------------------------------------------------------------------------
# BulkDeleteRequest schema tests
# ---------------------------------------------------------------------------

class TestBulkDeleteRequest:
    """Test BulkDeleteRequest Pydantic schema."""

    def test_valid_job_ids(self):
        """BulkDeleteRequest with valid job_ids passes."""
        req = BulkDeleteRequest(**BULK_DELETE_PAYLOAD)

        assert req.job_ids == [1, 2, 3]

    def test_empty_job_ids_accepted(self):
        """BulkDeleteRequest with empty list is accepted."""
        req = BulkDeleteRequest(job_ids=[])

        assert req.job_ids == []

    def test_single_job_id(self):
        """BulkDeleteRequest with a single job ID passes."""
        req = BulkDeleteRequest(job_ids=[42])

        assert req.job_ids == [42]

    def test_missing_job_ids_raises(self):
        """Missing job_ids field raises ValidationError."""
        with pytest.raises(ValidationError):
            BulkDeleteRequest()


# ---------------------------------------------------------------------------
# Dialect validation constants tests
# ---------------------------------------------------------------------------

class TestDialectConstants:
    """Test ALLOWED_SOURCE_DIALECTS and ALLOWED_TARGET_DIALECTS constants."""

    def test_source_dialects_correct_values(self):
        """ALLOWED_SOURCE_DIALECTS contains exactly the expected values."""
        assert ALLOWED_SOURCE_DIALECTS == {"Bigquery", "SQL Server", "Redshift"}

    def test_target_dialects_correct_values(self):
        """ALLOWED_TARGET_DIALECTS contains exactly the expected values."""
        assert ALLOWED_TARGET_DIALECTS == {"Redshift", "SQL Server", "BigQuery"}

    def test_source_dialects_is_set(self):
        """ALLOWED_SOURCE_DIALECTS is a set for O(1) lookup."""
        assert isinstance(ALLOWED_SOURCE_DIALECTS, set)

    def test_target_dialects_is_set(self):
        """ALLOWED_TARGET_DIALECTS is a set for O(1) lookup."""
        assert isinstance(ALLOWED_TARGET_DIALECTS, set)

    def test_source_has_three_entries(self):
        """Source dialects set has exactly 3 entries."""
        assert len(ALLOWED_SOURCE_DIALECTS) == 3

    def test_target_has_three_entries(self):
        """Target dialects set has exactly 3 entries."""
        assert len(ALLOWED_TARGET_DIALECTS) == 3
