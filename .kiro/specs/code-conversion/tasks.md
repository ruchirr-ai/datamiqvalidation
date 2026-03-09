# Implementation Plan: Code Conversion Module

## Overview

Implement the Code Conversion module for DataMIQ, providing standalone SQL/code conversion and batch conversion capabilities powered by AWS Bedrock LLM with optional sqlglot pre-processing. The implementation follows the existing FastAPI router → service → repository layering, SQLAlchemy models with Alembic migrations, Redis caching with PostgreSQL fallback, and workspace-scoped tenant isolation.

## Tasks

- [x] 1. Create data models and database migration
  - [x] 1.1 Create ConversionJob and ConversionBatch SQLAlchemy models
    - Create `backend/models/conversion_job.py` with the ConversionJob model as specified in the design (id, workspace_id, batch_id, source_code, target_code, source_dialect, target_dialect, asset_type, asset_name, bedrock_model, aws_region, prompt_template_path, use_sqlglot, sqlglot_success, status, error_message, retry_count, created_by, created_at, updated_at)
    - Create `backend/models/conversion_batch.py` with the ConversionBatch model as specified in the design (id, workspace_id, migration_project_id, source_connection_id, target_connection_id, bedrock_model, aws_region, prompt_template_path, use_sqlglot, max_retries, status, total_assets, completed_assets, failed_assets, created_by, created_at, updated_at, jobs relationship)
    - Add indexes: idx_conversion_jobs_workspace, idx_conversion_jobs_batch, idx_conversion_jobs_status, idx_conversion_jobs_asset_type, idx_conversion_batches_workspace, idx_conversion_batches_status, idx_conversion_batches_project
    - Register models in `backend/models/__init__.py`
    - _Requirements: 5.1, 5.2_

  - [x] 1.2 Create Alembic migration for conversion tables
    - Generate Alembic migration that creates `conversion_batches` table first (referenced by FK), then `conversion_jobs` table
    - Include all indexes, foreign keys (batch_id → conversion_batches.id ON DELETE SET NULL, source_connection_id → connections.id, target_connection_id → connections.id), and default values as specified in the design
    - _Requirements: 5.1, 5.2_

  - [x] 1.3 Create Pydantic request/response schemas
    - Create `backend/models/conversion_schemas.py` with: StandaloneConversionRequest, BatchConversionRequest, AssetSelection, ConversionJobResponse, ConversionBatchResponse, PaginatedJobsResponse, S3ExportRequest, DeployRequest, and BedrockModelResponse
    - Include field validators for asset_type enum (TABLE_DDL, STORED_PROCEDURE, FUNCTION, VIEW, MATERIALIZED_VIEW, SCHEDULED_QUERY) and status enum (pending, in_progress, completed, failed, completed_with_errors)
    - _Requirements: 5.1, 5.2, 9.12_

  - [x] 1.4 Write unit tests for data models and schemas
    - Test ConversionJob and ConversionBatch model creation with valid data
    - Test Pydantic schema validation with valid payloads, invalid payloads (missing fields, wrong types), and edge cases (empty strings, very long source_code)
    - Test asset_type and status enum validation
    - _Requirements: 5.1, 5.2_

- [x] 2. Implement ConversionRepository
  - [x] 2.1 Create ConversionRepository with CRUD operations
    - Create `backend/repositories/conversion_repository.py` implementing: create_job, get_job, list_jobs (with pagination and filtering by status, asset_type, source_dialect), update_job, delete_job, create_batch, get_batch, list_batch_jobs, update_batch, get_completed_batch_jobs
    - All queries MUST include workspace_id filter for tenant isolation
    - list_jobs must support page/page_size pagination and return (list, total_count) tuple
    - _Requirements: 5.3, 5.4, 7.1_

  - [x] 2.2 Write unit tests for ConversionRepository
    - Test CRUD operations for ConversionJob and ConversionBatch with sample payloads
    - Test workspace isolation: verify queries with workspace_id=1 do not return records with workspace_id=2
    - Test pagination and filtering for list_jobs
    - Test cascade behavior on batch deletion
    - _Requirements: 5.3, 5.4, 7.1_

