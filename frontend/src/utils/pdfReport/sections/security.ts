import type { AssessmentReportSecurity } from '../../../services/assessmentsApi';
import type { PDFContext } from '../types';
import { C } from '../types';
import { newPage, sectionHeading, drawMetricRow, drawTable } from '../helpers';

export function renderSecurity(ctx: PDFContext, policies: AssessmentReportSecurity[]): void {
  if (policies.length === 0) return;
  newPage(ctx);
  sectionHeading(ctx, `Security Policies (${policies.length})`);

  const rls = policies.filter(p => p.security_type === 'RLS').length;
  const cls = policies.filter(p => p.security_type === 'CLS').length;
  const tables = new Set(policies.map(p => p.table_name)).size;

  drawMetricRow(ctx, [
    { v: String(policies.length), l: 'Total Policies', color: C.PRIMARY_L, bg: C.PRIMARY_BG },
    { v: String(rls), l: 'Row-Level Security', color: C.DANGER, bg: C.DANGER_BG },
    { v: String(cls), l: 'Column-Level Security', color: C.WARNING, bg: C.WARNING_BG },
    { v: String(tables), l: 'Protected Tables', color: C.SUCCESS, bg: C.SUCCESS_BG },
  ]);

  drawTable(ctx,
    ['Type', 'Table', 'Policy', 'Grantees'],
    policies.map(s => [
      s.security_type || 'N/A',
      s.table_name,
      s.policy_name || 'N/A',
      s.grantees?.join(', ') || 'N/A',
    ]),
  );
}
