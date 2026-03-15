# Implementation Plan: Data Validation Module

## Overview

Implement the Data Validation module for DataMIQ, providing post-migration data integrity verification for BigQuery-to-Redshift migrations. The module performs DDL schema comparison, row count verification, and record-level data matching per table, with AI-powered discrepancy analysis via AWS Bedrock. Implementation follows the existing FastAPI router → service → repository layering, SQLAlchemy models with Alembic migrations, Redis caching with PostgreSQL fallback, and workspace-scoped tenant isolation. The frontend provides a Validation Dashboard and Validation Detail page built with React/TypeScript.

## Tasks

- [x] 1. Create data models and database migration
  - [x] 1.1 Create ValidationRun and ValidationTableResult SQLAlchemy models
    - Create `backend/models/validation_run.py` with the ValidationRun model as specified in the design (id, workspace_id, migration_id, source_connection_id, target_connection_id, bedrock_model, batch_size, type_mapping_overrides JSONB, status, progress_percentage, tables_total, tables_passed, tables_failed, tables_error, started_at, completed_at, duration_seconds, created_by, created_at, updated_at)
    - Create `backend/models/validation_table_result.py` with the ValidationTableResult model as specified in the design (id, run_id FK, workspace_id, table_name, dataset_name, ddl_status, ddl_comparison_result JSONB, row_count_status, row_count_result JSONB, data_match_status, data_match_result JSONB, ai_analysis JSONB, status, error_message, started_at, completed_at, duration_seconds, created_at, updated_at)
    - Add indexes: idx_validation_runs_workspace, idx_validation_runs_migration, idx_validation_runs_status, idx_vtresults_run, idx_vtresults_workspace, idx_vtresults_table_name, idx_vtresults_status
    - Add foreign key constraint from validation_table_results.run_id to validation_runs.id with ON DELETE CASCADE
    - Use server_default func.current_timestamp() for created_at columns
    - Register models in `backend/models/__init__.py`
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.9_

  - [x] 1.2 Create Alembic migration for validation tables
    - Generate Alembic migration that creates `validation_runs` table first (referenced by FK), then `validation_table_results` table
    - Include all indexes, foreign keys, NOT NULL constraints on workspace_id/migration_id/run_id, and default values as specified in the design
    - Use JSONB type for ddl_comparison_result, row_count_result, data_match_result, ai_analysis, and type_mapping_overrides
    - Include downgrade that drops validation_table_results first, then validation_runs
    - _Requirements: 9.1, 9.2, 9.5, 9.6, 9.8, 9.10_

  - [x] 1.3 Create Pydantic request/response schemas
    - Create `backend/models/validation_schemas.py` with: ValidationRunStatus enum, ValidationStepStatus enum, CreateValidationRunRequest, ValidationRunResponse, ValidationTableResultResponse, ValidationTableDetailResponse, ValidationReportResponse, PaginatedValidationRunsResponse
    - Include field validators: batch_size (ge=100, le=100000, default=10000), tables as Optional list, type_mapping_overrides as Optional dict
    - _Requirements: 8.1, 8.3, 8.4, 8.5, 8.6, 8.8, 9.1, 9.2_

  - [x] 1.4 Write unit tests for data models and schemas
    - Test ValidationRun and ValidationTableResult model creation with valid data
    - Test Pydantic schema validation with valid payloads, invalid payloads (missing fields, wrong types), and edge cases (empty table list, single table, 100 tables)
    - Test ValidationRunStatus and ValidationStepStatus enum validation
    - Test CreateValidationRunRequest batch_size bounds validation (below 100, above 100000)
    - Include sample payloads for valid validation run creation, invalid migration_id, missing connection
    - _Requirements: 16.1, 16.11_

