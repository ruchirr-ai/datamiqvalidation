/**
 * PDF Report Generator — Professional Edition
 */
import jsPDF from 'jspdf';
import type { PDFGeneratorOptions, PDFContext } from './types';
import { C } from './types';
import { getLogoDark, LOGO_ASPECT } from './shellkodeLogo';
import { registerSatoshiFont } from './fonts';

import { renderSummary } from './sections/summary';
import { renderDatasets } from './sections/datasets';
import { renderTables } from './sections/tables';
import { renderViews } from './sections/views';
import { renderProcedures, renderFunctions } from './sections/routines';
import { renderMLModels } from './sections/mlModels';
import { renderQueryInsights } from './sections/queryInsights';
import { renderUserInsights } from './sections/userInsights';
import { renderSecurity } from './sections/security';
import { renderRecommendations } from './sections/recommendations';
import { renderTCO } from './sections/tco';

export type { PDFGeneratorOptions } from './types';

// ── Cover page — deep blue background ──
function renderCover(ctx: PDFContext, name: string, projectId: string, status: string, logoPng: string): void {
  const { doc, pageW, pageH, margin } = ctx;

  // Deep navy-blue background for a premium look
  doc.setFillColor(10, 36, 75);
  doc.rect(0, 0, pageW, pageH, 'F');

  // Subtle accent stripe at very top
  doc.setFillColor(...C.PRIMARY);
  doc.rect(0, 0, pageW, 2.5, 'F');

  // Shellkode logo top-right (SVG aspect 126:23 = ~5.48:1)
  const coverLogoH = 10;
  const coverLogoW = coverLogoH * LOGO_ASPECT;
  doc.addImage(logoPng, 'PNG', pageW - margin - coverLogoW, 10, coverLogoW, coverLogoH);

  // Brand name — #00ADEF on dark
  doc.setFont('Satoshi', 'bold');
  doc.setFontSize(16);
  doc.setTextColor(...C.PRIMARY);
  doc.text('DataMIQ', margin + 4, 20);

  // Tagline
  doc.setFont('Satoshi', 'normal');
  doc.setFontSize(8);
  doc.setTextColor(160, 185, 220);
  doc.text('Data Assessment & Migration Platform', margin + 4, 27);

  // Thin separator
  doc.setDrawColor(255, 255, 255);
  doc.setGState(new (doc as any).GState({ opacity: 0.1 }));
  doc.setLineWidth(0.3);
  doc.line(margin + 4, 32, pageW - margin, 32);
  doc.setGState(new (doc as any).GState({ opacity: 1 }));

  // Main title area
  const titleY = pageH * 0.34;

  // Label — #00ADEF accent
  doc.setFont('Satoshi', 'normal');
  doc.setFontSize(11);
  doc.setTextColor(...C.PRIMARY);
  doc.text('ASSESSMENT REPORT', margin + 8, titleY - 10);

  // Assessment name — large, white, bold
  doc.setFont('Satoshi', 'bold');
  doc.setFontSize(36);
  doc.setTextColor(...C.WHITE);
  const nameLines = doc.splitTextToSize(name, ctx.contentW - 16);
  nameLines.forEach((line: string, i: number) => {
    doc.text(line, margin + 8, titleY + 6 + i * 14);
  });
  const nameEndY = titleY + 6 + nameLines.length * 14;

  // Meta info
  const metaY = nameEndY + 14;
  const ts = new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' });
  const metaItems = [
    ['Project', projectId],
    ['Status', status.toUpperCase()],
    ['Generated', `${ts} IST`],
  ];

  metaItems.forEach(([label, value], i) => {
    const my = metaY + i * 12;
    doc.setFont('Satoshi', 'normal');
    doc.setFontSize(7.5);
    doc.setTextColor(120, 150, 190);
    doc.text(label.toUpperCase(), margin + 8, my);
    doc.setFont('Satoshi', 'bold');
    doc.setFontSize(11);
    doc.setTextColor(220, 230, 245);
    doc.text(value, margin + 8, my + 5.5);
  });

  // Bottom accent — #00ADEF bar
  doc.setFillColor(...C.PRIMARY);
  doc.rect(0, pageH - 3, pageW, 3, 'F');
}

