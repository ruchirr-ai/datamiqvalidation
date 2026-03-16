# Requirements Document

## Introduction

The Validation Engine UI (dashboard list page and detail page) requires a comprehensive redesign to improve usability, information density, and visual polish. The current implementation hides critical per-table validation status behind modal dialogs, uses cryptic shorthand for table counts, lacks run naming, shows inconsistent status badges, and has alignment and whitespace issues. This redesign brings the validation pages up to enterprise-grade quality consistent with the Snowflake-inspired design system used across DataMIQ.

## Glossary

- **Dashboard**: The `ValidationDashboardPage` component that lists all validation runs in a paginated table with filters and a create form.
- **Detail_Page**: The `ValidationDetailPage` component that displays comprehensive information for a single validation run including per-table results with expandable DDL, row count, and data match panels.
- **Validation_Run**: A record in the `validation_runs` table representing a single execution of post-migration data validation across one or more tables.
- **Table_Result**: A record in the `validation_table_results` table representing the DDL, row count, and data match outcomes for a single table within a Validation_Run.
- **Run_Name**: An optional user-provided label for a Validation_Run to aid identification (e.g. "Pre-release check" or "Nightly validation").
- **Expandable_Row**: A table row on the Dashboard that can be toggled open via a chevron icon to reveal inline per-table validation status without navigating away.
- **Status_Badge**: A colored label indicating the status of a Validation_Run or Table_Result (e.g. pending, running, completed, failed).
- **Table_Summary**: A human-readable string summarizing per-table outcomes (e.g. "3 Passed, 1 Failed") replacing the cryptic "3p / 1f / 0e" format.
- **Backend_API**: The FastAPI endpoints under `/api/validations/` that serve validation data.
- **ValidationRun_Model**: The SQLAlchemy model class `ValidationRun` in `backend/models/validation_run.py`.
- **ValidationRun_Schema**: The Pydantic schemas in `backend/models/validation_schemas.py` for request/response serialization.

## Requirements

### Requirement 1: Run Naming

**User Story:** As a user, I want to give my validation runs a descriptive name, so that I can easily identify them in the dashboard list.

#### Acceptance Criteria

1. THE ValidationRun_Model SHALL include an optional `run_name` column of type VARCHAR(255) with a default value of NULL.
2. THE ValidationRun_Schema SHALL include an optional `run_name` field in both the `CreateValidationRunRequest` and `ValidationRunResponse` schemas.
3. WHEN a user creates a validation run with a `run_name` value, THE Backend_API SHALL persist the `run_name` on the Validation_Run record.
4. WHEN a user creates a validation run without a `run_name` value, THE Backend_API SHALL store NULL for the `run_name` field.
5. THE Dashboard SHALL display the `run_name` as the primary identifier for each run row, falling back to "Run #<id>" when `run_name` is NULL or empty.
6. THE Dashboard create form SHALL include a text input field labeled "Run Name" that accepts up to 255 characters and is optional.

### Requirement 2: Accurate Run Status Derivation

**User Story:** As a user, I want the dashboard status badge to accurately reflect the validation outcome, so that I can trust the status at a glance without opening the detail page.

#### Acceptance Criteria

1. WHEN all Table_Results for a Validation_Run have a status of "completed" and all individual step statuses (ddl_status, row_count_status, data_match_status) are "passed", THE Backend_API SHALL set the Validation_Run status to "completed".
2. WHEN any Table_Result for a Validation_Run has a ddl_status, row_count_status, or data_match_status of "failed", THE Backend_API SHALL set the Validation_Run status to "failed".
3. WHEN any Table_Result for a Validation_Run has a status of "error" and no Table_Result has a "failed" step status, THE Backend_API SHALL set the Validation_Run status to "failed".
4. THE Dashboard Status_Badge SHALL display the status value returned by the Backend_API without client-side overrides.
5. THE Detail_Page Status_Badge SHALL display the same status value as the Dashboard for the same Validation_Run.

### Requirement 3: Human-Readable Table Summary

**User Story:** As a user, I want to see table validation outcomes in plain language, so that I can understand results without decoding abbreviations.

#### Acceptance Criteria

1. THE Dashboard SHALL display table outcomes using the format "<N> Passed, <N> Failed, <N> Errors" where N is the respective count.
2. WHEN a count is zero, THE Dashboard SHALL omit that category from the display (e.g. "3 Passed, 1 Failed" when errors is zero).
3. THE Dashboard SHALL use color-coded text for each category: green for Passed, red for Failed, amber for Errors.

### Requirement 4: Inline Expandable Rows

**User Story:** As a user, I want to expand a validation run row on the dashboard to see per-table DDL, row count, and data match status inline, so that I can quickly assess results without navigating to the detail page.

#### Acceptance Criteria

