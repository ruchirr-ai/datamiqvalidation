# Implementation Plan: Iceberg Production Hardening

## Overview

This plan enhances the existing BQ-to-Iceberg migration feature with production hardening: S3 Tables maintenance configuration, Glue catalog validation, compaction strategy selection, Lake Formation prerequisites, API throttling, hidden partitioning enforcement, and incremental load watermarking. Tasks are ordered by dependency — foundational services first, then API layer, then frontend.

## Tasks

- [x] 1. Add error codes and validator functions
  - [x] 1.1 Add new error codes to error_codes.py
    - Add `S3_TABLES_THROTTLED`, `S3_TABLES_MAINTENANCE_CONFIG_FAILED`, `GLUE_ID_INVALID`, and `COMPACTION_STRATEGY_INVALID` to the `ErrorCode` enum in `backend/services/bq_iceberg_migration/error_codes.py`
    - _Requirements: 6.4, 1.6, 2.2, 3.4_

  - [x] 1.2 Implement glue.id validation in validators.py
    - Add `_GLUE_ID_PATTERN` regex and `validate_glue_id()` function to `backend/services/bq_iceberg_migration/validators.py`
    - Pattern: `^\d{12}:s3tablescatalog/[a-z0-9][a-z0-9.\-]{1,61}[a-z0-9]$`
    - Return `(is_valid, error_message)` tuple with specific error message on failure
    - _Requirements: 2.2, 2.6_

  - [x] 1.3 Implement maintenance config validation in validators.py
    - Add `validate_maintenance_config(target_file_size_mb, min_snapshots_to_keep, max_snapshot_age_hours)` to `backend/services/bq_iceberg_migration/validators.py`
    - Validate target_file_size_mb in [64, 512], min_snapshots_to_keep > 0, max_snapshot_age_hours > 0
    - _Requirements: 4.3, 4.4_

  - [x] 1.4 Implement compaction strategy validation in validators.py
    - Add `validate_compaction_strategy(strategy, sort_columns, table_schema_columns)` to `backend/services/bq_iceberg_migration/validators.py`
    - Validate strategy in {binpack, sort, z-order}, sort_columns non-empty for sort/z-order, all sort columns exist in schema
    - _Requirements: 1.5, 3.4_

  - [x] 1.5 Implement S3 Tables parallelism validation in validators.py
    - Add `validate_s3_tables_parallelism(parallelism)` to `backend/services/bq_iceberg_migration/validators.py`
    - Accept values in [1, 8], reject values outside that range
    - _Requirements: 6.1, 6.7_

  - [x] 1.6 Write property tests for validators (Properties 2, 4, 6, 7)
    - **Property 2: Compaction sort column validation**
    - **Property 4: glue.id validation rejects invalid formats**
    - **Property 6: Maintenance config validation**
    - **Property 7: S3 Tables parallelism enforcement**
    - Test file: `backend/tests/property/test_iceberg_production_hardening.py`
    - Use Hypothesis with min 100 examples per property
    - **Validates: Requirements 1.5, 2.2, 2.6, 3.4, 4.3, 4.4, 6.1, 6.7**

  - [x] 1.7 Write unit tests for validators
    - Test file: `backend/tests/unit/test_iceberg_production_hardening.py`
    - Test `validate_glue_id` with valid/invalid formats, edge cases
    - Test `validate_maintenance_config` boundary values (64, 512, 0, -1)
    - Test `validate_compaction_strategy` with missing sort columns, invalid strategy names
    - Test `validate_s3_tables_parallelism` with boundary values (0, 1, 8, 9, 16)
    - _Requirements: 2.2, 2.6, 4.3, 4.4, 6.1, 6.7_

