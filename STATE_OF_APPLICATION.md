# DataMIQ — State of the Application
**Prepared for:** CTO Review
**Date:** July 6, 2026
**Prepared by:** Lead Technical Architect (Kiro AI)
**Classification:** Internal Technical Reference

---

## Table of Contents
1. [Latest Codebase Status](#1-latest-codebase-status)
2. [Current Code Modules — Breakdown by Section](#2-current-code-modules--breakdown-by-section)
3. [API-Based Approach & API Registry](#3-api-based-approach--api-registry)
4. [Integration & Data Flow Documentation](#4-integration--data-flow-documentation)

---

## 1. Latest Codebase Status

### Repository Overview

| Property | Detail |
|---|---|
| **Primary Active Branch** | `prajwal-dev` (HEAD) |
| **Parallel Dev Branch** | `datamiq-dev` (merged into prajwal-dev) |
| **Contributor Branch** | `muthu-dev` (merged via explicit merge commits) |
| **Backend Runtime** | Python 3.13 (CPython), FastAPI, Uvicorn |
| **Frontend Runtime** | Node.js, React 18, TypeScript 5.3, Vite 5 |
| **Database** | PostgreSQL (SQLAlchemy ORM, Alembic migrations) |
| **Cache** | Redis (hiredis driver) |
| **Infrastructure** | AWS (KMS, Secrets Manager, S3, Redshift, Glue, DataSync) |


### Recent Git Commits (Latest 25)

| Commit | Description |
|---|---|
| `076bf05` | **HEAD** — fix: ClickHouse converter — correct model IDs, fix JSON parsing, structured result UI |
| `f6bca8e` | merge: resolve conflicts with datamiq-dev — keep comprehensive BQ-to-ClickHouse prompt |
| `688444c` | **feat: BQ to Iceberg migration — full feature implementation with tests** |
| `2bd87a4` | Add ClickHouse to Code Converter: target dialect + prompt template |
| `e65a251` | Merge muthu-dev: view filtering, custom ORDER BY per table |
| `04357a6` | Add custom per-table ORDER BY UI for ClickHouse migration |
| `7e31fb2` | Filter out views from migration table selection (backend + frontend) |
| `17e12e9` | Add SESSION_USER, CURRENT_USER to system functions exclusion list |
| `489a858` | Add tooltips for partition/clustering columns; profile actual STRING max lengths |
| `77b5e0a` | Increase BI repeat threshold from 3 to 10 occurrences in 30 days |
| `1763107` | Remove migration cost rate calculations from TCO UI — show only total |
| `1e74226` | Fix: remove character_maximum_length, parse max from STRING(N) notation |
| `6e24c3a` | Fix STRUCT/ARRAY type detection: strip angle brackets before matching base type |
| `18f0f94` | Smart VARCHAR sizing: use max_length from BQ schema, default 65535 when unknown |
| `f122d50` | Remove TCO calculation details from UI, add version/created_by to report summary |
| `0903832` | Fix UDF detection, default TCO region from dataset location |
| `0a57915` | **Add ClickHouse migration support: connection, wizard, execution engine, DB persistence** |
| `8828b7d` | Switch frontend font from Inter to Satoshi |
| `7f7d57b` | Switch PDF report font from Helvetica to Satoshi |
| `fefbbde` | Update PDF report: add RG provisioned + migration cost breakdown to TCO section |
| `a1061b1` | Preserve analyze mode when re-running assessment |
| `5027086` | Fix: fall back to REST API (with num_bytes) when TABLE_STORAGE not enabled |

### Key Structural Milestones Integrated
- **BQ → Apache Iceberg** migration pipeline is fully implemented (orchestrator, type mapper, partition mapper, Glue catalog integration, S3 Tables adapter, schema evolution, dedup guard, cost engine, Athena verifier, validation service — backed by 35+ property & unit tests).
- **ClickHouse migration** target added as both a migration pathway and a SQL conversion dialect.
- **Production hardening** spec for Iceberg in progress (`.kiro/specs/iceberg-production-hardening`).
- **Validation Dashboard** module complete (data-validation-module spec implemented).
- **SQL Code Conversion** module complete (Bedrock LLM-backed, multi-dialect: BQ→Redshift, BQ→ClickHouse, SQL Server→Redshift, Sybase→Redshift, DB2→Redshift).
- **KMS envelope encryption** for all database connection credentials complete (35 Alembic schema versions).


---

## 2. Current Code Modules — Breakdown by Section

### 2.1 High-Level Architecture Map

```
datamiq/
├── backend/                    ← Python FastAPI monolith (single-port, multi-router)
│   ├── main.py                 ← App entry point, router registration, lifespan events
│   ├── database.py             ← SQLAlchemy engine, session factory, QueuePool config
│   ├── routers/                ← 20 FastAPI routers (API surface)
│   ├── services/               ← Business logic layer
│   │   ├── bq_redshift_migration/  ← BQ→Redshift pipeline (3 pathways)
│   │   └── bq_iceberg_migration/   ← BQ→Iceberg pipeline (full sub-package)
│   ├── repositories/           ← Data access layer (SQLAlchemy queries)
│   ├── models/                 ← SQLAlchemy ORM models
│   ├── shared/                 ← Cross-cutting concerns (middleware, Redis, config)
│   ├── utils/                  ← Utilities (retry, SQL dependency parser, timezone)
│   ├── constants/              ← Default field configurations
│   ├── prompts/                ← LLM prompt templates (5 source→target combinations)
│   ├── alembic/                ← 35 versioned DB schema migrations
│   └── tests/                  ← unit/, integration/, property/ test suites
├── frontend/                   ← React 18 + TypeScript SPA (Vite)
│   └── src/
│       ├── pages/              ← 30+ page-level components
│       ├── components/         ← Reusable UI components (ui/, migrations/, assessments/, etc.)
│       ├── services/           ← API client modules (one per domain)
│       ├── contexts/           ← React contexts (Auth, Workspace, Theme, Language)
│       ├── types/              ← TypeScript interfaces
│       └── utils/              ← PDF export, CSV export, data type mapping
├── docs/                       ← Technical documentation (api/, backend/, database/, frontend/)
├── infrastructure/terraform/   ← IaC (Terraform)
├── iam-policies/               ← AWS IAM policy definitions
└── .kiro/specs/                ← 10 feature specs (requirements → design → tasks)
```


### 2.2 Backend — Detailed Module Breakdown

#### `backend/main.py`
Single application entry point. Registers all 20 routers, configures CORS from `CORS_ORIGINS` env var, handles lifespan events: DB connection test on startup, auto-recovery of `running` migrations stuck from prior crashes, and a background asyncio scheduler that polls every 30s for due `scheduled` migrations.

#### `backend/routers/` — API Surface (20 routers)

| Router File | Prefix | Responsibility |
|---|---|---|
| `auth_router.py` | `/api/auth` | Login, logout, token refresh, current user |
| `workspace_router.py` | `/api/workspaces` | Workspace CRUD, stats, analysis |
| `connections_router.py` | `/api/connections` | Database connection CRUD, test by type |
| `assessment_router.py` | `/api/assessments` | BQ/SQL Server assessment lifecycle + report sections |
| `bq_redshift_migration.py` | `/api/migrations` | BQ→Redshift migration lifecycle (3 pathways) |
| `bq_iceberg_migration.py` | `/api/iceberg-migrations` | BQ→Iceberg migration lifecycle |
| `clickhouse_migration_router.py` | `/api/clickhouse-migrations` | BQ→ClickHouse migration lifecycle |
| `conversion_router.py` | `/api/conversion` | LLM-backed SQL code conversion (single + batch) |
| `validation_router.py` | `/api/validation` | Post-migration data validation runs |
| `compatibility_router.py` | `/api/compatibility` | BQ→Redshift compatibility check |
| `dashboard_router.py` | `/api/dashboard` | Aggregated dashboard metrics |
| `jobs_router.py` | `/api/jobs` | Unified jobs view (assessments + migrations) |
| `schema_router.py` | `/api/schema` | Deep schema analysis from assessments |
| `copy_history_router.py` | `/api/copy-history` | Redshift COPY command history |
| `task_history_router.py` | `/api/task-history` | AWS DataSync task history |
| `field_config_router.py` | `/api/field-configs` | DB-type field configuration management |
| `chatagent_router.py` | `/api/chat` | AI chat agent (Bedrock/Claude) |
| `history_router.py` | `/api/history` | Conversion job history |
| `pathway_a_test_router.py` | `/api/test/pathway-a` | Pathway A integration test endpoint |
| `bq_export_test_router.py` | `/api/test/bq-export` | BigQuery export test endpoint |


#### `backend/services/` — Business Logic Layer

| Service | Responsibility |
|---|---|
| `authentication_service.py` | Login orchestration: bcrypt verify, lockout logic, JWT issue, Redis session cache |
| `auth_service.py` | Password hashing, lockout calculation, RBAC primitives |
| `jwt_service.py` | JWT token generation and validation (python-jose) |
| `rbac_service.py` | Role-based access control enforcement |
| `session_cache.py` | Redis-backed session storage and token blacklisting |
| `bigquery_assessment_service.py` | Connects to BQ, enumerates datasets/tables/views/routines/security, stores assessment data |
| `sqlserver_assessment_service.py` | SQL Server schema introspection and assessment |
| `compatibility_engine.py` | Analyzes BQ assessment data for Redshift compatibility gaps |
| `recommendation_engine.py` | Generates migration recommendations from assessment data |
| `tco_engine.py` | Total Cost of Ownership calculations (compute, storage, network) |
| `aws_pricing_service.py` | Queries AWS Price List API for live cost data |
| `conversion_service.py` | LLM SQL conversion orchestration (prompt → Bedrock → parse result) |
| `conversion_deploy_service.py` | Deploy converted SQL to target database |
| `conversion_export_service.py` | Export converted SQL (S3, download) |
| `conversion_cache.py` | Redis cache for conversion results |
| `validation_service.py` | Post-migration data validation (row count, checksums, sampling) |
| `validation_cache.py` | Redis cache for validation results |
| `bedrock_client.py` | AWS Bedrock API client (Claude/other foundation models) |
| `kms_encryption_service.py` | Envelope encryption of credentials using AWS KMS |
| `unified_kms_service.py` | Unified facade over KMS for encrypt/decrypt operations |
| `encryption_service.py` | Local encryption fallback (Fernet) |
| `aws_secrets.py` | AWS Secrets Manager read/write |
| `data_type_mapper.py` | Source→target database data type translation |
| `sqlglot_parser.py` | SQL parsing and dialect conversion using sqlglot |
| `context_service.py` | Builds LLM context from assessment/migration data |
| `conversation_service.py` | Multi-turn conversation management for chat agent |
| `history_service.py` | Conversion job history retrieval |
| `history_cache.py` | Redis cache for history data |
| `prompt_template_manager.py` | Loads and renders prompt templates from `backend/prompts/` |
| `audit_logger.py` | Structured audit log writer to PostgreSQL |

#### `backend/services/bq_redshift_migration/` — BQ→Redshift Pipeline Sub-Package

| Module | Responsibility |
|---|---|
| `orchestrator.py` | Top-level migration state machine; delegates to pathway implementations |
| `pathway_a.py` | Pathway A: BQ Export → GCS → AWS DataSync → S3 → Redshift COPY |
| `pathway_b.py` | Pathway B: BQ Export → GCS → AWS DataSync agent transfer |
| `pathway_c.py` | Pathway C: BQ Export → GCS → Direct GCS-to-S3 transfer → Redshift COPY |
| `bigquery_exporter.py` | Executes BQ export jobs to GCS (Parquet/Avro/CSV) |
| `gcs_to_s3_transfer.py` | Streams objects from GCS bucket to S3 bucket |
| `aws_datasync_manager.py` | Creates and monitors AWS DataSync tasks |
| `redshift_loader.py` | Issues Redshift COPY commands, validates load status |
| `checkpoint_manager.py` | Persists migration progress checkpoints for resume |
| `manifest_handler.py` | Generates and validates Redshift COPY manifests |
| `background_worker.py` | Runs migration stages in background threads |
| `scheduler.py` | Processes scheduled migration triggers |


#### `backend/services/bq_iceberg_migration/` — BQ→Iceberg Pipeline Sub-Package

| Module | Responsibility |
|---|---|
| `orchestrator.py` | Migration state machine: structure review → approval → execution → validation |
| `type_mapper.py` | BigQuery → Apache Iceberg data type mapping |
| `iceberg_types.py` | Iceberg type system definitions and utilities |
| `partition_mapper.py` | Translates BQ partitioning/clustering to Iceberg partition specs |
| `schema_evolution.py` | Handles target schema evolution (add/drop/rename columns) |
| `iceberg_loader.py` | Writes Parquet data to Iceberg tables via AWS Glue catalog |
| `s3_tables_adapter.py` | Adapter for AWS S3 Tables (managed Iceberg) |
| `athena_verifier.py` | Post-load verification via Amazon Athena queries |
| `validation_service.py` | Data integrity validation (row counts, schema match, sample comparison) |
| `validators.py` | Individual validator implementations |
| `dedup_guard.py` | Prevents duplicate record insertion on resume/retry |
| `cost_engine.py` | Iceberg migration cost estimation (S3, Glue, Athena) |
| `credential_provider.py` | Provides GCP and AWS credentials for pipeline operations |
| `structure_report.py` | Generates pre-migration structure analysis report |
| `error_codes.py` | Typed error codes for structured error propagation |

#### `backend/repositories/` — Data Access Layer

| Repository | Responsibility |
|---|---|
| `user_repository.py` | User CRUD, login attempt tracking, lockout management |
| `connection_repository.py` | Connection CRUD with encrypted credential storage |
| `assessment_repository.py` | Assessment and related sub-entity CRUD |
| `bq_redshift_migration_repository.py` | BQ→Redshift migration record CRUD |
| `conversion_repository.py` | SQL conversion job and batch CRUD |
| `validation_repository.py` | Validation run and table result CRUD |
| `history_repository.py` | Conversion history queries |
| `agent_repository.py` | DataSync agent record management |

#### `backend/models/` — SQLAlchemy ORM Models

25 model files covering: `user`, `workspace`, `connection`, `assessment` (+ `assessment_log`), `bq_redshift_migration`, `migration_bq_iceberg`, `conversion_job_db`, `conversion_batch`, `conversion_log`, `copy_history`, `task_history`, `datasync_agent`, `field_configuration`, `validation_run`, `validation_table_result`, `iceberg_table_validation`, `conversation`, `message`, `attachment`, and supporting schema models.

#### `backend/alembic/versions/` — Schema Migration History

35 versioned migrations covering: auth tables → multi-tenancy → BQ/Redshift migration tables → connection table → field configurations → export format/compression → assessment tables → assessment logs → unique constraints → dependency fields → DataSync fields → load type fields → table load configs → DataSync agents table → copy history → task history → KMS-encrypted connection params → chat tables → conversion tables → batch naming → assessment indexes → validation tables → validation run names → check flags → assessment versioning → **BQ→Iceberg migration tables** (migration 035).

#### `backend/shared/` — Cross-Cutting Infrastructure

| Module | Responsibility |
|---|---|
| `middleware/auth_middleware.py` | JWT extraction, validation, user object hydration, role/permission guards |
| `middleware/workspace_middleware.py` | Workspace membership validation, `workspace_id` injection |
| `redis_client.py` | Redis connection pool with fallback-safe wrapper |
| `config_validator.py` | Validates required environment variables on startup |
| `datasync_client.py` | AWS DataSync boto3 client wrapper |


### 2.3 Frontend — Detailed Module Breakdown

**Tech Stack:** React 18.2, TypeScript 5.3, Vite 5, React Router 6.20, Recharts 3.7, Radix UI, Lucide React, jsPDF + html2pdf (PDF export), Vitest + Testing Library (tests), fast-check (property tests).

#### `frontend/src/pages/` — Application Pages (30+)

| Page | Route Purpose |
|---|---|
| `LoginScreen` | Authentication entry point |
| `DashboardPage` | Aggregated KPI overview with charts |
| `ConnectionsPage` | Database connection management |
| `AssessmentsPage` | Assessment list and creation |
| `AssessmentReportPage` | Full assessment report with multi-section tabs |
| `MigrationsPage` | BQ→Redshift migration list and wizard |
| `migrations/BQIcebergMigrationsPage` | BQ→Iceberg migration management |
| `migrations/IcebergStructureReviewPage` | Pre-migration structure review and approval |
| `migrations/BQRedshiftMigrationsPage` | BQ→Redshift migration management |
| `ValidationDashboardPage` | Data validation runs overview |
| `ValidationDetailPage` | Per-run validation result detail |
| `BatchConverterPage` | Batch SQL code conversion |
| `StandaloneConverterPage` | Single-asset SQL conversion |
| `QueryHistoryPage` | BQ query history and user insights |
| `CopyHistoryPage` | Redshift COPY command history |
| `TaskHistoryPage` | AWS DataSync task history |
| `JobsPage` | Unified jobs monitor |
| `WorkspacesPage` | Workspace management |
| `DatabaseFieldConfigPage` | DB field type configuration |
| `AssessmentReportPage` | SQL Server assessment report |
| `assessments/CompatibilityCheckPage` | BQ→Redshift compatibility analysis |
| `assessments/SchemaAnalysisPage` | Deep schema explorer |
| `AdminPage` | User/admin management |
| `ProfilePage` | User profile |
| `DocumentationPage` | In-app documentation viewer |

#### `frontend/src/components/` — Reusable Component Library

| Directory | Key Components |
|---|---|
| `ui/` | Button, Input, Select, Modal, Table, Card, Badge, Alert, Dropdown, Toggle, Avatar, Logo |
| `migrations/` | `CreateMigrationWizard`, `IcebergProgressDisplay`, `IcebergCostAnalysisTab`, `StructureReviewTable`, `IcebergValidationResults`, `CompactionStrategySelector`, `MaintenanceConfigForm` |
| `assessments/` | `CreateAssessmentModal`, `EditAssessmentModal`, `QueryInsightsSection`, `ViewLogsModal`, SQL Server section components |
| `connections/` | `CreateConnectionModal` |
| `conversion/` | `AssetSelector`, `CodePane`, `BatchHistoryTable`, `ConversionLogsPanel` |
| `ChatAgent/` | `ChatAgent` (floating AI assistant panel) |
| `fieldConfig/` | `FieldConfigModal`, `DynamicField`, `DatabaseTypeList` |
| `layout/` | `MainLayout`, `Header`, `Sidebar` |
| `auth/` | `ProtectedRoute` |

#### `frontend/src/services/` — API Client Layer

One typed service module per backend domain: `api.ts` (base client + connection helpers), `authApi.ts`, `assessmentsApi.ts`, `bqRedshiftApi.ts`, `bqIcebergApi.ts`, `conversionApi.ts`, `validationApi.ts`, `copyHistoryApi.ts`, `taskHistoryApi.ts`, `fieldConfigApi.ts`, `clickhouseMigrationApi.ts`.

The base `ApiClient` class in `api.ts` uses `fetch()` with:
- JWT Bearer token injected from `localStorage` on every request
- Automatic `401` interception → `localStorage.removeItem('auth_token')` → redirect to `/login`
- Environment-aware base URL: `localhost:8000` in dev, relative path (nginx proxy) in production

#### `frontend/src/contexts/`
- `AuthContext` — user state, JWT token, login/logout/refresh, workspace list
- `WorkspaceContext` — active workspace switching
- `ThemeContext` — light/dark theme
- `LanguageContext` — internationalization scaffold


### 2.4 Test Suite

| Location | Count | Type |
|---|---|---|
| `backend/tests/unit/` | 32 files | Unit tests (services, models, repositories) |
| `backend/tests/property/` | 24 files | Property-based tests using Hypothesis (100+ iterations each) |
| `backend/tests/integration/` | 3 files | Integration tests (BQ Iceberg API, conversion router, validation router) |
| `backend/tests/fixtures/` | `sample_payloads.py` | Centralized test payload library |
| `frontend/src/pages/__tests__/` | 3 files | React component tests + property tests (Vitest + fast-check) |
| `frontend/src/components/conversion/__tests__/` | Component tests | Conversion UI tests |
| `frontend/src/pages/migrations/__tests__/` | Migration tests | Migration page tests |

Coverage artifacts: `backend/htmlcov/` (HTML coverage report) and `backend/.coverage` (coverage data). The backend property test suite is notably extensive for the BQ→Iceberg module: type mapping, schema validation, orchestrator behavior, input validation, infrastructure properties, and structure/cost reporting.

---

## 3. API-Based Approach & API Registry

### Architectural Approach

DataMIQ uses a **RESTful API** architectural pattern with the following characteristics:

- **Single-host monolith with logical router separation** — all services run on a single FastAPI app (port 8000), with 20 distinct routers providing domain separation. The codebase is structured to support future microservice extraction (services/repositories are already decoupled from routers).
- **JSON over HTTP** — all API contracts use `application/json` request/response bodies.
- **JWT Bearer authentication** — all protected routes use `Depends(get_current_user)` from `auth_middleware.py`.
- **Background task execution** — long-running operations (migrations, assessments) are dispatched to `threading.Thread` workers to keep HTTP responses non-blocking.
- **OpenAPI/Swagger auto-generated** — FastAPI generates OpenAPI 3.x spec automatically. Available at runtime at `/api/docs` (Swagger UI) and `/api/redoc` (ReDoc).
- **Workspace-scoped resources** — resource endpoints extract `workspace_id` from the JWT token via `get_workspace_id()` middleware helper; all queries are filtered accordingly.

### Full API Registry

#### Authentication — `/api/auth`

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/login` | Authenticate with username + password; returns JWT token |
| POST | `/api/auth/logout` | Invalidate token, remove Redis session |
| GET | `/api/auth/me` | Get current user info and workspaces |
| POST | `/api/auth/refresh` | Refresh JWT token |
| GET | `/api/auth/health` | Auth service health check |

#### Workspaces — `/api/workspaces`

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/workspaces` | List all workspaces for current user |
| POST | `/api/workspaces` | Create a new workspace |
| GET | `/api/workspaces/analysis` | Get workspace resource analysis and stats |


#### Database Connections — `/api/connections`

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/connections/test` | Test a connection by type (BigQuery, PostgreSQL, MySQL, SQL Server, MongoDB, ClickHouse) |
| GET | `/api/connections/test/{connection_id}` | Test an existing saved connection by ID |
| GET | `/api/connections/health` | Connection service health check |
| POST | `/api/connections/` | Create and persist a new connection (credentials encrypted via KMS) |
| GET | `/api/connections/` | List all active connections |
| DELETE | `/api/connections/{connection_id}` | Delete a connection |
| PUT | `/api/connections/{connection_id}/status` | Update connection status (connected/disconnected/error) |
| PUT | `/api/connections/{connection_id}` | Update connection configuration |

#### Assessments — `/api/assessments`

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/assessments/tco/regions` | List available TCO regions |
| POST | `/api/assessments/` | Create a new assessment |
| GET | `/api/assessments/` | List all assessments |
| GET | `/api/assessments/{id}` | Get assessment detail |
| DELETE | `/api/assessments/{id}` | Delete assessment |
| PUT | `/api/assessments/{id}` | Update assessment metadata |
| POST | `/api/assessments/{id}/run` | Trigger assessment execution (async background) |
| GET | `/api/assessments/{id}/logs` | Get assessment execution logs |
| GET | `/api/assessments/{id}/assets` | Get discovered database assets (tables, views, routines) |
| GET | `/api/assessments/{id}/report` | Get full assessment report (JSONB payload) |
| GET | `/api/assessments/{id}/report/summary` | Get report summary section |
| GET | `/api/assessments/{id}/report/tables` | Get tables section (paginated, filterable, exportable) |
| GET | `/api/assessments/{id}/report/views` | Get views section (paginated, exportable) |
| GET | `/api/assessments/{id}/report/routines` | Get stored routines section |
| GET | `/api/assessments/{id}/report/additional-metadata` | Get additional metadata section |
| GET | `/api/assessments/{id}/report/security` | Get security section (policies, row-level security) |
| GET | `/api/assessments/{id}/report/ml-models` | Get ML models section (BigQuery ML) |
| GET | `/api/assessments/{id}/report/user-insights` | Get user activity insights |
| GET | `/api/assessments/{id}/recommendations` | Get AI-generated migration recommendations |
| GET | `/api/assessments/{id}/tco` | Get Total Cost of Ownership analysis |
| GET | `/api/assessments/{id}/query-insights` | Get query analysis insights (paginated, timeframe-filterable) |

#### BQ → Redshift Migration — `/api/migrations`

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/migrations/discover` | Discover BQ datasets and tables (metadata preview) |
| POST | `/api/migrations/` | Create a new migration project |
| GET | `/api/migrations/` | List all migrations |
| GET | `/api/migrations/{id}` | Get migration detail |
| POST | `/api/migrations/{id}/start` | Start migration execution |
| POST | `/api/migrations/{id}/pause` | Pause a running migration |
| POST | `/api/migrations/{id}/resume` | Resume a paused migration |
| POST | `/api/migrations/{id}/cancel` | Cancel a migration |
| GET | `/api/migrations/{id}/status` | Get real-time migration status and progress |
| GET | `/api/migrations/{id}/logs` | Get migration execution logs |
| GET | `/api/migrations/{id}/metrics` | Get migration performance metrics |
| POST | `/api/migrations/{id}/validate` | Run post-migration validation |
| POST | `/api/migrations/{id}/restart` | Restart a failed migration |
| PUT | `/api/migrations/{id}` | Update migration configuration |
| DELETE | `/api/migrations/{id}` | Delete a migration |


#### BQ → Apache Iceberg Migration — `/api/iceberg-migrations`

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/iceberg-migrations/` | Create a new BQ→Iceberg migration |
| GET | `/api/iceberg-migrations/` | List all Iceberg migrations |
| GET | `/api/iceberg-migrations/{id}` | Get migration detail |
| PUT | `/api/iceberg-migrations/{id}` | Update migration configuration |
| DELETE | `/api/iceberg-migrations/{id}` | Delete migration |
| POST | `/api/iceberg-migrations/{id}/start` | Start migration execution |
| POST | `/api/iceberg-migrations/{id}/pause` | Pause a running migration |
| POST | `/api/iceberg-migrations/{id}/resume` | Resume a paused migration |
| POST | `/api/iceberg-migrations/{id}/cancel` | Cancel a migration |
| POST | `/api/iceberg-migrations/{id}/restart` | Restart from beginning |
| GET | `/api/iceberg-migrations/{id}/status` | Get real-time status |
| GET | `/api/iceberg-migrations/{id}/logs` | Get execution logs |
| GET | `/api/iceberg-migrations/{id}/structure-report` | Get pre-migration structure analysis |
| POST | `/api/iceberg-migrations/{id}/approve-structure` | Approve structure and proceed |
| POST | `/api/iceberg-migrations/{id}/request-changes` | Request structure changes |
| POST | `/api/iceberg-migrations/{id}/custom-structure` | Submit custom structure definition |
| GET | `/api/iceberg-migrations/{id}/download-report` | Download migration report (Markdown) |

#### BQ → ClickHouse Migration — `/api/clickhouse-migrations`

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/clickhouse-migrations/` | Start a new BQ→ClickHouse migration |
| GET | `/api/clickhouse-migrations/` | List all ClickHouse migrations |
| GET | `/api/clickhouse-migrations/{id}/status` | Get migration status |
| GET | `/api/clickhouse-migrations/{id}/logs` | Get execution logs |
| POST | `/api/clickhouse-migrations/{id}/retry` | Retry failed tables |

#### SQL Code Conversion — `/api/conversion`

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/conversion/jobs` | Create a standalone (single-asset) conversion job |
| GET | `/api/conversion/jobs` | List all conversion jobs |
| POST | `/api/conversion/jobs/bulk-delete` | Bulk delete conversion jobs |
| GET | `/api/conversion/jobs/{id}` | Get job detail |
| DELETE | `/api/conversion/jobs/{id}` | Delete a job |
| GET | `/api/conversion/jobs/{id}/logs` | Get conversion logs |
| POST | `/api/conversion/batches` | Create a batch conversion |
| GET | `/api/conversion/batches` | List all batches |
| DELETE | `/api/conversion/batches/{id}` | Delete a batch |
| GET | `/api/conversion/batches/{id}` | Get batch detail |
| GET | `/api/conversion/batches/{id}/jobs` | List jobs within a batch |
| GET | `/api/conversion/batches/{id}/export-sql` | Export batch SQL (download) |
| POST | `/api/conversion/batches/{id}/export-s3` | Export batch SQL to S3 |
| POST | `/api/conversion/batches/{id}/deploy` | Deploy converted SQL to target database |
| GET | `/api/conversion/models` | List available Bedrock foundation models |
| GET | `/api/conversion/templates` | List available prompt templates |

#### Data Validation — `/api/validation`

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/validation/runs` | Create and start a validation run |
| GET | `/api/validation/runs` | List all validation runs |
| GET | `/api/validation/models` | List available Bedrock models for validation |
| GET | `/api/validation/migrations/{id}/info` | Get migration info for validation context |
| GET | `/api/validation/runs/{id}` | Get validation run detail |
| GET | `/api/validation/runs/{id}/table-results` | Get per-table validation results |
| GET | `/api/validation/runs/{id}/tables/{table}` | Get detail for a specific table result |
| GET | `/api/validation/runs/{id}/report` | Get validation summary report |
| DELETE | `/api/validation/runs/{id}` | Delete a validation run |


#### Compatibility Check — `/api/compatibility`

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/compatibility/check` | Run BQ→Redshift compatibility analysis on a completed assessment |
| POST | `/api/compatibility/save` | Save compatibility report to assessment JSONB |
| GET | `/api/compatibility/saved/{assessment_id}` | Retrieve a previously saved compatibility report |

#### Dashboard — `/api/dashboard`

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/dashboard/summary` | Get aggregated KPIs (connections, assessments, migrations, conversions, copy history) |

#### Jobs (Unified View) — `/api/jobs`

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/jobs/` | List all jobs (assessments + migrations) with unified status format |

#### Schema Analysis — `/api/schema`

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/schema/analysis/{assessment_id}` | Get full structured schema analysis (datasets, tables with columns, views, routines, type distribution) |

#### Copy & Task History — `/api/copy-history`, `/api/task-history`

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/copy-history/list` | List Redshift COPY history (filterable, paginated) |
| GET | `/api/copy-history/{id}` | Get single COPY history record |
| GET | `/api/task-history/list` | List AWS DataSync task history (filterable, paginated) |
| GET | `/api/task-history/{id}` | Get single task history record |

#### Field Configuration — `/api/field-configs`

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/field-configs/{database_type}` | Get field configurations for a DB type |
| POST | `/api/field-configs/` | Create a field configuration |
| PUT | `/api/field-configs/{id}` | Update a field configuration |
| DELETE | `/api/field-configs/{id}` | Delete a field configuration |
| POST | `/api/field-configs/{database_type}/seed` | Seed default configurations for a DB type |

#### AI Chat Agent — `/api/chat`

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/chat/` | Send a message to the AI assistant; context is auto-enriched with assessment/migration data |

#### Health & Root

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Application health check |
| GET | `/` | Root — returns API version and docs link |
| GET | `/api/docs` | Swagger UI (FastAPI auto-generated) |
| GET | `/api/redoc` | ReDoc API documentation |

### Total API Surface: ~95 endpoints across 20 routers


---

## 4. Integration & Data Flow Documentation

### 4.1 System Component Interaction Map

```
┌────────────────────────────────────────────────────────────┐
│                     Browser (React SPA)                     │
│  AuthContext → localStorage JWT → ApiClient (fetch + Bearer)│
└──────────────────────────┬─────────────────────────────────┘
                           │ HTTPS / HTTP (dev: :8000, prod: nginx proxy)
                           ▼
┌────────────────────────────────────────────────────────────┐
│            FastAPI Application  (Port 8000)                 │
│  CORSMiddleware → Router → auth_middleware (JWT validate)   │
│                          ↓                                  │
│               Service Layer (business logic)                │
│                          ↓                                  │
│            Repository Layer (SQLAlchemy queries)            │
└──────┬────────────────────────────────────────────┬────────┘
       │                                            │
       ▼                                            ▼
┌──────────────┐                          ┌────────────────────┐
│  PostgreSQL  │                          │    Redis Cache      │
│  (primary    │                          │  (sessions, tokens, │
│   datastore) │                          │   conversion cache, │
└──────────────┘                          │   validation cache) │
                                          └────────────────────┘
       ↕ boto3
┌────────────────────────────────────────────────────────────┐
│                    AWS Services                             │
│  KMS (credential encryption)  │  Secrets Manager           │
│  S3 (staging / export)        │  Bedrock (LLM inference)   │
│  Redshift (migration target)  │  Glue Catalog (Iceberg)    │
│  DataSync (BQ→S3 Pathway B)   │  Athena (Iceberg verify)   │
└────────────────────────────────────────────────────────────┘
       ↕ google-cloud-bigquery / google-cloud-storage
┌────────────────────────────────────────────────────────────┐
│                GCP Services                                 │
│  BigQuery (assessment source + migration source)            │
│  GCS (migration staging bucket)                             │
└────────────────────────────────────────────────────────────┘
```


### 4.2 Primary Data Lifecycle: User Authentication Flow

This walkthrough describes the complete end-to-end sequence from a user submitting credentials to receiving a protected API response.

**Step 1 — User submits login form (`LoginScreen.tsx`)**
```
POST /api/auth/login
Body: { "username": "admin", "password": "AdminPass123!" }
```

**Step 2 — `auth_router.py` receives the request**
- Instantiates `UserRepository(db)` and `AuthenticationService(user_repo)`.
- Calls `auth_service.authenticate_user(username, password)`.

**Step 3 — `AuthenticationService.authenticate_user()` executes**
1. `UserRepository.get_user_by_username(username)` → PostgreSQL query (table: `users`).
2. Checks `AuthService.is_account_locked(failed_attempts, locked_until)`.
3. `AuthService.verify_password(password, password_hash)` — bcrypt comparison.
4. On failure: increments `failed_login_attempts`, locks account if ≥ threshold.
5. On success:
   - Resets `failed_login_attempts = 0`.
   - Updates `last_login` timestamp.
   - `JWTService.generate_jwt_token(user_id, username, role)` → returns signed JWT (python-jose, HS256).
   - `session_cache.cache_session(user_id, token, session_data, ttl=28800)` → writes to Redis.
6. Returns `{ access_token, token_type: "bearer", user: { id, username, role, organization_id } }`.

**Step 4 — Frontend stores token**
- `AuthContext.login()` receives the response.
- `localStorage.setItem('auth_token', data.access_token)`.
- Calls `GET /api/auth/me` to load workspaces.
- React state: `user`, `workspaces`, `isAuthenticated = true`.

**Step 5 — Subsequent authenticated request**
```
GET /api/assessments/
Headers: { Authorization: "Bearer <jwt_token>" }
```

**Step 6 — `auth_middleware.get_current_user()` executes**
1. Extracts Bearer token from `Authorization` header.
2. Checks Redis blacklist — `session_cache.is_token_blacklisted(token)`.
3. If not blacklisted, checks Redis session cache — `session_cache.get_session(token)`.
4. On Redis miss, falls back to `JWTService.validate_jwt_token(token)` (stateless verification).
5. Builds `CurrentUser(user_id, username, role)` and injects into route handler.

**Step 7 — Router handler executes with authenticated user**
- `get_workspace_id(current_user)` extracts `workspace_id` from JWT payload.
- `AssessmentRepository(db).get_all(workspace_id=workspace_id)` → PostgreSQL query filtered by workspace.
- Response serialized and returned to frontend.

**Step 8 — 401 interception on expired token**
- `ApiClient.handleResponse()` detects `status === 401`.
- Clears `localStorage` token.
- Redirects to `/login` (if not already there).


### 4.3 Secondary Data Lifecycle: BQ → Redshift Migration Execution

This describes the complete technical flow for a migration from creation through execution.

**Step 1 — Migration creation**
```
POST /api/migrations/
Body: { migration_name, source_connection_id, target_connection_id, pathway, tables, ... }
```
- `connections_router` previously stored credentials AES-encrypted via `kms_encryption_service`.
- `bq_redshift_migration.py` router creates `MigrationBQRedshift` record in PostgreSQL (`status = 'ready'`).

**Step 2 — Execution trigger**
```
POST /api/migrations/{id}/start
```
- Router instantiates `MigrationOrchestrator(db)`.
- Spawns a `threading.Thread(target=orchestrator.start_migration, args=(migration_id,))`.
- HTTP response returns immediately (non-blocking).

**Step 3 — Orchestrator determines pathway**

The `MigrationOrchestrator` updates status to `running`, then delegates to the selected pathway:

**Pathway A (BQ → GCS → DataSync → S3 → Redshift COPY)**:
1. `BigQueryExporter.export_to_gcs()` — BQ Export Job writes Parquet to GCS staging bucket.
2. `CheckpointManager.save_checkpoint()` — records GCS export completion in DB.
3. `AwsDataSyncManager.create_task()` — creates DataSync task (GCS source → S3 destination).
4. `AwsDataSyncManager.start_and_monitor_task()` — polls DataSync until complete.
5. `RedshiftLoader.copy_from_s3()` — issues `COPY table FROM s3://... IAM_ROLE '...'` via psycopg2.
6. `CopyHistory` record written to PostgreSQL on each table load.

**Pathway C (BQ → GCS → Direct GCS→S3 → Redshift COPY)**:
1. `BigQueryExporter.export_to_gcs()` — same as Pathway A.
2. `GCSToS3Transfer.transfer()` — uses `google-cloud-storage-transfer` API or streaming copy.
3. `RedshiftLoader.copy_from_s3()` — same as Pathway A.

**Step 4 — Status updates**
- Worker thread updates `MigrationBQRedshift.status`, `current_stage`, `progress_percentage`, `total_rows_source`, `total_rows_target` directly in PostgreSQL.
- Frontend polls `GET /api/migrations/{id}/status` every N seconds to display real-time progress.

**Step 5 — Crash recovery**
- On next application startup, `main.py` lifespan queries for `status = 'running'` migrations and resets them to `'failed'`, allowing user-initiated resume from the UI.

**Step 6 — Scheduled migrations**
- `asyncio.create_task(check_scheduled_migrations())` runs every 30s.
- Queries `status = 'scheduled'` AND `next_run_time <= now`.
- Spawns a thread per due migration, identical to manual execution.

### 4.4 Tertiary Lifecycle: LLM SQL Code Conversion

```
POST /api/conversion/jobs
Body: { source_dialect, target_dialect, sql_code, model_id }
```
1. `ConversionService._build_prompt()` — `PromptTemplateManager` loads the matching `.txt` template from `backend/prompts/` based on `source_dialect → target_dialect`.
2. Context is assembled: source SQL + schema metadata (if available).
3. `BedrockClient.invoke_model(model_id, prompt)` → AWS Bedrock API call (synchronous).
4. Response parsed for converted SQL + explanation.
5. `ConversionJob` record written to PostgreSQL (`conversion_jobs` table).
6. Result cached in Redis via `ConversionCache` (key: hash of SQL + dialect pair).
7. Response returned. Frontend renders source vs. converted SQL side-by-side in `CodePane`.

For batch conversions, steps 2–6 repeat per asset within the batch. `ConversionBatch` and `ConversionLog` records track the aggregate state. Export to S3 or direct deployment to target database are separate subsequent operations.


### 4.5 Credential Encryption Flow (Security Layer)

All database connection credentials follow this envelope encryption pattern on write:

```
Plain credential
      │
      ▼
KMS.generate_data_key()  ──→  AWS KMS (KMS_KEY_ID from .env)
      │
      ├─→ plaintext_data_key  →  AES-256-GCM encrypt(credential)
      │                               │
      └─→ encrypted_data_key  ────────┼──→  stored in connection_params_encrypted (BYTEA)
                                      │
                                 ciphertext  ────────────────→  stored alongside

On read:
KMS.decrypt(encrypted_data_key)  →  plaintext_data_key  →  AES-256-GCM decrypt(ciphertext)
```

The `UnifiedKMSService` / `KMSEncryptionService` handle key caching with TTL to minimize KMS API calls. Decrypted values are never logged (enforced by `audit_logger.py` sanitization).

### 4.6 Redis Caching Integration

The `redis_client.py` wrapper implements the **cache-aside pattern** with transparent fallback:

```python
def get_data(key):
    try:
        cached = redis.get(key)          # 1. Try Redis
        if cached: return deserialize(cached)
    except RedisError as e:
        logger.warning(f"Redis miss: {e}")   # 2. Log and fall through
    
    data = db.query(...)                 # 3. Fetch from PostgreSQL
    
    try:
        redis.setex(key, ttl, serialize(data))  # 4. Populate cache (best-effort)
    except Exception: pass
    
    return data
```

**Cache domains:**

| Domain | TTL | Key Pattern |
|---|---|---|
| JWT Sessions | 8 hours | `session:{user_id}:{token_hash}` |
| Token Blacklist | 8 hours | `blacklist:{token_hash}` |
| Conversion Results | 1 hour | `conversion:{sql_hash}:{dialect}` |
| Validation Results | 30 min | `validation:{run_id}:{table}` |
| History Data | 15 min | `history:{user_id}:{page}` |

Redis is **never a hard dependency** — all cache failures are caught and logged; the application falls back to PostgreSQL queries transparently.

### 4.7 OpenAPI / API Specification Locations

| Artifact | Location / URL |
|---|---|
| **Swagger UI** (interactive) | `http://<host>:8000/api/docs` (runtime, auto-generated by FastAPI) |
| **ReDoc** (readable) | `http://<host>:8000/api/redoc` (runtime, auto-generated by FastAPI) |
| **OpenAPI JSON spec** | `http://<host>:8000/openapi.json` (runtime export) |
| **API documentation (auth)** | `docs/api/authentication.md` |
| **Feature specs** | `.kiro/specs/*/design.md` (per-feature API contracts) |
| **General API docs** | `docs/CONNECTIONS.md`, `docs/ASSESSMENTS.md`, `docs/MIGRATIONS.md` |
| **Postman collection** | Not currently committed to the repository |

> **Recommendation for CTO:** The live OpenAPI spec at `/openapi.json` is the canonical, always-up-to-date API contract. Exporting it and importing into Postman or publishing via API Gateway (AWS) is a one-step operation. Consider adding a CI step to export and commit `openapi.json` to the repo on each main-branch merge.


---

## Appendix A: Active Kiro Feature Specs

| Spec | Status | Description |
|---|---|---|
| `auth-navigation-system` | Tasks defined | Authentication, routing, protected routes |
| `bq-to-iceberg-migration` | Implementation complete (commit 688444c) | Full BQ→Iceberg migration pipeline |
| `chatagent-production-enhancements` | Tasks defined | AI chat agent enhancements |
| `code-conversion` | Tasks defined | SQL code conversion module |
| `coworker-features-integration` | Tasks defined | Collaboration features |
| `data-validation-module` | Implementation complete | Post-migration data validation |
| `database-field-configuration` | Tasks defined | Dynamic DB field config system |
| `iceberg-production-hardening` | **In progress** | Production robustness for Iceberg pipeline |
| `validation-dashboard-fixes` | Bugfix in progress | Validation UI fixes |
| `validation-ux-redesign` | Design complete | Redesigned validation UX |

## Appendix B: Supported Database Types

**Source systems (assessment + migration):**
- BigQuery (primary — all 3 migration pathways)
- SQL Server (assessment only)
- MongoDB, MySQL, PostgreSQL, ClickHouse (connection testing)

**Target systems:**
- Amazon Redshift (BQ→Redshift migration, 3 pathways)
- Apache Iceberg on AWS (via Glue + S3 Tables)
- ClickHouse (migration + SQL conversion)

**SQL Code Conversion Dialects (LLM-backed):**
- BigQuery → Amazon Redshift
- BigQuery → ClickHouse
- SQL Server → Amazon Redshift
- Sybase → Amazon Redshift
- DB2 → Amazon Redshift

## Appendix C: Key Environment Variables

| Variable | Purpose |
|---|---|
| `APP_DB_HOST/PORT/NAME/USER/PASSWORD` | PostgreSQL connection |
| `REDIS_HOST/PORT/PASSWORD` | Redis connection |
| `AWS_REGION` | AWS services region |
| `KMS_KEY_ID` | KMS key for credential encryption |
| `SECRET_MANAGER_SECRET_NAME` | Secrets Manager secret name |
| `AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY` | AWS credentials (or IAM role in prod) |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins |
| `APP_ENV` | `development` / `production` |
| `APP_PORT / APP_HOST` | Uvicorn bind address |

---

*This document was generated by automated codebase analysis on July 6, 2026. All endpoint counts, module descriptions, and data flows reflect the actual code state at commit `076bf05` (HEAD of `prajwal-dev`/`datamiq-dev`).*
