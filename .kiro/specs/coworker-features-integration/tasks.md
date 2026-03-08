# Implementation Plan: Coworker Features Integration

## Overview

This implementation plan integrates all missing features from coworker_version1 and coworker_version2 into the current DataMIQ implementation. The plan covers 10 major feature groups with comprehensive backend services, API endpoints, database schema, frontend UI components, testing infrastructure, and documentation.

The implementation follows a phased approach: database schema → backend services → API endpoints → frontend components → testing → documentation. Each phase builds on the previous, ensuring incremental validation and early error detection.

## Tasks

- [x] 1. Database Schema and Migrations
  - [x] 1.1 Create Alembic migration for conversion tables
    - Create conversion_jobs table with all columns, indexes, and constraints
    - Create conversion_batches table with foreign keys to connections
    - Create conversion_logs table with cascade delete on job_id
    - Add indexes on workspace_id, status, created_at for query optimization
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 38.1, 38.2, 38.3_
  
  - [x] 1.2 Create Alembic migration for history tracking tables
    - Create copy_history table with JSONB error_details column
    - Create task_history table with JSONB raw_result column
    - Create datasync_agents table with unique constraint on vm_ip
    - Add indexes on migration_id, status, started_at for audit queries
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5, 38.4, 38.5, 38.6_
  
  - [x] 1.3 Add downgrade functions to all migrations
    - Implement rollback logic for conversion tables
    - Implement rollback logic for history tables
    - Test migration and rollback in development environment
    - _Requirements: 38.7, 38.8_

- [x] 2. Backend Core Services - SQL Code Converter
  - [x] 2.1 Implement SQLGlotParser service
    - Create SQLGlotParser class with parse_and_transpile method
    - Support dialects: bigquery, redshift, postgres, mysql, snowflake, oracle, mssql
    - Implement format_sql with configurable indent width
    - Handle parsing errors with descriptive error messages
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.7_

  - [ ]* 2.2 Write property test for SQLGlot round-trip preservation
    - **Property 1: SQLGlot Round-Trip Preservation**
    - **Validates: Requirements 5.8**
    - Generate random SQL statements with Hypothesis
    - Verify parse→print→parse produces equivalent AST
    - Test with minimum 100 iterations across all supported dialects
    - _Requirements: 21.1_
  
  - [x] 2.3 Implement BedrockClient service
    - Create BedrockClient class with invoke_model method
    - Support model-specific payload formatting (Claude, Titan)
    - Implement exponential backoff retry for throttling errors (429, 503)
    - Load prompt templates from file system with variable substitution
    - Validate IAM permissions on initialization
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.9_
  
  - [x] 2.4 Implement ConversionService for standalone conversions
    - Create ConversionService.convert_standalone method
    - Attempt SQLGlot parsing first when use_sqlglot=true
    - Fallback to Bedrock on SQLGlot failure
    - Extract code from markdown blocks using unescape utility
    - Create Conversion_Log entries for each processing step
    - Filter all queries by workspace_id
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.9_
  
  - [x] 2.5 Implement ConversionService for batch conversions
    - Create ConversionService.convert_batch method
    - Create individual Conversion_Job records for each asset
    - Process jobs concurrently with configurable parallelism (default 5)
    - Update batch counters (completed_assets, failed_assets) atomically
    - Implement retry logic with exponential backoff
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.9_

- [x] 3. Backend Core Services - Export and Deploy
  - [x] 3.1 Implement ConversionExportService
    - Create export_single_job method generating SQL files
    - Create export_batch method generating ZIP archives
    - Upload to S3 with workspace-scoped prefix "workspace_{workspace_id}/conversions/"
    - Log export operations to Conversion_Log
    - _Requirements: 3.1, 3.2, 3.3, 3.7_
  
  - [x] 3.2 Implement ConversionDeployService
    - Create deploy_to_target method with KMS credential decryption
    - Execute target_code using appropriate database client
    - Support dry-run mode for validation without execution
    - Capture deployment errors with descriptive messages
    - _Requirements: 3.4, 3.5, 3.6, 3.8_


- [x] 4. Backend Core Services - History Tracking
  - [x] 4.1 Implement HistoryService for Copy History
    - Create create_copy_history method with status='running'
    - Create update_copy_history method calculating duration_seconds
    - Store complete COPY command text and metadata
    - Filter queries by workspace_id derived from migration ownership
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.6, 6.8_
  
  - [x] 4.2 Implement HistoryService for Task History
    - Create create_task_history method with DataSync task details
    - Store task_arn, agent_arn, agent_ip, source_uri, dest_uri
    - Update with files_transferred and bytes_transferred on completion
    - Handle agent_offline status with descriptive error messages
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_
  
  - [x] 4.3 Implement DataSync Agent Registry
    - Create register_datasync_agent method checking for existing vm_ip
    - Reuse existing agent_arn if VM IP already registered
    - Call AWS DataSync DescribeAgent API for health validation
    - Update last_used_at timestamp on agent usage
    - _Requirements: 8.1, 8.2, 8.3, 8.5, 8.7_
  
  - [ ]* 4.4 Write property test for agent registration idempotence
    - **Property 11: Agent Registration Idempotence**
    - **Validates: Requirements 8.2, 8.4**
    - Verify registering same VM IP returns same agent_arn
    - Test with minimum 100 iterations
    - _Requirements: 8.2, 8.4_

