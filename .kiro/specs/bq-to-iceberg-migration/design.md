# BigQuery to Apache Iceberg Migration - Design Document

## Overview

This design extends DataMIQ's migration platform to support Apache Iceberg as a new destination target. The feature reuses the existing export and transfer stages (Pathways A/B/C) and introduces a new **Iceberg Loader** service that replaces the Redshift Loader for Iceberg-bound migrations. A pre-load **Structure Review Checkpoint** gives users visibility and control over the proposed Iceberg table design before any tables are created. A **Cost Analysis Engine** provides TCO projections alongside the structure report.

### Key Design Decisions

1. **Reuse existing orchestrator** — The `MigrationOrchestrator` is extended (not replaced) with an Iceberg-aware load path. Export and transfer stages remain unchanged.
2. **New model, not extended model** — A new `MigrationBQIceberg` SQLAlchemy model is introduced rather than overloading `MigrationBQRedshift` with Iceberg-specific fields.
3. **PyIceberg as the Iceberg SDK** — All table creation, schema evolution, and data append operations use the PyIceberg library, which natively supports AWS Glue Data Catalog.
4. **Structure review as a first-class migration status** — The `pending_review` → `approved` status transition is enforced by the orchestrator before the load stage can begin.
5. **S3 Tables variant handled via adapter** — A thin adapter layer abstracts the difference between standard S3 Iceberg and AWS S3 Tables (managed Iceberg).
6. **Parallel table loading** — A configurable worker pool (default 4, max 16) processes tables concurrently during the load stage.
7. **IAM Role ARN as primary auth** — Supports both IAM Role (via STS AssumeRole) and access keys, with role-based access preferred.
8. **Cost analysis before commitment** — A dedicated cost engine calculates setup, recurring, and projected costs before the user approves the migration.
9. **User-defined custom structures** — Users can define Iceberg table structures from scratch, not just override recommendations.

---

## Architecture

### High-Level Flow

```
User creates Iceberg migration via Wizard
    → Orchestrator: Export stage (BQ → GCS)
    → Orchestrator: Transfer stage (GCS → S3 via Pathway A/B/C)
    → Structure Report Generator (analyze source metadata)
    → Cost Analysis Engine (calculate setup + recurring costs)
    → Status: pending_review (migration pauses)
    → User reviews structure, cost analysis, namespace naming
    → User approves (or defines custom structure / requests changes)
    → Status: approved
    → Parallel Iceberg Loader: Create tables & append data (N workers)
    → Athena Verification (optional, per config)
    → Row Count Validation (full or incremental)
    → Status: completed
```

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Backend Services                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────────┐    ┌──────────────────────────────────────┐   │
│  │   Orchestrator    │───▶│  Structure Report Generator           │   │
│  │  (Extended)       │    │  - Per-table design recommendations   │   │
│  └────────┬─────────┘    │  - Prerequisites checklist             │   │
│           │               │  - Custom structure support            │   │
│           │               └──────────────────────────────────────┘   │
│           │                                                           │
│           │               ┌──────────────────────────────────────┐   │
│           │───────────────▶│  Cost Analysis Engine                 │   │
│           │               │  - Setup costs                         │   │
│           │               │  - Recurring projections (3/6/12 mo)   │   │
│           │               │  - TCO comparison vs BigQuery          │   │
│           │               └──────────────────────────────────────┘   │
│           │                                                           │
│           ▼                                                           │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │         Parallel Iceberg Loader Service                        │   │
│  │  ┌────────────────┐  ┌────────────────────────────────────┐  │   │
│  │  │ Worker Pool    │  │ Deduplication Guard                 │  │   │
│  │  │ (1-16 workers) │  │ (snapshot-based file detection)     │  │   │
│  │  └────────────────┘  └────────────────────────────────────┘  │   │
│  │  ┌────────────────┐  ┌────────────────────────────────────┐  │   │
│  │  │ Type Mapper    │  │ Partition Spec Mapper               │  │   │
│  │  │ BQ → Iceberg   │  │ Default: day() for all time cols   │  │   │
│  │  └────────────────┘  └────────────────────────────────────┘  │   │
│  │  ┌────────────────┐  ┌────────────────────────────────────┐  │   │
│  │  │ Schema         │  │ S3 Tables Adapter                  │  │   │
│  │  │ Evolution Svc  │  │ (user-approved namespace naming)   │  │   │
│  │  └────────────────┘  └────────────────────────────────────┘  │   │
│  │  ┌────────────────┐  ┌────────────────────────────────────┐  │   │
│  │  │ Athena         │  │ Credential Provider                │  │   │
│  │  │ Verifier       │  │ (IAM Role or Access Keys)          │  │   │
│  │  └────────────────┘  └────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
                    │                        │
                    ▼                        ▼
    ┌───────────────────────┐   ┌───────────────────────┐
    │   AWS Glue Catalog    │   │   Amazon S3 / S3      │
    │   (PyIceberg)         │   │   Tables              │
    └───────────────────────┘   └───────────────────────┘
                                        │
                                        ▼
                            ┌───────────────────────┐
                            │   Amazon Athena       │
                            │   (Optional Verify)   │
                            └───────────────────────┘
