import type { TCOData } from '../../../services/assessmentsApi';
import type { PDFContext } from '../types';
import { C } from '../types';
import { newPage, sectionHeading, subHeading, drawCostBoxes, drawTable, drawCard, drawDivider, fmtDollar } from '../helpers';

export function renderTCO(ctx: PDFContext, tcoData: TCOData): void {
  newPage(ctx);
  sectionHeading(ctx, `TCO Analysis -- ${tcoData.region_label || tcoData.aws_region}`);

  const bq   = tcoData.bigquery_costs?.monthly || 0;
  const prov = tcoData.provisioned_costs?.monthly || 0;
  const sl   = tcoData.serverless_costs?.monthly || 0;

  // Monthly cost comparison
  subHeading(ctx, 'Monthly Cost Comparison');
  drawCostBoxes(ctx, [
    { label: 'BigQuery', value: fmtDollar(bq), sublabel: 'Current Monthly Cost', color: C.DANGER, bg: C.DANGER_BG },
    { label: 'Redshift Provisioned', value: fmtDollar(prov), sublabel: 'On-Demand Monthly', color: C.BLUE, bg: C.BLUE_BG },
    { label: 'Redshift Serverless', value: fmtDollar(sl), sublabel: 'Estimated Monthly', color: C.SUCCESS, bg: C.SUCCESS_BG },
  ]);

  drawDivider(ctx);

  // 3-year comparison
  const comp = tcoData.comparison;
  if (comp) {
    subHeading(ctx, '3-Year Total Cost of Ownership');

    const rows: string[][] = [
      ['BigQuery (Current)', fmtDollar(bq), fmtDollar(tcoData.bigquery_costs?.annual || 0), fmtDollar(comp.bq_3yr_tco)],
      ['Provisioned On-Demand', fmtDollar(prov), fmtDollar(tcoData.provisioned_costs?.annual || 0), fmtDollar(comp.provisioned_3yr_tco)],
    ];
    if (comp.provisioned_ri1yr_3yr_tco != null) {
      rows.push(['Provisioned 1-Yr RI', fmtDollar(tcoData.provisioned_costs?.ri_1yr_monthly || 0), fmtDollar(tcoData.provisioned_costs?.ri_1yr_annual || 0), fmtDollar(comp.provisioned_ri1yr_3yr_tco)]);
    }
    if (comp.provisioned_ri3yr_3yr_tco != null) {
      rows.push(['Provisioned 3-Yr RI', fmtDollar(tcoData.provisioned_costs?.ri_3yr_monthly || 0), fmtDollar(tcoData.provisioned_costs?.ri_3yr_annual || 0), fmtDollar(comp.provisioned_ri3yr_3yr_tco)]);
    }
    rows.push(['Serverless', fmtDollar(sl), fmtDollar(tcoData.serverless_costs?.annual || 0), fmtDollar(comp.serverless_3yr_tco)]);

    drawTable(ctx,
      ['Option', 'Monthly', 'Annual', '3-Year TCO'],
      rows,
    );

    drawCard(ctx, [
      `Best Option: Redshift ${comp.best_option === 'serverless' ? 'Serverless' : 'Provisioned'}`,
      `3-Year Savings vs BigQuery: ${fmtDollar(comp.savings_amount)} (${comp.savings_pct}%)`,
    ], '3-Year TCO Comparison Result', C.SUCCESS);
  }

  // Workload profile
  const wl = tcoData.workload_summary;
  if (wl?.workload_type) {
    drawCard(ctx, [
      `Pattern: ${wl.workload_type.label}`,
      `${wl.workload_type.description}`,
      `Total Queries: ${wl.total_queries.toLocaleString()} over ${wl.query_time_span_days.toFixed(0)} days (~${wl.workload_type.daily_queries.toLocaleString()}/day)`,
      `Monthly Compute: ${wl.monthly_slot_hours.toLocaleString(undefined, { maximumFractionDigits: 1 })} slot-hours, ${wl.estimated_rpu_hours_monthly.toLocaleString(undefined, { maximumFractionDigits: 0 })} est. RPU-hours`,
    ], 'Workload Profile', C.PRIMARY_L);
  }

  // Recommendation
  const rec = tcoData.recommendation;
  if (rec) {
    const lines = [rec.title];
    if (rec.annual_savings_vs_bq > 0) {
      lines.push(`Estimated annual savings vs BigQuery: ${fmtDollar(rec.annual_savings_vs_bq)}`);
    }
    rec.reasons.forEach(r => lines.push(`• ${r}`));
    drawCard(ctx, lines, `Recommendation (${rec.confidence} confidence)`, rec.confidence === 'high' ? C.SUCCESS : C.BLUE);
  }

  if (tcoData.provisioned_costs?.node_type) {
    drawCard(ctx, [
      `Node Type: ${tcoData.provisioned_costs.node_type}`,
      `Nodes: ${tcoData.provisioned_costs.num_nodes}`,
    ], 'Provisioned Cluster Configuration', C.PRIMARY_L);
  }
}

