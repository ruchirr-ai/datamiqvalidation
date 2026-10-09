/**
 * Validation Report export helpers (CSV + PDF).
 *
 * Normalized shape so BOTH the migration-based detail page and the direct
 * connection-mode results can produce identical, comprehensive reports.
 *
 * A "comprehensive" report means: for every FAILED check we surface the exact
 * row/column that mismatched (primary key, column, source value vs target
 * value) rather than just a pass/fail summary. The backend already computes
 * this as `sample_discrepancies` for data-match and specific-row checks, and
 * as column `discrepancies` for schema/DDL checks.
 */

import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';

/**
 * A single row/column-level mismatch for a failed check.
 * Mirrors the backend `sample_discrepancies` entry shapes plus schema
 * (DDL) column discrepancies, normalized into one flat structure.
 */
export interface ReportDiscrepancy {
  type: string;          // "value_mismatch" | "missing_in_target" | "extra_in_target" | "missing_column" | "type_mismatch" | ...
  primaryKey?: string;   // e.g. "id=42" or "order_id=7, line=3" (empty for schema checks)
  column?: string;       // the column that mismatched
  sourceValue?: string;  // source-side value / type
  targetValue?: string;  // target-side value / type
  note?: string;         // optional extra context
}

export interface ValidationReportRow {
  tableName: string;      // e.g. "customers" or "dbo.customers → public.customers"
  check: string;          // "Row Count", "NULL", "Schema", ...
  status: string;         // "passed" | "failed" | "error" | "skipped" | ...
  details: string;        // human-readable one-line summary
  discrepancies?: ReportDiscrepancy[]; // row/column-level mismatch detail (for failed checks)
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

const prettyType = (t: string): string => {
  switch (t) {
    case 'value_mismatch': return 'Value mismatch';
    case 'missing_in_target': return 'Missing in target';
    case 'extra_in_target': return 'Extra in target';
    case 'missing_column': return 'Missing column';
    case 'extra_column': return 'Extra column';
    case 'type_mismatch': return 'Type mismatch';
    case 'nullability_mismatch': return 'Nullability mismatch';
    default: return t ? t.replace(/_/g, ' ') : 'Mismatch';
  }
};

// ---------------------------------------------------------------------------
// Normalizers — turn a backend check `result` dict into readable summary +
// structured discrepancies. These accept the raw JSONB result object.
// ---------------------------------------------------------------------------

const asStr = (v: unknown): string =>
  v === null || v === undefined ? 'NULL' : String(v);

const formatPk = (pk: Record<string, unknown> | null | undefined): string => {
  if (!pk || typeof pk !== 'object') return '';
  return Object.entries(pk)
    .map(([k, v]) => `${k}=${asStr(v)}`)
    .join(', ');
};

/**
 * Extract structured discrepancies from a record-match / specific-row result's
 * `sample_discrepancies` array.
 */
export function extractRecordDiscrepancies(
  result: Record<string, any> | null | undefined,
): ReportDiscrepancy[] {
  const samples = result && Array.isArray(result.sample_discrepancies)
    ? result.sample_discrepancies
    : [];
  return samples.map((d: any): ReportDiscrepancy => {
    const base: ReportDiscrepancy = {
      type: d?.type || 'mismatch',
      primaryKey: formatPk(d?.primary_key),
    };
    if (d?.type === 'value_mismatch' && d?.details) {
      base.column = d.details.column;
      base.sourceValue = asStr(d.details.source_value);
      base.targetValue = asStr(d.details.target_value);
    }
    return base;
  });
}

/**
 * Extract column-level discrepancies from a DDL/schema result's
 * `discrepancies` array.
 */
export function extractSchemaDiscrepancies(
  result: Record<string, any> | null | undefined,
): ReportDiscrepancy[] {
  const items = result && Array.isArray(result.discrepancies)
    ? result.discrepancies
    : [];
  return items.map((d: any): ReportDiscrepancy => ({
    type: d?.type || 'schema_mismatch',
    column: d?.column_name || d?.column,
    sourceValue: d?.source_type ?? undefined,
    targetValue: d?.target_type ?? undefined,
    note: d?.expected_type ? `expected ${d.expected_type}` : undefined,
  }));
}

/**
 * Schema discrepancies as produced by the DIRECT path's `schema_check.details`
 * ({ missing_in_target: [...], extra_in_target: [...], type_mismatches: [...] }).
 */
export function extractDirectSchemaDiscrepancies(
  details: Record<string, any> | null | undefined,
): ReportDiscrepancy[] {
  if (!details) return [];
  const out: ReportDiscrepancy[] = [];
  (details.missing_in_target || []).forEach((c: string) =>
    out.push({ type: 'missing_column', column: c }));
  (details.extra_in_target || []).forEach((c: string) =>
    out.push({ type: 'extra_column', column: c }));
  (details.type_mismatches || []).forEach((m: any) =>
    out.push({
      type: 'type_mismatch',
      column: m?.column,
      sourceValue: m?.source_type,
      targetValue: m?.target_type,
    }));
  return out;
}

/** One-line human-readable summary for a check result (used in the main table). */
export function summarizeResult(check: string, result: Record<string, any> | null | undefined): string {
  if (!result || Object.keys(result).length === 0) return '';
  const r = result;
  switch (check) {
    case 'Row Count':
      return `source=${asStr(r.source_count)}, target=${asStr(r.target_count)}, diff=${asStr(r.difference)}`;
    case 'NULL':
      return `column=${asStr(r.column)}, source nulls=${asStr(r.source_null_count)}, target nulls=${asStr(r.target_null_count)}, diff=${asStr(r.difference)}`;
    case 'Duplicate':
      return `key=${asStr(r.match_key)}, source dup groups=${asStr(r.source_duplicate_count)}, target dup groups=${asStr(r.target_duplicate_count)}, diff=${asStr(r.difference)}`;
    case 'SUM':
    case 'AVERAGE':
      return `column=${asStr(r.column)}, source=${asStr(r.source_value)}, target=${asStr(r.target_value)}, diff=${asStr(r.difference)}`;
    case 'Schema':
      return `source cols=${asStr(r.source_column_count)}, target cols=${asStr(r.target_column_count)}, discrepancies=${Array.isArray(r.discrepancies) ? r.discrepancies.length : 0}`;
    case 'Data Match':
    case 'Specific Row':
      return `compared=${asStr(r.total_compared)}, matched=${asStr(r.matched_count)}, missing=${asStr(r.missing_count)}, extra=${asStr(r.extra_count)}, mismatched=${asStr(r.mismatch_count)}`;
    default:
      return '';
  }
}

// ---------------------------------------------------------------------------
// CSV
// ---------------------------------------------------------------------------

export function buildValidationCsv(rows: ValidationReportRow[]): string {
  const escape = (v: unknown) => `"${String(v ?? '').replace(/"/g, '""')}"`;

  // Section 1: summary of every check
  const summaryHeader = ['Table Name', 'Validation Check', 'Status', 'Details'];
  const summaryBody = rows.map((r) => [r.tableName, r.check, statusLabel(r.status), r.details]);

  // Section 2: full mismatch detail (one line per discrepancy)
  const detailHeader = ['Table Name', 'Check', 'Mismatch Type', 'Primary Key / Row', 'Column', 'Source Value', 'Target Value', 'Note'];
  const detailBody: string[][] = [];
  rows.forEach((r) => {
    (r.discrepancies || []).forEach((d) => {
      detailBody.push([
        r.tableName,
        r.check,
        prettyType(d.type),
        d.primaryKey || '',
        d.column || '',
        d.sourceValue ?? '',
        d.targetValue ?? '',
        d.note || '',
      ]);
    });
  });

  const lines: string[][] = [summaryHeader, ...summaryBody];
  if (detailBody.length > 0) {
    lines.push([]);                       // blank separator row
    lines.push(['Mismatch Details']);
    lines.push(detailHeader);
    lines.push(...detailBody);
  }

  return lines.map((row) => row.map(escape).join(',')).join('\n');
}

export function downloadCsv(filename: string, rows: ValidationReportRow[]): void {
  const blob = new Blob([buildValidationCsv(rows)], { type: 'text/csv;charset=utf-8;' });
  triggerDownload(blob, filename.endsWith('.csv') ? filename : `${filename}.csv`);
}

// ---------------------------------------------------------------------------
// PDF
// ---------------------------------------------------------------------------

const BLUE: [number, number, number] = [37, 99, 235];
const DARK: [number, number, number] = [17, 24, 39];
const GREY: [number, number, number] = [107, 114, 128];
const RED: [number, number, number] = [220, 38, 38];

export function downloadValidationPdf(
  filename: string,
  meta: ValidationReportMeta,
  rows: ValidationReportRow[],
): void {
  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
  const pageW = doc.internal.pageSize.getWidth();
  const margin = 14;
  let y = 18;

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

  // Overall status
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

  // Section heading: check results
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(11);
  doc.setTextColor(...DARK);
  doc.text('Check Results', margin, y);
  y += 2;

  // Results summary table
  autoTable(doc, {
    startY: y + 2,
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
      0: { cellWidth: 42 },
      1: { cellWidth: 24 },
      2: { cellWidth: 18 },
      3: { cellWidth: 'auto' },
    },
    didParseCell: (data) => {
      if (data.section === 'body' && data.column.index === 2) {
        const v = String(data.cell.raw).toLowerCase();
        if (v === 'passed') data.cell.styles.textColor = [22, 163, 74];
        else if (v === 'failed') data.cell.styles.textColor = RED;
        else if (v === 'error') data.cell.styles.textColor = [234, 88, 12];
        else data.cell.styles.textColor = GREY;
      }
    },
  });
  y = (doc as any).lastAutoTable.finalY + 8;