- [x] 2. Implement DataTypeMapper
  - [x] 2.1 Create DataTypeMapper with BigQuery-to-Redshift type mapping
    - Create `backend/services/data_type_mapper.py` with DEFAULT_BQ_TO_REDSHIFT_TYPE_MAP constant dict mapping all 12 type pairs: STRING→VARCHAR, INT64→BIGINT, FLOAT64→DOUBLE PRECISION, NUMERIC→DECIMAL, BIGNUMERIC→DECIMAL, BOOL→BOOLEAN, TIMESTAMP→TIMESTAMP, DATE→DATE, TIME→TIME, BYTES→VARBYTE, ARRAY→SUPER, STRUCT→SUPER
    - Implement DataTypeMapper class with __init__(overrides), is_equivalent(bq_type, redshift_type), get_expected_redshift_type(bq_type), to_dict(), from_dict(data) methods
    - Store default mapping as module-level configurable constant, not hardcoded inline
    - Support user-provided type_mapping_overrides that merge with defaults
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9, 10.10, 10.11, 10.12, 10.13_

  - [x] 2.2 Write unit tests for DataTypeMapper
    - Test all 12 default BigQuery-to-Redshift type mappings produce correct equivalence
    - Test is_equivalent returns True for mapped pairs (e.g., STRING vs VARCHAR)
    - Test is_equivalent returns False for non-mapped pairs
    - Test override merging: user override replaces default mapping
    - Test get_expected_redshift_type for known and unknown types
    - Test case-insensitive type comparison
    - _Requirements: 10.1–10.13, 16.5_

  - [x] 2.3 Write property test for DataTypeMapper round-trip
    - **Property 1: Data type mapping round-trip consistency**
    - Verify that serializing DataTypeMapper to dict (to_dict) then reconstructing via from_dict produces an equivalent mapping object for all defined type pairs
    - Use Hypothesis with minimum 100 iterations
    - **Validates: Requirements 10.14, 18.1**

- [x] 3. Implement ValidationRepository
  - [x] 3.1 Create ValidationRepository with CRUD operations
    - Create `backend/repositories/validation_repository.py` implementing: create_run, get_run, list_runs (with pagination and filtering by migration_id, status), update_run, delete_run, create_table_result, get_table_result, list_table_results, update_table_result
    - All queries MUST include workspace_id filter for tenant isolation
    - list_runs must support page/page_size pagination (default 20, max 100) and return (list, total_count) tuple
    - delete_run must cascade delete associated validation_table_results via FK CASCADE
    - _Requirements: 8.2, 8.7, 8.8, 8.9, 8.10, 15.1, 15.9_

  - [x] 3.2 Write unit tests for ValidationRepository
    - Test CRUD operations for ValidationRun and ValidationTableResult with sample payloads
    - Test workspace isolation: verify queries with workspace_id=1 do not return records with workspace_id=2
    - Test pagination and filtering for list_runs (by status, by migration_id)
    - Test cascade deletion: deleting a run removes all associated table results
    - Test get_run returns None for non-existent or wrong-workspace run_id
    - _Requirements: 15.1, 16.6_

