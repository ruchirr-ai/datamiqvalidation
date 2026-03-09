/**
 * PDF Report Generator using jsPDF + jspdf-autotable
 * Direct PDF generation - no html2canvas, no DOM cloning.
 */

import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import type {
  AssessmentFullReport,
  RecommendationsData,
  TCOData
} from '../services/assessmentsApi';

export interface PDFGeneratorOptions {
  report: AssessmentFullReport;
  selectedSections: string[];
  assessmentId: number;
  recommendations?: RecommendationsData | null;
  tcoData?: TCOData | null;
}

// Colors
const BLUE = [30, 64, 175] as const;     // #1e40af
const LIGHT_BLUE = [239, 246, 255] as const; // #eff6ff
const GRAY = [107, 114, 128] as const;   // #6b7280
const DARK = [17, 24, 39] as const;      // #111827
const WHITE = [255, 255, 255] as const;
const TH_BG = [241, 245, 249] as const;  // #f1f5f9
const BORDER = [203, 213, 225] as const; // #cbd5e1
const RED = [239, 68, 68] as const;
const GREEN = [16, 185, 129] as const;
const PURPLE = [139, 92, 246] as const;

const fmtSize = (mb: number): string => {
  if (mb < 1) return `${(mb * 1024).toFixed(0)} KB`;
  if (mb < 1024) return `${mb.toFixed(2)} MB`;
  const gb = mb / 1024;
  if (gb < 1024) return `${gb.toFixed(2)} GB`;
  return `${(gb / 1024).toFixed(2)} TB`;
};

const fmtNum = (n: number): string => n?.toLocaleString() ?? '0';

const fmtDate = (d: string | null): string => {
  if (!d) return 'N/A';
  try { return new Date(d).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }); } catch { return d; }
};