  // ---------------------------------------------------------------------
  // Mismatch detail — the comprehensive part: exactly which rows/columns failed
  // ---------------------------------------------------------------------
  const rowsWithDiscrepancies = rows.filter((r) => (r.discrepancies || []).length > 0);

  if (rowsWithDiscrepancies.length > 0) {
    const pageH = doc.internal.pageSize.getHeight();
    if (y > pageH - 30) { doc.addPage(); y = 18; }

    doc.setFont('helvetica', 'bold');
    doc.setFontSize(11);
    doc.setTextColor(...DARK);
    doc.text('Mismatch Details', margin, y);
    y += 2;

    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8);
    doc.setTextColor(...GREY);
    doc.text(
      'Rows and columns that caused each failed check (sampled, up to 100 per check).',
      margin,
      y + 4,
    );
    y += 8;

    rowsWithDiscrepancies.forEach((r) => {
      const pageH = doc.internal.pageSize.getHeight();
      if (y > pageH - 24) { doc.addPage(); y = 18; }

      // Sub-heading per failed check
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(9);
      doc.setTextColor(...RED);
      doc.text(
        sanitize(`${r.tableName}  •  ${r.check}  (${r.discrepancies!.length} issue${r.discrepancies!.length === 1 ? '' : 's'})`),
        margin,
        y,
      );
      y += 2;

      autoTable(doc, {
        startY: y + 2,
        margin: { left: margin, right: margin },
        head: [['Type', 'Primary Key / Row', 'Column', 'Source', 'Target']],
        body: r.discrepancies!.map((d) => [
          sanitize(prettyType(d.type)),
          sanitize(d.primaryKey || '-'),
          sanitize(d.column || (d.note ? '' : '-')),
          sanitize(d.sourceValue ?? '-'),
          sanitize(d.targetValue ?? '-'),
        ]),
        theme: 'grid',
        headStyles: { fillColor: [55, 65, 81], textColor: [255, 255, 255], fontSize: 7.5 },
        bodyStyles: { fontSize: 7.5, textColor: DARK },
        columnStyles: {
          0: { cellWidth: 30 },
          1: { cellWidth: 48 },
          2: { cellWidth: 32 },
          3: { cellWidth: 'auto' },
          4: { cellWidth: 'auto' },
        },
      });
      y = (doc as any).lastAutoTable.finalY + 6;
    });
  }

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
