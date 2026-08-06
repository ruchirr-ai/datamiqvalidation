import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { useLanguage } from '../contexts/LanguageContext';
import './DashboardPage.css';

interface DashboardData {
  total_connections: number;
  source_connections: number;
  target_connections: number;
  connected_count: number;
  total_assessments: number;
  completed_assessments: number;
  running_assessments: number;
  failed_assessments: number;
  total_tables_discovered: number;
  total_views_discovered: number;
  total_routines_discovered: number;
  total_size_mb: number;
  total_migrations: number;
  completed_migrations: number;
  running_migrations: number;
  failed_migrations: number;
  scheduled_migrations: number;
  total_batches: number;
  total_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  total_copies: number;
  completed_copies: number;
  total_rows_copied: number;
  total_bytes_copied: number;
  recent_assessments: any[];
  recent_migrations: any[];
  recent_copies: any[];
}

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const { t } = useLanguage();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [recentTab, setRecentTab] = useState<'assessments' | 'migrations' | 'copies'>('assessments');

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        const result = await api.get<DashboardData>('/api/dashboard/summary');
        setData(result);
      } catch (err) {
        console.error('Failed to load dashboard:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchDashboard();
  }, []);

  const formatSize = (mb: number) => {
    if (!mb) return '0 MB';
    if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`;
    return `${mb.toFixed(1)} MB`;
  };

  const formatTimestamp = (ts: string | null) => {
    if (!ts) return '—';
    return new Date(ts).toLocaleString('en-IN', {
      timeZone: 'Asia/Kolkata',
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  };

  if (loading) {
    return (
      <div className="dashboard-page">
        <div className="dashboard-loading">
          <span className="dash-spinner" />
          {t('dashboard.loading')}
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="dashboard-page">
        <div className="dashboard-header">
          <h1 className="dashboard-title">{t('dashboard.title')}</h1>
        </div>
        <div className="dashboard-loading">{t('dashboard.loadFailed')}</div>
      </div>
    );
  }

  const migrationTotal = Math.max(data.total_migrations, 1);
  const barPct = (count: number) => `${(count / migrationTotal) * 100}%`;

  const recentItems = recentTab === 'assessments' ? data.recent_assessments
    : recentTab === 'migrations' ? data.recent_migrations
    : data.recent_copies;

  return (
    <div className="dashboard-page">
      <div className="dashboard-header">
        <div className="dashboard-header-text">
          <h1 className="dashboard-title">
            <svg width="22" height="22" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
              <rect x="3" y="3" width="6" height="6" rx="1.5" />
              <rect x="11" y="3" width="6" height="6" rx="1.5" />
              <rect x="3" y="11" width="6" height="6" rx="1.5" />
              <rect x="11" y="11" width="6" height="6" rx="1.5" />
            </svg>
            {t('dashboard.title')}
          </h1>
          <p className="dashboard-subtitle">{t('dashboard.subtitle')}</p>
        </div>
        <div className="dashboard-header-actions">
          <span className="live-status-badge">
            <span className="live-dot" /> Live System Status
          </span>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="dashboard-cards">
        {/* Connections Card */}
        <div className="dash-card" onClick={() => navigate('/connections')}>
          <div className="dash-card-top">
            <div className="dash-card-icon blue">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
                <path d="M17 21v-2a1 1 0 0 1-1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1" />
                <path d="M7 21v-2a1 1 0 0 0 1-1v-1a1 1 0 0 0-1-1H6a1 1 0 0 0-1 1v1a1 1 0 0 0 1 1" />
                <path d="M17 14V3" /><path d="M7 14V3" />
                <path d="M17 3H7" /><path d="M17 8H7" />
              </svg>
            </div>
            <span className="dash-card-arrow">→</span>
          </div>
          <div className="dash-card-content">
            <div className="dash-card-label">{t('dashboard.connections')}</div>
            <div className="dash-card-value">{data.total_connections}</div>
            <div className="dash-card-detail">
              <span><span className="dash-detail-dot green" /> {data.connected_count} {t('dashboard.connected')}</span>
              <span className="detail-separator">•</span>
              <span>{data.source_connections} {t('dashboard.src')} / {data.target_connections} {t('dashboard.tgt')}</span>
            </div>
          </div>
        </div>

        {/* Assessments Card */}
        <div className="dash-card" onClick={() => navigate('/assessments')}>
          <div className="dash-card-top">
            <div className="dash-card-icon green">
              <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75">
                <path d="M9 2L3 6v4c0 4.5 3 7.5 6 8 3-.5 6-3.5 6-8V6l-6-4z" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M7 10l2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <span className="dash-card-arrow">→</span>
          </div>
          <div className="dash-card-content">
            <div className="dash-card-label">{t('dashboard.assessments')}</div>
            <div className="dash-card-value">{data.total_assessments}</div>
            <div className="dash-card-detail">
              <span><span className="dash-detail-dot green" /> {data.completed_assessments} {t('dashboard.done')}</span>
              {data.running_assessments > 0 && <span><span className="dash-detail-dot blue" /> {data.running_assessments} {t('dashboard.running')}</span>}
              {data.failed_assessments > 0 && <span><span className="dash-detail-dot red" /> {data.failed_assessments} {t('dashboard.failed')}</span>}
            </div>
          </div>
        </div>

        {/* Migrations Card */}
        <div className="dash-card" onClick={() => navigate('/migrations')}>
          <div className="dash-card-top">
            <div className="dash-card-icon purple">
              <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75">
                <path d="M3 10h14M14 6l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <span className="dash-card-arrow">→</span>
          </div>
          <div className="dash-card-content">
            <div className="dash-card-label">{t('dashboard.migrations')}</div>
            <div className="dash-card-value">{data.total_migrations}</div>
            <div className="dash-card-detail">
              <span><span className="dash-detail-dot green" /> {data.completed_migrations} {t('dashboard.done')}</span>
              {data.running_migrations > 0 && <span><span className="dash-detail-dot blue" /> {data.running_migrations} {t('dashboard.running')}</span>}
              {data.scheduled_migrations > 0 && <span><span className="dash-detail-dot yellow" /> {data.scheduled_migrations} {t('dashboard.scheduled')}</span>}
            </div>
          </div>
        </div>

        {/* Code Conversions Card */}
        <div className="dash-card" onClick={() => navigate('/converter')}>
          <div className="dash-card-top">
            <div className="dash-card-icon orange">
              <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75">
                <path d="M7 5L3 10l4 5" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M13 5l4 5-4 5" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M11 3L9 17" strokeLinecap="round" />
              </svg>
            </div>
            <span className="dash-card-arrow">→</span>
          </div>
          <div className="dash-card-content">
            <div className="dash-card-label">{t('dashboard.codeConversions')}</div>
            <div className="dash-card-value">{data.total_jobs}</div>
            <div className="dash-card-detail">
              <span><span className="dash-detail-dot green" /> {data.completed_jobs} {t('dashboard.done')}</span>
              {data.failed_jobs > 0 && <span><span className="dash-detail-dot red" /> {data.failed_jobs} {t('dashboard.failed')}</span>}
              <span className="detail-separator">•</span>
              <span>{data.total_batches} {t('dashboard.batches')}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Middle Row */}
      <div className="dashboard-mid-row">
        {/* Assessment Discovery */}
        <div className="dash-section">
          <div className="dash-section-header">
            <div>
              <h3 className="dash-section-title">{t('dashboard.assessmentDiscovery')}</h3>
              <p className="dash-section-sub">Source database objects analyzed</p>
            </div>
            <a className="dash-section-link" onClick={() => navigate('/assessments')}>{t('dashboard.viewAll')} →</a>
          </div>
          <div className="discovery-stats">
            <div className="discovery-stat">
              <div className="discovery-stat-value">{data.total_tables_discovered.toLocaleString()}</div>
              <div className="discovery-stat-label">{t('dashboard.tables')}</div>
            </div>
            <div className="discovery-stat">
              <div className="discovery-stat-value">{data.total_views_discovered.toLocaleString()}</div>
              <div className="discovery-stat-label">{t('dashboard.views')}</div>
            </div>
            <div className="discovery-stat">
              <div className="discovery-stat-value">{data.total_routines_discovered.toLocaleString()}</div>
              <div className="discovery-stat-label">{t('dashboard.routines')}</div>
            </div>
          </div>
          {data.total_size_mb > 0 && (
            <div className="volume-footer">
              <span className="volume-label">{t('dashboard.totalDataVolume')}</span>
              <span className="volume-badge">{formatSize(data.total_size_mb)}</span>
            </div>
          )}
        </div>

        {/* Migration Status */}
        <div className="dash-section">
          <div className="dash-section-header">
            <div>
              <h3 className="dash-section-title">{t('dashboard.migrationStatus')}</h3>
              <p className="dash-section-sub">Pipeline execution progress</p>
            </div>
            <a className="dash-section-link" onClick={() => navigate('/migrations')}>{t('dashboard.viewAll')} →</a>
          </div>
          <div className="migration-status-list">
            <div className="migration-status-row">
              <span className="migration-status-label">{t('dashboard.completed')}</span>
              <div className="migration-status-bar-bg">
                <div className="migration-status-bar-fill green" style={{ width: barPct(data.completed_migrations) }} />
              </div>
              <span className="migration-status-count">{data.completed_migrations}</span>
            </div>
            <div className="migration-status-row">
              <span className="migration-status-label">{t('dashboard.running')}</span>
              <div className="migration-status-bar-bg">
                <div className="migration-status-bar-fill blue" style={{ width: barPct(data.running_migrations) }} />
              </div>
              <span className="migration-status-count">{data.running_migrations}</span>
            </div>
            <div className="migration-status-row">
              <span className="migration-status-label">{t('dashboard.failed')}</span>
              <div className="migration-status-bar-bg">
                <div className="migration-status-bar-fill red" style={{ width: barPct(data.failed_migrations) }} />
              </div>
              <span className="migration-status-count">{data.failed_migrations}</span>
            </div>
            <div className="migration-status-row">
              <span className="migration-status-label">{t('dashboard.scheduled')}</span>
              <div className="migration-status-bar-bg">
                <div className="migration-status-bar-fill yellow" style={{ width: barPct(data.scheduled_migrations) }} />
              </div>
              <span className="migration-status-count">{data.scheduled_migrations}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="dashboard-recent">
        <div className="recent-header">
          <h3 className="dash-section-title">{t('dashboard.recentActivity')}</h3>
          <div className="recent-tabs">
            <button
              className={`recent-tab ${recentTab === 'assessments' ? 'active' : ''}`}
              onClick={() => setRecentTab('assessments')}
            >
              {t('dashboard.assessments')}
            </button>
            <button
              className={`recent-tab ${recentTab === 'migrations' ? 'active' : ''}`}
              onClick={() => setRecentTab('migrations')}
            >
              {t('dashboard.migrations')}
            </button>
            <button
              className={`recent-tab ${recentTab === 'copies' ? 'active' : ''}`}
              onClick={() => setRecentTab('copies')}
            >
              {t('dashboard.copyHistory')}
            </button>
          </div>
        </div>

        {recentItems.length === 0 ? (
          <div className="recent-empty">{t('dashboard.noRecentActivity')}</div>
        ) : (
          <div className="recent-table-container">
            <table className="recent-table">
              <thead>
                <tr>
                  {recentTab === 'assessments' && (
                    <>
                      <th>{t('dashboard.name')}</th>
                      <th>{t('dashboard.status')}</th>
                      <th>{t('dashboard.tables')}</th>
                      <th>{t('dashboard.size')}</th>
                      <th>{t('dashboard.started')}</th>
                    </>
                  )}
                  {recentTab === 'migrations' && (
                    <>
                      <th>{t('dashboard.name')}</th>
                      <th>{t('dashboard.status')}</th>
                      <th>{t('dashboard.pathway')}</th>
                      <th>{t('dashboard.created')}</th>
                    </>
                  )}
                  {recentTab === 'copies' && (
                    <>
                      <th>{t('dashboard.table')}</th>
                      <th>{t('dashboard.status')}</th>
                      <th>{t('dashboard.rows')}</th>
                      <th>{t('dashboard.started')}</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {recentTab === 'assessments' && recentItems.map((item: any) => (
                  <tr key={item.id} className="clickable-row" onClick={() => navigate(`/assessments/${item.id}/report`)}>
                    <td className="font-medium">{item.name}</td>
                    <td><span className={`recent-status ${item.status?.toLowerCase()}`}>{item.status}</span></td>
                    <td>{item.total_tables ?? 0}</td>
                    <td>{formatSize(item.total_size_mb ?? 0)}</td>
                    <td className="text-muted">{formatTimestamp(item.started_at)}</td>
                  </tr>
                ))}
                {recentTab === 'migrations' && recentItems.map((item: any) => (
                  <tr key={item.id}>
                    <td className="font-medium">{item.name}</td>
                    <td><span className={`recent-status ${item.status?.toLowerCase()}`}>{item.status}</span></td>
                    <td>Path {item.pathway}</td>
                    <td className="text-muted">{formatTimestamp(item.created_at)}</td>
                  </tr>
                ))}
                {recentTab === 'copies' && recentItems.map((item: any) => (
                  <tr key={item.id}>
                    <td className="font-medium">{item.table_name}</td>
                    <td><span className={`recent-status ${item.status?.toLowerCase()}`}>{item.status}</span></td>
                    <td>{(item.rows_loaded ?? 0).toLocaleString()}</td>
                    <td className="text-muted">{formatTimestamp(item.started_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
