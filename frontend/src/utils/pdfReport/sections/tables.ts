import type { AssessmentReportTable } from '../../../services/assessmentsApi';
import type { PDFContext } from '../types';
import { C } from '../types';
import { newPage, sectionHeading, drawMetricRow, drawTable, fmtSize, fmtNum } from '../helpers';

export function renderTables(ctx: PDFContext, tables: AssessmentReportTable[]): void {
  if (tables.length === 0) return;
  newPage(ctx);
  sectionHeading(ctx, `Tables (${tables.length})`);

  const totalRows = tables.reduce((s, t) => s + (t.row_count || 0), 0);
  const totalSize = tables.reduce((s, t) => s + (t.size_mb || 0), 0);
  const partitioned = tables.filter(t => t.partitioning_columns?.length > 0).length;
  const clustered = tables.filter(t => t.clustering_columns?.length > 0).length;

  drawMetricRow(ctx, [
    { v: String(tables.length), l: 'Total Tables', color: C.PRIMARY_L, bg: C.PRIMARY_BG },
    { v: fmtNum(totalRows), l: 'Total Rows', color: C.SUCCESS, bg: C.SUCCESS_BG },
    { v: fmtSize(totalSize), l: 'Total Size', color: C.PURPLE, bg: C.PURPLE_BG },
    { v: `${partitioned} / ${clustered}`, l: 'Partitioned / Clustered', color: C.WARNING, bg: C.WARNING_BG },
  ]);

  drawTable(ctx,
    ['Table', 'Type', 'Rows', 'Size', 'Partitioning', 'Clustering'],
    tables.map(t => [
      `${t.dataset_name}.${t.table_name}`,
      t.table_type || 'TABLE',
      fmtNum(t.row_count),
      fmtSize(t.size_mb),
      t.partitioning_columns?.join(', ') || 'None',
      t.clustering_columns?.join(', ') || 'None',
    ]),
  );
}
