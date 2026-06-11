# Requirements Document

## Introduction

This document defines the requirements for adding Apache Iceberg as a new migration destination in DataMIQ. The feature enables users to migrate data from Google BigQuery to Iceberg tables on AWS. Two destination variants are supported: standard Apache Iceberg on general-purpose S3, and AWS S3 Tables (managed Iceberg). Both use AWS Glue Data Catalog for table registration, ensuring immediate queryability via Athena, Redshift Spectrum, and EMR.

## Glossary

- **System**: The DataMIQ migration platform backend and UI components
- **Iceberg**: Apache Iceberg, an open table format for large analytic datasets
- **S3_Tables**: AWS S3 Tables, a managed Iceberg-compatible storage service
- **Glue_Data_Catalog**: AWS Glue Data Catalog, a metadata store for table definitions
- **PyIceberg**: Python library for interacting with Apache Iceberg tables
- **Parser**: Component that maps BigQuery schemas to Iceberg-compatible schemas
- **Validator**: Component that verifies migrated data correctness post-migration
- **Migration_Wizard**: The UI workflow that guides users through migration configuration
- **Structure_Report**: The Iceberg Structure Design Report generated before load stage
- **TCO**: Total Cost of Ownership, comparing current and projected costs
- **Namespace**: An S3 Tables organizational unit for grouping related tables
- **IAM_Role**: AWS Identity and Access Management role used for cross-account or service access

## Requirements

### Requirement 1: Iceberg Destination Type Selection

**User Story:** As a data engineer, I want to choose between general-purpose S3 Iceberg and AWS S3 Tables (managed Iceberg) as my migration destination, so that I can select the storage option that best fits my operational needs.

#### Acceptance Criteria

1. WHEN the user reaches the target configuration step of the migration wizard, THE System SHALL display exactly two Iceberg destination options: "Apache Iceberg on S3" and "AWS S3 Tables (Managed Iceberg)".
2. WHEN the user selects "Apache Iceberg on S3", THE System SHALL require the user to provide an S3 bucket name (1 to 63 characters, matching S3 bucket naming rules), an S3 path prefix (0 to 512 characters), and an AWS region selected from a list of available AWS regions.
3. WHEN the user selects "AWS S3 Tables (Managed Iceberg)", THE System SHALL require the user to provide an S3 table bucket ARN (matching the pattern `arn:aws:s3tables:<region>:<account-id>:bucket/<bucket-name>`) and an AWS region selected from a list of available AWS regions.
4. THE System SHALL store the selected Iceberg destination type as either `iceberg_s3` or `iceberg_s3_tables` in the migration configuration.
5. WHEN the user selects either Iceberg destination option, THE System SHALL require the user to provide an AWS Glue Data Catalog database name (1 to 255 characters, matching the pattern `[a-z0-9_]+`) where Iceberg tables will be registered.
6. IF the user submits the target configuration without selecting a destination type or without providing all required fields for the selected type, THEN THE System SHALL display a validation error message indicating which fields are missing and prevent form submission.

---

### Requirement 2: AWS Glue Data Catalog Integration

**User Story:** As a data engineer, I want my migrated Iceberg tables registered in AWS Glue Data Catalog, so that they are immediately queryable via Athena, Redshift Spectrum, and EMR without additional manual steps.

#### Acceptance Criteria

1. WHEN the Iceberg load stage begins for a table, THE System SHALL check whether the specified Glue Data Catalog database exists and create it if it does not exist, using the AWS Glue CreateDatabase API.
2. WHEN creating or updating an Iceberg table in the Glue catalog, THE System SHALL register the table with the `table_type` property set to `ICEBERG` and the `metadata_location` property pointing to the Iceberg metadata file in S3.
3. WHERE the configuration option `enable_load_stage_verification` is set to `true` (default: `false`), THE System SHALL verify that each table is queryable after load by executing a `SELECT 1 FROM <database>.<table> LIMIT 1` query via the AWS Athena API and confirming a successful query execution state within 120 seconds. WHEN `enable_load_stage_verification` is `false`, THE System SHALL defer table verification to the post-migration validation step.
4. IF the Glue catalog database creation fails due to insufficient IAM permissions, THEN THE System SHALL log the error with error code `GLUE_PERMISSION_DENIED`, mark the migration as failed, and display an error message indicating the required IAM permissions (`glue:CreateDatabase`, `glue:CreateTable`, `glue:UpdateTable`, `glue:GetTable`, `glue:GetDatabase`).
5. IF `enable_load_stage_verification` is enabled and the Athena verification query fails or times out after 120 seconds, THEN THE System SHALL log a warning with error code `ATHENA_VERIFICATION_TIMEOUT`, mark the table verification status as `unverified`, and continue processing remaining tables without failing the overall migration.
6. THE System SHALL set the following Iceberg table properties when registering tables in Glue: `write.format.default` = `parquet`, `write.parquet.compression-codec` = `zstd`, `format-version` = `2`, and `write.metadata.delete-after-commit.enabled` = `true` with `write.metadata.previous-versions-max` = `3`.

