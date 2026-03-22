---
inclusion: fileMatch
fileMatchPattern: "**/AssessmentReportPage*,**/BigQueryReportPage*,**/SQLServerReportPage*,**/reportUtils*,**/assessment*"
---

# Assessment Report File Ownership

The assessment report UI is split into separate files by database type. Follow these rules strictly.

## File Map

| File | Owns | When to modify |
|------|------|----------------|
| `frontend/src/pages/AssessmentReportPage.tsx` | Thin router only | Only if changing how the router loads summary or decides BigQuery vs SQL Server |
| `frontend/src/pages/BigQueryReportPage.tsx` | ALL BigQuery assessment UI | Any BigQuery assessment change (tabs, sections, layout, data fetching) |
| `frontend/src/pages/SQLServerReportPage.tsx` | ALL SQL Server assessment UI | Any SQL Server assessment change (tabs, sections, layout, data fetching) |
| `frontend/src/pages/reportUtils.tsx` | Shared utilities | TabSpinner, TabError, PaginationControls, formatSize, formatDate, formatNumber |

## Rules

1. If the user says "assessment page" without specifying BigQuery or SQL Server, ask which one they mean.
2. If the change is clearly about BigQuery (datasets, ML models, policy tags, slot hours), modify `BigQueryReportPage.tsx`.
3. If the change is clearly about SQL Server (schemas, triggers, linked servers, logins, CPU time), modify `SQLServerReportPage.tsx`.
4. NEVER put BigQuery-specific code in `SQLServerReportPage.tsx` or vice versa.
5. NEVER add section components back into `AssessmentReportPage.tsx` — it is a thin router only.
6. Shared components (QueryInsightsSection, Recommendations, TCO) are duplicated in each file since they have slight differences. If a shared change is needed, update both files.
