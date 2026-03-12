/**
 * Validation Detail Page
 *
 * Displays a single validation run with per-table results, expandable detail
 * panels (DDL, row count, data match, AI analysis), download report, and
 * auto-refresh while the run is active.
 *
 * Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7, 14.8, 14.9, 14.10
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  getValidationReport,
  deleteValidationRun,
  ValidationReport,
  ValidationTableDetail,
} from '../services/validationApi';
import './ValidationDetailPage.css';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const AUTO_REFRESH_MS = 10_000;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return '—';
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

// ---------------------------------------------------------------------------
// Status Icon
// ---------------------------------------------------------------------------

function StatusIcon({ status }: { status: string | null }) {
  if (status === 'passed') {
    return (
      <svg className="status-icon passed" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" aria-label="Passed">
        <path d="M6 10l3 3 5-5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (status === 'failed') {
    return (
      <svg className="status-icon failed" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" aria-label="Failed">
        <path d="M6 6l8 8M14 6l-8 8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  if (status === 'error') {
    return (
      <svg className="status-icon error" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" aria-label="Error">
        <path d="M10 7v4M10 13h.01" strokeLinecap="round" />
        <path d="M8.57 3.81L2.2 15a1 1 0 00.87 1.5h12.72a1 1 0 00.87-1.5L10.3 3.81a1 1 0 00-1.73 0z" />
      </svg>
    );
  }
  return <span className="status-icon pending" aria-label="Pending">—</span>;
}

// ---------------------------------------------------------------------------
// Overall status for a table row
// ---------------------------------------------------------------------------

function overallTableStatus(t: ValidationTableDetail): string {
  if (t.status === 'error') return 'error';
  const steps = [t.ddl_status, t.row_count_status, t.data_match_status];
  if (steps.some((s) => s === 'failed')) return 'failed';
  if (steps.some((s) => s === 'error')) return 'error';
  if (steps.every((s) => s === 'passed')) return 'passed';
  return 'pending';
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const ValidationDetailPage: React.FC = () => {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();

  const [report, setReport] = useState<ValidationReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedTable, setExpandedTable] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const refreshRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // --- Fetch report ---
  const fetchReport = useCallback(async () => {
    if (!runId) return;
    try {
      const data = await getValidationReport(Number(runId));
      setReport(data);
      setError(null);
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'message' in err
          ? String((err as { message: unknown }).message)
          : 'Failed to load validation report';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [runId]);

  // Initial load
  useEffect(() => {
    setLoading(true);
    fetchReport();
  }, [fetchReport]);

  // Auto-refresh while running or pending
  useEffect(() => {
    const isActive =
      report?.overall_status === 'running' || report?.overall_status === 'pending';

    if (isActive) {
      refreshRef.current = setInterval(fetchReport, AUTO_REFRESH_MS);
    }

    return () => {
      if (refreshRef.current) {
        clearInterval(refreshRef.current);
        refreshRef.current = null;
      }
    };
  }, [report?.overall_status, fetchReport]);

  // --- Handlers ---
  const handleBack = () => navigate('/validations');

  const handleDelete = async () => {
    if (!runId) return;
    if (!window.confirm('Delete this validation run? This cannot be undone.')) return;
    setDeleting(true);
    try {
      await deleteValidationRun(Number(runId));
      navigate('/validations');
    } catch {
      setDeleting(false);
    }
  };

  const handleDownloadReport = () => {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `validation-report-${runId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const toggleExpand = (tableName: string) => {
    setExpandedTable((prev) => (prev === tableName ? null : tableName));
  };

  // --- Status badge class ---
  const statusClass = (s: string | null | undefined): string => {
    if (!s) return 'pending';
    if (s === 'completed' || s === 'passed') return 'completed';
    if (s === 'running') return 'running';
    if (s === 'failed') return 'failed';
    return 'pending';
  };

  // --- Render states ---
  if (loading) {
    return (
      <div className="validation-detail">
        <div className="validation-detail-loading">
          <div className="validation-detail-spinner" />
          Loading validation run…
        </div>
      </div>
    );
  }

  if (error && !report) {
    return (
      <div className="validation-detail">
        <div className="validation-detail-error">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 8v4M12 16h.01" strokeLinecap="round" />
          </svg>
          <p className="validation-detail-error-text">{error}</p>
          <button className="validation-detail-back-btn" onClick={handleBack} type="button" aria-label="Back to dashboard">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M10 3L5 8l5 5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="validation-detail">
        <div className="validation-detail-not-found">
          <p className="validation-detail-not-found-text">Validation run not found.</p>
          <button className="validation-detail-back-btn" onClick={handleBack} type="button" aria-label="Back to dashboard">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M10 3L5 8l5 5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>
      </div>
    );
  }

  const isActive = report.overall_status === 'running' || report.overall_status === 'pending';
  const progressPct =
    report.total_tables > 0
      ? Math.round(
          ((report.tables_passed + report.tables_failed + report.tables_error) /
            report.total_tables) *
            100
        )
      : 0;

  return (
    <div className="validation-detail">
      {/* Header */}
      <div className="validation-detail-header">
        <button
          className="validation-detail-back-btn"
          onClick={handleBack}
          type="button"
          aria-label="Back to validations"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M10 3L5 8l5 5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>

        <h1 className="validation-detail-title">Validation Run #{runId}</h1>

        <span className={`validation-status-badge ${statusClass(report.overall_status)}`}>
          {report.overall_status}
        </span>

        <div className="validation-detail-header-actions">
          <button
            className="validation-detail-download-btn"
            onClick={handleDownloadReport}
            type="button"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
              <path d="M8 2v8M5 7l3 3 3-3" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M2 12v1a1 1 0 001 1h10a1 1 0 001-1v-1" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Download Report
          </button>

          <button
            className="validation-detail-delete-btn"
            onClick={handleDelete}
            disabled={deleting}
            type="button"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
              <path d="M3 4h10M6 4V3a1 1 0 011-1h2a1 1 0 011 1v1M5 4v8a1 1 0 001 1h4a1 1 0 001-1V4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {deleting ? 'Deleting…' : 'Delete'}
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="validation-detail-summary">
        <div className="validation-detail-stat-card">
          <span className="validation-detail-stat-value">{report.total_tables}</span>
          <span className="validation-detail-stat-label">Total Tables</span>
        </div>
        <div className="validation-detail-stat-card">
          <span className="validation-detail-stat-value passed">{report.tables_passed}</span>
          <span className="validation-detail-stat-label">Passed</span>
        </div>
        <div className="validation-detail-stat-card">
          <span className="validation-detail-stat-value failed">{report.tables_failed}</span>
          <span className="validation-detail-stat-label">Failed</span>
        </div>
        <div className="validation-detail-stat-card">
          <span className="validation-detail-stat-value error">{report.tables_error}</span>
          <span className="validation-detail-stat-label">Errors</span>
        </div>
        <div className="validation-detail-stat-card">
          <span className="validation-detail-stat-value">{formatDuration(report.duration_seconds)}</span>
          <span className="validation-detail-stat-label">Duration</span>
        </div>
      </div>

      {/* Progress bar (visible when running) */}
      {isActive && (
        <div className="validation-detail-progress" role="progressbar" aria-valuenow={progressPct} aria-valuemin={0} aria-valuemax={100}>
          <span className="validation-detail-progress-label">Progress</span>
          <div className="validation-detail-progress-bar">
            <div className="validation-detail-progress-fill" style={{ width: `${progressPct}%` }} />
          </div>
          <span className="validation-detail-progress-pct">{progressPct}%</span>
        </div>
      )}

      {/* Table Results */}
      <div className="validation-detail-table">
        <table>
          <thead>
            <tr>
              <th>Table Name</th>
              <th>DDL</th>
              <th>Row Count</th>
              <th>Data Match</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {report.tables.map((t) => {
              const overall = overallTableStatus(t);
              const isExpanded = expandedTable === t.table_name;
              return (
                <React.Fragment key={t.table_name}>
                  <tr
                    className={`table-row${isExpanded ? ' expanded' : ''}`}
                    onClick={() => toggleExpand(t.table_name)}
                    role="button"
                    tabIndex={0}
                    aria-expanded={isExpanded}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        toggleExpand(t.table_name);
                      }
                    }}
                  >
                    <td>{t.table_name}</td>
                    <td><StatusIcon status={t.ddl_status} /></td>
                    <td><StatusIcon status={t.row_count_status} /></td>
                    <td><StatusIcon status={t.data_match_status} /></td>
                    <td><StatusIcon status={overall} /></td>
                  </tr>

                  {isExpanded && (
                    <tr className="validation-detail-expand">
                      <td colSpan={5}>
                        <ExpandedPanel table={t} />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
            {report.tables.length === 0 && (
              <tr>
                <td colSpan={5} style={{ textAlign: 'center', color: 'var(--color-text-disabled)' }}>
                  No table results available.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};


// ---------------------------------------------------------------------------
// Expanded Panel
// ---------------------------------------------------------------------------

interface ExpandedPanelProps {
  table: ValidationTableDetail;
}

function ExpandedPanel({ table }: ExpandedPanelProps) {
  return (
    <div className="validation-detail-expand-inner">
      <DDLSection result={table.ddl_comparison_result} />
      <RowCountSection result={table.row_count_result} />
      <DataMatchSection result={table.data_match_result} />
      {table.ai_analysis && <AIAnalysisSection analysis={table.ai_analysis} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// DDL Comparison Section
// ---------------------------------------------------------------------------

interface DDLSectionProps {
  result: Record<string, unknown> | null;
}

function DDLSection({ result }: DDLSectionProps) {
  const discrepancies = (result?.discrepancies ?? []) as Array<Record<string, unknown>>;
  const sourceCount = (result?.source_column_count ?? '—') as number | string;
  const targetCount = (result?.target_column_count ?? '—') as number | string;

  return (
    <div className="validation-detail-section">
      <div className="validation-detail-section-header">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
          <rect x="2" y="2" width="12" height="12" rx="2" />
          <path d="M5 6h6M5 8h4M5 10h5" strokeLinecap="round" />
        </svg>
        DDL Comparison
        <span style={{ marginLeft: 'auto', fontWeight: 400, fontSize: 'var(--font-size-xs)', color: 'var(--color-text-secondary)' }}>
          Source: {String(sourceCount)} cols · Target: {String(targetCount)} cols
        </span>
      </div>
      <div className="validation-detail-section-body">
        {discrepancies.length === 0 ? (
          <p className="validation-detail-no-data">No discrepancies found.</p>
        ) : (
          <table className="validation-detail-ddl-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Column</th>
                <th>Source Type</th>
                <th>Target Type</th>
                <th>Expected Type</th>
              </tr>
            </thead>
            <tbody>
              {discrepancies.map((d, i) => (
                <tr key={i}>
                  <td>
                    <span className={`validation-detail-discrepancy-type ${String(d.type ?? d.discrepancy_type ?? '')}`}>
                      {String(d.type ?? d.discrepancy_type ?? '—')}
                    </span>
                  </td>
                  <td>{String(d.column_name ?? '—')}</td>
                  <td>{String(d.source_type ?? '—')}</td>
                  <td>{String(d.target_type ?? '—')}</td>
                  <td>{String(d.expected_type ?? '—')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Row Count Section
// ---------------------------------------------------------------------------

interface RowCountSectionProps {
  result: Record<string, unknown> | null;
}

function RowCountSection({ result }: RowCountSectionProps) {
  if (!result) {
    return (
      <div className="validation-detail-section">
        <div className="validation-detail-section-header">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <path d="M2 4h12M2 8h12M2 12h12" strokeLinecap="round" />
          </svg>
          Row Count
        </div>
        <div className="validation-detail-section-body">
          <p className="validation-detail-no-data">No row count data available.</p>
        </div>
      </div>
    );
  }

  const sourceCount = result.source_count as number | undefined;
  const targetCount = result.target_count as number | undefined;
  const difference = result.difference as number | undefined;
  const pctDiff = result.percentage_difference as number | undefined;

  return (
    <div className="validation-detail-section">
      <div className="validation-detail-section-header">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
          <path d="M2 4h12M2 8h12M2 12h12" strokeLinecap="round" />
        </svg>
        Row Count
      </div>
      <div className="validation-detail-section-body">
        <div className="validation-detail-row-stats">
          <div className="validation-detail-row-stat">
            <span className="validation-detail-row-stat-label">Source Count</span>
            <span className="validation-detail-row-stat-value">
              {sourceCount !== undefined ? sourceCount.toLocaleString() : '—'}
            </span>
          </div>
          <div className="validation-detail-row-stat">
            <span className="validation-detail-row-stat-label">Target Count</span>
            <span className="validation-detail-row-stat-value">
              {targetCount !== undefined ? targetCount.toLocaleString() : '—'}
            </span>
          </div>
          <div className="validation-detail-row-stat">
            <span className="validation-detail-row-stat-label">Difference</span>
            <span className="validation-detail-row-stat-value">
              {difference !== undefined ? difference.toLocaleString() : '—'}
            </span>
          </div>
          <div className="validation-detail-row-stat">
            <span className="validation-detail-row-stat-label">% Difference</span>
            <span className="validation-detail-row-stat-value">
              {pctDiff !== undefined ? `${pctDiff.toFixed(4)}%` : '—'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Data Match Section
// ---------------------------------------------------------------------------

interface DataMatchSectionProps {
  result: Record<string, unknown> | null;
}

function DataMatchSection({ result }: DataMatchSectionProps) {
  if (!result) {
    return (
      <div className="validation-detail-section">
        <div className="validation-detail-section-header">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <circle cx="8" cy="8" r="6" />
            <path d="M5.5 8l2 2 3-3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Data Match
        </div>
        <div className="validation-detail-section-body">
          <p className="validation-detail-no-data">No data match results available.</p>
        </div>
      </div>
    );
  }

  const totalCompared = result.total_compared as number | undefined;
  const matchedCount = result.matched_count as number | undefined;
  const missingCount = result.missing_count as number | undefined;
  const extraCount = result.extra_count as number | undefined;
  const mismatchCount = result.mismatch_count as number | undefined;
  const sampleDiscrepancies = (result.sample_discrepancies ?? []) as Array<Record<string, unknown>>;

  return (
    <div className="validation-detail-section">
      <div className="validation-detail-section-header">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
          <circle cx="8" cy="8" r="6" />
          <path d="M5.5 8l2 2 3-3" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        Data Match
      </div>
      <div className="validation-detail-section-body">
        <div className="validation-detail-match-stats">
          <div className="validation-detail-match-stat">
            <span className="validation-detail-match-stat-label">Total Compared</span>
            <span className="validation-detail-match-stat-value">
              {totalCompared !== undefined ? totalCompared.toLocaleString() : '—'}
            </span>
          </div>
          <div className="validation-detail-match-stat">
            <span className="validation-detail-match-stat-label">Matched</span>
            <span className="validation-detail-match-stat-value">
              {matchedCount !== undefined ? matchedCount.toLocaleString() : '—'}
            </span>
          </div>
          <div className="validation-detail-match-stat">
            <span className="validation-detail-match-stat-label">Missing</span>
            <span className="validation-detail-match-stat-value">
              {missingCount !== undefined ? missingCount.toLocaleString() : '—'}
            </span>
          </div>
          <div className="validation-detail-match-stat">
            <span className="validation-detail-match-stat-label">Extra</span>
            <span className="validation-detail-match-stat-value">
              {extraCount !== undefined ? extraCount.toLocaleString() : '—'}
            </span>
          </div>
          <div className="validation-detail-match-stat">
            <span className="validation-detail-match-stat-label">Mismatched</span>
            <span className="validation-detail-match-stat-value">
              {mismatchCount !== undefined ? mismatchCount.toLocaleString() : '—'}
            </span>
          </div>
        </div>

        {sampleDiscrepancies.length > 0 && (
          <div className="validation-detail-sample-discrepancies">
            <table>
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Primary Key</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {sampleDiscrepancies.map((d, i) => {
                  const details = d.details as Record<string, unknown> | null;
                  return (
                    <tr key={i}>
                      <td>
                        <span className={`validation-detail-discrepancy-type ${String(d.type ?? '')}`}>
                          {String(d.type ?? '—')}
                        </span>
                      </td>
                      <td>{d.primary_key ? JSON.stringify(d.primary_key) : '—'}</td>
                      <td>
                        {details
                          ? `${String(details.column ?? '')}: ${String(details.source_value ?? '')} → ${String(details.target_value ?? '')}`
                          : '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AI Analysis Section
// ---------------------------------------------------------------------------

interface AIAnalysisSectionProps {
  analysis: Record<string, unknown>;
}

function AIAnalysisSection({ analysis }: AIAnalysisSectionProps) {
  const rootCause = analysis.root_cause as string | undefined;
  const impact = analysis.impact_assessment as string | undefined;
  const workarounds = (analysis.recommended_workarounds ?? []) as string[];

  return (
    <div className="validation-ai-section">
      <div className="validation-detail-section-header">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
          <circle cx="8" cy="8" r="6" />
          <path d="M6 6.5a2 2 0 013.5 1.5c0 1-1.5 1.5-1.5 1.5M8 12h.01" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        AI Analysis
      </div>
      <div className="validation-detail-section-body">
        {rootCause && (
          <div className="validation-ai-field">
            <span className="validation-ai-field-label">Root Cause</span>
            <span className="validation-ai-field-value">{rootCause}</span>
          </div>
        )}
        {impact && (
          <div className="validation-ai-field">
            <span className="validation-ai-field-label">Impact Assessment</span>
            <span className="validation-ai-field-value">{impact}</span>
          </div>
        )}
        {workarounds.length > 0 && (
          <div className="validation-ai-field">
            <span className="validation-ai-field-label">Recommended Workarounds</span>
            <ul className="validation-ai-workarounds">
              {workarounds.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        )}
        {!rootCause && !impact && workarounds.length === 0 && (
          <p className="validation-detail-no-data">No AI analysis data available.</p>
        )}
      </div>
    </div>
  );
}
