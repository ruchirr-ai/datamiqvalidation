# Implementation Plan: Validation UX Redesign

## Overview

Redesign the Validation Engine UI/UX across backend and frontend. Backend changes add a `run_name` column (with Alembic migration), an `include_table_results` query parameter on the list endpoint, and updated schemas. Frontend changes introduce run naming in the create form, inline expandable rows with per-table status on the dashboard, human-readable table summaries, row-click navigation, layout/alignment fixes, and richer status badges on the detail page. Implementation language: Python (FastAPI) for backend, TypeScript (React) for frontend.

## Tasks

- [x] 1. Database migration and model update for run_name
  - [x] 1.1 Create Alembic migration 032 to add run_name column
    - Create `backend/alembic/versions/032_add_run_name_to_validation_runs.py`
    - Add nullable VARCHAR(255) column `run_name` to `validation_runs` table using `op.add_column`
    - Include idempotency check (inspect columns before adding) following the pattern in migration 031
    - Implement downgrade function that drops the `run_name` column
    - Use revision='032', down_revision='031'
    - _Requirements: 9.1, 9.2, 9.3_

  - [x] 1.2 Add run_name column to ValidationRun model
    - Add `run_name = Column(String(255), nullable=True)` to `backend/models/validation_run.py`
    - Update `to_dict()` to include `'run_name': self.run_name`
    - _Requirements: 1.1_

  - [x] 1.3 Update Pydantic schemas for run_name and table_results
    - In `backend/models/validation_schemas.py`:
    - Add `run_name: Optional[str] = Field(None, max_length=255)` to `CreateValidationRunRequest`
    - Add `run_name: Optional[str] = None` to `ValidationRunResponse`
    - Add `table_results: Optional[list[ValidationTableResultResponse]] = None` to `ValidationRunResponse`
    - _Requirements: 1.2, 6.4_

  - [x] 1.4 Write unit tests for run_name schema validation
    - Test `CreateValidationRunRequest` accepts valid run_name (1–255 chars)
    - Test `CreateValidationRunRequest` accepts missing/None run_name
    - Test `CreateValidationRunRequest` rejects run_name exceeding 255 chars
    - Test `ValidationRunResponse` serializes run_name and table_results correctly
    - Include sample payloads for each case
    - _Requirements: 1.1, 1.2, 6.4_

- [x] 2. Backend API changes for run_name and include_table_results
  - [x] 2.1 Update ValidationRepository with table results eager-load method
    - Add `list_runs_with_table_results(workspace_id, migration_id, status, page, page_size)` to `backend/repositories/validation_repository.py`
    - Use SQLAlchemy `joinedload` or a secondary query to fetch `ValidationTableResult` records alongside runs
    - Return the same `(list, total_count)` tuple as `list_runs`
    - All queries MUST include workspace_id filter
    - _Requirements: 6.1, 6.2_

  - [x] 2.2 Update ValidationService for run_name and table results
    - In `backend/services/validation_service.py`:
    - Update `create_validation_run()` to accept and persist `run_name` parameter
    - Update `list_runs()` to accept `include_table_results: bool` parameter; when true, call `list_runs_with_table_results` and include summary-level table result fields in each run response
    - _Requirements: 1.3, 1.4, 6.1, 6.2, 6.3_

  - [x] 2.3 Update ValidationRouter for run_name and include_table_results
    - In `backend/routers/validation_router.py`:
    - Update `POST /api/validations/` to pass `run_name` from request body to service
    - Update `GET /api/validations/` to accept `include_table_results: bool = False` query parameter and pass to service
    - _Requirements: 1.3, 6.1, 6.2, 6.3_

  - [x] 2.4 Write unit tests for run_name persistence and table results inclusion
    - Test `create_validation_run` with run_name persists correctly
    - Test `create_validation_run` without run_name stores None
    - Test `list_runs` with `include_table_results=true` returns table_results array
    - Test `list_runs` with `include_table_results=false` returns no table_results
    - Test status derivation: all passed → "completed", any failed → "failed", error with no failed → "failed"
    - Mock repository and cache dependencies
    - Include sample payloads following Arrange-Act-Assert pattern
    - _Requirements: 1.3, 1.4, 2.1, 2.2, 2.3, 6.1, 6.2, 6.3_

  - [x] 2.5 Write property test for run_name round-trip
    - **Property 1: Run Name Persistence Round-Trip**
    - Create file `backend/tests/property/test_property_run_name.py`
    - For any string s of length 0–255, creating a run with run_name=s and retrieving it must return run_name == s; creating without run_name must return None
    - Use Hypothesis text strategy with max_size=255, minimum 100 iterations
    - **Validates: Requirements 1.1, 1.3, 1.4**

  - [x] 2.6 Write property test for status derivation consistency
    - **Property 2: Status Derivation Consistency**
    - Create file `backend/tests/property/test_property_status_derivation.py`
    - For any set of table results with step statuses from {passed, failed, error}: all passed → "completed"; any failed → "failed"; any error and no failed → "failed"
    - Use Hypothesis with lists of sampled_from statuses, minimum 100 iterations
    - **Validates: Requirements 2.1, 2.2, 2.3**

  - [x] 2.7 Write integration tests for run_name and include_table_results endpoints
    - In `backend/tests/integration/test_validation_router_integration.py`:
    - Test `POST /api/validations/` with run_name → `GET /api/validations/{id}` returns run_name
    - Test `GET /api/validations/?include_table_results=true` returns table_results array
    - Test `GET /api/validations/?include_table_results=false` returns no table_results
    - Include sample payloads for all scenarios
    - _Requirements: 1.3, 6.1, 6.2, 6.3_

