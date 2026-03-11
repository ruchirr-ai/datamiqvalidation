# Requirements Document: Data Validation Module

## Introduction

This document specifies requirements for the Data Validation module of the DataMIQ platform. The module validates table-level data migrations from BigQuery to Redshift by comparing source DDL against target DDL, verifying row counts, and performing record-level data matching. It leverages existing connection, assessment, and migration data, integrates AWS Bedrock for AI-powered analysis of discrepancies, and produces detailed validation reports with issue causes and workarounds. Data is highly sensitive; validation accuracy is paramount and any errors or hindrances must be immediately surfaced.

## Glossary

- **Validation_Run**: A single execution of the validation process for a set of migrated tables, tracking overall status and progress
- **Validation_Table_Result**: Per-table validation outcome containing DDL comparison, row count check, and record-level match results
- **Validation_Report**: Aggregated output of a Validation_Run showing pass/fail per table with issue details, causes, and workarounds
- **DDL_Comparison**: Structural comparison of source BigQuery table schema against target Redshift table schema, including column names, data types, nullability, and ordering
- **Row_Count_Check**: Numeric comparison of total row count in source table versus target table
- **Record_Level_Match**: Row-by-row comparison of source data against target data to detect missing, extra, or mismatched records
- **Data_Type_Mapping**: Expected mapping of BigQuery data types to equivalent Redshift data types used during DDL comparison
- **Validation_Service**: Backend service orchestrating DDL comparison, row count checks, and record-level matching
- **Validation_Repository**: Database access layer for persisting and querying validation results with workspace isolation
- **Validation_Cache**: Redis cache layer for validation results following cache-aside pattern with PostgreSQL fallback
- **Bedrock_Analysis**: AI-powered analysis of validation discrepancies using AWS Bedrock to identify root causes and suggest workarounds
- **Source_Connection**: BigQuery database connection used to read source table metadata and data
- **Target_Connection**: Redshift database connection used to read target table metadata and data
- **Assessment_Report**: Existing assessment data containing source table metadata (columns, types, row counts) from the Assessment module
- **Migration_Record**: Existing migration record from MigrationBQRedshift tracking source/target configuration and row counts

## Requirements

### Requirement 1: Create Validation Run

**User Story:** As a database migration engineer, I want to create a validation run for a completed migration, so that I can verify data integrity between BigQuery source and Redshift target.

#### Acceptance Criteria

1. WHEN a user provides a migration_id, source_connection_id, target_connection_id, and list of table names, THE Validation_Service SHALL create a Validation_Run with status 'pending'
2. WHEN a user provides a migration_id without an explicit table list, THE Validation_Service SHALL retrieve the table list from the Migration_Record source_tables field
3. THE Validation_Service SHALL verify that the Migration_Record status is 'completed' before creating a Validation_Run
4. IF the Migration_Record status is not 'completed', THEN THE Validation_Service SHALL return an error indicating migration must complete before validation
5. THE Validation_Service SHALL verify that Source_Connection and Target_Connection exist and are active before creating a Validation_Run
6. IF Source_Connection or Target_Connection is inactive or missing, THEN THE Validation_Service SHALL return an error identifying the invalid connection
7. THE Validation_Service SHALL create one Validation_Table_Result record per table with status 'pending'
8. THE Validation_Service SHALL filter all database queries by workspace_id to maintain workspace isolation
9. THE Validation_Service SHALL log Validation_Run creation with migration_id, table count, and workspace_id to structured logs
10. THE Validation_Service SHALL store Validation_Run metadata in Redis with TTL of 15 minutes using key pattern "validation:run:{run_id}"


### Requirement 2: DDL Schema Comparison

**User Story:** As a database migration engineer, I want to compare source BigQuery DDL against target Redshift DDL for each table, so that I can detect structural differences introduced during migration.

#### Acceptance Criteria

