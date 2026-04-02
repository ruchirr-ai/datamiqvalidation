/**
 * CSV Export Utility
 * Converts data arrays to CSV and triggers browser download.
 */

type CsvRow = Record<string, any>;

function escapeCsvValue(val: any): string {
  if (val === null || val === undefined) return '';
  const str = String(val);
  if (str.includes(',') || str.includes('"') || str.includes('\n')) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

export function downloadCsv(rows: CsvRow[], columns: { key: string; header: string }[], filename: string) {
  if (rows.length === 0) return;

  const header = columns.map(c => escapeCsvValue(c.header)).join(',');
  const lines = rows.map(row =>
    columns.map(c => escapeCsvValue(row[c.key])).join(',')
  );
  const csv = [header, ...lines].join('\n');

  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
