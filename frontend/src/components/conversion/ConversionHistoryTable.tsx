/**
 * ConversionHistoryTable
 *
 * Displays a list of past quick conversions for the current workspace.
 * Clicking a row invokes onSelectJob so the parent can load the result
 * into the side-by-side code panes.
 *
 * Enhanced with:
 * - "Manage History" button that toggles selection mode
 * - Checkboxes on each row when in selection mode
 * - "Delete Selected" button enabled only when ≥1 job selected
 * - Confirmation dialog before bulk deletion showing count
 * - Calls bulkDeleteJobs API, removes deleted jobs, exits selection mode
 * - "View Logs" action per job row that opens ConversionLogsPanel
 * - Displays asset_name column
 * - Displays "Query" label for QUERY and SCHEDULED_QUERY asset types
 *
 * Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.5, 5.5, 9.6, 10.6
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Badge } from '../ui';
import {
  listJobs,
  bulkDeleteJobs,
  ConversionJob,
  PaginatedJobsResponse,
} from '../../services/conversionApi';
import { ConversionLogsPanel } from './ConversionLogsPanel';
import './ConversionHistoryTable.css';

export interface ConversionHistoryTableProps {
  /** Called when a row is clicked; parent should load the job into the panes */
  onSelectJob: (job: ConversionJob) => void;
  /** ID of the currently selected/loaded job (highlights the row) */
  selectedJobId?: number | null;
  /** Incremented by the parent after a new conversion completes to trigger refresh */
  refreshToken?: number;
}

const PAGE_SIZE = 10;

/** Map a job status string to a Badge variant */
const statusVariant = (
  status: string
): 'success' | 'error' | 'warning' | 'info' | 'default' => {
  switch (status) {
    case 'completed':
      return 'success';
    case 'failed':
      return 'error';
    case 'in_progress':
      return 'info';
    case 'pending':
      return 'warning';
    default:
      return 'default';
  }
};

/** Format an ISO date string to IST locale representation */
const formatDate = (iso: string): string => {
  try {
    // Ensure UTC interpretation: append 'Z' if no timezone indicator present
    const utcIso = iso.endsWith('Z') || iso.includes('+') || iso.includes('-', 10) ? iso : iso + 'Z';
    const d = new Date(utcIso);
    return d.toLocaleString('en-IN', {
      timeZone: 'Asia/Kolkata',
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    });
  } catch {
    return iso;
  }
};

/** Display label for asset type — "Query" for both QUERY and SCHEDULED_QUERY */
const assetTypeLabel = (assetType: string): string => {
  if (assetType === 'QUERY' || assetType === 'SCHEDULED_QUERY') {
    return 'Query';
  }
  return assetType;
};

