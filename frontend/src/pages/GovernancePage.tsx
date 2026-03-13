import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { useLanguage } from '../contexts/LanguageContext';
import './GovernancePage.css';

interface AuditRecord {
  id: number;
  action: string;
  resource_type: string;
  resource_name: string;
  performed_by: string;
  performed_at: string;
  details: string | null;
  ip_address: string | null;
  status: string;
}

export const GovernancePage: React.FC = () => {
  const { t } = useLanguage();
  const [records, setRecords] = useState<AuditRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [actionFilter, setActionFilter] = useState('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(15);
  const [selectedRecord, setSelectedRecord] = useState<AuditRecord | null>(null);

  useEffect(() => { fetchRecords(); }, [currentPage, rowsPerPage, actionFilter]);

  const fetchRecords = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      params.append('limit', String(rowsPerPage));
      params.append('offset', String((currentPage - 1) * rowsPerPage));
      if (actionFilter !== 'all') params.append('action', actionFilter);
      if (searchQuery) params.append('search', searchQuery);
      const data = await api.get<{ records: AuditRecord[]; total: number }>(`/api/governance/audit/?${params}`);
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

  const getActionBadge = (action: string) => {
    const map: Record<string, { bg: string; color: string }> = {
      create: { bg: '#ECFDF5', color: '#059669' },
      update: { bg: '#EFF6FF', color: '#2563EB' },
      delete: { bg: '#FEF2F2', color: '#DC2626' },
      execute: { bg: '#FFF7ED', color: '#EA580C' },
      login: { bg: '#F0FDF4', color: '#16A34A' },
      logout: { bg: '#F9FAFB', color: '#6B7280' },
    };
    const s = map[action] || { bg: '#F3F4F6', color: '#374151' };
    return <span className="gov-action-badge" style={{ background: s.bg, color: s.color }}>{action}</span>;
  };

  const getResourceIcon = (type: string) => {
    const icons: Record<string, string> = {
      connection: '🔗', assessment: '🛡️', migration: '➡️', user: '👤',
      workspace: '📦', validation: '✅', conversion: '🔄',
    };
    return icons[type] || '📋';
  };

  return (
    <div className="gov-page">
      <div className="gov-header">
        <h1 className="gov-title">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M10 2L3 6v4c0 4.5 3 7.5 7 8 4-.5 7-3.5 7-8V6l-7-4z" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          {t('nav.governance')}
        </h1>
        <p className="gov-subtitle">{t('governance.subtitle')}</p>
      </div>

      <div className="gov-toolbar">
        <div className="gov-search">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="#9CA3AF" strokeWidth="2">
            <circle cx="7" cy="7" r="5" /><path d="M11 11l3 3" strokeLinecap="round" />
          </svg>
          <input type="text" placeholder={t('governance.searchPlaceholder')}
            value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()} onBlur={handleSearch} />
        </div>
        <select className="gov-filter" value={actionFilter} onChange={e => { setActionFilter(e.target.value); setCurrentPage(1); }}>
          <option value="all">{t('governance.allActions')}</option>
          <option value="create">{t('governance.create')}</option>
          <option value="update">{t('governance.update')}</option>
          <option value="delete">{t('governance.delete')}</option>
          <option value="execute">{t('governance.execute')}</option>
          <option value="login">{t('governance.login')}</option>
        </select>
      </div>

      <div className="gov-table-container">
        {loading ? (
          <div className="gov-loading"><div className="gov-spinner" /><p>{t('governance.loading')}</p></div>
        ) : records.length === 0 ? (
          <div className="gov-empty">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="#D1D5DB" strokeWidth="1.5">
              <path d="M24 6L10 14v8c0 9 6 15 14 16 8-1 14-7 14-16v-8L24 6z" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <h4>{t('governance.noRecords')}</h4>
            <p>{t('governance.noRecordsDesc')}</p>
          </div>
        ) : (
          <table className="gov-table">
            <thead>
              <tr>
                <th>{t('governance.action')}</th>
                <th>{t('governance.resource')}</th>
                <th>{t('governance.resourceName')}</th>
                <th>{t('governance.performedBy')}</th>
                <th>{t('governance.status')}</th>
                <th>{t('governance.ipAddress')}</th>
                <th>{t('governance.timestamp')}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {records.map(r => (
                <tr key={r.id}>
                  <td>{getActionBadge(r.action)}</td>
                  <td><span className="gov-resource-type">{getResourceIcon(r.resource_type)} {r.resource_type}</span></td>
                  <td className="gov-resource-name">{r.resource_name}</td>
                  <td>{r.performed_by}</td>
                  <td><span className={`gov-status ${r.status}`}>{r.status}</span></td>
                  <td className="gov-ip">{r.ip_address || '—'}</td>
                  <td className="gov-time">{formatTimestamp(r.performed_at)}</td>
                  <td>
                    {r.details && (
                      <button className="gov-detail-btn" onClick={() => setSelectedRecord(r)} title="View details">
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <path d="M2 8s2.5-5 6-5 6 5 6 5-2.5 5-6 5-6-5-6-5z" /><circle cx="8" cy="8" r="2" />
                        </svg>
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {total > 0 && (
        <div className="gov-pagination">
          <span>{t('common.showing')} {Math.min((currentPage - 1) * rowsPerPage + 1, total)}–{Math.min(currentPage * rowsPerPage, total)} {t('common.of')} {total}</span>
          <div className="gov-pagination-controls">
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
        <div className="gov-modal-overlay" onClick={() => setSelectedRecord(null)}>
          <div className="gov-modal" onClick={e => e.stopPropagation()}>
            <div className="gov-modal-header">
              <h3>{t('governance.auditDetails')}</h3>
              <button onClick={() => setSelectedRecord(null)}>✕</button>
            </div>
            <div className="gov-modal-body">
              <div className="gov-detail-grid">
                <div className="gov-detail-item"><label>{t('governance.action')}</label>{getActionBadge(selectedRecord.action)}</div>
                <div className="gov-detail-item"><label>{t('governance.resource')}</label><span>{selectedRecord.resource_type}</span></div>
                <div className="gov-detail-item"><label>{t('governance.resourceName')}</label><span>{selectedRecord.resource_name}</span></div>
                <div className="gov-detail-item"><label>{t('governance.performedBy')}</label><span>{selectedRecord.performed_by}</span></div>
                <div className="gov-detail-item"><label>{t('governance.status')}</label><span>{selectedRecord.status}</span></div>
                <div className="gov-detail-item"><label>{t('governance.ipAddress')}</label><span>{selectedRecord.ip_address || '—'}</span></div>
                <div className="gov-detail-item"><label>{t('governance.timestamp')}</label><span>{formatTimestamp(selectedRecord.performed_at)}</span></div>
              </div>
              {selectedRecord.details && (
                <div className="gov-detail-section">
                  <label>{t('governance.details')}</label>
                  <pre className="gov-code-block">{selectedRecord.details}</pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
