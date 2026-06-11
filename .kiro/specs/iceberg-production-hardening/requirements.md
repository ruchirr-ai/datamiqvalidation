# Requirements Document

## Introduction

This document defines the requirements for production hardening of the BigQuery-to-Iceberg migration feature in DataMIQ. These enhancements address real-world operational issues discovered during multi-tenant data lakehouse deployments using AWS S3 Tables. The changes span S3 Tables maintenance configuration, Glue catalog validation, compaction strategy selection, Lake Formation prerequisites, API throttling, hidden partitioning, and incremental load watermarking.

## Glossary

- **System**: The DataMIQ migration platform backend and UI components
- **S3_Tables_API**: The AWS Boto3 S3Tables client API for managing table maintenance and configuration
- **Maintenance_Configuration**: S3 Tables settings for compaction and snapshot management applied via `put_table_maintenance_configuration()`
- **Compaction**: The process of merging small data files into larger files to improve query performance
- **Binpack**: A compaction strategy that combines small files into target-sized files without reordering data
- **Sort_Compaction**: A compaction strategy that combines files and sorts data by specified columns
- **Z_Order_Compaction**: A compaction strategy that interleaves multiple sort columns for multi-dimensional query optimization
- **Snapshot_Management**: S3 Tables configuration controlling how many snapshots are retained and for how long
- **Glue_ID**: The catalog identifier required by S3 Tables in the format `{account_id}:s3tablescatalog/{bucket-name}`
- **Lake_Formation**: AWS Lake Formation, a service for managing fine-grained data lake permissions
- **Data_Location_Permission**: A Lake Formation permission granting access to a specific S3 or S3 Tables storage location
- **Hidden_Partitioning**: Iceberg partition transforms (e.g., `days()`, `hours()`) that enable automatic partition pruning without requiring explicit partition filters in queries
- **File_Time_Watermark**: A monotonically increasing timestamp tracking the maximum `file_modification_time` processed per table for incremental loads
- **Throttling**: Rate limiting applied by the S3 Tables API when concurrent requests exceed service capacity
- **Structure_Report**: The Iceberg Structure Design Report generated before the load stage
- **Migration_Config**: The persisted migration configuration stored in the `checkpoint_data` JSONB field

## Requirements

### Requirement 1: S3 Tables Maintenance Configuration After Table Creation

**User Story:** As a data engineer, I want the system to configure S3 Tables maintenance settings (compaction and snapshot management) immediately after creating each Iceberg table, so that my tables are automatically optimized without manual AWS console intervention.

#### Acceptance Criteria

1. WHEN the System creates an Iceberg table on an S3 Tables destination, THE System SHALL call the S3 Tables API `put_table_maintenance_configuration()` via Boto3 immediately after successful table creation, configuring both `icebergCompaction` and `icebergSnapshotManagement` settings.
2. THE System SHALL configure `icebergCompaction` with `isEnabled` set to `true` and `targetFileSizeMB` set to the user-configured value (integer between 64 and 512, default 512).
3. THE System SHALL configure `icebergSnapshotManagement` with `isEnabled` set to `true`, `minSnapshotsToKeep` set to the user-configured value (integer, default 30), and `maxSnapshotAgeHours` set to the user-configured value (integer, default 720).
4. THE System SHALL configure the compaction strategy as one of: `binpack` (default), `sort`, or `z-order`, based on the per-table configuration set during structure review.
5. WHEN the compaction strategy is `sort` or `z-order`, THE System SHALL include the specified sort columns in the maintenance configuration, using the column names validated against the table schema.
6. IF the `put_table_maintenance_configuration()` call fails on the first attempt, THEN THE System SHALL immediately log a WARNING-level entry with the error details and retry up to 3 times with exponential backoff (delays of 2, 6, and 18 seconds). IF all retries are exhausted and the error cannot be logged, THEN THE System SHALL fail the entire table creation. IF retries are exhausted but error logging succeeds, THE System SHALL log an ERROR with error code `S3_TABLES_MAINTENANCE_CONFIG_FAILED` and continue the migration without failing the table creation.
7. THE System SHALL NOT attempt to set maintenance-related table properties via PyIceberg table properties for S3 Tables destinations, as S3 Tables silently ignores properties set through the Iceberg catalog interface.
8. THE System SHALL log an INFO-level entry for each successful maintenance configuration call, including the table name, compaction strategy, target file size, and snapshot retention settings.

