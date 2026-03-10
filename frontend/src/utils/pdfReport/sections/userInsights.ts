import type { AssessmentReportQueryStat } from '../../../services/assessmentsApi';
import type { PDFContext } from '../types';
import { C } from '../types';
import { newPage, sectionHeading, drawMetricRow, drawTable, fmtSize } from '../helpers';

export function renderUserInsights(ctx: PDFContext, qs: AssessmentReportQueryStat[]): void {
  if (qs.length === 0) return;
  newPage(ctx);

  const umap = new Map<string, { count: number; bytes: number; slots: number; cacheHits: number }>();
  qs.forEach(q => {
    const e = q.user_email || 'Unknown';
    const x = umap.get(e) || { count: 0, bytes: 0, slots: 0, cacheHits: 0 };
    x.count++;
    x.bytes += q.bytes_scanned || 0;
    x.slots += q.slot_milliseconds || 0;
    if (q.cache_hit) x.cacheHits++;
    umap.set(e, x);
  });

  const sorted = Array.from(umap.entries()).sort((a, b) => b[1].count - a[1].count);
  const topUser = sorted[0];
  const totalBytes = qs.reduce((s, q) => s + (q.bytes_scanned || 0), 0);

  sectionHeading(ctx, `User Insights (${umap.size} users)`);

  drawMetricRow(ctx, [
    { v: String(umap.size), l: 'Unique Users', color: C.PRIMARY_L, bg: C.PRIMARY_BG },
    { v: String(qs.length), l: 'Total Queries', color: C.ACCENT, bg: C.ACCENT_L },
    { v: fmtSize(totalBytes / (1024 * 1024)), l: 'Total Data Scanned', color: C.PURPLE, bg: C.PURPLE_BG },
    { v: topUser ? String(topUser[1].count) : '0', l: 'Most Active User Queries', color: C.WARNING, bg: C.WARNING_BG },
  ]);

  drawTable(ctx,
    ['User', 'Queries', 'Data Scanned', 'Total Slot Time', 'Cache Hit %'],
    sorted.map(([em, d]) => [
      em,
      String(d.count),
      fmtSize(d.bytes / (1024 * 1024)),
      (d.slots / 1000).toFixed(1) + 's',
      d.count > 0 ? ((d.cacheHits / d.count) * 100).toFixed(1) + '%' : '0%',
    ]),
  );
}
