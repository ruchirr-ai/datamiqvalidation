import type { AssessmentReportView } from '../../../services/assessmentsApi';
import type { PDFContext } from '../types';
import { C } from '../types';
import { newPage, sectionHeading, subHeading, drawMetricRow, drawCustomTable, sanitize, checkPage } from '../helpers';

function getDeps(v: any): string {
  const parts: string[] = [];
  if (v.dependent_tables?.length)    parts.push(`Tables: ${v.dependent_tables.join(', ')}`);
  if (v.dependent_views?.length)     parts.push(`Views: ${v.dependent_views.join(', ')}`);
  if (v.dependent_functions?.length) parts.push(`Fns: ${v.dependent_functions.join(', ')}`);
  return sanitize(parts.join(' | ')) || 'None';
}

function renderViewTable(ctx: PDFContext, views: any[]): void {
  drawCustomTable(ctx,
    ['View', 'Type', 'Definition (Preview)', 'Dependencies'],
    views.map(v => [
      v.view_name,
      v.view_type || 'VIEW',
      sanitize((v.view_definition || '').substring(0, 300) + ((v.view_definition || '').length > 300 ? '...' : '')),
      getDeps(v),
    ]),
    {
      0: { cellWidth: 40 },
      1: { cellWidth: 22 },
      2: { cellWidth: 'auto' },
      3: { cellWidth: 50 },
    },
    { fontSize: 6.5 },
  );
}

export function renderViews(ctx: PDFContext, views: AssessmentReportView[]): void {
  if (views.length === 0) return;

  const standardViews = views.filter((v: any) => v.view_type !== 'MATERIALIZED_VIEW');
  const materializedViews = views.filter((v: any) => v.view_type === 'MATERIALIZED_VIEW');
  const withDeps = views.filter((v: any) => (v as any).dependent_tables?.length > 0).length;

  // Summary page
  newPage(ctx);
  sectionHeading(ctx, `Views (${views.length})`);

  drawMetricRow(ctx, [
    { v: String(views.length), l: 'Total Views', color: C.PRIMARY_L, bg: C.PRIMARY_BG },
    { v: String(materializedViews.length), l: 'Materialized', color: C.ACCENT, bg: C.ACCENT_L },
    { v: String(standardViews.length), l: 'Standard', color: C.SUCCESS, bg: C.SUCCESS_BG },
    { v: String(withDeps), l: 'With Dependencies', color: C.WARNING, bg: C.WARNING_BG },
  ]);

  // Standard Views
  if (standardViews.length > 0) {
    checkPage(ctx, 30);
    subHeading(ctx, `Standard Views (${standardViews.length})`);
    renderViewTable(ctx, standardViews);
  }

  // Materialized Views
  if (materializedViews.length > 0) {
    newPage(ctx);
    subHeading(ctx, `Materialized Views (${materializedViews.length})`);
    renderViewTable(ctx, materializedViews);
  }
}