export function generatePDF(opts: PDFGeneratorOptions): void {
  const { report, selectedSections, recommendations, tcoData } = opts;
  const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
  const pageW = doc.internal.pageSize.getWidth();
  const margin = 12;
  const contentW = pageW - margin * 2;
  let y = margin;

  // Helper: add new page if needed
  const checkPage = (needed: number) => {
    const pageH = doc.internal.pageSize.getHeight();
    if (y + needed > pageH - margin) {
      doc.addPage();
      y = margin;
    }
  };

  // Helper: draw section heading
  const sectionHeading = (title: string) => {
    checkPage(16);
    // Blue left bar + light blue background
    doc.setFillColor(...LIGHT_BLUE);
    doc.rect(margin, y, contentW, 9, 'F');
    doc.setFillColor(...BLUE);
    doc.rect(margin, y, 1.5, 9, 'F');
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(12);
    doc.setTextColor(...BLUE);
    doc.text(title, margin + 5, y + 6.5);
    y += 13;
  };

  // Helper: draw a metric box
  const drawMetric = (x: number, w: number, value: string, label: string) => {
    doc.setFillColor(...LIGHT_BLUE);
    doc.roundedRect(x, y, w, 16, 1, 1, 'F');
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(14);
    doc.setTextColor(...BLUE);
    doc.text(value, x + w / 2, y + 7, { align: 'center' });
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(7);
    doc.setTextColor(...GRAY);
    doc.text(label.toUpperCase(), x + w / 2, y + 13, { align: 'center' });
  };

  // Helper: draw a card
  const drawCard = (lines: string[], titleText?: string) => {
    const lineH = 5;
    const cardH = (titleText ? lineH : 0) + lines.length * lineH + 6;
    checkPage(cardH);
    doc.setFillColor(249, 250, 251);
    doc.setDrawColor(229, 231, 235);
    doc.roundedRect(margin, y, contentW, cardH, 1, 1, 'FD');
    let cy = y + 4;
    if (titleText) {
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(9);
      doc.setTextColor(...DARK);
      doc.text(titleText, margin + 4, cy + 2);
      cy += lineH;
    }
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8);
    doc.setTextColor(...GRAY);
    lines.forEach(line => {
      doc.text(line, margin + 4, cy + 2);
      cy += lineH;
    });
    y += cardH + 3;
  };

  // Helper: draw table using autotable
  const drawTable = (headers: string[], rows: string[][]) => {
    checkPage(20);
    autoTable(doc, {
      startY: y,
      margin: { left: margin, right: margin },
      head: [headers],
      body: rows,
      theme: 'grid',
      styles: {
        fontSize: 8,
        cellPadding: 2,
        textColor: [71, 85, 105],
        lineColor: [...BORDER],
        lineWidth: 0.2,
      },
      headStyles: {
        fillColor: [...TH_BG],
        textColor: [51, 65, 85],
        fontStyle: 'bold',
        fontSize: 7.5,
      },
      alternateRowStyles: {
        fillColor: [248, 250, 252],
      },
      didDrawPage: () => {
        // Reset y after page break
      },
    });
    y = (doc as any).lastAutoTable.finalY + 6;
  };

  // ===== HEADER =====
  doc.setFillColor(...BLUE);
  doc.rect(0, 0, pageW, 22, 'F');
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(18);
  doc.setTextColor(...WHITE);
  doc.text(report.assessment.name, margin, 10);
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(9);
  doc.text(
    `Assessment Report  •  Generated ${new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })} IST  •  Project: ${report.assessment.project_id}`,
    margin, 17
  );
  y = 28;

  // ===== SUMMARY =====
  if (selectedSections.includes('summary')) {
    sectionHeading('Summary');
    const procs = report.routines.filter(r => r.routine_type === 'PROCEDURE').length;
    const funcs = report.routines.filter(r => r.routine_type === 'FUNCTION').length;
    const metrics = [
      { v: String(report.assessment.total_datasets), l: 'Datasets' },
      { v: String(report.assessment.total_tables), l: 'Tables' },
      { v: String(report.assessment.total_views), l: 'Views' },
      { v: String(report.routines.length), l: 'Routines' },
      { v: String(procs), l: 'Procedures' },
      { v: String(funcs), l: 'Functions' },
      { v: String(report.ml_models.length), l: 'ML Models' },
      { v: fmtSize(report.assessment.total_size_mb), l: 'Total Size' },
    ];
    const mw = (contentW - 7 * 2) / 8; // 8 metrics with 2mm gap
    metrics.forEach((m, i) => {
      drawMetric(margin + i * (mw + 2), mw, m.v, m.l);
    });
    y += 20;
    drawCard([
      `Started: ${fmtDate(report.assessment.started_at)}`,
      `Completed: ${fmtDate(report.assessment.completed_at)}`,
      `Status: ${report.assessment.status.toUpperCase()}`,
    ]);
  }

  // ===== DATASETS =====
  if (selectedSections.includes('datasets') && report.datasets.length > 0) {
    doc.addPage(); y = margin;
    sectionHeading(`Datasets (${report.datasets.length})`);
    drawTable(
      ['Dataset', 'Tables', 'Size', 'Location'],
      report.datasets.map(d => [d.dataset_name, String(d.table_count), fmtSize(d.total_size_mb), d.location || 'N/A'])
    );
  }

  // ===== TABLES =====
  if (selectedSections.includes('tables') && report.tables.length > 0) {
    doc.addPage(); y = margin;
    sectionHeading(`Tables (${report.tables.length})`);
    drawTable(
      ['Table', 'Type', 'Rows', 'Size', 'Partitioning', 'Clustering'],
      report.tables.map(t => [
        `${t.dataset_name}.${t.table_name}`,
        t.table_type || 'TABLE',
        fmtNum(t.row_count),
        fmtSize(t.size_mb),
        t.partitioning_columns?.join(', ') || 'None',
        t.clustering_columns?.join(', ') || 'None',
      ])
    );
  }

  // ===== VIEWS =====
  if (selectedSections.includes('views') && report.views.length > 0) {
    doc.addPage(); y = margin;
    sectionHeading(`Views (${report.views.length})`);
    drawTable(
      ['View', 'Definition (Preview)'],
      report.views.map(v => [
        v.view_name,
        (v.view_definition || '').substring(0, 120) + ((v.view_definition || '').length > 120 ? '...' : ''),
      ])
    );
  }

  // ===== STORED PROCEDURES =====
  if (selectedSections.includes('procedures')) {
    const procs = report.routines.filter(r => r.routine_type === 'PROCEDURE');
    if (procs.length > 0) {
      doc.addPage(); y = margin;
      sectionHeading(`Stored Procedures (${procs.length})`);
      drawTable(
        ['Procedure', 'Language', 'Created'],
        procs.map(p => [p.routine_name, p.external_language || 'SQL', fmtDate(p.creation_time)])
      );
    }
  }

  // ===== FUNCTIONS =====
  if (selectedSections.includes('functions')) {
    const funcs = report.routines.filter(r => r.routine_type === 'FUNCTION');
    if (funcs.length > 0) {
      doc.addPage(); y = margin;
      sectionHeading(`Functions (${funcs.length})`);
      drawTable(
        ['Function', 'Language', 'Return Type', 'Created'],
        funcs.map(f => [f.routine_name, f.external_language || 'SQL', f.return_type || 'N/A', fmtDate(f.creation_time)])
      );
    }
  }

  // ===== ML MODELS =====
  if (selectedSections.includes('ml-models') && report.ml_models.length > 0) {
    doc.addPage(); y = margin;
    sectionHeading(`ML & Spark Models (${report.ml_models.length})`);
    drawTable(
      ['Model', 'Type', 'Created'],
      report.ml_models.map(m => [`${m.dataset_name}.${m.model_name}`, m.model_type || 'N/A', fmtDate(m.creation_time)])
    );
  }

  // ===== QUERY INSIGHTS =====
  if (selectedSections.includes('query-insights') && report.query_stats.length > 0) {
    doc.addPage(); y = margin;
    sectionHeading(`Query Insights (${report.query_stats.length} total, top 50)`);
    const top = report.query_stats.slice(0, 50);
    drawTable(
      ['User', 'Query Preview', 'Bytes Scanned', 'Slot Time', 'Cache'],
      top.map(q => [
        q.user_email || 'N/A',
        q.query_text ? q.query_text.substring(0, 60) : 'N/A',
        q.bytes_scanned ? fmtSize(q.bytes_scanned / (1024 * 1024)) : 'N/A',
        q.slot_milliseconds ? (q.slot_milliseconds / 1000).toFixed(1) + 's' : 'N/A',
        q.cache_hit ? 'Yes' : 'No',
      ])
    );
  }

  // ===== USER INSIGHTS =====
  if (selectedSections.includes('user-insights') && report.query_stats.length > 0) {
    doc.addPage(); y = margin;
    const umap = new Map<string, { count: number; bytes: number; slots: number }>();
    report.query_stats.forEach(q => {
      const e = q.user_email || 'Unknown';
      const x = umap.get(e) || { count: 0, bytes: 0, slots: 0 };
      x.count++; x.bytes += q.bytes_scanned || 0; x.slots += q.slot_milliseconds || 0;
      umap.set(e, x);
    });
    const sorted = Array.from(umap.entries()).sort((a, b) => b[1].count - a[1].count);
    sectionHeading(`User Insights (${umap.size} users)`);
    drawTable(
      ['User', 'Queries', 'Data Scanned', 'Total Slot Time'],
      sorted.map(([em, d]) => [em, String(d.count), fmtSize(d.bytes / (1024 * 1024)), (d.slots / 1000).toFixed(1) + 's'])
    );
  }

  // ===== SECURITY =====
  if (selectedSections.includes('security') && report.security_policies.length > 0) {
    doc.addPage(); y = margin;
    sectionHeading(`Security Policies (${report.security_policies.length})`);
    drawTable(
      ['Type', 'Table', 'Policy', 'Grantees'],
      report.security_policies.map(s => [
        s.security_type || 'N/A',
        s.table_name,
        s.policy_name || 'N/A',
        s.grantees?.join(', ') || 'N/A',
      ])
    );
  }

  // ===== RECOMMENDATIONS =====
  if (selectedSections.includes('recommendations') && recommendations) {
    doc.addPage(); y = margin;
    sectionHeading('Recommendations');

    const cfg = recommendations.config_recommendation;
    if (cfg) {
      const recType = cfg.recommended === 'provisioned' ? 'Redshift Provisioned' : 'Redshift Serverless';
      drawCard(
        [`Recommended: ${recType}`, ...cfg.reasons.map(r => `• ${r}`)],
        'Configuration Recommendation'
      );
      if (cfg.provisioned) {
        drawCard([
          `Node: ${cfg.provisioned.node_type} × ${cfg.provisioned.num_nodes}`,
          `vCPU: ${cfg.provisioned.vcpu_total} | Memory: ${cfg.provisioned.memory_gb_total} GB | Storage: ${cfg.provisioned.storage_type}`,
        ], 'Provisioned Configuration');
      }
    }

    if (recommendations.dist_sort_keys?.length > 0) {
      checkPage(12);
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(10);
      doc.setTextColor(...DARK);
      doc.text('Distribution & Sort Keys', margin, y + 4);
      y += 8;
      drawTable(
        ['Table', 'Dist Key', 'Sort Key', 'Reasoning'],
        recommendations.dist_sort_keys.map(d => [
          d.table_name, d.distkey, d.sortkey, d.reasoning?.join('; ') || '',
        ])
      );
    }

    if (recommendations.architecture?.strategies?.length > 0) {
      checkPage(12);
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(10);
      doc.setTextColor(...DARK);
      doc.text('Architecture Strategies', margin, y + 4);
      y += 8;
      recommendations.architecture.strategies.forEach(s => {
        drawCard(s.points.map(p => `• ${p}`), s.title);
      });
    }
  }

  // ===== TCO ANALYSIS =====
  if (selectedSections.includes('tco') && tcoData) {
    doc.addPage(); y = margin;
    sectionHeading(`TCO Analysis — ${tcoData.region_label || tcoData.aws_region}`);

    const bq = tcoData.bigquery_costs?.monthly || 0;
    const prov = tcoData.provisioned_costs?.monthly || 0;
    const sl = tcoData.serverless_costs?.monthly || 0;
    const fmt$ = (n: number) => '$' + n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

    // Three cost boxes
    const boxW = (contentW - 8) / 3;
    const costs = [
      { label: 'BigQuery Monthly', value: fmt$(bq), color: RED },
      { label: 'Provisioned Monthly', value: fmt$(prov), color: BLUE },
      { label: 'Serverless Monthly', value: fmt$(sl), color: PURPLE },
    ];
    costs.forEach((c, i) => {
      const bx = margin + i * (boxW + 4);
      doc.setFillColor(249, 250, 251);
      doc.roundedRect(bx, y, boxW, 20, 1, 1, 'F');
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(7);
      doc.setTextColor(...GRAY);
      doc.text(c.label, bx + boxW / 2, y + 6, { align: 'center' });
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(16);
      doc.setTextColor(c.color[0], c.color[1], c.color[2]);
      doc.text(c.value, bx + boxW / 2, y + 16, { align: 'center' });
    });
    y += 26;

    const comp = tcoData.comparison;
    if (comp) {
      drawTable(
        ['Option', '3-Year Cost'],
        [
          ['BigQuery', '$' + (comp.bq_3yr_tco?.toLocaleString() || '0')],
          ['Redshift Provisioned', '$' + (comp.provisioned_3yr_tco?.toLocaleString() || '0')],
          ['Redshift Serverless', '$' + (comp.serverless_3yr_tco?.toLocaleString() || '0')],
        ]
      );
      drawCard([
        `Best Option: ${comp.best_option}`,
        `Savings: $${comp.savings_amount?.toLocaleString() || '0'} (${comp.savings_pct?.toFixed(1) || '0'}%)`,
      ], '3-Year TCO Comparison Result');
    }

    if (tcoData.provisioned_costs?.node_type) {
      drawCard([
        `${tcoData.provisioned_costs.node_type} × ${tcoData.provisioned_costs.num_nodes} nodes`,
      ], 'Recommended Provisioned Setup');
    }
  }

  // ===== FOOTER on last page =====
  const pageH = doc.internal.pageSize.getHeight();
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(7);
  doc.setTextColor(...GRAY);
  doc.text(
    `Generated by DataMIQ • ${new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })} IST`,
    pageW / 2, pageH - 5, { align: 'center' }
  );

  // Save
  const filename = `${report.assessment.name.replace(/[^a-zA-Z0-9-_ ]/g, '')}_Report.pdf`;
  doc.save(filename);
}