```

---

## Components and Interfaces

### 1. BQ-to-Iceberg Type Mapper (`services/bq_iceberg_migration/type_mapper.py`)

Maps BigQuery column types to PyIceberg type objects.

```python
class BQToIcebergTypeMapper:
    """Maps BigQuery data types to Iceberg types using PyIceberg type system."""

    TYPE_MAP: dict[str, IcebergType] = {
        "STRING": StringType(),
        "BYTES": BinaryType(),
        "INT64": LongType(),
        "INTEGER": LongType(),
        "FLOAT64": DoubleType(),
        "FLOAT": DoubleType(),
        "NUMERIC": DecimalType(38, 9),
        "BIGNUMERIC": DecimalType(38, 18),
        "BOOLEAN": BooleanType(),
        "BOOL": BooleanType(),
        "DATE": DateType(),
        "DATETIME": TimestampType(),       # without timezone
        "TIMESTAMP": TimestamptzType(),    # with timezone
        "TIME": TimeType(),
        "GEOGRAPHY": StringType(),         # fallback
        "JSON": StringType(),              # fallback
    }

    MAX_STRUCT_DEPTH = 15

    def map_column(self, bq_type: str, bq_mode: str, fields: list | None = None, depth: int = 0) -> IcebergType:
        """Map a single BQ column to an Iceberg type, handling STRUCT/ARRAY recursively.
        If depth > MAX_STRUCT_DEPTH, flatten remaining to StringType (JSON)."""
        ...

    def map_schema(self, bq_columns: list[dict]) -> Schema:
        """Map a full BQ table schema to an Iceberg Schema object."""
        ...

    def is_nullable(self, bq_mode: str) -> bool:
        """REQUIRED → False, NULLABLE/REPEATED → True."""
        ...
```

### 2. Partition Spec Mapper (`services/bq_iceberg_migration/partition_mapper.py`)

Converts BigQuery partitioning configuration to Iceberg `PartitionSpec`. Default is `day()` for all time-based columns.

```python
class PartitionSpecMapper:
    """Maps BQ partitioning and clustering to Iceberg partition specs and sort orders."""

    # Default is day() for all time-based columns unless BQ explicitly specifies otherwise
    DEFAULT_TRANSFORM = "day"

    GRANULARITY_TO_TRANSFORM: dict[str, str] = {
        "DAY": "day",
        "HOUR": "hour",
        "MONTH": "month",
        "YEAR": "year",
    }

    def map_partition_spec(self, partition_column: str, column_type: str, granularity: str | None) -> PartitionSpec:
        """Create Iceberg PartitionSpec from BQ partition config.
        Uses day() as default for DATE, DATETIME, and TIMESTAMP columns.
        Only uses hour/month/year if BQ explicitly specifies that granularity."""
        transform = self.GRANULARITY_TO_TRANSFORM.get(granularity, self.DEFAULT_TRANSFORM) if granularity else self.DEFAULT_TRANSFORM
        ...

    def map_sort_order(self, clustering_columns: list[str]) -> SortOrder:
        """Create Iceberg SortOrder preserving BQ clustering column sequence."""
        ...
```

### 3. Credential Provider (`services/bq_iceberg_migration/credential_provider.py`)

Abstracts AWS credential management, supporting both IAM Role ARN and access keys.

```python
class AWSCredentialProvider:
    """Provides AWS credentials via IAM Role (STS AssumeRole) or direct access keys."""

    def __init__(self, kms_service, sts_client):
        self._kms = kms_service
        self._sts = sts_client

    def get_session(self, connection_params: dict) -> boto3.Session:
        """Return a boto3 session using either IAM Role or access keys.
        If aws_role_arn is provided, uses STS AssumeRole.
        Otherwise, decrypts and uses access key credentials."""
        if connection_params.get("aws_role_arn"):
            return self._assume_role(connection_params["aws_role_arn"], connection_params["aws_region"])
        else:
            access_key = connection_params["aws_access_key_id"]
            secret_key = self._kms.decrypt(connection_params["aws_secret_access_key"])
            return boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=connection_params["aws_region"]
            )

    def _assume_role(self, role_arn: str, region: str) -> boto3.Session:
        """Assume IAM role and return temporary credentials session."""
        response = self._sts.assume_role(RoleArn=role_arn, RoleSessionName="datamiq-iceberg-migration")
        creds = response["Credentials"]
        return boto3.Session(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
            region_name=region
        )
```

### 4. Parallel Iceberg Loader (`services/bq_iceberg_migration/iceberg_loader.py`)

Core service that creates Iceberg tables and appends data files using a configurable worker pool.

```python
class ParallelIcebergLoader:
    """Creates Iceberg tables and loads Parquet data files using parallel workers."""

    DEFAULT_PARALLELISM = 4
    MAX_PARALLELISM = 16

    def __init__(self, catalog: GlueCatalog, credential_provider: AWSCredentialProvider,
                 type_mapper: BQToIcebergTypeMapper, partition_mapper: PartitionSpecMapper,
                 dedup_guard: DeduplicationGuard, parallelism: int = 4):
        self._catalog = catalog
        self._cred_provider = credential_provider
        self._type_mapper = type_mapper
        self._partition_mapper = partition_mapper
        self._dedup_guard = dedup_guard
        self._parallelism = min(max(parallelism, 1), self.MAX_PARALLELISM)

    async def load_tables(self, migration: MigrationBQIceberg, structure_plan: dict,
                          progress_callback: Callable) -> LoadResult:
        """Load all tables in parallel using asyncio worker pool."""
        semaphore = asyncio.Semaphore(self._parallelism)
        tasks = []
        for table_plan in structure_plan["tables"]:
            task = asyncio.create_task(self._load_single_table(semaphore, migration, table_plan, progress_callback))
            tasks.append(task)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return self._aggregate_results(results)

    async def _load_single_table(self, semaphore, migration, table_plan, progress_callback) -> TableLoadResult:
        """Load a single table with independent error handling."""
        async with semaphore:
            try:
                # 1. Check deduplication before append
                # 2. Create table (or verify existing)
                # 3. Append data files
                # 4. Update shard status
                # 5. Report progress
                ...
            except Exception as e:
                # Mark this table as failed, do NOT propagate to other tables
                ...

    def create_table(self, database: str, table_name: str, schema: Schema,
                     partition_spec: PartitionSpec, sort_order: SortOrder,
                     properties: dict) -> Table:
        """Create an Iceberg table in Glue Data Catalog."""
        ...

    def append_data_files(self, table: Table, s3_file_uris: list[str]) -> None:
        """Register existing Parquet files as data files in the Iceberg table."""
        ...

    def ensure_database_exists(self, database: str) -> None:
        """Create Glue database if it doesn't exist."""
        ...