1. WHEN DDL comparison starts for a table, THE Validation_Service SHALL retrieve source column metadata from the Assessment_Report (AssessmentColumn records) for the table
2. WHEN DDL comparison starts for a table, THE Validation_Service SHALL query the Target_Connection to retrieve target Redshift column metadata (column_name, data_type, is_nullable, ordinal_position)
3. THE Validation_Service SHALL compare each source column against its target counterpart using the Data_Type_Mapping rules for BigQuery-to-Redshift type equivalence
4. WHEN a source column has no matching target column, THE Validation_Service SHALL record a 'missing_column' discrepancy with column name and source data type
5. WHEN a target column has no matching source column, THE Validation_Service SHALL record an 'extra_column' discrepancy with column name and target data type
6. WHEN a source column data type does not match the expected Redshift equivalent per Data_Type_Mapping, THE Validation_Service SHALL record a 'type_mismatch' discrepancy with source type, target type, and expected type
7. WHEN a source column nullability differs from target column nullability, THE Validation_Service SHALL record a 'nullability_mismatch' discrepancy
8. THE Validation_Service SHALL store DDL comparison results as JSONB in the Validation_Table_Result ddl_comparison_result field
9. THE Validation_Service SHALL set Validation_Table_Result ddl_status to 'passed' when zero discrepancies are found, or 'failed' when one or more discrepancies exist
10. THE Validation_Service SHALL support configurable Data_Type_Mapping overrides via JSONB configuration on the Validation_Run

### Requirement 3: Row Count Validation

**User Story:** As a database migration engineer, I want to compare row counts between source and target tables, so that I can quickly detect data loss or duplication during migration.

#### Acceptance Criteria

1. WHEN row count validation starts for a table, THE Validation_Service SHALL query the Source_Connection to retrieve the current row count from BigQuery
2. WHEN row count validation starts for a table, THE Validation_Service SHALL query the Target_Connection to retrieve the current row count from Redshift
3. THE Validation_Service SHALL compare source row count against target row count and calculate the absolute difference and percentage difference
4. WHEN source row count equals target row count, THE Validation_Service SHALL set Validation_Table_Result row_count_status to 'passed'
5. WHEN source row count does not equal target row count, THE Validation_Service SHALL set Validation_Table_Result row_count_status to 'failed' and store source_count, target_count, and difference
6. THE Validation_Service SHALL store row count results in the Validation_Table_Result row_count_result JSONB field including source_count, target_count, difference, and percentage_difference
7. THE Validation_Service SHALL log row count comparison results with table name, source count, and target count
8. IF Source_Connection query fails, THEN THE Validation_Service SHALL set row_count_status to 'error' and store the error message
9. IF Target_Connection query fails, THEN THE Validation_Service SHALL set row_count_status to 'error' and store the error message
10. THE Validation_Service SHALL use query timeouts of 300 seconds for row count queries to prevent long-running operations

### Requirement 4: Record-Level Data Matching

**User Story:** As a database migration engineer, I want every record in the source table compared to its equivalent in the target table, so that I can detect any data corruption, missing rows, or value mismatches introduced during migration.

#### Acceptance Criteria

1. WHEN record-level matching starts for a table, THE Validation_Service SHALL determine a primary key or unique identifier for the table from Assessment_Report column metadata or user-provided configuration
2. IF no primary key or unique identifier can be determined, THEN THE Validation_Service SHALL use a hash of all column values as a row identifier and log a warning
3. THE Validation_Service SHALL read source data from BigQuery in configurable batch sizes (default 10000 rows) to manage memory usage
4. THE Validation_Service SHALL read target data from Redshift in matching batch sizes using the same ordering as source
5. FOR EACH source record, THE Validation_Service SHALL locate the corresponding target record by primary key and compare all column values
6. WHEN a source record has no matching target record, THE Validation_Service SHALL record a 'missing_in_target' discrepancy with the primary key value
7. WHEN a target record has no matching source record, THE Validation_Service SHALL record an 'extra_in_target' discrepancy with the primary key value
8. WHEN column values differ between matched source and target records, THE Validation_Service SHALL record a 'value_mismatch' discrepancy with column name, source value, and target value
9. THE Validation_Service SHALL apply data type-aware comparison logic accounting for BigQuery-to-Redshift type conversion differences (e.g., TIMESTAMP precision, NUMERIC scale)
10. THE Validation_Service SHALL store record-level match summary in Validation_Table_Result data_match_result JSONB field including total_compared, matched_count, missing_count, extra_count, mismatch_count, and sample discrepancies (capped at 100 samples)
11. THE Validation_Service SHALL set Validation_Table_Result data_match_status to 'passed' when zero discrepancies are found, or 'failed' when one or more discrepancies exist
12. IF record-level matching encounters an error, THEN THE Validation_Service SHALL set data_match_status to 'error', store the error message, and continue with remaining tables


