import type { AssessmentReportMLModel } from '../../../services/assessmentsApi';
import type { PDFContext } from '../types';
import { C } from '../types';
import { newPage, sectionHeading, drawMetricRow, drawTable, fmtDate } from '../helpers';

export function renderMLModels(ctx: PDFContext, models: AssessmentReportMLModel[]): void {
  if (models.length === 0) return;
  newPage(ctx);
  sectionHeading(ctx, `ML & Spark Models (${models.length})`);

  const types = new Set(models.map(m => m.model_type || 'Unknown'));
  const datasets = new Set(models.map(m => m.dataset_name));

  drawMetricRow(ctx, [
    { v: String(models.length), l: 'Total Models', color: C.PURPLE, bg: C.PURPLE_BG },
    { v: String(types.size), l: 'Model Types', color: C.PRIMARY_L, bg: C.PRIMARY_BG },
    { v: String(datasets.size), l: 'Datasets', color: C.SUCCESS, bg: C.SUCCESS_BG },
  ]);

  drawTable(ctx,
    ['Model', 'Type', 'Dataset', 'Created'],
    models.map(m => [m.model_name, m.model_type || 'N/A', m.dataset_name, fmtDate(m.creation_time)]),
  );
}