- [x] 5. Repository Layer Implementation
  - [x] 5.1 Implement ConversionRepository
    - Create create_job, get_job, update_job_status methods
    - Create create_batch, get_batch, get_batch_jobs methods
    - Create create_log method for Conversion_Log entries
    - Implement pagination for get_batch_jobs (default 50, max 200)
    - All queries filter by workspace_id
    - _Requirements: 1.9, 2.10, 9.5, 42.4_
  
  - [x] 5.2 Implement HistoryRepository
    - Create create_copy_history, get_copy_history_by_migration methods
    - Create create_task_history, get_task_history_by_migration methods
    - Implement pagination with configurable page size
    - Support sorting by started_at, completed_at, duration_seconds
    - Validate workspace_id through migration ownership
    - _Requirements: 6.8, 7.8, 10.3, 11.3_
  
  - [x] 5.3 Implement AgentRepository
    - Create register_agent, get_agent_by_vm_ip methods
    - Create list_agents, update_agent_status methods
    - Enforce unique constraint on vm_ip
    - Filter all queries by workspace_id
    - _Requirements: 8.1, 8.4, 12.2, 12.3_


- [x] 6. Caching Layer Implementation
  - [x] 6.1 Implement ConversionCache with cache-aside pattern
    - Cache Conversion_Job with key "conversion:job:{job_id}" TTL 1 hour
    - Cache active jobs (status='processing') with TTL 1 minute
    - Cache Conversion_Batch with key "conversion:batch:{batch_id}" TTL 1 hour
    - Implement Redis fallback to PostgreSQL on connection failure
    - Compress large target_code values before caching
    - _Requirements: 1.10, 28.1, 28.2, 28.3, 28.7, 28.10_
  
  - [ ]* 6.2 Write property test for cache invalidation on status change
    - **Property 12: Cache Invalidation on Status Change**
    - **Validates: Requirements 28.5**
    - Verify cache invalidated when job status changes
    - Test with minimum 100 iterations
    - _Requirements: 28.5_
  
  - [x] 6.3 Implement HistoryCache with cache-aside pattern
    - Cache active Copy_History with key "copy_history:active:{migration_id}" TTL 1 minute
    - Cache Copy_History lists with TTL 5 minutes
    - Cache active Task_History with TTL 1 minute
    - Cache DataSync_Agent registry with TTL 1 hour
    - Use Redis pipelines for bulk operations
    - _Requirements: 6.9, 7.10, 29.1, 29.2, 29.3, 29.5, 29.10_
  
  - [ ]* 6.4 Write property test for cache TTL correctness
    - **Property 18: Cache TTL Correctness**
    - **Validates: Requirements 1.10, 28.1, 29.1**
    - Verify Redis TTL matches configured values
    - Test with minimum 100 iterations
    - _Requirements: 1.10, 28.1, 29.1_

- [x] 7. API Endpoints - Conversion APIs
  - [x] 7.1 Implement POST /api/conversions/standalone endpoint
    - Accept source_code, source_dialect, target_dialect, asset_type parameters
    - Extract workspace_id from JWT token
    - Call ConversionService.convert_standalone
    - Return job_id, status, target_code, sqlglot_success
    - _Requirements: 9.1_
  
  - [x] 7.2 Implement POST /api/conversions/batch endpoint
    - Accept source_connection_id, target_connection_id, asset_list parameters
    - Validate connections belong to user's workspace
    - Call ConversionService.convert_batch
    - Return batch_id, status, total_assets, progress counters
    - _Requirements: 9.2, 23.4_
  
  - [x] 7.3 Implement GET /api/conversions/jobs/{job_id} endpoint
    - Validate workspace_id matches job's workspace
    - Return complete job details with target_code
    - Return 404 if job not found or workspace mismatch
    - _Requirements: 9.3, 23.5_
  
  - [x] 7.4 Implement GET /api/conversions/batches/{batch_id} endpoint
    - Return batch details with progress statistics
    - Include completed_assets, failed_assets counters
    - _Requirements: 9.4_


  - [x] 7.5 Implement GET /api/conversions/batches/{batch_id}/jobs endpoint
    - Return paginated list of jobs for batch
    - Support page and page_size query parameters
    - _Requirements: 9.5_
  
  - [x] 7.6 Implement POST /api/conversions/jobs/{job_id}/export endpoint
    - Generate SQL file or ZIP archive
    - Support export_format query parameter (sql, zip)
    - Validate workspace_id before export
    - _Requirements: 9.7, 23.8_
  
  - [x] 7.7 Implement POST /api/conversions/jobs/{job_id}/deploy endpoint
    - Accept target_connection_id and dry_run parameters
    - Validate workspace_id before deployment
    - Call ConversionDeployService.deploy_to_target
    - _Requirements: 9.8, 23.9_
  
  - [x] 7.8 Implement GET /api/conversions/jobs endpoint with filters
    - Support filters: workspace_id, status, asset_type, date_range
    - Implement pagination with default page_size=50, max=200
    - _Requirements: 9.9_