---

### Requirement 3: BigQuery to Iceberg Schema Mapping

**User Story:** As a data engineer, I want BigQuery table schemas automatically mapped to Iceberg-compatible schemas, so that data types, partitioning, and clustering are preserved during migration.

#### Acceptance Criteria

1. WHEN the system creates an Iceberg table, THE System SHALL map each BigQuery column data type to an Iceberg type using the following mapping: STRING→string, BYTES→binary, INT64/INTEGER→long, FLOAT64/FLOAT→double, NUMERIC→decimal(38,9), BIGNUMERIC→decimal(38,18), BOOLEAN/BOOL→boolean, DATE→date, DATETIME→timestamp (without timezone), TIMESTAMP→timestamptz, TIME→time, GEOGRAPHY→string, JSON→string, STRUCT/RECORD→struct (with nested field mapping), ARRAY→list.
2. WHEN a BigQuery table has a time-based partitioning column (DATE, DATETIME, or TIMESTAMP type), THE System SHALL create an Iceberg partition spec using the `day()` transform as the default for all time-based columns, unless the BigQuery partition granularity explicitly specifies HOUR (in which case `hour()` SHALL be used), MONTH (in which case `month()` SHALL be used), or YEAR (in which case `year()` SHALL be used).
3. WHEN a BigQuery table has clustering columns defined, THE System SHALL apply Iceberg sort order using those columns in the same ordinal sequence as defined in BigQuery.
4. WHEN a BigQuery column has mode `REQUIRED`, THE System SHALL mark the corresponding Iceberg field as `required` (non-nullable). WHEN a BigQuery column has mode `NULLABLE` or `REPEATED`, THE System SHALL mark the field as `optional`.
5. IF a BigQuery column uses a data type not present in the mapping (unrecognized type), THEN THE System SHALL map it to Iceberg `string` type, log a warning with the original type name and column name, and continue processing.
6. WHEN a BigQuery table has nested STRUCT/RECORD fields, THE System SHALL recursively map all nested fields to Iceberg struct types preserving the full nesting hierarchy up to 15 levels deep.
7. IF a STRUCT/RECORD nesting exceeds 15 levels, THEN THE System SHALL flatten the remaining levels into a JSON string field, log a warning indicating the truncation depth, and continue processing.

---

### Requirement 4: Pre-Load Structure Review and Approval Checkpoint

**User Story:** As a data engineer, I want to review the recommended Iceberg table structure (schemas, partitioning, properties) and any target-account prerequisites before the system creates tables, so that I can verify the design is correct and ensure my AWS environment is ready before committing to the migration.

#### Acceptance Criteria

1. AFTER the source data assessment completes (or when the user triggers migration with an existing assessment) and BEFORE the load stage begins, THE System SHALL generate an **Iceberg Structure Design Report** and transition the migration to a `pending_review` status, pausing execution until the user explicitly approves.
2. THE Iceberg Structure Design Report SHALL include, for each source table:
   - Proposed Iceberg table name (derived from BQ table name, lowercased, special characters replaced with underscores)
   - Full column listing with: source BQ type, mapped Iceberg type, nullability, and any mapping warnings
   - Proposed partition spec (partition columns and transforms) with a rationale (e.g., "Partitioned by `day(event_date)` based on BQ DATE partitioning")
   - Proposed sort order (from BQ clustering columns)
   - Estimated row count and data size from assessment
   - Proposed table properties (format version, compression, metadata settings)
3. THE Report SHALL include a **Prerequisites Checklist** section listing all actions the user must complete on their target AWS account before proceeding, including:
   - IAM permissions required (specific policy actions for S3, Glue, Athena, and S3 Tables if applicable)
   - S3 bucket existence and write access confirmation
   - Glue Data Catalog database existence or permission to create it
   - Athena workgroup configuration (for post-load verification queries)
   - For S3 Tables: table bucket creation and namespace setup
   - Network/VPC considerations if applicable (e.g., VPC endpoints for S3/Glue)
