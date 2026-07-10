# BQ → Iceberg Migration: Complete Testing Guide

## Overview

This guide covers end-to-end testing of the BigQuery to Apache Iceberg migration feature, including the UI wizard, structure review, cost analysis, load progress, and validation results. It also covers the production hardening features (S3 Tables maintenance, compaction strategy, hidden partitioning, watermark).

**App URL:** http://localhost:3000  
**API URL:** http://localhost:8000  
**API Docs:** http://localhost:8000/api/docs

---

## Routes in the App

| URL | What it does |
|-----|-------------|
| `/migrations/bq-iceberg` | Main list page — all Iceberg migrations |
| `/migrations/bq-iceberg/:id` | Migration detail (same list, filtered) |
| `/migrations/bq-iceberg/:id/structure-review` | Structure report review + approval |

**To reach BQ→Iceberg:** Sidebar → **Migrations** → click **BigQuery → Iceberg** tab/card

---

## Test Section 1: Migration List Page

**URL:** `/migrations/bq-iceberg`

### ✅ Checklist

- [ ] Page loads without error
- [ ] Header shows "BigQuery → Iceberg" title
- [ ] "New Migration" button visible top-right
- [ ] Status filter buttons visible: All, Pending, Running, Pending Review, Approved, Completed, Failed, Cancelled
- [ ] Destination type dropdown: "All destinations", "Iceberg on S3", "S3 Tables"
- [ ] Search box works — filters by migration name
- [ ] Empty state shown when no migrations exist
- [ ] Each migration row shows: Name, Destination badge, Pathway, Region/Glue DB, Status badge, Stage, Progress bar, Updated time
- [ ] Clicking a row navigates to migration detail
- [ ] **Pending Review** status shows a "Review" button — clicking navigates to structure review page
- [ ] **Pending/Approved** status shows "Start" button
- [ ] **Running** shows "Pause" and "Cancel" buttons
- [ ] **Paused/Failed** shows "Resume" button
- [ ] Delete button (trash icon) available for non-running migrations

---

## Test Section 2: Create Migration Modal

**Trigger:** Click "New Migration" on the list page

### 2.1 Form Fields

- [ ] **Migration Name** — required, text input
- [ ] **Pathway** dropdown:
  - Path A — GCS → S3 Storage Transfer
  - Path B — DataSync (GCP VM)
  - Path C — Hybrid
- [ ] **Destination Type** dropdown:
  - Apache Iceberg on S3
  - AWS S3 Tables (Managed)

### 2.2 Source (BigQuery) Fields

- [ ] GCP Project ID — required
- [ ] Dataset — required
- [ ] Tables (comma-separated) — required, e.g. `orders, users, events`

### 2.3 Target (AWS) Fields

- [ ] AWS Region — required, default `us-east-1`
- [ ] Glue Database Name — required, must match `[a-z0-9_]+`

**When Destination = "Apache Iceberg on S3":**
- [ ] S3 Bucket — required
- [ ] S3 Path Prefix — optional, default `iceberg/`

**When Destination = "AWS S3 Tables (Managed)":**
- [ ] Table Bucket ARN — required, format: `arn:aws:s3tables:<region>:<account-id>:bucket/<name>`
- [ ] Namespace — optional

### 2.4 Intermediate Storage (GCS) Fields

- [ ] GCS Bucket — required
- [ ] GCS Path — optional, default `exports/`

### 2.5 AWS Credentials (Optional)

- [ ] Access Key ID
- [ ] Secret Access Key (password field)
- [ ] Note: if omitted, IAM role is used

### 2.6 Validation Tests

| Input | Expected Error |
|-------|---------------|
| Empty migration name | "Migration name is required" |
| Empty project ID | "GCP Project ID is required" |
| Empty dataset | "BQ Dataset is required" |
| Empty tables | "At least one table name is required" |
| Empty Glue DB name | "Glue database name is required" |
| Glue DB = `My-DB` (uppercase/hyphen) | "Glue database name: lowercase letters, numbers, underscores only" |
| Destination=S3 + empty S3 bucket | "S3 bucket is required for Iceberg on S3" |
| Destination=S3Tables + empty ARN | "Table Bucket ARN is required for S3 Tables" |
| Empty GCS bucket | "GCS bucket is required" |