### Requirement 5: Validation Run Orchestration

**User Story:** As a database migration engineer, I want the validation process to run as a background task across all selected tables, so that I can monitor progress without blocking the UI.

#### Acceptance Criteria

1. WHEN a Validation_Run is started, THE Validation_Service SHALL execute validation as a FastAPI background task
2. THE Validation_Service SHALL update Validation_Run status to 'running' and record started_at timestamp when execution begins
3. THE Validation_Service SHALL process tables sequentially, executing DDL comparison, row count validation, and record-level matching for each table in order
4. WHEN each table validation completes, THE Validation_Service SHALL update the Validation_Table_Result with results and set its status to 'completed' or 'failed'
5. WHEN each table validation completes, THE Validation_Service SHALL update Validation_Run progress_percentage based on completed tables divided by total tables
6. WHEN all tables complete validation, THE Validation_Service SHALL set Validation_Run status to 'completed' and record completed_at timestamp
7. IF any table validation encounters an unrecoverable error, THEN THE Validation_Service SHALL mark that table as 'error' and continue with remaining tables
8. IF all tables encounter errors, THEN THE Validation_Service SHALL set Validation_Run status to 'failed'
9. THE Validation_Service SHALL update Validation_Run summary statistics: tables_passed, tables_failed, tables_error
10. THE Validation_Service SHALL invalidate Redis cache for the Validation_Run after each table completes to ensure fresh data on next read
11. THE Validation_Service SHALL log start, progress, and completion events for each table with structured logging including run_id, table_name, and duration_ms

### Requirement 6: AI-Powered Discrepancy Analysis

**User Story:** As a database migration engineer, I want AI-powered analysis of validation discrepancies, so that I can understand root causes and get actionable workarounds without manual investigation.

#### Acceptance Criteria

1. WHEN a Validation_Run completes with one or more failed tables, THE Validation_Service SHALL invoke Bedrock_Analysis for each failed table
2. THE Validation_Service SHALL construct a prompt containing the table name, DDL discrepancies, row count differences, and sample record-level mismatches
3. THE Validation_Service SHALL invoke the Bedrock_Client with the constructed prompt using the configured Bedrock model
4. WHEN Bedrock returns analysis, THE Validation_Service SHALL parse the response to extract root_cause, impact_assessment, and recommended_workarounds
5. THE Validation_Service SHALL store Bedrock_Analysis results in the Validation_Table_Result ai_analysis JSONB field
6. IF Bedrock invocation fails, THEN THE Validation_Service SHALL log the error and set ai_analysis to null without failing the overall validation
7. THE Validation_Service SHALL include source and target database types (BigQuery, Redshift) in the prompt for context-aware analysis
8. THE Validation_Service SHALL limit prompt size to 10000 characters by truncating sample discrepancies if necessary
9. THE Validation_Service SHALL log Bedrock invocation duration and model_id for each analysis call
10. THE Validation_Service SHALL support configurable Bedrock model selection per Validation_Run

### Requirement 7: Validation Report Generation

**User Story:** As a database migration engineer, I want a comprehensive validation report showing pass/fail status per table with detailed issue descriptions, so that I can assess migration quality and take corrective action.

#### Acceptance Criteria

1. WHEN a user requests a validation report for a completed Validation_Run, THE Validation_Service SHALL generate a Validation_Report containing overall summary and per-table details
2. THE Validation_Report SHALL include overall summary: total_tables, tables_passed, tables_failed, tables_error, overall_status (passed/failed), started_at, completed_at, duration_seconds
3. THE Validation_Report SHALL include per-table details: table_name, ddl_status, row_count_status, data_match_status, overall_table_status
4. FOR EACH failed table, THE Validation_Report SHALL include DDL discrepancies list with discrepancy_type, column_name, source_value, target_value, and expected_value
5. FOR EACH failed table with row count mismatch, THE Validation_Report SHALL include source_count, target_count, difference, and percentage_difference
6. FOR EACH failed table with record-level mismatches, THE Validation_Report SHALL include total_compared, matched_count, mismatch_count, and sample discrepancies (up to 100)
7. FOR EACH failed table with Bedrock_Analysis, THE Validation_Report SHALL include root_cause, impact_assessment, and recommended_workarounds
8. THE Validation_Service SHALL cache the generated Validation_Report in Redis with TTL of 30 minutes using key pattern "validation:report:{run_id}"
9. THE Validation_Service SHALL return the Validation_Report as JSON via API endpoint
10. THE Validation_Report SHALL include migration_id, source_connection name, and target_connection name for traceability