- [x] 4. Implement ValidationCache
  - [x] 4.1 Create ValidationCache with Redis caching and PostgreSQL fallback
    - Create `backend/services/validation_cache.py` following the existing `conversion_cache.py` pattern
    - Implement: get_run, set_run (TTL 15 min), invalidate_run, get_table_result, set_table_result (TTL 15 min), invalidate_table_result, get_report, set_report (TTL 30 min), invalidate_report, invalidate_all_for_run
    - Key patterns include workspace_id: `validation:run:{workspace_id}:{run_id}`, `validation:table:{workspace_id}:{run_id}:{table_name}`, `validation:report:{workspace_id}:{run_id}`
    - If Redis is unavailable, fall back to PostgreSQL queries without raising errors
    - Log cache hit, miss, and error events for monitoring
    - Serialize cached data as JSON with datetime fields converted to ISO 8601 strings
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8, 11.9, 11.10_

  - [x] 4.2 Write unit tests for ValidationCache
    - Test cache set/get/invalidate for run, table result, and report
    - Test Redis fallback: when Redis raises ConnectionError, verify no exception is raised
    - Test TTL values are correctly applied (15 min for runs/tables, 30 min for reports)
    - Test invalidate_all_for_run clears all related keys
    - Test workspace_id is included in cache keys to prevent cross-tenant access
    - _Requirements: 11.1–11.10, 16.7_

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement ValidationService - Core creation and query logic
  - [x] 6.1 Create ValidationService with validation run creation
    - Create `backend/services/validation_service.py` implementing create_validation_run(workspace_id, migration_id, source_connection_id, target_connection_id, tables, bedrock_model, batch_size, type_mapping_overrides, created_by)
    - Verify Migration_Record status is 'completed' before creating run; return error if not
    - Verify Source_Connection and Target_Connection exist and are active; return error identifying invalid connection
    - If tables list is not provided, retrieve from Migration_Record source_tables field
    - Create ValidationRun with status 'pending' and one ValidationTableResult per table with status 'pending'
    - Cache ValidationRun in Redis with TTL 15 minutes
    - Log creation with migration_id, table count, and workspace_id
    - Filter all queries by workspace_id
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10_

  - [x] 6.2 Add query, report, and delete methods to ValidationService
    - Implement get_run, list_runs (paginated with migration_id/status filters), get_table_results, get_table_detail, get_report, delete_run
    - get_report generates ValidationReportResponse with overall summary (total_tables, tables_passed/failed/error, overall_status, duration) and per-table details including DDL discrepancies, row count stats, record match summary, and AI analysis
    - Cache report in Redis with TTL 30 minutes
    - Include migration_id, source_connection name, and target_connection name in report for traceability
    - All methods enforce workspace_id filtering
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9, 7.10, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

  - [x] 6.3 Write unit tests for ValidationService creation and query logic
    - Test create_validation_run with valid inputs creates run and table results
    - Test create_validation_run with non-completed migration returns error
    - Test create_validation_run with inactive connection returns error
    - Test create_validation_run without explicit tables retrieves from migration record
    - Test get_run, list_runs, get_table_results, get_table_detail, delete_run
    - Test get_report generates correct aggregation of per-table results
    - Test workspace isolation on all methods
    - Mock external dependencies (database connections, Redis)
    - Include sample payloads for valid creation, invalid migration_id, missing connection, empty table list, single table, 100 tables
    - _Requirements: 16.1, 16.8, 16.10, 16.11_

- [ ] 7. Implement ValidationService - DDL comparison logic
  - [x] 7.1 Implement DDL schema comparison in ValidationService
    - Implement _validate_ddl method that retrieves source column metadata from AssessmentColumn records (existing Assessment module)
    - Query Target_Connection to retrieve Redshift column metadata (column_name, data_type, is_nullable, ordinal_position)
    - Compare each source column against target using DataTypeMapper for type equivalence
    - Detect and record discrepancies: missing_column, extra_column, type_mismatch, nullability_mismatch
    - Store results as JSONB in ddl_comparison_result field with discrepancies list, source_column_count, target_column_count, columns_compared
    - Set ddl_status to 'passed' (zero discrepancies) or 'failed' (one or more discrepancies)
    - Support configurable type_mapping_overrides from ValidationRun
    - Decrypt target connection credentials using KMS before establishing connection
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 15.2, 15.3_

  - [x] 7.2 Write unit tests for DDL comparison logic
    - Test DDL comparison with identical schemas produces zero discrepancies and 'passed' status
    - Test detection of missing_column when source has column not in target
    - Test detection of extra_column when target has column not in source
    - Test detection of type_mismatch when types don't match expected mapping
    - Test detection of nullability_mismatch
    - Test type_mapping_overrides are applied correctly
    - Test mapped type pairs (e.g., STRING vs VARCHAR) are treated as equivalent
    - Mock Assessment and Redshift connection queries
    - _Requirements: 16.2_

  - [x] 7.3 Write property test for DDL comparison identity
    - **Property 2: DDL comparison with identical schemas produces zero discrepancies**
    - Generate random column definitions (name, type from BQ types, nullability) and verify comparing identical source and target always produces zero discrepancies and 'passed' status
    - Use Hypothesis with minimum 100 iterations, generating lists of column defs
    - **Validates: Requirements 18.2, 18.8**

  - [x] 7.4 Write property test for DDL discrepancy count bound
    - **Property 3: DDL discrepancy count is bounded by total columns compared**
    - Generate random source and target column sets and verify the count of discrepancies is always ≤ total number of columns compared
    - Use Hypothesis with minimum 100 iterations
    - **Validates: Requirements 18.5, 18.8**

