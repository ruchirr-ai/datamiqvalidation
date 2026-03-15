import React, { useState, useEffect } from 'react';
import { taskHistoryApi, TaskRecord } from '../services/taskHistoryApi';
import { useLanguage } from '../contexts/LanguageContext';
import './TaskHistoryPage.css';

export const TaskHistoryPage: React.FC = () => {
  const { t } = useLanguage();
  const [records, setRecords] = useState<TaskRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(15);
  const [selectedRecord, setSelectedRecord] = useState<TaskRecord | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  useEffect(() => {
    if (toast) { const t = setTimeout(() => setToast(null), 4000); return () => clearTimeout(t); }
  }, [toast]);

  useEffect(() => { fetchRecords(); }, [currentPage, rowsPerPage, statusFilter]);

  const fetchRecords = async () => {
    try {
      setLoading(true);
      const data = await taskHistoryApi.list({
        status_filter: statusFilter !== 'all' ? statusFilter : undefined,
        search: searchQuery || undefined,
        limit: rowsPerPage,
        offset: (currentPage - 1) * rowsPerPage,
      });
      setRecords(data.records);
      setTotal(data.total);
    } catch (err: any) {
      setToast({ message: `Failed to load task history: ${err.message}`, type: 'error' });
      setRecords([]);
    } finally { setLoading(false); }
  };

  const handleSearch = () => { setCurrentPage(1); fetchRecords(); };
  const handleKeyDown = (e: React.KeyboardEvent) => { if (e.key === 'Enter') handleSearch(); };
  const totalPages = Math.ceil(total / rowsPerPage);

  const formatTimestamp = (ts: string | null) => {
    if (!ts) return '—';
    return new Date(ts).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const formatDuration = (seconds: number | null) => {
    if (seconds === null || seconds === undefined) return '—';
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    if (seconds < 3600) { const m = Math.floor(seconds / 60); return `${m}m ${Math.round(seconds % 60)}s`; }
    const h = Math.floor(seconds / 3600); const m = Math.floor((seconds % 3600) / 60);
    return `${h}h ${m}m`;
  };

  const formatBytes = (bytes: number) => {
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0; let val = bytes;
    while (val >= 1024 && i < units.length - 1) { val /= 1024; i++; }
    return `${val.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
  };

  const getStatusBadge = (status: string) => {
    const styles: Record<string, { bg: string; color: string; key: string }> = {
      completed: { bg: '#ECFDF5', color: '#059669', key: 'taskHistory.completed' },
      running: { bg: '#EFF6FF', color: '#2563EB', key: 'taskHistory.running' },
      failed: { bg: '#FEF2F2', color: '#DC2626', key: 'taskHistory.failed' },
      agent_offline: { bg: '#FFF7ED', color: '#EA580C', key: 'taskHistory.agentOffline' },
    };
    const s = styles[status] || styles.failed;
    return (
      <span className="task-status-badge" style={{ background: s.bg, color: s.color }}>
        {status === 'running' && <span className="task-status-dot" style={{ background: s.color }} />}
        {t(s.key)}
      </span>
    );
  };

  return (
    <div className="task-history-page">
      {toast && (
        <div className={`task-toast task-toast--${toast.type}`}>
          {toast.message}
          <button onClick={() => setToast(null)} className="task-toast-close">×</button>
        </div>
      )}

      <div className="task-history-header">
        <div className="task-history-title-section">
          <h1 className="task-history-title">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" className="page-title-icon">
              <path d="M3 10h4l3-7 4 14 3-7h3" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Task History
          </h1>
          <div className="task-history-subheader">
            <span className="task-history-count">{total} {t('taskHistory.title')}</span>
            <div className="task-history-actions">
              <div className="search-box">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="7" cy="7" r="5" />
                  <path d="M11 11l3 3" strokeLinecap="round" />
                </svg>
                <input type="text" placeholder={t('taskHistory.searchPlaceholder')} value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} onKeyDown={handleKeyDown} onBlur={handleSearch} />
              </div>
              <select className="task-filter-select" value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setCurrentPage(1); }}>
                <option value="all">{t('taskHistory.allStatus')}</option>
                <option value="completed">{t('taskHistory.completed')}</option>
                <option value="running">{t('taskHistory.running')}</option>
                <option value="failed">{t('taskHistory.failed')}</option>
                <option value="agent_offline">{t('taskHistory.agentOffline')}</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <div className="task-table-container">
        {loading ? (
          <div className="task-loading"><div className="task-spinner" /><p>{t('taskHistory.loading')}</p></div>
        ) : records.length === 0 ? (
          <div className="task-empty">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="#9CA3AF" strokeWidth="2">
              <path d="M12 24h6l4-10 6 20 4-10h4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <h4>{t('taskHistory.noRecords')}</h4>
            <p>{t('taskHistory.noRecordsDesc')}</p>
          </div>
        ) : (
          <table className="task-table">
            <thead>
              <tr>
                <th>{t('taskHistory.migration')}</th>
                <th>{t('taskHistory.table')}</th>
                <th>{t('taskHistory.status')}</th>
                <th>{t('taskHistory.files')}</th>
                <th>{t('taskHistory.size')}</th>
                <th>{t('taskHistory.duration')}</th>
                <th>{t('taskHistory.agentIp')}</th>
                <th>{t('taskHistory.startedAt')}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {records.map((r) => (
                <tr key={r.id}>
                  <td>
                    <div className="task-migration-name">{r.migration_name}</div>
                    <div className="task-migration-id">ID: {r.migration_id}</div>
                  </td>
                  <td><span className="task-table-name">{r.table_name || 'All tables'}</span></td>
                  <td>{getStatusBadge(r.status)}</td>
                  <td className="task-number-cell">{(r.files_transferred || 0).toLocaleString()}</td>
                  <td className="task-number-cell">{formatBytes(r.bytes_transferred)}</td>
                  <td className="task-number-cell">{formatDuration(r.duration_seconds)}</td>
                  <td><span className="task-agent-ip">{r.agent_ip || '—'}</span></td>
                  <td className="timestamp-cell">{formatTimestamp(r.started_at)}</td>
                  <td>
                    <button className="task-detail-btn" onClick={() => setSelectedRecord(r)} title="View details">
                      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <path d="M2 8s2.5-5 6-5 6 5 6 5-2.5 5-6 5-6-5-6-5z" />
                        <circle cx="8" cy="8" r="2" />
                      </svg>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {total > 0 && (
        <div className="task-pagination">
          <span className="pagination-info">{t('taskHistory.showing')} {Math.min((currentPage - 1) * rowsPerPage + 1, total)}–{Math.min(currentPage * rowsPerPage, total)} {t('taskHistory.of')} {total}</span>
          <div className="pagination-controls">
            <div className="rows-per-page">
              <span>{t('taskHistory.rowsPerPage')}</span>
              <select value={rowsPerPage} onChange={(e) => { setRowsPerPage(Number(e.target.value)); setCurrentPage(1); }}>
                <option value={10}>10</option><option value={15}>15</option><option value={25}>25</option><option value={50}>50</option>
              </select>
            </div>
            <div className="pagination-buttons">
              <button className="pagination-btn" disabled={currentPage === 1} onClick={() => setCurrentPage(p => p - 1)}>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10 4L6 8l4 4" strokeLinecap="round" strokeLinejoin="round" /></svg>
              </button>
              <span style={{ fontSize: '13px', color: '#6B7280' }}>{t('taskHistory.page')} {currentPage} {t('taskHistory.of')} {totalPages}</span>
              <button className="pagination-btn" disabled={currentPage === totalPages} onClick={() => setCurrentPage(p => p + 1)}>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" /></svg>
              </button>
            </div>
          </div>
        </div>
      )}

      {selectedRecord && (
        <div className="task-modal-overlay" onClick={() => setSelectedRecord(null)}>
          <div className="task-modal" onClick={(e) => e.stopPropagation()}>
            <div className="task-modal-header">
              <h3>{t('taskHistory.details')}</h3>
              <button className="modal-close" onClick={() => setSelectedRecord(null)}>
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 6l8 8M14 6l-8 8" strokeLinecap="round" /></svg>
              </button>
            </div>
            <div className="task-modal-body">
              <div className="task-detail-grid">
                <div className="task-detail-item"><label>{t('taskHistory.migration')}</label><span>{selectedRecord.migration_name} (ID: {selectedRecord.migration_id})</span></div>
                <div className="task-detail-item"><label>{t('taskHistory.table')}</label><span>{selectedRecord.table_name || 'All tables'}</span></div>
                <div className="task-detail-item"><label>{t('taskHistory.status')}</label><span>{getStatusBadge(selectedRecord.status)}</span></div>
                <div className="task-detail-item"><label>{t('taskHistory.taskType')}</label><span>{selectedRecord.task_type?.toUpperCase() || 'DATASYNC'}</span></div>
                <div className="task-detail-item"><label>{t('taskHistory.started')}</label><span>{formatTimestamp(selectedRecord.started_at)}</span></div>
                <div className="task-detail-item"><label>{t('taskHistory.completed2')}</label><span>{formatTimestamp(selectedRecord.completed_at)}</span></div>
                <div className="task-detail-item"><label>{t('taskHistory.duration')}</label><span>{formatDuration(selectedRecord.duration_seconds)}</span></div>
                <div className="task-detail-item"><label>{t('taskHistory.filesTransferred')}</label><span>{(selectedRecord.files_transferred || 0).toLocaleString()}</span></div>
                <div className="task-detail-item"><label>{t('taskHistory.bytesTransferred')}</label><span>{formatBytes(selectedRecord.bytes_transferred)}</span></div>
                <div className="task-detail-item"><label>{t('taskHistory.agentIp')}</label><span>{selectedRecord.agent_ip || '—'}</span></div>
              </div>

              {selectedRecord.source_uri && (
                <div className="task-detail-section"><label>{t('taskHistory.source')}</label><pre className="task-code-block">{selectedRecord.source_uri}</pre></div>
              )}
              {selectedRecord.dest_uri && (
                <div className="task-detail-section"><label>{t('taskHistory.destination')}</label><pre className="task-code-block">{selectedRecord.dest_uri}</pre></div>
              )}
              {selectedRecord.task_arn && (
                <div className="task-detail-section"><label>{t('taskHistory.taskArn')}</label><pre className="task-code-block">{selectedRecord.task_arn}</pre></div>
              )}
              {selectedRecord.execution_arn && (
                <div className="task-detail-section"><label>{t('taskHistory.executionArn')}</label><pre className="task-code-block">{selectedRecord.execution_arn}</pre></div>
              )}
              {selectedRecord.agent_arn && (
                <div className="task-detail-section"><label>{t('taskHistory.agentArn')}</label><pre className="task-code-block">{selectedRecord.agent_arn}</pre></div>
              )}
              {selectedRecord.error_message && (
                <div className="task-detail-section task-error-section"><label>{t('taskHistory.error')}</label><pre className="task-code-block task-error-block">{selectedRecord.error_message}</pre></div>
              )}
              {selectedRecord.error_details && (
                <div className="task-detail-section task-error-section"><label>{t('taskHistory.errorDetails')}</label><pre className="task-code-block task-error-block">{JSON.stringify(selectedRecord.error_details, null, 2)}</pre></div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
