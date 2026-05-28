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
  const rg   = (tcoData as any).rg_provisioned_costs?.monthly || 0;

  // Monthly cost comparison
  subHeading(ctx, 'Monthly Cost Comparison');
  const costBoxes = [
    { label: 'BigQuery', value: fmtDollar(bq), sublabel: 'Current Monthly Cost', color: C.DANGER, bg: C.DANGER_BG },
    { label: 'Redshift RA3', value: fmtDollar(prov), sublabel: 'On-Demand Monthly', color: C.BLUE, bg: C.BLUE_BG },
  ];
  if (rg > 0) {
    costBoxes.push({ label: 'Redshift RG', value: fmtDollar(rg), sublabel: 'Graviton Monthly', color: C.BLUE, bg: C.BLUE_BG });
  }
  costBoxes.push({ label: 'Redshift Serverless', value: fmtDollar(sl), sublabel: 'Estimated Monthly', color: C.BLUE, bg: C.BLUE_BG });
  drawCostBoxes(ctx, costBoxes);

  drawDivider(ctx);

  // 3-year comparison
  const comp = tcoData.comparison;
  if (comp) {
    subHeading(ctx, '3-Year Total Cost of Ownership');

    const rows: string[][] = [
      ['BigQuery (Current)', fmtDollar(bq), fmtDollar(tcoData.bigquery_costs?.annual || 0), fmtDollar(comp.bq_3yr_tco)],
      ['RA3 Provisioned On-Demand', fmtDollar(prov), fmtDollar(tcoData.provisioned_costs?.annual || 0), fmtDollar(comp.provisioned_3yr_tco)],
    ];
    if (comp.provisioned_ri1yr_3yr_tco != null) {
      rows.push(['RA3 Provisioned 1-Yr RI', fmtDollar(tcoData.provisioned_costs?.ri_1yr_monthly || 0), fmtDollar(tcoData.provisioned_costs?.ri_1yr_annual || 0), fmtDollar(comp.provisioned_ri1yr_3yr_tco)]);
    }
    if (comp.provisioned_ri3yr_3yr_tco != null) {
      rows.push(['RA3 Provisioned 3-Yr RI', fmtDollar(tcoData.provisioned_costs?.ri_3yr_monthly || 0), fmtDollar(tcoData.provisioned_costs?.ri_3yr_annual || 0), fmtDollar(comp.provisioned_ri3yr_3yr_tco)]);
    }
    if ((comp as any).rg_provisioned_3yr_tco != null) {
      rows.push(['RG Provisioned (Graviton)', fmtDollar(rg), fmtDollar((tcoData as any).rg_provisioned_costs?.annual || 0), fmtDollar((comp as any).rg_provisioned_3yr_tco)]);
    }
    rows.push(['Serverless', fmtDollar(sl), fmtDollar(tcoData.serverless_costs?.annual || 0), fmtDollar(comp.serverless_3yr_tco)]);

    drawTable(ctx,
      ['Option', 'Monthly', 'Annual', '3-Year TCO'],
      rows,
    );

    const bestLabel = comp.best_option === 'serverless' ? 'Serverless' : comp.best_option === 'rg_provisioned' ? 'RG Provisioned' : 'RA3 Provisioned';
    drawCard(ctx, [
      `Best Option: Redshift ${bestLabel}`,
      `3-Year Savings vs BigQuery: ${fmtDollar(comp.savings_amount)} (${comp.savings_pct}%)`,
    ], '3-Year TCO Comparison Result', C.SUCCESS);
  }

  // One-time migration costs
  const migration = tcoData.migration_costs as any;
  if (migration && migration.total > 0) {
    subHeading(ctx, 'One-Time Migration Costs');
    const migRows: string[][] = [];
    if (migration.gcp_egress) {
      migRows.push(['GCP Data Egress (Standard Tier)', `${migration.gcp_egress.billable_gb} GB × $${migration.gcp_egress.rate_per_gb}/GB`, fmtDollar(migration.gcp_egress.cost)]);
    }
    if (migration.gcs_staging) {
      migRows.push(['GCS Temp Storage (~1 week)', `$${migration.gcs_staging.rate_per_gb_month}/GB/mo`, fmtDollar(migration.gcs_staging.cost)]);
    }
    if (migration.s3_staging) {
      migRows.push(['S3 Temp Storage (~1 week)', `$${migration.s3_staging.rate_per_gb_month}/GB/mo`, fmtDollar(migration.s3_staging.cost)]);
    }
    migRows.push(['Total One-Time', `${migration.data_volume_gb} GB`, fmtDollar(migration.total)]);
    drawTable(ctx, ['Item', 'Detail', 'Cost'], migRows);
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
    const configLines = [
      `RA3 Node Type: ${tcoData.provisioned_costs.node_type} × ${tcoData.provisioned_costs.num_nodes}`,
    ];
    if ((tcoData as any).rg_provisioned_costs?.node_type) {
      configLines.push(`RG Node Type: ${(tcoData as any).rg_provisioned_costs.node_type} × ${(tcoData as any).rg_provisioned_costs.num_nodes}`);
    }
    drawCard(ctx, configLines, 'Provisioned Cluster Configuration', C.PRIMARY_L);
  }
}

