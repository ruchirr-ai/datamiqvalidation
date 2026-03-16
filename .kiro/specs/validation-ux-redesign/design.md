# Technical Design Document

## Introduction

This document describes the technical design for the Validation Engine UI/UX Redesign. It covers database schema changes, backend API modifications, and frontend component updates needed to satisfy the requirements in `requirements.md`. The design builds on the existing validation module codebase and follows the project's Snowflake-inspired design system, multi-tenant architecture, and caching strategy.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (React)                        │
│  ┌──────────────────────┐  ┌─────────────────────────────┐  │
│  │ ValidationDashboard  │  │  ValidationDetailPage       │  │
│  │  - Run naming form   │  │  - run_name header          │  │
│  │  - Expandable rows   │  │  - Status badges (text)     │  │
│  │  - Human-readable    │  │  - Tables summary card      │  │
│  │    table summaries   │  │                             │  │
│  │  - Chevron toggle    │  │                             │  │
│  │  - Row click nav     │  │                             │  │
│  └──────────┬───────────┘  └──────────┬──────────────────┘  │
│             │                         │                     │
│  ┌──────────▼─────────────────────────▼──────────────────┐  │
│  │              validationApi.ts                         │  │
│  │  - run_name in types                                  │  │
│  │  - include_table_results param                        │  │
│  └──────────┬────────────────────────────────────────────┘  │
└─────────────┼───────────────────────────────────────────────┘
              │ HTTP
┌─────────────▼───────────────────────────────────────────────┐
│                   Backend (FastAPI)                          │
│  ┌──────────────────────┐  ┌─────────────────────────────┐  │
│  │ validation_router.py │  │ validation_service.py       │  │
│  │  - run_name in POST  │  │  - run_name persistence     │  │
│  │  - include_table_    │  │  - status derivation logic  │  │
│  │    results query     │  │  - table results in list    │  │
│  └──────────┬───────────┘  └──────────┬──────────────────┘  │
│             │                         │                     │
│  ┌──────────▼─────────────────────────▼──────────────────┐  │
│  │           validation_repository.py                    │  │
│  │  - run_name column queries                            │  │
│  │  - eager-load table results                           │  │
│  └──────────┬────────────────────────────────────────────┘  │
└─────────────┼───────────────────────────────────────────────┘
              │ SQL
┌─────────────▼───────────────────────────────────────────────┐
│                   PostgreSQL                                │
│  validation_runs (+ run_name VARCHAR(255) NULL)             │
│  validation_table_results (unchanged)                       │
└─────────────────────────────────────────────────────────────┘
```

## Database Changes

### Migration 032: Add run_name Column

**File**: `backend/alembic/versions/032_add_run_name_to_validation_runs.py`

```sql
-- upgrade
ALTER TABLE validation_runs ADD COLUMN run_name VARCHAR(255) NULL;

