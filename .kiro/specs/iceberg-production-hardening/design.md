# Iceberg Production Hardening - Design Document

## Overview

This design extends the existing BQ-to-Iceberg migration feature with production hardening enhancements discovered during multi-tenant data lakehouse deployments. The changes modify existing services to add S3 Tables maintenance configuration, Glue catalog validation, compaction strategy selection, Lake Formation prerequisites, API throttling, hidden partitioning enforcement, and incremental load watermarking.

### Key Design Decisions

1. **Maintenance config via Boto3 API, not PyIceberg properties** — S3 Tables silently ignores properties set through the Iceberg catalog interface. We call `put_table_maintenance_configuration()` directly after table creation.
2. **glue.id auto-derivation** — Rather than requiring manual entry, the system derives `glue.id` from the table bucket ARN, reducing configuration errors.
3. **Per-table compaction strategy** — Compaction strategy is set per-table during structure review, allowing workload-specific optimization.
4. **S3 Tables parallelism cap at 8** — Lower than the standard S3 Iceberg max of 16, reflecting S3 Tables API rate limits.
5. **Hidden partitioning only** — Identity partitions on time columns are never created; transforms (`days()`, `hours()`, etc.) are always used.
6. **File-time watermark for incremental loads** — A monotonically increasing watermark stored in `checkpoint_data` enables efficient incremental processing.

---

## Architecture

### Modified Component Flow

```
Table Creation (existing)
    → S3TablesAdapter.create_table()
    → NEW: S3TablesAdapter.configure_maintenance()  ← Boto3 put_table_maintenance_configuration
    → Glue catalog registration (with validated glue.id)
    → Continue load...
```

### Throttling Retry Flow

```
S3 Tables API Call
    → HTTP 429 / SlowDown?
        → YES: Retry with exponential backoff (1s, 2s, 4s, 8s, 16s) up to 5 retries
        → NO: Other error? Use existing retry logic (S3_TABLES_API_FAILED)
    → All retries exhausted?
        → Mark table failed with S3_TABLES_THROTTLED, continue other tables
```

### Incremental Load Watermark Flow

```
Start Incremental Load for Table X
    → Read watermark from checkpoint_data["file_time_watermarks"][table_name]
    → Filter source files: file_modification_time > watermark
    → No files? Log INFO, mark completed (0 files), return
    → Process files...
    → All files processed successfully?
        → YES: Update watermark = max(file_modification_time) across processed files
        → NO (partial failure): Do NOT update watermark, preserve previous value
```

---

## Components and Interfaces

### 1. S3TablesAdapter — New Methods

```python
# backend/services/bq_iceberg_migration/s3_tables_adapter.py

@dataclass
class MaintenanceConfig:
    """Configuration for S3 Tables maintenance settings."""
    compaction_enabled: bool = True
    target_file_size_mb: int = 512  # 64-512
    compaction_strategy: str = "binpack"  # binpack | sort | z-order
    sort_columns: list[str] = field(default_factory=list)
    snapshot_management_enabled: bool = True
    min_snapshots_to_keep: int = 30
    max_snapshot_age_hours: int = 720


class S3TablesAdapter:
    # ... existing methods ...

    def configure_maintenance(
        self,
        namespace: str,
        table_name: str,
        config: MaintenanceConfig,
    ) -> bool:
        """
        Configure S3 Tables maintenance (compaction + snapshot management)
        via put_table_maintenance_configuration() Boto3 API.

        Called immediately after successful table creation.
        Retries up to 3 times with exponential backoff (2s, 6s, 18s).
        Logs error but does NOT fail the table creation on failure.

        Args:
            namespace: Table namespace.
            table_name: Table name.
            config: MaintenanceConfig with user settings.

        Returns:
            True if configuration succeeded, False if all retries failed.
        """
        ...

    def _build_maintenance_payload(self, config: MaintenanceConfig) -> dict:
        """
        Build the put_table_maintenance_configuration API payload.

        Returns:
            Dict matching the Boto3 API shape for maintenance configuration.
        """
        ...

    @staticmethod
    def derive_glue_id(table_bucket_arn: str) -> str:
        """
        Derive the glue.id catalog identifier from a table bucket ARN.

        Extracts account_id and bucket_name from:
            arn:aws:s3tables:<region>:<account-id>:bucket/<bucket-name>
        Returns:
            String in format: {account_id}:s3tablescatalog/{bucket-name}

        Raises:
            ValueError: If ARN format is invalid.
        """
        ...
```

