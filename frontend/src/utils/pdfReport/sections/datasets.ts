import type { DatasetSummary } from '../../../services/assessmentsApi';
import type { PDFContext } from '../types';
import { C } from '../types';
import { newPage, sectionHeading, drawMetricRow, drawTable, fmtSize } from '../helpers';

export function renderDatasets(ctx: PDFContext, datasets: DatasetSummary[]): void {
  if (datasets.length === 0) return;
  newPage(ctx);
  sectionHeading(ctx, `Datasets (${datasets.length})`);

  // Summary metrics — table_count from datasets includes views, label accordingly
  const totalObjects = datasets.reduce((s, d) => s + d.table_count, 0);
  const totalSize = datasets.reduce((s, d) => s + d.total_size_mb, 0);
  const locations = new Set(datasets.map(d => d.location || 'N/A'));

  drawMetricRow(ctx, [
    { v: String(datasets.length), l: 'Total Datasets', color: C.PRIMARY_L, bg: C.PRIMARY_BG },
    { v: String(totalObjects), l: 'Total Objects', color: C.SUCCESS, bg: C.SUCCESS_BG },
    { v: fmtSize(totalSize), l: 'Total Size', color: C.PURPLE, bg: C.PURPLE_BG },
    { v: String(locations.size), l: 'Regions', color: C.WARNING, bg: C.WARNING_BG },
  ]);

  drawTable(ctx,
    ['Dataset', 'Tables', 'Size', 'Location'],
    datasets.map(d => [d.dataset_name, String(d.table_count), fmtSize(d.total_size_mb), d.location || 'N/A']),
  );
}