- [x] 3. Checkpoint - Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Frontend API client updates
  - [x] 4.1 Update validationApi.ts types and methods
    - In `frontend/src/services/validationApi.ts`:
    - Add `run_name?: string` to `CreateValidationRunRequest`
    - Add `run_name: string | null` and `table_results?: ValidationTableResult[] | null` to `ValidationRun` interface
    - Update `listValidationRuns()` to accept optional `includeTableResults: boolean` parameter and append `include_table_results=true` to query params when set
    - _Requirements: 1.2, 6.1, 6.4_

- [x] 5. Dashboard page — run naming and table column redesign
  - [x] 5.1 Add run_name input to the create form
    - In `frontend/src/pages/ValidationDashboardPage.tsx`:
    - Add a text input labeled "Run Name" (optional, max 255 chars) before the migration selector in the create form
    - Wire the input value to the `handleCreate` payload as `run_name`
    - _Requirements: 1.5, 1.6_

  - [x] 5.2 Redesign table columns with chevron, name, and human-readable summary
    - Replace current table columns with: chevron toggle, Name (run_name or "Run #id" fallback), Status badge, Progress, Tables summary ("3 Passed, 1 Failed"), Started, Duration, Actions
    - Implement `formatTableSummary()` helper that omits zero-count categories and uses color-coded spans (green passed, red failed, amber errors)
    - Add CSS classes `.summary-passed`, `.summary-failed`, `.summary-error` to `ValidationDashboardPage.css`
    - _Requirements: 1.5, 3.1, 3.2, 3.3_

  - [x] 5.3 Write component tests for run naming and table summary
    - Test dashboard renders run_name as primary identifier
    - Test dashboard renders "Run #id" fallback when run_name is null
    - Test human-readable table summary renders correct counts with colors
    - Test summary omits zero-count categories
    - Test create form includes run_name input
    - Mock validationApi methods
    - _Requirements: 1.5, 1.6, 3.1, 3.2, 3.3_