### 2. Validators — New Functions

```python
# backend/services/bq_iceberg_migration/validators.py

# New glue.id validation pattern
_GLUE_ID_PATTERN = re.compile(
    r'^\d{12}:s3tablescatalog/[a-z0-9][a-z0-9.\-]{1,61}[a-z0-9]$'
)


def validate_glue_id(glue_id: str) -> ValidationResult:
    """
    Validate a glue.id catalog identifier for S3 Tables.

    Expected format: {account_id}:s3tablescatalog/{bucket-name}
    - account_id: 12-digit AWS account ID
    - bucket-name: valid S3 bucket name (3-63 chars)

    Args:
        glue_id: The glue.id value to validate.

    Returns:
        Tuple of (is_valid, error_message).
    """
    ...


def validate_maintenance_config(
    target_file_size_mb: int,
    min_snapshots_to_keep: int,
    max_snapshot_age_hours: int,
) -> ValidationResult:
    """
    Validate S3 Tables maintenance configuration values.

    Rules:
    - target_file_size_mb: integer in [64, 512]
    - min_snapshots_to_keep: positive integer
    - max_snapshot_age_hours: positive integer

    Returns:
        Tuple of (is_valid, error_message).
    """
    ...


def validate_compaction_strategy(
    strategy: str,
    sort_columns: list[str],
    table_schema_columns: list[str],
) -> ValidationResult:
    """
    Validate compaction strategy and sort column references.

    Rules:
    - strategy must be one of: binpack, sort, z-order
    - If strategy is sort or z-order, sort_columns must be non-empty
    - Each sort column must exist in table_schema_columns

    Returns:
        Tuple of (is_valid, error_message).
    """
    ...


def validate_s3_tables_parallelism(parallelism: int) -> ValidationResult:
    """
    Validate parallelism for S3 Tables destinations (max 8).

    Returns:
        Tuple of (is_valid, error_message).
    """
    ...
```

### 3. IcebergLoader — Modified Methods

```python
# backend/services/bq_iceberg_migration/iceberg_loader.py

class ParallelIcebergLoader:
    # ... existing attributes ...

    # New: S3 Tables throttling retry config
    S3_TABLES_THROTTLE_MAX_RETRIES = 5
    S3_TABLES_THROTTLE_BASE_DELAY = 1.0  # seconds
    S3_TABLES_THROTTLE_MAX_DELAY = 32.0  # seconds

    async def _load_single_table_s3_tables(
        self,
        table_config: dict,
        s3_tables_adapter: "S3TablesAdapter",
        maintenance_config: "MaintenanceConfig",
    ) -> TableLoadResult:
        """
        Load a single table to S3 Tables with maintenance config and throttle handling.

        After successful table creation:
        1. Calls s3_tables_adapter.configure_maintenance()
        2. Appends data files with throttle-aware retry

        Throttle retry: exponential backoff starting at 1s, doubling each retry,
        max 5 retries, max delay 32s. Uses error code S3_TABLES_THROTTLED.
        """
        ...

    async def _retry_with_throttle_backoff(
        self,
        operation: Callable,
        table_name: str,
        operation_name: str,
    ) -> Any:
        """
        Execute an S3 Tables API operation with throttle-specific retry logic.

        Distinguishes HTTP 429 / SlowDown from other errors.
        Logs WARNING on each throttle retry with table_name, operation,
        retry count, and backoff delay.

        Raises:
            ThrottleExhaustedException: If all 5 retries are exhausted.
        """
        ...

    def _compute_file_time_watermark(
        self,
        processed_files: list[dict],
    ) -> Optional[str]:
        """
        Compute the maximum file_modification_time across processed files.

        Returns:
            ISO 8601 UTC timestamp string (e.g., "2024-01-15T10:30:00Z")
            or None if no files were processed.
        """
        ...

    def _filter_files_by_watermark(
        self,
        files: list[dict],
        watermark: Optional[str],
    ) -> list[dict]:
        """
        Filter source data files to include only those newer than watermark.

        Args:
            files: List of file metadata dicts with 'file_modification_time' key.
            watermark: ISO 8601 UTC timestamp, or None (include all files).

        Returns:
            Filtered list of files with modification_time > watermark.
        """
        ...
```

