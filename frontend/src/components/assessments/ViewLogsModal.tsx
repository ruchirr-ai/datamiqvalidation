/**
 * View Logs Modal
 * 
 * Displays assessment execution logs in the same format as Migration Logs
 */

import React, { useState, useEffect } from 'react';
import { Button } from '../ui';
import { getAssessmentLogs } from '../../services/assessmentsApi';
import './ViewLogsModal.css';

interface ViewLogsModalProps {
  isOpen: boolean;
  assessmentId: number;
  onClose: () => void;
}

interface LogEntry {
  id: number;
  assessment_id: number;
  log_level: string;
  message: string;
  created_at: string;
  stage?: string;
  error_code?: string;
  stack_trace?: string;
  log_metadata?: any;
}

export const ViewLogsModal: React.FC<ViewLogsModalProps> = ({
  isOpen,
  assessmentId,
  onClose,
}) => {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      fetchLogs();
    }
  }, [isOpen, assessmentId]);

  const fetchLogs = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await getAssessmentLogs(assessmentId);
      setLogs(response.logs || []);
    } catch (err: any) {
      console.error('Failed to fetch logs:', err);
      setError(err.detail || err.message || 'Failed to load logs');
      setLogs([]);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-dialog logs-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Assessment Logs</h3>
          <button className="modal-close" onClick={onClose}>
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M6 6l8 8M14 6l-8 8" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <div className="modal-body logs-modal-body">
          {loading ? (
            <div className="logs-loading">
              <div className="spinner"></div>
              <p>Loading logs...</p>
            </div>
          ) : error ? (
            <div className="logs-error">
              <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="var(--color-error)" strokeWidth="2">
                <circle cx="24" cy="24" r="20" />
                <path d="M18 18l12 12M30 18l-12 12" strokeLinecap="round" />
              </svg>
              <h4>Failed to Load Logs</h4>
              <p>{error}</p>
            </div>
          ) : logs.length > 0 ? (
            <div className="logs-container">
              <div className="logs-list">
                {logs.map((log) => (
                  <div key={log.id} className={`log-entry log-level-${log.log_level?.toLowerCase()}`}>
                    <div className="log-header">
                      <span className={`log-level ${log.log_level?.toLowerCase()}`}>
                        {log.log_level}
                      </span>
                      {log.stage && (
                        <span className="log-stage">{log.stage}</span>
                      )}
                      <span className="log-time">
                        {new Date(log.created_at).toLocaleString()}
                      </span>
                    </div>
                    <div className="log-message">{log.message}</div>
                    {log.error_code && (
                      <div className="log-error-code">Error Code: {log.error_code}</div>
                    )}
                    {log.stack_trace && (
                      <details className="log-stack-trace">
                        <summary>Stack Trace</summary>
                        <pre>{log.stack_trace}</pre>
                      </details>
                    )}
                    {log.log_metadata && Object.keys(log.log_metadata).length > 0 && (
                      <details className="log-metadata">
                        <summary>Metadata</summary>
                        <pre>{JSON.stringify(log.log_metadata, null, 2)}</pre>
                      </details>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="logs-empty">
              <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="var(--color-text-secondary)" strokeWidth="2">
                <path d="M12 12h24M12 20h24M12 28h16" strokeLinecap="round" />
              </svg>
              <h4>No Logs Available</h4>
              <p>This assessment hasn't generated any logs yet.</p>
            </div>
          )}
        </div>
        <div className="modal-footer">
          <Button variant="outline" onClick={fetchLogs} disabled={loading}>
            Refresh
          </Button>
          <Button variant="primary" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
};