4. THE Report SHALL include a **Warnings and Recommendations** section highlighting:
   - Any columns mapped to a fallback type (e.g., unrecognized BQ type → string)
   - Tables with no partitioning (recommendation to consider adding one for large tables > 1GB)
   - Tables with deeply nested STRUCTs that will be flattened
   - Potential naming conflicts (e.g., table names that conflict with Athena reserved words)
   - Estimated total storage footprint on S3
5. THE System SHALL present the report in the UI as a dedicated review page accessible from the migration detail view, with sections collapsible per table, and a global "Approve & Proceed" button and a "Request Changes" option.
6. WHEN the user clicks "Approve & Proceed", THE System SHALL transition the migration status from `pending_review` to `approved` and allow the load stage to begin (either immediately if the migration was running, or on next scheduled/manual start).
7. WHEN the user clicks "Request Changes", THE System SHALL allow the user to:
   - Override the partition spec for any table (select different column or transform)
   - Override the sort order for any table
   - Exclude specific tables from the migration
   - Add custom table properties (key-value pairs)
   - Change the Glue database name by mapping BigQuery datasets to specific Glue database names
   - Define the Iceberg table structure from scratch for any individual table (see AC8)
   - After making changes, re-generate the report for confirmation
8. WHEN the user is in the structure review step, THE System SHALL allow the user to create or select the Glue database name for each mapped BigQuery dataset, enabling explicit mapping of BQ datasets to specific Glue database names.
9. FOR any table in the structure review, THE System SHALL provide a "Define Custom Structure" option that allows the user to define the Iceberg table structure from scratch rather than using the system's recommendation. Custom structure definition SHALL include: table name, column definitions (name, Iceberg type, nullability), partition spec (columns and transforms), sort order (columns and direction), and table properties (key-value pairs). THE System SHALL validate that the user-defined structure is compatible with the source data (e.g., column count matches, types are valid Iceberg types) and display warnings for any potential data loss or incompatibility before approval.
10. THE System SHALL persist the approved structure design (including any user overrides or custom definitions) in the migration's `checkpoint_data` JSONB field under a key `iceberg_structure_plan`, so that the load stage uses the approved configuration rather than re-computing it.
11. IF the migration is resumed after a failure in the load stage, THE System SHALL use the previously approved structure plan from `checkpoint_data` without requiring re-approval, unless the user explicitly triggers a re-review.
12. THE System SHALL expose the structure report via an API endpoint (`GET /api/migrations/bq-iceberg/{id}/structure-report`) returning the full report as JSON, enabling programmatic review and approval (`POST /api/migrations/bq-iceberg/{id}/approve-structure`).
13. THE System SHALL include a "Download Report" option that exports the structure design as a PDF or Markdown file for offline review and stakeholder sharing.

---

### Requirement 5: Iceberg Table Creation and Data Loading

**User Story:** As a data engineer, I want the system to create Iceberg tables and load Parquet data files from S3 into them, so that my BigQuery data is available as queryable Iceberg tables after migration.

#### Acceptance Criteria

1. WHEN the load stage begins for a table, THE System SHALL create an Iceberg table using PyIceberg with the mapped schema, partition spec, and sort order derived from the BigQuery source table metadata captured during assessment.
2. WHEN loading data files into an Iceberg table, THE System SHALL use the Parquet data files already transferred to S3 during the transfer stage and register them as data files in the Iceberg table via PyIceberg's append operation.
3. WHEN the load stage completes for a single table, THE System SHALL update the migration shard record's `load_status` to `completed` and record the `load_completed_at` timestamp.
4. IF the Iceberg table already exists in the Glue catalog (e.g., during a retry or resume), THEN THE System SHALL check whether the existing table schema is compatible with the source schema and append new data without recreating the table.
5. WHEN resuming a failed load or retrying a table, THE System SHALL verify that no data files from a previous partial attempt are already registered in the Iceberg table before appending, using Iceberg snapshot metadata to detect and skip already-registered files, ensuring zero duplicate rows.
6. IF table creation fails due to an S3 access error, THEN THE System SHALL retry the operation up to 3 times with exponential backoff (delays of 5, 15, and 45 seconds) before marking the shard as failed with error code `ICEBERG_S3_ACCESS_ERROR`.
7. WHEN loading into an S3 Tables (managed Iceberg) destination, THE System SHALL use the user-provided table namespace name (confirmed during the structure review step) to create the namespace via the S3 Tables API (if not existing) and create the table within the S3 table bucket, then register it in Glue Data Catalog. THE System SHALL NOT create any namespace without explicit user approval, and all resource names and properties must be confirmed by the user before creation on the target.
8. THE System SHALL track load progress per table and update the migration's `progress_percentage` field after each table completes, calculated as `(completed_tables / total_tables) * 100` for the load stage.

