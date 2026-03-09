import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
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
          Loading dashboard...
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="dashboard-page">
        <div className="dashboard-header">
          <h1 className="dashboard-title">Dashboard</h1>
        </div>
        <div className="dashboard-loading">Failed to load dashboard data.</div>
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
        <h1 className="dashboard-title">
          <svg width="22" height="22" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
            <rect x="3" y="3" width="6" height="6" rx="1" />
            <rect x="11" y="3" width="6" height="6" rx="1" />
            <rect x="3" y="11" width="6" height="6" rx="1" />
            <rect x="11" y="11" width="6" height="6" rx="1" />
          </svg>
          Dashboard
        </h1>
        <p className="dashboard-subtitle">Overview of your migration platform</p>
      </div>

      {/* Summary Cards */}
      <div className="dashboard-cards">
        {/* Connections Card */}
        <div className="dash-card" onClick={() => navigate('/connections')}>
          <div className="dash-card-icon blue">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M17 21v-2a1 1 0 0 1-1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1" />
              <path d="M7 21v-2a1 1 0 0 0 1-1v-1a1 1 0 0 0-1-1H6a1 1 0 0 0-1 1v1a1 1 0 0 0 1 1" />
              <path d="M17 14V3" /><path d="M7 14V3" />
              <path d="M17 3H7" /><path d="M17 8H7" />
            </svg>
          </div>
          <div className="dash-card-content">
            <div className="dash-card-label">Connections</div>
            <div className="dash-card-value">{data.total_connections}</div>
            <div className="dash-card-detail">
              <span><span className="dash-detail-dot green" /> {data.connected_count} connected</span>
              <span>{data.source_connections} src / {data.target_connections} tgt</span>
            </div>
          </div>
        </div>

        {/* Assessments Card */}
        <div className="dash-card" onClick={() => navigate('/assessments')}>
          <div className="dash-card-icon green">
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M9 2L3 6v4c0 4.5 3 7.5 6 8 3-.5 6-3.5 6-8V6l-6-4z" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M7 10l2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <div className="dash-card-content">
            <div className="dash-card-label">Assessments</div>
            <div className="dash-card-value">{data.total_assessments}</div>
            <div className="dash-card-detail">
              <span><span className="dash-detail-dot green" /> {data.completed_assessments} done</span>
              {data.running_assessments > 0 && <span><span className="dash-detail-dot blue" /> {data.running_assessments} running</span>}
              {data.failed_assessments > 0 && <span><span className="dash-detail-dot red" /> {data.failed_assessments} failed</span>}
            </div>
          </div>
        </div>

        {/* Migrations Card */}
        <div className="dash-card" onClick={() => navigate('/migrations')}>
          <div className="dash-card-icon purple">
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M3 10h14M14 6l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <div className="dash-card-content">
            <div className="dash-card-label">Migrations</div>
            <div className="dash-card-value">{data.total_migrations}</div>
            <div className="dash-card-detail">
              <span><span className="dash-detail-dot green" /> {data.completed_migrations} done</span>
              {data.running_migrations > 0 && <span><span className="dash-detail-dot blue" /> {data.running_migrations} running</span>}
              {data.scheduled_migrations > 0 && <span><span className="dash-detail-dot yellow" /> {data.scheduled_migrations} scheduled</span>}
            </div>
          </div>
        </div>

        {/* Code Conversions Card */}
        <div className="dash-card" onClick={() => navigate('/converter')}>
          <div className="dash-card-icon orange">
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M7 5L3 10l4 5" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M13 5l4 5-4 5" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M11 3L9 17" strokeLinecap="round" />
            </svg>
          </div>
          <div className="dash-card-content">
            <div className="dash-card-label">Code Conversions</div>
            <div className="dash-card-value">{data.total_jobs}</div>
            <div className="dash-card-detail">
              <span><span className="dash-detail-dot green" /> {data.completed_jobs} done</span>
              {data.failed_jobs > 0 && <span><span className="dash-detail-dot red" /> {data.failed_jobs} failed</span>}
              <span>{data.total_batches} batches</span>
            </div>
          </div>
        </div>
      </div>

      {/* Middle Row */}
      <div className="dashboard-mid-row">
        {/* Assessment Discovery */}
        <div className="dash-section">
          <div className="dash-section-header">
            <h3 className="dash-section-title">Assessment Discovery</h3>
            <a className="dash-section-link" onClick={() => navigate('/assessments')}>View All</a>
          </div>
          <div className="discovery-stats">
            <div className="discovery-stat">
              <div className="discovery-stat-value">{data.total_tables_discovered.toLocaleString()}</div>
              <div className="discovery-stat-label">Tables</div>
            </div>
            <div className="discovery-stat">
              <div className="discovery-stat-value">{data.total_views_discovered.toLocaleString()}</div>
              <div className="discovery-stat-label">Views</div>
            </div>
            <div className="discovery-stat">
              <div className="discovery-stat-value">{data.total_routines_discovered.toLocaleString()}</div>
              <div className="discovery-stat-label">Routines</div>
            </div>
          </div>
          {data.total_size_mb > 0 && (
            <div style={{ textAlign: 'center', marginTop: 12, fontSize: 13, color: '#6B7280' }}>
              Total data volume: <strong style={{ color: '#111827' }}>{formatSize(data.total_size_mb)}</strong>
            </div>
          )}
        </div>

        {/* Migration Status */}
        <div className="dash-section">
          <div className="dash-section-header">
            <h3 className="dash-section-title">Migration Status</h3>
            <a className="dash-section-link" onClick={() => navigate('/migrations')}>View All</a>
          </div>
          <div className="migration-status-list">
            <div className="migration-status-row">
              <span className="migration-status-label">Completed</span>
              <div className="migration-status-bar-bg">
                <div className="migration-status-bar-fill green" style={{ width: barPct(data.completed_migrations) }} />
              </div>
              <span className="migration-status-count">{data.completed_migrations}</span>
            </div>
            <div className="migration-status-row">
              <span className="migration-status-label">Running</span>
              <div className="migration-status-bar-bg">
                <div className="migration-status-bar-fill blue" style={{ width: barPct(data.running_migrations) }} />
              </div>
              <span className="migration-status-count">{data.running_migrations}</span>
            </div>
            <div className="migration-status-row">
              <span className="migration-status-label">Failed</span>
              <div className="migration-status-bar-bg">
                <div className="migration-status-bar-fill red" style={{ width: barPct(data.failed_migrations) }} />
              </div>
              <span className="migration-status-count">{data.failed_migrations}</span>
            </div>
            <div className="migration-status-row">
              <span className="migration-status-label">Scheduled</span>
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
        <div className="dash-section-header">
          <h3 className="dash-section-title">Recent Activity</h3>
        </div>
        <div className="recent-tabs">
          <button
            className={`recent-tab ${recentTab === 'assessments' ? 'active' : ''}`}
            onClick={() => setRecentTab('assessments')}
          >
            Assessments
          </button>
          <button
            className={`recent-tab ${recentTab === 'migrations' ? 'active' : ''}`}
            onClick={() => setRecentTab('migrations')}
          >
            Migrations
          </button>
          <button
            className={`recent-tab ${recentTab === 'copies' ? 'active' : ''}`}
            onClick={() => setRecentTab('copies')}
          >
            Copy History
          </button>
        </div>

        {recentItems.length === 0 ? (
          <div className="recent-empty">No recent activity</div>
        ) : (
          <table className="recent-table">
            <thead>
              <tr>
                {recentTab === 'assessments' && (
                  <>
                    <th>Name</th>
                    <th>Status</th>
                    <th>Tables</th>
                    <th>Size</th>
                    <th>Started</th>
                  </>
                )}
                {recentTab === 'migrations' && (
                  <>
                    <th>Name</th>
                    <th>Status</th>
                    <th>Pathway</th>
                    <th>Created</th>
                  </>
                )}
                {recentTab === 'copies' && (
                  <>
                    <th>Table</th>
                    <th>Status</th>
                    <th>Rows</th>
                    <th>Started</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {recentTab === 'assessments' && recentItems.map((item: any) => (
                <tr key={item.id} style={{ cursor: 'pointer' }} onClick={() => navigate(`/assessments/${item.id}/report`)}>
                  <td>{item.name}</td>
                  <td><span className={`recent-status ${item.status}`}>{item.status}</span></td>
                  <td>{item.total_tables ?? 0}</td>
                  <td>{formatSize(item.total_size_mb ?? 0)}</td>
                  <td>{formatTimestamp(item.started_at)}</td>
                </tr>
              ))}
              {recentTab === 'migrations' && recentItems.map((item: any) => (
                <tr key={item.id}>
                  <td>{item.name}</td>
                  <td><span className={`recent-status ${item.status}`}>{item.status}</span></td>
                  <td>Path {item.pathway}</td>
                  <td>{formatTimestamp(item.created_at)}</td>
                </tr>
              ))}
              {recentTab === 'copies' && recentItems.map((item: any) => (
                <tr key={item.id}>
                  <td>{item.table_name}</td>
                  <td><span className={`recent-status ${item.status}`}>{item.status}</span></td>
                  <td>{(item.rows_loaded ?? 0).toLocaleString()}</td>
                  <td>{formatTimestamp(item.started_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