- [x] 8. API Endpoints - History APIs
  - [x] 8.1 Implement GET /api/copy-history endpoint
    - Support filters: migration_id, status, date_range
    - Support sorting by started_at, completed_at, rows_loaded, bytes_loaded
    - Return summary statistics (total_rows_loaded, success_count, failure_count)
    - Implement pagination with default page_size=50
    - _Requirements: 10.1, 10.5, 10.6, 10.7_
  
  - [x] 8.2 Implement GET /api/copy-history/{id} endpoint
    - Return detailed Copy_History record with copy_command
    - Validate workspace_id through migration ownership
    - Return 404 if record not found or workspace mismatch
    - _Requirements: 10.2, 10.10_
  
  - [x] 8.3 Implement GET /api/task-history endpoint
    - Support filters: migration_id, status, agent_ip, date_range
    - Return summary statistics (total_files_transferred, agent_offline_count)
    - Cache active tasks (status='running') with TTL 1 minute
    - _Requirements: 11.1, 11.8, 11.10_
  
  - [x] 8.4 Implement GET /api/task-history/{id} endpoint
    - Return detailed Task_History record including raw_result JSONB
    - Validate workspace_id through migration ownership
    - _Requirements: 11.2_
  
  - [x] 8.5 Implement POST /api/datasync-agents endpoint
    - Accept vm_ip and aws_region parameters
    - Call HistoryService.register_datasync_agent
    - Return agent_arn (new or existing)
    - _Requirements: 12.1_


  - [x] 8.6 Implement GET /api/datasync-agents endpoint
    - List all registered agents with status
    - Support filtering by status (online, offline, unknown)
    - _Requirements: 12.2, 12.7_
  
  - [x] 8.7 Implement DELETE /api/datasync-agents/{id} endpoint
    - Prevent deletion if agent used by active migrations
    - Return 409 Conflict if agent in use
    - _Requirements: 12.5, 12.6_

- [ ] 9. Checkpoint - Backend Services Complete
  - Ensure all backend services pass unit tests
  - Verify workspace isolation in all database queries
  - Confirm Redis fallback works when cache unavailable
  - Ask the user if questions arise

- [x] 10. Utility Functions and Enhanced Services
  - [x] 10.1 Implement code unescape utility
    - Create backend/utils/unescape.py with extract_code_from_markdown function
    - Extract code from markdown blocks (```sql ... ```)
    - Handle language specifiers and preserve whitespace
    - Return original text if no code blocks found
    - _Requirements: 36.1, 36.2, 36.3, 36.4, 36.5, 36.6, 36.7_
  
  - [ ]* 10.2 Write unit tests for unescape utility
    - Test extraction from markdown with language specifier
    - Test extraction from markdown without language specifier
    - Test multiple code blocks (extract first)
    - Test with sample inputs from various AI models
    - _Requirements: 36.10_
  
  - [x] 10.3 Implement prompt template management
    - Store templates in backend/prompts/ directory
    - Support variable substitution using {variable_name} syntax
    - Create default template bigquery-to-redshift-conversion.txt
    - Validate template file exists before conversion
    - Cache loaded templates with 1-hour TTL
    - _Requirements: 40.1, 40.2, 40.3, 40.4, 40.5, 40.9_
  
  - [x] 10.4 Implement retry strategy with exponential backoff
    - Create RetryStrategy class with execute_with_retry method
    - Retry on Bedrock throttling (429) and service errors (503)
    - Do NOT retry on validation errors (400)
    - Use delays: 5s, 10s, 20s with max_delay=60s
    - Increment retry_count in Conversion_Job
    - _Requirements: 41.1, 41.2, 41.3, 41.7_
  
  - [ ]* 10.5 Write property test for retry logic
    - **Property 14: Retry Logic for Transient Errors**
    - **Validates: Requirements 41.1, 41.2**
    - Verify exponential backoff delays
    - Test with minimum 100 iterations
    - _Requirements: 41.1, 41.2_


- [ ] 11. Security and Workspace Isolation
  - [ ] 11.1 Implement workspace isolation middleware for conversion APIs
    - Filter all Conversion_Job queries by workspace_id from JWT
    - Filter all Conversion_Batch queries by workspace_id from JWT
    - Filter all Conversion_Log queries by workspace_id from JWT
    - Return 404 for cross-workspace access attempts
    - Log isolation violations to audit log
    - _Requirements: 23.1, 23.2, 23.3, 23.5, 23.6, 23.10_
  
  - [ ]* 11.2 Write property test for workspace isolation in queries
    - **Property 2: Workspace Isolation in Queries**
    - **Validates: Requirements 1.9, 23.1, 24.1**
    - Verify all queries include workspace_id filter
    - Test with minimum 100 iterations
    - _Requirements: 1.9, 23.1, 24.1_
  
  - [ ] 11.3 Implement workspace isolation for history APIs
    - Filter Copy_History by workspace_id derived from migration ownership
    - Filter Task_History by workspace_id derived from migration ownership
    - Filter DataSync_Agent queries by workspace_id from JWT
    - Prevent agent deletion if used by other workspace migrations
    - _Requirements: 24.1, 24.2, 24.3, 24.6, 24.7, 24.9_
  
  - [ ]* 11.4 Write property test for workspace isolation in cache keys
    - **Property 3: Workspace Isolation in Cache Keys**
    - **Validates: Requirements 23.7, 24.8**
    - Verify all cache keys include workspace_id
    - Test with minimum 100 iterations
    - _Requirements: 23.7, 24.8_
  
  - [ ] 11.5 Implement AWS Bedrock access control
    - Use IAM role for Bedrock API access (not access keys)
    - Validate IAM permissions on service initialization
    - Implement rate limiting per workspace (configurable limit per hour)
    - Log all Bedrock invocations to CloudWatch with workspace_id
    - Validate prompt_template_path to prevent path traversal
    - _Requirements: 25.1, 25.2, 25.3, 25.4, 25.7_
  
  - [ ]* 11.6 Write property test for rate limiting enforcement
    - **Property 13: Rate Limiting Enforcement**
    - **Validates: Requirements 25.3**
    - Verify HTTP 429 returned when limit exceeded
    - Test with minimum 100 iterations
    - _Requirements: 25.3_

