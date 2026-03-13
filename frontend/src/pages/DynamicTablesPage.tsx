import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { useLanguage } from '../contexts/LanguageContext';
import './DynamicTablesPage.css';

interface DynamicTable {
  id: number;
  table_name: string;
  schema_name: string;
  migration_id: number;
  migration_name: string;
  created_at: string;
  row_count: number;
  size_mb: number;
  status: string;
  source_table: string;
}

export const DynamicTablesPage: React.FC = () => {
  const { t } = useLanguage();
  const [tables, setTables] = useState<DynamicTable[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(15);

  useEffect(() => { fetchTables(); }, [currentPage, rowsPerPage]);

  const fetchTables = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      params.append('limit', String(rowsPerPage));
      params.append('offset', String((currentPage - 1) * rowsPerPage));
      if (searchQuery) params.append('search', searchQuery);
      const data = await api.get<{ tables: DynamicTable[]; total: number }>(`/api/dynamic-tables/?${params}`);
      setTables(data.tables || []);
      setTotal(data.total || 0);
    } catch {
      setTables([]);
      setTotal(0);
    } finally { setLoading(false); }
  };

  const handleSearch = () => { setCurrentPage(1); fetchTables(); };
  const totalPages = Math.ceil(total / rowsPerPage) || 1;

  const formatSize = (mb: number) => {
    if (!mb) return '0 MB';
    if (mb >= 1024) return `${(mb / 1024).toFixed(2)} GB`;
    return `${mb.toFixed(2)} MB`;
  };

  return (
    <div className="dt-page">
      <div className="dt-header">
        <h1 className="dt-title">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
            <rect x="3" y="3" width="14" height="14" rx="2" /><path d="M3 7h14M7 7v10" strokeLinecap="round" />
          </svg>
          {t('nav.dynamicTables')}
        </h1>
        <p className="dt-subtitle">{t('dynamicTables.subtitle')}</p>
      </div>

      <div className="dt-toolbar">
        <div className="dt-search">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="#9CA3AF" strokeWidth="2">
            <circle cx="7" cy="7" r="5" /><path d="M11 11l3 3" strokeLinecap="round" />
          </svg>
          <input type="text" placeholder={t('dynamicTables.searchPlaceholder')}
            value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()} onBlur={handleSearch} />
        </div>
      </div>

      <div className="dt-table-container">
        {loading ? (
          <div className="dt-loading"><div className="dt-spinner" /><p>{t('dynamicTables.loading')}</p></div>
        ) : tables.length === 0 ? (
          <div className="dt-empty">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="#D1D5DB" strokeWidth="1.5">
              <rect x="8" y="8" width="32" height="32" rx="4" /><path d="M8 16h32M16 16v24" strokeLinecap="round" />
            </svg>
            <h4>{t('dynamicTables.noTables')}</h4>
            <p>{t('dynamicTables.noTablesDesc')}</p>
          </div>
        ) : (
          <table className="dt-table">
            <thead>
              <tr>
                <th>{t('dynamicTables.tableName')}</th>
                <th>{t('dynamicTables.schema')}</th>
                <th>{t('dynamicTables.sourceTable')}</th>
                <th>{t('dynamicTables.migration')}</th>
                <th>{t('dynamicTables.rows')}</th>
                <th>{t('dynamicTables.size')}</th>
                <th>{t('dynamicTables.status')}</th>
                <th>{t('dynamicTables.createdAt')}</th>
              </tr>
            </thead>
            <tbody>
              {tables.map(tbl => (
                <tr key={tbl.id}>
                  <td className="dt-name">{tbl.table_name}</td>
                  <td>{tbl.schema_name}</td>
                  <td>{tbl.source_table}</td>
                  <td>{tbl.migration_name}</td>
                  <td className="dt-number">{tbl.row_count?.toLocaleString() ?? '—'}</td>
                  <td className="dt-number">{formatSize(tbl.size_mb)}</td>
                  <td><span className={`dt-status ${tbl.status}`}>{tbl.status}</span></td>
                  <td className="dt-time">{new Date(tbl.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {total > 0 && (
        <div className="dt-pagination">
          <span>{t('common.showing')} {Math.min((currentPage - 1) * rowsPerPage + 1, total)}–{Math.min(currentPage * rowsPerPage, total)} {t('common.of')} {total}</span>
          <div className="dt-pagination-controls">
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
    </div>
  );
};
