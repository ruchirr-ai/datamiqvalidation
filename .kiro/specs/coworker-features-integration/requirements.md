# Requirements Document: Coworker Features Integration

## Introduction

This document specifies requirements for integrating all missing features from coworker_version1 and coworker_version2 into the current DataMIQ implementation. The integration includes 10 major feature groups: SQL Code Converter Module, Enhanced Testing Infrastructure, AWS Bedrock Client Service, Copy History Module, Task History Module, DataSync Agent Registry, Enhanced Services, Utility Functions, Migration Scripts, and Documentation Updates.

The integration maintains workspace isolation, follows existing architecture patterns, implements comprehensive testing, and adheres to security best practices including KMS encryption and AWS Secrets Manager integration.

## Glossary

- **SQL_Code_Converter**: AI-powered service that converts SQL code between different database dialects using AWS Bedrock and SQLGlot
- **Conversion_Job**: Individual SQL code conversion request (standalone or part of a batch)
- **Conversion_Batch**: Group of conversion jobs tied to a migration project
- **Conversion_Log**: Structured log entry tracking conversion processing steps
- **SQLGlot**: Open-source SQL parser and transpiler library
- **AWS_Bedrock**: AWS managed service for foundation models and generative AI
- **Bedrock_Client**: Service wrapper for AWS Bedrock API interactions
- **Copy_History**: Audit trail of Redshift COPY commands executed during migrations
- **Task_History**: Audit trail of AWS DataSync tasks executed during migrations
- **DataSync_Agent**: AWS DataSync agent VM registration for GCS to S3 transfers
- **Prompt_Template**: Text template for structuring AI model requests
- **Asset_Type**: Type of database object being converted (view, stored_procedure, function, trigger, etc.)
- **Workspace_Isolation**: Security pattern ensuring all queries filter by workspace_id
- **Cache_Aside_Pattern**: Caching strategy with Redis primary and PostgreSQL fallback
- **Property_Based_Testing**: Testing approach using generated inputs to verify universal properties
- **Round_Trip_Property**: Property test verifying parse→print→parse produces equivalent result


## Requirements

### Requirement 1: SQL Code Converter - Standalone Conversion

**User Story:** As a database migration engineer, I want to convert individual SQL code snippets between database dialects, so that I can quickly test conversions and validate syntax transformations.

#### Acceptance Criteria

1. WHEN a user provides source SQL code, source dialect, target dialect, and asset type, THE SQL_Code_Converter SHALL create a Conversion_Job with status 'pending'
2. WHEN use_sqlglot is enabled and source/target dialects are supported, THE SQL_Code_Converter SHALL attempt SQLGlot parsing before invoking AWS_Bedrock
3. IF SQLGlot parsing succeeds, THEN THE SQL_Code_Converter SHALL set sqlglot_success to true and store the transpiled code
4. IF SQLGlot parsing fails OR use_sqlglot is disabled, THEN THE SQL_Code_Converter SHALL invoke AWS_Bedrock with the configured prompt template
5. WHEN AWS_Bedrock returns converted code, THE SQL_Code_Converter SHALL extract the code from markdown blocks and store it as target_code
6. THE SQL_Code_Converter SHALL create Conversion_Log entries for each processing step (template_loaded, sqlglot_parse_started, bedrock_invocation_started, etc.)
7. WHEN conversion completes successfully, THE SQL_Code_Converter SHALL set Conversion_Job status to 'completed'
8. IF conversion fails after max retries, THEN THE SQL_Code_Converter SHALL set status to 'failed' and store error_message
9. THE SQL_Code_Converter SHALL filter all database queries by workspace_id to maintain workspace isolation
10. THE SQL_Code_Converter SHALL cache conversion results in Redis with TTL of 1 hour using key pattern "conversion:job:{job_id}"


### Requirement 2: SQL Code Converter - Batch Conversion

**User Story:** As a database migration engineer, I want to convert multiple SQL assets in a single batch operation, so that I can efficiently convert all views, stored procedures, and functions for a migration project.

#### Acceptance Criteria

1. WHEN a user creates a batch conversion with source/target connections and asset list, THE SQL_Code_Converter SHALL create a Conversion_Batch with status 'pending'
2. THE SQL_Code_Converter SHALL create individual Conversion_Job records for each asset in the batch with batch_id reference
3. THE SQL_Code_Converter SHALL set Conversion_Batch total_assets to the count of jobs created
4. WHEN processing batch jobs, THE SQL_Code_Converter SHALL process jobs concurrently with configurable parallelism
5. WHEN each job completes, THE SQL_Code_Converter SHALL increment Conversion_Batch completed_assets counter
6. WHEN each job fails, THE SQL_Code_Converter SHALL increment Conversion_Batch failed_assets counter
7. WHEN all jobs complete, THE SQL_Code_Converter SHALL set Conversion_Batch status to 'completed'
8. IF any job fails after retries, THE Conversion_Batch SHALL still complete but track failed_assets count
9. THE SQL_Code_Converter SHALL support retry logic with exponential backoff for transient Bedrock failures
10. THE SQL_Code_Converter SHALL filter all queries by workspace_id and validate user access to source/target connections


### Requirement 3: SQL Code Converter - Export and Deploy

**User Story:** As a database migration engineer, I want to export converted SQL code to files or deploy directly to target databases, so that I can integrate conversions into my migration workflow.

#### Acceptance Criteria

1. WHEN a user requests export of a single conversion job, THE SQL_Code_Converter SHALL generate a SQL file with target_code and appropriate file extension
2. WHEN a user requests export of a batch, THE SQL_Code_Converter SHALL generate a ZIP archive containing all converted SQL files organized by asset_type
3. WHERE S3 export is configured, THE SQL_Code_Converter SHALL upload exported files to S3 bucket with workspace-scoped prefix "workspace_{workspace_id}/conversions/"
4. WHEN a user requests deployment of converted code, THE SQL_Code_Converter SHALL validate target connection credentials using KMS decryption
5. WHEN deploying to target database, THE SQL_Code_Converter SHALL execute target_code using appropriate database client
6. IF deployment fails, THEN THE SQL_Code_Converter SHALL capture error details and return descriptive error message
7. THE SQL_Code_Converter SHALL log all export and deploy operations to Conversion_Log with step names 'export_started', 'export_completed', 'deploy_started', 'deploy_completed'
8. THE SQL_Code_Converter SHALL support dry-run mode for deployment validation without execution
9. THE SQL_Code_Converter SHALL filter all operations by workspace_id
10. THE SQL_Code_Converter SHALL cache export file metadata in Redis with TTL of 30 minutes


### Requirement 4: AWS Bedrock Client Service

**User Story:** As a developer, I want a reusable AWS Bedrock client service, so that I can integrate AI-powered features across multiple modules without duplicating Bedrock integration code.

#### Acceptance Criteria

1. THE Bedrock_Client SHALL initialize with AWS region and credentials from environment configuration
2. WHEN listing available models, THE Bedrock_Client SHALL call Bedrock ListFoundationModels API and return model metadata
3. WHEN invoking a model, THE Bedrock_Client SHALL accept model_id, prompt, and optional parameters (temperature, max_tokens, top_p)
4. THE Bedrock_Client SHALL format requests according to model-specific payload structure (Claude, Titan, etc.)
5. WHEN Bedrock API returns response, THE Bedrock_Client SHALL extract generated text from model-specific response format
6. IF Bedrock API returns throttling error, THEN THE Bedrock_Client SHALL implement exponential backoff retry with max 3 attempts
7. IF Bedrock API returns validation error, THEN THE Bedrock_Client SHALL raise descriptive exception without retry
8. THE Bedrock_Client SHALL log all API calls to CloudWatch with request_id, model_id, and duration_ms
9. THE Bedrock_Client SHALL support loading prompt templates from file system with variable substitution
10. THE Bedrock_Client SHALL validate AWS IAM permissions on initialization and fail fast if Bedrock access is denied