---

### Requirement 2: Glue Catalog glue.id Validation

**User Story:** As a data engineer, I want the system to validate and store the correct `glue.id` format for S3 Tables catalogs, so that PyIceberg can connect to the correct Glue sub-catalog and table operations succeed on the first attempt.

#### Acceptance Criteria

1. THE System SHALL store the `glue.id` value in the migration configuration for S3 Tables destinations, using the format `{account_id}:s3tablescatalog/{bucket-name}` where `account_id` is the 12-digit AWS account ID and `bucket-name` is the S3 Tables bucket name extracted from the table bucket ARN.
2. WHEN the user tests an S3 Tables connection, THE System SHALL validate that the `glue.id` value matches the pattern `^\d{12}:s3tablescatalog/[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$` and return a specific error message if the format is invalid.
3. THE System SHALL derive the `glue.id` automatically from the provided table bucket ARN (`arn:aws:s3tables:<region>:<account-id>:bucket/<bucket-name>`) by extracting the account ID and bucket name components.
4. THE Structure_Report prerequisites checklist SHALL include the correct `glue.id` value as a reference item, displaying the derived catalog identifier so the user can verify it matches their AWS environment.
5. WHEN initializing the PyIceberg GlueCatalog for S3 Tables operations, THE System SHALL pass the validated `glue.id` as the catalog `warehouse` property, ensuring the catalog connects to the S3 Tables sub-catalog rather than the default Glue catalog.
6. IF the `glue.id` validation fails during connection testing, THEN THE System SHALL return an error message stating: "Invalid glue.id format. Expected: {account_id}:s3tablescatalog/{bucket-name}. Verify your table bucket ARN is correct."

---

### Requirement 3: Compaction Strategy Selection in Structure Review

**User Story:** As a data engineer, I want to select a compaction strategy (binpack, sort, or z-order) for each table during structure review, so that I can optimize query performance based on my workload patterns.

#### Acceptance Criteria

1. WHEN generating the Iceberg Structure Design Report for an S3 Tables destination, THE System SHALL include a "Compaction Strategy" field for each table, defaulting to `binpack`.
2. WHEN a source BigQuery table has clustering columns defined, THE System SHALL recommend `sort` compaction with those clustering columns as the sort columns, displayed as a suggestion the user can accept or override.
3. THE System SHALL allow the user to select one of three compaction strategies per table during structure review: `binpack`, `sort`, or `z-order`.
4. WHEN the user selects `sort` or `z-order` compaction, THE System SHALL require the user to specify one or more sort columns from the table schema, validating that each specified column exists in the table schema.
5. THE System SHALL persist the per-table compaction strategy and sort columns in the approved structure plan within `checkpoint_data`, under the key `compaction_config` for each table entry. IF the persistence step fails, THEN THE System SHALL block the user from proceeding to the load phase until persistence succeeds, displaying an error message indicating the failure.
6. WHEN the user does not explicitly select a compaction strategy, THE System SHALL apply the default `binpack` strategy for that table.
7. THE System SHALL display a brief explanation for each strategy option: "Binpack: Combines small files without reordering (best for append-heavy workloads)", "Sort: Reorders data by specified columns (best for range queries on specific columns)", "Z-Order: Interleaves multiple columns (best for queries filtering on multiple columns simultaneously)".

---

### Requirement 4: Maintenance Configuration UI