// ── Page numbers & footer ──
function addPageNumbers(doc: jsPDF): void {
  const totalPages = doc.getNumberOfPages();
  const pageW = doc.internal.pageSize.getWidth();
  const pageH = doc.internal.pageSize.getHeight();

  for (let i = 2; i <= totalPages; i++) {
    doc.setPage(i);

    // Footer bg
    doc.setFillColor(...C.GRAY_BG);
    doc.rect(0, pageH - 10, pageW, 10, 'F');
    doc.setDrawColor(...C.GRAY_XL);
    doc.setLineWidth(0.3);
    doc.line(0, pageH - 10, pageW, pageH - 10);

    // Left: brand
    doc.setFont('Satoshi', 'bold');
    doc.setFontSize(7);
    doc.setTextColor(...C.PRIMARY);
    doc.text('DataMIQ', 14, pageH - 4);
    doc.setFont('Satoshi', 'normal');
    doc.setTextColor(...C.GRAY_L);
    const bw = doc.getTextWidth('DataMIQ');
    doc.text('  by Shellkode', 14 + bw, pageH - 4);

    // Center: timestamp
    const ts = new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' });
    doc.setFontSize(6.5);
    doc.setTextColor(...C.GRAY_L);
    doc.text(ts + ' IST', pageW / 2, pageH - 4, { align: 'center' });

    // Right: page badge
    const pageText = `${i - 1} / ${totalPages - 1}`;
    const ptw = doc.getTextWidth(pageText) + 6;
    doc.setFillColor(...C.PRIMARY);
    doc.roundedRect(pageW - 14 - ptw, pageH - 7.5, ptw + 2, 5.5, 1, 1, 'F');
    doc.setFont('Satoshi', 'bold');
    doc.setFontSize(6.5);
    doc.setTextColor(...C.WHITE);
    doc.text(pageText, pageW - 14 - ptw / 2 + 1, pageH - 3.8, { align: 'center' });
  }
}

// ── Main entry (async — needs to convert SVG logo to PNG) ──
export async function generatePDF(opts: PDFGeneratorOptions): Promise<void> {
  const { report, selectedSections, recommendations, tcoData, queryInsightsData } = opts;

  // Convert SVG logo to PNG data URL
  const logoPng = await getLogoDark();

  const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
  registerSatoshiFont(doc);
  const pageW = doc.internal.pageSize.getWidth();
  const pageH = doc.internal.pageSize.getHeight();
  const margin = 14;

  const ctx: PDFContext = {
    doc, y: margin, margin, pageW, pageH,
    contentW: pageW - margin * 2,
  };

  renderCover(ctx, report.assessment.name, report.assessment.project_id, report.assessment.status, logoPng);

  const has = (s: string) => selectedSections.includes(s);

  if (has('summary'))         { doc.addPage(); ctx.y = margin; renderSummary(ctx, report); }
  if (has('datasets'))        renderDatasets(ctx, report.datasets);
  if (has('tables'))          renderTables(ctx, report.tables);
  if (has('views'))           renderViews(ctx, report.views);
  if (has('procedures'))      renderProcedures(ctx, report.routines);
  if (has('functions'))       renderFunctions(ctx, report.routines);
  if (has('ml-models'))       renderMLModels(ctx, report.ml_models);
  if (has('query-insights'))  renderQueryInsights(ctx, report.query_stats, queryInsightsData);
  if (has('user-insights'))   renderUserInsights(ctx, report.query_stats);
  if (has('security'))        renderSecurity(ctx, report.security_policies);
  if (has('recommendations') && recommendations) renderRecommendations(ctx, recommendations);
  if (has('tco') && tcoData)  renderTCO(ctx, tcoData);

  addPageNumbers(doc);

  const filename = `${report.assessment.name.replace(/[^a-zA-Z0-9-_ ]/g, '')}_Report.pdf`;
  doc.save(filename);
}