- [ ] 2. Implement S3TablesAdapter maintenance configuration
  - [x] 2.1 Add MaintenanceConfig dataclass and derive_glue_id to s3_tables_adapter.py
    - Add `MaintenanceConfig` dataclass with fields: compaction_enabled, target_file_size_mb, compaction_strategy, sort_columns, snapshot_management_enabled, min_snapshots_to_keep, max_snapshot_age_hours
    - Add static method `derive_glue_id(table_bucket_arn)` that extracts account_id and bucket_name from ARN format `arn:aws:s3tables:<region>:<account-id>:bucket/<bucket-name>` and returns `{account_id}:s3tablescatalog/{bucket-name}`
    - File: `backend/services/bq_iceberg_migration/s3_tables_adapter.py`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.3_

  - [x] 2.2 Add configure_maintenance method to S3TablesAdapter
    - Implement `configure_maintenance(namespace, table_name, config)` that calls `put_table_maintenance_configuration()` via Boto3
    - Implement `_build_maintenance_payload(config)` to construct the API payload
    - Retry up to 3 times with exponential backoff (2s, 6s, 18s)
    - Log WARNING on each retry, ERROR with `S3_TABLES_MAINTENANCE_CONFIG_FAILED` on exhaustion
    - Return True on success, False on failure (non-fatal to table creation)
    - Log INFO on success with table name, strategy, file size, snapshot settings
    - _Requirements: 1.1, 1.6, 1.7, 1.8_

  - [x] 2.3 Write property tests for S3TablesAdapter (Properties 1, 3)
    - **Property 1: Maintenance configuration payload correctness**
    - **Property 3: glue.id derivation round-trip**
    - Test file: `backend/tests/property/test_iceberg_production_hardening.py`
    - Use Hypothesis with custom strategies for valid ARNs and maintenance configs
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3**

  - [x] 2.4 Write unit tests for S3TablesAdapter maintenance
    - Test `configure_maintenance` retry behavior (mock Boto3 failures)
    - Test `configure_maintenance` does not fail table creation on error
    - Test `_build_maintenance_payload` produces correct API shape for each strategy
    - Test `derive_glue_id` with valid ARNs and invalid ARN formats
    - Test no PyIceberg maintenance properties set for S3 Tables
    - _Requirements: 1.6, 1.7, 1.8, 2.1, 2.3_

- [ ] 3. Implement hidden partitioning enforcement
  - [x] 3.1 Verify and enforce hidden partitioning in partition_mapper.py
    - Verify `PartitionSpecMapper` in `backend/services/bq_iceberg_migration/partition_mapper.py` uses `TRANSFORM_MAP` for all time-based columns
    - Ensure `map_partition_spec()` always uses transform functions (day, hour, month, year) and never creates identity partitions
    - Add explicit guard: raise error if identity partition would be created on a time column
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.7_

  - [x] 3.2 Write property tests for partition mapping (Properties 9, 10)
    - **Property 9: Hidden partition transform mapping**
    - **Property 10: Partition transform display format**
    - Test file: `backend/tests/property/test_iceberg_production_hardening.py`
    - Use `st.sampled_from(["DATE", "DATETIME", "TIMESTAMP"])` and `st.sampled_from([None, "HOUR", "DAY", "MONTH", "YEAR"])`
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7**

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Implement IcebergLoader throttle retry and watermark logic
  - [x] 5.1 Add throttle retry logic to iceberg_loader.py
    - Add `S3_TABLES_THROTTLE_MAX_RETRIES = 5`, `S3_TABLES_THROTTLE_BASE_DELAY = 1.0`, `S3_TABLES_THROTTLE_MAX_DELAY = 32.0` constants to `ParallelIcebergLoader`
    - Implement `_retry_with_throttle_backoff(operation, table_name, operation_name)` with exponential backoff (1s, 2s, 4s, 8s, 16s)
    - Distinguish HTTP 429 / SlowDown from other errors using `S3_TABLES_THROTTLED` vs `S3_TABLES_API_FAILED`
    - Log WARNING on each throttle retry with table_name, operation, retry count, backoff delay
    - Mark table failed with `S3_TABLES_THROTTLED` after 5 retries exhausted
    - File: `backend/services/bq_iceberg_migration/iceberg_loader.py`
    - _Requirements: 6.3, 6.4, 6.5, 6.6_

  - [x] 5.2 Add maintenance config call after table creation in iceberg_loader.py
    - Modify `_load_single_table_s3_tables()` to accept `maintenance_config` parameter
    - Call `s3_tables_adapter.configure_maintenance()` immediately after successful table creation
    - Continue load even if maintenance config fails (non-fatal)
    - _Requirements: 1.1, 1.6_

  - [x] 5.3 Implement file-time watermark logic in iceberg_loader.py
    - Add `_compute_file_time_watermark(processed_files)` — returns max file_modification_time as ISO 8601 UTC string
    - Add `_filter_files_by_watermark(files, watermark)` — returns files with modification_time > watermark, all files if watermark is None
    - Integrate watermark read from `checkpoint_data["file_time_watermarks"][table_name]` at start of incremental load
    - Update watermark only on full success (not on partial failure)
    - Log INFO when no new files found, mark completed with zero files
    - Store watermark as ISO 8601 UTC with second precision
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [x] 5.4 Write property tests for watermark logic (Properties 11, 12, 13, 14)
    - **Property 11: File-time watermark filtering**
    - **Property 12: Watermark monotonicity**
    - **Property 13: Watermark preservation on failure**
    - **Property 14: Watermark format**
    - Test file: `backend/tests/property/test_iceberg_production_hardening.py`
    - Use `st.lists(st.datetimes())` for file times, `st.datetimes(timezones=st.just(timezone.utc))` for watermarks
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.6**

  - [x] 5.5 Write property test for error code classification (Property 8)
    - **Property 8: S3 Tables error code classification**
    - Test file: `backend/tests/property/test_iceberg_production_hardening.py`
    - Use `st.sampled_from([429, 403, 404, 500])` for HTTP status, `st.sampled_from(["SlowDown", "AccessDenied", "NoSuchKey", "InternalError"])` for error codes
    - **Validates: Requirements 6.4**

  - [x] 5.6 Write unit tests for throttle retry and watermark
    - Test throttle retry backoff sequence (1s, 2s, 4s, 8s, 16s)
    - Test throttle exhausted marks table failed with S3_TABLES_THROTTLED
    - Test maintenance config called after table creation
    - Test maintenance config failure does not fail table creation
    - Test watermark not updated on partial failure
    - Test no new files logs INFO and returns zero files
    - Test full reload resets watermark to null
    - _Requirements: 6.3, 6.5, 6.6, 8.4, 8.5, 8.7_