**User Story:** As a data engineer, I want to configure S3 Tables maintenance parameters (target file size, snapshot retention) through the migration wizard UI, so that I can tune table optimization settings without using the AWS console.

#### Acceptance Criteria

1. WHEN the user configures an S3 Tables destination in the migration wizard, THE System SHALL display a "Table Maintenance Settings" section with configurable fields for: target file size in MB, minimum snapshots to keep, and maximum snapshot age in hours.
2. THE System SHALL set default values for maintenance settings: target file size = 512 MB, minimum snapshots to keep = 30, maximum snapshot age = 720 hours.
3. THE System SHALL validate that target file size is an integer between 64 and 512 (inclusive), minimum snapshots to keep is a positive integer, and maximum snapshot age is a positive integer representing hours.
4. IF the user enters a target file size value of 0 or leaves the field empty, THEN THE System SHALL display a validation error: "Target file size is required." IF the user enters a non-zero value outside the range 64-512, THEN THE System SHALL display a validation error: "Target file size must be between 64 MB and 512 MB."
5. THE System SHALL display the "Table Maintenance Settings" section only when the selected destination type is `iceberg_s3_tables`, hiding it for standard S3 Iceberg destinations.
6. THE System SHALL persist the maintenance configuration values in the migration configuration and include them in the structure report for user confirmation before table creation.

---

### Requirement 5: Lake Formation Prerequisites for S3 Tables

**User Story:** As a data engineer, I want the structure report to list all Lake Formation permissions required for S3 Tables migrations, so that I can configure my AWS environment correctly before the migration begins.

#### Acceptance Criteria

1. WHEN generating the Structure_Report prerequisites checklist for an S3 Tables destination, THE System SHALL include a "Lake Formation Permissions" section listing all required permissions.
2. THE Lake Formation Permissions section SHALL include: data location permission on the S3 Tables bucket ARN (format: `arn:aws:s3tables:<region>:<account-id>:bucket/<bucket-name>`), noting that this uses the bucket ARN and not an `s3://` path.
3. THE Lake Formation Permissions section SHALL include: `DESCRIBE` permission on the Glue catalog database, and `SELECT` permission on the Glue catalog tables within that database.
4. THE Lake Formation Permissions section SHALL include: `lakeformation:GetDataAccess` IAM permission required on the execution role that performs the migration.
5. THE Lake Formation Permissions section SHALL include: Lake Formation permissions granted to the Glue execution role (the role used by the Glue catalog to access S3 Tables data).
6. THE System SHALL display the Lake Formation prerequisites section only for S3 Tables destinations, omitting it for standard S3 Iceberg destinations.
7. THE System SHALL format each Lake Formation prerequisite as an actionable checklist item with the specific ARN or permission string the user needs to configure.

---

### Requirement 6: S3 Tables API Concurrency Throttling

**User Story:** As a data engineer, I want the system to handle S3 Tables API rate limits gracefully with appropriate concurrency defaults and retry logic, so that migrations do not fail due to throttling errors.

#### Acceptance Criteria

1. WHEN the migration destination is `iceberg_s3_tables`, THE System SHALL set the default parallelism for the load stage to 4 concurrent tables (instead of the general default of 4 for standard S3 Iceberg, with a maximum of 8 for S3 Tables).
2. WHEN the user configures parallelism greater than 8 for an S3 Tables destination, THE System SHALL display a warning message: "S3 Tables API has lower concurrency limits than standard S3. Parallelism above 8 may cause throttling errors and slower overall throughput."
3. WHEN the S3 Tables API returns an HTTP 429 status code or a `SlowDown` error, THE System SHALL retry the operation with exponential backoff starting at 1 second, doubling on each retry, up to a maximum of 5 retries with a maximum delay of 32 seconds.
4. THE System SHALL distinguish S3 Tables API throttling errors (HTTP 429, SlowDown) from general S3 access errors (HTTP 403, 404, 500) by using distinct error codes: `S3_TABLES_THROTTLED` for throttling and `S3_TABLES_API_FAILED` for other S3 Tables errors.
5. WHEN an S3 Tables throttling error occurs, THE System SHALL log a WARNING-level entry with the table name, operation attempted, retry count, and backoff delay, without marking the table as failed until all retries are exhausted.
6. IF all 5 retries for a throttled S3 Tables API call are exhausted, THEN THE System SHALL mark the table shard as failed with error code `S3_TABLES_THROTTLED` and continue processing other tables.
7. THE System SHALL enforce a maximum parallelism of 8 specifically for S3 Tables destinations only, preventing the user from configuring a value higher than 8 for `iceberg_s3_tables`. Standard S3 Iceberg destinations (`iceberg_s3`) SHALL continue to support parallelism up to 16.

