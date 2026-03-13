import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { useLanguage } from '../contexts/LanguageContext';
import './QueryHistoryPage.css';

interface QueryRecord {
  id: number;
  query_text: string;
  database_type: string;
  connection_name: string;
  status: string;
  duration_ms: number | null;
  rows_affected: number | null;
  executed_by: string;
  executed_at: string;
  error_message: string | null;
}

export const QueryHistoryPage: React.FC = () => {
  const { t } = useLanguage();
  const [records, setRecords] = useState<QueryRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [dbFilter, setDbFilter] = useState('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(15);
  const [selectedRecord, setSelectedRecord] = useState<QueryRecord | null>(null);

  useEffect(() => { fetchRecords(); }, [currentPage, rowsPerPage, statusFilter, dbFilter]);

  const fetchRecords = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      params.append('limit', String(rowsPerPage));
      params.append('offset', String((currentPage - 1) * rowsPerPage));
      if (statusFilter !== 'all') params.append('status', statusFilter);
      if (dbFilter !== 'all') params.append('database_type', dbFilter);
      if (searchQuery) params.append('search', searchQuery);
      const data = await api.get<{ records: QueryRecord[]; total: number }>(`/api/query-history/?${params}`);
      setRecords(data.records || []);
      setTotal(data.total || 0);
    } catch {
      setRecords([]);
      setTotal(0);
    } finally { setLoading(false); }
  };

  const handleSearch = () => { setCurrentPage(1); fetchRecords(); };
  const totalPages = Math.ceil(total / rowsPerPage) || 1;

  const formatTimestamp = (ts: string) => {
    return new Date(ts).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const formatDuration = (ms: number | null) => {
    if (ms === null) return '—';
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`;
  };

  const getStatusBadge = (status: string) => {
    const map: Record<string, { bg: string; color: string }> = {
      success: { bg: '#ECFDF5', color: '#059669' },
      completed: { bg: '#ECFDF5', color: '#059669' },
      failed: { bg: '#FEF2F2', color: '#DC2626' },
      running: { bg: '#EFF6FF', color: '#2563EB' },
    };
    const s = map[status] || map.failed;
    return <span className="qh-status-badge" style={{ background: s.bg, color: s.color }}>{status}</span>;
  };

  return (
    <div className="qh-page">
      <div className="qh-header">
        <div className="qh-title-section">
          <h1 className="qh-title">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="10" cy="10" r="7" /><path d="M10 6v4l3 2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {t('nav.queryHistory')}
          </h1>
          <p className="qh-subtitle">{t('queryHistory.subtitle')}</p>
        </div>
      </div>

      <div className="qh-toolbar">
        <div className="qh-search">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="#9CA3AF" strokeWidth="2">
            <circle cx="7" cy="7" r="5" /><path d="M11 11l3 3" strokeLinecap="round" />
          </svg>
          <input type="text" placeholder={t('queryHistory.searchPlaceholder')}
            value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()} onBlur={handleSearch} />
        </div>
        <select className="qh-filter" value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setCurrentPage(1); }}>
          <option value="all">{t('queryHistory.allStatus')}</option>
          <option value="success">{t('queryHistory.success')}</option>
          <option value="failed">{t('queryHistory.failed')}</option>
        </select>
        <select className="qh-filter" value={dbFilter} onChange={e => { setDbFilter(e.target.value); setCurrentPage(1); }}>
          <option value="all">{t('queryHistory.allDatabases')}</option>
          <option value="bigquery">BigQuery</option>
          <option value="redshift">Redshift</option>
          <option value="postgresql">PostgreSQL</option>
        </select>
      </div>

      <div className="qh-table-container">
        {loading ? (
          <div className="qh-loading"><div className="qh-spinner" /><p>{t('queryHistory.loading')}</p></div>
        ) : records.length === 0 ? (
          <div className="qh-empty">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="#D1D5DB" strokeWidth="1.5">
              <circle cx="24" cy="24" r="18" /><path d="M24 14v10l7 4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <h4>{t('queryHistory.noRecords')}</h4>
            <p>{t('queryHistory.noRecordsDesc')}</p>
          </div>
        ) : (
          <table className="qh-table">
            <thead>
              <tr>
                <th>{t('queryHistory.query')}</th>
                <th>{t('queryHistory.database')}</th>
                <th>{t('queryHistory.connection')}</th>
                <th>{t('queryHistory.status')}</th>
                <th>{t('queryHistory.duration')}</th>
                <th>{t('queryHistory.rows')}</th>
                <th>{t('queryHistory.executedBy')}</th>
                <th>{t('queryHistory.executedAt')}</th>
              </tr>
            </thead>
            <tbody>
              {records.map(r => (
                <tr key={r.id} onClick={() => setSelectedRecord(r)}>
                  <td className="qh-query-cell"><code>{r.query_text.substring(0, 80)}{r.query_text.length > 80 ? '…' : ''}</code></td>
                  <td><span className="qh-db-badge">{r.database_type}</span></td>
                  <td>{r.connection_name}</td>
                  <td>{getStatusBadge(r.status)}</td>
                  <td className="qh-number">{formatDuration(r.duration_ms)}</td>
                  <td className="qh-number">{r.rows_affected?.toLocaleString() ?? '—'}</td>
                  <td>{r.executed_by}</td>
                  <td className="qh-time">{formatTimestamp(r.executed_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {total > 0 && (
        <div className="qh-pagination">
          <span>{t('common.showing')} {Math.min((currentPage - 1) * rowsPerPage + 1, total)}–{Math.min(currentPage * rowsPerPage, total)} {t('common.of')} {total}</span>
          <div className="qh-pagination-controls">
            <span>{t('common.rowsPerPage')}</span>
            <select value={rowsPerPage} onChange={e => { setRowsPerPage(Number(e.target.value)); setCurrentPage(1); }}>
              <option value={10}>10</option><option value={15}>15</option><option value={25}>25</option><option value={50}>50</option>
            </select>
            <button disabled={currentPage === 1} onClick={() => setCurrentPage(p => p - 1)}>‹</button>
            <span>{currentPage} / {totalPages}</span>
            <button disabled={currentPage === totalPages} onClick={() => setCurrentPage(p => p + 1)}>›</button>
          </div>
        </div>
      )}

      {selectedRecord && (
        <div className="qh-modal-overlay" onClick={() => setSelectedRecord(null)}>
          <div className="qh-modal" onClick={e => e.stopPropagation()}>
            <div className="qh-modal-header">
              <h3>{t('queryHistory.queryDetails')}</h3>
              <button onClick={() => setSelectedRecord(null)}>✕</button>
            </div>
            <div className="qh-modal-body">
              <div className="qh-detail-grid">
                <div className="qh-detail-item"><label>{t('queryHistory.database')}</label><span>{selectedRecord.database_type}</span></div>
                <div className="qh-detail-item"><label>{t('queryHistory.connection')}</label><span>{selectedRecord.connection_name}</span></div>
                <div className="qh-detail-item"><label>{t('queryHistory.status')}</label>{getStatusBadge(selectedRecord.status)}</div>
                <div className="qh-detail-item"><label>{t('queryHistory.duration')}</label><span>{formatDuration(selectedRecord.duration_ms)}</span></div>
                <div className="qh-detail-item"><label>{t('queryHistory.rows')}</label><span>{selectedRecord.rows_affected?.toLocaleString() ?? '—'}</span></div>
                <div className="qh-detail-item"><label>{t('queryHistory.executedBy')}</label><span>{selectedRecord.executed_by}</span></div>
                <div className="qh-detail-item"><label>{t('queryHistory.executedAt')}</label><span>{formatTimestamp(selectedRecord.executed_at)}</span></div>
              </div>
              <div className="qh-detail-section">
                <label>{t('queryHistory.query')}</label>
                <pre className="qh-code-block">{selectedRecord.query_text}</pre>
              </div>
              {selectedRecord.error_message && (
                <div className="qh-detail-section qh-error-section">
                  <label>{t('queryHistory.error')}</label>
                  <pre className="qh-code-block qh-error-block">{selectedRecord.error_message}</pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
