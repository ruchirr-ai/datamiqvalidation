import type { AssessmentFullReport } from '../../../services/assessmentsApi';
import type { PDFContext } from '../types';
import { C } from '../types';
import { sectionHeading, drawMetricRow, drawCard, drawDivider, fmtSize, fmtDate, checkPage } from '../helpers';

export function renderSummary(ctx: PDFContext, report: AssessmentFullReport): void {
  sectionHeading(ctx, 'Executive Summary');

  const a = report.assessment;
  const procs = report.routines.filter(r => r.routine_type === 'PROCEDURE').length;
  const funcs = report.routines.filter(r => r.routine_type === 'FUNCTION').length;

  // Row 1: Core counts
  drawMetricRow(ctx, [
    { v: String(a.total_datasets), l: 'Datasets', color: C.PRIMARY_L, bg: C.PRIMARY_BG },
    { v: String(a.total_tables), l: 'Tables', color: C.SUCCESS, bg: C.SUCCESS_BG },
    { v: String(a.total_views), l: 'Views', color: C.ACCENT, bg: C.ACCENT_L },
    { v: fmtSize(a.total_size_mb), l: 'Total Data Size', color: C.PURPLE, bg: C.PURPLE_BG },
  ]);

  // Row 2: Code objects
  drawMetricRow(ctx, [
    { v: String(report.routines.length), l: 'Total Routines', color: C.WARNING, bg: C.WARNING_BG },
    { v: String(procs), l: 'Stored Procedures', color: C.PRIMARY_L, bg: C.PRIMARY_BG },
    { v: String(funcs), l: 'Functions', color: C.ACCENT, bg: C.ACCENT_L },
    { v: String(report.ml_models.length), l: 'ML Models', color: C.PURPLE, bg: C.PURPLE_BG },
  ]);

  drawDivider(ctx);

  // Assessment details card
  drawCard(ctx, [
    `Project: ${a.project_id}`,
    `Started: ${fmtDate(a.started_at)}`,
    `Completed: ${fmtDate(a.completed_at)}`,
    `Status: ${a.status.toUpperCase()}`,
  ], 'Assessment Details', C.PRIMARY_L);

  // Quick stats card — filter to base tables only
  const baseTables = report.tables.filter(t =>
    !t.table_type || t.table_type === 'BASE TABLE' || t.table_type === 'EXTERNAL' || t.table_type === 'TABLE'
  );
  const totalRows = baseTables.reduce((s, t) => s + (t.row_count || 0), 0);
  const partitioned = baseTables.filter(t => t.partitioning_columns?.length > 0).length;
  const clustered = baseTables.filter(t => t.clustering_columns?.length > 0).length;
  const securedTables = baseTables.filter(t => t.has_row_security || t.has_column_security).length;

  checkPage(ctx, 30);
  drawCard(ctx, [
    `Total Rows: ${totalRows.toLocaleString()}`,
    `Partitioned Tables: ${partitioned} of ${a.total_tables}`,
    `Clustered Tables: ${clustered} of ${a.total_tables}`,
    `Tables with Security: ${securedTables}`,
    `Security Policies: ${report.security_policies.length}`,
    `Query Stats Available: ${report.query_stats.length} queries`,
  ], 'Infrastructure Overview', C.SUCCESS);
}