- [x] 3. Implement SqlGlotParser service
  - [x] 3.1 Create SqlGlotParser with parse and transpile logic
    - Create `backend/services/sqlglot_parser.py` implementing parse_and_transpile(source_code, source_dialect, target_dialect) → SqlGlotResult
    - SqlGlotResult contains: transpiled_code (str | None), success (bool), warning (str | None)
    - On parse failure, return success=False with descriptive warning; do not raise exceptions
    - Map platform dialect names (e.g., "bigquery", "redshift", "mongodb") to sqlglot dialect identifiers
    - Add `sqlglot` to `backend/requirements.txt`
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 3.2 Write unit tests for SqlGlotParser
    - Test successful parse and transpile of a BigQuery SELECT statement to Redshift dialect
    - Test parse failure with invalid SQL returns success=False and a warning
    - Test unsupported dialect gracefully returns success=False
    - _Requirements: 4.1, 4.2, 4.3_

- [x] 4. Implement BedrockClient service
  - [x] 4.1 Create BedrockClient for prompt template fetching and model invocation
    - Create `backend/services/bedrock_client.py` implementing: fetch_prompt_template(s3_path, region), render_prompt(template, source_code, source_dialect, target_dialect, asset_type, sqlglot_output), invoke_model(prompt, model_id, region), list_models(region)
    - Use boto3 with IAM role-based auth (no hardcoded credentials)
    - Implement exponential backoff retry for throttling/transient Bedrock errors up to configurable max_retries
    - Return descriptive error when S3 template path is invalid or template cannot be fetched
    - Log invocation metadata (model_id, region, token usage, latency, workspace_id) at INFO level; never log source/target code
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 7.3_

  - [x] 4.2 Write unit tests for BedrockClient
    - Test fetch_prompt_template with mocked S3 GetObject (success and failure cases)
    - Test render_prompt correctly substitutes template parameters
    - Test invoke_model with mocked Bedrock InvokeModel (success, throttling retry, failure)
    - Test list_models with mocked Bedrock ListFoundationModels
    - Test exponential backoff retry logic
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement ConversionCache service
  - [x] 6.1 Create ConversionCache with Redis caching and PostgreSQL fallback
    - Create `backend/services/conversion_cache.py` following the existing `session_cache.py` pattern
    - Implement: get_batch_status(batch_id), set_batch_status(batch_id, status_dict) with TTL 2 minutes, invalidate_batch_status(batch_id), get_discovered_assets(project_id), set_discovered_assets(project_id, assets) with TTL 15 minutes, invalidate_discovered_assets(project_id)
    - Key patterns: `conversion:batch:{batch_id}:status`, `conversion:assets:{project_id}`
    - If Redis is unavailable, fall back to PostgreSQL queries without degrading functionality
    - Log Redis errors as warnings
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x] 6.2 Write unit tests for ConversionCache
    - Test cache set/get/invalidate for batch status
    - Test cache set/get/invalidate for discovered assets
    - Test Redis fallback: when Redis raises ConnectionError, verify PostgreSQL fallback is used
    - Test TTL values are correctly applied
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [x] 7. Implement ConversionService core orchestration
  - [x] 7.1 Create ConversionService with standalone conversion logic
    - Create `backend/services/conversion_service.py` implementing create_standalone_conversion(request, workspace_id, user_id)
    - Orchestration flow: create ConversionJob (status=pending) → optionally run SqlGlotParser if use_sqlglot=True → fetch prompt template via BedrockClient → render prompt → invoke Bedrock model → update job with target_code and status=completed
    - On failure, retry up to max_retries with exponential backoff, then mark job as failed with error_message
    - Record sqlglot_success and use_sqlglot in job metadata
    - Validate workspace access before processing
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 4.1, 4.2, 4.3, 7.2_

  - [x] 7.2 Add batch conversion logic to ConversionService
    - Implement create_batch_conversion(request, workspace_id, user_id): create ConversionBatch (status=pending) → create individual ConversionJobs for each selected asset → start background task via FastAPI BackgroundTasks
    - Implement run_batch_background(batch_id, workspace_id): process jobs sequentially (configurable concurrency), update each job status, update batch progress counters, update Redis cache after each job, set final batch status to completed or completed_with_errors
    - _Requirements: 2.3, 2.4, 2.5, 2.6_

  - [x] 7.3 Add query, delete, and Bedrock model listing methods
    - Implement get_job, list_jobs (with pagination/filtering), delete_job, get_batch, list_batch_jobs, list_bedrock_models
    - All methods enforce workspace_id filtering
    - list_jobs supports filtering by status, asset_type, source_dialect
    - _Requirements: 5.3, 5.4, 9.2, 9.3, 9.4, 9.6, 9.7, 9.11_

  - [x] 7.4 Write unit tests for ConversionService
    - Test standalone conversion end-to-end with mocked BedrockClient and SqlGlotParser
    - Test standalone conversion with sqlglot enabled (success and parse failure fallback)
    - Test standalone conversion retry logic on Bedrock failure
    - Test batch conversion creates correct number of jobs
    - Test batch background processing updates progress counters
    - Test workspace isolation on get_job and list_jobs
    - Sample payloads for standalone: {source_code: "SELECT * FROM dataset.table", source_dialect: "bigquery", target_dialect: "redshift", asset_type: "TABLE_DDL", ...}
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.3, 2.4, 2.6, 4.2, 7.1, 7.2_

