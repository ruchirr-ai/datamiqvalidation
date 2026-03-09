"""
Pydantic request/response schemas for the Code Conversion module.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class AssetType(str, Enum):
    """Supported database asset types for conversion."""
    QUERY = "QUERY"
    TABLE_DDL = "TABLE_DDL"
    STORED_PROCEDURE = "STORED_PROCEDURE"
    FUNCTION = "FUNCTION"
    VIEW = "VIEW"
    MATERIALIZED_VIEW = "MATERIALIZED_VIEW"
    SCHEDULED_QUERY = "SCHEDULED_QUERY"  # Kept for backward compatibility


class JobStatus(str, Enum):
    """Status values for individual conversion jobs."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class BatchStatus(str, Enum):
    """Status values for batch conversion operations."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class StandaloneConversionRequest(BaseModel):
    """Request body for POST /api/conversions/standalone."""
    source_code: str = Field(..., min_length=1, description="Source SQL or code to convert")
    source_dialect: str = Field(..., min_length=1, description="Source database dialect")
    target_dialect: str = Field(..., min_length=1, description="Target database dialect")
    asset_type: AssetType = Field(..., description="Type of database asset")
    asset_name: Optional[str] = Field(None, max_length=255, description="Optional asset name")
    aws_region: str = Field(..., min_length=1, description="AWS region for Bedrock")
    bedrock_model: str = Field(..., min_length=1, description="Bedrock model identifier")
    prompt_template_path: str = Field(..., min_length=1, description="S3 path to prompt template")
    max_retries: int = Field(3, ge=0, le=10, description="Max retry attempts on failure")
    use_sqlglot: bool = Field(False, description="Enable sqlglot pre-processing")
    additional_context: Optional[str] = Field(None, description="Additional context for prompt")

    @field_validator('additional_context')
    @classmethod
    def validate_additional_context_length(cls, v: Optional[str]) -> Optional[str]:
        """Validate additional_context does not exceed 50,000 characters."""
        if v is not None and len(v) > 50000:
            raise ValueError('additional_context exceeds maximum length of 50,000 characters')
        return v


class AssetSelection(BaseModel):
    """Single asset entry within a batch conversion request."""
    asset_type: AssetType
    asset_name: str = Field(..., min_length=1, max_length=255)
    source_code: str = Field(default="", description="Source SQL or code; may be empty for discovery-based assets")


class BatchConversionRequest(BaseModel):
    """Request body for POST /api/conversions/batch."""
    migration_project_id: int = Field(..., description="Migration project ID")
    source_connection_id: int = Field(..., description="Source connection ID")
    target_connection_id: int = Field(..., description="Target connection ID")
    batch_name: Optional[str] = Field(None, max_length=255, description="Optional human-readable batch name")
    assets: list[AssetSelection] = Field(..., min_length=1, description="Assets to convert")
    source_dialect: str = Field(..., min_length=1)
    target_dialect: str = Field(..., min_length=1)
    aws_region: str = Field(..., min_length=1)
    bedrock_model: str = Field(..., min_length=1)
    prompt_template_path: str = Field(..., min_length=1)
    max_retries: int = Field(3, ge=0, le=10)
    use_sqlglot: bool = Field(False)


class S3ExportRequest(BaseModel):
    """Request body for POST /api/conversions/batch/{batch_id}/export/s3."""
    s3_path: str = Field(..., min_length=1, description="Target S3 path for export")
    region: str = Field(..., min_length=1, description="AWS region for S3 bucket")


class DeployRequest(BaseModel):
    """Request body for POST /api/conversions/batch/{batch_id}/deploy."""
    target_connection_id: int = Field(..., description="Target connection to deploy to")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class ConversionJobResponse(BaseModel):
    """Response schema for a single conversion job."""
    id: int
    workspace_id: int
    batch_id: Optional[int] = None
    source_code: str
    target_code: Optional[str] = None
    source_dialect: str
    target_dialect: str
    asset_type: str
    asset_name: Optional[str] = None
    bedrock_model: str
    aws_region: str
    status: str
    error_message: Optional[str] = None
    use_sqlglot: bool
    sqlglot_success: Optional[bool] = None
    retry_count: int
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator('created_by', mode='before')
    @classmethod
    def coerce_created_by(cls, v):
        if v is not None:
            return str(v)
        return v


class ConversionBatchResponse(BaseModel):
    """Response schema for a batch conversion."""
    id: int
    workspace_id: int
    batch_name: Optional[str] = None
    migration_project_id: Optional[int] = None
    source_connection_id: int
    target_connection_id: int
    status: str
    total_assets: int
    completed_assets: int
    failed_assets: int
    bedrock_model: str
    aws_region: str
    use_sqlglot: bool
    max_retries: int
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator('created_by', mode='before')
    @classmethod
    def coerce_created_by(cls, v):
        if v is not None:
            return str(v)
        return v


class PaginatedJobsResponse(BaseModel):
    """Paginated list of conversion jobs."""
    jobs: list[ConversionJobResponse]
    total: int
    page: int
    page_size: int


class BedrockModelResponse(BaseModel):
    """Response schema for a single Bedrock model entry."""
    model_id: str
    model_name: str
    provider: Optional[str] = None


class ConversionLogResponse(BaseModel):
    """Response schema for a single conversion log entry."""
    id: int
    job_id: int
    timestamp: datetime
    log_level: str
    step_name: str
    message: str
    duration_ms: Optional[int] = None

    model_config = {"from_attributes": True}


class BulkDeleteRequest(BaseModel):
    """Request body for bulk deletion of conversion jobs."""
    job_ids: list[int]


# ---------------------------------------------------------------------------
# Dialect validation constants
# ---------------------------------------------------------------------------

ALLOWED_SOURCE_DIALECTS: set[str] = {"BigQuery", "Bigquery", "bigquery", "SQL Server", "sql server", "Redshift", "redshift"}
ALLOWED_TARGET_DIALECTS: set[str] = {"Redshift", "redshift", "SQL Server", "sql server", "BigQuery", "Bigquery", "bigquery"}