```

### 5. Deduplication Guard (`services/bq_iceberg_migration/dedup_guard.py`)

Ensures zero duplicate data on retry/resume by checking Iceberg snapshot metadata.

```python
class DeduplicationGuard:
    """Prevents duplicate data file registration during retry/resume operations."""

    def get_registered_files(self, table: Table) -> set[str]:
        """Get all data file paths currently registered in the Iceberg table's latest snapshot."""
        snapshot = table.current_snapshot()
        if not snapshot:
            return set()
        return {file.file_path for file in snapshot.manifests(table.io)}

    def filter_new_files(self, table: Table, candidate_files: list[str]) -> list[str]:
        """Return only files not already registered in the table.
        Compares candidate S3 URIs against snapshot metadata."""
        registered = self.get_registered_files(table)
        return [f for f in candidate_files if f not in registered]

    def is_safe_to_append(self, table: Table, candidate_files: list[str]) -> tuple[bool, list[str]]:
        """Check if append is safe (no duplicates). Returns (safe, new_files_only)."""
        new_files = self.filter_new_files(table, candidate_files)
        return (len(new_files) > 0, new_files)
```

### 6. S3 Tables Adapter (`services/bq_iceberg_migration/s3_tables_adapter.py`)

Handles the managed Iceberg variant. Namespace names are user-provided (collected during structure review).

```python
class S3TablesAdapter:
    """Adapter for AWS S3 Tables (managed Iceberg) operations.
    All resource names must be user-approved before creation."""

    def __init__(self, s3tables_client, table_bucket_arn: str, aws_region: str):
        ...

    def ensure_namespace(self, namespace: str) -> None:
        """Create namespace in S3 table bucket if not exists.
        Namespace name MUST be user-provided and approved during structure review."""
        ...

    def create_table(self, namespace: str, table_name: str, schema: Schema,
                     partition_spec: PartitionSpec) -> dict:
        """Create table in S3 Tables and return metadata location.
        Table name MUST be user-approved."""
        ...

    def validate_namespace_name(self, namespace: str) -> bool:
        """Validate namespace name follows S3 Tables naming conventions."""
        ...
```

### 7. Structure Report Generator (`services/bq_iceberg_migration/structure_report.py`)

Generates the pre-load structure design report. Supports both recommendations and custom user-defined structures.

```python
class StructureReportGenerator:
    """Generates the Iceberg Structure Design Report for user review.
    Supports system recommendations and user-defined custom structures."""

    def generate(self, migration: MigrationBQIceberg, assessment_tables: list[AssessmentTable],
                 type_mapper: BQToIcebergTypeMapper, partition_mapper: PartitionSpecMapper) -> dict:
        """Generate the full structure report as a JSON-serializable dict.
        Includes per-table recommendations, prerequisites, and warnings."""
        ...

    def apply_overrides(self, report: dict, overrides: dict) -> dict:
        """Apply user overrides (partition changes, exclusions, custom properties)."""
        ...

    def apply_custom_structure(self, report: dict, table_name: str, custom_def: dict) -> dict:
        """Replace system recommendation with user-defined custom structure for a table.
        custom_def includes: table_name, columns (name, type, nullable),
        partition_spec, sort_order, and table_properties."""
        ...

    def validate_custom_structure(self, custom_def: dict, source_columns: list[dict]) -> list[str]:
        """Validate user-defined structure against source data.
        Returns list of warnings (e.g., type incompatibility, missing columns)."""
        ...

    def apply_dataset_to_db_mapping(self, report: dict, mapping: dict[str, str]) -> dict:
        """Apply BQ dataset → Glue database name mapping."""
        ...

    def export_markdown(self, report: dict) -> str:
        """Export report as Markdown for download."""
        ...

    def export_pdf(self, report: dict) -> bytes:
        """Export report as PDF for download."""
        ...