### Requirement 5: SQLGlot Parser Integration

**User Story:** As a database migration engineer, I want automatic SQL parsing and transpilation using SQLGlot, so that I can get fast, deterministic conversions for supported dialect pairs without AI model invocation costs.

#### Acceptance Criteria

1. THE SQLGlot_Parser SHALL support parsing SQL from dialects: bigquery, redshift, postgres, mysql, snowflake, oracle, mssql
2. WHEN parsing SQL, THE SQLGlot_Parser SHALL call sqlglot.parse with source dialect and return abstract syntax tree
3. IF parsing succeeds, THEN THE SQLGlot_Parser SHALL transpile AST to target dialect using sqlglot.transpile
4. IF parsing fails with syntax error, THEN THE SQLGlot_Parser SHALL return error details with line number and position
5. THE SQLGlot_Parser SHALL validate that source and target dialects are different before attempting transpilation
6. WHEN transpilation completes, THE SQLGlot_Parser SHALL return formatted SQL with consistent indentation
7. THE SQLGlot_Parser SHALL support pretty-printing transpiled SQL with configurable indent width
8. FOR ALL valid SQL statements, parsing then printing then parsing SHALL produce equivalent AST (round-trip property)
9. THE SQLGlot_Parser SHALL handle multi-statement SQL by parsing and transpiling each statement independently
10. THE SQLGlot_Parser SHALL log parsing errors with sufficient context for debugging


### Requirement 6: Copy History Tracking

**User Story:** As a database migration engineer, I want to track all Redshift COPY commands executed during migrations, so that I can audit data loading operations and troubleshoot failures.

#### Acceptance Criteria

1. WHEN a Redshift COPY command is executed, THE System SHALL create a Copy_History record with status 'running'
2. THE Copy_History SHALL store the complete COPY command text, source URI, file format, compression type, and IAM role ARN
3. THE Copy_History SHALL record started_at timestamp when COPY command begins execution
4. WHEN COPY command completes successfully, THE System SHALL update Copy_History with status 'completed', completed_at timestamp, rows_loaded, and bytes_loaded
5. IF COPY command fails, THEN THE System SHALL update Copy_History with status 'failed', error_message, and error_details as JSONB
6. THE System SHALL calculate duration_seconds as difference between completed_at and started_at
7. THE System SHALL associate Copy_History records with migration_id and migration_name for traceability
8. THE System SHALL provide API endpoint to query Copy_History filtered by workspace_id, migration_id, status, and date range
9. THE System SHALL cache recent Copy_History records (last 24 hours) in Redis with TTL of 5 minutes
10. THE System SHALL support pagination for Copy_History queries with default page size of 50 records


### Requirement 7: Task History Tracking

**User Story:** As a database migration engineer, I want to track all AWS DataSync tasks executed during migrations, so that I can monitor GCS to S3 transfers and diagnose agent connectivity issues.

#### Acceptance Criteria

1. WHEN a DataSync task is created, THE System SHALL create a Task_History record with status 'running'
2. THE Task_History SHALL store task_arn, execution_arn, agent_arn, agent_ip, source_location_arn, and dest_location_arn
3. THE Task_History SHALL record source_uri (GCS path) and dest_uri (S3 path) for traceability
4. WHEN DataSync task completes, THE System SHALL update Task_History with status 'completed', files_transferred, bytes_transferred, and duration_seconds
5. IF DataSync task fails, THEN THE System SHALL update Task_History with status 'failed', error_message, error_code, and error_details as JSONB
6. IF DataSync agent is offline, THEN THE System SHALL set Task_History status to 'agent_offline' with descriptive error_message
7. THE System SHALL store raw DataSync API response in raw_result JSONB field for debugging
8. THE System SHALL associate Task_History records with migration_id and migration_name
9. THE System SHALL provide API endpoint to query Task_History filtered by workspace_id, migration_id, status, agent_ip, and date range
10. THE System SHALL cache active Task_History records (status='running') in Redis with TTL of 1 minute for real-time monitoring


### Requirement 8: DataSync Agent Registry

**User Story:** As a database migration engineer, I want to register and reuse DataSync agents across migrations, so that I can avoid duplicate agent registrations and efficiently manage agent VMs.

#### Acceptance Criteria

1. WHEN a user provides a DataSync agent VM IP address, THE System SHALL check DataSync_Agent registry for existing agent_arn
2. IF agent VM IP exists in registry, THEN THE System SHALL reuse the existing agent_arn without creating new agent registration
3. IF agent VM IP does not exist, THEN THE System SHALL register new agent with AWS DataSync and store agent_arn in DataSync_Agent table
4. THE System SHALL enforce unique constraint on vm_ip column to prevent duplicate registrations
5. WHEN registering new agent, THE System SHALL validate agent connectivity by calling AWS DataSync DescribeAgent API
6. THE System SHALL update DataSync_Agent status field to 'online', 'offline', or 'unknown' based on agent health check
7. THE System SHALL update last_used_at timestamp whenever an agent is used in a migration
8. THE System SHALL provide API endpoint to list all registered agents filtered by workspace_id and status
9. THE System SHALL cache agent registry data in Redis with TTL of 1 hour using key pattern "datasync:agent:{vm_ip}"
10. THE System SHALL support agent deletion only if no active migrations are using the agent


### Requirement 9: Conversion API Endpoints

**User Story:** As a frontend developer, I want RESTful API endpoints for SQL code conversion, so that I can build user interfaces for standalone and batch conversion workflows.

#### Acceptance Criteria

1. THE System SHALL provide POST /api/conversions/standalone endpoint accepting source_code, source_dialect, target_dialect, asset_type, bedrock_model, use_sqlglot parameters
2. THE System SHALL provide POST /api/conversions/batch endpoint accepting source_connection_id, target_connection_id, asset_list, bedrock_model, use_sqlglot parameters
3. THE System SHALL provide GET /api/conversions/jobs/{job_id} endpoint returning Conversion_Job details with target_code
4. THE System SHALL provide GET /api/conversions/batches/{batch_id} endpoint returning Conversion_Batch with progress statistics
5. THE System SHALL provide GET /api/conversions/batches/{batch_id}/jobs endpoint returning all Conversion_Job records for a batch with pagination
6. THE System SHALL provide GET /api/conversions/jobs/{job_id}/logs endpoint returning Conversion_Log entries for debugging
7. THE System SHALL provide POST /api/conversions/jobs/{job_id}/export endpoint generating SQL file or ZIP archive
8. THE System SHALL provide POST /api/conversions/jobs/{job_id}/deploy endpoint executing converted code on target database
9. THE System SHALL provide GET /api/conversions/jobs endpoint with filters for workspace_id, status, asset_type, date_range
10. THE System SHALL validate workspace_id in JWT token matches resource workspace_id for all endpoints


### Requirement 10: Copy History API Endpoints

**User Story:** As a frontend developer, I want RESTful API endpoints for Copy History, so that I can display Redshift COPY command audit trails in the UI.

#### Acceptance Criteria