- [x] 8. Implement ValidationService - Row count validation logic
  - [x] 8.1 Implement row count validation in ValidationService
    - Implement _validate_row_count method that queries Source_Connection (BigQuery) for current row count and Target_Connection (Redshift) for current row count
    - Compare counts and calculate absolute difference and percentage_difference
    - Set row_count_status to 'passed' (equal counts) or 'failed' (different counts)
    - Store results in row_count_result JSONB: source_count, target_count, difference, percentage_difference
    - Set row_count_status to 'error' with error message if source or target query fails
    - Use query timeout of 300 seconds for row count queries
    - Log comparison results with table name, source count, and target count
    - Decrypt connection credentials using KMS
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 15.2, 15.3_

  - [x] 8.2 Write unit tests for row count validation
    - Test row count with equal counts produces 'passed' status
    - Test row count with different counts produces 'failed' status with correct difference
    - Test row count with source query failure produces 'error' status
    - Test row count with target query failure produces 'error' status
    - Test percentage_difference calculation
    - Mock BigQuery and Redshift connection queries
    - _Requirements: 16.3_

  - [x] 8.3 Write property test for row count equality
    - **Property 4: Row count comparison with equal counts always produces 'passed' status**
    - Generate random positive integers, use same value for source and target, verify status is always 'passed' and difference is always 0
    - Use Hypothesis with minimum 100 iterations
    - **Validates: Requirements 18.3**

- [x] 9. Implement ValidationService - Record-level matching logic
  - [x] 9.1 Implement record-level data matching in ValidationService
    - Implement _validate_records method that determines primary key from AssessmentColumn metadata or user config; fall back to hash of all columns with warning if no PK found
    - Read source data from BigQuery in configurable batch sizes (default 10000 rows)
    - Read target data from Redshift in matching batch sizes with same ordering
    - For each source record, locate matching target record by PK and compare all column values
    - Detect discrepancies: missing_in_target, extra_in_target, value_mismatch (with column name, source value, target value)
    - Apply data type-aware comparison logic for BigQuery-to-Redshift type differences (TIMESTAMP precision, NUMERIC scale)
    - Store summary in data_match_result JSONB: total_compared, matched_count, missing_count, extra_count, mismatch_count, sample_discrepancies (capped at 100)
    - Set data_match_status to 'passed' (zero discrepancies) or 'failed' (one or more)
    - On error, set data_match_status to 'error', store error message, continue with remaining tables
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 4.11, 4.12, 15.2, 15.3_

  - [x] 9.2 Write unit tests for record-level matching
    - Test matching with identical datasets produces zero mismatches and 'passed' status
    - Test detection of missing_in_target records
    - Test detection of extra_in_target records
    - Test detection of value_mismatch with column details
    - Test hash-based row identification when no PK is available
    - Test sample discrepancies are capped at 100
    - Test error handling sets data_match_status to 'error'
    - Mock BigQuery and Redshift data reads
    - _Requirements: 16.4_

  - [x] 9.3 Write property test for record-level matching identity
    - **Property 5: Record-level matching with identical datasets produces zero mismatches**
    - Generate random row data (list of dicts with consistent keys/types) and verify comparing identical source and target always produces matched_count == total_compared and zero mismatches
    - Use Hypothesis with minimum 100 iterations
    - **Validates: Requirements 18.4, 18.9**

