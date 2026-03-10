import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import './WorkspacesPage.css';

interface WorkspaceStats {
  connections: number;
  assessments: number;
  migrations: number;
  conversions: number;
  members: number;
}

interface Workspace {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  organization_id: number;
  role: string;
  created_at: string | null;
  is_active: boolean;
  stats: WorkspaceStats;
}

interface MigrationItem {
  id: number;
  name: string;
  pathway: string;
  status: string;
  current_stage: string | null;
  progress: number;
  source_dataset: string | null;
  target_schema: string | null;
  total_rows_source: number;
  total_rows_target: number;
  created_at: string | null;
  start_time: string | null;
  end_time: string | null;
  duration_seconds: number | null;
}

interface AnalysisData {
  workspace_id: number;
  overview: {
    source_type: string;
    target_type: string;
    total_connections: number;
    source_connections: number;
    target_connections: number;
    total_assessments: number;
    completed_assessments: number;
    total_migrations: number;
  };
  size_breakdown: {
    total_size_mb: number;
    data_size_mb: number;
    index_size_mb: number;
    storage_size_mb: number;
  };
  stats: {
    datasets: number;
    tables: number;
    views: number;
    routines: number;
    total_records: number;
  };
  top_tables: { name: string; dataset: string; row_count: number; size_mb: number }[];
  recent_assessments: { id: number; name: string; status: string; total_tables: number; total_size_mb: number; started_at: string | null }[];
  recent_migrations: MigrationItem[];
  connections: {
    source: { id: number; name: string; database: string; status: string }[];
    target: { id: number; name: string; database: string; status: string }[];
  };
}

type TabId = 'overview' | 'assessments' | 'migrations' | 'connections';

