import React, { useState, useEffect } from 'react';
import { copyHistoryApi, CopyRecord } from '../services/copyHistoryApi';
import { useLanguage } from '../contexts/LanguageContext';
import './CopyHistoryPage.css';

export const CopyHistoryPage: React.FC = () => {
  const { t } = useLanguage();
  const [records, setRecords] = useState<CopyRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(15);
  const [selectedRecord, setSelectedRecord] = useState<CopyRecord | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  useEffect(() => {
    fetchRecords();
  }, [currentPage, rowsPerPage, statusFilter]);

  const fetchRecords = async () => {
    try {
      setLoading(true);
      const data = await copyHistoryApi.list({
        status_filter: statusFilter !== 'all' ? statusFilter : undefined,
        search: searchQuery || undefined,
        limit: rowsPerPage,
        offset: (currentPage - 1) * rowsPerPage,
      });
      setRecords(data.records);
      setTotal(data.total);
    } catch (err: any) {
      setToast({ message: `Failed to load copy history: ${err.message}`, type: 'error' });
      setRecords([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    setCurrentPage(1);
    fetchRecords();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch();
  };

  const totalPages = Math.ceil(total / rowsPerPage);

  const formatTimestamp = (ts: string | null) => {
    if (!ts) return '—';
    return new Date(ts).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const formatDuration = (seconds: number | null) => {
    if (seconds === null || seconds === undefined) return '—';
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${mins}m ${secs}s`;
  };

  const formatBytes = (bytes: number) => {
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    let val = bytes;
    while (val >= 1024 && i < units.length - 1) { val /= 1024; i++; }
    return `${val.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
  };

  const formatRows = (rows: number) => {
    if (!rows) return '0';
    return rows.toLocaleString();
  };

  const getStatusBadge = (status: string) => {
    const styles: Record<string, { bg: string; color: string; key: string }> = {
      completed: { bg: '#ECFDF5', color: '#059669', key: 'copyHistory.completed' },
      running: { bg: '#EFF6FF', color: '#2563EB', key: 'copyHistory.running' },
      failed: { bg: '#FEF2F2', color: '#DC2626', key: 'copyHistory.failed' },
    };
    const s = styles[status] || styles.failed;
    return (
      <span className="copy-status-badge" style={{ background: s.bg, color: s.color }}>
        {status === 'running' && <span className="copy-status-dot" style={{ background: s.color }} />}
        {t(s.key)}
      </span>
    );
  };

  return (
    <div className="copy-history-page">
      {/* Toast */}
      {toast && (
        <div className={`copy-toast copy-toast--${toast.type}`}>
          {toast.message}
          <button onClick={() => setToast(null)} className="copy-toast-close">×</button>
        </div>
      )}

      {/* Header */}
      <div className="copy-history-header">
        <div className="copy-history-title-section">
          <h1 className="copy-history-title">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" className="page-title-icon">
              <path d="M4 4h12M4 8h12M4 12h8" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Copy History
          </h1>
          <div className="copy-history-subheader">
            <span className="copy-history-count">{total} {t('copyHistory.title')}</span>
            <div className="copy-history-actions">
              <div className="search-box">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="7" cy="7" r="5" />
                  <path d="M11 11l3 3" strokeLinecap="round" />
                </svg>
                <input
                  type="text"
                  placeholder={t('copyHistory.searchPlaceholder')}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={handleKeyDown}
                  onBlur={handleSearch}
                />
              </div>
              <select
                className="copy-filter-select"
                value={statusFilter}
                onChange={(e) => { setStatusFilter(e.target.value); setCurrentPage(1); }}
              >
                <option value="all">{t('copyHistory.allStatus')}</option>
                <option value="completed">{t('copyHistory.completed')}</option>
                <option value="running">{t('copyHistory.running')}</option>
                <option value="failed">{t('copyHistory.failed')}</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="copy-table-container">
        {loading ? (
          <div className="copy-loading">
            <div className="copy-spinner" />
            <p>{t('copyHistory.loading')}</p>
          </div>
        ) : records.length === 0 ? (
          <div className="copy-empty">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="#9CA3AF" strokeWidth="2">
              <path d="M12 12h24M12 20h24M12 28h16" strokeLinecap="round" />
            </svg>
            <h4>{t('copyHistory.noRecords')}</h4>
            <p>{t('copyHistory.noRecordsDesc')}</p>
          </div>
        ) : (
          <table className="copy-table">
            <thead>
              <tr>
                <th>{t('copyHistory.migration')}</th>
                <th>{t('copyHistory.table')}</th>
                <th>{t('copyHistory.status')}</th>
                <th>{t('copyHistory.rows')}</th>
                <th>{t('copyHistory.size')}</th>
                <th>{t('copyHistory.duration')}</th>
                <th>{t('copyHistory.startedAt')}</th>
                <th>{t('copyHistory.format')}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {records.map((r) => (
                <tr key={r.id}>
                  <td>
                    <div className="copy-migration-name">{r.migration_name}</div>
                    <div className="copy-migration-id">ID: {r.migration_id}</div>
                  </td>
                  <td>
                    <span className="copy-table-name">{r.schema_name}.{r.table_name}</span>
                  </td>
                  <td>{getStatusBadge(r.status)}</td>
                  <td className="copy-number-cell">{formatRows(r.rows_loaded)}</td>
                  <td className="copy-number-cell">{formatBytes(r.bytes_loaded)}</td>
                  <td className="copy-number-cell">{formatDuration(r.duration_seconds)}</td>
                  <td className="timestamp-cell">{formatTimestamp(r.started_at)}</td>
                  <td><span className="copy-format-badge">{r.file_format || '—'}</span></td>
                  <td>
                    <button className="copy-detail-btn" onClick={() => setSelectedRecord(r)} title="View details">
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

      {/* Pagination */}
      {total > 0 && (
        <div className="copy-pagination">
          <span className="pagination-info">
            {t('copyHistory.showing')} {Math.min((currentPage - 1) * rowsPerPage + 1, total)}–{Math.min(currentPage * rowsPerPage, total)} {t('copyHistory.of')} {total}
          </span>
          <div className="pagination-controls">
            <div className="rows-per-page">
              <span>{t('copyHistory.rowsPerPage')}</span>
              <select value={rowsPerPage} onChange={(e) => { setRowsPerPage(Number(e.target.value)); setCurrentPage(1); }}>
                <option value={10}>10</option>
                <option value={15}>15</option>
                <option value={25}>25</option>
                <option value={50}>50</option>
              </select>
            </div>
            <div className="pagination-buttons">
              <button className="pagination-btn" disabled={currentPage === 1} onClick={() => setCurrentPage(p => p - 1)}>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M10 4L6 8l4 4" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
              <span style={{ fontSize: '13px', color: '#6B7280' }}>{t('copyHistory.page')} {currentPage} {t('copyHistory.of')} {totalPages}</span>
              <button className="pagination-btn" disabled={currentPage === totalPages} onClick={() => setCurrentPage(p => p + 1)}>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M6 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Detail Modal */}
      {selectedRecord && (
        <div className="copy-modal-overlay" onClick={() => setSelectedRecord(null)}>
          <div className="copy-modal" onClick={(e) => e.stopPropagation()}>
            <div className="copy-modal-header">
              <h3>{t('copyHistory.details')}</h3>
              <button className="modal-close" onClick={() => setSelectedRecord(null)}>
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M6 6l8 8M14 6l-8 8" strokeLinecap="round" />
                </svg>
              </button>
            </div>
            <div className="copy-modal-body">
              <div className="copy-detail-grid">
                <div className="copy-detail-item">
                  <label>{t('copyHistory.migration')}</label>
                  <span>{selectedRecord.migration_name} (ID: {selectedRecord.migration_id})</span>
                </div>
                <div className="copy-detail-item">
                  <label>{t('copyHistory.table')}</label>
                  <span>{selectedRecord.schema_name}.{selectedRecord.table_name}</span>
                </div>
                <div className="copy-detail-item">
                  <label>{t('copyHistory.status')}</label>
                  <span>{getStatusBadge(selectedRecord.status)}</span>
                </div>
                <div className="copy-detail-item">
                  <label>{t('copyHistory.started')}</label>
                  <span>{formatTimestamp(selectedRecord.started_at)}</span>
                </div>
                <div className="copy-detail-item">
                  <label>{t('copyHistory.completed2')}</label>
                  <span>{formatTimestamp(selectedRecord.completed_at)}</span>
                </div>
                <div className="copy-detail-item">
                  <label>{t('copyHistory.duration')}</label>
                  <span>{formatDuration(selectedRecord.duration_seconds)}</span>
                </div>
                <div className="copy-detail-item">
                  <label>{t('copyHistory.rowsLoaded')}</label>
                  <span>{formatRows(selectedRecord.rows_loaded)}</span>
                </div>
                <div className="copy-detail-item">
                  <label>{t('copyHistory.bytesLoaded')}</label>
                  <span>{formatBytes(selectedRecord.bytes_loaded)}</span>
                </div>
                <div className="copy-detail-item">
                  <label>{t('copyHistory.format')}</label>
                  <span>{selectedRecord.file_format || '—'}</span>
                </div>
                <div className="copy-detail-item">
                  <label>{t('copyHistory.compression')}</label>
                  <span>{selectedRecord.compression || 'NONE'}</span>
                </div>
              </div>

              {selectedRecord.source_uri && (
                <div className="copy-detail-section">
                  <label>{t('copyHistory.sourceUri')}</label>
                  <pre className="copy-code-block">{selectedRecord.source_uri}</pre>
                </div>
              )}

              <div className="copy-detail-section">
                <label>{t('copyHistory.copyCommand')}</label>
                <pre className="copy-code-block">{selectedRecord.copy_command}</pre>
              </div>

              {selectedRecord.error_message && (
                <div className="copy-detail-section copy-error-section">
                  <label>{t('copyHistory.error')}</label>
                  <pre className="copy-code-block copy-error-block">{selectedRecord.error_message}</pre>
                </div>
              )}

              {selectedRecord.error_details && (
                <div className="copy-detail-section copy-error-section">
                  <label>{t('copyHistory.errorDetails')}</label>
                  <pre className="copy-code-block copy-error-block">{JSON.stringify(selectedRecord.error_details, null, 2)}</pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