### 4. StructureReportGenerator — Modified Methods

```python
# backend/services/bq_iceberg_migration/structure_report.py

# New: Compaction strategy descriptions
COMPACTION_STRATEGY_DESCRIPTIONS = {
    "binpack": "Combines small files without reordering (best for append-heavy workloads)",
    "sort": "Reorders data by specified columns (best for range queries on specific columns)",
    "z-order": "Interleaves multiple columns (best for queries filtering on multiple columns simultaneously)",
}


class StructureReportGenerator:
    # ... existing methods ...

    def _generate_table_report(self, table_meta, type_mapper, partition_mapper, glue_database):
        """
        MODIFIED: Now includes compaction_config field per table.

        New fields in returned dict:
        - compaction_config: {
            "strategy": "binpack" | "sort" | "z-order",
            "sort_columns": [...],  # only for sort/z-order
            "recommended_strategy": "sort",  # if clustering columns exist
            "recommended_sort_columns": [...]
          }
        """
        ...

    def _generate_prerequisites(self, destination_type, migration=None):
        """
        MODIFIED: Now includes Lake Formation prerequisites for S3 Tables.

        New section in returned dict for iceberg_s3_tables:
        - lake_formation: {
            "data_location_permission": "...",
            "glue_database_describe": "...",
            "glue_tables_select": "...",
            "iam_get_data_access": "...",
            "glue_execution_role": "..."
          }
        - glue_id: "<derived glue.id value>"
        """
        ...

    def _generate_lake_formation_prerequisites(
        self,
        table_bucket_arn: str,
        glue_database: str,
        aws_region: str,
        account_id: str,
    ) -> list[dict]:
        """
        Generate Lake Formation prerequisite checklist items.

        Each item is an actionable checklist entry with the specific
        ARN or permission string the user needs to configure.

        Returns:
            List of dicts with keys: description, arn_or_permission, action_type
        """
        ...
```

### 5. PartitionSpecMapper — Modified Logic

```python
# backend/services/bq_iceberg_migration/partition_mapper.py

class PartitionSpecMapper:
    """
    MODIFIED: Enforces hidden partitioning transforms for all time-based columns.
    Never creates identity partitions on time columns.
    """

    # Mapping: (partition_type, granularity) → transform
    TRANSFORM_MAP = {
        ("DATE", None): "day",
        ("DATE", "DAY"): "day",
        ("DATETIME", None): "day",
        ("DATETIME", "DAY"): "day",
        ("DATETIME", "HOUR"): "hour",
        ("DATETIME", "MONTH"): "month",
        ("DATETIME", "YEAR"): "year",
        ("TIMESTAMP", None): "day",
        ("TIMESTAMP", "DAY"): "day",
        ("TIMESTAMP", "HOUR"): "hour",
        ("TIMESTAMP", "MONTH"): "month",
        ("TIMESTAMP", "YEAR"): "year",
    }

    def map_partition_spec(
        self,
        partition_column: str,
        partition_type: str,
        granularity: Optional[str] = None,
    ) -> PartitionSpec:
        """
        Map BQ partitioning to Iceberg hidden partition transform.

        Always uses transform functions (days, hours, months, years).
        Never creates identity partitions on time-based columns.

        Args:
            partition_column: Source column name.
            partition_type: BQ type (DATE, DATETIME, TIMESTAMP).
            granularity: BQ granularity (HOUR, DAY, MONTH, YEAR) or None.

        Returns:
            PartitionSpec with the appropriate transform.
        """
        ...
```

### 6. Error Codes — New Constants

```python
# backend/services/bq_iceberg_migration/error_codes.py

class ErrorCode(str, Enum):
    # ... existing codes ...

    # New: S3 Tables throttling (retryable)
    S3_TABLES_THROTTLED = "S3_TABLES_THROTTLED"

    # New: Maintenance configuration failure (non-retryable after exhausting retries)
    S3_TABLES_MAINTENANCE_CONFIG_FAILED = "S3_TABLES_MAINTENANCE_CONFIG_FAILED"

    # New: Glue ID validation failure (non-retryable)
    GLUE_ID_INVALID = "GLUE_ID_INVALID"

    # New: Compaction strategy validation failure (non-retryable)
    COMPACTION_STRATEGY_INVALID = "COMPACTION_STRATEGY_INVALID"
```

