/**
 * Shared utilities for Assessment Report Pages
 * 
 * Contains common components and helper functions used by both
 * BigQueryReportPage and SQLServerReportPage.
 */

import React from 'react';
import { Button } from '../components/ui';
import { Select } from '../components/ui/Select';

// Tab loading spinner
export const TabSpinner: React.FC<{ message?: string }> = ({ message }) => (
  <div style={{ padding: '40px', textAlign: 'center' }}>
    <div className="spinner" style={{ margin: '0 auto' }}></div>
    <p style={{ marginTop: '16px', color: 'var(--color-text-secondary)' }}>{message || 'Loading...'}</p>
  </div>
);

export const TabError: React.FC<{ message: string; onRetry?: () => void }> = ({ message, onRetry }) => (
  <div style={{ padding: '20px', textAlign: 'center' }}>
    <p style={{ color: 'var(--color-error)', marginBottom: '12px' }}>{message}</p>
    {onRetry && <Button variant="outline" onClick={onRetry}>Retry</Button>}
  </div>
);

// Helper functions
export const formatSize = (sizeMb: number) => {
  if (sizeMb < 1024) return `${sizeMb.toFixed(2)} MB`;
  const sizeGb = sizeMb / 1024;
  if (sizeGb < 1024) return `${sizeGb.toFixed(2)} GB`;
  return `${(sizeGb / 1024).toFixed(2)} TB`;
};

export const formatDate = (dateString: string | null) => {
  if (!dateString) return 'N/A';
  try { return new Date(dateString).toLocaleString(); } catch { return dateString; }
};

export const formatNumber = (num: number) => num.toLocaleString();

// Pagination component
export const PaginationControls: React.FC<{
  page: number; totalPages: number; total: number; pageSize: number;
  onPageChange: (p: number) => void; onPageSizeChange: (s: number) => void;
}> = ({ page, totalPages, total, pageSize, onPageChange, onPageSizeChange }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '16px', flexWrap: 'wrap', gap: '12px' }}>
    <div style={{ fontSize: '13px', color: 'var(--color-text-secondary)' }}>
      Showing {Math.min((page - 1) * pageSize + 1, total)}–{Math.min(page * pageSize, total)} of {total}
    </div>
    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
      <Select value={pageSize} onChange={(v) => onPageSizeChange(Number(v))} options={[{ value: 25, label: '25 / page' }, { value: 50, label: '50 / page' }, { value: 100, label: '100 / page' }]} />
      <button className="filter-btn" disabled={page <= 1} onClick={() => onPageChange(page - 1)} style={{ padding: '6px 16px', cursor: page <= 1 ? 'not-allowed' : 'pointer', opacity: page <= 1 ? 0.5 : 1 }}>← Prev</button>
      <span style={{ fontSize: '13px', color: 'var(--color-text-secondary)' }}>Page {page} of {totalPages}</span>
      <button className="filter-btn" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)} style={{ padding: '6px 16px', cursor: page >= totalPages ? 'not-allowed' : 'pointer', opacity: page >= totalPages ? 0.5 : 1 }}>Next →</button>
    </div>
  </div>
);