---

### Requirement 6: Schema Evolution for Incremental Loads

**User Story:** As a data engineer, I want the system to handle schema changes (new columns) during incremental loads, so that my Iceberg tables evolve over time without breaking existing data or queries.

#### Acceptance Criteria

1. WHEN an incremental load detects that the source BigQuery table has new columns not present in the existing Iceberg table, THE System SHALL use Iceberg's schema evolution API to add the new columns to the Iceberg table before loading data.
2. WHEN adding new columns via schema evolution, THE System SHALL add them as `optional` (nullable) fields regardless of their BigQuery mode, to maintain backward compatibility with existing data files.
3. WHEN an incremental load detects that a source column's data type has changed in a compatible manner, THE System SHALL use Iceberg's type promotion to update the column type. The only valid type promotions are: `int` → `long`, `float` → `double`, and `decimal(P,S)` → `decimal(P',S)` where P' > P (scale must remain the same). Any other type change (including `long` → `decimal`) SHALL be treated as incompatible per AC4.
4. IF an incremental load detects an incompatible schema change (e.g., STRING changed to INTEGER, a column was removed from source, or a type change not in the valid promotion list), THEN THE System SHALL log an error with error code `SCHEMA_EVOLUTION_INCOMPATIBLE`, skip that table, mark the table's shard as failed, and continue processing other tables.
5. THE System SHALL log each schema evolution operation (column additions, type promotions) as an INFO-level migration log entry including the table name, column name, old type (if applicable), and new type.

---

### Requirement 7: Migration Orchestrator Integration

**User Story:** As a data engineer, I want Iceberg migrations to use the same orchestration framework (pathways, checkpointing, scheduling) as existing Redshift migrations, so that I get the same reliability and operational features.

#### Acceptance Criteria

1. THE System SHALL support all three existing transfer pathways (A: GCS→S3 via Storage Transfer, B: GCS→S3 via DataSync, C: Direct) for Iceberg migrations, reusing the existing export and transfer stage implementations.
2. WHEN creating an Iceberg migration, THE System SHALL store the migration with a `destination_type` field set to `iceberg_s3` or `iceberg_s3_tables`, while preserving all existing fields for source configuration, storage configuration, and scheduling.
3. THE System SHALL support checkpoint-based resume for Iceberg migrations: if the migration fails during the load stage, resuming SHALL skip tables whose shards have `load_status` = `completed` and retry only pending or failed tables.
4. THE System SHALL support all existing migration lifecycle operations for Iceberg migrations: start, pause, resume, cancel, and restart, using the extended status transitions (pending → running → pending_review → approved → running [load] → completed/failed/paused/cancelled).
5. WHEN the user cancels or navigates back from `pending_review` status, THE System SHALL preserve all existing migration configuration (connections, source settings, target settings, assessment data, and table selections) and allow the user to modify any previous step without requiring re-entry of unchanged settings.
6. WHEN an Iceberg migration completes, THE System SHALL record `total_rows_source`, `total_rows_target` (from Iceberg table snapshots), `total_bytes_transferred`, `duration_seconds`, and `last_run_at` in the migration metrics, consistent with existing Redshift migration metrics.
7. THE System SHALL support both full-load and incremental-load modes for Iceberg migrations, using the same `load_type` and `table_load_configs` configuration as existing migrations.

---

### Requirement 8: Connection and Configuration Model

**User Story:** As a data engineer, I want to configure Iceberg destination connections with all required credentials and settings, so that the system can create tables and write data to my chosen Iceberg destination.

#### Acceptance Criteria