### Requirement 8: Validation API Endpoints

**User Story:** As a frontend developer, I want RESTful API endpoints for data validation, so that I can build user interfaces for creating, monitoring, and reviewing validation runs.

#### Acceptance Criteria

1. THE System SHALL provide POST /api/validations endpoint accepting migration_id, source_connection_id, target_connection_id, tables (optional), bedrock_model, batch_size, type_mapping_overrides parameters to create and start a Validation_Run
2. THE System SHALL provide GET /api/validations endpoint returning a paginated list of Validation_Run records filtered by workspace_id with optional filters for migration_id and status
3. THE System SHALL provide GET /api/validations/{run_id} endpoint returning Validation_Run details including progress_percentage, status, and summary statistics
4. THE System SHALL provide GET /api/validations/{run_id}/tables endpoint returning all Validation_Table_Result records for a run with per-table status
5. THE System SHALL provide GET /api/validations/{run_id}/tables/{table_name} endpoint returning detailed Validation_Table_Result including ddl_comparison_result, row_count_result, data_match_result, and ai_analysis
6. THE System SHALL provide GET /api/validations/{run_id}/report endpoint returning the full Validation_Report as JSON
7. THE System SHALL provide DELETE /api/validations/{run_id} endpoint to delete a Validation_Run and all associated Validation_Table_Result records
8. THE System SHALL support pagination with query parameters page and page_size (default 20, max 100) on list endpoints
9. THE System SHALL validate workspace_id from request context matches resource workspace_id for all endpoints
10. THE System SHALL return HTTP 404 if a Validation_Run or Validation_Table_Result does not exist or belongs to a different workspace

### Requirement 9: Database Schema for Validation

**User Story:** As a database administrator, I want properly designed database tables for validation data, so that validation results are stored efficiently with appropriate indexes and constraints.

#### Acceptance Criteria

1. THE System SHALL create validation_runs table with columns: id, workspace_id, migration_id, source_connection_id, target_connection_id, bedrock_model, batch_size, type_mapping_overrides (JSONB), status, progress_percentage, tables_total, tables_passed, tables_failed, tables_error, started_at, completed_at, duration_seconds, created_by, created_at, updated_at
2. THE System SHALL create validation_table_results table with columns: id, run_id, workspace_id, table_name, dataset_name, ddl_status, ddl_comparison_result (JSONB), row_count_status, row_count_result (JSONB), data_match_status, data_match_result (JSONB), ai_analysis (JSONB), status, error_message, started_at, completed_at, duration_seconds, created_at, updated_at
3. THE System SHALL create indexes on validation_runs (workspace_id, migration_id, status)
4. THE System SHALL create indexes on validation_table_results (run_id, workspace_id, table_name, status)
5. THE System SHALL create foreign key constraint from validation_table_results.run_id to validation_runs.id with ON DELETE CASCADE
6. THE System SHALL use JSONB type for ddl_comparison_result, row_count_result, data_match_result, ai_analysis, and type_mapping_overrides to support flexible data structures
7. THE System SHALL use server_default func.current_timestamp() for created_at columns
8. THE System SHALL create Alembic migration script to create all validation tables with proper rollback support
9. THE System SHALL enforce NOT NULL constraint on workspace_id, migration_id, and run_id columns
10. THE System SHALL use BigInteger type for row count fields within JSONB to support tables with billions of rows

### Requirement 10: BigQuery-to-Redshift Data Type Mapping

**User Story:** As a database migration engineer, I want a well-defined mapping of BigQuery data types to Redshift equivalents, so that DDL comparison produces accurate results accounting for expected type transformations.

#### Acceptance Criteria