- [x] 6. Dashboard page — expandable rows and row click navigation
  - [x] 6.1 Implement expandable row toggle with chevron
    - Add state: `expandedRunId`, `expandedTableResults`, `expandedLoading`, `expandedError`
    - Add chevron button in first column with `e.stopPropagation()` to prevent navigation
    - On chevron click: toggle expand/collapse; if not cached, fetch from `GET /api/validations/{runId}/tables`
    - Render expanded row as `<tr>` with `<td colSpan>` containing nested table (Table Name, DDL, Row Count, Data Match, Overall) with mini status badges
    - Cache fetched results in component state to avoid redundant API calls
    - Support keyboard activation (Enter and Space) on chevron button
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 10.3_

  - [x] 6.2 Implement loading and error states for expandable rows
    - Show loading spinner inside expanded area while fetching table results
    - Show inline error message with retry button if fetch fails
    - Add CSS classes `.validation-expanded-loading`, `.validation-expanded-error` to `ValidationDashboardPage.css`
    - _Requirements: 10.1, 10.2_

  - [x] 6.3 Implement row click navigation to detail page
    - Add `onClick` handler on each `<tr>` that navigates to `/validations/{runId}`
    - Ensure chevron click calls `e.stopPropagation()` and does NOT navigate
    - Ensure delete button calls `e.stopPropagation()` and does NOT navigate
    - Use `cursor: pointer` on rows, `cursor: default` on chevron/action cells
    - _Requirements: 5.1, 5.2, 5.3_

  - [x] 6.4 Add chevron and expandable row CSS styles
    - Add `.validation-chevron-btn` styles (transparent bg, 28px hit target, rotate animation on expand)
    - Add `.validation-expanded-row` and `.validation-nested-table` styles
    - Add mini status badge styles for nested table cells
    - _Requirements: 4.1, 4.5_

  - [x] 6.5 Write component tests for expandable rows and navigation
    - Test chevron click expands row and shows nested table with correct data
    - Test chevron click on expanded row collapses it
    - Test chevron click does NOT trigger navigation
    - Test row click (outside chevron/actions) navigates to detail page
    - Test delete button click does NOT navigate
    - Test loading spinner shows while fetching table results
    - Test error message with retry shows on fetch failure
    - Test re-expanding a previously expanded row uses cached data (no redundant API call)
    - Test keyboard activation (Enter/Space) on chevron
    - Mock validationApi methods
    - _Requirements: 4.1–4.7, 5.1–5.3, 10.1–10.3_

  - [x] 6.6 Write property test for table summary accuracy
    - **Property 3: Table Summary Accuracy**
    - For any non-negative integers (passed, failed, errors), the formatTableSummary function must include exactly the non-zero categories with correct counts and omit zero-count categories
    - Test in frontend test file or backend depending on where the logic lives
    - **Validates: Requirements 3.1, 3.2, 3.3**

- [x] 7. Dashboard page — layout and alignment fixes
  - [x] 7.1 Fix progress bar vertical centering and actions alignment
    - In `ValidationDashboardPage.css`:
    - Progress bar cell: `display: flex; align-items: center; gap: 8px;`
    - Actions cell: `display: flex; justify-content: center; gap: 4px;`
    - Reduce header-to-toolbar gap to `8px`
    - Table rows: consistent `height: 48px; padding: 0 12px;`
    - Empty state: vertically compact and centered
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 8. Checkpoint - Ensure all dashboard tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Detail page — richer status display and run_name header
  - [x] 9.1 Display run_name in detail page header
    - In `frontend/src/pages/ValidationDetailPage.tsx`:
    - Update page header to show `run.run_name || "Validation Run #" + run.id`
    - _Requirements: 8.3_

  - [x] 9.2 Replace SVG status icons with text-based StatusBadge component
    - Replace `StatusIcon` component with `StatusBadge` that renders colored `<span>` with text labels: "Passed" (green), "Failed" (red), "Error" (amber), "Pending" (grey)
    - Use class `.vd-status-badge` with status-specific modifiers (`.passed`, `.failed`, `.error`, `.pending`)
    - Apply to all DDL, Row Count, and Data Match status cells in the table results
    - _Requirements: 8.1, 8.2_

  - [x] 9.3 Add "Tables" summary card to detail page
    - Add a "Tables" card showing `tables_total` count alongside existing Passed, Failed, Errors summary cards
    - Update CSS grid/flex layout in `ValidationDetailPage.css` to accommodate 4 cards
    - _Requirements: 8.4_

  - [x] 9.4 Add StatusBadge CSS styles to detail page
    - In `ValidationDetailPage.css`:
    - Add `.vd-status-badge` base styles and color variants: green (#4CAF50) for passed, red (#DC2626) for failed, amber (#F59E0B) for error, grey (#6B7280) for pending
    - Update summary cards layout for 4-card grid
    - _Requirements: 8.1, 8.2_

  - [x] 9.5 Write component tests for detail page changes
    - Test detail page displays run_name in header when available
    - Test detail page displays "Validation Run #id" fallback when run_name is null
    - Test StatusBadge renders text labels ("Passed", "Failed", "Error", "Pending") with correct CSS classes
    - Test summary cards include "Tables" card with correct count
    - Mock validationApi methods
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [x] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- The design uses Python (FastAPI) and TypeScript (React), so no language selection was needed
- All backend queries must include workspace_id for tenant isolation
- CSS files use CRLF line endings (Windows environment)