- [ ] 6. Implement structure report enhancements
  - [x] 6.1 Add compaction strategy to structure report
    - Modify `_generate_table_report()` in `backend/services/bq_iceberg_migration/structure_report.py` to include `compaction_config` field per table
    - Default to `binpack`, recommend `sort` when source has clustering columns
    - Add `COMPACTION_STRATEGY_DESCRIPTIONS` dict with descriptions for each strategy
    - _Requirements: 3.1, 3.2, 3.7_

  - [x] 6.2 Add Lake Formation prerequisites to structure report
    - Modify `_generate_prerequisites()` to include Lake Formation section for S3 Tables destinations
    - Implement `_generate_lake_formation_prerequisites(table_bucket_arn, glue_database, aws_region, account_id)` returning actionable checklist items
    - Include: data location permission on bucket ARN, DESCRIBE on Glue database, SELECT on Glue tables, lakeformation:GetDataAccess IAM permission, Glue execution role permissions
    - Include derived glue.id in prerequisites
    - Only show for S3 Tables destinations
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 2.4_

  - [x] 6.3 Write property test for structure report (Properties 5, 15)
    - **Property 5: Structure report compaction defaults and recommendations**
    - **Property 15: Lake Formation prerequisites contain specific ARNs**
    - Test file: `backend/tests/property/test_iceberg_production_hardening.py`
    - Use custom strategies for table metadata with/without clustering and valid bucket ARNs
    - **Validates: Requirements 3.1, 3.2, 5.2, 5.3, 5.4, 5.7**

  - [x] 6.4 Write unit tests for structure report enhancements
    - Test compaction strategy persistence in checkpoint_data
    - Test default binpack when no selection made
    - Test strategy descriptions returned in response
    - Test Lake Formation section only shown for S3 Tables
    - Test glue.id included in prerequisites
    - _Requirements: 3.5, 3.6, 3.7, 5.6, 2.4_

