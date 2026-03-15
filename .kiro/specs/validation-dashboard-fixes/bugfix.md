# Bugfix Requirements Document

## Introduction

Two visual bugs exist on the Validation Dashboard page (`ValidationDashboardPage`). First, the "Total Rows" column in the "New Validation Run" form shows "—" instead of the actual row count for certain tables when the migration's `checkpoint_data` does not contain `num_rows` in its `export_results` entries or when the table name doesn't match after splitting on `.`. Second, info tooltips (DDL, Row Count, Data Match, Bedrock Model) overflow off the right edge of the viewport because the CSS uses centered absolute positioning (`left: 50%; transform: translateX(-50%)`) without accounting for viewport boundaries. The same tooltip overflow pattern also exists in `StandaloneConverterPage.css` and `BatchConverterPage.css` for `.sqlglot-tooltip`.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a migration's `checkpoint_data.export_results` entries do not contain a `num_rows` field (or it is null) AND the per-table fallback keys (`row_count`, `total_rows`) are also absent from `checkpoint_data` THEN the system returns `table_row_counts[table_name] = None` from `get_migration_info()`, causing the frontend to render "—" in the Total Rows column instead of the actual row count

1.2 WHEN a migration's `checkpoint_data.export_results` contains entries where the `table` field uses a fully-qualified reference (e.g. `project.dataset.table`) AND the table name extracted via `rsplit(".", 1)[-1]` does not match the table name in `migration.source_tables` THEN the system fails to associate the row count with the correct table, resulting in `None` for that table's row count

1.3 WHEN an info tooltip (DDL, Row Count, Data Match, or Bedrock Model) is rendered near the right edge of the viewport THEN the tooltip overflows beyond the right edge of the visible area because the CSS positions it with `left: 50%; transform: translateX(-50%)` without any viewport boundary constraint

1.4 WHEN a `.sqlglot-tooltip` in `StandaloneConverterPage` or `BatchConverterPage` is rendered near the left or right edge of the viewport THEN the tooltip similarly overflows beyond the visible area due to the same centered absolute positioning pattern

### Expected Behavior (Correct)

2.1 WHEN a migration's `checkpoint_data.export_results` entries do not contain `num_rows` AND the per-table fallback keys are absent THEN the system SHALL attempt additional fallback sources (e.g. `total_rows_exported` in the export result, or `row_count` from the BigQuery assessment metadata via `AssessmentTable`) and return a numeric count instead of `None` wherever possible

2.2 WHEN a migration's `checkpoint_data.export_results` contains fully-qualified table references THEN the system SHALL correctly extract the table name by splitting on `.` and taking the last segment, and SHALL perform case-insensitive matching against `migration.source_tables` to ensure the row count is associated with the correct table

2.3 WHEN an info tooltip (`.vtc-tooltip`) is rendered near the right edge of the viewport THEN the system SHALL constrain the tooltip position so it remains fully visible within the viewport, using CSS `right: 0` alignment or equivalent technique to prevent overflow

2.4 WHEN a `.sqlglot-tooltip` in `StandaloneConverterPage` or `BatchConverterPage` is rendered near the viewport edge THEN the system SHALL constrain the tooltip position so it remains fully visible within the viewport

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a migration's `checkpoint_data.export_results` contains valid `num_rows` values for all tables THEN the system SHALL CONTINUE TO display the correct row counts in the Total Rows column as it does today

3.2 WHEN an info tooltip is rendered in the center of the viewport (not near any edge) THEN the system SHALL CONTINUE TO display the tooltip centered below its parent pill element

3.3 WHEN the user selects/deselects tables in the "New Validation Run" form THEN the system SHALL CONTINUE TO update the per-table validation config (DDL, Row Count, Data Match checkboxes and sampling controls) correctly

3.4 WHEN the user creates a validation run with valid inputs THEN the system SHALL CONTINUE TO submit the request with the correct `source_connection_id`, `target_connection_id`, `tables`, and `table_configs` payload