- [x] 12. Configuration Management
  - [x] 12.1 Add Bedrock and conversion configuration to .env
    - AWS_BEDROCK_REGION (default: us-east-1)
    - AWS_BEDROCK_DEFAULT_MODEL (default: anthropic.claude-v2)
    - CONVERSION_PROMPT_TEMPLATES_DIR (default: backend/prompts)
    - CONVERSION_MAX_RETRIES (default: 3)
    - CONVERSION_BATCH_PARALLELISM (default: 5)
    - BEDROCK_RATE_LIMIT_PER_WORKSPACE_HOUR (default: 100)
    - _Requirements: 26.1, 26.2, 26.3, 26.4, 26.6, 26.8_


  - [x] 12.2 Add DataSync and history configuration to .env
    - AWS_DATASYNC_REGION (default: us-east-1)
    - DATASYNC_AGENT_HEALTH_CHECK_INTERVAL_SECONDS (default: 300)
    - COPY_HISTORY_CACHE_TTL_SECONDS (default: 300)
    - TASK_HISTORY_CACHE_TTL_SECONDS (default: 60)
    - HISTORY_DEFAULT_PAGE_SIZE (default: 50)
    - HISTORY_MAX_PAGE_SIZE (default: 200)
    - _Requirements: 27.1, 27.2, 27.3, 27.4, 27.5, 27.6_
  
  - [x] 12.3 Update .env.example with all new configuration variables
    - Document all Bedrock, conversion, DataSync, and history settings
    - Provide example values for each configuration
    - _Requirements: 43.1_
  
  - [x] 12.4 Implement configuration validation on startup
    - Validate all required configuration present
    - Log warnings for missing optional values
    - Fail fast if critical configuration missing
    - _Requirements: 26.10, 27.10_

- [ ] 13. Checkpoint - Security and Configuration Complete
  - Verify workspace isolation prevents cross-workspace access
  - Confirm rate limiting works for Bedrock API calls
  - Test configuration loading from .env files
  - Ask the user if questions arise

- [ ] 14. Frontend - Standalone Converter Page
  - [ ] 14.1 Create StandaloneConverterPage component
    - Provide code editor for source SQL with syntax highlighting (Monaco/CodeMirror)
    - Add dropdown selectors for source_dialect and target_dialect
    - Add dropdown for asset_type (view, stored_procedure, function, trigger, table_ddl)
    - Add toggle for use_sqlglot with tooltip
    - Add dropdown for bedrock_model selection
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_
  
  - [ ] 14.2 Implement conversion submission and result display
    - Call POST /api/conversions/standalone on Convert button click
    - Display loading state during conversion
    - Display target_code in read-only editor with syntax highlighting
    - Show conversion metadata (duration, sqlglot_success, model_used)
    - _Requirements: 13.6, 13.7, 13.8_
  
  - [ ] 14.3 Add export and deploy functionality
    - Provide Export button to download SQL file
    - Provide Deploy button with confirmation dialog
    - Display diff view comparing source and target code side-by-side
    - _Requirements: 13.9, 13.10, 45.2_
  
  - [ ]* 14.4 Write component tests for StandaloneConverterPage
    - Test rendering all input fields and buttons
    - Test conversion request submission
    - Test displaying converted code on success
    - Test displaying error message on failure
    - _Requirements: 22.1, 22.2, 22.3, 22.4_


- [ ] 15. Frontend - Batch Converter Page
  - [ ] 15.1 Create BatchConverterPage component
    - Add dropdown selectors for source_connection and target_connection
    - Add multi-select list for asset_type (views, stored_procedures, functions, triggers)
    - Fetch available assets from source database when connection selected
    - Display asset list with checkboxes for selection
    - Add Select All and Deselect All buttons
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_
  
  - [ ] 15.2 Implement batch conversion workflow
    - Call POST /api/conversions/batch on Start Batch Conversion
    - Navigate to progress view showing real-time updates
    - Display progress bar with percentage and ETA
    - Show list of jobs with status indicators (pending, processing, completed, failed)
    - _Requirements: 14.7, 14.8, 14.9, 45.4_
  
  - [ ] 15.3 Add batch export functionality
    - Provide Export All button to download ZIP archive
    - Support pause and resume for batch conversions
    - _Requirements: 14.10, 45.5_
  
  - [ ]* 15.4 Write component tests for BatchConverterPage
    - Test fetching assets when source connection selected
    - Test enabling Start button only when assets selected
    - Test displaying real-time progress updates
    - _Requirements: 22.5, 22.6, 22.7_