- [x] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Implement ValidationService - Orchestration and AI analysis
  - [x] 11.1 Implement background validation orchestration
    - Implement run_validation_background(run_id, workspace_id) as FastAPI background task
    - Update ValidationRun status to 'running' and record started_at timestamp
    - Process tables sequentially: DDL comparison → row count validation → record-level matching for each table
    - After each table completes, update ValidationTableResult with results and status ('completed' or 'failed')
    - Update progress_percentage after each table (completed / total * 100)
    - On unrecoverable table error, mark table as 'error' and continue with remaining tables
    - When all tables complete, set run status to 'completed' (or 'failed' if all tables errored) and record completed_at, duration_seconds
    - Update summary statistics: tables_passed, tables_failed, tables_error
    - Invalidate Redis cache for the run after each table completes
    - Log start, progress, and completion events with run_id, table_name, duration_ms
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10, 5.11, 12.1, 12.2, 12.9, 12.10_

  - [x] 11.2 Implement AI-powered discrepancy analysis via Bedrock
    - Implement _run_bedrock_analysis method invoked for each failed table after run completes
    - Construct prompt containing table name, DDL discrepancies, row count differences, sample record-level mismatches, source/target database types (BigQuery, Redshift)
    - Limit prompt size to 10000 characters by truncating sample discrepancies if necessary
    - Invoke BedrockClient with configured model; parse response to extract root_cause, impact_assessment, recommended_workarounds
    - Store results in ValidationTableResult ai_analysis JSONB field
    - On Bedrock failure, log error and set ai_analysis to null without failing the validation
    - Support configurable Bedrock model selection per ValidationRun
    - Log Bedrock invocation duration and model_id
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10_

  - [x] 11.3 Write unit tests for orchestration and AI analysis
    - Test background orchestration processes all tables and updates progress
    - Test orchestration continues on table error and marks table as 'error'
    - Test run status set to 'completed' when tables finish, 'failed' when all error
    - Test summary statistics (tables_passed, tables_failed, tables_error) are correct
    - Test Bedrock analysis is invoked for failed tables
    - Test Bedrock failure does not fail the overall validation
    - Test prompt construction includes table name, discrepancies, and stays within 10000 char limit
    - Test cache invalidation after each table completion
    - Mock BedrockClient, database connections, Redis
    - _Requirements: 16.1, 16.9, 16.10_

  - [x] 11.4 Write property test for report invariant
    - **Property 6: tables_passed + tables_failed + tables_error always equals tables_total**
    - Generate random validation run outcomes (lists of table statuses) and verify the invariant holds after orchestration completes
    - Use Hypothesis with minimum 100 iterations
    - **Validates: Requirements 18.6**

  - [x] 11.5 Write property test for progress percentage bounds
    - **Property 7: progress_percentage is always between 0 and 100 inclusive**
    - Generate random table counts and completion states, verify progress_percentage stays in [0, 100] after any table completion update
    - Use Hypothesis with minimum 100 iterations
    - **Validates: Requirements 18.10**

- [x] 12. Implement structured logging and error handling
  - [x] 12.1 Add structured logging to ValidationService
    - Add structured log entries for each validation step: run_started, ddl_comparison_started/completed, row_count_started/completed, record_match_started/completed, ai_analysis_started/completed, run_completed
    - Include run_id, table_name, workspace_id, and duration_ms in every log entry
    - Log errors with level 'ERROR' including stack trace and error context
    - Log connection timeouts with table_name, query_type, and timeout_seconds
    - Mask sensitive data values in log messages (log column names and discrepancy types only, no raw data)
    - Log summary at run completion: tables_passed, tables_failed, tables_error, total_duration_seconds
    - Track and log total duration for each validation phase per table
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8, 12.9, 12.10_

  - [x] 12.2 Add error sanitization to ValidationService
    - Sanitize error messages to exclude connection credentials, hostnames, or internal IP addresses before returning to client
    - Use parameterized queries for all database operations to prevent SQL injection
    - On critical error (connection lost mid-validation), immediately update table result status to 'error' and continue
    - _Requirements: 15.4, 15.5, 15.8, 15.9, 12.8_