1. THE System SHALL provide GET /api/copy-history endpoint with filters for workspace_id, migration_id, status, date_range
2. THE System SHALL provide GET /api/copy-history/{id} endpoint returning detailed Copy_History record
3. THE System SHALL provide GET /api/migrations/{migration_id}/copy-history endpoint returning all Copy_History for a migration
4. THE System SHALL support pagination with query parameters page and page_size (default 50, max 200)
5. THE System SHALL support sorting by started_at, completed_at, duration_seconds, rows_loaded, bytes_loaded
6. THE System SHALL return Copy_History records in descending order by started_at by default
7. THE System SHALL include summary statistics (total_rows_loaded, total_bytes_loaded, success_count, failure_count) in list responses
8. THE System SHALL validate workspace_id in JWT token matches migration workspace_id
9. THE System SHALL cache Copy_History list responses in Redis with TTL of 5 minutes
10. THE System SHALL return HTTP 404 if Copy_History record does not exist or belongs to different workspace


### Requirement 11: Task History API Endpoints

**User Story:** As a frontend developer, I want RESTful API endpoints for Task History, so that I can display DataSync task execution details and agent status in the UI.

#### Acceptance Criteria

1. THE System SHALL provide GET /api/task-history endpoint with filters for workspace_id, migration_id, status, agent_ip, date_range
2. THE System SHALL provide GET /api/task-history/{id} endpoint returning detailed Task_History record including raw_result
3. THE System SHALL provide GET /api/migrations/{migration_id}/task-history endpoint returning all Task_History for a migration
4. THE System SHALL provide GET /api/task-history/agents endpoint returning unique agent_ip values with latest status
5. THE System SHALL support pagination with query parameters page and page_size (default 50, max 200)
6. THE System SHALL support sorting by started_at, completed_at, duration_seconds, files_transferred, bytes_transferred
7. THE System SHALL return Task_History records in descending order by started_at by default
8. THE System SHALL include summary statistics (total_files_transferred, total_bytes_transferred, success_count, failure_count, agent_offline_count) in list responses
9. THE System SHALL validate workspace_id in JWT token matches migration workspace_id
10. THE System SHALL cache active Task_History records (status='running') in Redis with TTL of 1 minute


### Requirement 12: DataSync Agent API Endpoints

**User Story:** As a frontend developer, I want RESTful API endpoints for DataSync Agent management, so that I can display registered agents and their status in the UI.

#### Acceptance Criteria

1. THE System SHALL provide POST /api/datasync-agents endpoint accepting vm_ip, aws_region parameters to register new agent
2. THE System SHALL provide GET /api/datasync-agents endpoint returning all registered agents with status
3. THE System SHALL provide GET /api/datasync-agents/{id} endpoint returning detailed agent information
4. THE System SHALL provide PUT /api/datasync-agents/{id}/health-check endpoint to refresh agent status
5. THE System SHALL provide DELETE /api/datasync-agents/{id} endpoint to remove agent registration
6. THE System SHALL prevent agent deletion if any active migrations reference the agent_arn
7. THE System SHALL support filtering agents by status (online, offline, unknown)
8. THE System SHALL return agent last_used_at timestamp to identify unused agents
9. THE System SHALL validate workspace_id in JWT token for all agent operations
10. THE System SHALL cache agent list in Redis with TTL of 1 hour


### Requirement 13: Frontend - Standalone Converter Page

**User Story:** As a database migration engineer, I want a web interface for standalone SQL conversion, so that I can quickly test and validate SQL code conversions between dialects.

#### Acceptance Criteria

1. THE Standalone_Converter_Page SHALL provide code editor for source SQL input with syntax highlighting
2. THE Standalone_Converter_Page SHALL provide dropdown selectors for source_dialect and target_dialect
3. THE Standalone_Converter_Page SHALL provide dropdown selector for asset_type (view, stored_procedure, function, trigger, table_ddl)
4. THE Standalone_Converter_Page SHALL provide toggle for use_sqlglot option with tooltip explaining SQLGlot vs Bedrock
5. THE Standalone_Converter_Page SHALL provide dropdown for bedrock_model selection with available models
6. WHEN user clicks Convert button, THE Standalone_Converter_Page SHALL call POST /api/conversions/standalone and display loading state
7. WHEN conversion completes, THE Standalone_Converter_Page SHALL display target_code in read-only code editor with syntax highlighting
8. THE Standalone_Converter_Page SHALL display conversion metadata (duration, sqlglot_success, model_used)
9. THE Standalone_Converter_Page SHALL provide Export button to download converted SQL as file
10. THE Standalone_Converter_Page SHALL provide Deploy button to execute converted code on target database with confirmation dialog


### Requirement 14: Frontend - Batch Converter Page

**User Story:** As a database migration engineer, I want a web interface for batch SQL conversion, so that I can convert multiple database objects efficiently for migration projects.

#### Acceptance Criteria

1. THE Batch_Converter_Page SHALL provide dropdown selectors for source_connection and target_connection
2. THE Batch_Converter_Page SHALL provide multi-select list for asset_type (views, stored_procedures, functions, triggers)
3. WHEN user selects source_connection and asset_types, THE Batch_Converter_Page SHALL fetch available assets from source database
4. THE Batch_Converter_Page SHALL display asset list with checkboxes for selection
5. THE Batch_Converter_Page SHALL provide Select All and Deselect All buttons for asset selection
6. THE Batch_Converter_Page SHALL provide configuration options for bedrock_model, use_sqlglot, max_retries
7. WHEN user clicks Start Batch Conversion, THE Batch_Converter_Page SHALL call POST /api/conversions/batch and navigate to progress view
8. THE Batch_Converter_Page SHALL display real-time progress with completed_assets / total_assets counter
9. THE Batch_Converter_Page SHALL display list of conversion jobs with status indicators (pending, processing, completed, failed)
10. THE Batch_Converter_Page SHALL provide Export All button to download ZIP archive of all converted SQL files


### Requirement 15: Frontend - Copy History Page

**User Story:** As a database migration engineer, I want a web interface to view Copy History, so that I can audit Redshift COPY operations and troubleshoot data loading issues.

#### Acceptance Criteria

1. THE Copy_History_Page SHALL display table of Copy_History records with columns: table_name, status, started_at, duration_seconds, rows_loaded, bytes_loaded
2. THE Copy_History_Page SHALL provide filters for migration_id, status, date_range
3. THE Copy_History_Page SHALL provide search box to filter by schema_name or table_name
4. THE Copy_History_Page SHALL display summary statistics at top (total_rows_loaded, total_bytes_loaded, success_rate)
5. THE Copy_History_Page SHALL support sorting by clicking column headers
6. THE Copy_History_Page SHALL implement pagination with page size selector (25, 50, 100, 200)
7. WHEN user clicks a Copy_History row, THE Copy_History_Page SHALL display modal with full details including copy_command and error_details
8. THE Copy_History_Page SHALL display status with color coding (green=completed, red=failed, yellow=running)
9. THE Copy_History_Page SHALL auto-refresh every 30 seconds when viewing running COPY operations
10. THE Copy_History_Page SHALL provide Export to CSV button for filtered results


### Requirement 16: Frontend - Task History Page

**User Story:** As a database migration engineer, I want a web interface to view Task History, so that I can monitor DataSync task executions and diagnose agent connectivity issues.

#### Acceptance Criteria