```

### 8. Cost Analysis Engine (`services/bq_iceberg_migration/cost_engine.py`)

Calculates setup costs, recurring costs, and projections for the Iceberg migration.

```python
class CostAnalysisEngine:
    """Calculates and projects costs for Iceberg migration setup and operations."""

    # AWS pricing constants (configurable per region)
    S3_STORAGE_PER_GB_MONTH = 0.023      # Standard S3
    S3_PUT_REQUEST_PER_1000 = 0.005
    GLUE_CATALOG_PER_MILLION_REQUESTS = 1.00
    GLUE_STORAGE_PER_100K_OBJECTS_MONTH = 1.00
    ATHENA_PER_TB_SCANNED = 5.00
    S3_TABLES_STORAGE_PER_GB_MONTH = 0.028  # S3 Tables premium
    ZSTD_COMPRESSION_RATIO_OPTIMISTIC = 5.0
    ZSTD_COMPRESSION_RATIO_CONSERVATIVE = 3.0

    def calculate(self, assessment_data: dict, destination_type: str,
                  aws_region: str, growth_rate_monthly: float = 0.05,
                  bq_current_costs: dict | None = None) -> CostReport:
        """Generate full cost analysis report."""
        ...

    def _calculate_setup_costs(self, data_size_bytes: int, table_count: int,
                               destination_type: str) -> dict:
        """One-time costs: initial S3 storage, Glue API calls, data transfer."""
        ...

    def _calculate_recurring_costs(self, data_size_bytes: int, table_count: int,
                                    destination_type: str) -> dict:
        """Monthly recurring: S3 storage, Glue requests, Athena queries."""
        ...

    def _project_costs(self, base_monthly: float, growth_rate: float) -> dict:
        """Project costs at 3, 6, and 12 month horizons."""
        return {
            "3_month": base_monthly * sum((1 + growth_rate) ** i for i in range(3)),
            "6_month": base_monthly * sum((1 + growth_rate) ** i for i in range(6)),
            "12_month": base_monthly * sum((1 + growth_rate) ** i for i in range(12)),
        }

    def _calculate_tco_comparison(self, bq_costs: dict, iceberg_projected: dict) -> dict:
        """Compare BigQuery current costs vs projected Iceberg costs."""
        ...

    def recalculate_with_growth_rate(self, report: CostReport, new_growth_rate: float) -> CostReport:
        """Re-calculate projections with user-adjusted growth rate."""
        ...
```

### 9. Schema Evolution Service (`services/bq_iceberg_migration/schema_evolution.py`)

Handles incremental load schema changes. Only supports valid Iceberg type promotions.

```python
class SchemaEvolutionService:
    """Manages Iceberg schema evolution for incremental loads.
    Only valid promotions: int→long, float→double, decimal(P,S)→decimal(P',S) where P'>P."""

    VALID_PROMOTIONS: dict[type, set[type]] = {
        IntegerType: {LongType},
        FloatType: {DoubleType},
        # DecimalType: checked dynamically (P' > P, same S)
    }

    def detect_changes(self, existing_schema: Schema, new_bq_columns: list[dict]) -> SchemaChanges:
        """Detect new columns, type promotions, and incompatible changes."""
        ...

    def apply_evolution(self, table: Table, changes: SchemaChanges) -> None:
        """Apply compatible schema changes to the Iceberg table.
        New columns always added as optional (nullable) regardless of BQ mode."""
        ...

    def is_compatible_promotion(self, old_type: IcebergType, new_type: IcebergType) -> bool:
        """Check if a type change is a valid Iceberg promotion.
        Valid: int→long, float→double, decimal precision widening (same scale).
        Invalid: long→decimal, string→int, any other change."""
        if isinstance(old_type, DecimalType) and isinstance(new_type, DecimalType):
            return new_type.precision > old_type.precision and new_type.scale == old_type.scale
        return type(new_type) in self.VALID_PROMOTIONS.get(type(old_type), set())
```

### 10. Athena Verifier (`services/bq_iceberg_migration/athena_verifier.py`)

Optional per-table verification during load (controlled by `enable_load_stage_verification`).

```python
class AthenaVerifier:
    """Verifies Iceberg tables are queryable via Athena.
    Only runs during load stage if enable_load_stage_verification is True.
    Always available for post-migration validation."""

    def __init__(self, athena_client, workgroup: str = "primary", timeout_seconds: int = 120):
        ...

    def verify_table_queryable(self, database: str, table_name: str) -> VerificationResult:
        """Run SELECT 1 FROM <db>.<table> LIMIT 1 and confirm success within timeout."""
        ...

    def count_rows(self, database: str, table_name: str, timeout_seconds: int = 300) -> int | None:
        """Run SELECT COUNT(*) for post-migration validation."""
        ...
```

### 11. Validation Service (`services/bq_iceberg_migration/validation_service.py`)

Handles both full-load and incremental-load validation logic.

```python
class IcebergValidationService:
    """Validates migrated data correctness for both full and incremental loads."""

    def validate_full_load(self, source_count: int, target_count: int) -> ValidationResult:
        """Full load: exact match required (difference must be 0)."""
        passed = source_count == target_count
        return ValidationResult(passed=passed, source=source_count, target=target_count)

    def validate_incremental_load(self, previous_snapshot_count: int, current_snapshot_count: int,
                                   batch_export_count: int) -> ValidationResult:
        """Incremental: verify delta matches exported batch count.
        delta = current_snapshot_count - previous_snapshot_count
        Must equal batch_export_count."""
        delta = current_snapshot_count - previous_snapshot_count
        passed = delta >= batch_export_count
        return ValidationResult(passed=passed, expected_delta=batch_export_count, actual_delta=delta)
```

### 12. Iceberg Migration Orchestrator Extension

The existing `MigrationOrchestrator` is extended with Iceberg-specific execution and state management.

```python
class IcebergMigrationOrchestrator:
    """Orchestrates BQ-to-Iceberg migrations, extending the base orchestrator pattern.
    Preserves all state on cancel/back from pending_review."""

    def _execute_iceberg_migration(self, migration: MigrationBQIceberg) -> bool:
        """Execute the Iceberg-specific load stage after export+transfer."""
        # 1. Generate structure report (if not already approved)
        # 2. Generate cost analysis report
        # 3. Transition to pending_review and pause
        # 4. On approval, load tables using ParallelIcebergLoader
        # 5. Run Athena verification (if enabled)
        # 6. Run row count validation (full or incremental)
        ...

    def _handle_cancel_from_review(self, migration: MigrationBQIceberg) -> None:
        """Cancel from pending_review: preserve all config, connections, assessment data.
        User can return to any previous step without re-entry."""
        migration.status = "cancelled"
        # Do NOT clear: connections, source_settings, target_settings, assessment_data, table_selections
        # All checkpoint_data preserved for potential restart
        ...

    def _handle_back_navigation(self, migration: MigrationBQIceberg, target_step: str) -> None:
        """Allow user to navigate back to any step while preserving current state."""
        # Preserve all existing configuration
        # Only clear data that would be regenerated by the target step
        ...