1. THE Validation_Service SHALL map BigQuery STRING to Redshift VARCHAR
2. THE Validation_Service SHALL map BigQuery INT64 to Redshift BIGINT
3. THE Validation_Service SHALL map BigQuery FLOAT64 to Redshift DOUBLE PRECISION
4. THE Validation_Service SHALL map BigQuery NUMERIC/BIGNUMERIC to Redshift DECIMAL with matching precision and scale
5. THE Validation_Service SHALL map BigQuery BOOL to Redshift BOOLEAN
6. THE Validation_Service SHALL map BigQuery TIMESTAMP to Redshift TIMESTAMP
7. THE Validation_Service SHALL map BigQuery DATE to Redshift DATE
8. THE Validation_Service SHALL map BigQuery TIME to Redshift TIME
9. THE Validation_Service SHALL map BigQuery BYTES to Redshift VARBYTE
10. THE Validation_Service SHALL map BigQuery ARRAY and STRUCT types to Redshift SUPER type
11. THE Validation_Service SHALL treat mapped type pairs as equivalent during DDL comparison (e.g., STRING vs VARCHAR is a pass, not a mismatch)
12. THE Validation_Service SHALL allow users to override default type mappings via type_mapping_overrides JSONB on the Validation_Run
13. THE Validation_Service SHALL store the default Data_Type_Mapping as a configurable constant, not hardcoded inline
14. FOR ALL defined type mappings, serializing the mapping to JSON then deserializing SHALL produce an equivalent mapping object (round-trip property)

### Requirement 11: Validation Caching

**User Story:** As a frontend developer, I want validation data cached for fast UI loading, so that repeated page views and report access do not re-query the database each time.

#### Acceptance Criteria

1. THE Validation_Cache SHALL implement cache-aside pattern with Redis as primary cache and PostgreSQL as fallback
2. THE Validation_Cache SHALL cache Validation_Run details with TTL of 15 minutes using key pattern "validation:run:{run_id}"
3. THE Validation_Cache SHALL cache Validation_Table_Result details with TTL of 15 minutes using key pattern "validation:table:{run_id}:{table_name}"
4. THE Validation_Cache SHALL cache Validation_Report with TTL of 30 minutes using key pattern "validation:report:{run_id}"
5. WHEN a Validation_Run status changes, THE Validation_Cache SHALL invalidate all cached keys for that run
6. WHEN a Validation_Table_Result is updated, THE Validation_Cache SHALL invalidate the cached key for that table result and the parent run
7. IF Redis is unavailable, THEN THE Validation_Cache SHALL fall back to PostgreSQL queries without raising errors
8. THE Validation_Cache SHALL log cache hit, miss, and error events for monitoring
9. THE Validation_Cache SHALL include workspace_id in cache key patterns to prevent cross-tenant data leakage
10. THE Validation_Cache SHALL serialize cached data as JSON with datetime fields converted to ISO 8601 strings


### Requirement 12: Validation Logging and Error Handling

**User Story:** As a database migration engineer, I want detailed logging and immediate error surfacing during validation, so that I can diagnose issues quickly given the high sensitivity of the data.

#### Acceptance Criteria

1. THE Validation_Service SHALL create structured log entries for each validation step: run_started, ddl_comparison_started, ddl_comparison_completed, row_count_started, row_count_completed, record_match_started, record_match_completed, ai_analysis_started, ai_analysis_completed, run_completed
2. THE Validation_Service SHALL include run_id, table_name, workspace_id, and duration_ms in every log entry
3. WHEN a validation step encounters an error, THE Validation_Service SHALL log the error with log_level 'ERROR' including stack trace and error context
4. WHEN a connection query times out, THE Validation_Service SHALL log the timeout with table_name, query_type, and timeout_seconds
5. THE Validation_Service SHALL store validation logs in PostgreSQL for audit trail persistence
6. THE Validation_Service SHALL send validation logs to CloudWatch for centralized monitoring
7. THE Validation_Service SHALL mask any sensitive data values in log messages, logging only column names and discrepancy types without raw data content
8. IF a critical error occurs (e.g., connection lost mid-validation), THEN THE Validation_Service SHALL immediately update Validation_Table_Result status to 'error' and continue with remaining tables
9. THE Validation_Service SHALL track and log total duration for each validation phase (DDL, row count, record match, AI analysis) per table
10. THE Validation_Service SHALL log a summary at run completion including tables_passed, tables_failed, tables_error, and total_duration_seconds

### Requirement 13: Frontend - Validation Dashboard Page