1. THE Task_History_Page SHALL display table of Task_History records with columns: task_name, agent_ip, status, started_at, duration_seconds, files_transferred, bytes_transferred
2. THE Task_History_Page SHALL provide filters for migration_id, status, agent_ip, date_range
3. THE Task_History_Page SHALL provide search box to filter by task_name or table_name
4. THE Task_History_Page SHALL display summary statistics at top (total_files_transferred, total_bytes_transferred, success_rate, agent_offline_count)
5. THE Task_History_Page SHALL support sorting by clicking column headers
6. THE Task_History_Page SHALL implement pagination with page size selector (25, 50, 100, 200)
7. WHEN user clicks a Task_History row, THE Task_History_Page SHALL display modal with full details including source_uri, dest_uri, error_details, raw_result
8. THE Task_History_Page SHALL display status with color coding (green=completed, red=failed, yellow=running, orange=agent_offline)
9. THE Task_History_Page SHALL auto-refresh every 30 seconds when viewing running tasks
10. THE Task_History_Page SHALL provide Export to CSV button for filtered results


### Requirement 17: Database Schema - Conversion Tables

**User Story:** As a database administrator, I want properly designed database tables for conversion features, so that conversion data is stored efficiently with appropriate indexes and constraints.

#### Acceptance Criteria

1. THE System SHALL create conversion_jobs table with columns: id, workspace_id, batch_id, source_code, target_code, source_dialect, target_dialect, asset_type, asset_name, bedrock_model, aws_region, prompt_template_path, use_sqlglot, sqlglot_success, status, error_message, retry_count, created_by, created_at, updated_at
2. THE System SHALL create conversion_batches table with columns: id, workspace_id, migration_project_id, source_connection_id, target_connection_id, bedrock_model, aws_region, prompt_template_path, use_sqlglot, max_retries, status, total_assets, completed_assets, failed_assets, created_by, created_at, updated_at
3. THE System SHALL create conversion_logs table with columns: id, job_id, workspace_id, timestamp, log_level, step_name, message, duration_ms
4. THE System SHALL create indexes on conversion_jobs (workspace_id, batch_id, status, asset_type)
5. THE System SHALL create indexes on conversion_batches (workspace_id, status, migration_project_id)
6. THE System SHALL create indexes on conversion_logs (job_id, workspace_id)
7. THE System SHALL create foreign key constraint from conversion_jobs.batch_id to conversion_batches.id with ON DELETE SET NULL
8. THE System SHALL create foreign key constraint from conversion_logs.job_id to conversion_jobs.id with ON DELETE CASCADE
9. THE System SHALL create foreign key constraints from conversion_batches to connections table for source_connection_id and target_connection_id
10. THE System SHALL create Alembic migration script to create all conversion tables with proper rollback support


### Requirement 18: Database Schema - History Tables

**User Story:** As a database administrator, I want properly designed database tables for history tracking features, so that audit data is stored efficiently with appropriate indexes and constraints.

#### Acceptance Criteria

1. THE System SHALL create copy_history table with columns: id, migration_id, migration_name, schema_name, table_name, copy_command, source_uri, file_format, compression, iam_role_arn, status, started_at, completed_at, duration_seconds, rows_loaded, bytes_loaded, error_message, error_details, created_at
2. THE System SHALL create task_history table with columns: id, migration_id, migration_name, task_arn, execution_arn, task_name, task_type, agent_arn, agent_ip, source_location_arn, source_uri, dest_location_arn, dest_uri, table_name, status, started_at, completed_at, duration_seconds, files_transferred, bytes_transferred, error_message, error_code, error_details, raw_result, created_at
3. THE System SHALL create datasync_agents table with columns: id, vm_ip, agent_arn, aws_region, status, last_used_at, created_at, updated_at
4. THE System SHALL create indexes on copy_history (migration_id, status, started_at, schema_name, table_name)
5. THE System SHALL create indexes on task_history (migration_id, status, started_at, agent_ip, task_type)
6. THE System SHALL create unique index on datasync_agents (vm_ip)
7. THE System SHALL use JSONB type for error_details and raw_result columns to support flexible error data structures
8. THE System SHALL use BigInteger type for rows_loaded, bytes_loaded, files_transferred, bytes_transferred to support large data volumes
9. THE System SHALL use server_default func.current_timestamp() for created_at columns
10. THE System SHALL create Alembic migration script to create all history tables with proper rollback support


### Requirement 19: Testing - Unit Tests for Conversion Service

**User Story:** As a developer, I want comprehensive unit tests for the conversion service, so that I can verify conversion logic works correctly and catch regressions early.

#### Acceptance Criteria

1. THE Test Suite SHALL include unit test for standalone conversion with valid SQL input returning completed status
2. THE Test Suite SHALL include unit test for standalone conversion with SQLGlot enabled successfully transpiling supported dialect pairs
3. THE Test Suite SHALL include unit test for standalone conversion falling back to Bedrock when SQLGlot parsing fails
4. THE Test Suite SHALL include unit test for batch conversion creating correct number of Conversion_Job records
5. THE Test Suite SHALL include unit test for batch conversion updating completed_assets and failed_assets counters correctly
6. THE Test Suite SHALL include unit test for retry logic with exponential backoff on transient Bedrock failures
7. THE Test Suite SHALL include unit test for workspace isolation verifying queries filter by workspace_id
8. THE Test Suite SHALL include unit test for cache invalidation when conversion job status changes
9. THE Test Suite SHALL include sample payloads for all supported dialect pairs (BigQuery→Redshift, MySQL→PostgreSQL, etc.)
10. THE Test Suite SHALL achieve minimum 80% code coverage for conversion service module


### Requirement 20: Testing - Integration Tests for Conversion API

**User Story:** As a developer, I want comprehensive integration tests for conversion API endpoints, so that I can verify end-to-end conversion workflows function correctly.

#### Acceptance Criteria

1. THE Test Suite SHALL include integration test for POST /api/conversions/standalone with valid payload returning 200 and job_id
2. THE Test Suite SHALL include integration test for POST /api/conversions/standalone with invalid dialect returning 400 error
3. THE Test Suite SHALL include integration test for POST /api/conversions/batch with valid connections returning 200 and batch_id
4. THE Test Suite SHALL include integration test for GET /api/conversions/jobs/{job_id} returning complete job details with target_code
5. THE Test Suite SHALL include integration test for GET /api/conversions/batches/{batch_id}/jobs with pagination returning correct page size
6. THE Test Suite SHALL include integration test for POST /api/conversions/jobs/{job_id}/export generating downloadable SQL file
7. THE Test Suite SHALL include integration test for workspace isolation verifying 404 when accessing job from different workspace
8. THE Test Suite SHALL include integration test for authentication verifying 401 when JWT token is missing
9. THE Test Suite SHALL include sample payloads for success cases, validation errors, and edge cases
10. THE Test Suite SHALL mock AWS Bedrock API calls to avoid external dependencies and costs


### Requirement 21: Testing - Property-Based Tests for SQLGlot Parser

**User Story:** As a developer, I want property-based tests for the SQLGlot parser, so that I can verify round-trip properties and catch edge cases with generated inputs.

#### Acceptance Criteria