1. THE System SHALL support a new connection type `iceberg` in the connections model, with `connection_params` storing: `destination_type` (iceberg_s3 or iceberg_s3_tables), `s3_bucket` or `table_bucket_arn`, `s3_path_prefix`, `aws_region`, `glue_database_name`, `aws_access_key_id`, and `aws_secret_access_key` (encrypted via KMS).
2. WHEN the user tests an Iceberg connection, THE System SHALL verify: (a) S3 bucket or table bucket accessibility by performing a HeadBucket or ListTables API call, (b) Glue Data Catalog access by calling GetDatabase, and (c) write permissions by creating and immediately deleting a test object at the configured S3 path prefix. The test SHALL complete within 30 seconds.
3. IF the connection test fails on any of the three verification steps, THEN THE System SHALL return a specific error message indicating which step failed and what IAM permissions are required.
4. THE System SHALL encrypt the `aws_secret_access_key` field using the existing KMS encryption service before storing it in the database, consistent with how existing AWS credentials are encrypted for Redshift migrations.
5. WHEN displaying an Iceberg connection in the UI, THE System SHALL show the connection status (connected/disconnected/error), destination type, S3 bucket or table bucket ARN, Glue database name, and AWS region, without exposing the secret access key value.
6. THE System SHALL support IAM Role ARN (`aws_role_arn`) as an alternative to access key credentials for Iceberg connections, enabling the system to assume the specified role via AWS STS AssumeRole for accessing S3, Glue, Athena, and S3 Tables services. WHEN IAM Role ARN is provided, `aws_access_key_id` and `aws_secret_access_key` are not required.

---

### Requirement 9: Migration Wizard UI for Iceberg Destination

**User Story:** As a data engineer, I want the migration creation wizard to guide me through configuring an Iceberg destination, so that I can set up migrations without needing to know all the technical details upfront.

#### Acceptance Criteria

1. WHEN the user starts creating a new migration, THE System SHALL present a destination type selector in the target configuration step with options: "Amazon Redshift" (existing) and "Apache Iceberg" (new), displayed as selectable cards with a brief description of each option (maximum 100 characters per description).
2. WHEN the user selects "Apache Iceberg" as the destination, THE System SHALL display a sub-selection for the Iceberg storage type ("Standard S3" or "AWS S3 Tables") and dynamically show the appropriate configuration fields for the selected sub-type.
3. WHEN the user completes the Iceberg target configuration, THE System SHALL display a summary panel showing: destination type, S3 bucket/table bucket, Glue database name, AWS region, number of source tables selected, and estimated table count to be created.
4. THE System SHALL validate all Iceberg configuration fields on the client side before submission: S3 bucket name format, Glue database name format (lowercase alphanumeric and underscores, 1-255 characters), AWS region from allowed list, and table bucket ARN format (when S3 Tables is selected).
5. WHEN the user navigates back from a later wizard step to the target configuration step, THE System SHALL preserve all previously entered Iceberg configuration values without requiring re-entry.

---

### Requirement 10: Validation and Post-Migration Verification

**User Story:** As a data engineer, I want the system to validate that migrated Iceberg tables contain the correct data, so that I can trust the migration results before using the tables in production queries.

#### Acceptance Criteria

1. WHEN an Iceberg migration completes, THE System SHALL automatically run row count validation by comparing the BigQuery source table row count (from the assessment data) against the Iceberg table row count (from the Iceberg table snapshot metadata) for each migrated table.
2. IF the row count difference between source and target for any table exceeds 0 rows for a full load (exact match required), THEN THE System SHALL mark that table's validation status as `failed` and log a WARNING with the table name, source count, and target count. FOR incremental loads, THE System SHALL verify that the target row count increased by at least the number of new rows exported in the current batch, comparing the delta between the previous and current Iceberg snapshot row counts against the exported row count.
3. WHEN the user manually triggers validation for a completed Iceberg migration, THE System SHALL execute an Athena query `SELECT COUNT(*) FROM <database>.<table>` for each table and compare against the source row count, completing within 300 seconds per table.
4. THE System SHALL store validation results per table including: table name, source row count, target row count, match status (passed/failed/skipped), and validation timestamp, accessible via the migration detail API endpoint.
5. IF validation cannot be performed because Athena query execution fails, THEN THE System SHALL mark the table validation as `skipped` with the error reason and log a WARNING, without marking the overall migration as failed.

---

### Requirement 11: Observability and Logging

**User Story:** As a data engineer, I want detailed logs and progress tracking for Iceberg migrations, so that I can monitor progress and troubleshoot issues.

#### Acceptance Criteria