- [ ] 16. Frontend - Copy History Page
  - [ ] 16.1 Create CopyHistoryPage component
    - Display table with columns: table_name, status, started_at, duration_seconds, rows_loaded, bytes_loaded
    - Add filters for migration_id, status, date_range
    - Add search box for schema_name or table_name
    - Display summary statistics (total_rows_loaded, total_bytes_loaded, success_rate)
    - _Requirements: 15.1, 15.2, 15.3, 15.4_
  
  - [ ] 16.2 Implement sorting and pagination
    - Support sorting by clicking column headers
    - Implement pagination with page size selector (25, 50, 100, 200)
    - Auto-refresh every 30 seconds for running operations
    - _Requirements: 15.5, 15.6, 15.9_
  
  - [ ] 16.3 Add detail modal and export
    - Display modal with full details on row click (copy_command, error_details)
    - Color-code status (green=completed, red=failed, yellow=running)
    - Provide Export to CSV button
    - Add data visualization charts (rows loaded over time)
    - _Requirements: 15.7, 15.8, 15.10, 45.6_
  
  - [ ]* 16.4 Write component tests for CopyHistoryPage
    - Test rendering table with pagination controls
    - Test filtering records by status
    - _Requirements: 22.8_


- [ ] 17. Frontend - Task History Page
  - [ ] 17.1 Create TaskHistoryPage component
    - Display table with columns: task_name, agent_ip, status, started_at, duration_seconds, files_transferred, bytes_transferred
    - Add filters for migration_id, status, agent_ip, date_range
    - Display summary statistics (total_files_transferred, agent_offline_count)
    - _Requirements: 16.1, 16.2, 16.3, 16.4_
  
  - [ ] 17.2 Implement sorting, pagination, and auto-refresh
    - Support sorting by clicking column headers
    - Implement pagination with page size selector
    - Auto-refresh every 30 seconds for running tasks
    - _Requirements: 16.5, 16.6, 16.9_
  
  - [ ] 17.3 Add detail modal and agent dashboard
    - Display modal with full details (source_uri, dest_uri, error_details, raw_result)
    - Color-code status (green=completed, red=failed, yellow=running, orange=agent_offline)
    - Provide Export to CSV button
    - Add agent status dashboard with online/offline indicators
    - _Requirements: 16.7, 16.8, 16.10, 45.7_
  
  - [ ]* 17.4 Write component tests for TaskHistoryPage
    - Test rendering table with pagination controls
    - Test filtering records by status
    - _Requirements: 22.9_

- [ ] 18. Frontend - UI Enhancements
  - [ ] 18.1 Add syntax highlighting and diff view
    - Integrate Monaco Editor or CodeMirror for SQL editing
    - Implement side-by-side diff view for source vs target comparison
    - _Requirements: 45.1, 45.2_
  
  - [ ] 18.2 Add browser features
    - Save conversion history in browser local storage
    - Implement browser notifications for long-running conversions
    - Add keyboard shortcuts (Ctrl+Enter to convert, Ctrl+S to export)
    - _Requirements: 45.3, 45.8, 45.9_
  
  - [ ] 18.3 Add contextual help
    - Provide tooltips explaining each configuration option
    - Add help icons with contextual documentation
    - _Requirements: 45.10_

- [ ] 19. Checkpoint - Frontend Complete
  - Test all frontend pages render correctly
  - Verify API integration works end-to-end
  - Confirm workspace isolation in UI (users see only their data)
  - Ask the user if questions arise


- [ ] 20. Testing Infrastructure Setup
  - [x] 20.1 Configure backend testing infrastructure
    - Create pytest.ini with test discovery patterns
    - Create conftest.py with shared fixtures (database, Redis, AWS mocks)
    - Organize tests in backend/tests/ (unit/, integration/, property/)
    - Configure test coverage reporting (minimum 80% backend)
    - _Requirements: 37.3, 37.4, 37.5, 37.9_
  
  - [ ] 20.2 Configure frontend testing infrastructure
    - Create test-setup.ts for jsdom environment
    - Create vitest.config.ts with test file patterns and coverage settings
    - Configure test coverage reporting (minimum 70% frontend)
    - Add test running scripts to package.json
    - _Requirements: 37.1, 37.2, 37.9, 37.10_
  
  - [x] 20.3 Create test fixtures and mocks
    - Create sample conversion jobs, batches, and history records
    - Create mock AWS Bedrock API responses
    - Create mock SQLGlot parser responses
    - _Requirements: 37.6, 37.7, 37.8_