1. THE Test Suite SHALL include property test verifying FOR ALL valid SQL statements, parse→transpile→parse produces equivalent AST (round-trip property)
2. THE Test Suite SHALL include property test verifying FOR ALL SQL statements, parsing with invalid dialect returns descriptive error
3. THE Test Suite SHALL include property test verifying FOR ALL supported dialect pairs, transpilation preserves semantic meaning
4. THE Test Suite SHALL include property test verifying FOR ALL SQL statements, pretty-printing produces valid parseable SQL
5. THE Test Suite SHALL use Hypothesis library with minimum 100 iterations per property test
6. THE Test Suite SHALL generate SQL statements with varying complexity (simple SELECT, complex JOIN, subqueries, CTEs)
7. THE Test Suite SHALL generate SQL statements with edge cases (empty strings, very long identifiers, special characters)
8. THE Test Suite SHALL verify idempotence property: pretty_print(pretty_print(sql)) equals pretty_print(sql)
9. THE Test Suite SHALL verify invariant: length of transpiled SQL is within reasonable bounds of source SQL
10. THE Test Suite SHALL capture and report any failing examples for debugging


### Requirement 22: Testing - Frontend Component Tests

**User Story:** As a frontend developer, I want comprehensive component tests for conversion UI, so that I can verify user interactions and state management work correctly.

#### Acceptance Criteria

1. THE Test Suite SHALL include component test for StandaloneConverterPage rendering all input fields and buttons
2. THE Test Suite SHALL include component test for StandaloneConverterPage submitting conversion request on button click
3. THE Test Suite SHALL include component test for StandaloneConverterPage displaying converted code when API returns success
4. THE Test Suite SHALL include component test for StandaloneConverterPage displaying error message when API returns failure
5. THE Test Suite SHALL include component test for BatchConverterPage fetching assets when source connection is selected
6. THE Test Suite SHALL include component test for BatchConverterPage enabling Start button only when assets are selected
7. THE Test Suite SHALL include component test for BatchConverterPage displaying real-time progress updates
8. THE Test Suite SHALL include component test for CopyHistoryPage rendering table with pagination controls
9. THE Test Suite SHALL include component test for TaskHistoryPage filtering records by status
10. THE Test Suite SHALL achieve minimum 70% code coverage for frontend components


### Requirement 23: Security - Workspace Isolation for Conversion Features

**User Story:** As a security engineer, I want strict workspace isolation for all conversion features, so that users cannot access conversion data from other workspaces.

#### Acceptance Criteria

1. THE System SHALL filter all Conversion_Job queries by workspace_id from JWT token
2. THE System SHALL filter all Conversion_Batch queries by workspace_id from JWT token
3. THE System SHALL filter all Conversion_Log queries by workspace_id from JWT token
4. THE System SHALL validate source_connection_id and target_connection_id belong to user's workspace before creating batch
5. THE System SHALL return HTTP 404 when user attempts to access Conversion_Job from different workspace
6. THE System SHALL return HTTP 404 when user attempts to access Conversion_Batch from different workspace
7. THE System SHALL include workspace_id in all Redis cache keys to prevent cross-workspace cache pollution
8. THE System SHALL validate workspace_id matches between JWT token and resource before export operations
9. THE System SHALL validate workspace_id matches between JWT token and resource before deploy operations
10. THE System SHALL log all workspace isolation violations to audit log with user_id and attempted resource_id


### Requirement 24: Security - Workspace Isolation for History Features

**User Story:** As a security engineer, I want strict workspace isolation for all history tracking features, so that users cannot access audit data from other workspaces.

#### Acceptance Criteria

1. THE System SHALL filter all Copy_History queries by workspace_id derived from migration_id ownership
2. THE System SHALL filter all Task_History queries by workspace_id derived from migration_id ownership
3. THE System SHALL filter all DataSync_Agent queries by workspace_id from JWT token
4. THE System SHALL validate migration_id belongs to user's workspace before creating Copy_History record
5. THE System SHALL validate migration_id belongs to user's workspace before creating Task_History record
6. THE System SHALL return HTTP 404 when user attempts to access Copy_History from different workspace
7. THE System SHALL return HTTP 404 when user attempts to access Task_History from different workspace
8. THE System SHALL include workspace_id in all Redis cache keys for history data
9. THE System SHALL prevent DataSync_Agent deletion if agent is used by migrations in other workspaces
10. THE System SHALL log all workspace isolation violations to audit log with user_id and attempted resource_id


### Requirement 25: Security - AWS Bedrock Access Control

**User Story:** As a security engineer, I want secure AWS Bedrock access control, so that only authorized services can invoke AI models and costs are controlled.

#### Acceptance Criteria

1. THE System SHALL use IAM role for Bedrock API access, not access keys
2. THE System SHALL validate Bedrock IAM permissions on service initialization and fail fast if access is denied
3. THE System SHALL implement rate limiting for Bedrock API calls per workspace (configurable limit per hour)
4. THE System SHALL log all Bedrock API invocations to CloudWatch with workspace_id, user_id, model_id, prompt_length, response_length
5. THE System SHALL implement cost tracking by recording Bedrock API usage per workspace
6. THE System SHALL support configurable model whitelist to restrict which Bedrock models can be used
7. THE System SHALL validate prompt_template_path is within allowed directory to prevent path traversal attacks
8. THE System SHALL sanitize user-provided SQL code before including in Bedrock prompts to prevent prompt injection
9. THE System SHALL implement timeout for Bedrock API calls (default 60 seconds) to prevent hanging requests
10. THE System SHALL encrypt Bedrock API request/response logs at rest using KMS


### Requirement 26: Configuration - Bedrock and Conversion Settings

**User Story:** As a DevOps engineer, I want all Bedrock and conversion settings configurable via environment variables, so that I can deploy to different environments without code changes.

#### Acceptance Criteria

1. THE System SHALL load AWS_BEDROCK_REGION from .env file with default 'us-east-1'
2. THE System SHALL load AWS_BEDROCK_DEFAULT_MODEL from .env file with default 'anthropic.claude-v2'
3. THE System SHALL load CONVERSION_PROMPT_TEMPLATES_DIR from .env file with default 'backend/prompts'
4. THE System SHALL load CONVERSION_MAX_RETRIES from .env file with default 3
5. THE System SHALL load CONVERSION_RETRY_DELAY_SECONDS from .env file with default 5
6. THE System SHALL load CONVERSION_BATCH_PARALLELISM from .env file with default 5
7. THE System SHALL load CONVERSION_CACHE_TTL_SECONDS from .env file with default 3600
8. THE System SHALL load BEDROCK_RATE_LIMIT_PER_WORKSPACE_HOUR from .env file with default 100
9. THE System SHALL load BEDROCK_ALLOWED_MODELS as comma-separated list from .env file
10. THE System SHALL validate all configuration values on startup and log warnings for missing optional values


### Requirement 27: Configuration - DataSync and History Settings

**User Story:** As a DevOps engineer, I want all DataSync and history tracking settings configurable via environment variables, so that I can customize behavior per environment.

#### Acceptance Criteria

1. THE System SHALL load AWS_DATASYNC_REGION from .env file with default 'us-east-1'
2. THE System SHALL load DATASYNC_AGENT_HEALTH_CHECK_INTERVAL_SECONDS from .env file with default 300
3. THE System SHALL load COPY_HISTORY_CACHE_TTL_SECONDS from .env file with default 300
4. THE System SHALL load TASK_HISTORY_CACHE_TTL_SECONDS from .env file with default 60
5. THE System SHALL load HISTORY_DEFAULT_PAGE_SIZE from .env file with default 50
6. THE System SHALL load HISTORY_MAX_PAGE_SIZE from .env file with default 200
7. THE System SHALL load HISTORY_AUTO_REFRESH_INTERVAL_SECONDS from .env file with default 30
8. THE System SHALL load DATASYNC_TASK_TIMEOUT_SECONDS from .env file with default 3600
9. THE System SHALL load COPY_COMMAND_TIMEOUT_SECONDS from .env file with default 7200
10. THE System SHALL validate all configuration values are within reasonable bounds and log errors for invalid values


