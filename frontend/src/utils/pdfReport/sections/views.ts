import type { AssessmentReportView } from '../../../services/assessmentsApi';
import type { PDFContext } from '../types';
import { C } from '../types';
import { newPage, sectionHeading, drawMetricRow, drawCustomTable, sanitize } from '../helpers';

function getDeps(v: any): string {
  const parts: string[] = [];
  if (v.dependent_tables?.length)    parts.push(`Tables: ${v.dependent_tables.join(', ')}`);
  if (v.dependent_views?.length)     parts.push(`Views: ${v.dependent_views.join(', ')}`);
  if (v.dependent_functions?.length) parts.push(`Fns: ${v.dependent_functions.join(', ')}`);
  return sanitize(parts.join(' | ')) || 'None';
}

export function renderViews(ctx: PDFContext, views: AssessmentReportView[]): void {
  if (views.length === 0) return;
  newPage(ctx);
  sectionHeading(ctx, `Views (${views.length})`);

  const materialized = views.filter((v: any) => v.view_type === 'MATERIALIZED_VIEW').length;
  const withDeps = views.filter((v: any) => (v as any).dependent_tables?.length > 0).length;

  drawMetricRow(ctx, [
    { v: String(views.length), l: 'Total Views', color: C.PRIMARY_L, bg: C.PRIMARY_BG },
    { v: String(materialized), l: 'Materialized', color: C.ACCENT, bg: C.ACCENT_L },
    { v: String(views.length - materialized), l: 'Standard', color: C.SUCCESS, bg: C.SUCCESS_BG },
    { v: String(withDeps), l: 'With Dependencies', color: C.WARNING, bg: C.WARNING_BG },
  ]);

  drawCustomTable(ctx,
    ['View', 'Type', 'Definition (Preview)', 'Dependencies'],
    views.map(v => [
      v.view_name,
      v.view_type || 'VIEW',
      sanitize((v.view_definition || '').substring(0, 100) + ((v.view_definition || '').length > 100 ? '...' : '')),
      getDeps(v),
    ]),
    {
      0: { cellWidth: 45 },
      1: { cellWidth: 25 },
      2: { cellWidth: 'auto' },
      3: { cellWidth: 60 },
    },
    { fontSize: 7 },
  );
}