- [ ] 21. Unit Tests - Conversion Service
  - [ ]* 21.1 Write unit test for standalone conversion with SQLGlot success
    - Test SQLGlot parsing succeeds and Bedrock not called
    - Verify sqlglot_success=true in result
    - _Requirements: 19.2_
  
  - [ ]* 21.2 Write unit test for SQLGlot fallback to Bedrock
    - Test SQLGlot parsing fails, Bedrock invoked
    - Verify target_code extracted from markdown
    - _Requirements: 19.3_
  
  - [ ]* 21.3 Write unit test for batch conversion job creation
    - Test correct number of Conversion_Job records created
    - Verify all jobs have batch_id reference
    - _Requirements: 19.4_
  
  - [ ]* 21.4 Write unit test for batch counter updates
    - Test completed_assets and failed_assets increment correctly
    - Verify batch status changes to 'completed' when all jobs done
    - _Requirements: 19.5_
  
  - [ ]* 21.5 Write unit test for retry logic with exponential backoff
    - Test Bedrock throttling triggers retry with delays
    - Verify retry_count increments
    - _Requirements: 19.6_
  
  - [ ]* 21.6 Write unit test for workspace isolation
    - Test all queries filter by workspace_id
    - Verify cross-workspace access returns 404
    - _Requirements: 19.7_
  
  - [ ]* 21.7 Write unit test for cache invalidation
    - Test cache invalidated when job status changes
    - _Requirements: 19.8_


- [ ] 22. Integration Tests - Conversion API
  - [ ]* 22.1 Write integration test for POST /api/conversions/standalone
    - Test with valid payload returns 200 and job_id
    - Test with invalid dialect returns 400 error
    - Mock AWS Bedrock API to avoid costs
    - _Requirements: 20.1, 20.2, 20.10_
  
  - [ ]* 22.2 Write integration test for POST /api/conversions/batch
    - Test with valid connections returns 200 and batch_id
    - Verify batch progress updates correctly
    - _Requirements: 20.3_
  
  - [ ]* 22.3 Write integration test for GET /api/conversions/jobs/{job_id}
    - Test returns complete job details with target_code
    - _Requirements: 20.4_
  
  - [ ]* 22.4 Write integration test for workspace isolation
    - Test 404 when accessing job from different workspace
    - Test 401 when JWT token missing
    - _Requirements: 20.7, 20.8_
  
  - [ ]* 22.5 Write integration test for export endpoint
    - Test POST /api/conversions/jobs/{job_id}/export generates SQL file
    - _Requirements: 20.6_

- [ ] 23. Property-Based Tests
  - [ ]* 23.1 Write property test for SQLGlot pretty-print idempotence
    - **Property: pretty_print(pretty_print(sql)) equals pretty_print(sql)**
    - **Validates: Requirements 21.8**
    - Test with minimum 100 iterations
    - _Requirements: 21.4, 21.8_
  
  - [ ]* 23.2 Write property test for transpilation semantic preservation
    - **Property: Transpilation preserves semantic meaning**
    - **Validates: Requirements 21.3**
    - Test with minimum 100 iterations across dialect pairs
    - _Requirements: 21.3_
  
  - [ ]* 23.3 Write property test for batch job count consistency
    - **Property 5: Batch Job Count Consistency**
    - **Validates: Requirements 2.2**
    - Verify N assets creates exactly N jobs
    - Test with minimum 100 iterations
    - _Requirements: 2.2_
  
  - [ ]* 23.4 Write property test for batch counter invariant
    - **Property 6: Batch Counter Invariant**
    - **Validates: Requirements 2.5, 2.6**
    - Verify completed_assets + failed_assets ≤ total_assets
    - Test with minimum 100 iterations
    - _Requirements: 2.5, 2.6_
  
  - [ ]* 23.5 Write property test for duration calculation accuracy
    - **Property 9: Duration Calculation Accuracy**
    - **Validates: Requirements 6.6**
    - Verify duration_seconds equals completed_at - started_at
    - Test with minimum 100 iterations
    - _Requirements: 6.6_


  - [ ]* 23.6 Write property test for compression round-trip
    - **Property 17: Compression Round-Trip**
    - **Validates: Requirements 42.6**
    - Verify compress→decompress produces original value
    - Test with minimum 100 iterations
    - _Requirements: 42.6_
  
  - [ ]* 23.7 Write property test for markdown code extraction
    - **Property 8: Markdown Code Extraction**
    - **Validates: Requirements 1.5, 36.1**
    - Verify extracted code has no markdown formatting
    - Test with minimum 100 iterations
    - _Requirements: 1.5, 36.1_
  
  - [ ]* 23.8 Write property test for batch concurrency limit
    - **Property 16: Batch Concurrency Limit**
    - **Validates: Requirements 42.1**
    - Verify processing jobs never exceed parallelism limit
    - Test with minimum 100 iterations
    - _Requirements: 42.1_

- [ ] 24. Checkpoint - Testing Complete
  - Verify all unit tests pass with 80%+ backend coverage
  - Verify all integration tests pass
  - Verify all 18 property tests pass with 100 iterations each
  - Confirm frontend tests achieve 70%+ coverage
  - Ask the user if questions arise