- [x] 13. Implement ValidationRouter API endpoints
  - [x] 13.1 Create ValidationRouter with all endpoints
    - Create `backend/routers/validation_router.py` with FastAPI router (prefix `/api/validations`)
    - Implement: POST `/` (201, create and start validation run via background task), GET `/` (200, paginated list with filters for migration_id, status, page, page_size), GET `/{run_id}` (200, run details), GET `/{run_id}/tables` (200, table results list), GET `/{run_id}/tables/{table_name}` (200, table detail with JSONB fields), GET `/{run_id}/report` (200, full report), DELETE `/{run_id}` (204, cascade delete)
    - Validate workspace_id from request context matches resource workspace_id
    - Return HTTP 404 if resource does not exist or belongs to different workspace
    - Support pagination with page (default 1) and page_size (default 20, max 100)
    - Inject DB session, BackgroundTasks, workspace_id from header
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9, 8.10_

  - [x] 13.2 Register ValidationRouter in main.py
    - Import and include validation_router in `backend/main.py` via `app.include_router(validation_router)`
    - Import ValidationRun and ValidationTableResult models in main.py to ensure SQLAlchemy registration
    - _Requirements: 8.1_

  - [x] 13.3 Write integration tests for ValidationRouter endpoints
    - Test POST /api/validations with valid payload returns 201 and ValidationRun details
    - Test POST /api/validations with invalid migration_id returns 400
    - Test POST /api/validations with inactive connection returns 400
    - Test GET /api/validations returns paginated list filtered by workspace_id
    - Test GET /api/validations/{run_id} returns run details, 404 for non-existent
    - Test GET /api/validations/{run_id}/tables returns per-table results
    - Test GET /api/validations/{run_id}/report returns full ValidationReport
    - Test DELETE /api/validations/{run_id} returns 204 and cascading deletion
    - Test workspace isolation: cross-workspace access returns 404
    - Include sample payloads for all endpoints following Arrange-Act-Assert pattern
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.6, 17.7, 17.8, 17.9, 17.10_

- [x] 14. Checkpoint - Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 15. Implement frontend API client
  - [x] 15.1 Create validationApi service
    - Create `frontend/src/services/validationApi.ts` following the existing `conversionApi.ts` pattern
    - Implement TypeScript interfaces: CreateValidationRunRequest, ValidationRunResponse, ValidationTableResultResponse, ValidationTableDetailResponse, ValidationReportResponse, PaginatedValidationRunsResponse
    - Implement API methods: createValidationRun, listValidationRuns (with pagination, migration_id, status filters), getValidationRun, getValidationTableResults, getValidationTableDetail, getValidationReport, deleteValidationRun
    - Include workspace_id header in all requests
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

- [x] 16. Implement Validation Dashboard Page
  - [x] 16.1 Create ValidationDashboardPage with run list and creation form
    - Create `frontend/src/pages/ValidationDashboardPage.tsx` following the `BatchConverterPage.tsx` pattern
    - Display list of ValidationRun records in a table with columns: run_id, migration_name, status, progress_percentage, tables_passed, tables_failed, started_at, duration
    - "New Validation" button opens a creation form with dropdown selectors for migration (completed only), source_connection, and target_connection pre-populated from migration data
    - Optional fields: bedrock_model, batch_size, type_mapping_overrides, tables list
    - Status color coding: green for passed, red for failed, yellow for running, gray for pending
    - Auto-refresh every 10 seconds when any run has status 'running'
    - Pagination with page size selector (10, 20, 50)
    - Filters for status and migration_id
    - Display overall pass rate percentage across completed runs
    - Clicking a run row navigates to Validation Detail page
    - Filter all data by current workspace_id
    - Create `frontend/src/pages/ValidationDashboardPage.css` for styling
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7, 13.8, 13.9, 13.10_

  - [x] 16.2 Write component tests for ValidationDashboardPage
    - Test renders run list with correct columns
    - Test "New Validation" button opens creation form
    - Test status color coding renders correctly
    - Test pagination controls work
    - Test filter by status and migration_id
    - Test auto-refresh triggers when a run is 'running'
    - Test clicking a row navigates to detail page
    - Mock validationApi methods
    - _Requirements: 13.1–13.10_