1. THE Dashboard SHALL display a chevron icon in the first column of each Validation_Run row that toggles the Expandable_Row open and closed.
2. WHEN the chevron is clicked, THE Dashboard SHALL expand the row to show a nested table listing each Table_Result with columns: Table Name, DDL status, Row Count status, Data Match status, and Overall status.
3. WHEN the chevron is clicked on an already-expanded row, THE Dashboard SHALL collapse the Expandable_Row.
4. THE Dashboard SHALL fetch per-table results for the expanded run from the Backend_API (using the existing `GET /api/validations/{run_id}/tables` endpoint or an equivalent lightweight response).
5. WHEN the Expandable_Row is open, THE Dashboard SHALL display status badges (passed, failed, error, pending) for each validation step of each table.
6. THE chevron click SHALL NOT trigger navigation to the Detail_Page.
7. THE Dashboard SHALL support keyboard activation (Enter and Space keys) for the chevron toggle.

### Requirement 5: Row Click Navigation to Detail Page

**User Story:** As a user, I want to click on a validation run row to navigate to its detail page, so that I can view comprehensive results.

#### Acceptance Criteria

1. WHEN a user clicks on a Validation_Run row (outside the chevron and action buttons), THE Dashboard SHALL navigate to the Detail_Page at `/validations/<run_id>`.
2. WHEN a user clicks the chevron icon, THE Dashboard SHALL toggle the Expandable_Row without navigating.
3. WHEN a user clicks a delete button, THE Dashboard SHALL trigger the delete action without navigating.

### Requirement 6: Backend API — Table Results in List Response

**User Story:** As a developer, I want the list runs API to optionally include lightweight table result summaries, so that the dashboard can render expandable rows without additional API calls per run.

#### Acceptance Criteria

1. THE Backend_API list runs endpoint (`GET /api/validations/`) SHALL accept an optional query parameter `include_table_results` (boolean, default false).
2. WHEN `include_table_results` is true, THE Backend_API SHALL include a `table_results` array on each Validation_Run in the response containing summary-level Table_Result objects (id, table_name, ddl_status, row_count_status, data_match_status, status).
3. WHEN `include_table_results` is false or omitted, THE Backend_API SHALL return Validation_Run objects without the `table_results` field.
4. THE ValidationRun_Schema `ValidationRunResponse` SHALL include an optional `table_results` field of type `list[ValidationTableResultResponse] | None`.

### Requirement 7: Dashboard Layout and Alignment Fixes

**User Story:** As a user, I want the dashboard to look polished and professional with proper alignment and reduced whitespace, so that it feels like an enterprise-grade application.

#### Acceptance Criteria

1. THE Dashboard progress bar and progress percentage text SHALL be vertically centered within the table cell.
2. THE Dashboard action buttons (logs, delete) SHALL be horizontally centered within the Actions column.
3. THE Dashboard SHALL reduce excessive vertical whitespace between the header, toolbar, and table sections.
4. THE Dashboard empty state SHALL be vertically compact and centered within the available space.
5. THE Dashboard table rows SHALL have consistent row height and padding matching the Snowflake-inspired design system.

### Requirement 8: Detail Page Richer Status Display

**User Story:** As a user, I want the detail page to show richer status information instead of minimal check/cross icons, so that I can understand validation outcomes at a glance.

#### Acceptance Criteria

1. THE Detail_Page SHALL display status for each validation step (DDL, Row Count, Data Match) using colored Status_Badges with text labels ("Passed", "Failed", "Error", "Pending") instead of bare SVG check/cross icons.
2. THE Detail_Page Status_Badges SHALL use the same color scheme as the Dashboard: green for passed, red for failed, amber for error, grey for pending.
3. THE Detail_Page SHALL display the `run_name` in the header when available, falling back to "Validation Run #<id>" when `run_name` is NULL or empty.
4. THE Detail_Page summary cards SHALL include a "Tables" label showing the total table count alongside the existing Passed, Failed, and Errors cards.

### Requirement 9: Database Migration for run_name Column

**User Story:** As a developer, I want a database migration that adds the `run_name` column to the `validation_runs` table, so that the schema change is versioned and repeatable.

#### Acceptance Criteria

1. THE migration script SHALL add a nullable VARCHAR(255) column named `run_name` to the `validation_runs` table.
2. THE migration script SHALL include a downgrade function that removes the `run_name` column.
3. THE migration script SHALL be idempotent and safe to run on an existing database with data.

### Requirement 10: Expandable Row Loading and Error States

**User Story:** As a user, I want to see loading and error feedback when expanding a run row, so that I know the system is working and can handle failures gracefully.

#### Acceptance Criteria

1. WHILE the Dashboard is fetching table results for an Expandable_Row, THE Dashboard SHALL display a loading spinner within the expanded area.
2. IF the fetch for table results fails, THEN THE Dashboard SHALL display an inline error message within the expanded area with a retry option.
3. THE Dashboard SHALL cache fetched table results in component state so that re-expanding a previously expanded row does not trigger a redundant API call.