- [x] 8. Implement ExportService and DeployService
  - [x] 8.1 Create ExportService for .sql file generation and S3 export
    - Create `backend/services/conversion_export_service.py` implementing: generate_single_sql(job) → bytes, generate_batch_sql(jobs) → bytes, export_to_s3(jobs, s3_path, region)
    - Single .sql export: return target_code as downloadable file with filename `{asset_name}_{target_dialect}.sql`
    - Batch .sql export: combine all successfully converted assets separated by comment headers (`-- Asset: {asset_name} ({asset_type})`)
    - S3 export: write individual .sql files organized by asset_type subdirectories
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 8.2 Create DeployService for target database deployment
    - Create `backend/services/conversion_deploy_service.py` implementing deploy_batch(batch, jobs, target_connection) → DeployResult
    - Execute converted DDL/code assets against target connection in dependency order (TABLE_DDL first, then VIEWs, then STORED_PROCEDUREs/FUNCTIONs, then MATERIALIZED_VIEWs, then SCHEDULED_QUERYs)
    - Stop on first failure, report which assets succeeded and which failed
    - Use platform's existing KMS encryption service to decrypt target connection credentials
    - _Requirements: 6.4, 6.5, 7.4_

  - [x] 8.3 Write unit tests for ExportService and DeployService
    - Test single .sql generation produces correct filename and content
    - Test batch .sql generation includes comment headers separating assets
    - Test S3 export with mocked boto3 S3 client
    - Test deploy ordering: TABLE_DDL before VIEWs before procedures
    - Test deploy stops on first failure and reports partial results
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement ConversionRouter API endpoints
  - [x] 10.1 Create ConversionRouter with standalone and job endpoints
    - Create `backend/routers/conversion_router.py` with FastAPI router (prefix `/api/conversions`)
    - Implement: POST `/standalone` (201), GET `/jobs` (200, paginated with query params: page, page_size, status, asset_type, source_dialect), GET `/jobs/{job_id}` (200), DELETE `/jobs/{job_id}` (200)
    - Inject DB session, validate workspace access, use Pydantic request/response models
    - Return appropriate HTTP status codes: 201 for creation, 200 for success, 400 for validation, 401 for auth, 403 for authz, 404 for not found
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.12_

  - [x] 10.2 Add batch conversion endpoints to ConversionRouter
    - Implement: POST `/batch` (201), GET `/batch/{batch_id}` (200), GET `/batch/{batch_id}/jobs` (200), POST `/batch/{batch_id}/export/sql` (200, file download), POST `/batch/{batch_id}/export/s3` (200), POST `/batch/{batch_id}/deploy` (200)
    - Batch creation starts background task via FastAPI BackgroundTasks
    - _Requirements: 9.5, 9.6, 9.7, 9.8, 9.9, 9.10_

  - [x] 10.3 Add Bedrock models listing endpoint
    - Implement: GET `/models` with query param `region` (200)
    - _Requirements: 9.11_

  - [x] 10.4 Register ConversionRouter in main.py and import models
    - Import and include conversion_router in `backend/main.py` via `app.include_router(conversion_router)`
    - Import ConversionJob and ConversionBatch models in main.py to ensure SQLAlchemy registration
    - _Requirements: 9.1_

  - [x] 10.5 Write integration tests for ConversionRouter endpoints
    - Test POST /api/conversions/standalone with valid payload returns 201
    - Test POST /api/conversions/standalone with missing fields returns 400
    - Test GET /api/conversions/jobs returns paginated results
    - Test GET /api/conversions/jobs/{job_id} returns job detail, 404 for non-existent
    - Test DELETE /api/conversions/jobs/{job_id} returns 200, 404 for non-existent
    - Test POST /api/conversions/batch with valid payload returns 201
    - Test GET /api/conversions/batch/{batch_id} returns batch status
    - Test workspace isolation: request with wrong workspace returns 403/404
    - _Requirements: 9.1–9.12, 7.1, 7.2_