### 7. API Router — New/Modified Endpoints

```python
# backend/routers/bq_iceberg_migration.py

class MaintenanceConfigRequest(BaseModel):
    """Request schema for maintenance configuration."""
    target_file_size_mb: int = Field(512, ge=64, le=512)
    min_snapshots_to_keep: int = Field(30, gt=0)
    max_snapshot_age_hours: int = Field(720, gt=0)


class CompactionConfigRequest(BaseModel):
    """Per-table compaction strategy configuration."""
    strategy: str = Field("binpack", pattern="^(binpack|sort|z-order)$")
    sort_columns: list[str] = Field(default_factory=list)


class CreateIcebergMigrationRequest(BaseModel):
    """MODIFIED: Added maintenance_config field."""
    # ... existing fields ...

    # NEW: Maintenance configuration (S3 Tables only)
    maintenance_config: Optional[MaintenanceConfigRequest] = None


class StructureApprovalRequest(BaseModel):
    """MODIFIED: Added per-table compaction_config."""
    # ... existing fields ...

    # NEW: Per-table compaction configuration
    table_compaction_configs: Optional[Dict[str, CompactionConfigRequest]] = None
```

### 8. Frontend Components — New UI Elements

```
┌─────────────────────────────────────────────────────────────┐
│  Migration Wizard - Step 3: Destination Configuration        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Destination Type: [S3 Tables ▼]                             │
│                                                               │
│  Table Bucket ARN: [arn:aws:s3tables:us-east-1:...]          │
│  Namespace: [my_namespace]                                    │
│  Glue Database: [my_database]                                │
│  Derived glue.id: 123456789012:s3tablescatalog/my-bucket ✓   │
│                                                               │
│  ┌─── Table Maintenance Settings ──────────────────────────┐ │
│  │  Target File Size (MB): [512]  (64-512)                 │ │
│  │  Min Snapshots to Keep: [30]                            │ │
│  │  Max Snapshot Age (hours): [720]                        │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  Parallelism: [4]  (max 8 for S3 Tables)                    │
│  ⚠️ S3 Tables has lower concurrency limits than standard S3  │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```