**User Story:** As a database migration engineer, I want a web interface to create, monitor, and review validation runs, so that I can manage the validation process and review results visually.

#### Acceptance Criteria

1. THE Validation_Dashboard SHALL display a list of Validation_Run records with columns: run_id, migration_name, status, progress_percentage, tables_passed, tables_failed, started_at, duration
2. THE Validation_Dashboard SHALL provide a "New Validation" button that opens a form to create a Validation_Run
3. THE Validation_Dashboard "New Validation" form SHALL provide dropdown selectors for migration, source_connection, and target_connection pre-populated from migration data
4. THE Validation_Dashboard SHALL provide filters for status (pending, running, completed, failed) and migration_id
5. THE Validation_Dashboard SHALL display status with color coding: green for passed, red for failed, yellow for running, gray for pending
6. THE Validation_Dashboard SHALL auto-refresh every 10 seconds when any Validation_Run has status 'running'
7. WHEN a user clicks a Validation_Run row, THE Validation_Dashboard SHALL navigate to the Validation Detail page
8. THE Validation_Dashboard SHALL support pagination with page size selector (10, 20, 50)
9. THE Validation_Dashboard SHALL display overall pass rate as a percentage across all completed runs
10. THE Validation_Dashboard SHALL filter all data by the current workspace_id

### Requirement 14: Frontend - Validation Detail Page

**User Story:** As a database migration engineer, I want a detailed view of a validation run showing per-table results, so that I can drill into specific table issues and review AI-generated analysis.

#### Acceptance Criteria

1. THE Validation_Detail_Page SHALL display Validation_Run summary: migration_name, status, progress bar, tables_passed, tables_failed, tables_error, started_at, completed_at, duration
2. THE Validation_Detail_Page SHALL display a table of Validation_Table_Result records with columns: table_name, ddl_status, row_count_status, data_match_status, overall_status
3. THE Validation_Detail_Page SHALL display per-column status icons: checkmark for passed, cross for failed, warning for error
4. WHEN a user clicks a table row, THE Validation_Detail_Page SHALL expand an inline detail panel showing DDL discrepancies, row count comparison, and record-level match summary
5. THE Validation_Detail_Page DDL detail panel SHALL display a side-by-side comparison of source columns versus target columns with mismatches highlighted
6. THE Validation_Detail_Page row count panel SHALL display source_count, target_count, difference, and percentage_difference
7. THE Validation_Detail_Page record match panel SHALL display matched_count, missing_count, extra_count, mismatch_count, and a scrollable list of sample discrepancies
8. WHEN Bedrock_Analysis is available for a failed table, THE Validation_Detail_Page SHALL display an "AI Analysis" section with root_cause, impact_assessment, and recommended_workarounds
9. THE Validation_Detail_Page SHALL provide a "Download Report" button to download the full Validation_Report as JSON
10. THE Validation_Detail_Page SHALL auto-refresh every 10 seconds while the Validation_Run status is 'running'

### Requirement 15: Security and Workspace Isolation

**User Story:** As a platform administrator, I want validation data fully isolated per workspace with encrypted credential handling, so that sensitive migration data is protected across tenants.

#### Acceptance Criteria

1. THE Validation_Repository SHALL include workspace_id filter in every database query
2. THE Validation_Service SHALL decrypt Source_Connection and Target_Connection credentials using KMS before establishing database connections
3. THE Validation_Service SHALL use decrypted credentials only in memory and discard them after connection is established
4. THE Validation_Service SHALL validate that the requesting user has access to the workspace before executing any validation operation
5. IF a user attempts to access a Validation_Run belonging to a different workspace, THEN THE System SHALL return HTTP 404 without revealing the resource exists
6. THE Validation_Service SHALL include workspace_id in all Redis cache keys to prevent cross-tenant cache access
7. THE Validation_Service SHALL log workspace_id in all audit log entries for traceability
8. THE Validation_Service SHALL sanitize error messages to exclude connection credentials, hostnames, or internal IP addresses before returning to the client
9. THE Validation_Service SHALL use parameterized queries for all database operations to prevent SQL injection
10. THE Validation_Service SHALL enforce rate limiting of 10 concurrent validation runs per workspace to prevent resource exhaustion


### Requirement 16: Testing - Unit Tests