- [x] 17. Implement Validation Detail Page
  - [x] 17.1 Create ValidationDetailPage with per-table results and expandable panels
    - Create `frontend/src/pages/ValidationDetailPage.tsx`
    - Display run summary: migration_name, status, progress bar, tables_passed, tables_failed, tables_error, started_at, completed_at, duration
    - Table of ValidationTableResult records with columns: table_name, ddl_status, row_count_status, data_match_status, overall_status
    - Per-column status icons: checkmark for passed, cross for failed, warning for error
    - Clicking a table row expands inline detail panel showing:
      - DDL discrepancies: side-by-side source vs target columns with mismatches highlighted
      - Row count: source_count, target_count, difference, percentage_difference
      - Record match: matched_count, missing_count, extra_count, mismatch_count, scrollable sample discrepancies list
    - "AI Analysis" section for failed tables with Bedrock analysis: root_cause, impact_assessment, recommended_workarounds
    - "Download Report" button to download full ValidationReport as JSON
    - Auto-refresh every 10 seconds while run status is 'running'
    - Create `frontend/src/pages/ValidationDetailPage.css` for styling
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7, 14.8, 14.9, 14.10_

  - [x] 17.2 Write component tests for ValidationDetailPage
    - Test renders run summary with correct data
    - Test table results list renders with status icons
    - Test expanding a table row shows DDL, row count, and record match panels
    - Test AI Analysis section renders when available
    - Test Download Report button triggers JSON download
    - Test auto-refresh while status is 'running'
    - Mock validationApi methods
    - _Requirements: 14.1–14.10_

- [x] 18. Wire frontend routes and navigation
  - [x] 18.1 Add validation pages to App router and navigation
    - Register ValidationDashboardPage and ValidationDetailPage routes in `frontend/src/App.tsx`
    - Add navigation link to sidebar for "Data Validation"
    - Route: `/validations` for dashboard, `/validations/:runId` for detail page
    - _Requirements: 13.1, 14.1_

- [x] 19. Checkpoint - Ensure frontend builds without errors
  - Ensure all tests pass, ask the user if questions arise.

- [x] 20. Add security and workspace isolation enforcement
  - [x] 20.1 Add workspace isolation and security to validation endpoints
    - Validate requesting user has access to workspace before executing any validation operation
    - Return HTTP 404 (not 403) for cross-workspace access attempts to avoid revealing resource existence
    - Include workspace_id in all Redis cache keys
    - Log workspace_id in all audit log entries
    - Enforce rate limiting of 10 concurrent validation runs per workspace
    - Use parameterized queries for all database operations
    - Discard decrypted credentials from memory after connection is established
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7, 15.8, 15.9, 15.10_

- [x] 21. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Backend uses Python + FastAPI; frontend uses React + TypeScript
- All database queries must include workspace_id for tenant isolation
- Redis caching follows the existing conversion_cache.py pattern with PostgreSQL fallback
- AWS credentials use IAM roles — no hardcoded secrets
- Property tests use Hypothesis library with minimum 100 iterations per property
- Unit tests mock all external dependencies (BigQuery, Redshift, Bedrock, Redis)
- Structured logging follows existing patterns with JSON format and CloudWatch integration
