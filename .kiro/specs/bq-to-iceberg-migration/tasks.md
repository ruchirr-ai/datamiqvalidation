# Implementation Plan: BigQuery to Apache Iceberg Migration

## Overview

This plan implements the BQ-to-Iceberg migration feature for DataMIQ, extending the existing orchestrator with Iceberg-specific services. The implementation uses Python/FastAPI for the backend, PyIceberg for Iceberg operations, Hypothesis for property-based tests, and React for the frontend. Tasks are ordered to build foundational components first, then wire them together with the orchestrator, API, and UI layers.

## Tasks

- [x] 1. Database models and Alembic migration
  - [x] 1.1 Create MigrationBQIceberg and IcebergTableValidation SQLAlchemy models
    - Create `backend/models/migration_bq_iceberg.py` with `MigrationBQIceberg` model
    - Create `backend/models/iceberg_table_validation.py` with `IcebergTableValidation` model
    - Include all columns, constraints (check_iceberg_dest_type, check_iceberg_pathway, check_parallelism_range), indexes, and unique constraints as defined in the design
    - Add `iceberg` as a valid connection type in the existing Connection model
    - _Requirements: 1.4, 7.2, 8.1_

  - [x] 1.2 Create Alembic migration for Iceberg tables
    - Create new Alembic version file under `backend/alembic/versions/`
    - Create `migrations_bq_iceberg` table with all columns and constraints
    - Create `iceberg_table_validations` table with unique constraint on (migration_id, table_name)
    - Add indexes on `workspace_id`, `status`, `destination_type`
    - Include downgrade to drop both tables
    - _Requirements: 7.2, 8.1_

  - [x] 1.3 Write unit tests for data models
    - Test model instantiation with valid data
    - Test constraint validation (destination_type, pathway, parallelism range)
    - Test JSONB field serialization/deserialization
    - _Requirements: 1.4, 7.2_