---

### Requirement 7: Hidden Partitioning Enforcement

**User Story:** As a data engineer, I want the system to use Iceberg hidden partitioning transforms for all time-based partition columns, so that queries benefit from automatic partition pruning without requiring explicit partition filter predicates.

#### Acceptance Criteria

1. WHEN creating partition specs for Iceberg tables, THE System SHALL use hidden partitioning transforms (`days()`, `hours()`, `months()`, `years()`) on timestamp and date columns rather than creating identity partitions on raw column values.
2. WHEN a BigQuery table has DATE partitioning, THE System SHALL apply the `days()` transform to the partition column in the Iceberg partition spec by default.
3. WHEN a BigQuery table has DATETIME or TIMESTAMP partitioning with HOUR granularity, THE System SHALL apply the `hours()` transform to the partition column. IF the system detects a mismatch between the specified granularity and the applied transform (e.g., `days()` applied when HOUR was specified), THEN THE System SHALL fail the partition spec creation with an error indicating the transform-granularity mismatch.
4. WHEN a BigQuery table has DATETIME or TIMESTAMP partitioning with MONTH granularity, THE System SHALL apply the `months()` transform to the partition column.
5. WHEN a BigQuery table has DATETIME or TIMESTAMP partitioning with YEAR granularity, THE System SHALL apply the `years()` transform to the partition column.
6. THE System SHALL display the partition transform in the structure report as a human-readable description (e.g., "Partitioned by days(event_timestamp)") so the user understands that hidden partitioning is being applied.
7. THE System SHALL NOT create identity partitions on time-based columns, as identity partitions require explicit partition filters in queries and do not benefit from automatic partition pruning.

---

### Requirement 8: Incremental Load File-Time Watermark

**User Story:** As a data engineer, I want the system to track the maximum file modification time per table and only process newer files during incremental loads, so that re-processing is minimized and incremental loads are efficient.

#### Acceptance Criteria

1. WHEN an incremental load completes for a table, THE System SHALL record the maximum `file_modification_time` across all processed data files as the watermark for that table in the migration's `checkpoint_data` under the key `file_time_watermarks`.
2. WHEN starting an incremental load for a table that has a previously recorded watermark, THE System SHALL filter the source data files to include only files with `file_modification_time` strictly greater than the stored watermark value.
3. THE System SHALL update the watermark monotonically: a new watermark value SHALL only be written if it is strictly greater than the existing watermark value for that table.
4. IF an incremental load fails partway through processing, THEN THE System SHALL NOT update the watermark, preserving the previous watermark value so that the next retry reprocesses all files from the last successful watermark.
5. WHEN no files are discovered with `file_modification_time` greater than the stored watermark during the file discovery phase, THE System SHALL log an INFO-level message indicating no new files to process for that table and mark the table's incremental load as completed with zero files appended, regardless of any subsequent processing outcome.
6. THE System SHALL store watermark values as ISO 8601 UTC timestamps with second precision (e.g., `2024-01-15T10:30:00Z`) in the `checkpoint_data` JSONB field.
7. WHEN the user triggers a full reload for a table that has an existing watermark, THE System SHALL reset the watermark for that table to null, causing the next load to process all available files regardless of modification time.

