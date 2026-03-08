"""
Unit tests for Code Conversion data models and Pydantic schemas.

Tests ConversionJob and ConversionBatch SQLAlchemy model creation,
Pydantic schema validation (valid, invalid, edge cases), and
asset_type / status enum validation.

Requirements: 5.1, 5.2
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from models.conversion_job import ConversionJob
from models.conversion_batch import ConversionBatch
from models.conversion_schemas import (
    AssetType,
    JobStatus,
    BatchStatus,
    StandaloneConversionRequest,
    BatchConversionRequest,
    AssetSelection,
    S3ExportRequest,
    DeployRequest,
    ConversionJobResponse,
    ConversionBatchResponse,
    PaginatedJobsResponse,
    BedrockModelResponse,
)
from tests.fixtures.sample_payloads import (
    VALID_STANDALONE_CONVERSION,
    VALID_STANDALONE_CONVERSION_MINIMAL,
    VALID_STANDALONE_CONVERSION_SQLGLOT,
    VALID_BATCH_CONVERSION,
    VALID_S3_EXPORT,
    VALID_DEPLOY_REQUEST,
    VALID_CONVERSION_JOB_DATA,
    VALID_CONVERSION_JOB_COMPLETED,
    VALID_CONVERSION_BATCH_DATA,
    VALID_ASSET_TYPES,
    INVALID_ASSET_TYPES,
    VALID_JOB_STATUSES,
    VALID_BATCH_STATUSES,
)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------

class TestAssetTypeEnum:
    """Test AssetType enum values and validation."""

    def test_all_valid_asset_types_exist(self):
        """All expected asset types are defined in the enum."""
        for at in VALID_ASSET_TYPES:
            assert AssetType(at) == at

    def test_invalid_asset_type_raises(self):
        """Invalid strings are rejected by the enum."""
        for bad in INVALID_ASSET_TYPES:
            with pytest.raises(ValueError):
                AssetType(bad)

    def test_asset_type_is_str_enum(self):
        """AssetType members are usable as plain strings."""
        assert AssetType.TABLE_DDL == "TABLE_DDL"
        assert isinstance(AssetType.VIEW, str)


class TestJobStatusEnum:
    """Test JobStatus enum values."""

    def test_all_valid_job_statuses(self):
        """All expected job statuses are defined."""
        for s in VALID_JOB_STATUSES:
            assert JobStatus(s) == s

    def test_invalid_job_status_raises(self):
        """Invalid status strings are rejected."""
        for bad in ["unknown", "PENDING", "cancelled", ""]:
            with pytest.raises(ValueError):
                JobStatus(bad)


class TestBatchStatusEnum:
    """Test BatchStatus enum values."""

    def test_all_valid_batch_statuses(self):
        """All expected batch statuses are defined."""
        for s in VALID_BATCH_STATUSES:
            assert BatchStatus(s) == s

    def test_completed_with_errors_status(self):
        """The completed_with_errors status is available for batches but not jobs."""
        assert BatchStatus("completed_with_errors") == BatchStatus.COMPLETED_WITH_ERRORS
        with pytest.raises(ValueError):
            JobStatus("completed_with_errors")


# ---------------------------------------------------------------------------
# SQLAlchemy model instantiation tests (no DB required)
# ---------------------------------------------------------------------------

class TestConversionJobModel:
    """Test ConversionJob SQLAlchemy model creation with valid data."""

    def test_create_job_with_valid_data(self):
        """ConversionJob can be instantiated with all required fields."""
        job = ConversionJob(**VALID_CONVERSION_JOB_DATA)

        assert job.workspace_id == 1
        assert job.source_code == VALID_CONVERSION_JOB_DATA["source_code"]
        assert job.source_dialect == "Bigquery"
        assert job.target_dialect == "Redshift"
        assert job.asset_type == "TABLE_DDL"
        assert job.bedrock_model == VALID_CONVERSION_JOB_DATA["bedrock_model"]
        assert job.aws_region == "us-east-1"
        assert job.status == "pending"
        assert job.use_sqlglot is False
        assert job.retry_count == 0
        assert job.created_by == "testuser"

    def test_create_completed_job(self):
        """ConversionJob with target_code and completed status."""
        job = ConversionJob(**VALID_CONVERSION_JOB_COMPLETED)

        assert job.target_code is not None
        assert job.status == "completed"
        assert job.sqlglot_success is True

    def test_nullable_fields_default_to_none(self):
        """Optional fields default to None when not provided."""
        job = ConversionJob(**VALID_CONVERSION_JOB_DATA)

        assert job.batch_id is None
        assert job.target_code is None
        assert job.sqlglot_success is None
        assert job.error_message is None

    def test_to_dict_returns_all_keys(self):
        """to_dict() includes every expected key."""
        job = ConversionJob(**VALID_CONVERSION_JOB_DATA)
        d = job.to_dict()

        expected_keys = {
            "id", "workspace_id", "batch_id", "source_code", "target_code",
            "source_dialect", "target_dialect", "asset_type", "asset_name",
            "bedrock_model", "aws_region", "prompt_template_path",
            "use_sqlglot", "sqlglot_success", "status", "error_message",
            "retry_count", "created_by", "created_at", "updated_at",
        }
        assert set(d.keys()) == expected_keys

    def test_repr_contains_key_info(self):
        """__repr__ includes id, workspace_id, status, and asset_type."""
        job = ConversionJob(**VALID_CONVERSION_JOB_DATA)
        r = repr(job)

        assert "ConversionJob" in r
        assert "workspace_id=1" in r
        assert "pending" in r
        assert "TABLE_DDL" in r


class TestConversionBatchModel:
    """Test ConversionBatch SQLAlchemy model creation with valid data."""

    def test_create_batch_with_valid_data(self):
        """ConversionBatch can be instantiated with all required fields."""
        batch = ConversionBatch(**VALID_CONVERSION_BATCH_DATA)

        assert batch.workspace_id == 1
        assert batch.migration_project_id == 1
        assert batch.source_connection_id == 10
        assert batch.target_connection_id == 20
        assert batch.bedrock_model == VALID_CONVERSION_BATCH_DATA["bedrock_model"]
        assert batch.status == "pending"
        assert batch.total_assets == 5
        assert batch.completed_assets == 0
        assert batch.failed_assets == 0
        assert batch.max_retries == 3
        assert batch.use_sqlglot is False
        assert batch.created_by == "testuser"

    def test_to_dict_returns_all_keys(self):
        """to_dict() includes every expected key."""
        batch = ConversionBatch(**VALID_CONVERSION_BATCH_DATA)
        d = batch.to_dict()

        expected_keys = {
            "id", "workspace_id", "migration_project_id",
            "source_connection_id", "target_connection_id",
            "bedrock_model", "aws_region", "prompt_template_path",
            "use_sqlglot", "max_retries", "status",
            "total_assets", "completed_assets", "failed_assets",
            "created_by", "created_at", "updated_at",
        }
        assert set(d.keys()) == expected_keys

    def test_repr_contains_key_info(self):
        """__repr__ includes id, workspace_id, status, and total."""
        batch = ConversionBatch(**VALID_CONVERSION_BATCH_DATA)
        r = repr(batch)

        assert "ConversionBatch" in r
        assert "workspace_id=1" in r
        assert "pending" in r
        assert "total=5" in r


# ---------------------------------------------------------------------------
# Pydantic schema tests — StandaloneConversionRequest
# ---------------------------------------------------------------------------

class TestStandaloneConversionRequest:
    """Test Pydantic validation for StandaloneConversionRequest."""

    def test_valid_full_payload(self):
        """Full payload with all fields passes validation."""
        req = StandaloneConversionRequest(**VALID_STANDALONE_CONVERSION)

        assert req.source_code == VALID_STANDALONE_CONVERSION["source_code"]
        assert req.asset_type == AssetType.TABLE_DDL
        assert req.max_retries == 3
        assert req.use_sqlglot is False

    def test_valid_minimal_payload(self):
        """Minimal payload (defaults applied) passes validation."""
        req = StandaloneConversionRequest(**VALID_STANDALONE_CONVERSION_MINIMAL)

        assert req.max_retries == 3  # default
        assert req.use_sqlglot is False  # default
        assert req.asset_name is None  # optional

    def test_sqlglot_enabled(self):
        """Payload with use_sqlglot=True passes validation."""
        req = StandaloneConversionRequest(**VALID_STANDALONE_CONVERSION_SQLGLOT)
        assert req.use_sqlglot is True

    def test_missing_source_code_raises(self):
        """Missing source_code field raises ValidationError."""
        payload = {**VALID_STANDALONE_CONVERSION}
        del payload["source_code"]
        with pytest.raises(ValidationError) as exc_info:
            StandaloneConversionRequest(**payload)
        assert "source_code" in str(exc_info.value)

    def test_missing_asset_type_raises(self):
        """Missing asset_type field raises ValidationError."""
        payload = {**VALID_STANDALONE_CONVERSION}
        del payload["asset_type"]
        with pytest.raises(ValidationError) as exc_info:
            StandaloneConversionRequest(**payload)
        assert "asset_type" in str(exc_info.value)

    def test_missing_bedrock_model_raises(self):
        """Missing bedrock_model field raises ValidationError."""
        payload = {**VALID_STANDALONE_CONVERSION}
        del payload["bedrock_model"]
        with pytest.raises(ValidationError) as exc_info:
            StandaloneConversionRequest(**payload)
        assert "bedrock_model" in str(exc_info.value)

    def test_empty_source_code_raises(self):
        """Empty string source_code violates min_length=1."""
        payload = {**VALID_STANDALONE_CONVERSION, "source_code": ""}
        with pytest.raises(ValidationError) as exc_info:
            StandaloneConversionRequest(**payload)
        assert "source_code" in str(exc_info.value)

    def test_empty_source_dialect_raises(self):
        """Empty string source_dialect violates min_length=1."""
        payload = {**VALID_STANDALONE_CONVERSION, "source_dialect": ""}
        with pytest.raises(ValidationError) as exc_info:
            StandaloneConversionRequest(**payload)
        assert "source_dialect" in str(exc_info.value)

    def test_invalid_asset_type_raises(self):
        """Invalid asset_type string raises ValidationError."""
        payload = {**VALID_STANDALONE_CONVERSION, "asset_type": "INVALID_TYPE"}
        with pytest.raises(ValidationError) as exc_info:
            StandaloneConversionRequest(**payload)
        assert "asset_type" in str(exc_info.value)

    def test_wrong_type_source_code_raises(self):
        """Non-string source_code raises ValidationError."""
        payload = {**VALID_STANDALONE_CONVERSION, "source_code": 12345}
        with pytest.raises(ValidationError) as exc_info:
            StandaloneConversionRequest(**payload)
        assert "source_code" in str(exc_info.value)

    def test_max_retries_negative_raises(self):
        """Negative max_retries violates ge=0."""
        payload = {**VALID_STANDALONE_CONVERSION, "max_retries": -1}
        with pytest.raises(ValidationError) as exc_info:
            StandaloneConversionRequest(**payload)
        assert "max_retries" in str(exc_info.value)

    def test_max_retries_exceeds_limit_raises(self):
        """max_retries > 10 violates le=10."""
        payload = {**VALID_STANDALONE_CONVERSION, "max_retries": 11}
        with pytest.raises(ValidationError) as exc_info:
            StandaloneConversionRequest(**payload)
        assert "max_retries" in str(exc_info.value)

    def test_very_long_source_code_accepted(self):
        """Very long source_code string is accepted (no max_length on source_code)."""
        long_code = "SELECT " + ", ".join([f"col_{i}" for i in range(5000)]) + " FROM big_table"
        payload = {**VALID_STANDALONE_CONVERSION, "source_code": long_code}
        req = StandaloneConversionRequest(**payload)
        assert len(req.source_code) > 10000

    def test_all_asset_types_accepted(self):
        """Every valid AssetType value is accepted."""
        for at in VALID_ASSET_TYPES:
            payload = {**VALID_STANDALONE_CONVERSION, "asset_type": at}
            req = StandaloneConversionRequest(**payload)
            assert req.asset_type == AssetType(at)


# ---------------------------------------------------------------------------
# Pydantic schema tests — AssetSelection
# ---------------------------------------------------------------------------

class TestAssetSelection:
    """Test Pydantic validation for AssetSelection."""

    def test_valid_asset_selection(self):
        """Valid asset selection passes."""
        sel = AssetSelection(
            asset_type="TABLE_DDL",
            asset_name="users",
            source_code="CREATE TABLE users (id INT64)",
        )
        assert sel.asset_type == AssetType.TABLE_DDL
        assert sel.asset_name == "users"

    def test_empty_asset_name_raises(self):
        """Empty asset_name violates min_length=1."""
        with pytest.raises(ValidationError):
            AssetSelection(asset_type="VIEW", asset_name="", source_code="SELECT 1")

    def test_empty_source_code_raises(self):
        """Empty source_code violates min_length=1."""
        with pytest.raises(ValidationError):
            AssetSelection(asset_type="VIEW", asset_name="v1", source_code="")

    def test_asset_name_max_length(self):
        """asset_name exceeding 255 chars raises ValidationError."""
        with pytest.raises(ValidationError):
            AssetSelection(
                asset_type="VIEW",
                asset_name="a" * 256,
                source_code="SELECT 1",
            )


# ---------------------------------------------------------------------------
# Pydantic schema tests — BatchConversionRequest
# ---------------------------------------------------------------------------

class TestBatchConversionRequest:
    """Test Pydantic validation for BatchConversionRequest."""

    def test_valid_batch_payload(self):
        """Full valid batch payload passes validation."""
        req = BatchConversionRequest(**VALID_BATCH_CONVERSION)

        assert req.migration_project_id == 1
        assert len(req.assets) == 2
        assert req.use_sqlglot is True
        assert req.max_retries == 5

    def test_empty_assets_list_raises(self):
        """Empty assets list violates min_length=1."""
        payload = {**VALID_BATCH_CONVERSION, "assets": []}
        with pytest.raises(ValidationError) as exc_info:
            BatchConversionRequest(**payload)
        assert "assets" in str(exc_info.value)

    def test_missing_source_connection_id_raises(self):
        """Missing source_connection_id raises ValidationError."""
        payload = {**VALID_BATCH_CONVERSION}
        del payload["source_connection_id"]
        with pytest.raises(ValidationError) as exc_info:
            BatchConversionRequest(**payload)
        assert "source_connection_id" in str(exc_info.value)

    def test_missing_target_connection_id_raises(self):
        """Missing target_connection_id raises ValidationError."""
        payload = {**VALID_BATCH_CONVERSION}
        del payload["target_connection_id"]
        with pytest.raises(ValidationError) as exc_info:
            BatchConversionRequest(**payload)
        assert "target_connection_id" in str(exc_info.value)

    def test_invalid_asset_in_list_raises(self):
        """Invalid asset entry inside assets list raises ValidationError."""
        payload = {
            **VALID_BATCH_CONVERSION,
            "assets": [{"asset_type": "INVALID", "asset_name": "x", "source_code": "y"}],
        }
        with pytest.raises(ValidationError):
            BatchConversionRequest(**payload)


# ---------------------------------------------------------------------------
# Pydantic schema tests — S3ExportRequest & DeployRequest
# ---------------------------------------------------------------------------

class TestS3ExportRequest:
    """Test Pydantic validation for S3ExportRequest."""

    def test_valid_payload(self):
        """Valid S3 export payload passes."""
        req = S3ExportRequest(**VALID_S3_EXPORT)
        assert req.s3_path.startswith("s3://")

    def test_empty_s3_path_raises(self):
        """Empty s3_path violates min_length=1."""
        with pytest.raises(ValidationError):
            S3ExportRequest(s3_path="", region="us-east-1")

    def test_empty_region_raises(self):
        """Empty region violates min_length=1."""
        with pytest.raises(ValidationError):
            S3ExportRequest(s3_path="s3://bucket/path", region="")


class TestDeployRequest:
    """Test Pydantic validation for DeployRequest."""

    def test_valid_payload(self):
        """Valid deploy payload passes."""
        req = DeployRequest(**VALID_DEPLOY_REQUEST)
        assert req.target_connection_id == 20

    def test_missing_target_connection_id_raises(self):
        """Missing target_connection_id raises ValidationError."""
        with pytest.raises(ValidationError):
            DeployRequest()


# ---------------------------------------------------------------------------
# Pydantic schema tests — Response schemas
# ---------------------------------------------------------------------------

class TestConversionJobResponse:
    """Test ConversionJobResponse schema."""

    def test_valid_response(self):
        """Valid response payload passes."""
        now = datetime.now(timezone.utc)
        resp = ConversionJobResponse(
            id=1,
            workspace_id=1,
            source_code="SELECT 1",
            source_dialect="bigquery",
            target_dialect="redshift",
            asset_type="TABLE_DDL",
            bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
            aws_region="us-east-1",
            status="completed",
            use_sqlglot=False,
            retry_count=0,
            created_by="testuser",
            created_at=now,
            updated_at=now,
        )
        assert resp.id == 1
        assert resp.batch_id is None
        assert resp.target_code is None

    def test_missing_required_field_raises(self):
        """Missing required field raises ValidationError."""
        with pytest.raises(ValidationError):
            ConversionJobResponse(id=1)


class TestConversionBatchResponse:
    """Test ConversionBatchResponse schema."""

    def test_valid_response(self):
        """Valid batch response payload passes."""
        now = datetime.now(timezone.utc)
        resp = ConversionBatchResponse(
            id=1,
            workspace_id=1,
            source_connection_id=10,
            target_connection_id=20,
            status="completed",
            total_assets=5,
            completed_assets=5,
            failed_assets=0,
            bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
            aws_region="us-east-1",
            use_sqlglot=False,
            max_retries=3,
            created_by="testuser",
            created_at=now,
            updated_at=now,
        )
        assert resp.total_assets == 5
        assert resp.migration_project_id is None


class TestPaginatedJobsResponse:
    """Test PaginatedJobsResponse schema."""

    def test_empty_page(self):
        """Empty jobs list with pagination metadata passes."""
        resp = PaginatedJobsResponse(jobs=[], total=0, page=1, page_size=20)
        assert resp.jobs == []
        assert resp.total == 0


class TestBedrockModelResponse:
    """Test BedrockModelResponse schema."""

    def test_valid_model_response(self):
        """Valid Bedrock model response passes."""
        resp = BedrockModelResponse(
            model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            model_name="Claude 3 Sonnet",
            provider="Anthropic",
        )
        assert resp.provider == "Anthropic"

    def test_provider_optional(self):
        """Provider field is optional."""
        resp = BedrockModelResponse(
            model_id="amazon.titan-text-express-v1",
            model_name="Titan Text Express",
        )
        assert resp.provider is None