- [x] 2. Core type mapping and schema services
  - [x] 2.1 Implement BQ-to-Iceberg Type Mapper (`services/bq_iceberg_migration/type_mapper.py`)
    - Implement `BQToIcebergTypeMapper` class with full TYPE_MAP
    - Implement `map_column()` with recursive STRUCT/ARRAY handling up to MAX_STRUCT_DEPTH=15
    - Implement `map_schema()` to produce a full Iceberg Schema object
    - Implement `is_nullable()` for REQUIRED/NULLABLE/REPEATED modes
    - Flatten to StringType (JSON) when depth > 15 with warning log
    - Map unrecognized types to StringType with warning log
    - _Requirements: 3.1, 3.4, 3.5, 3.6, 3.7_

  - [x] 2.2 Write property test for type mapping completeness (Property 1)
    - **Property 1: Type mapping completeness and correctness**
    - Generate arbitrary BQ type strings from the defined mapping; verify correct Iceberg type output
    - Generate arbitrary unrecognized type strings; verify StringType output
    - **Validates: Requirements 3.1**

  - [x] 2.3 Write property test for nullability mapping (Property 2)
    - **Property 2: Nullability mapping**
    - Generate arbitrary BQ modes (REQUIRED, NULLABLE, REPEATED); verify correct nullable flag
    - **Validates: Requirements 3.4**

  - [x] 2.4 Write property test for recursive struct mapping (Property 5)
    - **Property 5: Recursive struct mapping up to depth limit**
    - Generate nested STRUCT schemas with varying depths (1-20); verify correct mapping up to 15 and flattening beyond
    - **Validates: Requirements 3.6, 3.7**

  - [x] 2.5 Implement Partition Spec Mapper (`services/bq_iceberg_migration/partition_mapper.py`)
    - Implement `PartitionSpecMapper` class with GRANULARITY_TO_TRANSFORM mapping
    - Implement `map_partition_spec()` with day() as default for all time-based columns
    - Implement `map_sort_order()` preserving BQ clustering column sequence
    - _Requirements: 3.2, 3.3_

  - [x] 2.6 Write property test for partition spec transform selection (Property 3)
    - **Property 3: Partition spec transform selection**
    - Generate arbitrary partition configs with optional granularity; verify day() default and explicit overrides
    - **Validates: Requirements 3.2**

  - [x] 2.7 Write property test for sort order preservation (Property 4)
    - **Property 4: Sort order preserves clustering column sequence**
    - Generate arbitrary lists of clustering columns; verify ordinal sequence preserved in Iceberg sort order
    - **Validates: Requirements 3.3**

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Credential and infrastructure services
  - [x] 4.1 Implement Credential Provider (`services/bq_iceberg_migration/credential_provider.py`)
    - Implement `AWSCredentialProvider` class with KMS and STS dependencies
    - Implement `get_session()` supporting both IAM Role ARN (STS AssumeRole) and access key paths
    - Implement `_assume_role()` with proper session name and region handling
    - Decrypt secret keys via existing KMS service
    - _Requirements: 8.1, 8.4, 8.6_

  - [x] 4.2 Write property test for credential encryption round-trip (Property 17)
    - **Property 17: Credential encryption round-trip**
    - Generate arbitrary secret key strings; verify encrypt→decrypt produces original
    - **Validates: Requirements 8.4**

  - [x] 4.3 Implement S3 Tables Adapter (`services/bq_iceberg_migration/s3_tables_adapter.py`)
    - Implement `S3TablesAdapter` class with s3tables_client dependency
    - Implement `ensure_namespace()` — create only with user-approved name
    - Implement `create_table()` — create table in S3 Tables and return metadata location
    - Implement `validate_namespace_name()` — S3 Tables naming conventions
    - _Requirements: 5.7, 1.3_

  - [x] 4.4 Implement Deduplication Guard (`services/bq_iceberg_migration/dedup_guard.py`)
    - Implement `DeduplicationGuard` class
    - Implement `get_registered_files()` from Iceberg snapshot metadata
    - Implement `filter_new_files()` comparing candidate URIs against registered set
    - Implement `is_safe_to_append()` returning (safe, new_files_only) tuple
    - _Requirements: 5.5_

  - [x] 4.5 Write property test for deduplication on resume (Property 15)
    - **Property 15: Deduplication on resume**
    - Generate arbitrary sets of registered files and candidate files; verify only new files returned
    - **Validates: Requirements 5.5**