```

---

## Data Models

### New Model: `MigrationBQIceberg`

```python
class MigrationBQIceberg(Base):
    """Migration configuration for BigQuery to Iceberg migrations."""
    __tablename__ = 'migrations_bq_iceberg'

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, nullable=False)
    migration_name = Column(String(255), nullable=False)
    pathway = Column(String(10), nullable=False)  # A, B, C

    # Source Configuration (BigQuery)
    source_connection_id = Column(Integer, nullable=True)
    source_project_id = Column(String(255))
    source_dataset = Column(String(255))
    source_tables = Column(ARRAY(Text))

    # Target Configuration (Iceberg)
    target_connection_id = Column(Integer, nullable=True)
    destination_type = Column(String(50), nullable=False)  # iceberg_s3 | iceberg_s3_tables
    s3_bucket = Column(String(255))           # For iceberg_s3
    s3_path_prefix = Column(String(512))      # For iceberg_s3
    table_bucket_arn = Column(String(500))    # For iceberg_s3_tables
    s3_tables_namespace = Column(String(255)) # User-provided namespace for S3 Tables
    aws_region = Column(String(50), nullable=False)
    glue_database_name = Column(String(255), nullable=False)
    dataset_to_db_mapping = Column(JSONB)     # BQ dataset → Glue DB name mapping

    # AWS Credentials (access keys OR role ARN)
    aws_access_key_id = Column(String(255))
    aws_secret_access_key_encrypted = Column(Text)
    aws_role_arn = Column(String(500))        # Alternative: IAM Role ARN

    # Intermediate Storage
    gcs_bucket = Column(String(255))
    gcs_path = Column(String(500))
    gcs_region = Column(String(100))
    export_format = Column(String(50), default='PARQUET')
    compression = Column(String(50), default='ZSTD')
    service_account_json_encrypted = Column(Text)

    # Load Configuration
    load_type = Column(String(20), default='full')  # full | incremental
    table_load_configs = Column(JSONB)
    parallelism = Column(Integer, default=4)         # 1-16 concurrent tables
    enable_load_stage_verification = Column(Boolean, default=False)  # Optional Athena check during load

    # State Management
    status = Column(String(50), nullable=False, default='pending')
    current_stage = Column(String(50))  # export, transfer, review, load
    checkpoint_data = Column(JSONB)     # Includes iceberg_structure_plan when approved
    resume_point = Column(String(100))

    # Structure Review
    structure_report = Column(JSONB)
    cost_analysis_report = Column(JSONB)    # Cost analysis data
    structure_approved_at = Column(DateTime)
    structure_approved_by = Column(Integer)

    # Scheduling
    schedule_type = Column(String(50))
    cron_expression = Column(String(100))
    next_run_time = Column(DateTime)

    # Metrics
    total_rows_source = Column(BigInteger)
    total_rows_target = Column(BigInteger)
    total_bytes_transferred = Column(BigInteger)
    progress_percentage = Column(Integer, default=0)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    duration_seconds = Column(Integer)
    last_run_at = Column(DateTime)

    # Metadata
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

    __table_args__ = (
        CheckConstraint("destination_type IN ('iceberg_s3', 'iceberg_s3_tables')", name='check_iceberg_dest_type'),
        CheckConstraint("pathway IN ('A', 'B', 'C')", name='check_iceberg_pathway'),
        CheckConstraint("parallelism >= 1 AND parallelism <= 16", name='check_parallelism_range'),
    )
```

### New Model: `IcebergTableValidation`

```python
class IcebergTableValidation(Base):
    """Per-table validation results for Iceberg migrations."""
    __tablename__ = 'iceberg_table_validations'

    id = Column(Integer, primary_key=True)
    migration_id = Column(Integer, ForeignKey('migrations_bq_iceberg.id'), nullable=False)
    table_name = Column(String(255), nullable=False)
    source_row_count = Column(BigInteger)
    target_row_count = Column(BigInteger)
    match_status = Column(String(50))  # passed, failed, skipped
    validation_type = Column(String(20))  # full, incremental
    batch_export_count = Column(BigInteger)  # For incremental: rows in this batch
    previous_snapshot_count = Column(BigInteger)  # For incremental: count before load
    error_reason = Column(Text)
    validated_at = Column(DateTime)

    __table_args__ = (
        UniqueConstraint('migration_id', 'table_name', name='unique_iceberg_validation'),
    )
