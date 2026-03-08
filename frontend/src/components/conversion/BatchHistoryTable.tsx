/**
 * BatchHistoryTable
 *
 * Displays a list of past batch conversions for the current workspace.
 * Fetches batch history from the API on mount. Supports:
 * - "Manage History" button that toggles selection mode with checkboxes
 * - "Delete Selected" with confirmation dialog, calls deleteBatch API
 * - Asset names displayed in expandable job detail views
 * - "View Logs" action per job row — opens ConversionLogsPanel
 * - "Query" label for QUERY and SCHEDULED_QUERY asset types
 * - Error state with retry option if batch fetch fails
 *
 * Requirements: 2.6, 5.6, 9.5, 13.2, 13.3, 13.4, 13.5
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Badge } from '../ui';
import {
  listBatches,
  deleteBatch,
  listBatchJobs,
  ConversionBatch,
  ConversionJob,
} from '../../services/conversionApi';
import { ConversionLogsPanel } from './ConversionLogsPanel';
import './BatchHistoryTable.css';

export interface BatchHistoryTableProps {
  /** Optional: called when a row is clicked */
  onSelectBatch?: (batch: ConversionBatch) => void;
  /** ID of the currently selected batch (highlights the row) */
  selectedBatchId?: number | null;
  /** Incremented by the parent after a new batch completes to trigger refresh */
  refreshToken?: number;
}

const PAGE_SIZE = 10;