1. THE System SHALL log each stage transition (export → transfer → load) for Iceberg migrations as INFO-level entries in the `migration_logs` table with the `stage` field set to `export`, `transfer`, or `load` respectively.
2. WHEN the load stage processes each table, THE System SHALL log: table creation start, schema mapping details (column count, partition spec), data file registration, and table creation completion, each as separate INFO-level log entries.
3. IF any Iceberg operation fails (table creation, data append, schema evolution, Glue registration), THEN THE System SHALL log an ERROR-level entry with: the operation name, table name, error message, and a categorized `error_code` (one of: `ICEBERG_TABLE_CREATE_FAILED`, `ICEBERG_APPEND_FAILED`, `ICEBERG_SCHEMA_EVOLUTION_FAILED`, `GLUE_REGISTRATION_FAILED`, `S3_TABLES_API_FAILED`).
4. THE System SHALL update the migration's `current_stage` field to `load` when the Iceberg load stage begins, enabling the existing status polling API to report accurate stage information to the UI.
5. WHEN the migration is in the load stage, THE System SHALL update `progress_percentage` after each table completes loading, so that the UI can display incremental progress rather than jumping from 0% to 100%.

---

### Requirement 12: Parallel Table Loading

**User Story:** As a data engineer, I want tables to be loaded in parallel during the Iceberg load stage, so that large migrations with many tables complete faster.

#### Acceptance Criteria

1. THE System SHALL support configurable parallelism for the Iceberg load stage with a default of 4 concurrent tables and a maximum of 16 concurrent tables.
2. WHEN loading tables in parallel, THE System SHALL ensure each parallel worker operates independently with its own error handling, so that a failure in one table does not affect the loading of other tables.
3. THE System SHALL account for parallel execution when tracking progress, updating `progress_percentage` as each individual table completes regardless of execution order.
4. IF one table fails during parallel loading, THEN THE System SHALL continue loading all other tables unaffected, marking only the failed table's shard as failed.
5. THE System SHALL allow the user to configure the parallelism level (number of concurrent tables) in the migration settings, with a minimum of 1 and a maximum of 16.

---

### Requirement 13: Pre-Migration Cost Analysis

**User Story:** As a data engineer, I want a detailed cost analysis of the Iceberg setup and projected recurring costs before migration begins, so that I can make informed decisions and get stakeholder approval.

#### Acceptance Criteria

1. WHEN the structure review stage is reached, THE System SHALL generate a cost analysis report and present it alongside the Iceberg Structure Design Report in a dedicated "Cost Analysis" tab or section.
2. THE Cost Analysis Report SHALL include: one-time setup costs (S3 storage provisioning, Glue API calls for table creation, data transfer costs), recurring monthly costs (S3 storage, Glue Data Catalog requests, Athena query costs, S3 Tables costs if applicable), and projected costs at 3-month, 6-month, and 12-month horizons based on estimated data growth.
3. THE System SHALL calculate storage costs based on the assessed data size with ZSTD compression ratio estimates (using a range of 3:1 to 5:1 for Parquet format) and present both optimistic and conservative projections.
4. WHERE current BigQuery cost data is available, THE System SHALL provide a TCO comparison between current BigQuery costs and projected Iceberg/S3 costs, highlighting potential savings or additional costs.
5. THE System SHALL allow the user to adjust growth rate assumptions and re-calculate cost projections dynamically within the cost analysis view.
6. THE System SHALL include the cost analysis in the downloadable report (PDF or Markdown format) alongside the structure design report.
7. THE System SHALL present all cost information BEFORE actual implementation begins, ensuring the user can make an informed decision during the `pending_review` stage.

---

### Non-Functional Requirements

#### Performance
- Iceberg table creation should complete within 30 seconds per table for tables with up to 500 columns
- Data file registration (append) should complete within 60 seconds per table for up to 1000 data files
- The overall load stage should not be more than 20% slower than the equivalent Redshift COPY operation for the same data volume

#### Security
- All AWS credentials stored encrypted via KMS (existing pattern)
- IAM role-based access preferred over access keys where possible
- No credentials logged in migration logs
- Workspace isolation enforced on all Iceberg migration resources

#### Reliability
- Checkpoint-based resume for all stages
- Retry with exponential backoff for transient AWS API failures
- Graceful handling of Glue API throttling (respect rate limits)
- Migration should not leave orphaned data files in S3 on failure (best effort cleanup)

#### Compatibility
- Iceberg format version 2 (supports row-level deletes, required for future features)
- Parquet as the only supported data file format
- ZSTD compression as default (best compression ratio for analytical workloads)
- Tables must be compatible with Athena engine version 3, Spark 3.x, and Trino 4xx
