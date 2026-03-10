import type { RecommendationsData } from '../../../services/assessmentsApi';
import type { PDFContext } from '../types';
import { C } from '../types';
import { newPage, sectionHeading, subHeading, drawCard, drawTable, drawDivider, sanitize } from '../helpers';

export function renderRecommendations(ctx: PDFContext, rec: RecommendationsData): void {
  newPage(ctx);
  sectionHeading(ctx, 'Recommendations');

  const cfg = rec.config_recommendation;
  if (cfg) {
    const recType = cfg.recommended === 'provisioned' ? 'Redshift Provisioned' : 'Redshift Serverless';
    const accentColor = cfg.recommended === 'serverless' ? C.PURPLE : C.PRIMARY_L;

    drawCard(ctx,
      [`Recommended Configuration: ${recType}`, ...cfg.reasons.map(r => sanitize(`* ${r}`))],
      'Configuration Recommendation',
      accentColor,
    );

    if (cfg.provisioned) {
      drawCard(ctx, [
        `Node Type: ${cfg.provisioned.node_type}`,
        `Nodes: ${cfg.provisioned.num_nodes}`,
        `vCPU Total: ${cfg.provisioned.vcpu_total}`,
        `Memory: ${cfg.provisioned.memory_gb_total} GB`,
        `Storage: ${cfg.provisioned.storage_type}`,
      ], 'Provisioned Configuration', C.PRIMARY_L);
    }

    if (cfg.serverless) {
      drawCard(ctx, [
        `Base RPU: ${cfg.serverless.base_rpu}`,
        `Max RPU: ${cfg.serverless.max_rpu}`,
        `Est. RPU Hours/Month: ${cfg.serverless.est_rpu_hours_monthly}`,
        `Est. Utilization: ${cfg.serverless.est_utilization_pct}%`,
      ], 'Serverless Configuration', C.PURPLE);
    }

    if (cfg.key_stats) {
      drawCard(ctx, [
        `Data Volume: ${cfg.key_stats.total_data_volume_gb.toFixed(2)} GB`,
        `Total Rows: ${cfg.key_stats.total_rows.toLocaleString()}`,
        `Tables: ${cfg.key_stats.total_tables}`,
        `Queries Analyzed: ${cfg.key_stats.total_queries_analyzed}`,
      ], 'Key Statistics', C.SUCCESS);
    }
  }

  drawDivider(ctx);

  if (rec.dist_sort_keys?.length > 0) {
    subHeading(ctx, 'Distribution & Sort Keys');
    drawTable(ctx,
      ['Table', 'Dist Key', 'Sort Key', 'Reasoning'],
      rec.dist_sort_keys.map(d => [
        d.table_name, d.distkey, d.sortkey, sanitize(d.reasoning?.join('; ') || ''),
      ]),
    );
  }

  if (rec.architecture?.strategies?.length > 0) {
    subHeading(ctx, 'Architecture Strategies');
    rec.architecture.strategies.forEach(s => {
      drawCard(ctx, s.points.map(p => sanitize(`* ${p}`)), sanitize(s.title), C.ACCENT);
    });
  }
}