### 2.7 Success Case

**Sample valid payload — Iceberg on S3:**
```
Migration Name: test-iceberg-s3
Pathway: A
Destination: Apache Iceberg on S3
GCP Project: assessiq-484512
Dataset: sales_analytics
Tables: customers, orders
AWS Region: us-east-1
Glue DB: sales_iceberg
S3 Bucket: my-iceberg-data
S3 Prefix: iceberg/
GCS Bucket: bq_data_transfer_rs
GCS Path: exports/
```

**Sample valid payload — S3 Tables:**
```
Migration Name: test-s3-tables
Pathway: A
Destination: AWS S3 Tables (Managed)
GCP Project: assessiq-484512
Dataset: sales_analytics
Tables: customers
AWS Region: us-east-1
Glue DB: sales_iceberg
Table Bucket ARN: arn:aws:s3tables:us-east-1:123456789012:bucket/my-tables
Namespace: analytics_ns
GCS Bucket: bq_data_transfer_rs
```

- [ ] Submit succeeds → modal closes
- [ ] Success toast "Migration created successfully" appears
- [ ] New migration appears in list with status `pending`

---

## Test Section 3: Migration Lifecycle Actions

### 3.1 Start

- [ ] Migration in `pending` status → click **Start**
- [ ] Status changes to `running`
- [ ] Stage indicator updates (export → transfer → load)
- [ ] Progress % updates incrementally

### 3.2 Pause

- [ ] Migration in `running` status → click **Pause**
- [ ] Status changes to `paused`
- [ ] Progress % preserved

### 3.3 Resume

- [ ] Migration in `paused` or `failed` status → click **Resume**
- [ ] Status changes to `running`
- [ ] Resumes from checkpoint (does not restart completed tables)

### 3.4 Cancel

- [ ] Migration in `running` or `paused` → click **Cancel**
- [ ] Status changes to `cancelled`
- [ ] All config (source, target, tables) still visible on detail page

### 3.5 Delete

- [ ] Non-running migration → click trash icon
- [ ] Confirm deletion
- [ ] Migration removed from list

---

## Test Section 4: Structure Review (pending_review status)

**URL:** `/migrations/bq-iceberg/:id/structure-review`  
**How to reach:** When migration status is `pending_review`, click **Review** button on the list row, OR navigate directly.

> The migration enters `pending_review` automatically after the export/transfer stage completes, before the load stage begins.

### 4.1 Page Load

- [ ] Page loads with "Iceberg Structure Review" title
- [ ] Subtitle explains purpose
- [ ] "Download Report" button in top-right

### 4.2 Dataset to Database Mapping Section

- [ ] Shows each BQ dataset with an editable input for the Glue DB name
- [ ] Changing the input updates the mapping
- [ ] Mapping is sent with approval

### 4.3 S3 Tables Namespace Section (S3 Tables only)

- [ ] Only visible when destination is `iceberg_s3_tables`
- [ ] Text input for namespace name
- [ ] Namespace sent with approval

### 4.4 Prerequisites Checklist

- [ ] Shows list of required AWS setup items
- [ ] Each item has a checkbox (manual confirmation by user)
- [ ] Categories visible (IAM, S3, Glue, Athena, etc.)
- [ ] For S3 Tables: **Lake Formation** section appears with:
  - Data location permission on bucket ARN
  - DESCRIBE on Glue database
  - SELECT on Glue tables
  - `lakeformation:GetDataAccess` IAM permission
  - Glue execution role permissions
  - Derived `glue.id` value (format: `{account_id}:s3tablescatalog/{bucket-name}`)

### 4.5 Warnings and Recommendations Section

- [ ] Shows warnings if any (e.g., unrecognized BQ type mapped to string)
- [ ] Each warning has severity (high/medium/low), table name, message, recommendation
- [ ] Empty state if no warnings

### 4.6 Table Structures Section

Each table shown as a collapsible section:

- [ ] Clicking header expands/collapses the table details
- [ ] Header shows: table name, column count, row count, data size
- [ ] Custom badge shown if user defined custom structure
- [ ] Excluded badge shown if table is excluded

