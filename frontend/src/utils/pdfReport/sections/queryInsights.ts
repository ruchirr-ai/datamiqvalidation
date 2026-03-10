/**
 * Query Level Metrics — rich analytics dashboard
 */
import type { AssessmentReportQueryStat } from '../../../services/assessmentsApi';
import type { PDFContext } from '../types';
import { C } from '../types';
import {
  newPage, sectionHeading, subHeading, drawMetricRow,
  drawCard, drawCustomTable, drawDivider, fmtSize, sanitize, checkPage,
} from '../helpers';

const WRITE_RE = /^\s*(INSERT|UPDATE|DELETE|MERGE|CREATE|DROP|ALTER|TRUNCATE|CALL)\b/i;

function fmtSlot(ms: number): string {
  const s = ms / 1000;
  if (s >= 3600) return (s / 3600).toFixed(1) + 'h';
  if (s >= 60) return (s / 60).toFixed(1) + 'm';
  return s.toFixed(1) + 's';
}

export function renderQueryInsights(ctx: PDFContext, qs: AssessmentReportQueryStat[]): void {
  if (qs.length === 0) return;

  const reads = qs.filter(q => q.query_text && !WRITE_RE.test(q.query_text.trim()));
  const writes = qs.filter(q => q.query_text && WRITE_RE.test(q.query_text.trim()));
  const readPct = ((reads.length / qs.length) * 100).toFixed(1);
  const writePct = ((writes.length / qs.length) * 100).toFixed(1);
  const totalSlotMs = qs.reduce((s, q) => s + (q.slot_milliseconds || 0), 0);
  const avgSlotMs = totalSlotMs / qs.length;
  const maxSlotMs = Math.max(...qs.map(q => q.slot_milliseconds || 0));
  const totalBytes = qs.reduce((s, q) => s + (q.bytes_scanned || 0), 0);
  const avgBytes = totalBytes / qs.length;
  const cacheHits = qs.filter(q => q.cache_hit).length;
  const cacheRatio = ((cacheHits / qs.length) * 100).toFixed(1);
  const uniqueUsers = new Set(qs.map(q => q.user_email || 'Unknown')).size;

  // Peak concurrency
  const hourBuckets = new Map<string, number>();
  qs.forEach(q => {
    if (q.execution_time) {
      try {
        const d = new Date(q.execution_time);
        const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:00`;
        hourBuckets.set(key, (hourBuckets.get(key) || 0) + 1);
      } catch { /* skip */ }
    }
  });
  let peakConcurrent = 0;
  let peakHour = 'N/A';
  hourBuckets.forEach((count, hour) => {
    if (count > peakConcurrent) { peakConcurrent = count; peakHour = hour; }
  });

  // ── Page 1: Dashboard ──
  newPage(ctx);
  sectionHeading(ctx, `Query Level Metrics (${qs.length} queries analyzed)`);

  // Row 1: Query classification
  drawMetricRow(ctx, [
    { v: String(qs.length), l: 'Total Queries', color: C.PRIMARY_L, bg: C.PRIMARY_BG },
    { v: `${reads.length} (${readPct}%)`, l: 'Read Queries (SELECT)', color: C.SUCCESS, bg: C.SUCCESS_BG },
    { v: `${writes.length} (${writePct}%)`, l: 'Write Queries (DML/DDL)', color: C.DANGER, bg: C.DANGER_BG },
    { v: String(uniqueUsers), l: 'Unique Users', color: C.ACCENT, bg: C.ACCENT_L },
  ]);

  // Row 2: Performance
  drawMetricRow(ctx, [
    { v: fmtSlot(avgSlotMs), l: 'Avg Slot Utilization', color: C.PRIMARY_L, bg: C.PRIMARY_BG },
    { v: fmtSlot(maxSlotMs), l: 'Peak Slot Time', color: C.DANGER, bg: C.DANGER_BG },
    { v: String(peakConcurrent), l: 'Peak Concurrent (hourly)', color: C.WARNING, bg: C.WARNING_BG },
    { v: cacheRatio + '%', l: 'Cache Hit Ratio', color: C.SUCCESS, bg: C.SUCCESS_BG },
  ]);

  drawDivider(ctx);

  // Data volume card
  drawCard(ctx, [
    `Total Data Scanned: ${fmtSize(totalBytes / (1024 * 1024))}`,
    `Avg Data per Query: ${fmtSize(avgBytes / (1024 * 1024))}`,
    `Total Slot Time: ${fmtSlot(totalSlotMs)}  |  Avg per Query: ${fmtSlot(avgSlotMs)}`,
    `Peak Hour: ${peakHour} (${peakConcurrent} queries)`,
  ], 'Data Volume & Compute Summary', C.PRIMARY_L);

  // ── Top 10 heaviest ──
  checkPage(ctx, 20);
  subHeading(ctx, 'Top 10 Heaviest Queries (by Slot Time)');
  const heaviest = [...qs].sort((a, b) => (b.slot_milliseconds || 0) - (a.slot_milliseconds || 0)).slice(0, 10);
  drawCustomTable(ctx,
    ['#', 'User', 'Query', 'Scanned', 'Slot Time', 'Cache'],
    heaviest.map((q, i) => [
      String(i + 1),
      q.user_email || 'N/A',
      sanitize(q.query_text || 'N/A'),
      q.bytes_scanned ? fmtSize(q.bytes_scanned / (1024 * 1024)) : 'N/A',
      q.slot_milliseconds ? fmtSlot(q.slot_milliseconds) : 'N/A',
      q.cache_hit ? 'Yes' : 'No',
    ]),
    {
      0: { cellWidth: 8 },
      1: { cellWidth: 35 },
      2: { cellWidth: 'auto', fontSize: 5.5 },
      3: { cellWidth: 20 },
      4: { cellWidth: 18 },
      5: { cellWidth: 12 },
    },
    { fontSize: 6 },
  );

  // ── Top 10 data-intensive ──
  checkPage(ctx, 20);
  subHeading(ctx, 'Top 10 Most Data-Intensive Queries (by Bytes Scanned)');
  const dataHeavy = [...qs].sort((a, b) => (b.bytes_scanned || 0) - (a.bytes_scanned || 0)).slice(0, 10);
  drawCustomTable(ctx,
    ['#', 'User', 'Query', 'Scanned', 'Slot Time', 'Cache'],
    dataHeavy.map((q, i) => [
      String(i + 1),
      q.user_email || 'N/A',
      sanitize(q.query_text || 'N/A'),
      q.bytes_scanned ? fmtSize(q.bytes_scanned / (1024 * 1024)) : 'N/A',
      q.slot_milliseconds ? fmtSlot(q.slot_milliseconds) : 'N/A',
      q.cache_hit ? 'Yes' : 'No',
    ]),
    {
      0: { cellWidth: 8 },
      1: { cellWidth: 35 },
      2: { cellWidth: 'auto', fontSize: 5.5 },
      3: { cellWidth: 20 },
      4: { cellWidth: 18 },
      5: { cellWidth: 12 },
    },
    { fontSize: 6 },
  );
}
