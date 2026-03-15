/**
 * Query Insights — matches the UI's 12 metric cards + top queries table
 */
import type { AssessmentReportQueryStat } from '../../../services/assessmentsApi';
import type { PDFContext, QueryInsightsData } from '../types';
import { C } from '../types';
import {
  newPage, sectionHeading, subHeading, drawMetricRow,
  drawCustomTable, drawDivider, sanitize, checkPage,
} from '../helpers';

function fmtTime(seconds: number): string {
  if (seconds < 1) return `${(seconds * 1000).toFixed(0)}ms`;
  if (seconds < 60) return `${seconds.toFixed(2)}s`;
  if (seconds < 3600) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}m ${s}s`;
  }
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

function fmtSlotMs(ms: number): string {
  const s = ms / 1000;
  if (s >= 3600) return (s / 3600).toFixed(1) + 'h';
  if (s >= 60) return (s / 60).toFixed(1) + 'm';
  return s.toFixed(1) + 's';
}

function fmtBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
}

function fmtNum(n: number): string {
  return n.toLocaleString();
}

export function renderQueryInsights(
  ctx: PDFContext,
  qs: AssessmentReportQueryStat[],
  insightsData?: QueryInsightsData | null,
): void {
  if (qs.length === 0 && !insightsData) return;

  // ── Page: Dashboard with 12 metric cards ──
  newPage(ctx);
  const totalQueries = insightsData?.summary?.total_query_count ?? qs.length;
  sectionHeading(ctx, `Query Insights (${fmtNum(totalQueries)} queries analyzed)`);

  if (insightsData?.summary) {
    const s = insightsData.summary;

    // Row 1: Total Queries | Avg Slot Time / Query | Bytes Scanned | Cache Hit Rate
    drawMetricRow(ctx, [
      { v: fmtNum(s.total_query_count), l: 'Total Queries', color: C.PRIMARY, bg: C.PRIMARY_BG },
      { v: fmtTime(s.avg_execution_time_seconds), l: 'Avg Slot Time / Query', color: C.PRIMARY, bg: C.PRIMARY_BG },
      { v: fmtBytes(s.total_bytes_scanned), l: 'Bytes Scanned', color: C.PRIMARY, bg: C.PRIMARY_BG },
      { v: s.cache_hit_rate.toFixed(1) + '%', l: 'Cache Hit Rate', color: C.PRIMARY, bg: C.PRIMARY_BG },
    ]);

    // Row 2: Max Concurrent | Peak Slot Util | Max Query Runtime | Avg Query Runtime
    drawMetricRow(ctx, [
      {
        v: String(s.max_concurrent_queries),
        l: `Max Concurrent Queries · Avg ${s.avg_concurrent_queries}/min`,
        color: C.PRIMARY, bg: C.PRIMARY_BG,
      },
      {
        v: String(s.peak_slot_utilization),
        l: `Peak Slot Utilization · Avg ${s.avg_slot_utilization} slots`,
        color: C.PRIMARY, bg: C.PRIMARY_BG,
      },
      {
        v: fmtTime(s.max_query_runtime_seconds),
        l: `Max Query Runtime · Min ${fmtTime(s.min_query_runtime_seconds)}`,
        color: C.PRIMARY, bg: C.PRIMARY_BG,
      },
      {
        v: fmtTime(s.avg_query_runtime_seconds),
        l: `Avg Query Runtime · Avg Slot ms ${fmtNum(s.avg_slot_ms_per_query)}`,
        color: C.PRIMARY, bg: C.PRIMARY_BG,
      },
    ]);

    // Row 3: Total Slot Hours | Avg Bytes / Query | Active Users | Read/Write
    const totalSlotHours = (s.total_slot_milliseconds / 3600000).toFixed(1) + 'h';
    const avgBytesPerQuery = s.total_query_count > 0
      ? fmtBytes(s.total_bytes_scanned / s.total_query_count) : '0 B';

    drawMetricRow(ctx, [
      { v: totalSlotHours, l: 'Total Slot Hours', color: C.PRIMARY, bg: C.PRIMARY_BG },
      { v: avgBytesPerQuery, l: 'Avg Bytes Scanned / Query', color: C.PRIMARY, bg: C.PRIMARY_BG },
      { v: String(s.active_users_count), l: 'Active Users', color: C.PRIMARY, bg: C.PRIMARY_BG },
      {
        v: `${fmtNum(s.read_queries)}/${fmtNum(s.write_queries)}`,
        l: 'Read / Write Queries',
        color: C.PRIMARY, bg: C.PRIMARY_BG,
      },
    ]);
  } else {
    // Fallback: compute from raw query_stats (less accurate)
    renderFallbackMetrics(ctx, qs);
  }

  drawDivider(ctx);

  // ── Top 10 Queries table ──
  checkPage(ctx, 20);
  subHeading(ctx, 'Top 10 Queries (Highest Slot Utilization)');

  if (insightsData?.queries && insightsData.queries.length > 0) {
    const topQueries = insightsData.queries.slice(0, 10);
    drawCustomTable(ctx,
      ['#', 'Job ID', 'Execution Time', 'Query', 'Scanned', 'Slot ms', 'Slot Util.', 'Est. Runtime', 'Cache', 'User'],
      topQueries.map((q, i) => {
        let execTime = 'N/A';
        if (q.execution_time) {
          try {
            const d = new Date(q.execution_time);
            execTime = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
          } catch { execTime = 'N/A'; }
        }
        return [
          String(i + 1),
          q.job_id || 'N/A',
          execTime,
          sanitize(q.query_text || 'N/A'),
          fmtBytes(q.bytes_scanned || 0),
          (q.slot_milliseconds || 0).toLocaleString(),
          q.slot_utilization ? `${q.slot_utilization} slots` : '0',
          q.est_runtime_seconds ? fmtTime(q.est_runtime_seconds) : 'N/A',
          q.cache_hit ? 'Yes' : 'No',
          q.user_email || 'N/A',
        ];
      }),
      {
        0: { cellWidth: 6 },
        1: { cellWidth: 22, fontSize: 5 },
        2: { cellWidth: 22 },
        3: { cellWidth: 'auto', fontSize: 5 },
        4: { cellWidth: 14 },
        5: { cellWidth: 16 },
        6: { cellWidth: 12 },
        7: { cellWidth: 14 },
        8: { cellWidth: 8 },
        9: { cellWidth: 22, fontSize: 5 },
      },
      { fontSize: 5.5 },
    );
  } else {
    // Fallback: use raw query_stats
    renderFallbackTable(ctx, qs);
  }
}


// ── Fallback renderers when insightsData is not available ──

const WRITE_RE = /^\s*(INSERT|UPDATE|DELETE|MERGE|CREATE|DROP|ALTER|TRUNCATE|CALL)\b/i;

function renderFallbackMetrics(ctx: PDFContext, qs: AssessmentReportQueryStat[]): void {
  const reads = qs.filter(q => q.query_text && !WRITE_RE.test(q.query_text.trim()));
  const writes = qs.filter(q => q.query_text && WRITE_RE.test(q.query_text.trim()));
  const totalSlotMs = qs.reduce((s, q) => s + (q.slot_milliseconds || 0), 0);
  const avgSlotMs = totalSlotMs / qs.length;
  const totalBytes = qs.reduce((s, q) => s + (q.bytes_scanned || 0), 0);
  const cacheHits = qs.filter(q => q.cache_hit).length;
  const cacheRatio = ((cacheHits / qs.length) * 100).toFixed(1);
  const uniqueUsers = new Set(qs.map(q => q.user_email || 'Unknown')).size;

  drawMetricRow(ctx, [
    { v: fmtNum(qs.length), l: 'Total Queries', color: C.PRIMARY, bg: C.PRIMARY_BG },
    { v: fmtSlotMs(avgSlotMs), l: 'Avg Slot Time / Query', color: C.PRIMARY, bg: C.PRIMARY_BG },
    { v: fmtBytes(totalBytes), l: 'Bytes Scanned', color: C.PRIMARY, bg: C.PRIMARY_BG },
    { v: cacheRatio + '%', l: 'Cache Hit Rate', color: C.PRIMARY, bg: C.PRIMARY_BG },
  ]);

  const totalSlotHours = (totalSlotMs / 3600000).toFixed(1) + 'h';
  const avgBytesPerQuery = qs.length > 0 ? fmtBytes(totalBytes / qs.length) : '0 B';

  drawMetricRow(ctx, [
    { v: totalSlotHours, l: 'Total Slot Hours', color: C.PRIMARY, bg: C.PRIMARY_BG },
    { v: avgBytesPerQuery, l: 'Avg Bytes Scanned / Query', color: C.PRIMARY, bg: C.PRIMARY_BG },
    { v: String(uniqueUsers), l: 'Active Users', color: C.PRIMARY, bg: C.PRIMARY_BG },
    { v: `${fmtNum(reads.length)}/${fmtNum(writes.length)}`, l: 'Read / Write Queries', color: C.PRIMARY, bg: C.PRIMARY_BG },
  ]);
}

function renderFallbackTable(ctx: PDFContext, qs: AssessmentReportQueryStat[]): void {
  const topRecent = [...qs]
    .sort((a, b) => (b.slot_milliseconds || 0) - (a.slot_milliseconds || 0))
    .slice(0, 10);

  drawCustomTable(ctx,
    ['#', 'Job ID', 'Execution Time', 'Query', 'Scanned', 'Slot ms', 'Cache', 'User'],
    topRecent.map((q, i) => {
      let execTime = 'N/A';
      if (q.execution_time) {
        try {
          const d = new Date(q.execution_time);
          execTime = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
        } catch { execTime = 'N/A'; }
      }
      return [
        String(i + 1),
        q.job_id || 'N/A',
        execTime,
        sanitize(q.query_text || 'N/A'),
        fmtBytes(q.bytes_scanned || 0),
        (q.slot_milliseconds || 0).toLocaleString(),
        q.cache_hit ? 'Yes' : 'No',
        q.user_email || 'N/A',
      ];
    }),
    {
      0: { cellWidth: 6 },
      1: { cellWidth: 24, fontSize: 5 },
      2: { cellWidth: 24 },
      3: { cellWidth: 'auto', fontSize: 5 },
      4: { cellWidth: 16 },
      5: { cellWidth: 18 },
      6: { cellWidth: 10 },
      7: { cellWidth: 24, fontSize: 5 },
    },
    { fontSize: 5.5 },
  );
}
