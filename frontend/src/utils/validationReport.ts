/**
 * Validation Report export helpers (CSV + PDF).
 *
 * Normalized shape so BOTH the migration-based detail page and the direct
 * connection-mode results can produce identical reports.
 */

import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';

export interface ValidationReportRow {
  tableName: string;      // e.g. "customers" or "dbo.customers → public.customers"
  check: string;          // "Row Count", "NULL", "Schema", ...
  status: string;         // "passed" | "failed" | "error" | "skipped" | ...
  details: string;        // human-readable detail / JSON string
}

export interface ValidationReportMeta {
  title: string;          // report heading
  subtitle?: string;      // e.g. "SQL Server → Redshift"
  overallStatus?: string; // passed/failed/error
  generatedAt?: string;   // ISO; defaults to now
  summary?: Array<{ label: string; value: string | number }>;
}

const sanitize = (s: unknown): string =>
  String(s ?? '')
    // jsPDF's default font can't render some unicode; keep it ASCII-safe
    .replace(/[^\x20-\x7E]/g, '')
    .trim();

const statusLabel = (s: string | null | undefined): string => {
  if (!s) return 'Skipped';
  return s.charAt(0).toUpperCase() + s.slice(1);
};

// ---------------------------------------------------------------------------
// CSV
// ---------------------------------------------------------------------------

export function buildValidationCsv(rows: ValidationReportRow[]): string {
  const escape = (v: unknown) => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const header = ['Table Name', 'Validation Check', 'Status', 'Details'];
  const body = rows.map((r) => [r.tableName, r.check, statusLabel(r.status), r.details]);
  return [header, ...body].map((row) => row.map(escape).join(',')).join('\n');
}

export function downloadCsv(filename: string, rows: ValidationReportRow[]): void {
  const blob = new Blob([buildValidationCsv(rows)], { type: 'text/csv;charset=utf-8;' });
  triggerDownload(blob, filename.endsWith('.csv') ? filename : `${filename}.csv`);
}

// ---------------------------------------------------------------------------
// PDF
// ---------------------------------------------------------------------------

export function downloadValidationPdf(
  filename: string,
  meta: ValidationReportMeta,
  rows: ValidationReportRow[],
): void {
  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
  const pageW = doc.internal.pageSize.getWidth();
  const margin = 14;
  let y = 18;

  // Brand accent
  const BLUE: [number, number, number] = [37, 99, 235];
  const DARK: [number, number, number] = [17, 24, 39];
  const GREY: [number, number, number] = [107, 114, 128];

  // Title
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(16);
  doc.setTextColor(...DARK);
  doc.text(sanitize(meta.title) || 'Validation Report', margin, y);
  y += 7;

  if (meta.subtitle) {
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(10);
    doc.setTextColor(...GREY);
    doc.text(sanitize(meta.subtitle), margin, y);
    y += 6;
  }

  // Overall status pill
  if (meta.overallStatus) {
    const label = `Overall: ${statusLabel(meta.overallStatus)}`;
    doc.setFontSize(10);
    doc.setFont('helvetica', 'bold');
    const colorMap: Record<string, [number, number, number]> = {
      passed: [22, 163, 74],
      failed: [220, 38, 38],
      error: [234, 88, 12],
    };
    doc.setTextColor(...(colorMap[meta.overallStatus.toLowerCase()] || GREY));
    doc.text(label, margin, y);
    y += 6;
  }

  // Generated timestamp
  const ts = meta.generatedAt || new Date().toISOString();
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(8);
  doc.setTextColor(...GREY);
  doc.text(`Generated: ${sanitize(new Date(ts).toLocaleString())}`, margin, y);
  y += 6;

  // Summary metrics row
  if (meta.summary && meta.summary.length > 0) {
    autoTable(doc, {
      startY: y,
      margin: { left: margin, right: margin },
      head: [meta.summary.map((s) => sanitize(s.label))],
      body: [meta.summary.map((s) => sanitize(s.value))],
      theme: 'grid',
      headStyles: { fillColor: BLUE, textColor: [255, 255, 255], fontSize: 8 },
      bodyStyles: { fontSize: 9, textColor: DARK },
      styles: { cellPadding: 2 },
    });
    y = (doc as any).lastAutoTable.finalY + 6;
  }

  // Results table
  autoTable(doc, {
    startY: y,
    margin: { left: margin, right: margin },
    head: [['Table', 'Check', 'Status', 'Details']],
    body: rows.map((r) => [
      sanitize(r.tableName),
      sanitize(r.check),
      statusLabel(r.status),
      sanitize(r.details),
    ]),
    theme: 'striped',
    headStyles: { fillColor: BLUE, textColor: [255, 255, 255], fontSize: 8 },
    bodyStyles: { fontSize: 8, textColor: DARK },
    columnStyles: {
      0: { cellWidth: 45 },
      1: { cellWidth: 28 },
      2: { cellWidth: 22 },
      3: { cellWidth: 'auto' },
    },
    didParseCell: (data) => {
      // Color the status cell
      if (data.section === 'body' && data.column.index === 2) {
        const v = String(data.cell.raw).toLowerCase();
        if (v === 'passed') data.cell.styles.textColor = [22, 163, 74];
        else if (v === 'failed') data.cell.styles.textColor = [220, 38, 38];
        else if (v === 'error') data.cell.styles.textColor = [234, 88, 12];
        else data.cell.styles.textColor = GREY;
      }
    },
  });

  // Page numbers
  const total = doc.getNumberOfPages();
  for (let i = 1; i <= total; i++) {
    doc.setPage(i);
    doc.setFontSize(7);
    doc.setTextColor(...GREY);
    doc.text(
      `Page ${i} of ${total}`,
      pageW - margin,
      doc.internal.pageSize.getHeight() - 8,
      { align: 'right' },
    );
  }

  doc.save(filename.endsWith('.pdf') ? filename : `${filename}.pdf`);
}

// ---------------------------------------------------------------------------
// Shared download trigger
// ---------------------------------------------------------------------------

function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