/** Map a batch status string to a Badge variant */
const statusVariant = (
  status: string
): 'success' | 'error' | 'warning' | 'info' | 'default' => {
  switch (status) {
    case 'completed':
      return 'success';
    case 'completed_with_errors':
      return 'warning';
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

export const BatchHistoryTable: React.FC<BatchHistoryTableProps> = ({
  onSelectBatch,
  selectedBatchId,
  refreshToken = 0,
}) => {
  const [batches, setBatches] = useState<ConversionBatch[]>([]);
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

  // Expanded batch job details
  const [expandedBatchId, setExpandedBatchId] = useState<number | null>(null);
  const [batchJobs, setBatchJobs] = useState<ConversionJob[]>([]);
  const [jobsLoading, setJobsLoading] = useState(false);

  // Logs panel state
  const [logsJobId, setLogsJobId] = useState<number | null>(null);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const fetchHistory = useCallback(async (p: number) => {
    try {
      setLoading(true);
      setError(null);
      const data = await listBatches(p, PAGE_SIZE);
      setBatches(data.batches);
      setTotal(data.total);
    } catch (err: any) {
      const msg =
        err?.detail || err?.message || 'Failed to load batch history.';
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

  const handleRowClick = (batch: ConversionBatch) => {
    if (selectionMode) return;
    onSelectBatch?.(batch);
    // Toggle expanded job details
    if (expandedBatchId === batch.id) {
      setExpandedBatchId(null);
      setBatchJobs([]);
    } else {
      setExpandedBatchId(batch.id);
      fetchBatchJobs(batch.id);
    }
  };

  const handleRowKeyDown = (e: React.KeyboardEvent, batch: ConversionBatch) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleRowClick(batch);
    }
  };

  const fetchBatchJobs = async (batchId: number) => {
    try {
      setJobsLoading(true);
      const jobs = await listBatchJobs(batchId);
      setBatchJobs(jobs);
    } catch {
      setBatchJobs([]);
    } finally {
      setJobsLoading(false);
    }
  };

  const toggleSelectionMode = () => {
    if (selectionMode) {
      setSelectedIds(new Set());
    }
    setSelectionMode((prev) => !prev);
  };

  const toggleBatchSelection = (batchId: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(batchId)) {
        next.delete(batchId);
      } else {
        next.add(batchId);
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
      const ids = Array.from(selectedIds);
      await Promise.all(ids.map((id) => deleteBatch(id)));
      // Remove deleted batches from displayed list
      const remaining = batches.filter((b) => !selectedIds.has(b.id));
      const newTotal = Math.max(0, total - selectedIds.size);
      setBatches(remaining);
      setTotal(newTotal);
      // Exit selection mode
      setSelectedIds(new Set());
      setSelectionMode(false);
      // Collapse expanded if it was deleted
      if (expandedBatchId && selectedIds.has(expandedBatchId)) {
        setExpandedBatchId(null);
        setBatchJobs([]);
      }
      // If current page is now empty and we're past page 1, go back
      if (remaining.length === 0 && page > 1) {
        setPage((p) => Math.max(1, p - 1));
      }
    } catch {
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
    <div className="batch-history">
      {/* Header */}
      <div className="batch-history__header">
        <h2 className="batch-history__title">
          <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            aria-hidden="true"
          >
            <rect x="2" y="2" width="5" height="5" rx="1" />
            <rect x="9" y="2" width="5" height="5" rx="1" />
            <rect x="2" y="9" width="5" height="5" rx="1" />
            <rect x="9" y="9" width="5" height="5" rx="1" />
          </svg>
          Batch History
          {total > 0 && (
            <span className="batch-history__count">({total})</span>
          )}
        </h2>
        <div className="batch-history__actions" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {selectionMode && (
            <button
              className="batch-history__delete-btn"
              onClick={handleDeleteSelected}
              disabled={selectedIds.size === 0}
              type="button"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '6px 14px',
                fontSize: '12px',
                fontWeight: 500,
                color: '#DC2626',
                background: '#fff',
                border: '1px solid #DC2626',
                borderRadius: '6px',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              Delete Selected
            </button>
          )}
          <button
            className="batch-history__manage-btn"
            onClick={toggleSelectionMode}
            type="button"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '6px 14px',
              fontSize: '12px',
              fontWeight: 500,
              color: '#1F2937',
              background: '#fff',
              border: '1px solid #E5E7EB',
              borderRadius: '6px',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            {selectionMode ? 'Cancel' : 'Manage History'}
          </button>
          <button
            className="batch-history__refresh-btn"
            onClick={() => fetchHistory(page)}
            type="button"
            aria-label="Refresh batch history"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '6px 12px',
              fontSize: '12px',
              fontWeight: 500,
              color: '#66748C',
              background: '#fff',
              border: '1px solid #E5E7EB',
              borderRadius: '6px',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
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
        <div className="batch-history__confirm-overlay" role="dialog" aria-label="Confirm deletion" style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div className="batch-history__confirm-dialog" style={{ background: '#fff', border: '1px solid #E5E7EB', borderRadius: '8px', boxShadow: '0 4px 16px rgba(0,0,0,0.12)', padding: '24px', maxWidth: '400px', width: '90%' }}>
            <p style={{ margin: '0 0 20px', fontSize: '13px', color: '#1F2937', lineHeight: 1.5 }}>
              Are you sure you want to delete {selectedIds.size} selected batch
              {selectedIds.size !== 1 ? 'es' : ''} and all associated jobs?
            </p>
            <div className="batch-history__confirm-actions" style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '8px' }}>
              <button
                onClick={cancelBulkDelete}
                type="button"
                disabled={deleting}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  padding: '8px 16px',
                  fontSize: '13px',
                  fontWeight: 500,
                  color: '#66748C',
                  background: '#fff',
                  border: '1px solid #E5E7EB',
                  borderRadius: '6px',
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                onClick={confirmBulkDelete}
                type="button"
                disabled={deleting}
                className="batch-history__confirm-delete-btn"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  padding: '8px 16px',
                  fontSize: '13px',
                  fontWeight: 500,
                  color: '#fff',
                  background: '#DC2626',
                  border: '1px solid #DC2626',
                  borderRadius: '6px',
                  cursor: 'pointer',
                }}
              >
                {deleting ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Loading */}
      {loading && batches.length === 0 && (
        <div className="batch-history__loading">Loading batch history…</div>
      )}

      {/* Error */}
      {error && (
        <div className="batch-history__error">
          <span>{error}</span>
          <button
            className="batch-history__retry-btn"
            onClick={() => fetchHistory(page)}
            type="button"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              padding: '6px 14px',
              fontSize: '12px',
              fontWeight: 500,
              color: '#2A6BDB',
              background: '#fff',
              border: '1px solid #2A6BDB',
              borderRadius: '6px',
              cursor: 'pointer',
            }}
          >
            Retry
          </button>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && batches.length === 0 && (
        <div className="batch-history__empty">
          No batch conversions yet. Start a batch conversion above to see history here.
        </div>
      )}

      {/* Table */}
      {batches.length > 0 && (
        <>
          <table className="batch-history__table" role="grid" aria-label="Batch conversion history">
            <thead>
              <tr>
                {selectionMode && <th scope="col" className="batch-history__checkbox-col"></th>}
                <th scope="col">Batch ID</th>
                <th scope="col">Project</th>
                <th scope="col">Status</th>
                <th scope="col">Total</th>
                <th scope="col">Completed</th>
                <th scope="col">Failed</th>
                <th scope="col">Created</th>
              </tr>
            </thead>
            <tbody>
              {batches.map((batch) => (
                <React.Fragment key={batch.id}>
                  <tr
                    className={
                      selectedBatchId === batch.id
                        ? 'batch-history__row--selected'
                        : ''
                    }
                    onClick={() => handleRowClick(batch)}
                    onKeyDown={(e) => handleRowKeyDown(e, batch)}
                    tabIndex={0}
                    role="row"
                    aria-selected={selectedBatchId === batch.id}
                    aria-expanded={expandedBatchId === batch.id}
                  >
                    {selectionMode && (
                      <td className="batch-history__checkbox-col">
                        <input
                          type="checkbox"
                          checked={selectedIds.has(batch.id)}
                          onChange={() => toggleBatchSelection(batch.id)}
                          onClick={(e) => e.stopPropagation()}
                          aria-label={`Select batch ${batch.id}`}
                        />
                      </td>
                    )}
                    <td>
                      <span className="batch-history__batch-id">#{batch.id}</span>
                    </td>
                    <td>
                      {batch.migration_project_id ? (
                        <span className="batch-history__project">
                          Project #{batch.migration_project_id}
                        </span>
                      ) : (
                        <span className="batch-history__project batch-history__project--empty">
                          —
                        </span>
                      )}
                    </td>
                    <td>
                      <Badge variant={statusVariant(batch.status)} size="sm">
                        {batch.status.replace(/_/g, ' ')}
                      </Badge>
                    </td>
                    <td>
                      <span className="batch-history__count-cell">{batch.total_assets}</span>
                    </td>
                    <td>
                      <span className="batch-history__count-cell batch-history__count-cell--success">
                        {batch.completed_assets}
                      </span>
                    </td>
                    <td>
                      <span className="batch-history__count-cell batch-history__count-cell--error">
                        {batch.failed_assets}
                      </span>
                    </td>
                    <td>
                      <span className="batch-history__date">
                        {formatDate(batch.created_at)}
                      </span>
                    </td>
                  </tr>

                  {/* Expanded job detail view */}
                  {expandedBatchId === batch.id && (
                    <tr className="batch-history__detail-row">
                      <td colSpan={selectionMode ? 9 : 8}>
                        <div className="batch-history__jobs">
                          <h4 className="batch-history__jobs-title">Jobs in Batch #{batch.id}</h4>
                          {jobsLoading && (
                            <div className="batch-history__jobs-loading">Loading jobs…</div>
                          )}
                          {!jobsLoading && batchJobs.length === 0 && (
                            <div className="batch-history__jobs-empty">No jobs found.</div>
                          )}
                          {!jobsLoading && batchJobs.length > 0 && (
                            <table className="batch-history__jobs-table" aria-label={`Jobs in batch ${batch.id}`}>
                              <thead>
                                <tr>
                                  <th>Asset Name</th>
                                  <th>Asset Type</th>
                                  <th>Status</th>
                                  <th>Actions</th>
                                </tr>
                              </thead>
                              <tbody>
                                {batchJobs.map((job) => (
                                  <tr key={job.id}>
                                    <td>
                                      {job.asset_name ? (
                                        <span className="batch-history__asset-name">
                                          {job.asset_name}
                                        </span>
                                      ) : (
                                        <span className="batch-history__asset-name batch-history__asset-name--empty">
                                          Untitled
                                        </span>
                                      )}
                                    </td>
                                    <td>
                                      <span className="batch-history__asset-type">
                                        {assetTypeLabel(job.asset_type)}
                                      </span>
                                    </td>
                                    <td>
                                      <Badge variant={statusVariant(job.status)} size="sm">
                                        {job.status}
                                      </Badge>
                                    </td>
                                    <td>
                                      <button
                                        className="batch-history__view-logs-btn"
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          openLogs(job.id);
                                        }}
                                        type="button"
                                        style={{
                                          display: 'inline-flex',
                                          alignItems: 'center',
                                          padding: '4px 10px',
                                          fontSize: '12px',
                                          fontWeight: 500,
                                          color: '#2A6BDB',
                                          background: 'transparent',
                                          border: '1px solid #2A6BDB',
                                          borderRadius: '6px',
                                          cursor: 'pointer',
                                        }}
                                      >
                                        View Logs
                                      </button>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="batch-history__pagination">
              <span>
                Page {page} of {totalPages}
              </span>
              <div className="batch-history__page-controls">
                <button
                  className="batch-history__page-btn"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  type="button"
                  aria-label="Previous page"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: '28px',
                    height: '28px',
                    background: 'transparent',
                    border: '1px solid #E5E7EB',
                    borderRadius: '6px',
                    color: '#66748C',
                    cursor: page <= 1 ? 'not-allowed' : 'pointer',
                    opacity: page <= 1 ? 0.4 : 1,
                  }}
                >
                  <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                    <path d="M10 4l-4 4 4 4" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
                <button
                  className="batch-history__page-btn"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  type="button"
                  aria-label="Next page"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: '28px',
                    height: '28px',
                    background: 'transparent',
                    border: '1px solid #E5E7EB',
                    borderRadius: '6px',
                    color: '#66748C',
                    cursor: page >= totalPages ? 'not-allowed' : 'pointer',
                    opacity: page >= totalPages ? 0.4 : 1,
                  }}
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