- [x] 11. Implement audit logging for conversion operations
  - [x] 11.1 Add audit logging to ConversionService
    - Use the existing `backend/services/audit_logger.py` to log all conversion operations
    - Log: standalone conversion created, batch conversion created, job deleted, batch export, batch deploy
    - Include workspace_id, user_id, and operation type in all audit log entries
    - Never log source_code or target_code content in audit logs
    - _Requirements: 7.5_

- [x] 12. Checkpoint - Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Implement frontend API client
  - [x] 13.1 Create ConversionApi service
    - Create `frontend/src/services/conversionApi.ts` following the existing `assessmentsApi.ts` pattern
    - Implement methods for all conversion endpoints: createStandaloneConversion, listJobs, getJob, deleteJob, createBatchConversion, getBatchStatus, listBatchJobs, exportBatchSql, exportBatchToS3, deployBatch, listBedrockModels
    - Include TypeScript interfaces for all request/response types
    - _Requirements: 9.1–9.11_

- [x] 14. Implement Standalone Converter UI
  - [x] 14.1 Create StandaloneConverterPage with configuration form and code panes
    - Create `frontend/src/pages/StandaloneConverterPage.tsx`
    - Configuration form: source dialect, target dialect, AWS region, Bedrock model dropdown (populated from GET /models), Prompt_Template S3 path, max retries, sqlGLOT toggle
    - Source code input pane: editable textarea with monospace font
    - Side-by-side result display: source (left) and converted code (right, read-only)
    - Copy-to-clipboard button and export-as-.sql button on the result pane
    - Loading indicator during conversion
    - Error message display on conversion failure
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 1.5, 1.6, 1.7_

  - [x] 14.2 Add conversion history list to StandaloneConverterPage
    - Add ConversionHistoryTable component below the converter showing past standalone conversions for the current workspace
    - Display: asset_name, source_dialect → target_dialect, status badge, created_at
    - Clicking a row loads the conversion result into the side-by-side panes
    - _Requirements: 10.6_

  - [x] 14.3 Create shared CodePane component
    - Create `frontend/src/components/conversion/CodePane.tsx` — read-only, syntax-highlighted code display with monospace font
    - Reusable across standalone and batch converter pages
    - _Requirements: 1.5, 1.7_

- [x] 15. Implement Batch Converter UI
  - [x] 15.1 Create BatchConverterPage with wizard steps
    - Create `frontend/src/pages/BatchConverterPage.tsx` with wizard-style multi-step flow
    - Step 1 — Asset Selection: display discovered assets grouped by Asset_Type with checkboxes and select-all per group
    - Step 2 — Configuration: pre-populated source/target connections from migration project, Bedrock model, template path, region, max retries, sqlglot toggle
    - Step 3 — Review & Confirm: summary of selected assets and configuration
    - _Requirements: 11.1, 11.2, 11.3_

  - [x] 15.2 Add progress monitoring and summary steps to BatchConverterPage
    - Step 4 — Progress: live progress bar, current asset being converted, completed/failed counts, error details per failed asset; polls GET /api/conversions/batch/{id} on interval
    - Step 5 — Summary: total converted, total failed, export action buttons (.sql download, S3 export, deploy to target DB)
    - _Requirements: 11.4, 11.5, 2.5, 2.7_

  - [x] 15.3 Create AssetSelector component
    - Create `frontend/src/components/conversion/AssetSelector.tsx` — grouped checkbox list for asset selection with select-all per Asset_Type group
    - _Requirements: 11.2, 2.1, 2.2_

  - [x] 15.4 Add batch history list to BatchConverterPage
    - Add ConversionHistoryTable showing past batch conversions for the current workspace
    - Display: batch id, migration project name, status badge, total/completed/failed counts, created_at
    - _Requirements: 11.6_

