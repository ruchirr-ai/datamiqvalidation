import React, { useState, useEffect, useRef } from 'react';
import {
  Database, Table2, Columns, Eye, Code2, Search,
  ChevronDown, ChevronRight, Loader,
  XCircle, BarChart3, Lock, Grid3X3, Layers
} from 'lucide-react';
import { Select } from '../../components/ui';
import {
  listAssessments, Assessment,
  getSchemaAnalysis, SchemaAnalysisData, SchemaTable
} from '../../services/assessmentsApi';
import './AssessmentsPage.css';
import './SchemaAnalysisPage.css';

export const SchemaAnalysisPage: React.FC = () => {
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [selectedAssessmentId, setSelectedAssessmentId] = useState<number | ''>('');
  const [loading, setLoading] = useState(false);
  const [loadingAssessments, setLoadingAssessments] = useState(true);
  const [data, setData] = useState<SchemaAnalysisData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState<'datasets' | 'tables' | 'views' | 'routines' | 'types'>('datasets');
  const [expandedDatasets, setExpandedDatasets] = useState<Record<string, boolean>>({});
  const [selectedTable, setSelectedTable] = useState<SchemaTable | null>(null);
  const hasFetched = useRef(false);

  useEffect(() => {
    if (!hasFetched.current) {
      hasFetched.current = true;
      fetchAssessments();
    }
  }, []);

  const fetchAssessments = async () => {
    try {
      setLoadingAssessments(true);
      const res = await listAssessments();
      setAssessments(res.assessments.filter(a => a.status === 'completed'));
    } catch {
      // silent
    } finally {
      setLoadingAssessments(false);
    }
  };

  const handleAnalyze = async () => {
    if (!selectedAssessmentId) return;
    try {
      setLoading(true);
      setError(null);
      setData(null);
      setSelectedTable(null);
      const result = await getSchemaAnalysis(selectedAssessmentId as number);
      setData(result);
      // Auto-expand first dataset
      if (result.datasets.length > 0) {
        setExpandedDatasets({ [result.datasets[0].name]: true });
      }
    } catch (err: any) {
      setError(err.detail || err.message || 'Failed to load schema analysis');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedAssessmentId) {
      handleAnalyze();
    } else {
      setData(null);
      setSelectedTable(null);
    }
  }, [selectedAssessmentId]);

  const toggleDataset = (name: string) => {
    setExpandedDatasets(prev => ({ ...prev, [name]: !prev[name] }));
  };

  const formatSize = (mb: number) => {
    if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`;
    if (mb >= 1) return `${mb.toFixed(1)} MB`;
    return `${(mb * 1024).toFixed(0)} KB`;
  };

  const formatRows = (n: number) => {
    if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`;
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
    return n.toString();
  };

  // Filter tables by search
  const filteredTables = data?.tables.filter(t => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return t.full_name.toLowerCase().includes(q) ||
      t.columns.some(c => c.name.toLowerCase().includes(q) || c.data_type.toLowerCase().includes(q));
  }) || [];

  const filteredViews = data?.views.filter(v => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return v.name.toLowerCase().includes(q) || (v.dataset || '').toLowerCase().includes(q);
  }) || [];

  const filteredRoutines = data?.routines.filter(r => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return r.name.toLowerCase().includes(q) || r.type.toLowerCase().includes(q);
  }) || [];

  const assessmentOptions = assessments.map(a => ({
    value: a.id,
    label: `${a.name} (${a.total_tables} tables, ${a.total_size_mb.toFixed(1)} MB)`,
  }));

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Schema Analysis</h1>
        <p className="page-description">
          Analyze source database schemas — tables, columns, data types, partitioning, clustering, and relationships
        </p>
      </div>

      <div className="page-content">
        {/* Selection Panel */}
        <div className="schema-selection-panel">
          <div className="schema-selection-row">
            <div className="schema-select-group">
              <label>Select Completed Assessment</label>
              {loadingAssessments ? (
                <div className="schema-loading-inline"><Loader size={16} className="spin" /> Loading assessments...</div>
              ) : (
                <Select
                  value={selectedAssessmentId}
                  onChange={(val) => setSelectedAssessmentId(val as number)}
                  options={assessmentOptions}
                  disabled={loading}
                />
              )}
            </div>
          </div>
          {error && (
            <div className="schema-error">
              <XCircle size={16} /> {error}
            </div>
          )}
        </div>

        {/* Loading */}
        {loading && (
          <div className="schema-loading-state">
            <Loader size={24} className="spin" />
            <span>Analyzing schema...</span>
          </div>
        )}

        {/* Results */}
        {data && !loading && (
          <>
            {/* Summary Cards */}
            <div className="schema-summary-grid">
              {[
                { label: 'Datasets', value: data.summary.datasets, icon: <Database size={18} /> },
                { label: 'Tables', value: data.summary.tables, icon: <Table2 size={18} /> },
                { label: 'Columns', value: data.summary.columns, icon: <Columns size={18} /> },
                { label: 'Views', value: data.summary.views, icon: <Eye size={18} /> },
                { label: 'Routines', value: data.summary.routines, icon: <Code2 size={18} /> },
                { label: 'Total Rows', value: formatRows(data.summary.total_rows), icon: <Layers size={18} /> },
                { label: 'Total Size', value: formatSize(data.summary.total_size_mb), icon: <Database size={18} /> },
                { label: 'Partitioned', value: data.summary.partitioned_tables, icon: <Grid3X3 size={18} /> },
                { label: 'Clustered', value: data.summary.clustered_tables, icon: <BarChart3 size={18} /> },
                { label: 'Secured', value: data.summary.secured_tables, icon: <Lock size={18} /> },
              ].map(card => (
                <div key={card.label} className="schema-summary-card">
                  <div className="schema-summary-icon">{card.icon}</div>
                  <div className="schema-summary-value">{card.value}</div>
                  <div className="schema-summary-label">{card.label}</div>
                </div>
              ))}
            </div>

            {/* Tabs + Search */}
            <div className="schema-toolbar">
              <div className="schema-tabs">
                {[
                  { key: 'datasets' as const, label: 'Datasets', count: data.summary.datasets },
                  { key: 'tables' as const, label: 'Tables', count: data.summary.tables },
                  { key: 'views' as const, label: 'Views', count: data.summary.views },
                  { key: 'routines' as const, label: 'Routines', count: data.summary.routines },
                  { key: 'types' as const, label: 'Data Types', count: data.type_distribution.length },
                ].map(tab => (
                  <button
                    key={tab.key}
                    className={`schema-tab ${activeTab === tab.key ? 'active' : ''}`}
                    onClick={() => { setActiveTab(tab.key); setSelectedTable(null); }}
                  >
                    {tab.label} <span className="schema-tab-count">{tab.count}</span>
                  </button>
                ))}
              </div>
              {activeTab !== 'types' && (
                <div className="schema-search">
                  <Search size={16} />
                  <input
                    type="text"
                    placeholder={`Search ${activeTab}...`}
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                  />
                </div>
              )}
            </div>

            {/* Datasets Tab */}
            {activeTab === 'datasets' && (
              <div className="schema-datasets">
                {data.datasets.filter(d => !searchQuery || d.name.toLowerCase().includes(searchQuery.toLowerCase())).map(ds => (
                  <div key={ds.name} className="schema-dataset-card">
                    <button className="schema-dataset-header" onClick={() => toggleDataset(ds.name)}>
                      <div className="schema-dataset-title">
                        {expandedDatasets[ds.name] ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                        <Database size={16} />
                        <span className="schema-dataset-name">{ds.name}</span>
                        <span className="schema-dataset-meta">{ds.table_count} tables · {formatSize(ds.total_size_mb)}</span>
                        {ds.location && <span className="schema-dataset-location">{ds.location}</span>}
                      </div>
                    </button>
                    {expandedDatasets[ds.name] && (
                      <div className="schema-dataset-tables">
                        {data.tables.filter(t => t.dataset === ds.name).map(t => (
                          <button
                            key={t.id}
                            className={`schema-table-row ${selectedTable?.id === t.id ? 'selected' : ''}`}
                            onClick={() => setSelectedTable(selectedTable?.id === t.id ? null : t)}
                          >
                            <Table2 size={14} />
                            <span className="schema-table-name">{t.name}</span>
                            <span className="schema-table-info">
                              {t.column_count} cols · {formatRows(t.row_count)} rows · {formatSize(t.size_mb)}
                            </span>
                            <div className="schema-table-badges">
                              {t.partitioning_columns.length > 0 && <span className="schema-badge partition">P</span>}
                              {t.clustering_columns.length > 0 && <span className="schema-badge cluster">C</span>}
                              {(t.has_column_security || t.has_row_security) && <span className="schema-badge security">S</span>}
                              {t.is_sharded && <span className="schema-badge shard">SH</span>}
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Tables Tab */}
            {activeTab === 'tables' && (
              <div className="schema-tables-view">
                <div className="schema-table-wrapper">
                  <table className="schema-data-table">
                    <thead>
                      <tr>
                        <th>Table</th>
                        <th>Dataset</th>
                        <th>Type</th>
                        <th>Columns</th>
                        <th>Rows</th>
                        <th>Size</th>
                        <th>Features</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredTables.map(t => (
                        <tr
                          key={t.id}
                          className={`schema-clickable-row ${selectedTable?.id === t.id ? 'selected' : ''}`}
                          onClick={() => setSelectedTable(selectedTable?.id === t.id ? null : t)}
                        >
                          <td className="schema-cell-name">{t.name}</td>
                          <td className="schema-cell-secondary">{t.dataset}</td>
                          <td className="schema-cell-secondary">{t.type}</td>
                          <td>{t.column_count}</td>
                          <td>{formatRows(t.row_count)}</td>
                          <td>{formatSize(t.size_mb)}</td>
                          <td>
                            <div className="schema-table-badges">
                              {t.partitioning_columns.length > 0 && <span className="schema-badge partition" title={`Partitioned: ${t.partitioning_columns.join(', ')}`}>P</span>}
                              {t.clustering_columns.length > 0 && <span className="schema-badge cluster" title={`Clustered: ${t.clustering_columns.join(', ')}`}>C</span>}
                              {(t.has_column_security || t.has_row_security) && <span className="schema-badge security">S</span>}
                              {t.is_sharded && <span className="schema-badge shard">SH</span>}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {filteredTables.length === 0 && (
                    <div className="schema-no-results">No tables match your search</div>
                  )}
                </div>
              </div>
            )}

            {/* Table Detail Panel */}
            {selectedTable && (
              <div className="schema-detail-panel">
                <div className="schema-detail-header">
                  <div className="schema-detail-title">
                    <Table2 size={18} />
                    <span>{selectedTable.full_name}</span>
                  </div>
                  <button className="schema-detail-close" onClick={() => setSelectedTable(null)}>
                    <XCircle size={18} />
                  </button>
                </div>
                <div className="schema-detail-meta">
                  <span>Type: {selectedTable.type}</span>
                  <span>Rows: {formatRows(selectedTable.row_count)}</span>
                  <span>Size: {formatSize(selectedTable.size_mb)}</span>
                  <span>Columns: {selectedTable.column_count}</span>
                  {selectedTable.partitioning_columns.length > 0 && (
                    <span>Partitioned by: {selectedTable.partitioning_columns.join(', ')}</span>
                  )}
                  {selectedTable.clustering_columns.length > 0 && (
                    <span>Clustered by: {selectedTable.clustering_columns.join(', ')}</span>
                  )}
                </div>
                <div className="schema-columns-table-wrapper">
                  <table className="schema-data-table">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Column Name</th>
                        <th>Data Type</th>
                        <th>Nullable</th>
                        <th>Partition</th>
                        <th>Cluster Pos</th>
                        <th>Max Length</th>
                        <th>Policy Tags</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedTable.columns.map((col, i) => (
                        <tr key={i}>
                          <td className="schema-cell-secondary">{col.ordinal_position}</td>
                          <td className="schema-cell-name">{col.name}</td>
                          <td className="schema-cell-type">{col.data_type}</td>
                          <td>{col.is_nullable ? 'Yes' : 'No'}</td>
                          <td>{col.is_partitioning ? '✓' : ''}</td>
                          <td>{col.clustering_position ?? ''}</td>
                          <td>{col.max_length ?? ''}</td>
                          <td className="schema-cell-tags">
                            {col.policy_tags.length > 0 ? col.policy_tags.join(', ') : ''}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Views Tab */}
            {activeTab === 'views' && (
              <div className="schema-views-section">
                {filteredViews.length === 0 ? (
                  <div className="schema-no-results">
                    {data.views.length === 0 ? 'No views found in this assessment' : 'No views match your search'}
                  </div>
                ) : (
                  <div className="schema-table-wrapper">
                    <table className="schema-data-table">
                      <thead>
                        <tr>
                          <th>View Name</th>
                          <th>Dataset</th>
                          <th>Type</th>
                          <th>Materialized</th>
                          <th>Definition</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredViews.map((v, i) => (
                          <tr key={i}>
                            <td className="schema-cell-name">{v.name}</td>
                            <td className="schema-cell-secondary">{v.dataset || '—'}</td>
                            <td className="schema-cell-secondary">{v.type}</td>
                            <td>{v.is_materialized ? 'Yes' : 'No'}</td>
                            <td className="schema-cell-definition">
                              {v.definition ? (
                                <code className="schema-code-snippet">{v.definition.substring(0, 120)}{v.definition.length > 120 ? '...' : ''}</code>
                              ) : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* Routines Tab */}
            {activeTab === 'routines' && (
              <div className="schema-routines-section">
                {filteredRoutines.length === 0 ? (
                  <div className="schema-no-results">
                    {data.routines.length === 0 ? 'No routines found in this assessment' : 'No routines match your search'}
                  </div>
                ) : (
                  <div className="schema-table-wrapper">
                    <table className="schema-data-table">
                      <thead>
                        <tr>
                          <th>Routine Name</th>
                          <th>Type</th>
                          <th>Language</th>
                          <th>Definition</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredRoutines.map((r, i) => (
                          <tr key={i}>
                            <td className="schema-cell-name">{r.name}</td>
                            <td className="schema-cell-secondary">{r.type}</td>
                            <td className="schema-cell-secondary">{r.language}</td>
                            <td className="schema-cell-definition">
                              {r.definition ? (
                                <code className="schema-code-snippet">{r.definition.substring(0, 120)}{r.definition.length > 120 ? '...' : ''}</code>
                              ) : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* Data Types Distribution Tab */}
            {activeTab === 'types' && (
              <div className="schema-types-section">
                <div className="schema-types-chart">
                  {data.type_distribution.map((td, i) => {
                    const maxCount = data.type_distribution[0]?.count || 1;
                    const pct = (td.count / maxCount) * 100;
                    return (
                      <div key={i} className="schema-type-bar-row">
                        <span className="schema-type-label">{td.type}</span>
                        <div className="schema-type-bar-track">
                          <div className="schema-type-bar-fill" style={{ width: `${pct}%` }} />
                        </div>
                        <span className="schema-type-count">{td.count}</span>
                      </div>
                    );
                  })}
                </div>
                {data.type_distribution.length === 0 && (
                  <div className="schema-no-results">No data type information available</div>
                )}
              </div>
            )}
          </>
        )}

        {/* Empty state */}
        {!data && !loading && !error && (
          <div className="empty-state">
            <div className="empty-state-icon">
              <svg width="64" height="64" viewBox="0 0 64 64" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="8" y="8" width="48" height="48" rx="4" />
                <path d="M8 20h48M20 8v48" />
                <circle cx="32" cy="36" r="8" />
              </svg>
            </div>
            <h2>Schema Analysis</h2>
            <p>
              Select a completed assessment above to analyze its database schema.
              We'll show all datasets, tables, columns, views, routines, and data type distributions.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