### Requirement 28: Caching Strategy - Conversion Data

**User Story:** As a system architect, I want efficient caching for conversion data, so that UI loads quickly and database load is minimized while maintaining data consistency.

#### Acceptance Criteria

1. THE System SHALL cache Conversion_Job records in Redis with key pattern "conversion:job:{job_id}" and TTL of 1 hour
2. THE System SHALL cache Conversion_Batch records in Redis with key pattern "conversion:batch:{batch_id}" and TTL of 1 hour
3. THE System SHALL cache active conversion jobs (status='processing') with TTL of 1 minute for real-time monitoring
4. THE System SHALL cache conversion job lists per workspace with key pattern "conversion:jobs:workspace:{workspace_id}:page:{page}" and TTL of 5 minutes
5. THE System SHALL invalidate Conversion_Job cache when job status changes from 'processing' to 'completed' or 'failed'
6. THE System SHALL invalidate Conversion_Batch cache when batch progress counters are updated
7. IF Redis is unavailable, THEN THE System SHALL fallback to PostgreSQL queries without caching
8. THE System SHALL implement cache-aside pattern with Redis primary and database fallback
9. THE System SHALL log cache hit/miss ratio to CloudWatch for monitoring
10. THE System SHALL compress large target_code values before caching to optimize Redis memory usage


### Requirement 29: Caching Strategy - History Data

**User Story:** As a system architect, I want efficient caching for history tracking data, so that audit queries are fast while maintaining real-time accuracy for active operations.

#### Acceptance Criteria

1. THE System SHALL cache Copy_History records with status='running' in Redis with key pattern "copy_history:active:{migration_id}" and TTL of 1 minute
2. THE System SHALL cache Copy_History list responses in Redis with key pattern "copy_history:list:workspace:{workspace_id}:filters:{hash}" and TTL of 5 minutes
3. THE System SHALL cache Task_History records with status='running' in Redis with key pattern "task_history:active:{migration_id}" and TTL of 1 minute
4. THE System SHALL cache Task_History list responses in Redis with key pattern "task_history:list:workspace:{workspace_id}:filters:{hash}" and TTL of 5 minutes
5. THE System SHALL cache DataSync_Agent registry in Redis with key pattern "datasync:agents:workspace:{workspace_id}" and TTL of 1 hour
6. THE System SHALL invalidate Copy_History cache when COPY command completes or fails
7. THE System SHALL invalidate Task_History cache when DataSync task completes or fails
8. THE System SHALL invalidate DataSync_Agent cache when agent status is updated
9. IF Redis is unavailable, THEN THE System SHALL fallback to PostgreSQL queries without caching
10. THE System SHALL use Redis pipelines for bulk cache operations to minimize network round trips


### Requirement 30: Logging and Monitoring - Conversion Operations

**User Story:** As a DevOps engineer, I want comprehensive logging and monitoring for conversion operations, so that I can troubleshoot issues and track system performance.

#### Acceptance Criteria

1. THE System SHALL log all conversion job creations to CloudWatch with workspace_id, user_id, source_dialect, target_dialect, asset_type
2. THE System SHALL log all Bedrock API invocations to CloudWatch with model_id, prompt_length, response_length, duration_ms, cost_estimate
3. THE System SHALL log all SQLGlot parsing attempts to CloudWatch with source_dialect, target_dialect, success status, error_message
4. THE System SHALL log all conversion failures to CloudWatch with job_id, error_message, retry_count, stack_trace
5. THE System SHALL create CloudWatch metrics for conversion_jobs_created, conversion_jobs_completed, conversion_jobs_failed per workspace
6. THE System SHALL create CloudWatch metrics for bedrock_api_calls, bedrock_api_errors, bedrock_api_latency per workspace
7. THE System SHALL create CloudWatch metrics for sqlglot_parse_success, sqlglot_parse_failure per dialect pair
8. THE System SHALL create CloudWatch alarms for high conversion failure rate (>20% in 5 minutes)
9. THE System SHALL create CloudWatch alarms for Bedrock API throttling errors
10. THE System SHALL store Conversion_Log entries in PostgreSQL for long-term audit trail with 90-day retention


### Requirement 31: Logging and Monitoring - History Operations

**User Story:** As a DevOps engineer, I want comprehensive logging and monitoring for history tracking operations, so that I can audit data loading and transfer activities.

#### Acceptance Criteria

1. THE System SHALL log all Copy_History record creations to CloudWatch with migration_id, table_name, copy_command_length
2. THE System SHALL log all COPY command completions to CloudWatch with migration_id, table_name, rows_loaded, bytes_loaded, duration_seconds
3. THE System SHALL log all Task_History record creations to CloudWatch with migration_id, agent_ip, source_uri, dest_uri
4. THE System SHALL log all DataSync task completions to CloudWatch with migration_id, agent_ip, files_transferred, bytes_transferred, duration_seconds
5. THE System SHALL create CloudWatch metrics for copy_commands_executed, copy_commands_succeeded, copy_commands_failed per migration
6. THE System SHALL create CloudWatch metrics for datasync_tasks_executed, datasync_tasks_succeeded, datasync_tasks_failed, datasync_agent_offline per migration
7. THE System SHALL create CloudWatch metrics for total_rows_loaded, total_bytes_loaded per migration
8. THE System SHALL create CloudWatch alarms for high COPY failure rate (>10% in 10 minutes)
9. THE System SHALL create CloudWatch alarms for DataSync agent offline status
10. THE System SHALL store all history records in PostgreSQL with 180-day retention policy


### Requirement 32: Documentation - API Endpoints

**User Story:** As a developer, I want comprehensive API documentation for all new endpoints, so that I can integrate with the conversion and history tracking features.

#### Acceptance Criteria

1. THE System SHALL provide OpenAPI/Swagger documentation for all conversion API endpoints in docs/api/conversions.md
2. THE System SHALL provide OpenAPI/Swagger documentation for all history API endpoints in docs/api/history.md
3. THE System SHALL document all request parameters with types, constraints, and examples
4. THE System SHALL document all response schemas with status codes and example payloads
5. THE System SHALL document all error responses with error codes and descriptions
6. THE System SHALL provide cURL examples for all API endpoints
7. THE System SHALL provide Python client examples for all API endpoints
8. THE System SHALL document authentication requirements (JWT token in Authorization header)
9. THE System SHALL document workspace isolation behavior and 404 responses for cross-workspace access
10. THE System SHALL document rate limiting policies for Bedrock-powered endpoints


### Requirement 33: Documentation - Database Schema

**User Story:** As a database administrator, I want comprehensive database schema documentation, so that I can understand table structures and relationships for new features.

#### Acceptance Criteria

1. THE System SHALL provide documentation for conversion_jobs table in docs/database/tables/conversion_jobs.md with all columns, indexes, and constraints
2. THE System SHALL provide documentation for conversion_batches table in docs/database/tables/conversion_batches.md with all columns, indexes, and constraints
3. THE System SHALL provide documentation for conversion_logs table in docs/database/tables/conversion_logs.md with all columns, indexes, and constraints
4. THE System SHALL provide documentation for copy_history table in docs/database/tables/copy_history.md with all columns, indexes, and constraints
5. THE System SHALL provide documentation for task_history table in docs/database/tables/task_history.md with all columns, indexes, and constraints
6. THE System SHALL provide documentation for datasync_agents table in docs/database/tables/datasync_agents.md with all columns, indexes, and constraints
7. THE System SHALL provide entity relationship diagrams showing relationships between new tables and existing tables
8. THE System SHALL document all foreign key relationships and cascade behaviors
9. THE System SHALL provide example SQL queries for common operations
10. THE System SHALL document data retention policies and archival strategies