**Inside each expanded table:**

**Columns tab:**
- [ ] Table with: Name, Source BQ Type, Iceberg Type, Nullable, Warnings columns
- [ ] Warning text shown in orange/red for fallback type mappings

**Partition Spec:**
- [ ] Shows current partition spec (e.g., `day(event_date)`)
- [ ] Rationale shown (e.g., "based on BQ DATE partitioning")
- [ ] "Override" button → shows edit controls
- [ ] Can add/remove partition columns
- [ ] Transform options: identity, day, hour, month, year, bucket, truncate
- [ ] **Hidden partitioning**: time columns must use day/hour/month/year (NOT identity)
- [ ] "Apply" saves the override

**Sort Order:**
- [ ] Shows current sort order from BQ clustering columns
- [ ] "Override" button → shows edit controls
- [ ] Can add/remove sort columns with direction (asc/desc)
- [ ] "Apply" saves the override

**Compaction Strategy (S3 Tables only):**
- [ ] Shows per-table compaction strategy (binpack default)
- [ ] If source has clustering columns → recommends `sort` strategy
- [ ] Options: binpack, sort, z-order
- [ ] Description shown:
  - Binpack: "Combines small files without reordering (best for append-heavy workloads)"
  - Sort: "Reorders data by specified columns (best for range queries on specific columns)"
  - Z-Order: "Interleaves multiple columns (best for queries filtering on multiple columns simultaneously)"
- [ ] For sort/z-order: sort columns input appears

**Table Properties:**
- [ ] Shows current properties (format-version: 2, compression: zstd, etc.)
- [ ] "Edit" button → can add/remove key-value pairs
- [ ] Changes saved

**Exclude Toggle:**
- [ ] Checkbox "Exclude from migration"
- [ ] When checked: table section grayed out with "Excluded" badge
- [ ] Excluded tables not sent to load stage

### 4.7 Action Buttons (Footer)

- [ ] **Request Changes** button → submits overrides, report regenerates
- [ ] **Approve & Proceed** button → approves structure, migration proceeds to load
- [ ] After approve: success message "Structure approved. Migration will proceed to load stage."
- [ ] After approve: auto-navigates back to migration list in ~2 seconds
- [ ] Migration status changes from `pending_review` → `approved` → `running` (load stage)

### 4.8 Download Report

- [ ] Click "Download Report" → downloads `iceberg-structure-report-{id}.md`
- [ ] File contains full structure plan in Markdown format

---

## Test Section 5: Cost Analysis

**How to reach:** On the structure review page, there should be a "Cost Analysis" tab alongside the structure report.

### 5.1 Content

- [ ] Setup costs section (S3 storage provisioning, Glue API calls, data transfer)
- [ ] Recurring monthly costs (S3 storage, Glue requests, Athena queries)
- [ ] Projections: 3-month, 6-month, 12-month
- [ ] Optimistic and conservative estimates
- [ ] TCO comparison (BigQuery vs Iceberg) if BQ cost data available

### 5.2 Growth Rate Adjustment

- [ ] Slider or input for monthly data growth rate (%)
- [ ] Changing value recalculates projections dynamically
- [ ] 12-month > 6-month > 3-month costs always
- [ ] Higher growth rate → higher projected costs

### 5.3 Download

- [ ] Cost data included in the downloadable report (PDF or Markdown)

---

## Test Section 6: Load Progress Display

**When:** Migration is in `running` status during the load stage

### 6.1 Progress Indicators

- [ ] Overall progress bar shows % complete
- [ ] Stage indicator shows: export → transfer → review → load
- [ ] Per-table status visible (pending / loading / completed / failed)
- [ ] Progress % updates after each table completes (not jumping 0→100)
- [ ] Parallel loading: multiple tables show "loading" simultaneously (up to 4 by default)

### 6.2 Parallelism (S3 Tables)

- [ ] Default parallelism: 4 concurrent tables
- [ ] Maximum for S3 Tables: 8 (enforced)
- [ ] If parallelism > 8 for S3 Tables: warning shown "S3 Tables API has lower concurrency limits..."
- [ ] Maximum for standard S3 Iceberg: 16

---