```

### Connection Model Extension

The existing `Connection` model's `type` field gains a new value: `"iceberg"`. The `connection_params` JSON stores:

```json
{
  "destination_type": "iceberg_s3",
  "s3_bucket": "my-data-lake",
  "s3_path_prefix": "iceberg/",
  "aws_region": "us-east-1",
  "glue_database_name": "analytics_db",
  "auth_type": "role",
  "aws_role_arn": "arn:aws:iam::123456789012:role/DataMIQIcebergRole"
}
```

Or with access keys:
```json
{
  "destination_type": "iceberg_s3_tables",
  "table_bucket_arn": "arn:aws:s3tables:us-east-1:123456789012:bucket/my-table-bucket",
  "aws_region": "us-east-1",
  "glue_database_name": "analytics_db",
  "auth_type": "keys",
  "aws_access_key_id": "AKIA...",
  "aws_secret_access_key": "encrypted-value"
}
```

### Database Migration (Alembic)

A new Alembic migration creates:
- `migrations_bq_iceberg` table
- `iceberg_table_validations` table
- Indexes on `workspace_id`, `status`, `destination_type`

---

## API Design

### New Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/migrations/bq-iceberg/create` | Create new Iceberg migration |
| GET | `/api/migrations/bq-iceberg/list` | List Iceberg migrations |
| GET | `/api/migrations/bq-iceberg/{id}` | Get migration details |
| PUT | `/api/migrations/bq-iceberg/{id}/update` | Update migration config |
| DELETE | `/api/migrations/bq-iceberg/{id}` | Delete migration |
| POST | `/api/migrations/bq-iceberg/{id}/start` | Start migration |
| POST | `/api/migrations/bq-iceberg/{id}/pause` | Pause migration |
| POST | `/api/migrations/bq-iceberg/{id}/resume` | Resume migration |
| POST | `/api/migrations/bq-iceberg/{id}/cancel` | Cancel (preserves config) |
| POST | `/api/migrations/bq-iceberg/{id}/restart` | Restart migration |
| GET | `/api/migrations/bq-iceberg/{id}/status` | Get status with progress |
| GET | `/api/migrations/bq-iceberg/{id}/logs` | Get migration logs |
| GET | `/api/migrations/bq-iceberg/{id}/structure-report` | Get structure report |
| GET | `/api/migrations/bq-iceberg/{id}/cost-analysis` | Get cost analysis |
| POST | `/api/migrations/bq-iceberg/{id}/cost-analysis/recalculate` | Recalculate with new growth rate |
| POST | `/api/migrations/bq-iceberg/{id}/approve-structure` | Approve structure plan |
| POST | `/api/migrations/bq-iceberg/{id}/request-changes` | Submit structure overrides |
| POST | `/api/migrations/bq-iceberg/{id}/custom-structure` | Define custom table structure |
| GET | `/api/migrations/bq-iceberg/{id}/download-report` | Download report (MD/PDF) |
| POST | `/api/migrations/bq-iceberg/{id}/validate` | Trigger manual validation |
| GET | `/api/migrations/bq-iceberg/{id}/validation-results` | Get validation results |
| POST | `/api/connections/test-iceberg` | Test Iceberg connection |

### Request/Response Examples

**Create Migration:**
```json
POST /api/migrations/bq-iceberg/create
{
  "migration_name": "analytics_to_iceberg",
  "pathway": "A",
  "source_connection_id": 1,
  "source_project_id": "my-gcp-project",
  "source_dataset": "analytics",
  "source_tables": ["events", "users", "sessions"],
  "destination_type": "iceberg_s3",
  "s3_bucket": "my-data-lake",
  "s3_path_prefix": "iceberg/analytics/",
  "aws_region": "us-east-1",
  "glue_database_name": "analytics_db",
  "aws_role_arn": "arn:aws:iam::123456789012:role/DataMIQIcebergRole",
  "gcs_bucket": "my-export-bucket",
  "gcs_path": "exports/analytics/",
  "load_type": "full",
  "parallelism": 8,
  "enable_load_stage_verification": false
}
```

**Define Custom Structure:**
```json
POST /api/migrations/bq-iceberg/{id}/custom-structure
{
  "table_name": "events",
  "custom_definition": {
    "iceberg_table_name": "raw_events",
    "columns": [
      {"name": "event_id", "type": "string", "nullable": false},
      {"name": "event_date", "type": "date", "nullable": true},
      {"name": "user_id", "type": "long", "nullable": true},
      {"name": "payload", "type": "string", "nullable": true}
    ],
    "partition_spec": {"column": "event_date", "transform": "month"},
    "sort_order": [{"column": "user_id", "direction": "asc"}],
    "table_properties": {
      "format-version": "2",
      "write.format.default": "parquet",
      "write.parquet.compression-codec": "zstd",
      "write.target-file-size-bytes": "536870912"
    }
  }
}
```

**Approve Structure (with overrides and dataset mapping):**
```json
POST /api/migrations/bq-iceberg/{id}/approve-structure
{
  "dataset_to_db_mapping": {
    "analytics": "analytics_lake_db",
    "marketing": "marketing_lake_db"
  },
  "s3_tables_namespace": "production_analytics",
  "overrides": {
    "events": {
      "partition_spec": {"column": "event_date", "transform": "month"},
      "custom_properties": {"write.target-file-size-bytes": "536870912"}
    },
    "excluded_tables": ["temp_sessions"]
  }
}
```

**Cost Analysis Response:**
```json
GET /api/migrations/bq-iceberg/{id}/cost-analysis
{
  "generated_at": "2026-05-20T10:00:00Z",
  "data_size_gb": 240,
  "compressed_size_gb_optimistic": 48,
  "compressed_size_gb_conservative": 80,
  "setup_costs": {
    "s3_initial_storage": 1.84,
    "glue_api_calls": 0.05,
    "data_transfer": 21.60,
    "total_setup": 23.49
  },
  "recurring_monthly": {
    "s3_storage_optimistic": 1.10,
    "s3_storage_conservative": 1.84,
    "glue_catalog": 0.01,
    "athena_verification": 0.24,
    "total_monthly_optimistic": 1.35,
    "total_monthly_conservative": 2.09
  },
  "projections": {
    "growth_rate_monthly": 0.05,
    "3_month_total": 4.25,
    "6_month_total": 9.18,
    "12_month_total": 21.47
  },
  "tco_comparison": {
    "bigquery_current_monthly": 45.00,
    "iceberg_projected_monthly": 2.09,
    "monthly_savings": 42.91,
    "annual_savings_projected": 514.92
  }
}
```

