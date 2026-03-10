/**
 * PDF Report — Professional drawing helpers & formatters
 */
import autoTable from 'jspdf-autotable';
import type { PDFContext } from './types';
import { C } from './types';

// ── Formatters ──

export const fmtSize = (mb: number): string => {
  if (mb < 0.001) return '0 KB';
  if (mb < 1) return `${(mb * 1024).toFixed(0)} KB`;
  if (mb < 1024) return `${mb.toFixed(2)} MB`;
  const gb = mb / 1024;
  if (gb < 1024) return `${gb.toFixed(2)} GB`;
  return `${(gb / 1024).toFixed(2)} TB`;
};

export const fmtNum = (n: number): string => n?.toLocaleString() ?? '0';

export const fmtDate = (d: string | null): string => {
  if (!d) return 'N/A';
  try { return new Date(d).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }); }
  catch { return d; }
};

export const fmtDollar = (n: number): string =>
  '$' + n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const sanitize = (s: string | null | undefined): string => {
  if (!s) return '';
  return s
    .replace(/[\u2018\u2019]/g, "'")
    .replace(/[\u201C\u201D]/g, '"')
    .replace(/\u2014/g, ' -- ')
    .replace(/\u2013/g, ' - ')
    .replace(/\u2026/g, '...')
    .replace(/\u00D7/g, 'x')
    .replace(/\u2022/g, '*')
    .replace(/[^\x00-\x7F]/g, '?');
};

// ── Page management ──

export function checkPage(ctx: PDFContext, needed: number): void {
  if (ctx.y + needed > ctx.pageH - ctx.margin - 12) {
    ctx.doc.addPage();
    ctx.y = ctx.margin;
  }
}

export function newPage(ctx: PDFContext): void {
  ctx.doc.addPage();
  ctx.y = ctx.margin;
}

// ── Section heading with gradient bar ──

export function sectionHeading(ctx: PDFContext, title: string): void {
  checkPage(ctx, 20);
  const { doc, margin, contentW } = ctx;

  // Light teal background
  doc.setFillColor(...C.PRIMARY_BG);
  doc.setDrawColor(...C.PRIMARY_XL);
  doc.roundedRect(margin, ctx.y, contentW, 11, 1.5, 1.5, 'FD');

  // Left accent bar
  doc.setFillColor(...C.PRIMARY);
  doc.roundedRect(margin, ctx.y, 3, 11, 1.5, 0, 'F');
  doc.rect(margin + 1.5, ctx.y, 1.5, 11, 'F');

  // Title
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(11);
  doc.setTextColor(...C.PRIMARY_D);
  doc.text(title, margin + 7, ctx.y + 7.5);

  ctx.y += 15;
}

// ── Sub heading ──

export function subHeading(ctx: PDFContext, title: string): void {
  checkPage(ctx, 14);
  const { doc, margin, contentW } = ctx;

  // Light background bar
  doc.setFillColor(...C.PRIMARY_BG);
  doc.roundedRect(margin, ctx.y, contentW, 8, 1, 1, 'F');
  // Left accent
  doc.setFillColor(...C.PRIMARY_L);
  doc.roundedRect(margin, ctx.y, 2, 8, 1, 0, 'F');

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(9);
  doc.setTextColor(...C.PRIMARY);
  doc.text(title, margin + 6, ctx.y + 5.5);
  ctx.y += 11;
}

// ── Metric boxes (professional cards with shadow effect) ──

export function drawMetricRow(
  ctx: PDFContext,
  items: { v: string; l: string; color?: readonly [number, number, number]; bg?: readonly [number, number, number] }[],
  boxH = 22,
): void {
  const gap = 3;
  const boxW = (ctx.contentW - (items.length - 1) * gap) / items.length;
  checkPage(ctx, boxH + 4);
  const { doc, margin } = ctx;

  items.forEach((m, i) => {
    const bx = margin + i * (boxW + gap);
    const bg = m.bg || C.PRIMARY_BG;
    const fg = m.color || C.PRIMARY;

    // Shadow
    doc.setFillColor(0, 0, 0);
    doc.setGState(new (doc as any).GState({ opacity: 0.04 }));
    doc.roundedRect(bx + 0.5, ctx.y + 0.5, boxW, boxH, 2, 2, 'F');
    doc.setGState(new (doc as any).GState({ opacity: 1 }));

    // Card bg
    doc.setFillColor(...bg);
    doc.setDrawColor(...C.GRAY_XL);
    doc.roundedRect(bx, ctx.y, boxW, boxH, 2, 2, 'FD');

    // Value
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(14);
    doc.setTextColor(fg[0], fg[1], fg[2]);
    doc.text(m.v, bx + boxW / 2, ctx.y + 11, { align: 'center' });

    // Label
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(6);
    doc.setTextColor(...C.GRAY);
    doc.text(m.l.toUpperCase(), bx + boxW / 2, ctx.y + 17, { align: 'center' });
  });
  ctx.y += boxH + 4;
}

// ── Info card with styled header ──