export const WorkspacesPage: React.FC = () => {
  const navigate = useNavigate();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedWs, setSelectedWs] = useState<Workspace | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisData | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [searchQuery, setSearchQuery] = useState('');
  const [pinnedIds, setPinnedIds] = useState<Set<number>>(() => {
    try {
      const saved = localStorage.getItem('datamiq_pinned_workspaces');
      return saved ? new Set(JSON.parse(saved)) : new Set<number>();
    } catch { return new Set<number>(); }
  });
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['pinned']));

  useEffect(() => {
    const fetchWorkspaces = async () => {
      try {
        const data = await api.get<Workspace[]>('/api/workspaces/');
        setWorkspaces(data);
        if (data.length > 0 && !selectedWs) {
          setSelectedWs(data[0]);
          setExpandedSections(prev => new Set([...prev, `ws-${data[0].id}`]));
        }
      } catch (err) {
        console.error('Failed to load workspaces:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchWorkspaces();
  }, []);

  useEffect(() => {
    if (selectedWs) {
      const fetchAnalysis = async () => {
        setAnalysisLoading(true);
        try {
          const data = await api.get<AnalysisData>(`/api/workspaces/${selectedWs.id}/analysis`);
          setAnalysis(data);
        } catch (err) {
          console.error('Failed to load analysis:', err);
        } finally {
          setAnalysisLoading(false);
        }
      };
      fetchAnalysis();
    }
  }, [selectedWs]);

  const togglePin = (id: number) => {
    setPinnedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      localStorage.setItem('datamiq_pinned_workspaces', JSON.stringify([...next]));
      return next;
    });
  };

  const toggleSection = (section: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev);
      if (next.has(section)) next.delete(section); else next.add(section);
      return next;
    });
  };

  const filteredWorkspaces = workspaces.filter(ws =>
    ws.name.toLowerCase().includes(searchQuery.toLowerCase())
  );
  const pinnedWorkspaces = filteredWorkspaces.filter(ws => pinnedIds.has(ws.id));

  const formatSize = (mb: number) => {
    if (!mb || mb === 0) return '0.00 MB';
    if (mb >= 1024) return `${(mb / 1024).toFixed(2)} GB`;
    return `${mb.toFixed(2)} MB`;
  };

  const formatNumber = (n: number) => {
    if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
    if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
    return n.toLocaleString();
  };

  if (loading) {
    return (
      <div className="ws-page">
        <div className="ws-loading"><span className="ws-spinner" /> Loading workspaces...</div>
      </div>
    );
  }

  return (
    <div className="ws-page">
      {/* Left Sidebar Panel */}
      <div className="ws-sidebar-panel">
        <div className="ws-sidebar-header">
          <div className="ws-sidebar-title-row">
            <h2 className="ws-sidebar-title">Your Workspaces</h2>
            <button className="ws-sidebar-new-btn" title="Create workspace">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M8 3v10M3 8h10" strokeLinecap="round" />
              </svg>
            </button>
          </div>

          {/* Pinned Section */}
          <div className="ws-pinned-section">
            <button className="ws-section-toggle" onClick={() => toggleSection('pinned')}>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2"
                style={{ transform: expandedSections.has('pinned') ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.15s' }}>
                <path d="M4 2l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <span>Pinned</span>
            </button>
            {expandedSections.has('pinned') && (
              <div className="ws-pinned-list">
                {pinnedWorkspaces.length === 0 ? (
                  <div className="ws-pinned-empty">No pinned workspaces</div>
                ) : (
                  pinnedWorkspaces.map(ws => (
                    <button key={ws.id} className={`ws-tree-item ${selectedWs?.id === ws.id ? 'active' : ''}`}
                      onClick={() => setSelectedWs(ws)}>
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M8 1l2 5h5l-4 3 1.5 5L8 11l-4.5 3L5 9 1 6h5z" /></svg>
                      <span>{ws.name}</span>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>

          {/* Search */}
          <div className="ws-search-box">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="#9CA3AF" strokeWidth="2">
              <circle cx="7" cy="7" r="5" /><path d="M11 11l3 3" strokeLinecap="round" />
            </svg>
            <input type="text" placeholder="Search workspaces" value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)} className="ws-search-input" />
          </div>
        </div>

        {/* Workspace Tree */}
        <div className="ws-tree">
          {filteredWorkspaces.map(ws => (
            <div key={ws.id} className="ws-tree-workspace">
              <div className={`ws-tree-ws-header ${selectedWs?.id === ws.id ? 'active' : ''}`}>
                <button className="ws-tree-ws-toggle" onClick={() => { setSelectedWs(ws); toggleSection(`ws-${ws.id}`); }}>
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2"
                    style={{ transform: expandedSections.has(`ws-${ws.id}`) ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.15s' }}>
                    <path d="M4 2l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M2 5h12M2 5l1.5-3h9l1.5 3M2 5v7a1.5 1.5 0 001.5 1.5h9A1.5 1.5 0 0014 12V5" />
                  </svg>
                  <span className="ws-tree-ws-name">{ws.name}</span>
                </button>
                <button className={`ws-pin-btn ${pinnedIds.has(ws.id) ? 'pinned' : ''}`}
                  onClick={e => { e.stopPropagation(); togglePin(ws.id); }} title={pinnedIds.has(ws.id) ? 'Unpin' : 'Pin'}>
                  <svg width="12" height="12" viewBox="0 0 16 16" fill={pinnedIds.has(ws.id) ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.5">
                    <path d="M8 1l2 5h5l-4 3 1.5 5L8 11l-4.5 3L5 9 1 6h5z" />
                  </svg>
                </button>
              </div>

              {expandedSections.has(`ws-${ws.id}`) && (
                <div className="ws-tree-children">
                  <button className="ws-tree-child" onClick={() => navigate('/connections')}>
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <circle cx="4" cy="8" r="2" /><circle cx="12" cy="8" r="2" /><path d="M6 8h4" />
                    </svg>
                    Source Connections
                  </button>
                  <button className="ws-tree-child" onClick={() => navigate('/connections')}>
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <circle cx="4" cy="8" r="2" /><circle cx="12" cy="8" r="2" /><path d="M6 8h4" />
                    </svg>
                    Target Connections
                  </button>
                  <button className="ws-tree-child" onClick={() => navigate('/assessments')}>
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M8 2L3 5v3c0 3 2 5 5 5.5 3-.5 5-2.5 5-5.5V5l-5-3z" />
                    </svg>
                    Assessments
                  </button>
                  <button className="ws-tree-child" onClick={() => navigate('/assessments/compatibility')}>
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M2 12l4-4 3 3 5-5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    Compatibility Check
                  </button>
                  <button className="ws-tree-child" onClick={() => navigate('/converter')}>
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M5 4L2 8l3 4M11 4l3 4-3 4M9 2L7 14" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    Code Converter
                  </button>
                  <button className="ws-tree-child" onClick={() => navigate('/migrations')}>
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M2 8h12M11 5l3 3-3 3" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    Migration Jobs
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Right Content Panel */}
      <div className="ws-content-panel">
        {!selectedWs ? (
          <div className="ws-empty-state">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="#D1D5DB" strokeWidth="1.5">
              <path d="M6 18h36M6 18l6-12h24l6 12M6 18v24a3 3 0 003 3h30a3 3 0 003-3V18" />
            </svg>
            <p>Select a workspace to view analysis</p>
          </div>
        ) : (
          <>
            {/* Breadcrumb + Actions */}
            <div className="ws-content-header">
              <div className="ws-breadcrumb">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M2 5h12M2 5l1.5-3h9l1.5 3M2 5v7a1.5 1.5 0 001.5 1.5h9A1.5 1.5 0 0014 12V5" />
                </svg>
                <span className="ws-breadcrumb-ws">{selectedWs.name}</span>
                <span className="ws-breadcrumb-sep">/</span>
                <span className="ws-breadcrumb-page">Database Analysis</span>
              </div>
              <div className="ws-content-actions">
                <button className="ws-action-btn" onClick={() => navigate('/assessments')}>
                  <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M4 2h8a1 1 0 011 1v10a1 1 0 01-1 1H4a1 1 0 01-1-1V3a1 1 0 011-1z" />
                    <path d="M6 6h4M6 9h4" strokeLinecap="round" />
                  </svg>
                  Report
                </button>
                <button className="ws-action-btn primary" onClick={() => {
                  if (selectedWs) {
                    setAnalysisLoading(true);
                    api.get<AnalysisData>(`/api/workspaces/${selectedWs.id}/analysis`).then(data => {
                      setAnalysis(data);
                      setAnalysisLoading(false);
                    }).catch(() => setAnalysisLoading(false));
                  }
                }}>
                  <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M2 8a6 6 0 0111.5-2.5M14 8a6 6 0 01-11.5 2.5" strokeLinecap="round" />
                    <path d="M14 2v4h-4" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  Re-analyze
                </button>
              </div>
            </div>

            {/* Tabs */}
            <div className="ws-tabs">
              {([
                { id: 'overview' as TabId, label: 'Overview' },
                { id: 'assessments' as TabId, label: 'Assessments' },
                { id: 'migrations' as TabId, label: 'Migrations' },
                { id: 'connections' as TabId, label: 'Connections' },
              ]).map(tab => (
                <button key={tab.id} className={`ws-tab ${activeTab === tab.id ? 'active' : ''}`}
                  onClick={() => setActiveTab(tab.id)}>{tab.label}</button>
              ))}
            </div>

            {/* Tab Content */}
            <div className="ws-tab-content">
              {analysisLoading ? (
                <div className="ws-loading"><span className="ws-spinner" /> Loading analysis...</div>
              ) : activeTab === 'overview' ? (
                <OverviewTab analysis={analysis} formatSize={formatSize} formatNumber={formatNumber} />
              ) : activeTab === 'assessments' ? (
                <AssessmentsTab analysis={analysis} navigate={navigate} />
              ) : activeTab === 'migrations' ? (
                <MigrationsTab analysis={analysis} navigate={navigate} />
              ) : (
                <ConnectionsTab analysis={analysis} navigate={navigate} />
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
};


/* ===== Overview Tab ===== */
const OverviewTab: React.FC<{ analysis: AnalysisData | null; formatSize: (n: number) => string; formatNumber: (n: number) => string }> = ({ analysis, formatSize, formatNumber }) => {
  if (!analysis) return <div className="ws-empty-tab">No analysis data available. Click Re-analyze to start.</div>;

  const ov = analysis.overview;
  const sz = analysis.size_breakdown;
  const st = analysis.stats;
  const total = sz.total_size_mb || 1;
  const dataPct = ((sz.data_size_mb / total) * 100).toFixed(1);
  const indexPct = ((sz.index_size_mb / total) * 100).toFixed(1);
  const storagePct = ((sz.storage_size_mb / total) * 100).toFixed(1);
  const maxRows = Math.max(...(analysis.top_tables.map(t => t.row_count) || [1]), 1);

  return (
    <div className="ws-overview">
      <div className="ws-overview-top">
        <div className="ws-info-cards">
          {[
            { label: 'SOURCE TYPE', value: ov.source_type, icon: '📊' },
            { label: 'TARGET TYPE', value: ov.target_type, icon: '🗄️' },
            { label: 'CONNECTIONS', value: String(ov.total_connections), icon: '🔗' },
            { label: 'ASSESSMENTS', value: String(ov.total_assessments), icon: '🛡️' },
          ].map((card, i) => (
            <div key={i} className="ws-info-card">
              <div className="ws-info-label">{card.label}</div>
              <div className="ws-info-value"><span>{card.icon}</span> {card.value}</div>
            </div>
          ))}
        </div>

        <div className="ws-donut-section">
          <svg viewBox="0 0 120 120" className="ws-donut-chart">
            <circle cx="60" cy="60" r="50" fill="none" stroke="#E5E7EB" strokeWidth="12" />
            <circle cx="60" cy="60" r="50" fill="none" stroke="#3B82F6" strokeWidth="12"
              strokeDasharray={`${(sz.data_size_mb / total) * 314} 314`} strokeDashoffset="0"
              transform="rotate(-90 60 60)" strokeLinecap="round" />
            <circle cx="60" cy="60" r="50" fill="none" stroke="#10B981" strokeWidth="12"
              strokeDasharray={`${(sz.index_size_mb / total) * 314} 314`}
              strokeDashoffset={`${-(sz.data_size_mb / total) * 314}`}
              transform="rotate(-90 60 60)" strokeLinecap="round" />
            <circle cx="60" cy="60" r="50" fill="none" stroke="#F59E0B" strokeWidth="12"
              strokeDasharray={`${(sz.storage_size_mb / total) * 314} 314`}
              strokeDashoffset={`${-((sz.data_size_mb + sz.index_size_mb) / total) * 314}`}
              transform="rotate(-90 60 60)" strokeLinecap="round" />
            <text x="60" y="55" textAnchor="middle" className="ws-donut-label">Total Size</text>
            <text x="60" y="72" textAnchor="middle" className="ws-donut-value">{formatSize(sz.total_size_mb)}</text>
          </svg>
          <div className="ws-donut-legend">
            <div className="ws-legend-item"><span className="ws-legend-dot" style={{ background: '#3B82F6' }} />Data Size <span className="ws-legend-val">{formatSize(sz.data_size_mb)}</span> <span className="ws-legend-pct">{dataPct}%</span></div>
            <div className="ws-legend-item"><span className="ws-legend-dot" style={{ background: '#10B981' }} />Index Size <span className="ws-legend-val">{formatSize(sz.index_size_mb)}</span> <span className="ws-legend-pct">{indexPct}%</span></div>
            <div className="ws-legend-item"><span className="ws-legend-dot" style={{ background: '#F59E0B' }} />Storage Size <span className="ws-legend-val">{formatSize(sz.storage_size_mb)}</span> <span className="ws-legend-pct">{storagePct}%</span></div>
          </div>
        </div>

        <div className="ws-stat-cards">
          {[
            { label: 'DATASETS', value: st.datasets, color: 'blue' },
            { label: 'TABLES', value: st.tables, color: 'green' },
            { label: 'TOTAL RECORDS', value: formatNumber(st.total_records), color: 'purple' },
          ].map((card, i) => (
            <div key={i} className="ws-stat-card">
              <div className={`ws-stat-icon ${card.color}`}>
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <rect x="3" y="3" width="14" height="14" rx="2" /><path d="M3 7h14M7 7v10" strokeLinecap="round" />
                </svg>
              </div>
              <div className="ws-stat-label">{card.label}</div>
              <div className="ws-stat-value">{card.value}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="ws-chart-section">
        <div className="ws-chart-header"><h3 className="ws-chart-title">Top Tables by Row Count</h3></div>
        {analysis.top_tables.length === 0 ? (
          <div className="ws-chart-empty">No table data available. Run an assessment to populate.</div>
        ) : (
          <div className="ws-bar-chart">
            {analysis.top_tables.map((t, i) => (
              <div key={i} className="ws-bar-item">
                <div className="ws-bar-fill" style={{ height: `${Math.max((t.row_count / maxRows) * 100, 4)}%` }}>
                  <span className="ws-bar-value">{formatNumber(t.row_count)}</span>
                </div>
                <div className="ws-bar-label" title={`${t.dataset}.${t.name}`}>{t.name}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};


/* ===== Assessments Tab ===== */
const AssessmentsTab: React.FC<{ analysis: AnalysisData | null; navigate: (path: string) => void }> = ({ analysis, navigate }) => {
  if (!analysis || analysis.recent_assessments.length === 0) {
    return (
      <div className="ws-empty-tab">
        <p>No assessments found.</p>
        <button className="ws-action-btn primary" onClick={() => navigate('/assessments')}>Go to Assessments</button>
      </div>
    );
  }
  return (
    <div className="ws-table-section">
      <table className="ws-data-table">
        <thead>
          <tr><th>Name</th><th>Status</th><th>Tables</th><th>Size</th><th>Started</th></tr>
        </thead>
        <tbody>
          {analysis.recent_assessments.map(a => (
            <tr key={a.id} className="ws-table-row-clickable" onClick={() => navigate(`/assessments/${a.id}/report`)}>
              <td className="ws-td-name">{a.name}</td>
              <td><span className={`ws-status-badge ${a.status}`}>{a.status}</span></td>
              <td>{a.total_tables}</td>
              <td>{a.total_size_mb ? `${a.total_size_mb} MB` : '—'}</td>
              <td>{a.started_at ? new Date(a.started_at).toLocaleDateString() : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <button className="ws-view-all-btn" onClick={() => navigate('/assessments')}>View all assessments →</button>
    </div>
  );
};

/* ===== Migrations Tab ===== */
const MigrationsTab: React.FC<{ analysis: AnalysisData | null; navigate: (path: string) => void }> = ({ analysis, navigate }) => {
  const migrations = analysis?.recent_migrations || [];

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return '—';
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  };

  if (migrations.length === 0) {
    return (
      <div className="ws-empty-tab">
        <p>No migrations found in this workspace.</p>
        <button className="ws-action-btn primary" onClick={() => navigate('/migrations')}>Go to Migrations</button>
      </div>
    );
  }

  return (
    <div className="ws-table-section">
      <div className="ws-migration-summary">
        <div className="ws-mig-stat">
          <span className="ws-mig-stat-value">{migrations.length}</span>
          <span className="ws-mig-stat-label">Total</span>
        </div>
        <div className="ws-mig-stat">
          <span className="ws-mig-stat-value ws-mig-completed">{migrations.filter(m => m.status === 'completed').length}</span>
          <span className="ws-mig-stat-label">Completed</span>
        </div>
        <div className="ws-mig-stat">
          <span className="ws-mig-stat-value ws-mig-running">{migrations.filter(m => m.status === 'running').length}</span>
          <span className="ws-mig-stat-label">Running</span>
        </div>
        <div className="ws-mig-stat">
          <span className="ws-mig-stat-value ws-mig-failed">{migrations.filter(m => m.status === 'failed').length}</span>
          <span className="ws-mig-stat-label">Failed</span>
        </div>
      </div>

      <table className="ws-data-table">
        <thead>
          <tr>
            <th>Migration Name</th>
            <th>Pathway</th>
            <th>Status</th>
            <th>Stage</th>
            <th>Progress</th>
            <th>Source → Target</th>
            <th>Duration</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {migrations.map(m => (
            <tr key={m.id} className="ws-table-row-clickable" onClick={() => navigate('/migrations')}>
              <td className="ws-td-name">{m.name}</td>
              <td><span className="ws-pathway-badge">Path {m.pathway}</span></td>
              <td><span className={`ws-status-badge ${m.status}`}>{m.status}</span></td>
              <td>{m.current_stage || '—'}</td>
              <td>
                <div className="ws-progress-bar">
                  <div className="ws-progress-fill" style={{ width: `${m.progress}%` }} />
                  <span className="ws-progress-text">{m.progress}%</span>
                </div>
              </td>
              <td className="ws-td-route">{m.source_dataset || '—'} → {m.target_schema || '—'}</td>
              <td>{formatDuration(m.duration_seconds)}</td>
              <td>{m.created_at ? new Date(m.created_at).toLocaleDateString() : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <button className="ws-view-all-btn" onClick={() => navigate('/migrations')}>View all migrations →</button>
    </div>
  );
};

/* ===== Connections Tab ===== */
const ConnectionsTab: React.FC<{ analysis: AnalysisData | null; navigate: (path: string) => void }> = ({ analysis, navigate }) => {
  if (!analysis) return <div className="ws-empty-tab">No data available.</div>;
  const { source, target } = analysis.connections;
  return (
    <div className="ws-connections-tab">
      <div className="ws-conn-group">
        <h4 className="ws-conn-group-title">Source Connections ({source.length})</h4>
        {source.length === 0 ? <p className="ws-conn-empty">No source connections</p> : (
          <div className="ws-conn-list">
            {source.map(c => (
              <div key={c.id} className="ws-conn-card">
                <div className="ws-conn-icon source">S</div>
                <div className="ws-conn-info">
                  <div className="ws-conn-name">{c.name}</div>
                  <div className="ws-conn-db">{c.database}</div>
                </div>
                <span className={`ws-status-badge ${c.status}`}>{c.status}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="ws-conn-group">
        <h4 className="ws-conn-group-title">Target Connections ({target.length})</h4>
        {target.length === 0 ? <p className="ws-conn-empty">No target connections</p> : (
          <div className="ws-conn-list">
            {target.map(c => (
              <div key={c.id} className="ws-conn-card">
                <div className="ws-conn-icon target">T</div>
                <div className="ws-conn-info">
                  <div className="ws-conn-name">{c.name}</div>
                  <div className="ws-conn-db">{c.database}</div>
                </div>
                <span className={`ws-status-badge ${c.status}`}>{c.status}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <button className="ws-view-all-btn" onClick={() => navigate('/connections')}>Manage all connections →</button>
    </div>
  );
};