**Recalculate Cost with New Growth Rate:**
```json
POST /api/migrations/bq-iceberg/{id}/cost-analysis/recalculate
{
  "growth_rate_monthly": 0.10
}
```

**Structure Report Response (abbreviated):**
```json
GET /api/migrations/bq-iceberg/{id}/structure-report
{
  "migration_id": 1,
  "generated_at": "2026-05-20T10:00:00Z",
  "tables": [
    {
      "source_table": "events",
      "proposed_name": "events",
      "structure_mode": "recommended",
      "columns": [
        {"name": "event_id", "bq_type": "STRING", "iceberg_type": "string", "nullable": false},
        {"name": "event_date", "bq_type": "DATE", "iceberg_type": "date", "nullable": true}
      ],
      "partition_spec": {"column": "event_date", "transform": "day", "rationale": "Default day() for DATE column"},
      "sort_order": ["user_id", "event_date"],
      "estimated_rows": 50000000,
      "estimated_size_mb": 2400,
      "table_properties": {
        "format-version": "2",
        "write.format.default": "parquet",
        "write.parquet.compression-codec": "zstd"
      },
      "warnings": []
    }
  ],
  "dataset_to_db_mapping": {"analytics": "analytics_db"},
  "s3_tables_namespace": null,
  "prerequisites": { ... },
  "warnings": []
}
```

---

## Correctness Properties

### Property 1: Type mapping completeness and correctness

**Validates: Requirements 3.1**

*For any* BigQuery column with a type in the defined mapping, the type mapper SHALL produce the corresponding Iceberg type, and for any unrecognized type, it SHALL produce StringType.

### Property 2: Nullability mapping

**Validates: Requirements 3.4**

*For any* BigQuery column, if its mode is REQUIRED the mapped Iceberg field SHALL be non-nullable, and if its mode is NULLABLE or REPEATED the mapped Iceberg field SHALL be nullable.

### Property 3: Partition spec transform selection

**Validates: Requirements 3.2**

*For any* BigQuery time-partitioned table with a partition column of type DATE, DATETIME, or TIMESTAMP, and an optional explicit granularity, the partition mapper SHALL produce `day()` as default, or the explicit granularity transform if specified.

### Property 4: Sort order preserves clustering column sequence

**Validates: Requirements 3.3**

*For any* list of BigQuery clustering columns, the Iceberg sort order SHALL contain those columns in the exact same ordinal sequence.

### Property 5: Recursive struct mapping up to depth limit

**Validates: Requirements 3.6, 3.7**

*For any* BigQuery STRUCT/RECORD schema with nesting depth ≤ 15, the type mapper SHALL produce an equivalent Iceberg struct type. For depth > 15, levels beyond 15 SHALL be flattened to StringType.

### Property 6: Input validation for Iceberg configuration fields

**Validates: Requirements 1.2, 1.3, 1.5, 9.4**

*For any* string, the validators SHALL correctly accept/reject based on S3 bucket naming rules, Glue database name pattern (`[a-z0-9_]+`, 1-255 chars), and table bucket ARN format.

### Property 7: Structure report contains all required fields per table

**Validates: Requirements 4.2**

*For any* set of assessment table metadata, the generated structure report SHALL contain all required fields for each table (proposed name, columns, partition spec, sort order, estimated size, properties).

### Property 8: Structure plan round-trip persistence

**Validates: Requirements 4.10**

*For any* approved structure plan (including custom definitions and overrides), serializing to JSONB and deserializing back SHALL produce an equivalent plan.

### Property 9: Progress percentage calculation with parallelism

**Validates: Requirements 5.8, 12.3**

*For any* migration with N total tables where M have completed (0 ≤ M ≤ N, N > 0), progress_percentage SHALL equal `floor((M / N) * 100)` regardless of parallel execution order.

### Property 10: Row count validation correctness (full and incremental)

**Validates: Requirements 10.1, 10.2**

*For any* pair of source and target row counts in a full load, validation SHALL pass if and only if they are equal. For incremental loads, validation SHALL pass if the snapshot delta ≥ batch export count.

### Property 11: Schema evolution adds new columns as optional

**Validates: Requirements 6.2**

*For any* new column detected during incremental load, regardless of BQ mode, it SHALL be added as optional in Iceberg.

### Property 12: Type promotion validity

**Validates: Requirements 6.3, 6.4**

