/**
 * Register Satoshi font with jsPDF
 */
import type { jsPDF } from 'jspdf';
import { SATOSHI_REGULAR } from './satoshiRegular';
import { SATOSHI_BOLD } from './satoshiBold';

export function registerSatoshiFont(doc: jsPDF): void {
  doc.addFileToVFS('Satoshi-Regular.ttf', SATOSHI_REGULAR);
  doc.addFont('Satoshi-Regular.ttf', 'Satoshi', 'normal');

  doc.addFileToVFS('Satoshi-Bold.ttf', SATOSHI_BOLD);
  doc.addFont('Satoshi-Bold.ttf', 'Satoshi', 'bold');

  // Set as default
  doc.setFont('Satoshi', 'normal');
}