## Test Section 7: Validation Results

**When:** Migration status is `completed`

### 7.1 Automatic Validation

- [ ] After completion: per-table row count comparison runs automatically
- [ ] Results table shows: Table Name, Source Row Count, Target Row Count, Status, Timestamp
- [ ] Status: `passed` (counts match), `failed` (mismatch), `skipped` (Athena error)
- [ ] For full load: source count must equal target count (exact match)
- [ ] For incremental: target delta ≥ batch export count

### 7.2 Manual Validation

- [ ] "Run Validation" button available on completed migration
- [ ] Clicking triggers Athena `SELECT COUNT(*)` per table
- [ ] Results update after completion (within 300 seconds per table)
- [ ] If Athena fails: table marked `skipped` with error reason, migration NOT marked failed

---

## Test Section 8: API Endpoint Tests

Use the API docs at http://localhost:8000/api/docs to test these directly.

### 8.1 CRUD

| Method | Endpoint | Expected |
|--------|----------|----------|
| POST | `/api/migrations/bq-iceberg/create` | 201 Created |
| GET | `/api/migrations/bq-iceberg/list` | 200 + `{migrations: [...]}` |
| GET | `/api/migrations/bq-iceberg/{id}` | 200 + migration object |
| PUT | `/api/migrations/bq-iceberg/{id}/update` | 200 |
| DELETE | `/api/migrations/bq-iceberg/{id}` | 200 |

### 8.2 Lifecycle

| Method | Endpoint | Precondition | Expected |
|--------|----------|-------------|----------|
| POST | `/{id}/start` | status=pending/approved | 200 |
| POST | `/{id}/pause` | status=running | 200 |
| POST | `/{id}/resume` | status=paused/failed | 200 |
| POST | `/{id}/cancel` | status=running/paused | 200 |
| GET | `/{id}/status` | any | 200 + status + progress |
| GET | `/{id}/logs` | any | 200 + log entries |

### 8.3 Structure Report & Approval

| Method | Endpoint | Expected |
|--------|----------|----------|
| GET | `/{id}/structure-report` | 200 + full report JSON |
| POST | `/{id}/approve-structure` | 200 + `{message: "..."}` |
| POST | `/{id}/request-changes` | 200 + `{message: "..."}` |
| POST | `/{id}/custom-structure` | 200 + validation result |
| GET | `/{id}/download-report` | 200 + Markdown blob |

### 8.4 Cost Analysis

| Method | Endpoint | Expected |
|--------|----------|----------|
| GET | `/{id}/cost-analysis` | 200 + cost report |
| POST | `/{id}/cost-analysis/recalculate` | 200 + updated report |

### 8.5 Validation

| Method | Endpoint | Expected |
|--------|----------|----------|
| POST | `/{id}/validate` | 200 + validation triggered |
| GET | `/{id}/validation-results` | 200 + per-table results |

### 8.6 Workspace Isolation

- [ ] Request migration from workspace 1 using workspace 2 token → 403 or empty results
- [ ] All list endpoints must filter by workspace_id

---

## Test Section 9: Production Hardening (S3 Tables Only)

These features apply only when `destination_type = iceberg_s3_tables`.

### 9.1 Maintenance Configuration

After table creation, `put_table_maintenance_configuration()` called with:
- [ ] `icebergCompaction.isEnabled = true`
- [ ] `targetFileSizeMB` = user-configured (64-512, default 512)
- [ ] `icebergSnapshotManagement.isEnabled = true`
- [ ] `minSnapshotsToKeep` = user-configured (default 30)
- [ ] `maxSnapshotAgeHours` = user-configured (default 720)

Check backend logs for: `INFO - Maintenance configuration applied for table <name>`

### 9.2 Compaction Strategy

After approving structure with `sort` strategy:
- [ ] Backend logs show: compaction strategy applied
- [ ] Sort columns included in maintenance config payload

### 9.3 glue.id Validation

- [ ] `glue.id` derived from ARN: `{account_id}:s3tablescatalog/{bucket-name}`
- [ ] Visible in prerequisites checklist on structure review page
- [ ] Invalid glue.id → error: "Invalid glue.id format. Expected: {account_id}:s3tablescatalog/{bucket-name}"