### Requirement 34: Documentation - Service Architecture

**User Story:** As a developer, I want comprehensive service architecture documentation, so that I can understand how conversion and history tracking services integrate with existing modules.

#### Acceptance Criteria

1. THE System SHALL provide documentation for ConversionService in docs/backend/services/conversion_service.md with all methods and usage examples
2. THE System SHALL provide documentation for BedrockClient in docs/backend/services/bedrock_client.md with all methods and usage examples
3. THE System SHALL provide documentation for SQLGlotParser in docs/backend/services/sqlglot_parser.md with all methods and usage examples
4. THE System SHALL provide documentation for ConversionExportService in docs/backend/services/conversion_export_service.md with all methods and usage examples
5. THE System SHALL provide documentation for ConversionDeployService in docs/backend/services/conversion_deploy_service.md with all methods and usage examples
6. THE System SHALL provide architecture diagrams showing service dependencies and data flow
7. THE System SHALL document integration points with existing ChatAgent module
8. THE System SHALL document error handling patterns and retry strategies
9. THE System SHALL document caching strategies and cache invalidation patterns
10. THE System SHALL provide code examples for common service usage patterns


### Requirement 35: Documentation - Frontend Components

**User Story:** As a frontend developer, I want comprehensive component documentation, so that I can understand and maintain the conversion and history tracking UI components.

#### Acceptance Criteria

1. THE System SHALL provide documentation for StandaloneConverterPage in docs/frontend/pages/standalone_converter_page.md with props, state, and usage
2. THE System SHALL provide documentation for BatchConverterPage in docs/frontend/pages/batch_converter_page.md with props, state, and usage
3. THE System SHALL provide documentation for CopyHistoryPage in docs/frontend/pages/copy_history_page.md with props, state, and usage
4. THE System SHALL provide documentation for TaskHistoryPage in docs/frontend/pages/task_history_page.md with props, state, and usage
5. THE System SHALL provide documentation for conversion UI components in docs/frontend/components/conversion/ with props and examples
6. THE System SHALL document state management patterns for conversion workflows
7. THE System SHALL document API integration patterns using conversionApi.ts service
8. THE System SHALL provide component screenshots and UI mockups
9. THE System SHALL document accessibility features (ARIA labels, keyboard navigation)
10. THE System SHALL provide Storybook stories for all reusable conversion components


### Requirement 36: Utility Functions - Code Unescaping

**User Story:** As a developer, I want a utility function to unescape code output from AI models, so that markdown code blocks are properly extracted and cleaned.

#### Acceptance Criteria