```
┌─────────────────────────────────────────────────────────────┐
│  Structure Review - Per-Table Compaction Strategy             │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Table: orders                                                │
│  Partition: days(created_at)                                  │
│                                                               │
│  Compaction Strategy: [Sort ▼]                               │
│    ℹ️ Recommended: Sort (source has clustering on order_date) │
│    • Binpack: Combines small files without reordering         │
│    • Sort: Reorders data by specified columns                 │
│    • Z-Order: Interleaves multiple columns                    │
│                                                               │
│  Sort Columns: [order_date, customer_id]                     │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Models

### Changes to MigrationBQIceberg Model

No new database columns are added. All new configuration is stored in the existing `checkpoint_data` JSONB field and the `table_load_configs` JSONB field.

#### checkpoint_data Structure (Extended)

```json
{
  "iceberg_structure_plan": {
    "tables": [
      {
        "source_table": "orders",
        "proposed_name": "orders",
        "compaction_config": {
          "strategy": "sort",
          "sort_columns": ["order_date", "customer_id"]
        },
        "partition_spec": {
          "column": "created_at",
          "transform": "day"
        }
      }
    ]
  },
  "maintenance_config": {
    "target_file_size_mb": 512,
    "min_snapshots_to_keep": 30,
    "max_snapshot_age_hours": 720
  },
  "glue_id": "123456789012:s3tablescatalog/my-table-bucket",
  "file_time_watermarks": {
    "orders": "2024-01-15T10:30:00Z",
    "customers": "2024-01-15T09:45:00Z"
  }
}
```

#### New Fields in table_load_configs

```json
{
  "orders": {
    "compaction_strategy": "sort",
    "sort_columns": ["order_date", "customer_id"]
  },
  "customers": {
    "compaction_strategy": "binpack",
    "sort_columns": []
  }
}
```

### Validation Constraints

| Field | Type | Range | Default |
|-------|------|-------|---------|
| target_file_size_mb | int | 64–512 | 512 |
| min_snapshots_to_keep | int | > 0 | 30 |
| max_snapshot_age_hours | int | > 0 | 720 |
| compaction_strategy | str | binpack, sort, z-order | binpack |
| sort_columns | list[str] | must exist in table schema | [] |
| parallelism (S3 Tables) | int | 1–8 | 4 |
| glue_id | str | `^\d{12}:s3tablescatalog/[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$` | derived |
| watermark | str | ISO 8601 UTC (second precision) | null |

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Maintenance configuration payload correctness

*For any* valid maintenance configuration (target_file_size_mb in [64, 512], compaction_strategy in {binpack, sort, z-order}, min_snapshots_to_keep > 0, max_snapshot_age_hours > 0, and sort_columns valid for the given strategy), the constructed `put_table_maintenance_configuration` API payload SHALL have `icebergCompaction.isEnabled` set to true, `targetFileSizeMB` matching the input, the correct strategy, and `icebergSnapshotManagement` fields matching the input values.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4**

### Property 2: Compaction sort column validation

*For any* table schema (list of column names) and any list of sort column names, the compaction strategy validator SHALL accept the configuration if and only if every sort column exists in the table schema, and SHALL reject it with an error identifying the invalid column(s) otherwise.

**Validates: Requirements 1.5, 3.4**

### Property 3: glue.id derivation round-trip

*For any* valid table bucket ARN matching `arn:aws:s3tables:<region>:<account-id>:bucket/<bucket-name>`, deriving the glue.id SHALL produce a string in the format `{account_id}:s3tablescatalog/{bucket-name}` where account_id and bucket-name are extracted from the ARN, and the derived glue.id SHALL pass the glue.id validation regex.

**Validates: Requirements 2.1, 2.2, 2.3**

### Property 4: glue.id validation rejects invalid formats

*For any* string that does NOT match the pattern `^\d{12}:s3tablescatalog/[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$`, the glue.id validator SHALL return `(False, error_message)` where the error message contains the expected format description.

**Validates: Requirements 2.2, 2.6**

### Property 5: Structure report compaction defaults and recommendations

*For any* table metadata with an S3 Tables destination, the generated structure report SHALL include a `compaction_config` field defaulting to `binpack`; and *for any* table metadata that includes clustering columns, the report SHALL recommend `sort` compaction with those clustering columns as the suggested sort columns.

**Validates: Requirements 3.1, 3.2**

### Property 6: Maintenance config validation

*For any* integer target_file_size_mb, the maintenance config validator SHALL accept values in [64, 512] and reject values outside that range; *for any* min_snapshots_to_keep or max_snapshot_age_hours, the validator SHALL accept positive integers and reject zero or negative values.

**Validates: Requirements 4.3, 4.4**

### Property 7: S3 Tables parallelism enforcement

*For any* integer parallelism value and an S3 Tables destination, the validator SHALL accept values in [1, 8] and reject values greater than 8 or less than 1.

**Validates: Requirements 6.1, 6.7**

### Property 8: S3 Tables error code classification

*For any* S3 Tables API error response, if the HTTP status is 429 or the error code is `SlowDown`, the system SHALL classify it as `S3_TABLES_THROTTLED`; for all other S3 Tables errors (403, 404, 500, etc.), the system SHALL classify it as `S3_TABLES_API_FAILED`.

**Validates: Requirements 6.4**

### Property 9: Hidden partition transform mapping

*For any* time-based partition column (DATE, DATETIME, or TIMESTAMP type) with any granularity (HOUR, DAY, MONTH, YEAR, or None), the partition mapper SHALL produce a PartitionSpec using the correct transform function (`day` for DATE/default, `hour` for HOUR granularity, `month` for MONTH, `year` for YEAR) and SHALL never produce an identity partition.

**Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5, 7.7**

### Property 10: Partition transform display format

*For any* partition spec with a transform and column name, the structure report display string SHALL contain the transform function wrapping the column name (e.g., `days(column_name)`) in a human-readable format.

**Validates: Requirements 7.6**

### Property 11: File-time watermark filtering

*For any* list of source files with `file_modification_time` values and any watermark timestamp, the filtering function SHALL return exactly those files whose `file_modification_time` is strictly greater than the watermark, and SHALL return all files when watermark is None.

**Validates: Requirements 8.2**

### Property 12: Watermark monotonicity

*For any* sequence of watermark update operations, the stored watermark SHALL never decrease — a new watermark value is written only if it is strictly greater than the existing value. After a successful load, the watermark SHALL equal the maximum `file_modification_time` across all processed files.

**Validates: Requirements 8.1, 8.3**

### Property 13: Watermark preservation on failure

*For any* incremental load that fails partway through processing, the watermark SHALL remain at its pre-load value, ensuring the next retry reprocesses all files from the last successful checkpoint.

**Validates: Requirements 8.4**

### Property 14: Watermark format

*For any* watermark value stored by the system, it SHALL be a valid ISO 8601 UTC timestamp with second precision matching the pattern `\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z`.

**Validates: Requirements 8.6**

### Property 15: Lake Formation prerequisites contain specific ARNs

*For any* valid table bucket ARN and AWS region, the generated Lake Formation prerequisites SHALL contain the bucket ARN in the data location permission entry and SHALL include the specific IAM permission strings (`lakeformation:GetDataAccess`, `DESCRIBE`, `SELECT`).

**Validates: Requirements 5.2, 5.3, 5.4, 5.7**

---

## Error Handling

### Error Code Table

| Error Code | Category | Retryable | Trigger |
|------------|----------|-----------|---------|
| `S3_TABLES_THROTTLED` | S3 Tables | Yes (5 retries, exponential backoff 1-32s) | HTTP 429 or SlowDown from S3 Tables API |
| `S3_TABLES_MAINTENANCE_CONFIG_FAILED` | S3 Tables | No (after 3 retries exhausted) | `put_table_maintenance_configuration()` failure |
| `GLUE_ID_INVALID` | Validation | No | glue.id format validation failure |
| `COMPACTION_STRATEGY_INVALID` | Validation | No | Invalid strategy or sort columns not in schema |

### Retry Strategies

| Operation | Max Retries | Backoff | Max Delay | On Exhaustion |
|-----------|-------------|---------|-----------|---------------|
| Maintenance config | 3 | Exponential (×3): 2s, 6s, 18s | 18s | Log error, continue migration |
| S3 Tables API (throttle) | 5 | Exponential (×2): 1s, 2s, 4s, 8s, 16s | 32s | Mark table failed, continue others |
| S3 Tables API (other) | 3 | Exponential (×3): 5s, 15s, 45s | 45s | Mark table failed (existing behavior) |

### Error Handling Principles

1. **Maintenance config failure is non-fatal** — Table creation succeeds even if maintenance configuration fails. The table will use S3 Tables default maintenance settings.
2. **Throttle errors are isolated** — A throttled table does not affect other tables being loaded in parallel.
3. **Watermark safety** — On any failure during incremental load, the watermark is NOT updated, ensuring safe retry.
4. **Validation errors are immediate** — Invalid glue.id, compaction strategy, or maintenance config values are rejected at the API layer before any AWS calls are made.

---

## Testing Strategy

### Property-Based Tests (Hypothesis)

Property-based tests use the [Hypothesis](https://hypothesis.readthedocs.io/) library with a minimum of 100 iterations per property. Each test references its design document property.

**Test file:** `backend/tests/property/test_iceberg_production_hardening.py`

| Property | Test Function | Key Generators |
|----------|---------------|----------------|
| Property 1 | `test_maintenance_payload_correctness` | `st.integers(64, 512)`, `st.sampled_from(["binpack", "sort", "z-order"])`, `st.integers(1, 1000)` |
| Property 2 | `test_compaction_sort_column_validation` | `st.lists(st.text(alphabet=ascii_lowercase, min_size=1))` for schema, subsets for sort columns |
| Property 3 | `test_glue_id_derivation_round_trip` | Custom strategy generating valid table bucket ARNs |
| Property 4 | `test_glue_id_validation_rejects_invalid` | `st.text()` filtered to exclude valid patterns |
| Property 5 | `test_structure_report_compaction_defaults` | Custom strategy for table metadata with/without clustering |
| Property 6 | `test_maintenance_config_validation` | `st.integers()` for boundary testing |
| Property 7 | `test_s3_tables_parallelism_enforcement` | `st.integers(0, 20)` |
| Property 8 | `test_error_code_classification` | `st.sampled_from([429, 403, 404, 500])`, `st.sampled_from(["SlowDown", "AccessDenied", ...])` |
| Property 9 | `test_hidden_partition_transform_mapping` | `st.sampled_from(["DATE", "DATETIME", "TIMESTAMP"])`, `st.sampled_from([None, "HOUR", "DAY", "MONTH", "YEAR"])` |
| Property 10 | `test_partition_transform_display_format` | `st.text(alphabet=ascii_lowercase+"_", min_size=1)` for column names, `st.sampled_from(["day", "hour", "month", "year"])` |
| Property 11 | `test_file_watermark_filtering` | `st.lists(st.datetimes())` for file times, `st.datetimes()` for watermark |
| Property 12 | `test_watermark_monotonicity` | `st.lists(st.datetimes())` for sequences of max times |
| Property 13 | `test_watermark_preservation_on_failure` | `st.datetimes()` for initial watermark, `st.lists(st.datetimes())` for file times |
| Property 14 | `test_watermark_format` | `st.datetimes(timezones=st.just(timezone.utc))` |
| Property 15 | `test_lake_formation_prerequisites_contain_arns` | Custom strategy for valid bucket ARNs |

### Unit Tests (pytest)

**Test file:** `backend/tests/unit/test_iceberg_production_hardening.py`

| Test | Validates |
|------|-----------|
| `test_maintenance_config_retry_on_failure` | Req 1.6: 3 retries with 2s, 6s, 18s backoff |
| `test_maintenance_config_does_not_fail_table_creation` | Req 1.6: Migration continues after config failure |
| `test_no_pyiceberg_maintenance_properties_for_s3_tables` | Req 1.7: No maintenance props via PyIceberg |
| `test_maintenance_config_success_logging` | Req 1.8: INFO log with correct fields |
| `test_glue_id_in_structure_report_prerequisites` | Req 2.4: Prerequisites include glue.id |
| `test_glue_id_passed_as_warehouse_property` | Req 2.5: Catalog init uses glue.id |
| `test_glue_id_validation_error_message` | Req 2.6: Specific error message format |
| `test_compaction_strategy_persistence_in_checkpoint` | Req 3.5: checkpoint_data contains compaction_config |
| `test_default_binpack_when_no_selection` | Req 3.6: Default strategy applied |
| `test_strategy_descriptions_in_response` | Req 3.7: API returns descriptions |
| `test_maintenance_ui_defaults` | Req 4.2: Default values 512/30/720 |
| `test_maintenance_settings_hidden_for_standard_s3` | Req 4.5: Not shown for iceberg_s3 |
| `test_lake_formation_section_for_s3_tables_only` | Req 5.6: LF section conditional |
| `test_throttle_warning_parallelism_above_8` | Req 6.2: Warning message |
| `test_throttle_retry_backoff_sequence` | Req 6.3: 1s, 2s, 4s, 8s, 16s delays |
| `test_throttle_exhausted_marks_table_failed` | Req 6.6: S3_TABLES_THROTTLED error code |
| `test_no_new_files_logs_info` | Req 8.5: INFO log, zero files result |
| `test_full_reload_resets_watermark` | Req 8.7: Watermark set to null |

### Integration Tests

**Test file:** `backend/tests/integration/test_iceberg_production_hardening_integration.py`

| Test | Validates |
|------|-----------|
| `test_create_migration_with_maintenance_config` | End-to-end API: create with maintenance settings |
| `test_structure_approval_with_compaction_config` | End-to-end: approve structure with per-table compaction |
| `test_connection_test_validates_glue_id` | End-to-end: connection test derives and validates glue.id |
| `test_incremental_load_watermark_lifecycle` | End-to-end: full → incremental → watermark update |

### Frontend Tests

| Component | Test |
|-----------|------|
| `MaintenanceConfigForm` | Renders fields, validates ranges, shows only for S3 Tables |
| `CompactionStrategySelector` | Renders options, shows sort columns for sort/z-order, displays descriptions |
| `StructureReviewTable` | Shows compaction config, partition transforms, LF prerequisites |
| `ParallelismInput` | Caps at 8 for S3 Tables, shows warning above 8 |

### Test Configuration

```python
# conftest.py additions
from hypothesis import settings, HealthCheck

settings.register_profile(
    "ci",
    max_examples=200,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.register_profile(
    "dev",
    max_examples=100,
)
```

Tag format for property tests:
```python
# Feature: iceberg-production-hardening, Property 1: Maintenance configuration payload correctness
```