### 9.4 API Throttling (Retry)

When S3 Tables API returns 429/SlowDown:
- [ ] WARNING logged: table_name, operation, retry count, backoff delay
- [ ] Retries: 1s, 2s, 4s, 8s, 16s (exponential backoff, max 5 retries)
- [ ] After 5 exhausted: table shard marked failed with `S3_TABLES_THROTTLED`
- [ ] Other tables continue unaffected

### 9.5 Hidden Partitioning

All time-based columns must use transform functions, never identity:
- [ ] DATE column → `day()` transform
- [ ] TIMESTAMP HOUR → `hour()` transform
- [ ] TIMESTAMP MONTH → `month()` transform
- [ ] TIMESTAMP YEAR → `year()` transform
- [ ] Structure review shows: e.g., "Partitioned by `days(event_timestamp)`"
- [ ] Identity partition on time column → error

### 9.6 Incremental Watermark

After incremental load completes:
- [ ] `checkpoint_data.file_time_watermarks[table_name]` updated
- [ ] Next incremental load only processes files with `file_modification_time > watermark`
- [ ] Watermark stored as ISO 8601 UTC: `2024-01-15T10:30:00Z`
- [ ] Watermark NOT updated on partial failure
- [ ] Full reload resets watermark to null

---

## Test Section 10: Backend Unit & Property Tests

Run from `backend/` directory:

```bash
# All Iceberg tests
.venv\Scripts\python.exe -m pytest tests/unit/test_bq_iceberg_models.py tests/unit/test_bq_iceberg_type_mapper.py tests/unit/test_iceberg_orchestrator.py -v

# Property tests
.venv\Scripts\python.exe -m pytest tests/property/test_bq_iceberg_type_mapping.py tests/property/test_bq_iceberg_schema_validation.py -v

# Production hardening tests
.venv\Scripts\python.exe -m pytest tests/unit/test_iceberg_production_hardening.py tests/property/test_iceberg_production_hardening.py -v

# Integration tests
.venv\Scripts\python.exe -m pytest tests/integration/test_bq_iceberg_api.py -v
```

### Key Properties Being Tested

| Property | What it verifies |
|----------|-----------------|
| Type mapping completeness | Every BQ type maps to correct Iceberg type |
| Nullability | REQUIRED → non-nullable, NULLABLE/REPEATED → optional |
| Struct depth | Nesting ≤15 preserved, >15 flattened to JSON string |
| Partition transform | day/hour/month/year applied correctly |
| Sort order preservation | Clustering column sequence maintained |
| Row count validation | Full load: exact match; incremental: delta ≥ batch |
| Progress % | floor((completed/total) * 100) |
| Watermark monotonicity | New watermark only written if > existing |
| Deduplication on resume | Only new files registered, no duplicates |
| State machine transitions | Only valid status transitions succeed |

---

## Known Issues & Workarounds

| Issue | Workaround |
|-------|-----------|
| Migration stuck in `pending_review` | Manually navigate to `/migrations/bq-iceberg/{id}/structure-review` and approve |
| `workspace_id FK violation` | Default org + workspace created in DB (already fixed) |
| Cost analysis tab not visible | Check if `GET /{id}/cost-analysis` returns data; may need assessment data first |
| Structure report empty tables | Ensure migration has completed export stage before reviewing |

---

## Quick Test Sequence (Happy Path)

1. Go to http://localhost:3000 → Login
2. Sidebar → **Migrations** → **BigQuery → Iceberg** tab
3. Click **New Migration**
4. Fill in form with sample data (Section 2.7 above)
5. Click Create → verify `pending` status in list
6. Click **Start** → watch status → `running` → `pending_review`
7. Click **Review** → check prerequisites, warnings, table structures
8. Optionally adjust partition/sort/compaction settings
9. Click **Approve & Proceed**
10. Watch status → `running` (load stage) → `completed`
11. Verify validation results show `passed` for all tables
12. Verify in AWS: tables created in Glue Data Catalog, data in S3/S3 Tables

---

*Last updated: June 2026*
*Feature: BQ → Iceberg Migration (bq-to-iceberg-migration + iceberg-production-hardening specs)*
