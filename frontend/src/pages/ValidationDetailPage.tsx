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
// Status Badge (text-based replacement for SVG StatusIcon)
// ---------------------------------------------------------------------------


// ---------------------------------------------------------------------------
// Status Badge (text-based replacement for SVG StatusIcon)
// ---------------------------------------------------------------------------

function StatusBadge({
  status,
}: {
  status?: string | null;
}) {
  const label =
    status === 'passed'
      ? 'Passed'
      : status === 'failed'
      ? 'Failed'
      : status === 'error'
      ? 'Error'
      : status === 'skipped'
      ? 'Skipped'
      : 'Pending';

  return (
    <span className={`vd-status-badge ${status || 'pending'}`}>
      {label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Overall status for a table row
// ---------------------------------------------------------------------------

function overallTableStatus(t: ValidationTableDetail): string {
  if (t.status === 'error') {
    return 'error';
  }

  const steps = [
    t.ddl_status,
    t.row_count_status,
    t.data_match_status,
    t.null_status,
    t.duplicate_status,
    t.sum_status,
    t.average_status,
    t.specific_row_status,
  ].filter(
    (status) =>
      status !== null &&
      status !== undefined &&
      status !== 'skipped'
  );

  if (steps.some((status) => status === 'error')) {
    return 'error';
  }

  if (steps.some((status) => status === 'failed')) {
    return 'failed';
  }

  if (steps.length > 0 && steps.every((status) => status === 'passed')) {
    return 'passed';
  }

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

  const rows: string[][] = [];

  const escapeCsv = (value: unknown) => {
    const text = String(value ?? '');
    return `"${text.replace(/"/g, '""')}"`;
  };

  const addRow = (
    tableName: string,
    check: string,
    status: string | null | undefined,
    details: string
  ) => {
    rows.push([
      tableName,
      check,
      status || 'Skipped',
      details,
    ]);
  };

  report.tables.forEach((table) => {
    addRow(
      table.table_name,
      'Row Count',
      table.row_count_status,
      JSON.stringify(table.row_count_result || {})
    );

    addRow(
      table.table_name,
      'NULL',
      table.null_status,
      JSON.stringify(table.null_result || {})
    );

    addRow(
      table.table_name,
      'Schema',
      table.ddl_status,
      JSON.stringify(table.ddl_comparison_result || {})
    );

    addRow(
      table.table_name,
      'Duplicate',
      table.duplicate_status,
      JSON.stringify(table.duplicate_result || {})
    );

    addRow(
      table.table_name,
      'SUM',
      table.sum_status,
      JSON.stringify(table.sum_result || {})
    );

    addRow(
      table.table_name,
      'AVERAGE',
      table.average_status,
      JSON.stringify(table.average_result || {})
    );

    addRow(
      table.table_name,
      'Specific Row',
      table.specific_row_status,
      JSON.stringify(table.specific_row_result || {})
    );
  });

  const csvRows = [
    [
      'Table Name',
      'Validation Check',
      'Status',
      'Details',
    ],
    ...rows,
  ];

  const csvContent = csvRows
    .map((row) => row.map(escapeCsv).join(','))
    .join('\n');

  const blob = new Blob(
    [csvContent],
    { type: 'text/csv;charset=utf-8;' }
  );

  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');

  a.href = url;
  a.download = `validation-report-${runId}.csv`;

  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);

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
    if (s === 'error') return 'error';
    if (s === 'skipped') return 'skipped';
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

        <h1 className="validation-detail-title">{report.run_name || `Validation Run #${runId}`}</h1>

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
          <span className="validation-detail-stat-label">Tables</span>
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

<td>
  <StatusBadge status={t.ddl_status} />
</td>

<td>
  <StatusBadge status={t.row_count_status} />
</td>

<td>
  <StatusBadge status={t.data_match_status} />
</td>

<td>
  <StatusBadge status={overall} />
</td>
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
function ValidationChecksSection({
  table,
}: {
  table: ValidationTableDetail;
}) {
  const checks = [
    {
      label: 'Row Count',
      status: table.row_count_status,
    },
    {
      label: 'NULL',
      status: table.null_status,
    },
    {
      label: 'Schema',
      status: table.ddl_status,
    },
    {
      label: 'Duplicate',
      status: table.duplicate_status,
    },
    {
      label: 'SUM',
      status: table.sum_status,
    },
    {
      label: 'AVERAGE',
      status: table.average_status,
    },
    {
      label: 'Specific Row',
      status: table.specific_row_status,
    },
  ];

  return (
    <div className="validation-checks-section">
      <div className="validation-checks-section-header">
        <h3>Validation Checks</h3>
        <span>
          {checks.filter(
  (check) =>
    check.status &&
    check.status !== 'skipped'
).length}{' '}
checks executed
        </span>
      </div>

      <div className="validation-checks-grid">
        {checks.map((check) => (
          <div
            key={check.label}
            className="validation-check-item"
          >
            <span className="validation-check-name">
              {check.label}
            </span>

            <StatusBadge
              status={check.status}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
function SpecificRowValidationSection({
  result,
}: {
  result?: Record<string, any> | null;
}) {
  if (!result || Object.keys(result).length === 0) {
    return null;
  }

  const discrepancies = Array.isArray(
    result.sample_discrepancies
  )
    ? result.sample_discrepancies
    : [];

  const formatPrimaryKey = (
    primaryKey: Record<string, any> | null | undefined
  ) => {
    if (!primaryKey) {
      return '—';
    }

    return Object.entries(primaryKey)
      .map(([key, value]) => `${key}=${value}`)
      .join(', ');
  };

  return (
    <div className="validation-result-section">
      <div className="validation-result-section-header">
        <div>
          <h3>Specific Row Details</h3>
          <span>
            Record-level comparison details
          </span>
        </div>
      </div>

      <div className="validation-result-summary">
        <div className="validation-result-metric">
          <span>Total Compared</span>
          <strong>
            {result.total_compared ?? 0}
          </strong>
        </div>

        <div className="validation-result-metric">
          <span>Matched</span>
          <strong>
            {result.matched_count ?? 0}
          </strong>
        </div>

        <div className="validation-result-metric">
          <span>Missing</span>
          <strong>
            {result.missing_count ?? 0}
          </strong>
        </div>

        <div className="validation-result-metric">
          <span>Extra</span>
          <strong>
            {result.extra_count ?? 0}
          </strong>
        </div>

        <div className="validation-result-metric">
          <span>Mismatched</span>
          <strong>
            {result.mismatch_count ?? 0}
          </strong>
        </div>
      </div>

      {discrepancies.length > 0 && (
        <div className="validation-discrepancies">
          <h4>Discrepancies</h4>

          {discrepancies.map(
            (
              discrepancy: any,
              index: number
            ) => {
              const type =
                discrepancy?.type;

              const primaryKey =
                formatPrimaryKey(
                  discrepancy?.primary_key
                );

              if (
                type ===
                'missing_in_target'
              ) {
                return (
                  <div
                    key={index}
                    className="validation-discrepancy-item"
                  >
                    <div className="validation-discrepancy-title">
                      Missing in Target
                    </div>

                    <div className="validation-discrepancy-detail">
                      <strong>
                        Primary Key:
                      </strong>{' '}
                      {primaryKey}
                    </div>
                  </div>
                );
              }

              if (
                type ===
                'extra_in_target'
              ) {
                return (
                  <div
                    key={index}
                    className="validation-discrepancy-item"
                  >
                    <div className="validation-discrepancy-title">
                      Extra in Target
                    </div>

                    <div className="validation-discrepancy-detail">
                      <strong>
                        Primary Key:
                      </strong>{' '}
                      {primaryKey}
                    </div>
                  </div>
                );
              }

              if (
                type ===
                'value_mismatch'
              ) {
                const details =
                  discrepancy?.details ||
                  {};

                return (
                  <div
                    key={index}
                    className="validation-discrepancy-item"
                  >
                    <div className="validation-discrepancy-title">
                      Value Mismatch
                    </div>

                    <div className="validation-discrepancy-detail">
                      <strong>
                        Primary Key:
                      </strong>{' '}
                      {primaryKey}
                    </div>

                    <div className="validation-discrepancy-detail">
                      <strong>
                        Column:
                      </strong>{' '}
                      {details.column ||
                        '—'}
                    </div>

                    <div className="validation-discrepancy-values">
                      <div>
                        <span>
                          Source
                        </span>
                        <code>
                          {details.source_value ??
                            'NULL'}
                        </code>
                      </div>

                      <div>
                        <span>
                          Target
                        </span>
                        <code>
                          {details.target_value ??
                            'NULL'}
                        </code>
                      </div>
                    </div>
                  </div>
                );
              }

              return null;
            }
          )}
        </div>
      )}

      {discrepancies.length === 0 &&
        (result.missing_count > 0 ||
          result.extra_count > 0 ||
          result.mismatch_count > 0) && (
          <div className="validation-discrepancy-empty">
            Discrepancy counts are available,
            but no sample records were returned.
          </div>
        )}
    </div>
  );
}
function NullValidationSection({
  result,
}: {
  result?: Record<string, any> | null;
}) {
  if (!result || Object.keys(result).length === 0) {
    return null;
  }

  return (
    <div className="validation-result-section">
      <div className="validation-result-section-header">
        <div>
          <h3>NULL Validation Details</h3>
          <span>NULL count comparison</span>
        </div>
      </div>

      <div className="validation-result-summary">
        <div className="validation-result-metric">
          <span>Column</span>
          <strong>{result.column || '—'}</strong>
        </div>

        <div className="validation-result-metric">
          <span>Source NULLs</span>
          <strong>{result.source_null_count ?? 0}</strong>
        </div>

        <div className="validation-result-metric">
          <span>Target NULLs</span>
          <strong>{result.target_null_count ?? 0}</strong>
        </div>

        <div className="validation-result-metric">
          <span>Difference</span>
          <strong>{result.difference ?? 0}</strong>
        </div>
      </div>
    </div>
  );
}


function DuplicateValidationSection({
  result,
}: {
  result?: Record<string, any> | null;
}) {
  if (!result || Object.keys(result).length === 0) {
    return null;
  }

  return (
    <div className="validation-result-section">
      <div className="validation-result-section-header">
        <div>
          <h3>Duplicate Validation Details</h3>
          <span>Duplicate group comparison</span>
        </div>
      </div>

      <div className="validation-result-summary">
        <div className="validation-result-metric">
          <span>Match Key</span>
          <strong>{result.match_key || '—'}</strong>
        </div>

        <div className="validation-result-metric">
          <span>Source Duplicates</span>
          <strong>
            {result.source_duplicate_count ?? 0}
          </strong>
        </div>

        <div className="validation-result-metric">
          <span>Target Duplicates</span>
          <strong>
            {result.target_duplicate_count ?? 0}
          </strong>
        </div>

        <div className="validation-result-metric">
          <span>Difference</span>
          <strong>{result.difference ?? 0}</strong>
        </div>
      </div>
    </div>
  );
}


function AggregateValidationSection({
  result,
  title,
}: {
  result?: Record<string, any> | null;
  title: 'SUM' | 'AVERAGE';
}) {
  if (!result || Object.keys(result).length === 0) {
    return null;
  }

  return (
    <div className="validation-result-section">
      <div className="validation-result-section-header">
        <div>
          <h3>{title} Validation Details</h3>
          <span>
            Source and target aggregate comparison
          </span>
        </div>
      </div>

      <div className="validation-result-summary">
        <div className="validation-result-metric">
          <span>Column</span>
          <strong>{result.column || '—'}</strong>
        </div>

        <div className="validation-result-metric">
          <span>Source Value</span>
          <strong>
            {result.source_value ?? 0}
          </strong>
        </div>

        <div className="validation-result-metric">
          <span>Target Value</span>
          <strong>
            {result.target_value ?? 0}
          </strong>
        </div>

        <div className="validation-result-metric">
          <span>Difference</span>
          <strong>{result.difference ?? 0}</strong>
        </div>
      </div>
    </div>
  );
}
// ---------------------------------------------------------------------------
// Expanded Panel
// ---------------------------------------------------------------------------

interface ExpandedPanelProps {
  table: ValidationTableDetail;
}

function ExpandedPanel({ table }: ExpandedPanelProps) {
  return (
    <div className="validation-detail-expand-inner">

      {/* Validation status overview */}
      <ValidationChecksSection
        table={table}
      />

      {/* Schema / DDL */}
      <DDLSection
        result={table.ddl_comparison_result}
      />

      {/* Row Count */}
      <RowCountSection
        result={table.row_count_result}
      />

      {/* Data Match */}
      <DataMatchSection
        result={table.data_match_result}
      />

      {/* NULL */}
      <NullValidationSection
        result={table.null_result}
      />

      {/* Duplicate */}
      <DuplicateValidationSection
        result={table.duplicate_result}
      />

      {/* SUM */}
      <AggregateValidationSection
        title="SUM"
        result={table.sum_result}
      />

      {/* AVERAGE */}
      <AggregateValidationSection
        title="AVERAGE"
        result={table.average_result}
      />

      {/* Specific Row */}
      <SpecificRowValidationSection
        result={table.specific_row_result}
      />

      {/* AI Analysis */}
      {table.ai_analysis && (
        <AIAnalysisSection
          analysis={table.ai_analysis}
        />
      )}

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
  if (!result || Object.keys(result).length === 0) {
    return null;
  }

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
  if (!result || Object.keys(result).length === 0) {
    return null;
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
  if (!result || Object.keys(result).length === 0) {
    return null;
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