- [x] 5. Schema evolution and validation services
  - [x] 5.1 Implement Schema Evolution Service (`services/bq_iceberg_migration/schema_evolution.py`)
    - Implement `SchemaEvolutionService` with VALID_PROMOTIONS mapping
    - Implement `detect_changes()` — detect new columns, type promotions, incompatible changes
    - Implement `apply_evolution()` — add new columns as optional regardless of BQ mode
    - Implement `is_compatible_promotion()` — int→long, float→double, decimal precision widening (same scale)
    - Log each schema evolution operation as INFO-level entry
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 5.2 Write property test for schema evolution nullability (Property 11)
    - **Property 11: Schema evolution adds new columns as optional**
    - Generate arbitrary new columns with any BQ mode; verify all added as optional in Iceberg
    - **Validates: Requirements 6.2**

  - [x] 5.3 Write property test for type promotion validity (Property 12)
    - **Property 12: Type promotion validity**
    - Generate arbitrary type pairs; verify only int→long, float→double, decimal(P,S)→decimal(P',S) where P'>P and S==S return true
    - **Validates: Requirements 6.3, 6.4**

  - [x] 5.4 Implement Validation Service (`services/bq_iceberg_migration/validation_service.py`)
    - Implement `IcebergValidationService` class
    - Implement `validate_full_load()` — exact match required (source == target)
    - Implement `validate_incremental_load()` — delta ≥ batch_export_count
    - Return `ValidationResult` with passed, source, target, and delta fields
    - _Requirements: 10.1, 10.2_

  - [x] 5.5 Write property test for row count validation (Property 10)
    - **Property 10: Row count validation correctness (full and incremental)**
    - Generate arbitrary source/target counts; verify full load passes iff equal
    - Generate arbitrary snapshot counts and batch counts; verify incremental passes iff delta ≥ batch
    - **Validates: Requirements 10.1, 10.2**

  - [x] 5.6 Implement Athena Verifier (`services/bq_iceberg_migration/athena_verifier.py`)
    - Implement `AthenaVerifier` class with athena_client dependency
    - Implement `verify_table_queryable()` — SELECT 1 LIMIT 1 within 120s timeout
    - Implement `count_rows()` — SELECT COUNT(*) within 300s timeout
    - Return `VerificationResult` with status and error details
    - _Requirements: 2.3, 2.5, 10.3_

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Structure report and cost analysis
  - [x] 7.1 Implement Structure Report Generator (`services/bq_iceberg_migration/structure_report.py`)
    - Implement `StructureReportGenerator` class
    - Implement `generate()` — produce full JSON report with per-table recommendations, prerequisites, warnings
    - Implement `apply_overrides()` — partition changes, exclusions, custom properties
    - Implement `apply_custom_structure()` — replace recommendation with user-defined structure
    - Implement `validate_custom_structure()` — validate against source data, return warnings
    - Implement `apply_dataset_to_db_mapping()` — BQ dataset → Glue DB name mapping
    - Implement `export_markdown()` and `export_pdf()` for downloadable reports
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.7, 4.8, 4.9, 4.10, 4.13_

  - [x] 7.2 Write property test for structure report completeness (Property 7)
    - **Property 7: Structure report contains all required fields per table**
    - Generate arbitrary assessment table metadata; verify all required fields present in output
    - **Validates: Requirements 4.2**

  - [x] 7.3 Write property test for structure plan round-trip (Property 8)
    - **Property 8: Structure plan round-trip persistence**
    - Generate arbitrary structure plans with overrides and custom definitions; verify JSON serialize→deserialize equivalence
    - **Validates: Requirements 4.10**

  - [x] 7.4 Write property test for custom structure validation (Property 20)
    - **Property 20: Custom structure validation**
    - Generate arbitrary custom structures and source column sets; verify incompatibilities detected
    - **Validates: Requirements 4.9**

  - [x] 7.5 Implement Cost Analysis Engine (`services/bq_iceberg_migration/cost_engine.py`)
    - Implement `CostAnalysisEngine` class with AWS pricing constants
    - Implement `calculate()` — full cost report with setup, recurring, projections
    - Implement `_calculate_setup_costs()` — S3 storage, Glue API, data transfer
    - Implement `_calculate_recurring_costs()` — S3 storage, Glue requests, Athena queries
    - Implement `_project_costs()` — 3/6/12 month projections with growth rate
    - Implement `_calculate_tco_comparison()` — BQ vs Iceberg cost comparison
    - Implement `recalculate_with_growth_rate()` — dynamic re-projection
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

  - [x] 7.6 Write property test for cost calculation consistency (Property 19)
    - **Property 19: Cost calculation consistency**
    - Generate arbitrary data sizes and growth rates; verify 12mo > 6mo > 3mo and higher growth → higher projections
    - **Validates: Requirements 13.3, 13.5**

- [x] 8. Parallel Iceberg Loader and Orchestrator
  - [x] 8.1 Implement Parallel Iceberg Loader (`services/bq_iceberg_migration/iceberg_loader.py`)
    - Implement `ParallelIcebergLoader` class with configurable worker pool (1-16)
    - Implement `load_tables()` — asyncio semaphore-based parallel loading
    - Implement `_load_single_table()` — dedup check, create/verify table, append data, update shard
    - Implement `create_table()` — create Iceberg table in Glue with required properties
    - Implement `append_data_files()` — register Parquet files via PyIceberg append
    - Implement `ensure_database_exists()` — create Glue database if not exists
    - Independent error handling per worker (failure isolation)
    - Retry with exponential backoff (5s, 15s, 45s) for S3 access errors
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.8, 12.1, 12.2, 12.4_

  - [x] 8.2 Write property test for progress percentage calculation (Property 9)
    - **Property 9: Progress percentage calculation with parallelism**
    - Generate arbitrary N total tables and M completed; verify progress = floor((M/N)*100)
    - **Validates: Requirements 5.8, 12.3**

  - [x] 8.3 Write property test for parallel worker isolation (Property 18)
    - **Property 18: Parallel worker isolation**
    - Simulate parallel workers with injected failures; verify non-failing workers complete successfully
    - **Validates: Requirements 12.2, 12.4**

  - [x] 8.4 Implement Iceberg Migration Orchestrator extension
    - Extend existing orchestrator pattern with `IcebergMigrationOrchestrator` class
    - Implement `_execute_iceberg_migration()` — generate report, pause at pending_review, load on approval
    - Implement `_handle_cancel_from_review()` — preserve all config on cancel
    - Implement `_handle_back_navigation()` — preserve state, clear only regenerated data
    - Implement status transitions: pending → running → pending_review → approved → running [load] → completed/failed
    - Support checkpoint-based resume (skip completed tables)
    - _Requirements: 7.1, 7.3, 7.4, 7.5, 7.6, 7.7_

  - [x] 8.5 Write property test for state machine transitions (Property 13)
    - **Property 13: State machine transition validity**
    - Generate arbitrary status transitions; verify only valid transitions succeed and cancel preserves config
    - **Validates: Requirements 7.4, 7.5**

  - [x] 8.6 Write property test for checkpoint-based resume (Property 14)
    - **Property 14: Checkpoint-based resume skips completed tables**
    - Generate arbitrary table load statuses; verify only non-completed tables are processed on resume
    - **Validates: Requirements 7.3**

- [x] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Input validation and error handling
  - [x] 10.1 Implement input validators for Iceberg configuration fields
    - Create `services/bq_iceberg_migration/validators.py`
    - Implement S3 bucket name validation (1-63 chars, S3 naming rules)
    - Implement Glue database name validation (`[a-z0-9_]+`, 1-255 chars)
    - Implement table bucket ARN validation (`arn:aws:s3tables:<region>:<account-id>:bucket/<name>`)
    - Implement IAM Role ARN validation
    - Implement parallelism range validation (1-16)
    - _Requirements: 1.2, 1.3, 1.5, 9.4_

  - [x] 10.2 Write property test for input validation (Property 6)
    - **Property 6: Input validation for Iceberg configuration fields**
    - Generate arbitrary strings; verify correct accept/reject for S3 bucket, Glue DB name, ARN formats
    - **Validates: Requirements 1.2, 1.3, 1.5, 9.4**

  - [x] 10.3 Implement error code categorization and logging
    - Create error code constants matching the design's error table
    - Implement structured error logging with categorized error_codes
    - Ensure no credentials are logged in migration logs
    - Log stage transitions, table operations, and schema evolution as INFO entries
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

  - [x] 10.4 Write property test for error code categorization (Property 16)
    - **Property 16: Error code categorization**
    - Generate arbitrary operation failures; verify correct error_code from defined set is logged
    - **Validates: Requirements 11.3**

- [x] 11. API endpoints
  - [x] 11.1 Implement CRUD API endpoints for Iceberg migrations
    - Create `backend/routers/bq_iceberg_migration.py`
    - POST `/api/migrations/bq-iceberg/create` — create migration with workspace isolation
    - GET `/api/migrations/bq-iceberg/list` — list migrations filtered by workspace_id
    - GET `/api/migrations/bq-iceberg/{id}` — get migration details
    - PUT `/api/migrations/bq-iceberg/{id}/update` — update migration config
    - DELETE `/api/migrations/bq-iceberg/{id}` — delete migration
    - Include request validation using Pydantic schemas
    - _Requirements: 1.4, 7.2, 9.3_

  - [x] 11.2 Implement lifecycle API endpoints
    - POST `/api/migrations/bq-iceberg/{id}/start` — start migration
    - POST `/api/migrations/bq-iceberg/{id}/pause` — pause migration
    - POST `/api/migrations/bq-iceberg/{id}/resume` — resume with checkpoint
    - POST `/api/migrations/bq-iceberg/{id}/cancel` — cancel preserving config
    - POST `/api/migrations/bq-iceberg/{id}/restart` — restart migration
    - GET `/api/migrations/bq-iceberg/{id}/status` — status with progress percentage
    - GET `/api/migrations/bq-iceberg/{id}/logs` — migration logs
    - _Requirements: 7.4, 7.5, 11.4, 11.5_

  - [x] 11.3 Implement structure report and approval API endpoints
    - GET `/api/migrations/bq-iceberg/{id}/structure-report` — full report as JSON
    - POST `/api/migrations/bq-iceberg/{id}/approve-structure` — approve with overrides and dataset mapping
    - POST `/api/migrations/bq-iceberg/{id}/request-changes` — submit structure overrides
    - POST `/api/migrations/bq-iceberg/{id}/custom-structure` — define custom table structure
    - GET `/api/migrations/bq-iceberg/{id}/download-report` — download as MD/PDF
    - _Requirements: 4.5, 4.6, 4.7, 4.8, 4.9, 4.12, 4.13_

  - [x] 11.4 Implement cost analysis API endpoints
    - GET `/api/migrations/bq-iceberg/{id}/cost-analysis` — get cost analysis report
    - POST `/api/migrations/bq-iceberg/{id}/cost-analysis/recalculate` — recalculate with new growth rate
    - _Requirements: 13.1, 13.5_

  - [x] 11.5 Implement validation and connection test API endpoints
    - POST `/api/migrations/bq-iceberg/{id}/validate` — trigger manual validation
    - GET `/api/migrations/bq-iceberg/{id}/validation-results` — get validation results
    - POST `/api/connections/test-iceberg` — test Iceberg connection (S3, Glue, write permissions)
    - _Requirements: 10.3, 10.4, 10.5, 8.2, 8.3_

  - [x] 11.6 Write integration tests for API endpoints
    - Test all CRUD endpoints with valid and invalid payloads
    - Test lifecycle endpoints with state transitions
    - Test structure report and approval flow
    - Test cost analysis endpoints
    - Test workspace isolation (cannot access other workspace's migrations)
    - Test authentication and authorization
    - _Requirements: 4.12, 7.4, 8.2, 8.3_

- [x] 12. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Frontend: Migration wizard and destination selection
  - [x] 13.1 Implement Iceberg destination selection in migration wizard
    - Add "Apache Iceberg" as a destination card alongside "Amazon Redshift"
    - Implement sub-selection for "Standard S3" vs "AWS S3 Tables"
    - Show dynamic configuration fields based on selected sub-type
    - Implement IAM Role ARN field as alternative to access keys
    - Preserve all values on back navigation
    - _Requirements: 1.1, 1.2, 1.3, 1.6, 9.1, 9.2, 9.5_

  - [x] 13.2 Implement client-side validation for Iceberg configuration
    - Validate S3 bucket name format
    - Validate Glue database name format (lowercase alphanumeric + underscores, 1-255)
    - Validate table bucket ARN format for S3 Tables
    - Validate AWS region from allowed list
    - Validate IAM Role ARN format
    - Display summary panel after configuration
    - _Requirements: 1.5, 1.6, 9.3, 9.4_

  - [x] 13.3 Write frontend tests for migration wizard
    - Test destination card selection and sub-type toggle
    - Test form field rendering for each destination type
    - Test client-side validation for all fields
    - Test back navigation preserves values
    - Test summary panel display
    - _Requirements: 9.1, 9.2, 9.4, 9.5_

- [x] 14. Frontend: Structure review and cost analysis
  - [x] 14.1 Implement structure review page
    - Create dedicated review page accessible from migration detail view
    - Render per-table sections (collapsible) with columns, partition spec, sort order, properties
    - Display prerequisites checklist and warnings/recommendations
    - Implement "Approve & Proceed" and "Request Changes" buttons
    - Implement override controls (partition, sort order, exclusions, custom properties)
    - Implement dataset-to-database mapping UI
    - Implement namespace naming input for S3 Tables
    - _Requirements: 4.5, 4.6, 4.7, 4.8_

  - [x] 14.2 Implement custom structure editor
    - Add "Define Custom Structure" option per table
    - Implement column definition editor (name, Iceberg type, nullability)
    - Implement partition spec editor (column + transform selection)
    - Implement sort order editor (columns + direction)
    - Implement table properties editor (key-value pairs)
    - Display validation warnings for incompatible structures
    - _Requirements: 4.9_

  - [x] 14.3 Implement cost analysis tab
    - Create "Cost Analysis" tab/section alongside structure report
    - Display setup costs, recurring monthly costs, and projections (3/6/12 months)
    - Display optimistic and conservative estimates
    - Display TCO comparison (BQ vs Iceberg) when available
    - Implement growth rate adjustment slider with dynamic recalculation
    - Include cost data in downloadable report
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7_

  - [x] 14.4 Write frontend tests for structure review and cost analysis
    - Test structure report rendering with collapsible sections
    - Test override controls and form submission
    - Test custom structure editor validation
    - Test cost analysis tab rendering
    - Test growth rate adjustment and recalculation
    - Test download report functionality
    - _Requirements: 4.5, 4.9, 13.1, 13.5_

- [x] 15. Frontend: Progress and validation display
  - [x] 15.1 Implement migration progress display for parallel loading
    - Show per-table progress during load stage
    - Display overall progress_percentage with incremental updates
    - Show table-level status (pending, loading, completed, failed)
    - Display current_stage indicator (export, transfer, review, load)
    - _Requirements: 5.8, 11.4, 11.5, 12.3_

  - [x] 15.2 Implement validation results display
    - Show per-table validation results (passed/failed/skipped)
    - Display source vs target row counts
    - Show validation timestamp and error reasons
    - Implement manual validation trigger button
    - _Requirements: 10.1, 10.4, 10.5_

  - [x] 15.3 Write frontend tests for progress and validation display
    - Test progress bar updates during parallel loading
    - Test per-table status rendering
    - Test validation results table
    - Test manual validation trigger
    - _Requirements: 5.8, 10.4, 12.3_

- [x] 16. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (20 properties total)
- Unit tests validate specific examples and edge cases
- The implementation uses Python (FastAPI, PyIceberg, Hypothesis) for backend and React for frontend
- All database queries must include workspace_id filter for multi-tenant isolation
- AWS credentials must be encrypted via KMS before storage
- The design uses Python code directly (not pseudocode), so no language selection was needed

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["2.2", "2.3", "2.4", "2.6", "2.7"] },
    { "id": 1, "tasks": ["4.2", "4.5", "5.1", "5.4", "5.6", "10.1"] },
    { "id": 2, "tasks": ["5.2", "5.3", "5.5", "10.2", "10.3"] },
    { "id": 3, "tasks": ["7.1", "7.5", "10.4"] },
    { "id": 4, "tasks": ["7.2", "7.3", "7.4", "7.6", "8.1"] },
    { "id": 5, "tasks": ["8.2", "8.3", "8.4"] },
    { "id": 6, "tasks": ["8.5", "8.6"] },
    { "id": 7, "tasks": ["11.1", "11.2", "11.3", "11.4", "11.5"] },
    { "id": 8, "tasks": ["11.6"] },
    { "id": 9, "tasks": ["13.1", "13.2"] },
    { "id": 10, "tasks": ["13.3", "14.1", "14.2", "14.3"] },
    { "id": 11, "tasks": ["14.4", "15.1", "15.2"] },
    { "id": 12, "tasks": ["15.3"] }
  ]
}
```