export function drawCard(
  ctx: PDFContext,
  lines: string[],
  titleText?: string,
  accentColor?: readonly [number, number, number],
): void {
  const lineH = 5;
  const titleH = titleText ? 8 : 0;
  const cardH = titleH + lines.length * lineH + 6;
  checkPage(ctx, cardH);
  const { doc, margin, contentW } = ctx;
  const accent = accentColor || C.PRIMARY_L;

  // Card body
  doc.setFillColor(...C.WHITE);
  doc.setDrawColor(...C.GRAY_XL);
  doc.setLineWidth(0.3);
  doc.roundedRect(margin, ctx.y, contentW, cardH, 2, 2, 'FD');

  // Left accent bar
  doc.setFillColor(accent[0], accent[1], accent[2]);
  doc.roundedRect(margin, ctx.y, 2.5, cardH, 2, 0, 'F');
  doc.rect(margin + 1.5, ctx.y, 1, cardH, 'F'); // fill the gap

  let cy = ctx.y + 4;
  if (titleText) {
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(9);
    doc.setTextColor(...C.DARK);
    doc.text(titleText, margin + 7, cy + 2);
    // Separator line under title
    cy += 5;
    doc.setDrawColor(...C.GRAY_XL);
    doc.setLineWidth(0.2);
    doc.line(margin + 7, cy, margin + contentW - 4, cy);
    cy += 3;
  }
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(8);
  doc.setTextColor(...C.GRAY);
  lines.forEach(line => {
    doc.text(line, margin + 7, cy + 2);
    cy += lineH;
  });
  ctx.y += cardH + 4;
}

// ── Professional data table ──

export function drawTable(ctx: PDFContext, headers: string[], rows: string[][]): void {
  checkPage(ctx, 20);
  autoTable(ctx.doc, {
    startY: ctx.y,
    margin: { left: ctx.margin, right: ctx.margin },
    head: [headers],
    body: rows,
    theme: 'grid',
    styles: {
      fontSize: 7.5, cellPadding: 2.5,
      textColor: [...C.BODY_TEXT],
      lineColor: [...C.BORDER], lineWidth: 0.2,
    },
    headStyles: {
      fillColor: [...C.PRIMARY_BG], textColor: [...C.PRIMARY_D],
      fontStyle: 'bold', fontSize: 7.5, cellPadding: 3,
    },
    alternateRowStyles: { fillColor: [...C.ALT_ROW] },
    didDrawPage: () => {},
  });
  ctx.y = (ctx.doc as any).lastAutoTable.finalY + 6;
}

// ── Custom table with column overrides ──

export function drawCustomTable(
  ctx: PDFContext,
  headers: string[],
  rows: (string | number)[][],
  columnStyles: Record<number, any>,
  opts?: { fontSize?: number; cellPadding?: number },
): void {
  checkPage(ctx, 20);
  const fs = opts?.fontSize ?? 7;
  autoTable(ctx.doc, {
    startY: ctx.y,
    margin: { left: ctx.margin, right: ctx.margin },
    head: [headers],
    body: rows,
    theme: 'grid',
    styles: {
      fontSize: fs, cellPadding: opts?.cellPadding ?? 2,
      textColor: [...C.BODY_TEXT], lineColor: [...C.BORDER],
      lineWidth: 0.2, overflow: 'linebreak',
    },
    headStyles: {
      fillColor: [...C.PRIMARY_BG], textColor: [...C.PRIMARY_D],
      fontStyle: 'bold', fontSize: fs + 0.5, cellPadding: 3,
    },
    alternateRowStyles: { fillColor: [...C.ALT_ROW] },
    columnStyles,
  });
  ctx.y = (ctx.doc as any).lastAutoTable.finalY + 6;
}

// ── Cost comparison boxes ──

export function drawCostBoxes(
  ctx: PDFContext,
  items: { label: string; value: string; sublabel?: string; color: readonly [number, number, number]; bg: readonly [number, number, number] }[],
): void {
  const gap = 4;
  const boxW = (ctx.contentW - (items.length - 1) * gap) / items.length;
  const boxH = 28;
  checkPage(ctx, boxH + 4);
  const { doc, margin } = ctx;

  items.forEach((c, i) => {
    const bx = margin + i * (boxW + gap);

    // Card
    doc.setFillColor(c.bg[0], c.bg[1], c.bg[2]);
    doc.setDrawColor(...C.GRAY_XL);
    doc.roundedRect(bx, ctx.y, boxW, boxH, 2, 2, 'FD');

    // Label
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(7);
    doc.setTextColor(...C.GRAY);
    doc.text(c.label, bx + boxW / 2, ctx.y + 9, { align: 'center' });

    // Value
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(18);
    doc.setTextColor(c.color[0], c.color[1], c.color[2]);
    doc.text(c.value, bx + boxW / 2, ctx.y + 20, { align: 'center' });

    // Sublabel
    if (c.sublabel) {
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(6);
      doc.setTextColor(...C.GRAY_L);
      doc.text(c.sublabel, bx + boxW / 2, ctx.y + 25, { align: 'center' });
    }
  });
  ctx.y += boxH + 5;
}

// ── Horizontal divider ──

export function drawDivider(ctx: PDFContext): void {
  ctx.doc.setDrawColor(...C.GRAY_XL);
  ctx.doc.setLineWidth(0.3);
  ctx.doc.line(ctx.margin, ctx.y, ctx.margin + ctx.contentW, ctx.y);
  ctx.y += 4;
}

// ── Badge-style inline label ──

export function drawBadge(
  ctx: PDFContext,
  x: number,
  text: string,
  color: readonly [number, number, number],
  bg: readonly [number, number, number],
): number {
  const { doc } = ctx;
  doc.setFontSize(6);
  const tw = doc.getTextWidth(text) + 4;
  doc.setFillColor(bg[0], bg[1], bg[2]);
  doc.roundedRect(x, ctx.y - 2.5, tw, 5, 1, 1, 'F');
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(color[0], color[1], color[2]);
  doc.text(text, x + 2, ctx.y + 0.5);
  return x + tw + 2;
}
