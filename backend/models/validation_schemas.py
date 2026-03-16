"""
Pydantic request/response schemas for the Data Validation module.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ValidationRunStatus(str, Enum):
    """Status values for validation runs."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ValidationStepStatus(str, Enum):
    """Status values for individual validation steps (DDL, row count, data match)."""
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class SamplingMode(str, Enum):
    """Sampling mode for data match validation."""
    ALL = "all"
    RANDOM = "random"


class TableValidationConfig(BaseModel):
    """Per-table validation configuration."""
    table_name: str = Field(..., description="Name of the table to validate")
    ddl_check: bool = Field(default=True, description="Run DDL/schema comparison")
    row_count_check: bool = Field(default=True, description="Run row count comparison")
    data_match_check: bool = Field(default=True, description="Run record-level data matching")
    sampling_mode: Optional[SamplingMode] = Field(default=None, description="Per-table sampling mode override")
    sample_limit: Optional[int] = Field(default=None, ge=100, le=10000000, description="Per-table sample limit when sampling_mode is 'random'")
    batch_size: Optional[int] = Field(default=None, ge=0, le=10000000, description="Per-table batch size for record-level matching")


class CreateValidationRunRequest(BaseModel):
    """Request body for POST /api/validations."""
    migration_id: int = Field(..., description="Migration project ID to validate")
    source_connection_id: Optional[int] = Field(None, description="Source connection ID (auto-filled from migration if omitted)")
    target_connection_id: Optional[int] = Field(None, description="Target connection ID (auto-filled from migration if omitted)")
    tables: Optional[list[str]] = Field(None, description="Optional list of table names to validate; defaults to all migration tables")
    table_configs: Optional[list[TableValidationConfig]] = Field(None, description="Per-table validation type configuration")
    bedrock_model: Optional[str] = Field(None, description="Bedrock model identifier for AI analysis")
    batch_size: int = Field(default=10000, ge=100, le=100000, description="Batch size for record-level matching")
    sampling_mode: SamplingMode = Field(default=SamplingMode.ALL, description="Whether to validate all records or a random sample")
    sample_limit: Optional[int] = Field(None, ge=100, le=10000000, description="Number of records to sample when sampling_mode is 'random'")
    type_mapping_overrides: Optional[dict[str, str]] = Field(None, description="Optional overrides for BigQuery-to-Redshift type mappings")
    run_name: Optional[str] = Field(None, max_length=255, description="Optional display name for the run")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class ValidationRunResponse(BaseModel):
    """Response schema for a validation run."""
    id: int
    workspace_id: int
    migration_id: int
    source_connection_id: int
    target_connection_id: int
    status: str
    progress_percentage: int
    tables_total: int
    tables_passed: int
    tables_failed: int
    tables_error: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    created_by: str
    created_at: datetime
    updated_at: datetime
    run_name: Optional[str] = None
    table_results: Optional[list["ValidationTableResultResponse"]] = None

    model_config = {"from_attributes": True}


class ValidationTableResultResponse(BaseModel):
    """Response schema for a per-table validation result (summary view)."""
    id: int
    run_id: int
    table_name: str
    dataset_name: Optional[str] = None
    ddl_status: Optional[str] = None
    row_count_status: Optional[str] = None
    data_match_status: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None

    model_config = {"from_attributes": True}


class ValidationTableDetailResponse(ValidationTableResultResponse):
    """Response schema for a per-table validation result with full JSONB details."""
    ddl_comparison_result: Optional[dict] = None
    row_count_result: Optional[dict] = None
    data_match_result: Optional[dict] = None
    ai_analysis: Optional[dict] = None


class ValidationReportResponse(BaseModel):
    """Response schema for a full validation report."""
    run_id: int
    migration_id: int
    source_connection_name: str
    target_connection_name: str
    overall_status: str
    total_tables: int
    tables_passed: int
    tables_failed: int
    tables_error: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    tables: list[ValidationTableDetailResponse]


class PaginatedValidationRunsResponse(BaseModel):
    """Paginated list of validation runs."""
    runs: list[ValidationRunResponse]
    total: int
    page: int
    page_size: int


class MigrationInfoResponse(BaseModel):
    """Migration info for auto-filling validation form."""
    migration_id: int
    migration_name: str
    source_connection_id: Optional[int] = None
    target_connection_id: Optional[int] = None
    source_connection_name: Optional[str] = None
    target_connection_name: Optional[str] = None
    tables: list[str] = []
    table_row_counts: Optional[dict[str, Optional[int]]] = Field(
        default=None,
        description="Row counts per table from the source migration metrics, keyed by table name",
    )


class BedrockModelResponse(BaseModel):
    """Bedrock model info."""
    model_id: str
    model_name: str
    provider: str