1. THE Unescape_Utility SHALL extract code from markdown code blocks (```sql ... ```)
2. THE Unescape_Utility SHALL remove markdown formatting characters from code output
3. THE Unescape_Utility SHALL handle multiple code blocks in single response by extracting the first block
4. THE Unescape_Utility SHALL preserve whitespace and indentation within code blocks
5. THE Unescape_Utility SHALL handle code blocks with language specifiers (```sql, ```python, etc.)
6. THE Unescape_Utility SHALL handle code blocks without language specifiers (```)
7. THE Unescape_Utility SHALL return original text if no code blocks are found
8. THE Unescape_Utility SHALL handle escaped characters within code blocks correctly
9. THE Unescape_Utility SHALL be implemented in backend/utils/unescape.py with comprehensive docstring
10. THE Unescape_Utility SHALL include unit tests with sample inputs from various AI models


### Requirement 37: Enhanced Testing Infrastructure

**User Story:** As a developer, I want enhanced testing infrastructure with proper setup and configuration, so that I can run tests efficiently in CI/CD pipelines.

#### Acceptance Criteria

1. THE System SHALL provide test-setup.ts for frontend test configuration with jsdom environment
2. THE System SHALL provide vitest.config.ts with proper test file patterns and coverage settings
3. THE System SHALL configure pytest.ini with test discovery patterns and coverage settings
4. THE System SHALL provide conftest.py with shared fixtures for database, Redis, and AWS mocks
5. THE System SHALL organize tests in backend/tests/ with subdirectories: unit/, integration/, property/
6. THE System SHALL provide test fixtures for sample conversion jobs, batches, and history records
7. THE System SHALL provide mock implementations for AWS Bedrock API responses
8. THE System SHALL provide mock implementations for SQLGlot parser responses
9. THE System SHALL configure test coverage reporting with minimum thresholds (80% backend, 70% frontend)
10. THE System SHALL provide test running scripts in package.json and pytest commands


### Requirement 38: Migration Scripts - Database Migrations

**User Story:** As a database administrator, I want Alembic migration scripts for all new tables, so that I can deploy schema changes safely across environments.

#### Acceptance Criteria

1. THE System SHALL provide Alembic migration script to create conversion_jobs table with all columns, indexes, and constraints
2. THE System SHALL provide Alembic migration script to create conversion_batches table with all columns, indexes, and constraints
3. THE System SHALL provide Alembic migration script to create conversion_logs table with all columns, indexes, and constraints
4. THE System SHALL provide Alembic migration script to create copy_history table with all columns, indexes, and constraints
5. THE System SHALL provide Alembic migration script to create task_history table with all columns, indexes, and constraints
6. THE System SHALL provide Alembic migration script to create datasync_agents table with all columns, indexes, and constraints
7. THE System SHALL provide downgrade functions in all migration scripts to support rollback
8. THE System SHALL test all migration scripts in development environment before production deployment
9. THE System SHALL document migration dependencies and execution order
10. THE System SHALL provide migration verification script to validate schema after migration


### Requirement 39: Integration with Existing ChatAgent Module

**User Story:** As a product manager, I want SQL Code Converter integrated with ChatAgent, so that users can request code conversions through conversational interface.

#### Acceptance Criteria

1. WHEN user asks ChatAgent to convert SQL code, THE ChatAgent SHALL recognize conversion intent and route to ConversionService
2. THE ChatAgent SHALL extract source_code, source_dialect, target_dialect from user message using natural language processing
3. THE ChatAgent SHALL call ConversionService.convert_standalone with extracted parameters
4. WHEN conversion completes, THE ChatAgent SHALL format converted code in chat response with syntax highlighting
5. THE ChatAgent SHALL provide follow-up options (Export, Deploy, Modify) as interactive buttons
6. THE ChatAgent SHALL maintain conversation context to support iterative refinement of conversions
7. THE ChatAgent SHALL handle conversion errors gracefully and suggest corrections
8. THE ChatAgent SHALL support batch conversion requests through conversational interface
9. THE ChatAgent SHALL log all conversion requests initiated through chat to audit trail
10. THE ChatAgent SHALL respect workspace isolation when accessing conversion features


### Requirement 40: Prompt Template Management

**User Story:** As a developer, I want a flexible prompt template system, so that I can customize AI model prompts for different conversion scenarios without code changes.

#### Acceptance Criteria

1. THE System SHALL store prompt templates as text files in backend/prompts/ directory
2. THE System SHALL support variable substitution in templates using {variable_name} syntax
3. THE System SHALL provide default template backend/prompts/bigquery-to-redshift-conversion.txt for BigQuery to Redshift conversions
4. THE System SHALL support template variables: {source_dialect}, {target_dialect}, {asset_type}, {source_code}
5. THE System SHALL validate template file exists before conversion and fail fast with descriptive error
6. THE System SHALL support custom templates per workspace by checking workspace-specific directory first
7. THE System SHALL provide template validation utility to verify all required variables are present
8. THE System SHALL log template loading operations with template_path and variable values (excluding source_code)
9. THE System SHALL cache loaded templates in memory with 1-hour TTL to reduce file I/O
10. THE System SHALL provide API endpoint to list available prompt templates per dialect pair


### Requirement 41: Error Handling and Retry Logic

**User Story:** As a system architect, I want robust error handling and retry logic, so that transient failures don't cause permanent conversion failures.

#### Acceptance Criteria

1. WHEN Bedrock API returns throttling error (429), THE System SHALL retry with exponential backoff (5s, 10s, 20s)
2. WHEN Bedrock API returns service unavailable error (503), THE System SHALL retry with exponential backoff up to max_retries
3. WHEN Bedrock API returns validation error (400), THE System SHALL NOT retry and mark job as failed immediately
4. WHEN SQLGlot parsing fails, THE System SHALL fallback to Bedrock without retry
5. WHEN database connection fails during conversion, THE System SHALL retry database operation up to 3 times
6. WHEN Redis connection fails during caching, THE System SHALL log warning and continue without caching
7. THE System SHALL increment retry_count in Conversion_Job for each retry attempt
8. THE System SHALL store error_message with full context including retry history
9. THE System SHALL implement circuit breaker pattern for Bedrock API to prevent cascading failures
10. THE System SHALL provide manual retry endpoint for failed conversion jobs


### Requirement 42: Performance Optimization

**User Story:** As a system architect, I want performance optimizations for conversion and history features, so that the system scales efficiently with increasing load.

#### Acceptance Criteria

1. THE System SHALL process batch conversion jobs in parallel with configurable concurrency limit (default 5)
2. THE System SHALL use database connection pooling with minimum 10 and maximum 50 connections
3. THE System SHALL use Redis connection pooling with minimum 5 and maximum 20 connections
4. THE System SHALL implement pagination for all list endpoints with maximum page size of 200
5. THE System SHALL use database indexes on all frequently queried columns (workspace_id, status, created_at)
6. THE System SHALL compress large target_code values before storing in database using gzip compression
7. THE System SHALL implement lazy loading for Conversion_Log entries (load only when requested)
8. THE System SHALL use Redis pipelines for bulk cache operations to reduce network latency
9. THE System SHALL implement query result caching for expensive aggregation queries (summary statistics)
10. THE System SHALL monitor query performance and log slow queries (>1 second) to CloudWatch


### Requirement 43: Deployment and Environment Configuration

**User Story:** As a DevOps engineer, I want comprehensive deployment configuration, so that I can deploy all new features to production safely.

#### Acceptance Criteria

1. THE System SHALL update .env.example with all new configuration variables for Bedrock, conversion, DataSync, and history features
2. THE System SHALL provide deployment checklist documenting all required environment variables
3. THE System SHALL provide IAM policy document for Bedrock API access with minimum required permissions
4. THE System SHALL provide IAM policy document for DataSync API access with minimum required permissions
5. THE System SHALL update requirements.txt with new dependencies (sqlglot, boto3 bedrock client)
6. THE System SHALL update frontend package.json with new dependencies if any
7. THE System SHALL provide database migration execution script with rollback instructions
8. THE System SHALL provide smoke test script to verify all new features after deployment
9. THE System SHALL update deployment documentation with new service dependencies
10. THE System SHALL provide rollback plan for each new feature in case of deployment issues


### Requirement 44: Cost Management and Optimization

**User Story:** As a product manager, I want cost management features for Bedrock usage, so that I can control AI model invocation costs per workspace.

#### Acceptance Criteria

1. THE System SHALL track Bedrock API usage per workspace with columns: workspace_id, model_id, invocation_count, total_input_tokens, total_output_tokens, estimated_cost
2. THE System SHALL calculate estimated cost based on model pricing (configurable per model in .env)
3. THE System SHALL enforce rate limits per workspace to prevent runaway costs (configurable limit per hour)
4. WHEN workspace exceeds rate limit, THE System SHALL return HTTP 429 with retry-after header
5. THE System SHALL provide API endpoint to query Bedrock usage statistics per workspace
6. THE System SHALL provide admin dashboard showing Bedrock usage and costs across all workspaces
7. THE System SHALL send CloudWatch alerts when workspace approaches rate limit (80% threshold)
8. THE System SHALL support cost allocation tags for AWS billing integration
9. THE System SHALL provide cost optimization recommendations (use SQLGlot when possible)
10. THE System SHALL generate monthly cost reports per workspace for billing purposes


### Requirement 45: User Experience Enhancements

**User Story:** As a database migration engineer, I want intuitive user experience features, so that I can efficiently use conversion and history tracking capabilities.

#### Acceptance Criteria

1. THE Standalone_Converter_Page SHALL provide syntax highlighting for source and target SQL code using Monaco Editor or CodeMirror
2. THE Standalone_Converter_Page SHALL provide diff view to compare source and target code side-by-side
3. THE Standalone_Converter_Page SHALL save conversion history in browser local storage for quick access
4. THE Batch_Converter_Page SHALL provide progress bar with percentage completion and ETA
5. THE Batch_Converter_Page SHALL provide ability to pause and resume batch conversions
6. THE Copy_History_Page SHALL provide data visualization charts (rows loaded over time, success rate)
7. THE Task_History_Page SHALL provide agent status dashboard with online/offline indicators
8. THE System SHALL provide browser notifications when long-running conversions complete
9. THE System SHALL provide keyboard shortcuts for common actions (Ctrl+Enter to convert, Ctrl+S to export)
10. THE System SHALL provide contextual help tooltips explaining each configuration option


## Summary

This requirements document specifies the integration of 10 major feature groups from coworker versions into the current DataMIQ implementation:

1. **SQL Code Converter Module** - AI-powered SQL conversion using AWS Bedrock and SQLGlot with standalone and batch modes
2. **Copy History Tracking** - Audit trail for Redshift COPY commands with detailed metrics
3. **Task History Tracking** - Audit trail for AWS DataSync tasks with agent monitoring
4. **DataSync Agent Registry** - Centralized agent management to prevent duplicate registrations
5. **AWS Bedrock Client Service** - Reusable service for AI model integration across modules
6. **SQLGlot Parser Integration** - Fast, deterministic SQL transpilation for supported dialects
7. **Enhanced Testing Infrastructure** - Comprehensive unit, integration, and property-based tests
8. **Frontend UI Components** - User interfaces for conversion, history viewing, and monitoring
9. **Security and Workspace Isolation** - Strict workspace boundaries with comprehensive access control
10. **Documentation and Deployment** - Complete API, schema, and architecture documentation

All requirements follow EARS patterns and INCOSE quality rules, ensuring clarity, testability, and completeness. The integration maintains existing architecture patterns, implements comprehensive security measures, and provides production-ready features with proper monitoring, caching, and error handling.

## Next Steps

After requirements approval, proceed to design phase to create detailed technical specifications including:
- Database schema design with ER diagrams
- API endpoint specifications with request/response schemas
- Service layer architecture with class diagrams
- Frontend component hierarchy and state management
- Integration patterns with existing modules
- Deployment architecture and infrastructure requirements