- [x] 16. Wire frontend routes and navigation
  - [x] 16.1 Add conversion pages to App router and navigation
    - Register StandaloneConverterPage and BatchConverterPage routes in `frontend/src/App.tsx`
    - Add navigation links to the sidebar/layout for "Code Converter" (standalone) and ensure batch converter is accessible from migration project context
    - _Requirements: 10.1, 11.1_

- [x] 17. Checkpoint - Ensure frontend builds without errors
  - Ensure all tests pass, ask the user if questions arise.

- [x] 18. Add dependencies and configuration
  - [x] 18.1 Update backend dependencies
    - Add `sqlglot` to `backend/requirements.txt`
    - Verify `boto3` is already present (for Bedrock and S3 access); add if missing
    - _Requirements: 4.1, 3.1_

  - [x] 18.2 Update .env.example with conversion-related configuration
    - Add example entries for any conversion-specific env vars (e.g., CONVERSION_BATCH_CONCURRENCY=1, default Bedrock region)
    - _Requirements: 3.1, 3.5_

- [x] 19. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 20. Local prompt template support
  - [x] 20.1 Add local file template loading to BedrockClient
    - Update `backend/services/bedrock_client.py` to support both local file paths (`prompts/template.txt` or `local://prompts/template.txt`) and S3 URIs (`s3://bucket/key`)
    - Add `_fetch_local_template()` method to read from `backend/prompts/` directory
    - Refactor S3 loading into `_fetch_s3_template()` method
    - Add `list_local_templates()` static method to scan `backend/prompts/` for `.txt` files and return metadata (path, name, description, source/target dialect)
    - _Requirements: 3.2, 3.3, 3.6_

  - [x] 20.2 Add templates listing API endpoint
    - Add `GET /api/conversions/templates` endpoint to `backend/routers/conversion_router.py`
    - Endpoint calls `BedrockClient.list_local_templates()` and returns the list
    - _Requirements: 3.6, 9.12_

  - [x] 20.3 Add frontend API method for templates
    - Add `PromptTemplate` interface and `listPromptTemplates()` method to `frontend/src/services/conversionApi.ts`
    - _Requirements: 3.6, 9.12_

  - [x] 20.4 Update StandaloneConverterPage with template dropdown
    - Replace text input with dropdown select populated from `GET /api/conversions/templates`
    - Auto-select first template on load
    - Include "Custom S3 Path..." option with conditional text input for manual S3 URI entry
    - _Requirements: 10.1, 3.6_

  - [x] 20.5 Update BatchConverterPage with template dropdown
    - Replace text input with dropdown select populated from `GET /api/conversions/templates`
    - Auto-select first template on load
    - Include "Custom S3 Path…" option with conditional text input for manual entry
    - Update review step to show template name instead of raw path
    - Fix validation to handle "custom" selection correctly
    - _Requirements: 11.3, 3.6_

  - [x] 20.6 Create BigQuery to Redshift prompt template
    - Create `backend/prompts/bigquery-to-redshift-conversion.txt` with comprehensive conversion guidelines
    - Include 10 conversion guideline categories: semi-structured data, date/time, table architecture, error handling, procedural logic, window functions, string functions, data type mappings, aggregation, performance optimization
    - Structured JSON output with converted_sql, accuracy_score, risks_and_issues, and optimization_recommendations
    - Template uses `{{ASSET_TYPE}}`, `{{ASSET_NAME}}`, `{{SOURCE_DIALECT}}`, `{{TARGET_DIALECT}}`, `{{SOURCE_CODE}}`, `{{SQLGLOT_OUTPUT}}` placeholders
    - _Requirements: 3.2_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Backend uses Python + FastAPI; frontend uses React + TypeScript
- All database queries must include workspace_id for tenant isolation
- Redis caching follows the existing session_cache.py pattern with PostgreSQL fallback
- AWS credentials use IAM roles — no hardcoded secrets
