/**
 * BatchPreviewWindow
 *
 * Displays after batch completion (status completed or completed_with_errors).
 * Lists all jobs with columns: asset name, asset type, status badge, Preview action.
 * Inline expandable side-by-side source/target code view on Preview click.
 * Only one job expanded at a time. Failed jobs show error message instead of Preview.
 *
 * Requirements: 11.1, 11.2, 11.3, 11.4, 11.5
 */

import React, { useState } from 'react';
import { Badge } from '../ui';
import { ConversionJob } from '../../services/conversionApi';
import './BatchPreviewWindow.css';

export interface BatchPreviewWindowProps {
  jobs: ConversionJob[];
}

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

/** Normalize asset type for display */
const displayAssetType = (type: string): string => {
  if (type === 'QUERY' || type === 'SCHEDULED_QUERY') return 'Query';
  return type
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
};

export const BatchPreviewWindow: React.FC<BatchPreviewWindowProps> = ({ jobs }) => {
  const [expandedJobId, setExpandedJobId] = useState<number | null>(null);

  const togglePreview = (jobId: number) => {
    setExpandedJobId((prev) => (prev === jobId ? null : jobId));
  };

  if (jobs.length === 0) {
    return null;
  }

  return (
    <div className="batch-preview" role="region" aria-label="Batch preview">
      <div className="batch-preview__header">
        <h3 className="batch-preview__title">
          <svg
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            aria-hidden="true"
          >
            <rect x="2" y="3" width="12" height="10" rx="1" />
            <path d="M8 3v10M2 8h12" strokeLinecap="round" />
          </svg>
          Batch Results
        </h3>
      </div>

      <table className="batch-preview__table">
        <thead>
          <tr>
            <th>Asset Name</th>
            <th>Asset Type</th>
            <th>Status</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <React.Fragment key={job.id}>
              <tr>
                <td>{job.asset_name ?? '—'}</td>
                <td>{displayAssetType(job.asset_type)}</td>
                <td>
                  <Badge variant={statusVariant(job.status)}>{job.status}</Badge>
                </td>
                <td>
                  {job.status === 'failed' ? (
                    <span className="batch-preview__error-msg">
                      {job.error_message ?? 'Unknown error'}
                    </span>
                  ) : (
                    <button
                      className="batch-preview__preview-btn"
                      onClick={() => togglePreview(job.id)}
                      type="button"
                    >
                      {expandedJobId === job.id ? 'Hide' : 'Preview'}
                    </button>
                  )}
                </td>
              </tr>
              {expandedJobId === job.id && (
                <tr className="batch-preview__expanded-row">
                  <td colSpan={4}>
                    <div className="batch-preview__code-compare">
                      <div className="batch-preview__code-pane">
                        <div className="batch-preview__code-label">Source</div>
                        <pre className="batch-preview__code">{job.source_code}</pre>
                      </div>
                      <div className="batch-preview__code-pane">
                        <div className="batch-preview__code-label">Target</div>
                        <pre className="batch-preview__code">
                          {job.target_code ?? 'No output'}
                        </pre>
                      </div>
                    </div>
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
};