- [x] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Update API router with new request models and fields
  - [x] 8.1 Add Pydantic request models to bq_iceberg_migration router
    - Add `MaintenanceConfigRequest` model with fields: target_file_size_mb (64-512, default 512), min_snapshots_to_keep (>0, default 30), max_snapshot_age_hours (>0, default 720)
    - Add `CompactionConfigRequest` model with fields: strategy (binpack|sort|z-order, default binpack), sort_columns (list[str])
    - File: `backend/routers/bq_iceberg_migration.py`
    - _Requirements: 4.1, 4.2, 4.3, 3.3_

  - [x] 8.2 Modify CreateIcebergMigrationRequest to include maintenance_config
    - Add optional `maintenance_config: Optional[MaintenanceConfigRequest]` field to the existing create migration request model
    - Wire maintenance config through to the loader service
    - Validate maintenance config using `validate_maintenance_config()` before proceeding
    - _Requirements: 4.1, 4.6_

  - [x] 8.3 Modify StructureApprovalRequest to include per-table compaction config
    - Add optional `table_compaction_configs: Optional[Dict[str, CompactionConfigRequest]]` field
    - Validate each table's compaction config using `validate_compaction_strategy()` against the table schema
    - Persist compaction configs in `checkpoint_data` under each table's `compaction_config` key
    - _Requirements: 3.3, 3.4, 3.5_

  - [x] 8.4 Add parallelism validation for S3 Tables in API
    - Call `validate_s3_tables_parallelism()` when destination is `iceberg_s3_tables`
    - Return warning message when parallelism > 8
    - Enforce max 8 for S3 Tables, allow up to 16 for standard S3 Iceberg
    - _Requirements: 6.1, 6.2, 6.7_

  - [x] 8.5 Write unit tests for API router changes
    - Test create migration with valid maintenance config
    - Test create migration with invalid maintenance config (out of range values)
    - Test structure approval with per-table compaction configs
    - Test compaction config validation rejects invalid sort columns
    - Test parallelism warning for S3 Tables above 8
    - Test parallelism rejection above 8 for S3 Tables
    - Test maintenance settings hidden for standard S3 destinations
    - _Requirements: 4.3, 4.4, 4.5, 3.4, 6.2, 6.7_

- [x] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Implement frontend components
  - [x] 10.1 Add TypeScript types for maintenance and compaction config
    - Add `MaintenanceConfig`, `CompactionConfig`, `CompactionStrategy` types to `frontend/src/types/bqIceberg.ts`
    - Add `LakeFormationPrerequisite` type for structure report display
    - _Requirements: 4.1, 3.3_

  - [x] 10.2 Implement MaintenanceConfigForm component
    - Create form component in `frontend/src/components/migrations/` with fields: target file size (64-512), min snapshots to keep, max snapshot age hours
    - Set defaults: 512, 30, 720
    - Show only when destination type is `iceberg_s3_tables`
    - Add client-side validation with error messages matching Req 4.4
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 10.3 Implement CompactionStrategySelector component
    - Create selector component in `frontend/src/components/migrations/` with dropdown for binpack/sort/z-order
    - Show sort columns input when strategy is sort or z-order
    - Display strategy descriptions from Req 3.7
    - Show recommendation when source has clustering columns
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.7_

  - [x] 10.4 Update ParallelismInput for S3 Tables cap
    - Modify parallelism input to cap at 8 when destination is `iceberg_s3_tables`
    - Display warning message when value exceeds 8: "S3 Tables API has lower concurrency limits than standard S3. Parallelism above 8 may cause throttling errors and slower overall throughput."
    - _Requirements: 6.1, 6.2, 6.7_

  - [x] 10.5 Update StructureReviewTable to show compaction and LF prerequisites
    - Display per-table compaction strategy in structure review
    - Display partition transforms as human-readable (e.g., "days(event_timestamp)")
    - Display Lake Formation prerequisites section for S3 Tables
    - Display derived glue.id value with validation indicator
    - _Requirements: 3.1, 5.1, 5.7, 7.6, 2.4_

  - [x] 10.6 Write frontend component tests
    - Test MaintenanceConfigForm renders fields, validates ranges, shows only for S3 Tables
    - Test CompactionStrategySelector renders options, shows sort columns for sort/z-order, displays descriptions
    - Test ParallelismInput caps at 8 for S3 Tables, shows warning above 8
    - Test StructureReviewTable shows compaction config, partition transforms, LF prerequisites
    - _Requirements: 4.1, 4.5, 3.3, 6.2, 7.6_

- [x] 11. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (15 properties total)
- Unit tests validate specific examples and edge cases
- All new configuration is stored in existing `checkpoint_data` JSONB field — no database migrations needed
- Frontend components are only shown for S3 Tables destinations (`iceberg_s3_tables`)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3", "1.4", "1.5"] },
    { "id": 1, "tasks": ["1.6", "1.7", "2.1", "3.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4", "3.2"] },
    { "id": 3, "tasks": ["5.1", "5.2", "5.3", "6.1", "6.2"] },
    { "id": 4, "tasks": ["5.4", "5.5", "5.6", "6.3", "6.4"] },
    { "id": 5, "tasks": ["8.1"] },
    { "id": 6, "tasks": ["8.2", "8.3", "8.4"] },
    { "id": 7, "tasks": ["8.5", "10.1"] },
    { "id": 8, "tasks": ["10.2", "10.3", "10.4", "10.5"] },
    { "id": 9, "tasks": ["10.6"] }
  ]
}
```