**User Story:** As a developer, I want comprehensive unit tests for the validation module, so that I can verify validation logic works correctly and catch regressions early.

#### Acceptance Criteria

1. THE Test Suite SHALL include unit tests for Validation_Service.create_validation_run with valid and invalid inputs including sample payloads
2. THE Test Suite SHALL include unit tests for DDL comparison logic verifying detection of missing columns, extra columns, type mismatches, and nullability mismatches
3. THE Test Suite SHALL include unit tests for row count comparison logic verifying passed, failed, and error scenarios
4. THE Test Suite SHALL include unit tests for record-level matching logic verifying detection of missing records, extra records, and value mismatches
5. THE Test Suite SHALL include unit tests for Data_Type_Mapping verifying all BigQuery-to-Redshift type pairs produce correct equivalence results
6. THE Test Suite SHALL include unit tests for Validation_Repository verifying workspace_id filtering on all CRUD operations
7. THE Test Suite SHALL include unit tests for Validation_Cache verifying cache-aside pattern with Redis hit, miss, and fallback scenarios
8. THE Test Suite SHALL include unit tests for Validation_Report generation verifying correct aggregation of per-table results
9. THE Test Suite SHALL include unit tests for Bedrock_Analysis prompt construction verifying prompt contains table name, discrepancy details, and stays within size limits
10. THE Test Suite SHALL mock external dependencies (BigQuery client, Redshift client, Bedrock client, Redis) in all unit tests
11. THE Test Suite SHALL include sample payloads for valid validation run creation, invalid migration_id, missing connection, and edge cases (empty table list, single table, 100 tables)

### Requirement 17: Testing - Integration Tests

**User Story:** As a developer, I want integration tests for validation API endpoints, so that I can verify the full request-response cycle works correctly.

#### Acceptance Criteria

1. THE Test Suite SHALL include integration tests for POST /api/validations with valid payload returning 201 and Validation_Run details
2. THE Test Suite SHALL include integration tests for POST /api/validations with invalid migration_id returning 400 error
3. THE Test Suite SHALL include integration tests for POST /api/validations with inactive connection returning 400 error
4. THE Test Suite SHALL include integration tests for GET /api/validations returning paginated list filtered by workspace_id
5. THE Test Suite SHALL include integration tests for GET /api/validations/{run_id} returning Validation_Run details
6. THE Test Suite SHALL include integration tests for GET /api/validations/{run_id}/tables returning per-table results
7. THE Test Suite SHALL include integration tests for GET /api/validations/{run_id}/report returning full Validation_Report
8. THE Test Suite SHALL include integration tests for DELETE /api/validations/{run_id} returning 204 and cascading deletion of table results
9. THE Test Suite SHALL include integration tests verifying workspace isolation by attempting cross-workspace access returning 404
10. THE Test Suite SHALL include sample payloads for all API endpoint tests following the Arrange-Act-Assert pattern

### Requirement 18: Testing - Property-Based Tests

**User Story:** As a developer, I want property-based tests for validation logic, so that I can verify universal correctness properties hold across a wide range of inputs.

#### Acceptance Criteria

1. THE Test Suite SHALL include a property test verifying that Data_Type_Mapping round-trip (serialize to JSON then deserialize) produces an equivalent mapping for all defined type pairs
2. THE Test Suite SHALL include a property test verifying that DDL comparison with identical source and target schemas always produces zero discrepancies (idempotence of identity comparison)
3. THE Test Suite SHALL include a property test verifying that row count comparison with equal counts always produces 'passed' status and zero difference
4. THE Test Suite SHALL include a property test verifying that record-level matching with identical source and target datasets always produces zero mismatches
5. THE Test Suite SHALL include a property test verifying that the count of discrepancies from DDL comparison is always less than or equal to the total number of columns compared (metamorphic property)
6. THE Test Suite SHALL include a property test verifying that Validation_Report tables_passed plus tables_failed plus tables_error always equals tables_total (invariant property)
7. THE Test Suite SHALL use Hypothesis library with minimum 100 iterations per property test
8. THE Test Suite SHALL generate random column definitions (name, type, nullability) for DDL comparison property tests
9. THE Test Suite SHALL generate random row data for record-level matching property tests
10. THE Test Suite SHALL include a property test verifying that progress_percentage is always between 0 and 100 inclusive after any table completion update
