/**
 * ConversionLogsPanel
 *
 * Modal overlay that displays chronological conversion log entries for a job.
 * Fetches logs via getJobLogs API and shows loading/error/data states.
 *
 * Requirements: 9.4, 9.5, 9.6, 9.7
 */

import React, { useState, useEffect, useCallback } from 'react';
import { getJobLogs, ConversionLog } from '../../services/conversionApi';
import './ConversionLogsPanel.css';

export interface ConversionLogsPanelProps {
  jobId: number;
  isOpen: boolean;
  onClose: () => void;
}

const levelClass = (level: string): string => {
  switch (level.toUpperCase()) {
    case 'INFO':
      return 'logs-panel__level--info';
    case 'WARNING':
      return 'logs-panel__level--warning';
    case 'ERROR':
      return 'logs-panel__level--error';
    default:
      return '';
  }
};

const formatTimestamp = (iso: string): string => {
  try {
    return new Date(iso).toLocaleString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return iso;
  }
};

export const ConversionLogsPanel: React.FC<ConversionLogsPanelProps> = ({
  jobId,
  isOpen,
  onClose,
}) => {
  const [logs, setLogs] = useState<ConversionLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchLogs = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getJobLogs(jobId);
      setLogs(data);
    } catch (err: any) {
      setError(err?.detail || err?.message || 'Failed to load logs');
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    if (isOpen) fetchLogs();
  }, [isOpen, fetchLogs]);

  if (!isOpen) return null;

  return (
    <div className="logs-panel__overlay" onClick={onClose} role="dialog" aria-label="Conversion logs">
      <div className="logs-panel" onClick={(e) => e.stopPropagation()}>
        <div className="logs-panel__header">
          <h3 className="logs-panel__title">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
              <path d="M2 3h12M2 6h12M2 9h8M2 12h10" strokeLinecap="round" />
            </svg>
            Conversion Logs
          </h3>
          <button className="logs-panel__close" onClick={onClose} type="button" aria-label="Close logs panel">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M4 4l8 8M12 4l-8 8" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        <div className="logs-panel__body">
          {loading && <div className="logs-panel__loading">Loading logs…</div>}

          {error && (
            <div className="logs-panel__error">
              <span>{error}</span>
              <button className="logs-panel__retry" onClick={fetchLogs} type="button">Retry</button>
            </div>
          )}

          {!loading && !error && logs.length === 0 && (
            <div className="logs-panel__empty">No log entries found.</div>
          )}

          {!loading && !error && logs.length > 0 && (
            <table className="logs-panel__table" aria-label="Log entries">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Level</th>
                  <th>Step</th>
                  <th>Message</th>
                  <th>Duration</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id}>
                    <td className="logs-panel__ts">{formatTimestamp(log.timestamp)}</td>
                    <td><span className={`logs-panel__level ${levelClass(log.log_level)}`}>{log.log_level}</span></td>
                    <td className="logs-panel__step">{log.step_name}</td>
                    <td className="logs-panel__msg">{log.message}</td>
                    <td className="logs-panel__dur">{log.duration_ms != null ? `${log.duration_ms}ms` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
};