-- downgrade
ALTER TABLE validation_runs DROP COLUMN run_name;
```

The migration uses `op.add_column` / `op.drop_column` and checks for column existence before adding to ensure idempotency.

### Model Change

**File**: `backend/models/validation_run.py`

Add one column to `ValidationRun`:

```python
run_name = Column(String(255), nullable=True)
```

Update `to_dict()` to include `'run_name': self.run_name`.

## Backend API Changes

### Schema Changes

**File**: `backend/models/validation_schemas.py`

1. `CreateValidationRunRequest` — add optional field:
   ```python
   run_name: Optional[str] = Field(None, max_length=255, description="Optional display name for the run")
   ```

2. `ValidationRunResponse` — add optional field:
   ```python
   run_name: Optional[str] = None
   table_results: Optional[list[ValidationTableResultResponse]] = None
   ```

### Router Changes

**File**: `backend/routers/validation_router.py`

1. `POST /api/validations/` — pass `run_name` from request to `service.create_validation_run()`.

2. `GET /api/validations/` — accept `include_table_results: bool = False` query parameter. When true, call service method that eager-loads table results and includes them in the response.

### Service Changes

**File**: `backend/services/validation_service.py`

1. `create_validation_run()` — accept and persist `run_name` parameter.

2. `list_runs()` — accept `include_table_results` parameter. When true, join-load `validation_table_results` for each run and include summary-level fields in the response.

3. Status derivation — after all table validations complete, derive the run status:
   - If all table step statuses are "passed" → run status = "completed"
   - If any table step status is "failed" → run status = "failed"
   - If any table status is "error" (and none "failed") → run status = "failed"

### Repository Changes

**File**: `backend/repositories/validation_repository.py`

1. Add method `list_runs_with_table_results()` that uses SQLAlchemy `joinedload` or a secondary query to fetch table results alongside runs.

### Cache Invalidation

**File**: `backend/services/validation_cache.py`

No new cache keys needed. Existing cache invalidation on run create/update/delete covers the changes. The `include_table_results` variant bypasses cache (or uses a separate cache key with short TTL) since it's a heavier payload.

## Frontend Changes

### Type Updates

**File**: `frontend/src/services/validationApi.ts`

1. Add `run_name?: string` to `CreateValidationRunRequest`.
2. Add `run_name: string | null` and `table_results?: ValidationTableResult[] | null` to `ValidationRun` interface.
3. Update `listValidationRuns()` to accept optional `includeTableResults` boolean and append `include_table_results=true` to query params when set.

### Dashboard Page Changes

**File**: `frontend/src/pages/ValidationDashboardPage.tsx`

#### Create Form — Run Name Input
Add a text input for `run_name` in the create form, placed before the migration selector. Wire it to the `handleCreate` payload.

#### Table Columns Redesign
Replace the current table columns with:

| Column | Content |
|--------|---------|
| ▶ (chevron) | Expand/collapse toggle |
| Name | `run_name` or "Run #<id>" fallback |
| Status | Colored status badge |
| Progress | Progress bar (running) or percentage |
| Tables | Human-readable: "3 Passed, 1 Failed" |
| Started | Formatted date |
| Duration | Formatted duration |
| Actions | Logs + Delete buttons |

#### Expandable Rows
State management:
```typescript
const [expandedRunId, setExpandedRunId] = useState<number | null>(null);
const [expandedTableResults, setExpandedTableResults] = useState<Record<number, ValidationTableResult[]>>({});
const [expandedLoading, setExpandedLoading] = useState<Record<number, boolean>>({});
const [expandedError, setExpandedError] = useState<Record<number, string | null>>({});
```

When chevron is clicked:
1. If already expanded, collapse (set `expandedRunId` to null).
2. If not expanded, set `expandedRunId` and check cache (`expandedTableResults[runId]`).
3. If not cached, fetch from `GET /api/validations/{runId}/tables`, show loading spinner.
4. On success, cache in `expandedTableResults` and render nested table.
5. On error, show inline error with retry button.

The expanded row renders as a `<tr>` with a single `<td colSpan={8}>` containing a nested table:

| Table Name | DDL | Row Count | Data Match | Overall |
|------------|-----|-----------|------------|---------|

Each cell shows a mini status badge (passed/failed/error/pending).

#### Row Click Navigation
- Clicking anywhere on the row (except chevron and action buttons) navigates to `/validations/{runId}`.
- Chevron click calls `e.stopPropagation()` and toggles expand.
- Delete button already calls `e.stopPropagation()`.

#### Human-Readable Table Summary
Replace `{run.tables_passed}p / {run.tables_failed}f / {run.tables_error}e` with:

```tsx
function formatTableSummary(passed: number, failed: number, errors: number): JSX.Element {
  const parts: JSX.Element[] = [];
  if (passed > 0) parts.push(<span className="summary-passed">{passed} Passed</span>);
  if (failed > 0) parts.push(<span className="summary-failed">{failed} Failed</span>);
  if (errors > 0) parts.push(<span className="summary-error">{errors} Errors</span>);
  if (parts.length === 0) return <span className="summary-none">—</span>;
  return <>{parts.reduce((a, b) => <>{a}, {b}</>)}</>;
}
```

Colors: `.summary-passed { color: #4CAF50; }`, `.summary-failed { color: #DC2626; }`, `.summary-error { color: #F59E0B; }`.

#### Layout & Alignment Fixes
- Progress bar cell: `display: flex; align-items: center; gap: 8px;`
- Actions cell: `display: flex; justify-content: center; gap: 4px;`
- Reduce header-to-toolbar gap from current spacing to `8px`.
- Table rows: consistent `height: 48px; padding: 0 12px;`.

### Dashboard CSS Changes

**File**: `frontend/src/pages/ValidationDashboardPage.css`

- Add `.validation-chevron-btn` styles (transparent background, 28px hit target, rotate animation).
- Add `.validation-expanded-row` and `.validation-nested-table` styles.
- Add `.summary-passed`, `.summary-failed`, `.summary-error` color classes.
- Add `.validation-expanded-loading`, `.validation-expanded-error` styles.
- Fix progress bar vertical centering.
- Fix actions cell horizontal centering.
- Reduce whitespace between header/toolbar/table.

### Detail Page Changes

**File**: `frontend/src/pages/ValidationDetailPage.tsx`

1. Display `run_name` in the page header: `run.run_name || "Validation Run #" + run.id`.
2. Replace SVG check/cross `StatusIcon` with text-based `StatusBadge`:
   ```tsx
   function StatusBadge({ status }: { status: string | null }) {
     const label = status === 'passed' ? 'Passed' : status === 'failed' ? 'Failed' : status === 'error' ? 'Error' : 'Pending';
     return <span className={`vd-status-badge ${status || 'pending'}`}>{label}</span>;
   }
   ```
3. Add a "Tables" summary card showing `tables_total` count alongside existing Passed/Failed/Errors cards.

### Detail Page CSS Changes

**File**: `frontend/src/pages/ValidationDetailPage.css`

- Add `.vd-status-badge` styles with color variants matching dashboard (green/red/amber/grey).
- Update summary cards layout to accommodate the new "Tables" card.

## Correctness Properties

### Property 1: Run Name Persistence Round-Trip
For any string `s` of length 0–255, creating a validation run with `run_name=s` and then retrieving it must return `run_name == s`. Creating without `run_name` must return `run_name == None`.

### Property 2: Status Derivation Consistency
For any set of table results with step statuses drawn from {passed, failed, error}:
- If all steps are "passed" → run status must be "completed"
- If any step is "failed" → run status must be "failed"
- If any table has "error" and no step is "failed" → run status must be "failed"
- The dashboard and detail page must show the same status for the same run.

### Property 3: Table Summary Accuracy
For any non-negative integers (passed, failed, errors), the human-readable summary must:
- Include exactly the non-zero categories
- Show correct counts for each category
- Omit categories with zero count

### Property 4: Expandable Row Data Integrity
For any validation run with N table results, expanding the row must display exactly N rows in the nested table, each with the correct table_name, ddl_status, row_count_status, data_match_status, and overall status.

### Property 5: Navigation Isolation
Clicking the chevron must never trigger navigation. Clicking the row (outside chevron/actions) must always navigate. Clicking delete must never navigate.

## Test Strategy

### Backend Unit Tests
- `test_create_run_with_run_name` — verify run_name persists
- `test_create_run_without_run_name` — verify run_name is None
- `test_list_runs_with_table_results` — verify table_results included when param is true
- `test_list_runs_without_table_results` — verify table_results absent when param is false/omitted
- `test_status_derivation_all_passed` — verify "completed" status
- `test_status_derivation_any_failed` — verify "failed" status
- `test_status_derivation_error_no_failed` — verify "failed" status

### Backend Property Tests
- Property test for run_name round-trip (Hypothesis: text strategy, max_length=255)
- Property test for status derivation (Hypothesis: lists of step statuses)
- Property test for table summary formatting (Hypothesis: non-negative integers)

### Frontend Component Tests
- Dashboard: render with run_name, render fallback "Run #id"
- Dashboard: chevron click expands row, does not navigate
- Dashboard: row click navigates, does not expand
- Dashboard: human-readable table summary renders correctly
- Dashboard: expanded row shows loading, then data, handles error
- Detail page: displays run_name in header
- Detail page: status badges show text labels with correct colors
- Detail page: summary cards include "Tables" count

### Integration Tests
- `POST /api/validations/` with run_name → `GET /api/validations/{id}` returns run_name
- `GET /api/validations/?include_table_results=true` returns table_results array
- `GET /api/validations/?include_table_results=false` returns no table_results

## Files to Modify

| File | Change |
|------|--------|
| `backend/alembic/versions/032_add_run_name_to_validation_runs.py` | New migration |
| `backend/models/validation_run.py` | Add `run_name` column |
| `backend/models/validation_schemas.py` | Add `run_name` + `table_results` fields |
| `backend/routers/validation_router.py` | Add `run_name` to create, `include_table_results` to list |
| `backend/services/validation_service.py` | Persist `run_name`, load table results, status derivation |
| `backend/repositories/validation_repository.py` | Add table results eager-load method |
| `frontend/src/services/validationApi.ts` | Add `run_name`, `table_results`, `includeTableResults` param |
| `frontend/src/pages/ValidationDashboardPage.tsx` | Run name form, expandable rows, table summary, layout fixes |
| `frontend/src/pages/ValidationDashboardPage.css` | Chevron, expanded row, summary, alignment styles |
| `frontend/src/pages/ValidationDetailPage.tsx` | Run name header, status badges, tables card |
| `frontend/src/pages/ValidationDetailPage.css` | Status badge styles, summary card layout |
| `backend/tests/unit/test_validation_service.py` | New tests for run_name, status derivation |
| `backend/tests/unit/test_validation_router.py` | New tests for run_name, include_table_results |
| `backend/tests/property/test_property_run_name.py` | New property test file |
| `backend/tests/property/test_property_status_derivation.py` | New property test file |
| `frontend/src/pages/__tests__/ValidationDashboardPage.test.tsx` | New tests for expandable rows, summary, navigation |
| `frontend/src/pages/__tests__/ValidationDetailPage.test.tsx` | New tests for run_name, status badges |