- [ ] 25. Logging and Monitoring Setup
  - [ ] 25.1 Implement CloudWatch logging for conversion operations
    - Log conversion job creations with workspace_id, user_id, dialects
    - Log Bedrock API invocations with model_id, duration_ms, cost_estimate
    - Log SQLGlot parsing attempts with success status
    - Log conversion failures with error_message and stack_trace
    - _Requirements: 30.1, 30.2, 30.3, 30.4_
  
  - [ ] 25.2 Create CloudWatch metrics for conversion operations
    - conversion_jobs_created, conversion_jobs_completed, conversion_jobs_failed per workspace
    - bedrock_api_calls, bedrock_api_errors, bedrock_api_latency per workspace
    - sqlglot_parse_success, sqlglot_parse_failure per dialect pair
    - _Requirements: 30.5, 30.6, 30.7_
  
  - [ ] 25.3 Create CloudWatch alarms for conversion operations
    - High conversion failure rate (>20% in 5 minutes)
    - Bedrock API throttling errors
    - _Requirements: 30.8, 30.9_
  
  - [ ] 25.4 Implement CloudWatch logging for history operations
    - Log Copy_History record creations with migration_id, table_name
    - Log COPY command completions with rows_loaded, bytes_loaded
    - Log Task_History record creations with agent_ip, source_uri
    - Log DataSync task completions with files_transferred, bytes_transferred
    - _Requirements: 31.1, 31.2, 31.3, 31.4_


  - [ ] 25.5 Create CloudWatch metrics for history operations
    - copy_commands_executed, copy_commands_succeeded, copy_commands_failed per migration
    - datasync_tasks_executed, datasync_tasks_succeeded, datasync_tasks_failed per migration
    - total_rows_loaded, total_bytes_loaded per migration
    - _Requirements: 31.5, 31.6, 31.7_
  
  - [ ] 25.6 Create CloudWatch alarms for history operations
    - High COPY failure rate (>10% in 10 minutes)
    - DataSync agent offline status
    - _Requirements: 31.8, 31.9_

- [ ] 26. Performance Optimization
  - [ ] 26.1 Implement database connection pooling
    - Configure minimum 10 and maximum 50 connections
    - Monitor connection pool status
    - _Requirements: 42.2_
  
  - [ ] 26.2 Implement Redis connection pooling
    - Configure minimum 5 and maximum 20 connections
    - Set appropriate timeouts (5 seconds)
    - _Requirements: 42.3_
  
  - [ ] 26.3 Optimize database queries
    - Add indexes on workspace_id, status, created_at
    - Implement query result caching for aggregations
    - Log slow queries (>1 second) to CloudWatch
    - _Requirements: 42.5, 42.9, 42.10_
  
  - [ ] 26.4 Implement compression for large values
    - Compress target_code values before database storage using gzip
    - Compress large cached values in Redis
    - _Requirements: 42.6_
  
  - [ ] 26.5 Optimize batch processing
    - Process jobs in parallel with configurable concurrency (default 5)
    - Use Redis pipelines for bulk cache operations
    - Implement lazy loading for Conversion_Log entries
    - _Requirements: 42.1, 42.7, 42.8_

- [ ] 27. Cost Management Features
  - [ ] 27.1 Implement Bedrock usage tracking
    - Create bedrock_usage table with workspace_id, model_id, invocation_count, estimated_cost
    - Calculate estimated cost based on model pricing from .env
    - Track total_input_tokens and total_output_tokens
    - _Requirements: 44.1, 44.2_
  
  - [ ] 27.2 Implement cost controls
    - Enforce rate limits per workspace to prevent runaway costs
    - Return HTTP 429 when workspace exceeds rate limit
    - Send CloudWatch alerts at 80% of rate limit
    - _Requirements: 44.3, 44.4, 44.7_
  
  - [ ] 27.3 Create cost reporting endpoints
    - GET /api/bedrock-usage endpoint for workspace usage statistics
    - Admin dashboard showing usage across all workspaces
    - Generate monthly cost reports per workspace
    - _Requirements: 44.5, 44.6, 44.10_


- [ ] 28. ChatAgent Integration
  - [ ] 28.1 Implement conversion intent recognition in ChatAgent
    - Recognize user requests to convert SQL code
    - Extract source_code, source_dialect, target_dialect from message
    - Route to ConversionService.convert_standalone
    - _Requirements: 39.1, 39.2, 39.3_
  
  - [ ] 28.2 Format conversion responses in chat
    - Display converted code with syntax highlighting
    - Provide follow-up options (Export, Deploy, Modify) as buttons
    - Maintain conversation context for iterative refinement
    - _Requirements: 39.4, 39.5, 39.6_
  
  - [ ] 28.3 Handle conversion errors in chat
    - Display error messages gracefully
    - Suggest corrections based on error type
    - Support batch conversion requests through chat
    - _Requirements: 39.7, 39.8_
  
  - [ ] 28.4 Ensure workspace isolation in ChatAgent
    - Respect workspace_id when accessing conversion features
    - Log all conversion requests to audit trail
    - _Requirements: 39.9, 39.10_

- [ ] 29. Documentation - API Endpoints
  - [ ] 29.1 Document conversion API endpoints
    - Create docs/api/conversions.md with OpenAPI/Swagger format
    - Document all request parameters with types and constraints
    - Document all response schemas with status codes
    - Provide cURL examples for all endpoints
    - Document authentication requirements (JWT token)
    - _Requirements: 32.1, 32.3, 32.4, 32.6, 32.8_
  
  - [ ] 29.2 Document history API endpoints
    - Create docs/api/history.md with OpenAPI/Swagger format
    - Document Copy History, Task History, and DataSync Agent endpoints
    - Document workspace isolation behavior and 404 responses
    - Document rate limiting policies for Bedrock endpoints
    - _Requirements: 32.2, 32.9, 32.10_