*For any* type change detected during schema evolution, `is_compatible_promotion` SHALL return true only for: int→long, float→double, decimal(P,S)→decimal(P',S) where P'>P and S==S. All other changes SHALL be treated as incompatible.

### Property 13: State machine transition validity

**Validates: Requirements 7.4, 7.5**

*For any* Iceberg migration, status transitions SHALL follow the valid state machine. Cancel from `pending_review` SHALL preserve all configuration data.

### Property 14: Checkpoint-based resume skips completed tables

**Validates: Requirements 7.3**

*For any* set of table load statuses, resuming SHALL process only tables whose load_status is NOT `completed`.

### Property 15: Deduplication on resume

**Validates: Requirements 5.5**

*For any* retry/resume operation, the deduplication guard SHALL detect already-registered files via snapshot metadata and exclude them from the append, ensuring zero duplicate rows.

### Property 16: Error code categorization

**Validates: Requirements 11.3**

*For any* Iceberg operation failure, the system SHALL log an ERROR with the correct categorized error_code from the defined set.

### Property 17: Credential encryption round-trip

**Validates: Requirements 8.4**

*For any* AWS secret access key string, encrypting via KMS and decrypting SHALL produce the original string.

### Property 18: Parallel worker isolation

**Validates: Requirements 12.2, 12.4**

*For any* set of tables being loaded in parallel, a failure in one worker SHALL NOT affect the execution or result of any other worker.

### Property 19: Cost calculation consistency

**Validates: Requirements 13.3, 13.5**

*For any* data size and growth rate, the cost engine SHALL produce consistent projections where 12-month cost > 6-month cost > 3-month cost, and recalculation with a higher growth rate SHALL produce higher projections.

### Property 20: Custom structure validation

**Validates: Requirements 4.9**

*For any* user-defined custom structure, the validator SHALL detect incompatibilities with source data (invalid Iceberg types, missing required columns) and produce appropriate warnings.

---

## Error Handling

### Error Categories and Codes

| Error Code | Category | Retry | Description |
|------------|----------|-------|-------------|
| `GLUE_PERMISSION_DENIED` | Auth | No | Missing IAM permissions for Glue |
| `GLUE_REGISTRATION_FAILED` | Glue | Yes (3x) | Failed to register table in Glue |
| `ICEBERG_TABLE_CREATE_FAILED` | Iceberg | Yes (3x) | Table creation failed |
| `ICEBERG_APPEND_FAILED` | Iceberg | Yes (3x) | Data file append failed |
| `ICEBERG_S3_ACCESS_ERROR` | S3 | Yes (3x) | S3 bucket/object access denied |
| `ICEBERG_SCHEMA_EVOLUTION_FAILED` | Schema | No | Schema evolution operation failed |
| `SCHEMA_EVOLUTION_INCOMPATIBLE` | Schema | No | Incompatible type change detected |
| `S3_TABLES_API_FAILED` | S3 Tables | Yes (3x) | S3 Tables API call failed |
| `ATHENA_VERIFICATION_TIMEOUT` | Athena | No | Verification query timed out |
| `COST_CALCULATION_FAILED` | Cost | No | Cost analysis calculation error |
| `CUSTOM_STRUCTURE_INVALID` | Validation | No | User-defined structure is invalid |

### Retry Strategy

- **Retryable errors**: Exponential backoff with delays of 5s, 15s, 45s (3 attempts max)
- **Non-retryable errors**: Log error, mark table/shard as failed, continue with remaining tables
- **Glue throttling**: Respect `ThrottlingException` with jittered backoff (1-5s base)
- **Parallel workers**: Each worker retries independently; one worker's retry does not block others

### Failure Isolation

- Table-level failures do NOT fail the entire migration
- Each parallel worker handles its own errors independently
- A failure in one worker does not affect other workers
- The migration status is `failed` only if ALL tables fail or a critical infrastructure error occurs
- Partial completion is tracked via per-table shard records

---

## Testing Strategy

### Property-Based Tests (Hypothesis)

**Library**: Hypothesis (Python)
**Minimum iterations**: 100 per property test

Tests to implement:
1. Type mapper correctness (Property 1)
2. Nullability mapping (Property 2)
3. Partition transform selection — day() default (Property 3)
4. Sort order preservation (Property 4)
5. Recursive struct mapping with depth limit (Property 5)
6. Input validation for all config fields (Property 6)
7. Structure report completeness (Property 7)
8. Structure plan round-trip with custom definitions (Property 8)
9. Progress calculation with parallel workers (Property 9)
10. Row count validation — full and incremental (Property 10)
11. Schema evolution nullability (Property 11)
12. Type promotion validity — only valid promotions pass (Property 12)
13. State machine transitions with cancel preservation (Property 13)
14. Resume skips completed tables (Property 14)
15. Deduplication guard correctness (Property 15)
16. Error code categorization (Property 16)
17. Credential encryption round-trip (Property 17)
18. Parallel worker isolation (Property 18)
19. Cost calculation consistency (Property 19)
20. Custom structure validation (Property 20)

### Unit Tests

- Type mapper for all BQ types including edge cases
- Partition mapper with day() default and explicit granularities
- Credential provider — IAM Role path and access key path
- Deduplication guard — file detection and filtering
- Cost engine — setup, recurring, and projection calculations
- Schema evolution — valid promotions and incompatible detection
- Custom structure validation logic
- S3 Tables adapter namespace validation
- Parallel loader — worker pool sizing and semaphore behavior

### Integration Tests

- End-to-end migration with mocked AWS services
- Athena verification (optional flag behavior)
- Connection test with IAM Role and access keys
- Structure report generation with custom definitions
- Cost analysis with real pricing data
- Alembic migration up/down
- API endpoint authentication and authorization
- Cancel from pending_review preserves state

### Frontend Tests

- Migration wizard Iceberg destination selection
- Form validation for all Iceberg config fields (including IAM Role ARN)
- Structure review page — recommendations and custom structure editor
- Cost analysis tab rendering and growth rate adjustment
- Namespace naming input for S3 Tables
- Dataset-to-database mapping UI
- Progress display during parallel load stage
- Navigation state preservation in wizard
- Cancel/back from review preserves form data
