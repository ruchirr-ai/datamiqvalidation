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

    table_name: str = Field(
        ...,
        description="Name of the table to validate"
    )

    # Existing checks
    ddl_check: bool = Field(
        default=True,
        description="Run DDL/schema comparison"
    )

    row_count_check: bool = Field(
        default=True,
        description="Run row count comparison"
    )

    data_match_check: bool = Field(
        default=True,
        description="Run record-level data matching"
    )

    # New validation checks
    null_check: bool = Field(
        default=False,
        description="Run NULL validation"
    )

    null_column: Optional[str] = Field(
        default=None,
        description="Column to check for NULL values"
    )

    duplicate_check: bool = Field(
        default=False,
        description="Run duplicate validation"
    )

    duplicate_match_key: Optional[str] = Field(
        default=None,
        description="Column used as the duplicate match key"
    )

    sum_check: bool = Field(
        default=False,
        description="Run SUM validation"
    )

    sum_column: Optional[str] = Field(
        default=None,
        description="Numeric column used for SUM validation"
    )

    average_check: bool = Field(
        default=False,
        description="Run AVERAGE validation"
    )

    average_column: Optional[str] = Field(
        default=None,
        description="Numeric column used for AVERAGE validation"
    )

    specific_row_check: bool = Field(
        default=False,
        description="Run specific row validation"
    )

    specific_row_match_key: Optional[str] = Field(
        default=None,
        description="Match key for specific row validation"
    )

    specific_row_start: Optional[int] = Field(
        default=None,
        description="Starting row for specific row validation"
    )

    specific_row_end: Optional[int] = Field(
        default=None,
        description="Ending row for specific row validation"
    )

    # Existing sampling configuration
    sampling_mode: Optional[SamplingMode] = Field(
        default=None,
        description="Per-table sampling mode override"
    )

    sample_limit: Optional[int] = Field(
        default=None,
        ge=100,
        le=10000000,
        description="Per-table sample limit when sampling_mode is 'random'"
    )

    batch_size: Optional[int] = Field(
        default=None,
        ge=0,
        le=10000000,
        description="Per-table batch size for record-level matching"
    )


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

    null_status: Optional[str] = None
    null_result: Optional[dict] = None

    duplicate_status: Optional[str] = None
    duplicate_result: Optional[dict] = None

    sum_status: Optional[str] = None
    sum_result: Optional[dict] = None

    average_status: Optional[str] = None
    average_result: Optional[dict] = None

    specific_row_status: Optional[str] = None
    specific_row_result: Optional[dict] = None

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
    duplicate_result: Optional[dict] = None
    sum_result: Optional[dict] = None
    average_result: Optional[dict] = None
    specific_row_result: Optional[dict] = None
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


# ---------------------------------------------------------------------------
# Direct validation test (connection-to-connection, no migration)
# ---------------------------------------------------------------------------

class DirectValidationRequest(BaseModel):
    """Request body for POST /api/validations/direct-test.

    Runs validation checks directly between two connections without a
    migration record. Works across any supported engine pair
    (e.g. SQL Server source -> Redshift target).
    """
    source_connection_id: int = Field(..., description="Source connection ID")
    target_connection_id: int = Field(..., description="Target connection ID")
    source_schema: str = Field(..., description="Source schema / dataset name")
    target_schema: str = Field(..., description="Target schema name")
    table_name: str = Field(..., description="Table to validate (same name on both sides)")

    row_count: bool = Field(default=True, description="Run row count comparison")
    ddl_check: bool = Field(default=False, description="Run schema/DDL comparison (live columns)")
    null_check: bool = Field(default=False, description="Run NULL count comparison")
    null_column: Optional[str] = Field(default=None, description="Column for NULL check")
    duplicate_check: bool = Field(default=False, description="Run duplicate count comparison")
    duplicate_match_key: Optional[str] = Field(default=None, description="Match key column for duplicate check")
    sum_check: bool = Field(default=False, description="Run SUM comparison")
    sum_column: Optional[str] = Field(default=None, description="Numeric column for SUM check")
    average_check: bool = Field(default=False, description="Run AVERAGE comparison")
    average_column: Optional[str] = Field(default=None, description="Numeric column for AVERAGE check")
    specific_row_check: bool = Field(default=False, description="Run specific-row comparison over a key range")
    specific_row_match_key: Optional[str] = Field(default=None, description="Match key column for specific-row check")
    specific_row_start: Optional[int] = Field(default=None, description="Start row (1-based) for specific-row check")
    specific_row_end: Optional[int] = Field(default=None, description="End row (1-based, inclusive) for specific-row check")


class DirectValidationCheckResult(BaseModel):
    """Result of a single direct validation check."""
    status: str
    source_value: Optional[float] = None
    target_value: Optional[float] = None
    difference: Optional[float] = None
    error_message: Optional[str] = None


class DirectValidationResponse(BaseModel):
    """Response for a direct validation test."""
    overall_status: str
    source_engine: str
    target_engine: str
    source_connection: str
    target_connection: str
    table_name: str
    checks: dict


# ---------------------------------------------------------------------------
# Saved direct validation configurations
# ---------------------------------------------------------------------------

class SaveDirectConfigRequest(BaseModel):
    """Request body for POST /api/validations/direct-configs.

    Persists the reusable setup of a direct (connection-to-connection)
    validation so it can be re-loaded into the wizard and re-run. Only the
    configuration is stored, never results.
    """
    name: str = Field(..., min_length=1, max_length=255, description="Display name for the saved configuration")
    source_connection_id: int = Field(..., description="Source connection ID")
    target_connection_id: int = Field(..., description="Target connection ID")
    config: dict = Field(
        ...,
        description="Table pairs and per-pair check configuration, as produced by the wizard",
    )


class DirectConfigResponse(BaseModel):
    """Response schema for a saved direct validation configuration."""
    id: int
    workspace_id: int
    name: str
    source_connection_id: int
    target_connection_id: int
    config: dict
    created_by: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