- [ ] 30. Documentation - Database Schema
  - [ ] 30.1 Document conversion tables
    - Create docs/database/tables/conversion_jobs.md
    - Create docs/database/tables/conversion_batches.md
    - Create docs/database/tables/conversion_logs.md
    - Document all columns, indexes, constraints, and foreign keys
    - _Requirements: 33.1, 33.2, 33.3_
  
  - [ ] 30.2 Document history tables
    - Create docs/database/tables/copy_history.md
    - Create docs/database/tables/task_history.md
    - Create docs/database/tables/datasync_agents.md
    - Provide example SQL queries for common operations
    - _Requirements: 33.4, 33.5, 33.6, 33.9_


  - [ ] 30.3 Create entity relationship diagrams
    - Document relationships between new and existing tables
    - Document cascade behaviors and data retention policies
    - _Requirements: 33.7, 33.8, 33.10_

- [ ] 31. Documentation - Service Architecture
  - [ ] 31.1 Document backend services
    - Create docs/backend/services/conversion_service.md
    - Create docs/backend/services/bedrock_client.md
    - Create docs/backend/services/sqlglot_parser.md
    - Create docs/backend/services/conversion_export_service.md
    - Create docs/backend/services/conversion_deploy_service.md
    - Include all methods with parameters, return types, and usage examples
    - _Requirements: 34.1, 34.2, 34.3, 34.4, 34.5_
  
  - [ ] 31.2 Document architecture patterns
    - Create architecture diagrams showing service dependencies
    - Document integration with existing ChatAgent module
    - Document error handling and retry strategies
    - Document caching strategies and invalidation patterns
    - _Requirements: 34.6, 34.7, 34.8, 34.9_

- [ ] 32. Documentation - Frontend Components
  - [ ] 32.1 Document frontend pages
    - Create docs/frontend/pages/standalone_converter_page.md
    - Create docs/frontend/pages/batch_converter_page.md
    - Create docs/frontend/pages/copy_history_page.md
    - Create docs/frontend/pages/task_history_page.md
    - Include props, state, and usage examples
    - _Requirements: 35.1, 35.2, 35.3, 35.4_
  
  - [ ] 32.2 Document frontend patterns
    - Document state management for conversion workflows
    - Document API integration using conversionApi.ts
    - Document accessibility features (ARIA labels, keyboard navigation)
    - _Requirements: 35.6, 35.7, 35.9_

- [ ] 33. Deployment Preparation
  - [ ] 33.1 Update dependencies
    - Add sqlglot to requirements.txt
    - Add boto3 bedrock client to requirements.txt
    - Update frontend package.json if needed
    - _Requirements: 43.5, 43.6_
  
  - [ ] 33.2 Create IAM policy documents
    - Create IAM policy for Bedrock API access (minimum permissions)
    - Create IAM policy for DataSync API access (minimum permissions)
    - _Requirements: 43.3, 43.4_
  
  - [ ] 33.3 Create deployment scripts
    - Create database migration execution script with rollback
    - Create smoke test script to verify features after deployment
    - Document rollback plan for each feature
    - _Requirements: 43.7, 43.8, 43.10_


  - [ ] 33.4 Create deployment checklist
    - Document all required environment variables
    - List new service dependencies
    - Provide deployment verification steps
    - _Requirements: 43.2, 43.9_

- [ ] 34. Final Integration and Testing
  - [ ] 34.1 Run end-to-end integration tests
    - Test standalone conversion workflow from UI to database
    - Test batch conversion with multiple assets
    - Test Copy History and Task History tracking
    - Test DataSync agent registration and reuse
    - Verify workspace isolation across all features
  
  - [ ] 34.2 Verify performance optimizations
    - Test database connection pooling under load
    - Verify Redis caching reduces database queries
    - Test batch processing with parallelism limit
    - Confirm slow query logging works
  
  - [ ] 34.3 Verify monitoring and alerting
    - Confirm CloudWatch metrics are being published
    - Test CloudWatch alarms trigger correctly
    - Verify audit logging captures all operations
  
  - [ ] 34.4 Security validation
    - Verify workspace isolation prevents cross-workspace access
    - Test rate limiting enforcement for Bedrock API
    - Confirm IAM roles work (not access keys)
    - Validate prompt template path restrictions

- [ ] 35. Final Checkpoint - All Features Complete
  - All 10 feature groups implemented and tested
  - All 45 requirements validated
  - All 18 correctness properties pass with 100 iterations
  - Documentation complete for APIs, database, services, and frontend
  - Deployment artifacts ready (migrations, IAM policies, scripts)
  - Ask the user if questions arise

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties with minimum 100 iterations
- Unit tests validate specific examples and edge cases with sample payloads
- All database queries MUST filter by workspace_id for multi-tenant security
- Redis fallback to PostgreSQL is CRITICAL - never let cache failures break the app
- Use IAM roles for AWS services, never hardcode access keys
- Checkpoints ensure incremental validation at key milestones
- Test coverage targets: 80% backend, 70% frontend
- All configuration must be in .env files, never hardcoded
