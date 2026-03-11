/**
 * Validation Dashboard Page
 *
 * Lists validation runs with summary stats, status filtering, pagination,
 * and an inline creation form. Clicking a row navigates to the detail page.
 *
 * Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7, 13.8, 13.9, 13.10
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  listValidationRuns,
  createValidationRun,
  deleteValidationRun,
  ValidationRun,
  CreateValidationRunRequest,
} from '../services/validationApi';
import { listConnections, Connection } from '../services/api';
import { bqRedshiftApi } from '../services/bqRedshiftApi';
import './ValidationDashboardPage.css';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STATUS_OPTIONS = ['all', 'pending', 'running', 'completed', 'failed'] as const;
const PAGE_SIZE_OPTIONS = [10, 20, 50] as const;
const AUTO_REFRESH_MS = 10_000;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Format an ISO date string to a readable locale string */
function formatDate(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return '—';
  }
}

/** Format duration in seconds to "Xm Ys" or "Xs" */
function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return '—';
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const ValidationDashboardPage: React.FC = () => {
  const navigate = useNavigate();

  // --- Data state ---
  const [runs, setRuns] = useState<ValidationRun[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // --- Filters & pagination ---
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(20);

  // --- Create form ---
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState<CreateValidationRunRequest>({
    migration_id: 0,
    source_connection_id: 0,
    target_connection_id: 0,
  });
  const [tablesInput, setTablesInput] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // --- Dropdown data ---
  const [connections, setConnections] = useState<Connection[]>([]);
  const [migrations, setMigrations] = useState<{ id: number; migration_name: string }[]>([]);

  // --- Auto-refresh ---
  const refreshRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // --- Fetch dropdown data when form opens ---
  useEffect(() => {
    if (!showForm) return;
    listConnections()
      .then(setConnections)
      .catch(() => setConnections([]));
    bqRedshiftApi
      .listMigrations()
      .then((m) => setMigrations(m.map((x) => ({ id: x.id, migration_name: x.migration_name }))))
      .catch(() => setMigrations([]));
  }, [showForm]);

  // --- Fetch runs ---
  const fetchRuns = useCallback(async () => {
    try {
      const filterValue = statusFilter === 'all' ? undefined : statusFilter;
      const data = await listValidationRuns(page, pageSize, undefined, filterValue);
      setRuns(data.runs);
      setTotal(data.total);
      setError(null);
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'message' in err
          ? String((err as { message: unknown }).message)
          : 'Failed to load validation runs';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, statusFilter]);

  // Initial load + refetch on filter/page change
  useEffect(() => {
    setLoading(true);
    fetchRuns();
  }, [fetchRuns]);

  // Auto-refresh when any run is running or pending
  useEffect(() => {
    const hasActive = runs.some(
      (r) => r.status === 'running' || r.status === 'pending'
    );

    if (hasActive) {
      refreshRef.current = setInterval(fetchRuns, AUTO_REFRESH_MS);
    }

    return () => {
      if (refreshRef.current) {
        clearInterval(refreshRef.current);
        refreshRef.current = null;
      }
    };
  }, [runs, fetchRuns]);

  // --- Summary stats ---
  const totalRuns = total;
  const passedRuns = runs.filter((r) => r.status === 'completed').length;
  const failedRuns = runs.filter((r) => r.status === 'failed').length;
  const runningRuns = runs.filter(
    (r) => r.status === 'running' || r.status === 'pending'
  ).length;

  // --- Pagination ---
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  // --- Handlers ---
  const handleRowClick = (runId: number) => {
    navigate(`/validations/${runId}`);
  };

  const handleDelete = async (e: React.MouseEvent, runId: number) => {
    e.stopPropagation();
    if (!window.confirm('Delete this validation run? This cannot be undone.')) return;
    try {
      await deleteValidationRun(runId);
      fetchRuns();
    } catch {
      // Silently refresh — the run may already be gone
      fetchRuns();
    }
  };

  const handleCreate = async () => {
    if (creating) return;
    setCreating(true);
    setCreateError(null);

    const payload: CreateValidationRunRequest = {
      ...formData,
    };

    // Parse comma-separated tables
    const trimmed = tablesInput.trim();
    if (trimmed) {
      payload.tables = trimmed.split(',').map((t) => t.trim()).filter(Boolean);
    }

    try {
      await createValidationRun(payload);
      setShowForm(false);
      setFormData({ migration_id: 0, source_connection_id: 0, target_connection_id: 0 });
      setTablesInput('');
      fetchRuns();
    } catch (err: unknown) {
      let msg = 'Failed to create validation run';
      if (err && typeof err === 'object') {
        if ('detail' in err) {
          const detail = (err as { detail: unknown }).detail;
          msg = typeof detail === 'string' ? detail : JSON.stringify(detail);
        } else if ('message' in err) {
          msg = String((err as { message: unknown }).message);
        }
      }
      setCreateError(msg);
    } finally {
      setCreating(false);
    }
  };

  const canSubmit =
    formData.migration_id > 0 &&
    formData.source_connection_id > 0 &&
    formData.target_connection_id > 0;

  // --- Render ---
  return (
    <div className="validation-dashboard">
      {/* Header */}
      <div className="validation-header">
        <h1 className="validation-title">
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <path d="M9 11l2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx="11" cy="11" r="8" />
          </svg>
          Data Validation
        </h1>
        <p className="validation-subtitle">Post-migration data integrity verification</p>
      </div>

      {/* Stats */}
      <div className="validation-stats">
        <div className="validation-stat-card">
          <span className="validation-stat-count">{totalRuns}</span>
          <span className="validation-stat-label">Total Runs</span>
        </div>
        <div className="validation-stat-card">
          <span className="validation-stat-count passed">{passedRuns}</span>
          <span className="validation-stat-label">Passed</span>
        </div>
        <div className="validation-stat-card">
          <span className="validation-stat-count failed">{failedRuns}</span>
          <span className="validation-stat-label">Failed</span>
        </div>
        <div className="validation-stat-card">
          <span className="validation-stat-count running">{runningRuns}</span>
          <span className="validation-stat-label">Running</span>
        </div>
      </div>

      {/* Toolbar */}
      <div className="validation-toolbar">
        <div className="validation-toolbar-left">
          <button
            className="validation-new-btn"
            onClick={() => setShowForm((v) => !v)}
            type="button"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M7 1v12M1 7h12" strokeLinecap="round" />
            </svg>
            New Validation
          </button>

          <select
            className="validation-filter-select"
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            aria-label="Filter by status"
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s === 'all' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
              </option>
            ))}
          </select>
        </div>

        <div className="validation-toolbar-right">
          <div className="validation-pagination">
            <select
              className="validation-page-size-select"
              value={pageSize}
              onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
              aria-label="Page size"
            >
              {PAGE_SIZE_OPTIONS.map((s) => (
                <option key={s} value={s}>{s} / page</option>
              ))}
            </select>

            <button
              className="validation-page-btn"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              aria-label="Previous page"
              type="button"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M8 3L4 7l4 4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>

            <span className="validation-pagination-info">
              {page} / {totalPages}
            </span>

            <button
              className="validation-page-btn"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              aria-label="Next page"
              type="button"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M6 3l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* Create Form */}
      {showForm && (
        <div className="validation-create-form">
          <h3 className="validation-create-title">New Validation Run</h3>

          <div className="validation-form-grid">
            <div className="validation-form-field">
              <label className="validation-form-label" htmlFor="vf-migration-id">
                Migration *
              </label>
              <select
                id="vf-migration-id"
                className="validation-form-input"
                value={formData.migration_id || ''}
                onChange={(e) =>
                  setFormData((d) => ({ ...d, migration_id: Number(e.target.value) || 0 }))
                }
              >
                <option value="">Select a migration</option>
                {migrations.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.migration_name}
                  </option>
                ))}
              </select>
            </div>

            <div className="validation-form-field">
              <label className="validation-form-label" htmlFor="vf-source-conn">
                Source Connection *
              </label>
              <select
                id="vf-source-conn"
                className="validation-form-input"
                value={formData.source_connection_id || ''}
                onChange={(e) =>
                  setFormData((d) => ({ ...d, source_connection_id: Number(e.target.value) || 0 }))
                }
              >
                <option value="">Select source connection</option>
                {connections.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.type})
                  </option>
                ))}
              </select>
            </div>

            <div className="validation-form-field">
              <label className="validation-form-label" htmlFor="vf-target-conn">
                Target Connection *
              </label>
              <select
                id="vf-target-conn"
                className="validation-form-input"
                value={formData.target_connection_id || ''}
                onChange={(e) =>
                  setFormData((d) => ({ ...d, target_connection_id: Number(e.target.value) || 0 }))
                }
              >
                <option value="">Select target connection</option>
                {connections.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.type})
                  </option>
                ))}
              </select>
            </div>

            <div className="validation-form-field">
              <label className="validation-form-label" htmlFor="vf-tables">
                Tables (comma-separated)
              </label>
              <input
                id="vf-tables"
                className="validation-form-input"
                type="text"
                placeholder="e.g. users, orders"
                value={tablesInput}
                onChange={(e) => setTablesInput(e.target.value)}
              />
            </div>

            <div className="validation-form-field">
              <label className="validation-form-label" htmlFor="vf-batch-size">
                Batch Size
              </label>
              <input
                id="vf-batch-size"
                className="validation-form-input"
                type="number"
                min={100}
                max={100000}
                placeholder="10000"
                value={formData.batch_size ?? ''}
                onChange={(e) =>
                  setFormData((d) => ({
                    ...d,
                    batch_size: e.target.value ? Number(e.target.value) : undefined,
                  }))
                }
              />
            </div>

            <div className="validation-form-field">
              <label className="validation-form-label" htmlFor="vf-bedrock-model">
                Bedrock Model
              </label>
              <input
                id="vf-bedrock-model"
                className="validation-form-input"
                type="text"
                placeholder="Optional"
                value={formData.bedrock_model ?? ''}
                onChange={(e) =>
                  setFormData((d) => ({
                    ...d,
                    bedrock_model: e.target.value || undefined,
                  }))
                }
              />
            </div>
          </div>

          {createError && (
            <p className="validation-error-text" style={{ margin: 0 }}>
              {createError}
            </p>
          )}

          <div className="validation-form-actions">
            <button
              className="validation-form-submit"
              disabled={!canSubmit || creating}
              onClick={handleCreate}
              type="button"
            >
              {creating ? 'Creating…' : 'Create & Start'}
            </button>
            <button
              className="validation-form-cancel"
              onClick={() => { setShowForm(false); setCreateError(null); }}
              type="button"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Content */}
      {loading ? (
        <div className="validation-loading">
          <div className="validation-spinner" />
          Loading validation runs…
        </div>
      ) : error ? (
        <div className="validation-error">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 8v4M12 16h.01" strokeLinecap="round" />
          </svg>
          <p className="validation-error-text">{error}</p>
        </div>
      ) : runs.length === 0 ? (
        <div className="validation-empty">
          <svg className="validation-empty-icon" width="36" height="36" viewBox="0 0 36 36" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <rect x="6" y="6" width="24" height="24" rx="3" />
            <path d="M14 18h8M18 14v8" strokeLinecap="round" />
          </svg>
          <p className="validation-empty-text">
            No validation runs found. Click "New Validation" to get started.
          </p>
        </div>
      ) : (
        <div className="validation-table-wrapper">
          <table className="validation-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Status</th>
                <th>Progress</th>
                <th>Tables</th>
                <th>Started</th>
                <th>Duration</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id} onClick={() => handleRowClick(run.id)}>
                  <td>{run.id}</td>
                  <td>
                    <span className={`validation-status-badge ${run.status}`}>
                      {run.status}
                    </span>
                  </td>
                  <td>
                    {run.status === 'running' ? (
                      <div className="validation-progress-cell">
                        <div className="validation-progress-bar">
                          <div
                            className="validation-progress-fill"
                            style={{ width: `${run.progress_percentage}%` }}
                          />
                        </div>
                        <span className="validation-progress-text">
                          {run.progress_percentage}%
                        </span>
                      </div>
                    ) : run.status === 'completed' || run.status === 'failed' ? (
                      <span className="validation-progress-text">100%</span>
                    ) : (
                      <span className="validation-progress-text">—</span>
                    )}
                  </td>
                  <td>
                    <div className="validation-tables-cell">
                      <span className="passed-count">{run.tables_passed}p</span>
                      <span className="separator">/</span>
                      <span className="failed-count">{run.tables_failed}f</span>
                      <span className="separator">/</span>
                      <span className="error-count">{run.tables_error}e</span>
                    </div>
                  </td>
                  <td>{formatDate(run.started_at)}</td>
                  <td>{formatDuration(run.duration_seconds)}</td>
                  <td>
                    <button
                      className="validation-delete-btn"
                      onClick={(e) => handleDelete(e, run.id)}
                      aria-label={`Delete run ${run.id}`}
                      type="button"
                    >
                      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
                        <path d="M3 4h10M6 4V3a1 1 0 011-1h2a1 1 0 011 1v1M5 4v8a1 1 0 001 1h4a1 1 0 001-1V4" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