export const ConversionHistoryTable: React.FC<ConversionHistoryTableProps> = ({
  onSelectJob,
  selectedJobId,
  refreshToken = 0,
}) => {
  const [jobs, setJobs] = useState<ConversionJob[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Selection mode state
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  // Confirmation dialog state
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Logs panel state
  const [logsJobId, setLogsJobId] = useState<number | null>(null);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const fetchHistory = useCallback(async (p: number) => {
    try {
      setLoading(true);
      setError(null);
      const data: PaginatedJobsResponse = await listJobs(p, PAGE_SIZE, undefined, undefined, undefined, true);
      setJobs(data.jobs);
      setTotal(data.total);
    } catch (err: any) {
      const msg =
        err?.detail || err?.message || 'Failed to load conversion history.';
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHistory(page);
  }, [page, refreshToken, fetchHistory]);

  useEffect(() => {
    if (refreshToken > 0) {
      setPage(1);
    }
  }, [refreshToken]);

  const handleRowClick = (job: ConversionJob) => {
    if (!selectionMode) {
      onSelectJob(job);
    }
  };

  const handleRowKeyDown = (e: React.KeyboardEvent, job: ConversionJob) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      if (!selectionMode) {
        onSelectJob(job);
      }
    }
  };

  const toggleSelectionMode = () => {
    if (selectionMode) {
      // Exit selection mode — clear selections
      setSelectedIds(new Set());
    }
    setSelectionMode((prev) => !prev);
  };

  const toggleJobSelection = (jobId: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(jobId)) {
        next.delete(jobId);
      } else {
        next.add(jobId);
      }
      return next;
    });
  };

  const handleDeleteSelected = () => {
    if (selectedIds.size === 0) return;
    setShowConfirmDialog(true);
  };

  const confirmBulkDelete = async () => {
    try {
      setDeleting(true);
      await bulkDeleteJobs(Array.from(selectedIds));
      // Remove deleted jobs from displayed list
      const remaining = jobs.filter((j) => !selectedIds.has(j.id));
      const newTotal = Math.max(0, total - selectedIds.size);
      setJobs(remaining);
      setTotal(newTotal);
      // Exit selection mode
      setSelectedIds(new Set());
      setSelectionMode(false);
      // If current page is now empty and we're past page 1, go back
      if (remaining.length === 0 && page > 1) {
        setPage((p) => Math.max(1, p - 1));
      }
    } catch (err: any) {
      // Keep selection mode active on error
    } finally {
      setDeleting(false);
      setShowConfirmDialog(false);
    }
  };

  const cancelBulkDelete = () => {
    setShowConfirmDialog(false);
  };

  const openLogs = (jobId: number) => {
    setLogsJobId(jobId);
  };

  const closeLogs = () => {
    setLogsJobId(null);
  };

  return (
    <div className="conversion-history">
      {/* Header */}
      <div className="conversion-history__header">
        <h2 className="conversion-history__title">
          <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            aria-hidden="true"
          >
            <circle cx="8" cy="8" r="6" />
            <path d="M8 5v3l2 2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Conversion History
          {total > 0 && (
            <span className="conversion-history__count">({total})</span>
          )}
        </h2>
        <div className="conversion-history__actions">
          {selectionMode && (
            <button
              className="conversion-history__delete-btn"
              onClick={handleDeleteSelected}
              disabled={selectedIds.size === 0}
              type="button"
            >
              Delete Selected
            </button>
          )}
          <button
            className="conversion-history__manage-btn"
            onClick={toggleSelectionMode}
            type="button"
          >
            {selectionMode ? 'Cancel' : 'Manage History'}
          </button>
          <button
            className="conversion-history__refresh-btn"
            onClick={() => fetchHistory(page)}
            type="button"
            aria-label="Refresh conversion history"
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 16 16"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              aria-hidden="true"
            >
              <path
                d="M2 8a6 6 0 0 1 10.3-4.2M14 2v4h-4M14 8a6 6 0 0 1-10.3 4.2M2 14v-4h4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            Refresh
          </button>
        </div>
      </div>

      {/* Confirmation Dialog */}
      {showConfirmDialog && (
        <div className="conversion-history__confirm-overlay" role="dialog" aria-label="Confirm deletion">
          <div className="conversion-history__confirm-dialog">
            <p>Are you sure you want to delete {selectedIds.size} selected job{selectedIds.size !== 1 ? 's' : ''}?</p>
            <div className="conversion-history__confirm-actions">
              <button onClick={cancelBulkDelete} type="button" disabled={deleting}>
                Cancel
              </button>
              <button onClick={confirmBulkDelete} type="button" disabled={deleting} className="conversion-history__confirm-delete-btn">
                {deleting ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Loading */}
      {loading && jobs.length === 0 && (
        <div className="conversion-history__loading">Loading history…</div>
      )}

      {/* Error */}
      {error && (
        <div className="conversion-history__error">{error}</div>
      )}

      {/* Empty state */}
      {!loading && !error && jobs.length === 0 && (
        <div className="conversion-history__empty">
          No quick conversions yet. Run a conversion above to get started.
        </div>
      )}

      {/* Table */}
      {jobs.length > 0 && (
        <>
          <table className="conversion-history__table" role="grid" aria-label="Conversion history">
            <thead>
              <tr>
                {selectionMode && <th scope="col" className="conversion-history__checkbox-col"></th>}
                <th scope="col">Asset Name</th>
                <th scope="col">Asset Type</th>
                <th scope="col">Conversion</th>
                <th scope="col">Status</th>
                <th scope="col">Date</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr
                  key={job.id}
                  className={
                    selectedJobId === job.id
                      ? 'conversion-history__row--selected'
                      : ''
                  }
                  onClick={() => handleRowClick(job)}
                  onKeyDown={(e) => handleRowKeyDown(e, job)}
                  tabIndex={0}
                  role="row"
                  aria-selected={selectedJobId === job.id}
                >
                  {selectionMode && (
                    <td className="conversion-history__checkbox-col">
                      <input
                        type="checkbox"
                        checked={selectedIds.has(job.id)}
                        onChange={() => toggleJobSelection(job.id)}
                        onClick={(e) => e.stopPropagation()}
                        aria-label={`Select job ${job.id}`}
                      />
                    </td>
                  )}
                  <td>
                    {job.asset_name ? (
                      <span className="conversion-history__asset-name">
                        {job.asset_name}
                      </span>
                    ) : (
                      <span className="conversion-history__asset-name conversion-history__asset-name--empty">
                        Untitled
                      </span>
                    )}
                  </td>
                  <td>
                    <span className="conversion-history__asset-type">
                      {assetTypeLabel(job.asset_type)}
                    </span>
                  </td>
                  <td>
                    <span className="conversion-history__dialect">
                      {job.source_dialect}
                      <svg
                        className="conversion-history__dialect-arrow"
                        width="14"
                        height="14"
                        viewBox="0 0 16 16"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        aria-hidden="true"
                      >
                        <path
                          d="M3 8h10m0 0l-3-3m3 3l-3 3"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                      {job.target_dialect}
                    </span>
                  </td>
                  <td>
                    <Badge variant={statusVariant(job.status)} size="sm">
                      {job.status}
                    </Badge>
                  </td>
                  <td>
                    <span className="conversion-history__date">
                      {formatDate(job.created_at)}
                    </span>
                  </td>
                  <td>
                    <button
                      className="conversion-history__view-logs-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        openLogs(job.id);
                      }}
                      type="button"
                    >
                      View Logs
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="conversion-history__pagination">
              <span>
                Page {page} of {totalPages}
              </span>
              <div className="conversion-history__page-controls">
                <button
                  className="conversion-history__page-btn"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  type="button"
                  aria-label="Previous page"
                >
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 16 16"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    aria-hidden="true"
                  >
                    <path
                      d="M10 4l-4 4 4 4"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </button>
                <button
                  className="conversion-history__page-btn"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  type="button"
                  aria-label="Next page"
                >
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 16 16"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    aria-hidden="true"
                  >
                    <path
                      d="M6 4l4 4-4 4"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Conversion Logs Panel */}
      {logsJobId !== null && (
        <ConversionLogsPanel
          jobId={logsJobId}
          isOpen={true}
          onClose={closeLogs}
        />
      )}
    </div>
  );
};
