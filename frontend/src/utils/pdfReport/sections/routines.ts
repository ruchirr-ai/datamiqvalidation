import type { AssessmentReportRoutine } from '../../../services/assessmentsApi';
import type { PDFContext } from '../types';
import { C } from '../types';
import { newPage, sectionHeading, drawMetricRow, drawCustomTable, fmtDate, sanitize } from '../helpers';

function getDeps(r: any): string {
  const parts: string[] = [];
  if (r.dependent_tables?.length)    parts.push(`Tables: ${r.dependent_tables.join(', ')}`);
  if (r.dependent_views?.length)     parts.push(`Views: ${r.dependent_views.join(', ')}`);
  if (r.dependent_functions?.length) parts.push(`Fns: ${r.dependent_functions.join(', ')}`);
  if (r.calls_procedures?.length)    parts.push(`Calls: ${r.calls_procedures.join(', ')}`);
  return sanitize(parts.join(' | ')) || 'None';
}

export function renderProcedures(ctx: PDFContext, routines: AssessmentReportRoutine[]): void {
  const procs = routines.filter(r => r.routine_type === 'PROCEDURE');
  if (procs.length === 0) return;
  newPage(ctx);
  sectionHeading(ctx, `Stored Procedures (${procs.length})`);

  const langs = new Set(procs.map(p => p.external_language || 'SQL'));
  const withDeps = procs.filter((p: any) => (p as any).dependent_tables?.length > 0).length;

  drawMetricRow(ctx, [
    { v: String(procs.length), l: 'Total Procedures', color: C.PRIMARY_L, bg: C.PRIMARY_BG },
    { v: String(langs.size), l: 'Languages', color: C.ACCENT, bg: C.ACCENT_L },
    { v: String(withDeps), l: 'With Table Dependencies', color: C.WARNING, bg: C.WARNING_BG },
  ]);

  drawCustomTable(ctx,
    ['Procedure', 'Language', 'Created', 'Dependencies'],
    procs.map(p => [
      p.routine_name,
      p.external_language || 'SQL',
      fmtDate(p.creation_time),
      getDeps(p),
    ]),
    {
      0: { cellWidth: 50 },
      1: { cellWidth: 22 },
      2: { cellWidth: 40 },
      3: { cellWidth: 'auto' },
    },
    { fontSize: 7 },
  );
}

export function renderFunctions(ctx: PDFContext, routines: AssessmentReportRoutine[]): void {
  const funcs = routines.filter(r => r.routine_type === 'FUNCTION');
  if (funcs.length === 0) return;
  newPage(ctx);
  sectionHeading(ctx, `Functions (${funcs.length})`);

  const langs = new Set(funcs.map(f => f.external_language || 'SQL'));
  const withDeps = funcs.filter((f: any) => (f as any).dependent_tables?.length > 0).length;

  drawMetricRow(ctx, [
    { v: String(funcs.length), l: 'Total Functions', color: C.PRIMARY_L, bg: C.PRIMARY_BG },
    { v: String(langs.size), l: 'Languages', color: C.ACCENT, bg: C.ACCENT_L },
    { v: String(withDeps), l: 'With Table Dependencies', color: C.SUCCESS, bg: C.SUCCESS_BG },
  ]);

  drawCustomTable(ctx,
    ['Function', 'Language', 'Return Type', 'Created', 'Dependencies'],
    funcs.map(f => [
      f.routine_name,
      f.external_language || 'SQL',
      f.return_type || 'N/A',
      fmtDate(f.creation_time),
      getDeps(f),
    ]),
    {
      0: { cellWidth: 42 },
      1: { cellWidth: 22 },
      2: { cellWidth: 28 },
      3: { cellWidth: 36 },
      4: { cellWidth: 'auto' },
    },
    { fontSize: 7 },
  );
}
