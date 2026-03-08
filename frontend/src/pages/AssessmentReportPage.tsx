/**
 * Assessment Report Page
 * 
 * Displays comprehensive assessment report with all BigQuery metadata
 */

import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  FileSearch, ArrowLeft, Database, Table as TableIcon, Eye, Code, 
  Brain, Activity, Shield, Users, TrendingUp, Lock, DollarSign,
  Zap, Info, CheckCircle, Server
} from 'lucide-react';
import { Button, Badge } from '../components/ui';
import { 
  getAssessmentReport, AssessmentFullReport,
  getAssessmentRecommendations, RecommendationsData,
  getAssessmentTCO, TCOData,
  getTCORegions, AWSRegion
} from '../services/assessmentsApi';
import './AssessmentReportPage.css';

export const AssessmentReportPage: React.FC = () => {
  const { assessmentId } = useParams<{ assessmentId: string }>();
  const navigate = useNavigate();
  const [report, setReport] = useState<AssessmentFullReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>('summary');
  const hasFetchedRef = useRef(false);

  useEffect(() => {
    // Prevent duplicate fetches in React.StrictMode
    if (assessmentId && !hasFetchedRef.current) {
      hasFetchedRef.current = true;
      fetchAssessmentReport();
    }
  }, [assessmentId]);

  const fetchAssessmentReport = async () => {
    try {
      setLoading(true);
      setError(null);

      const data = await getAssessmentReport(parseInt(assessmentId!));
      setReport(data);
    } catch (err: any) {
      console.error('Failed to fetch assessment report:', err);
      setError(err.detail || err.message || 'Failed to load assessment report');
    } finally {
      setLoading(false);
    }
  };

  const formatSize = (sizeMb: number) => {
    if (sizeMb < 1024) return `${sizeMb.toFixed(2)} MB`;
    const sizeGb = sizeMb / 1024;
    if (sizeGb < 1024) return `${sizeGb.toFixed(2)} GB`;
    const sizeTb = sizeGb / 1024;
    return `${sizeTb.toFixed(2)} TB`;
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'N/A';
    try {
      return new Date(dateString).toLocaleString();
    } catch {
      return dateString;
    }
  };

  const formatNumber = (num: number) => {
    return num.toLocaleString();
  };

  // Get unique users from query stats
  const getUniqueUsers = () => {
    if (!report) return [];
    const users = new Set(report.query_stats.map(q => q.user_email).filter(Boolean));
    return Array.from(users);
  };

  // Separate stored procedures and functions
  const getStoredProcedures = () => {
    if (!report) return [];
    return report.routines.filter(r => r.routine_type === 'PROCEDURE');
  };

  const getFunctions = () => {
    if (!report) return [];
    return report.routines.filter(r => r.routine_type === 'FUNCTION');
  };

  // Detect Spark models from routines
  const getSparkModels = () => {
    if (!report) return [];
    return report.routines.filter(r => 
      r.external_language === 'PYTHON' && 
      r.definition && 
      (r.definition.includes('pyspark') || r.definition.includes('spark.'))
    );
  };

  if (loading) {
    return (
      <div className="assessment-report-page">
        <div style={{ padding: '40px', textAlign: 'center' }}>
          <div className="spinner" style={{ margin: '0 auto' }}></div>
          <p style={{ marginTop: '16px', color: 'var(--color-text-secondary)' }}>Loading assessment report...</p>
        </div>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="assessment-report-page">
        <div style={{ padding: '40px', textAlign: 'center' }}>
          <p style={{ color: 'var(--color-error)', marginBottom: '16px' }}>{error || 'Assessment not found'}</p>
          <Button variant="primary" onClick={() => navigate('/assessments')}>
            Back
          </Button>
        </div>
      </div>
    );
  }

  const tabs = [
    { id: 'summary', label: 'Summary', icon: FileSearch },
    { id: 'datasets', label: 'Datasets', icon: Database },
    { id: 'tables', label: 'Tables', icon: TableIcon },
    { id: 'views', label: 'Views', icon: Eye },
    { id: 'procedures', label: 'Stored Procedures', icon: Code },
    { id: 'functions', label: 'Functions', icon: Code },
    { id: 'ml-models', label: 'ML & Spark Models', icon: Brain },
    { id: 'query-insights', label: 'Query Insights', icon: Activity },
    { id: 'user-insights', label: 'User Insights', icon: Users },
    { id: 'security', label: 'Security', icon: Shield },
    { id: 'recommendations', label: 'Recommendations', icon: TrendingUp },
    { id: 'tco', label: 'TCO Analysis', icon: DollarSign },
  ];

  return (
    <div className="assessment-report-page">
      {/* Header */}
      <div className="report-header">
        <Button variant="outline" onClick={() => navigate('/assessments')}>
          <ArrowLeft size={16} />
          Back
        </Button>
        
        <div className="report-title-section">
          <h1 className="report-title">
            <FileSearch size={24} />
            {report.assessment.name}
          </h1>
          <Badge variant={report.assessment.status === 'completed' ? 'success' : 'warning'}>
            {report.assessment.status}
          </Badge>
        </div>
      </div>

      {/* Tabs */}
      <div className="report-tabs">
        {tabs.map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              className={`report-tab ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <Icon size={16} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div className="report-content">
        {activeTab === 'summary' && (
          <SummarySection report={report} formatSize={formatSize} formatDate={formatDate} formatNumber={formatNumber} getSparkModels={getSparkModels} setActiveTab={setActiveTab} />
        )}
        {activeTab === 'datasets' && (
          <DatasetsSection datasets={report.datasets} formatSize={formatSize} formatDate={formatDate} />
        )}
        {activeTab === 'tables' && (
          <TablesSection tables={report.tables} columns={report.columns} formatSize={formatSize} formatDate={formatDate} formatNumber={formatNumber} />
        )}
        {activeTab === 'views' && (
          <ViewsSection views={report.views} formatDate={formatDate} />
        )}
        {activeTab === 'procedures' && (
          <RoutinesSection routines={getStoredProcedures()} title="Stored Procedures" formatDate={formatDate} />
        )}
        {activeTab === 'functions' && (
          <RoutinesSection routines={getFunctions()} title="Functions" formatDate={formatDate} />
        )}
        {activeTab === 'ml-models' && (
          <MLModelsSection mlModels={report.ml_models} sparkModels={getSparkModels()} formatDate={formatDate} />
        )}
        {activeTab === 'query-insights' && (
          <QueryInsightsSection queryStats={report.query_stats} formatDate={formatDate} formatNumber={formatNumber} />
        )}
        {activeTab === 'user-insights' && (
          <UserInsightsSection queryStats={report.query_stats} />
        )}
        {activeTab === 'security' && (
          <SecuritySection 
            securityPolicies={report.security_policies} 
            columns={report.columns}
            tables={report.tables}
          />
        )}
        {activeTab === 'recommendations' && (
          <RecommendationsSection assessmentId={parseInt(assessmentId!)} />
        )}
        {activeTab === 'tco' && (
          <TCOAnalysisSection assessmentId={parseInt(assessmentId!)} />
        )}
      </div>
    </div>
  );
};

// Summary Section Component
const SummarySection: React.FC<any> = ({ report, formatSize, formatDate, formatNumber, getSparkModels, setActiveTab }) => (
  <div className="section-content">
    <h2 className="section-heading">Assessment Summary</h2>
    
    {/* Table of Contents */}
    <div className="table-of-contents">
      <h3 className="toc-heading">Quick Navigation</h3>
      <div className="toc-grid">
        <button className="toc-item" onClick={() => setActiveTab('datasets')}>
          <Database size={16} />
          <span>Datasets ({report.assessment.total_datasets})</span>
        </button>
        <button className="toc-item" onClick={() => setActiveTab('tables')}>
          <TableIcon size={16} />
          <span>Tables ({report.assessment.total_tables})</span>
        </button>
        <button className="toc-item" onClick={() => setActiveTab('columns')}>
          <TableIcon size={16} />
          <span>Columns</span>
        </button>
        <button className="toc-item" onClick={() => setActiveTab('views')}>
          <Eye size={16} />
          <span>Views ({report.assessment.total_views})</span>
        </button>
        <button className="toc-item" onClick={() => setActiveTab('stored-procedures')}>
          <Code size={16} />
          <span>Stored Procedures ({report.assessment.total_routines})</span>
        </button>
        <button className="toc-item" onClick={() => setActiveTab('ml-models')}>
          <Brain size={16} />
          <span>ML Models ({report.assessment.total_ml_models})</span>
        </button>
        <button className="toc-item" onClick={() => setActiveTab('query-insights')}>
          <Activity size={16} />
          <span>Query Insights</span>
        </button>
        <button className="toc-item" onClick={() => setActiveTab('user-insights')}>
          <Users size={16} />
          <span>User Insights</span>
        </button>
        <button className="toc-item" onClick={() => setActiveTab('security')}>
          <Shield size={16} />
          <span>Security Policies</span>
        </button>
        <button className="toc-item" onClick={() => setActiveTab('recommendations')}>
          <TrendingUp size={16} />
          <span>Recommendations</span>
        </button>
        <button className="toc-item" onClick={() => setActiveTab('tco')}>
          <DollarSign size={16} />
          <span>TCO Analysis</span>
        </button>
      </div>
    </div>
    
    {/* Summary Cards */}
    <div className="summary-grid">
      <div className="summary-card">
        <div className="summary-icon" style={{ background: '#EFF6FF', color: '#2563EB' }}>
          <Database size={24} />
        </div>
        <div className="summary-content">
          <div className="summary-value">{report.assessment.total_datasets}</div>
          <div className="summary-label">Datasets</div>
        </div>
      </div>

      <div className="summary-card">
        <div className="summary-icon" style={{ background: '#F0FDF4', color: '#16A34A' }}>
          <TableIcon size={24} />
        </div>
        <div className="summary-content">
          <div className="summary-value">{report.assessment.total_tables}</div>
          <div className="summary-label">Tables</div>
        </div>
      </div>

      <div className="summary-card">
        <div className="summary-icon" style={{ background: '#FEF3C7', color: '#CA8A04' }}>
          <Eye size={24} />
        </div>
        <div className="summary-content">
          <div className="summary-value">{report.assessment.total_views}</div>
          <div className="summary-label">Views</div>
        </div>
      </div>

      <div className="summary-card">
        <div className="summary-icon" style={{ background: '#FCE7F3', color: '#DB2777' }}>
          <Code size={24} />
        </div>
        <div className="summary-content">
          <div className="summary-value">{report.assessment.total_routines}</div>
          <div className="summary-label">SPs & Functions</div>
        </div>
      </div>

      <div className="summary-card">
        <div className="summary-icon" style={{ background: '#EDE9FE', color: '#7C3AED' }}>
          <Brain size={24} />
        </div>
        <div className="summary-content">
          <div className="summary-value">{report.assessment.total_ml_models}</div>
          <div className="summary-label">ML Models</div>
        </div>
      </div>

      <div className="summary-card">
        <div className="summary-icon" style={{ background: '#FFF7ED', color: '#EA580C' }}>
          <Activity size={24} />
        </div>
        <div className="summary-content">
          <div className="summary-value">{getSparkModels().length}</div>
          <div className="summary-label">Spark Models</div>
        </div>
      </div>

      <div className="summary-card">
        <div className="summary-icon" style={{ background: '#F3F4F6', color: '#6B7280' }}>
          <Database size={24} />
        </div>
        <div className="summary-content">
          <div className="summary-value">{formatSize(report.assessment.total_size_mb)}</div>
          <div className="summary-label">Total Data Size</div>
        </div>
      </div>
    </div>

    {/* Assessment Details */}
    <div className="details-section">
      <h3 className="subsection-heading">Assessment Details</h3>
      <div className="details-grid">
        <div className="detail-item">
          <span className="detail-label">Project ID:</span>
          <span className="detail-value">{report.assessment.project_id}</span>
        </div>
        <div className="detail-item">
          <span className="detail-label">Started At:</span>
          <span className="detail-value">{formatDate(report.assessment.started_at)}</span>
        </div>
        <div className="detail-item">
          <span className="detail-label">Completed At:</span>
          <span className="detail-value">{formatDate(report.assessment.completed_at)}</span>
        </div>
      </div>
    </div>
  </div>
);

// Continue in next part...

// Datasets Section Component
const DatasetsSection: React.FC<any> = ({ datasets, formatSize, formatDate }) => (
  <div className="section-content">
    <h2 className="section-heading">Datasets ({datasets.length})</h2>
    {datasets.length === 0 ? (
      <div className="empty-state">
        <Database size={48} />
        <p>No datasets found</p>
      </div>
    ) : (
      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Dataset Name</th>
              <th>Region</th>
              <th>Created Date</th>
              <th>Number of Tables</th>
              <th>Tables Size</th>
            </tr>
          </thead>
          <tbody>
            {datasets.map((dataset: any, index: number) => (
              <tr key={index}>
                <td className="font-medium">{dataset.dataset_name}</td>
                <td>{dataset.location || 'N/A'}</td>
                <td>{formatDate(dataset.creation_time)}</td>
                <td>{dataset.table_count}</td>
                <td>{formatSize(dataset.total_size_mb)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )}
  </div>
);

// Tables Section Component with Column Modal
const TablesSection: React.FC<any> = ({ tables, columns, formatSize, formatDate, formatNumber }) => {
  const [selectedTable, setSelectedTable] = useState<any | null>(null);
  const [showColumnsModal, setShowColumnsModal] = useState(false);

  // Filter to show only BASE TABLEs (not views)
  const baseTables = tables.filter((t: any) => t.table_type === 'BASE TABLE');

  const handleTableClick = (table: any) => {
    setSelectedTable(table);
    setShowColumnsModal(true);
  };

  const getColumnsForTable = (tableId: number) => {
    return columns.filter((col: any) => col.table_id === tableId);
  };

  const formatColumnArray = (arr: any) => {
    // Handle null, undefined, or non-array values
    if (!arr) return 'None';
    
    // If it's not an array, try to parse it
    if (!Array.isArray(arr)) {
      // If it's a string that looks like JSON, try to parse it
      if (typeof arr === 'string') {
        try {
          const parsed = JSON.parse(arr);
          if (Array.isArray(parsed)) {
            arr = parsed;
          } else {
            return 'None';
          }
        } catch {
          return 'None';
        }
      } else {
        return 'None';
      }
    }
    
    // Filter out any malformed entries (single characters like '[', ']', '"')
    const filtered = arr.filter((item: any) => 
      item && typeof item === 'string' && item.length > 1 && 
      item !== '[]' && item !== '""'
    );
    
    if (filtered.length === 0) return 'None';
    
    return filtered.join(', ');
  };

  return (
    <div className="section-content">
      <h2 className="section-heading">Tables ({baseTables.length})</h2>
      {baseTables.length === 0 ? (
        <div className="empty-state">
          <TableIcon size={48} />
          <p>No tables found</p>
        </div>
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Dataset Name</th>
                <th>Table Name</th>
                <th>Creation Time</th>
                <th>Row Count</th>
                <th>Size</th>
                <th>Partitioning</th>
                <th>Clustering</th>
              </tr>
            </thead>
            <tbody>
              {baseTables.map((table: any) => (
                <tr key={table.id}>
                  <td className="font-medium">{table.dataset_name}</td>
                  <td>
                    <button
                      className="table-name-link"
                      onClick={() => handleTableClick(table)}
                      title="Click to view columns"
                    >
                      {table.table_name}
                    </button>
                  </td>
                  <td className="text-sm">{formatDate(table.creation_time)}</td>
                  <td className="text-right">{formatNumber(table.row_count)}</td>
                  <td className="text-right">{formatSize(table.size_mb)}</td>
                  <td className="text-sm">{formatColumnArray(table.partitioning_columns)}</td>
                  <td className="text-sm">{formatColumnArray(table.clustering_columns)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Columns Modal */}
      {showColumnsModal && selectedTable && (
        <div className="modal-overlay" onClick={() => setShowColumnsModal(false)}>
          <div className="modal-content columns-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">
                <TableIcon size={20} />
                {selectedTable.dataset_name}.{selectedTable.table_name}
              </h3>
              <button className="modal-close" onClick={() => setShowColumnsModal(false)}>
                ×
              </button>
            </div>
            <div className="modal-body">
              <div className="table-container">
                <table className="data-table compact">
                  <thead>
                    <tr>
                      <th>Column Name</th>
                      <th>Data Type</th>
                      <th>Nullable</th>
                      <th>Position</th>
                      <th>Partitioning</th>
                      <th>Clustering</th>
                      <th>Policy Tags</th>
                    </tr>
                  </thead>
                  <tbody>
                    {getColumnsForTable(selectedTable.id).map((column: any, idx: number) => (
                      <tr key={idx}>
                        <td className="font-medium">{column.column_name}</td>
                        <td className="font-mono text-sm">{column.data_type}</td>
                        <td className="text-center">
                          {column.is_nullable ? (
                            <Badge variant="default">Yes</Badge>
                          ) : (
                            <Badge variant="error">No</Badge>
                          )}
                        </td>
                        <td className="text-center">{column.ordinal_position}</td>
                        <td className="text-center">
                          {column.is_partitioning_column ? (
                            <Badge variant="info">Yes</Badge>
                          ) : (
                            <span className="text-muted">-</span>
                          )}
                        </td>
                        <td className="text-center">
                          {column.clustering_ordinal_position !== null ? (
                            <Badge variant="info">{column.clustering_ordinal_position}</Badge>
                          ) : (
                            <span className="text-muted">-</span>
                          )}
                        </td>
                        <td className="text-sm">
                          {column.policy_tags && column.policy_tags.length > 0 ? (
                            formatColumnArray(column.policy_tags)
                          ) : (
                            <span className="text-muted">None</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// Views Section Component - Table Format with Clickable Names
const ViewsSection: React.FC<any> = ({ views, formatDate }) => {
  const [expandedView, setExpandedView] = useState<number | null>(null);

  const handleViewClick = (index: number) => {
    setExpandedView(expandedView === index ? null : index);
  };

  // Debug: Log the first view to see its structure
  React.useEffect(() => {
    if (views && views.length > 0) {
      console.log('First view data:', views[0]);
      console.log('View keys:', Object.keys(views[0]));
    }
  }, [views]);

  return (
    <div className="section-content">
      <h2 className="section-heading">Views ({views.length})</h2>
      {views.length === 0 ? (
        <div className="empty-state">
          <Eye size={48} />
          <p>No views found</p>
        </div>
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Created Time</th>
              </tr>
            </thead>
            <tbody>
              {views.map((view: any, index: number) => {
                const isExpanded = expandedView === index;
                const totalDeps = (view.dependent_tables?.length || 0) + 
                                 (view.dependent_views?.length || 0) + 
                                 (view.dependent_functions?.length || 0);
                
                return (
                  <React.Fragment key={index}>
                    <tr>
                      <td>
                        <button
                          className="table-name-link"
                          onClick={() => handleViewClick(index)}
                          title="Click to view dependencies"
                        >
                          {view.view_name}
                        </button>
                      </td>
                      <td>
                        <Badge variant={view.view_type === 'MATERIALIZED_VIEW' ? 'info' : 'default'}>
                          {view.view_type}
                        </Badge>
                      </td>
                      <td className="text-sm">{formatDate(view.creation_time)}</td>
                    </tr>
                    
                    {isExpanded && (
                      <tr className="expanded-row">
                        <td colSpan={3}>
                          <div className="dependency-details">
                            {/* SQL Definition */}
                            {view.view_definition && (
                              <div className="dependency-section">
                                <h4 className="dependency-section-title">
                                  <Code size={16} />
                                  SQL Definition
                                </h4>
                                <pre className="sql-code"><code>{view.view_definition}</code></pre>
                              </div>
                            )}
                            
                            {/* Dependencies */}
                            {totalDeps > 0 ? (
                              <div className="dependency-section">
                                <h4 className="dependency-section-title">
                                  <Database size={16} />
                                  Dependencies ({totalDeps})
                                </h4>
                                
                                {view.dependent_tables && view.dependent_tables.length > 0 && (
                                  <div className="dependency-group">
                                    <h5 className="dependency-group-title">
                                      <TableIcon size={14} />
                                      Tables ({view.dependent_tables.length})
                                    </h5>
                                    <div className="dependency-list">
                                      {view.dependent_tables.map((table: string, idx: number) => (
                                        <Badge key={idx} variant="default" className="dependency-badge">
                                          {table}
                                        </Badge>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                
                                {view.dependent_views && view.dependent_views.length > 0 && (
                                  <div className="dependency-group">
                                    <h5 className="dependency-group-title">
                                      <Eye size={14} />
                                      Views ({view.dependent_views.length})
                                    </h5>
                                    <div className="dependency-list">
                                      {view.dependent_views.map((v: string, idx: number) => (
                                        <Badge key={idx} variant="info" className="dependency-badge">
                                          {v}
                                        </Badge>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                
                                {view.dependent_functions && view.dependent_functions.length > 0 && (
                                  <div className="dependency-group">
                                    <h5 className="dependency-group-title">
                                      <Code size={14} />
                                      Functions ({view.dependent_functions.length})
                                    </h5>
                                    <div className="dependency-list">
                                      {view.dependent_functions.map((func: string, idx: number) => (
                                        <Badge key={idx} variant="warning" className="dependency-badge">
                                          {func}
                                        </Badge>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            ) : (
                              <div className="dependency-section">
                                <h4 className="dependency-section-title">
                                  <Database size={16} />
                                  Dependencies
                                </h4>
                                <p className="text-muted">No dependencies found</p>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

// Routines Section Component (for both SPs and Functions) - Table Format with Clickable Names
const RoutinesSection: React.FC<any> = ({ routines, title, formatDate }) => {
  const [expandedRoutine, setExpandedRoutine] = useState<number | null>(null);

  const handleRoutineClick = (index: number) => {
    setExpandedRoutine(expandedRoutine === index ? null : index);
  };

  // Debug: Log the first routine to see its structure
  React.useEffect(() => {
    if (routines && routines.length > 0) {
      console.log(`First ${title} data:`, routines[0]);
      console.log(`${title} keys:`, Object.keys(routines[0]));
    }
  }, [routines, title]);

  return (
    <div className="section-content">
      <h2 className="section-heading">{title} ({routines.length})</h2>
      {routines.length === 0 ? (
        <div className="empty-state">
          <Code size={48} />
          <p>No {title.toLowerCase()} found</p>
        </div>
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Language</th>
                <th>Created Time</th>
              </tr>
            </thead>
            <tbody>
              {routines.map((routine: any, index: number) => {
                const isExpanded = expandedRoutine === index;
                const totalDeps = (routine.dependent_tables?.length || 0) + 
                                 (routine.dependent_views?.length || 0) + 
                                 (routine.dependent_functions?.length || 0) +
                                 (routine.calls_procedures?.length || 0);
                
                return (
                  <React.Fragment key={index}>
                    <tr>
                      <td>
                        <button
                          className="table-name-link"
                          onClick={() => handleRoutineClick(index)}
                          title="Click to view dependencies"
                        >
                          {routine.routine_name}
                        </button>
                      </td>
                      <td>
                        <Badge variant="default">{routine.routine_type}</Badge>
                      </td>
                      <td>
                        {routine.external_language ? (
                          <Badge variant="info">{routine.external_language}</Badge>
                        ) : (
                          <span className="text-muted">SQL</span>
                        )}
                      </td>
                      <td className="text-sm">{formatDate(routine.creation_time)}</td>
                    </tr>
                    
                    {isExpanded && (
                      <tr className="expanded-row">
                        <td colSpan={4}>
                          <div className="dependency-details">
                            {/* Routine Metadata */}
                            {(routine.return_type || routine.external_language) && (
                              <div className="dependency-section">
                                <h4 className="dependency-section-title">
                                  <Code size={16} />
                                  Routine Information
                                </h4>
                                <div className="routine-metadata">
                                  {routine.return_type && (
                                    <div className="metadata-item">
                                      <span className="metadata-label">Return Type:</span>
                                      <code className="metadata-value">{routine.return_type}</code>
                                    </div>
                                  )}
                                  {routine.external_language && (
                                    <div className="metadata-item">
                                      <span className="metadata-label">Language:</span>
                                      <Badge variant="info">{routine.external_language}</Badge>
                                    </div>
                                  )}
                                </div>
                              </div>
                            )}
                            
                            {/* SQL Definition */}
                            {routine.definition && (
                              <div className="dependency-section">
                                <h4 className="dependency-section-title">
                                  <Code size={16} />
                                  Definition
                                </h4>
                                <pre className="sql-code"><code>{routine.definition}</code></pre>
                              </div>
                            )}
                            
                            {/* Dependencies */}
                            {totalDeps > 0 ? (
                              <div className="dependency-section">
                                <h4 className="dependency-section-title">
                                  <Database size={16} />
                                  Dependencies ({totalDeps})
                                </h4>
                                
                                {routine.dependent_tables && routine.dependent_tables.length > 0 && (
                                  <div className="dependency-group">
                                    <h5 className="dependency-group-title">
                                      <TableIcon size={14} />
                                      Tables ({routine.dependent_tables.length})
                                    </h5>
                                    <div className="dependency-list">
                                      {routine.dependent_tables.map((table: string, idx: number) => (
                                        <Badge key={idx} variant="default" className="dependency-badge">
                                          {table}
                                        </Badge>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                
                                {routine.dependent_views && routine.dependent_views.length > 0 && (
                                  <div className="dependency-group">
                                    <h5 className="dependency-group-title">
                                      <Eye size={14} />
                                      Views ({routine.dependent_views.length})
                                    </h5>
                                    <div className="dependency-list">
                                      {routine.dependent_views.map((v: string, idx: number) => (
                                        <Badge key={idx} variant="info" className="dependency-badge">
                                          {v}
                                        </Badge>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                
                                {routine.dependent_functions && routine.dependent_functions.length > 0 && (
                                  <div className="dependency-group">
                                    <h5 className="dependency-group-title">
                                      <Code size={14} />
                                      Functions ({routine.dependent_functions.length})
                                    </h5>
                                    <div className="dependency-list">
                                      {routine.dependent_functions.map((func: string, idx: number) => (
                                        <Badge key={idx} variant="warning" className="dependency-badge">
                                          {func}
                                        </Badge>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                
                                {routine.calls_procedures && routine.calls_procedures.length > 0 && (
                                  <div className="dependency-group">
                                    <h5 className="dependency-group-title">
                                      <Code size={14} />
                                      Calls Procedures ({routine.calls_procedures.length})
                                    </h5>
                                    <div className="dependency-list">
                                      {routine.calls_procedures.map((proc: string, idx: number) => (
                                        <Badge key={idx} variant="error" className="dependency-badge">
                                          {proc}
                                        </Badge>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            ) : (
                              <div className="dependency-section">
                                <h4 className="dependency-section-title">
                                  <Database size={16} />
                                  Dependencies
                                </h4>
                                <p className="text-muted">No dependencies found</p>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

// ML Models Section Component
const MLModelsSection: React.FC<any> = ({ mlModels, sparkModels, formatDate }) => (
  <div className="section-content">
    <h2 className="section-heading">ML & Spark Models</h2>
    
    {/* ML Models */}
    <div className="subsection">
      <h3 className="subsection-heading">BigQuery ML Models ({mlModels.length})</h3>
      {mlModels.length === 0 ? (
        <div className="empty-state-small">
          <p>No ML models found</p>
        </div>
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Model Name</th>
                <th>Model Type</th>
                <th>Dataset</th>
                <th>Created</th>
                <th>Last Modified</th>
              </tr>
            </thead>
            <tbody>
              {mlModels.map((model: any, index: number) => (
                <tr key={index}>
                  <td className="font-medium">{model.model_name}</td>
                  <td><Badge variant="info">{model.model_type}</Badge></td>
                  <td>{model.dataset_name}</td>
                  <td className="text-sm">{formatDate(model.creation_time)}</td>
                  <td className="text-sm">{formatDate(model.last_modified_time)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>

    {/* Spark Models */}
    <div className="subsection">
      <h3 className="subsection-heading">Spark Models ({sparkModels.length})</h3>
      {sparkModels.length === 0 ? (
        <div className="empty-state-small">
          <p>No Spark models found</p>
        </div>
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Routine Name</th>
                <th>Type</th>
                <th>Language</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {sparkModels.map((model: any, index: number) => (
                <tr key={index}>
                  <td className="font-medium">{model.routine_name}</td>
                  <td><Badge variant="warning">Spark</Badge></td>
                  <td><Badge variant="default">{model.external_language}</Badge></td>
                  <td className="text-sm">{formatDate(model.creation_time)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  </div>
);

// Continue in next part...

// Query Insights Section Component with Time Filters and Charts
const QueryInsightsSection: React.FC<any> = ({ queryStats, formatDate, formatNumber }) => {
  const [timeFilter, setTimeFilter] = useState('all'); // all, 24h, 7d, 30d - matching User Insights

  // Detect query type (read vs write)
  const detectQueryType = (queryText: string | null): 'read' | 'write' => {
    if (!queryText) return 'read';
    const upperQuery = queryText.toUpperCase().trim();
    const writeKeywords = ['INSERT', 'UPDATE', 'DELETE', 'MERGE', 'CREATE', 'DROP', 'ALTER', 'TRUNCATE'];
    return writeKeywords.some(keyword => upperQuery.startsWith(keyword)) ? 'write' : 'read';
  };

  // Filter queries by time - matching User Insights logic
  const filterQueriesByTime = (queries: any[]) => {
    if (timeFilter === 'all') return queries;
    
    const now = new Date();
    const cutoffTime = new Date();
    
    switch (timeFilter) {
      case '24h':
        cutoffTime.setHours(now.getHours() - 24);
        break;
      case '7d':
        cutoffTime.setDate(now.getDate() - 7);
        break;
      case '30d':
        cutoffTime.setDate(now.getDate() - 30);
        break;
      default:
        return queries;
    }

    return queries.filter(q => {
      if (!q.execution_time) return false;
      const execTime = new Date(q.execution_time);
      return execTime >= cutoffTime;
    });
  };

  const filteredQueries = filterQueriesByTime(queryStats);

  // Debug logging to understand data
  React.useEffect(() => {
    console.log('[Query Insights Debug]');
    console.log('Total queryStats received:', queryStats?.length || 0);
    console.log('After time filter:', filteredQueries.length);
    console.log('Time filter:', timeFilter);
    console.log('Unique users:', new Set(queryStats?.map((q: any) => q.user_email)).size);
    console.log('Sample query data:', queryStats?.[0]);
    if (filteredQueries.length > 0) {
      console.log('Filtered sample:', filteredQueries[0]);
    }
  }, [queryStats, timeFilter, filteredQueries.length]);

  // Calculate KPI metrics
  const totalQueries = filteredQueries.length;
  const readQueries = filteredQueries.filter(q => detectQueryType(q.query_text) === 'read').length;
  const writeQueries = filteredQueries.filter(q => detectQueryType(q.query_text) === 'write').length;
  
  // Average execution time (using slot_milliseconds as proxy)
  const avgExecutionTime = totalQueries > 0
    ? filteredQueries.reduce((sum, q) => sum + (q.slot_milliseconds || 0), 0) / totalQueries
    : 0;
  
  // Cache hit rate
  const cacheHitRate = totalQueries > 0 
    ? (filteredQueries.filter((q: any) => q.cache_hit).length / totalQueries * 100)
    : 0;
  
  // Total bytes scanned
  const totalBytesScanned = filteredQueries.reduce((sum: number, q: any) => sum + (q.bytes_scanned || 0), 0);
  
  // Read vs write percentages
  const readPercentage = totalQueries > 0 ? ((readQueries / totalQueries) * 100) : 0;
  const writePercentage = totalQueries > 0 ? ((writeQueries / totalQueries) * 100) : 0;

  // Calculate hourly/daily aggregations based on time filter
  const getHourlyStats = () => {
    const statsData: { [key: string]: { 
      label: string; 
      queries: number; 
      totalSlots: number; 
      totalBytes: number; 
      totalExecTime: number;
      count: number;
    } } = {};
    
    filteredQueries.forEach(q => {
      if (!q.execution_time) return;
      const date = new Date(q.execution_time);
      
      let label: string;
      // Group by hour for 24h, by day for longer periods
      if (timeFilter === '24h') {
        // Group by hour for last 24 hours
        label = `${date.getHours().toString().padStart(2, '0')}:00`;
      } else {
        // Group by date for 7d, 30d, all
        label = `${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getDate().toString().padStart(2, '0')}`;
      }
      
      if (!statsData[label]) {
        statsData[label] = { label, queries: 0, totalSlots: 0, totalBytes: 0, totalExecTime: 0, count: 0 };
      }
      
      statsData[label].queries++;
      statsData[label].totalSlots += q.slot_milliseconds || 0;
      statsData[label].totalBytes += q.bytes_scanned || 0;
      statsData[label].totalExecTime += q.slot_milliseconds || 0;
      statsData[label].count++;
    });

    // Calculate averages and return sorted
    const result = Object.values(statsData).map(h => ({
      label: h.label,
      queries: h.queries,
      avgSlotMs: h.count > 0 ? Math.round(h.totalSlots / h.count) : 0,
      avgBytesScanned: h.count > 0 ? Math.round(h.totalBytes / h.count) : 0,
      avgExecutionTime: h.count > 0 ? Math.round(h.totalExecTime / h.count) : 0,
      totalSlots: h.totalSlots
    })).sort((a, b) => a.label.localeCompare(b.label));
    
    // Limit to reasonable number of bars for display
    if (result.length > 24) {
      // For very long periods, show only last 24 data points
      return result.slice(-24);
    }
    
    return result;
  };

  const hourlyStats = getHourlyStats();

  // Format time duration
  const formatDuration = (ms: number): string => {
    if (ms < 1000) return `${Math.round(ms)}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(2)}s`;
    return `${(ms / 60000).toFixed(2)}m`;
  };

  // Format bytes
  const formatBytes = (bytes: number): string => {
    if (bytes < 1024) return `${bytes}B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)}KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(2)}MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)}GB`;
  };

  return (
    <div className="section-content">
      <div className="query-insights-header">
        <h2 className="section-heading">Query Insights</h2>
        
        {/* Time Filter Dropdown */}
        <div className="time-filter-dropdown">
          <select 
            className="filter-select"
            value={timeFilter}
            onChange={(e) => setTimeFilter(e.target.value)}
          >
            <option value="all">All Time</option>
            <option value="24h">Last 24 Hours</option>
            <option value="7d">Last 7 Days</option>
            <option value="30d">Last 30 Days</option>
          </select>
        </div>
      </div>

      {filteredQueries.length === 0 ? (
        <div className="empty-state">
          <Activity size={48} />
          <p>No query statistics found for selected time period</p>
        </div>
      ) : (
        <>
          {/* KPI Tiles */}
          <div className="kpi-tiles">
            <div className="kpi-tile">
              <div className="kpi-icon">
                <Activity size={24} />
              </div>
              <div className="kpi-content">
                <div className="kpi-label">Total Queries</div>
                <div className="kpi-value">{formatNumber(totalQueries)}</div>
                <div className="kpi-subtitle">
                  {readQueries} read · {writeQueries} write
                </div>
              </div>
            </div>
            
            <div className="kpi-tile">
              <div className="kpi-icon">
                <Brain size={24} />
              </div>
              <div className="kpi-content">
                <div className="kpi-label">Avg Execution Time</div>
                <div className="kpi-value">{formatDuration(avgExecutionTime)}</div>
                <div className="kpi-subtitle">
                  Per query average
                </div>
              </div>
            </div>
            
            <div className="kpi-tile">
              <div className="kpi-icon">
                <TrendingUp size={24} />
              </div>
              <div className="kpi-content">
                <div className="kpi-label">Cache Hit Rate</div>
                <div className="kpi-value">{cacheHitRate.toFixed(1)}%</div>
                <div className="kpi-subtitle">
                  {filteredQueries.filter(q => q.cache_hit).length} cached queries
                </div>
              </div>
            </div>
            
            <div className="kpi-tile">
              <div className="kpi-icon">
                <Database size={24} />
              </div>
              <div className="kpi-content">
                <div className="kpi-label">Total Bytes Scanned</div>
                <div className="kpi-value">{formatBytes(totalBytesScanned)}</div>
                <div className="kpi-subtitle">
                  Avg: {formatBytes(totalQueries > 0 ? totalBytesScanned / totalQueries : 0)}
                </div>
              </div>
            </div>
          </div>

          {/* Charts Row */}
          <div className="charts-row">
            {/* Read vs Write Pie Chart */}
            <div className="chart-card">
              <h3 className="chart-title">Query Type Distribution</h3>
              <div className="pie-chart-wrapper">
                <svg viewBox="0 0 200 200" className="pie-chart">
                  {totalQueries > 0 && (
                    <>
                      {/* Read slice */}
                      <circle
                        cx="100"
                        cy="100"
                        r="70"
                        fill="none"
                        stroke="#4CAF50"
                        strokeWidth="50"
                        strokeDasharray={`${(readQueries / totalQueries) * 439.82} 439.82`}
                        transform="rotate(-90 100 100)"
                      />
                      {/* Write slice */}
                      <circle
                        cx="100"
                        cy="100"
                        r="70"
                        fill="none"
                        stroke="#2A6BDB"
                        strokeWidth="50"
                        strokeDasharray={`${(writeQueries / totalQueries) * 439.82} 439.82`}
                        strokeDashoffset={`-${(readQueries / totalQueries) * 439.82}`}
                        transform="rotate(-90 100 100)"
                      />
                      {/* Center text */}
                      <text x="100" y="95" textAnchor="middle" className="pie-center-text">
                        {totalQueries}
                      </text>
                      <text x="100" y="110" textAnchor="middle" className="pie-center-label">
                        queries
                      </text>
                    </>
                  )}
                </svg>
                <div className="pie-legend">
                  <div className="legend-item">
                    <span className="legend-dot" style={{ background: '#4CAF50' }}></span>
                    <span className="legend-text">Read: {readQueries} ({readPercentage.toFixed(1)}%)</span>
                  </div>
                  <div className="legend-item">
                    <span className="legend-dot" style={{ background: '#2A6BDB' }}></span>
                    <span className="legend-text">Write: {writeQueries} ({writePercentage.toFixed(1)}%)</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Hourly Activity Chart */}
            <div className="chart-card chart-card-wide">
              <h3 className="chart-title">
                {timeFilter === '24h' ? 'Hourly Query Activity' : 'Daily Query Activity'}
              </h3>
              {hourlyStats.length > 0 ? (
                <div className="multi-bar-chart">
                  <div className="chart-y-axis">
                    <span className="y-label">Queries</span>
                  </div>
                  <div className="chart-bars">
                    {hourlyStats.map((stat, idx) => {
                      const maxQueries = Math.max(...hourlyStats.map(s => s.queries), 1);
                      const queryHeight = (stat.queries / maxQueries) * 100;
                      
                      return (
                        <div key={idx} className="bar-group" title={`${stat.label}\nQueries: ${stat.queries}\nAvg Exec: ${formatDuration(stat.avgExecutionTime)}\nSlots: ${formatNumber(stat.totalSlots)}ms`}>
                          <div className="bar-stack">
                            <div className="bar bar-primary" style={{ height: `${queryHeight}%` }}>
                              {stat.queries > 0 && <span className="bar-value">{stat.queries}</span>}
                            </div>
                          </div>
                          <div className="bar-label">{stat.label}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div className="chart-empty">No activity data available</div>
              )}
            </div>
          </div>

          {/* Query List */}
          <div className="query-list-section">
            <h3 className="subsection-heading">Recent Queries (Top 50)</h3>
            <div className="queries-table-container">
              <table className="queries-table">
                <thead>
                  <tr>
                    <th>Query User</th>
                    <th>Execution Time</th>
                    <th>Data Scanned</th>
                    <th>Cache Status</th>
                    <th>Query Slots Utilised</th>
                    <th>Query Start Time</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredQueries.slice(0, 50).map((query: any, index: number) => {
                    const startTime = query.execution_time ? new Date(query.execution_time) : null;
                    
                    return (
                      <tr key={index}>
                        <td className="query-user-cell">
                          <span className="text-sm">{query.user_email || 'Unknown'}</span>
                        </td>
                        <td className="execution-time-cell">
                          <span className="text-sm">{formatDuration(query.slot_milliseconds || 0)}</span>
                        </td>
                        <td className="data-scanned-cell">
                          <span className="text-sm">{formatBytes(query.bytes_scanned || 0)}</span>
                        </td>
                        <td className="cache-status-cell">
                          <Badge variant={query.cache_hit ? 'success' : 'default'}>
                            {query.cache_hit ? 'Cache' : 'Non-Cache'}
                          </Badge>
                        </td>
                        <td className="slots-cell">
                          <span className="text-sm">{formatNumber(query.slot_milliseconds || 0)}ms</span>
                        </td>
                        <td className="start-time-cell">
                          <span className="text-sm">{startTime ? formatDate(startTime) : 'N/A'}</span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

// User Insights Section Component
const UserInsightsSection: React.FC<any> = ({ queryStats }) => {
  const [timeFilter, setTimeFilter] = useState('all'); // all, 24h, 7d, 30d
  
  // Filter queries by time frame
  const getFilteredQueries = () => {
    if (timeFilter === 'all') return queryStats;
    
    const now = new Date();
    const cutoffTime = new Date();
    
    switch (timeFilter) {
      case '24h':
        cutoffTime.setHours(now.getHours() - 24);
        break;
      case '7d':
        cutoffTime.setDate(now.getDate() - 7);
        break;
      case '30d':
        cutoffTime.setDate(now.getDate() - 30);
        break;
      default:
        return queryStats;
    }
    
    return queryStats.filter((query: any) => {
      if (!query.execution_time) return false;
      const queryTime = new Date(query.execution_time);
      return queryTime >= cutoffTime;
    });
  };
  
  const filteredQueries = getFilteredQueries();
  
  // Group queries by user and calculate metrics
  const userStats = filteredQueries.reduce((acc: any, query: any) => {
    const user = query.user_email || 'Unknown';
    if (!acc[user]) {
      acc[user] = {
        queryCount: 0,
        totalBytesScanned: 0,
        totalSlotMilliseconds: 0,
        cacheHits: 0,
        totalQueries: 0,
      };
    }
    acc[user].queryCount++;
    acc[user].totalQueries++;
    acc[user].totalBytesScanned += query.bytes_scanned || 0;
    acc[user].totalSlotMilliseconds += query.slot_milliseconds || 0;
    if (query.cache_hit) acc[user].cacheHits++;
    return acc;
  }, {});

  const users = Object.entries(userStats).map(([email, stats]: [string, any]) => ({
    email,
    queryCount: stats.queryCount,
    totalBytesScanned: stats.totalBytesScanned,
    totalSlotMilliseconds: stats.totalSlotMilliseconds,
    cacheHits: stats.cacheHits,
    cacheHitRate: stats.totalQueries > 0 ? (stats.cacheHits / stats.totalQueries * 100).toFixed(1) : '0.0',
  })).sort((a, b) => b.queryCount - a.queryCount);

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const gb = bytes / (1024 * 1024 * 1024);
    if (gb >= 1) return `${gb.toFixed(2)} GB`;
    const mb = bytes / (1024 * 1024);
    if (mb >= 1) return `${mb.toFixed(2)} MB`;
    const kb = bytes / 1024;
    return `${kb.toFixed(2)} KB`;
  };

  const formatSlots = (milliseconds: number) => {
    if (milliseconds === 0) return '0';
    const seconds = milliseconds / 1000;
    if (seconds >= 3600) return `${(seconds / 3600).toFixed(2)} slot-hrs`;
    if (seconds >= 60) return `${(seconds / 60).toFixed(2)} slot-mins`;
    return `${seconds.toFixed(2)} slot-secs`;
  };

  return (
    <div className="section-content">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h2 className="section-heading">User Insights ({users.length} users)</h2>
        
        {/* Time Filter */}
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{ fontSize: '14px', color: 'var(--color-text-secondary)' }}>Time Frame:</span>
          <select
            value={timeFilter}
            onChange={(e) => setTimeFilter(e.target.value)}
            style={{
              padding: '6px 12px',
              borderRadius: '6px',
              border: '1px solid var(--color-divider)',
              fontSize: '14px',
              backgroundColor: 'var(--color-bg-surface)',
              cursor: 'pointer',
            }}
          >
            <option value="all">All Time</option>
            <option value="24h">Last 24 Hours</option>
            <option value="7d">Last 7 Days</option>
            <option value="30d">Last 30 Days</option>
          </select>
        </div>
      </div>
      
      {users.length === 0 ? (
        <div className="empty-state">
          <Users size={48} />
          <p>No user data found for selected time frame</p>
        </div>
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ textAlign: 'left' }}>User Email</th>
                <th style={{ textAlign: 'right' }}>Queries Executed</th>
                <th style={{ textAlign: 'right' }}>Total Data Scanned</th>
                <th style={{ textAlign: 'right' }}>Slots Utilized</th>
                <th style={{ textAlign: 'right' }}>Cache Hit Ratio</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user: any, index: number) => (
                <tr key={index}>
                  <td className="font-medium" style={{ textAlign: 'left' }}>{user.email}</td>
                  <td style={{ textAlign: 'right' }}>{user.queryCount.toLocaleString()}</td>
                  <td style={{ textAlign: 'right' }}>{formatBytes(user.totalBytesScanned)}</td>
                  <td style={{ textAlign: 'right' }}>{formatSlots(user.totalSlotMilliseconds)}</td>
                  <td style={{ textAlign: 'right' }}>
                    <Badge variant={parseFloat(user.cacheHitRate) > 50 ? 'success' : parseFloat(user.cacheHitRate) > 20 ? 'warning' : 'default'}>
                      {user.cacheHitRate}%
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

// Security Section Component
const SecuritySection: React.FC<any> = ({ securityPolicies, columns, tables }) => {
  const [expandedPolicy, setExpandedPolicy] = useState<number | null>(null);
  
  // Filter RLS policies
  const rlsPolicies = securityPolicies.filter((p: any) => p.security_type === 'RLS');
  
  // Create a map of table_id to table_name for quick lookup
  const tableIdToName = tables.reduce((acc: any, table: any) => {
    acc[table.id] = `${table.dataset_name}.${table.table_name}`;
    return acc;
  }, {});
  
  // Helper function to safely parse policy_tags
  const parsePolicyTags = (policyTags: any): string[] => {
    console.log('parsePolicyTags input:', policyTags, 'type:', typeof policyTags);
    
    if (!policyTags) return [];
    
    // If it's already an array, return it
    if (Array.isArray(policyTags)) {
      console.log('Already array:', policyTags);
      return policyTags;
    }
    
    // If it's a string, try to parse it as JSON
    if (typeof policyTags === 'string') {
      // Handle empty string
      if (policyTags.trim() === '' || policyTags === '[]') {
        return [];
      }
      
      try {
        const parsed = JSON.parse(policyTags);
        console.log('Parsed from string:', parsed);
        return Array.isArray(parsed) ? parsed : [];
      } catch (e) {
        console.warn('Failed to parse policy_tags:', policyTags, e);
        return [];
      }
    }
    
    return [];
  };
  
  // Extract CLS data from columns (columns with policy tags) and enrich with table names
  const clsColumns = columns
    .map((col: any) => {
      const tags = parsePolicyTags(col.policy_tags);
      return {
        ...col,
        policy_tags: tags,
        table_name: tableIdToName[col.table_id] || 'Unknown'
      };
    })
    .filter((col: any) => col.policy_tags && col.policy_tags.length > 0);
  
  // Group CLS columns by table
  const clsByTable = clsColumns.reduce((acc: any, col: any) => {
    const tableName = col.table_name;
    if (!acc[tableName]) {
      acc[tableName] = [];
    }
    acc[tableName].push(col);
    return acc;
  }, {});
  
  const totalSecurityItems = rlsPolicies.length + Object.keys(clsByTable).length;

  return (
    <div className="section-content">
      <h2 className="section-heading">Security Policies</h2>
      
      {totalSecurityItems === 0 ? (
        <div className="empty-state">
          <Shield size={48} />
          <p>No security policies found</p>
        </div>
      ) : (
        <div className="security-sections">
          {/* Row-Level Security (RLS) Section */}
          {rlsPolicies.length > 0 && (
            <div className="security-subsection">
              <h3 className="subsection-heading">
                <Shield size={20} />
                Row-Level Security (RLS) Policies ({rlsPolicies.length})
              </h3>
              <div className="rls-policies-list">
                {rlsPolicies.map((policy: any, index: number) => {
                  const isExpanded = expandedPolicy === index;
                  const hasDDL = policy.security_metadata && policy.security_metadata.ddl;
                  
                  return (
                    <div key={index} className="rls-policy-card">
                      <div className="rls-policy-header">
                        <div className="rls-policy-info">
                          <h4 className="rls-policy-name">
                            <Shield size={16} />
                            {policy.policy_name}
                          </h4>
                          <div className="rls-policy-meta">
                            <Badge variant="info">
                              <Database size={12} />
                              {policy.table_name}
                            </Badge>
                          </div>
                        </div>
                        {hasDDL && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setExpandedPolicy(isExpanded ? null : index)}
                          >
                            {isExpanded ? 'Hide' : 'Show'} DDL
                          </Button>
                        )}
                      </div>
                      
                      <div className="rls-policy-details">
                        <div className="rls-detail-row">
                          <span className="rls-detail-label">Filter Predicate:</span>
                          <code className="rls-detail-value">{policy.filter_predicate || 'N/A'}</code>
                        </div>
                        
                        <div className="rls-detail-row">
                          <span className="rls-detail-label">Grantees:</span>
                          <div className="rls-grantees">
                            {policy.grantees && policy.grantees.length > 0 ? (
                              policy.grantees.map((grantee: string, idx: number) => (
                                <Badge key={idx} variant="success" className="grantee-badge">
                                  <Users size={12} />
                                  {grantee.trim()}
                                </Badge>
                              ))
                            ) : (
                              <span className="text-muted">No grantees specified</span>
                            )}
                          </div>
                        </div>
                        
                        {policy.creation_time && (
                          <div className="rls-detail-row">
                            <span className="rls-detail-label">Created:</span>
                            <span className="rls-detail-value">{new Date(policy.creation_time).toLocaleString()}</span>
                          </div>
                        )}
                      </div>
                      
                      {isExpanded && hasDDL && (
                        <div className="rls-ddl-section">
                          <div className="rls-ddl-header">
                            <Code size={14} />
                            <span>Policy DDL</span>
                          </div>
                          <pre className="rls-ddl-code"><code>{policy.security_metadata.ddl}</code></pre>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          
          {/* Column-Level Security (CLS) Section */}
          {Object.keys(clsByTable).length > 0 && (
            <div className="security-subsection">
              <h3 className="subsection-heading">
                <Lock size={20} />
                Column-Level Security (CLS) - Policy Tags ({Object.keys(clsByTable).length} tables)
              </h3>
              <div className="cls-tables">
                {Object.entries(clsByTable).map(([tableName, cols]: [string, any], tableIdx: number) => (
                  <div key={tableIdx} className="cls-table-group">
                    <h4 className="cls-table-name">
                      <Database size={16} />
                      {tableName}
                      <Badge variant="default" className="cls-column-count">
                        {cols.length} {cols.length === 1 ? 'column' : 'columns'}
                      </Badge>
                    </h4>
                    <div className="table-container">
                      <table className="data-table cls-table">
                        <thead>
                          <tr>
                            <th>Column Name</th>
                            <th>Data Type</th>
                            <th>Policy Tags</th>
                          </tr>
                        </thead>
                        <tbody>
                          {cols.map((col: any, colIdx: number) => (
                            <tr key={colIdx}>
                              <td className="font-medium">
                                <Lock size={14} className="inline-icon" />
                                {col.column_name}
                              </td>
                              <td>
                                <Badge variant="default">{col.data_type}</Badge>
                              </td>
                              <td>
                                <div className="policy-tags-list">
                                  {col.policy_tags && col.policy_tags.length > 0 ? (
                                    col.policy_tags.map((tag: string, tagIdx: number) => (
                                      <Badge key={tagIdx} variant="warning" className="policy-tag">
                                        <Shield size={12} />
                                        {tag}
                                      </Badge>
                                    ))
                                  ) : (
                                    <span className="text-muted">No tags</span>
                                  )}
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// Sharded Tables Section Component
const ShardedTablesSection: React.FC<any> = ({ shardedTables, formatSize, formatDate }) => {
  const [expandedShard, setExpandedShard] = useState<number | null>(null);

  return (
    <div className="section-content">
      <h2 className="section-heading">Sharded Table Groups ({shardedTables.length})</h2>
      {shardedTables.length === 0 ? (
        <div className="empty-state">
          <TrendingUp size={48} />
          <p>No sharded tables found</p>
        </div>
      ) : (
        <div className="sharded-list">
          {shardedTables.map((shard: any, index: number) => {
            const isExpanded = expandedShard === index;
            
            return (
              <div key={index} className="shard-item">
                <div className="shard-header">
                  <div className="shard-info">
                    <h4 className="shard-name">{shard.shard_group}</h4>
                    <div className="shard-meta">
                      <Badge variant="info">{shard.shard_count} shards</Badge>
                      <span className="text-sm">Size: {formatSize(shard.total_size_mb)}</span>
                      <span className="text-sm text-muted">
                        Range: {formatDate(shard.date_range_start)} - {formatDate(shard.date_range_end)}
                      </span>
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setExpandedShard(isExpanded ? null : index)}
                  >
                    {isExpanded ? 'Hide' : 'Show'} Tables
                  </Button>
                </div>
                
                {isExpanded && shard.shard_tables && (
                  <div className="shard-tables">
                    <ul>
                      {shard.shard_tables.map((table: string, idx: number) => (
                        <li key={idx}>{table}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

// Recommendations Section Component
const RecommendationsSection: React.FC<{ assessmentId: number }> = ({ assessmentId }) => {
  const [data, setData] = useState<RecommendationsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const result = await getAssessmentRecommendations(assessmentId);
        setData(result);
      } catch (err: any) {
        setError(err.detail || err.message || 'Failed to load recommendations');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [assessmentId]);

  if (loading) return <div className="section-content"><div style={{ padding: '40px', textAlign: 'center' }}><div className="spinner" style={{ margin: '0 auto' }}></div><p style={{ marginTop: '16px', color: 'var(--color-text-secondary)' }}>Generating recommendations...</p></div></div>;
  if (error || !data) return <div className="section-content"><p style={{ color: 'var(--color-error)', padding: '20px' }}>{error || 'No data'}</p></div>;

  const { query_classification: qc, config_recommendation: cr, dist_sort_keys: dsk, architecture: arch } = data;
  const recommended = cr.recommended;

  return (
    <div className="section-content">
      <h2 className="section-heading">Migration Recommendations</h2>

      {/* Distribution & Sort Key Recommendations */}
      <div className="rec-section">
        <h3 className="rec-section-title"><TableIcon size={18} /> Distribution & Sort Key Recommendations</h3>
        {dsk.length === 0 ? (
          <div className="empty-state-small"><p>No table-level recommendations available.</p></div>
        ) : (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Table</th>
                  <th>DISTKEY</th>
                  <th>SORTKEY</th>
                  <th>Reasoning</th>
                </tr>
              </thead>
              <tbody>
                {dsk.map((row, i) => (
                  <tr key={i}>
                    <td className="font-mono font-medium">{row.table_name}</td>
                    <td><Badge variant={row.distkey === 'EVEN' ? 'default' : 'info'}>{row.distkey}</Badge></td>
                    <td><Badge variant={row.sortkey === 'AUTO' ? 'default' : 'info'}>{row.sortkey}</Badge></td>
                    <td>
                      <ul className="rec-reasoning-list">
                        {row.reasoning.map((r, j) => <li key={j}>{r}</li>)}
                      </ul>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="rec-info-box" style={{ marginTop: 'var(--spacing-6)' }}>
          <div className="rec-info-title"><Info size={16} /> Key Optimization Guidelines</div>
          <ul className="rec-info-list">
            <li>DISTKEY should be chosen based on JOIN columns with high cardinality for even data distribution across nodes.</li>
            <li>SORTKEY should align with WHERE clause filters and ORDER BY columns — BigQuery partitioning/clustering columns are ideal candidates.</li>
            <li>Tables with fewer than 1M rows use EVEN distribution (no skew benefit from KEY distribution).</li>
            <li>Use COMPOUND sort keys when queries filter on multiple columns in a predictable order.</li>
          </ul>
        </div>
      </div>

      {/* Query Classification & Architecture */}
      <div className="rec-section">
        <h3 className="rec-section-title"><Activity size={18} /> Query Classification & Architecture</h3>
        <div className="rec-cards-row">
          <div className="rec-card rec-card-blue">
            <div className="rec-card-icon"><Zap size={24} /></div>
            <div className="rec-card-value">{qc.adhoc_count.toLocaleString()}</div>
            <div className="rec-card-label">Ad-hoc Queries</div>
            <div className="rec-card-pct">{qc.adhoc_pct}%</div>
          </div>
          <div className="rec-card rec-card-purple">
            <div className="rec-card-icon"><TrendingUp size={24} /></div>
            <div className="rec-card-value">{qc.bi_count.toLocaleString()}</div>
            <div className="rec-card-label">BI / Scheduled Queries</div>
            <div className="rec-card-pct">{qc.bi_pct}%</div>
          </div>
          <div className="rec-card rec-card-green">
            <div className="rec-card-icon"><Activity size={24} /></div>
            <div className="rec-card-value">{qc.total_queries.toLocaleString()}</div>
            <div className="rec-card-label">Total Queries Analyzed</div>
          </div>
        </div>

        {/* Architecture Recommendation */}
        {arch.strategies.map((s, i) => (
          <div key={i} className="rec-info-box">
            <div className="rec-info-title"><Info size={16} /> {s.title}</div>
            <ul className="rec-info-list">
              {s.points.map((p, j) => <li key={j}>{p}</li>)}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
};

// TCO Analysis Section Component
const TCOAnalysisSection: React.FC<{ assessmentId: number }> = ({ assessmentId }) => {
  const [data, setData] = useState<TCOData | null>(null);
  const [regions, setRegions] = useState<AWSRegion[]>([]);
  const [selectedRegion, setSelectedRegion] = useState('us-east-1');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getTCORegions().then(r => setRegions(r.regions)).catch(() => {});
  }, []);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const result = await getAssessmentTCO(assessmentId, selectedRegion);
        setData(result);
      } catch (err: any) {
        setError(err.detail || err.message || 'Failed to load TCO analysis');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [assessmentId, selectedRegion]);

  const fmt = (n: number) => `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  if (loading) return <div className="section-content"><div style={{ padding: '40px', textAlign: 'center' }}><div className="spinner" style={{ margin: '0 auto' }}></div><p style={{ marginTop: '16px', color: 'var(--color-text-secondary)' }}>Calculating TCO...</p></div></div>;
  if (error || !data) return <div className="section-content"><p style={{ color: 'var(--color-error)', padding: '20px' }}>{error || 'No data'}</p></div>;

  const { bigquery_costs: bq, provisioned_costs: prov, serverless_costs: svls, migration_costs: mig, comparison: cmp } = data;
  const maxTCO = Math.max(cmp.bq_3yr_tco, cmp.provisioned_3yr_tco, cmp.serverless_3yr_tco) || 1;

  return (
    <div className="section-content">
      <div className="tco-header-row">
        <h2 className="section-heading" style={{ margin: 0 }}>TCO Analysis</h2>
        <div className="tco-region-select">
          <label>AWS Region:</label>
          <select value={selectedRegion} onChange={e => setSelectedRegion(e.target.value)} className="filter-select">
            {regions.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
        </div>
      </div>

      {/* Cost Optimization Opportunity */}
      <div className={`tco-savings-box ${cmp.savings_pct > 0 ? 'tco-savings-positive' : 'tco-savings-neutral'}`}>
        <div className="tco-savings-icon"><DollarSign size={28} /></div>
        <div className="tco-savings-content">
          <div className="tco-savings-title">
            {cmp.savings_pct > 0 ? `${cmp.savings_pct}% Cost Optimization Opportunity` : 'Cost Comparison'}
          </div>
          <div className="tco-savings-detail">
            BigQuery 3-Year: <strong>{fmt(cmp.bq_3yr_tco)}</strong> → Best Redshift ({cmp.best_option}): <strong>{fmt(cmp.best_option === 'serverless' ? cmp.serverless_3yr_tco : cmp.provisioned_3yr_tco)}</strong>
            {cmp.savings_pct > 0 && <> — Savings: <strong>{fmt(cmp.savings_amount)}</strong></>}
          </div>
        </div>
      </div>

      {/* Provisioned not viable warning */}
      {cmp.provisioned_viable === false && cmp.provisioned_note && (
        <div className="rec-info-box" style={{ borderLeft: '4px solid #f59e0b', background: '#fffbeb' }}>
          <div className="rec-info-title" style={{ color: '#b45309' }}>⚠️ Light Workload Detected</div>
          <p style={{ margin: '4px 0 0', color: '#92400e', fontSize: '13px' }}>{cmp.provisioned_note}</p>
        </div>
      )}

      {/* Monthly Cost Summary */}
      <div className="tco-section">
        <h3 className="rec-section-title"><Database size={18} /> Monthly Cost Summary</h3>
        <div className="tco-cost-grid">
          <div className="tco-cost-card">
            <div className="tco-cost-label">BigQuery (Current)</div>
            <div className="tco-cost-value">{fmt(bq.monthly)}<span>/mo</span></div>
            <div className="tco-cost-detail">Storage {fmt(bq.storage.monthly)} + Query {fmt(bq.query.monthly)}</div>
          </div>
          <div className="tco-cost-card">
            <div className="tco-cost-label">Redshift Provisioned</div>
            <div className="tco-cost-value">{fmt(prov.monthly)}<span>/mo</span></div>
            <div className="tco-cost-detail">{prov.num_nodes}× {prov.node_type}</div>
          </div>
          <div className="tco-cost-card">
            <div className="tco-cost-label">Redshift Serverless</div>
            <div className="tco-cost-value">{fmt(svls.monthly)}<span>/mo</span></div>
            <div className="tco-cost-detail">{svls.est_rpu_hours_monthly} RPU-hrs/mo</div>
          </div>
        </div>
      </div>

      {/* Redshift Cost Details */}
      <div className="tco-section">
        <h3 className="rec-section-title"><Server size={18} /> Redshift Cost Details</h3>
        <div className="rec-config-grid">
          {/* Provisioned */}
          <div className={`rec-config-card ${cmp.best_option === 'provisioned' ? 'rec-config-recommended' : ''}`}>
            {cmp.best_option === 'provisioned' && <div className="rec-badge">Best Value</div>}
            {cmp.provisioned_viable === false && <div className="rec-badge" style={{ background: '#f59e0b' }}>Not Recommended</div>}
            <div className="rec-config-header"><Server size={20} /><span>Provisioned Cluster</span></div>
            <div className="rec-config-details">
              <div className="rec-config-row"><span>Node Type</span><span className="font-mono">{prov.node_type}</span></div>
              <div className="rec-config-row"><span>Nodes</span><span>{prov.num_nodes}</span></div>
              <div className="rec-config-row"><span>Compute</span><span>{fmt(prov.compute_monthly)}/mo</span></div>
              <div className="rec-config-row"><span>Storage</span><span>{fmt(prov.storage_monthly)}/mo</span></div>
              <div className="rec-config-row rec-config-row-total"><span>Total</span><span>{fmt(prov.monthly)}/mo</span></div>
              <div className="rec-config-row"><span>Annual</span><span>{fmt(prov.annual)}</span></div>
            </div>
          </div>
          {/* Serverless */}
          <div className={`rec-config-card ${cmp.best_option === 'serverless' ? 'rec-config-recommended' : ''}`}>
            {cmp.best_option === 'serverless' && <div className="rec-badge">Best Value</div>}
            <div className="rec-config-header"><Zap size={20} /><span>Serverless</span></div>
            <div className="rec-config-details">
              <div className="rec-config-row"><span>Base RPU</span><span>{svls.base_rpu} <span style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>(AWS min)</span></span></div>
              <div className="rec-config-row"><span>Max RPU</span><span>{svls.max_rpu}</span></div>
              <div className="rec-config-row"><span>Est. RPU-hours/mo</span><span>{svls.est_rpu_hours_monthly?.toLocaleString()}</span></div>
              <div className="rec-config-row"><span>RPU Rate</span><span>${svls.rpu_hour_rate}/RPU-hr</span></div>
              <div className="rec-config-row"><span>Compute</span><span>{fmt(svls.compute_monthly)}/mo</span></div>
              <div className="rec-config-row"><span>Storage</span><span>{fmt(svls.storage_monthly)}/mo</span></div>
              <div className="rec-config-row rec-config-row-total"><span>Total</span><span>{fmt(svls.monthly)}/mo</span></div>
              <div className="rec-config-row"><span>Annual</span><span>{fmt(svls.annual)}</span></div>
            </div>
          </div>
        </div>
      </div>

      {/* 3-Year TCO Comparison Bar Chart */}
      <div className="tco-section">
        <h3 className="rec-section-title"><TrendingUp size={18} /> 3-Year TCO Comparison</h3>
        <div className="tco-bar-chart">
          <div className="tco-bar-item">
            <div className="tco-bar-label-top">{fmt(cmp.bq_3yr_tco)}</div>
            <div className="tco-bar" style={{ height: `${Math.max((cmp.bq_3yr_tco / maxTCO) * 200, 20)}px`, background: 'linear-gradient(to top, #ef4444, #f87171)' }}></div>
            <div className="tco-bar-label">BigQuery</div>
          </div>
          <div className="tco-bar-item">
            <div className="tco-bar-label-top">{fmt(cmp.provisioned_3yr_tco)}</div>
            <div className="tco-bar" style={{ height: `${Math.max((cmp.provisioned_3yr_tco / maxTCO) * 200, 20)}px`, background: 'linear-gradient(to top, #3b82f6, #60a5fa)' }}></div>
            <div className="tco-bar-label">Provisioned</div>
          </div>
          <div className="tco-bar-item">
            <div className="tco-bar-label-top">{fmt(cmp.serverless_3yr_tco)}</div>
            <div className="tco-bar" style={{ height: `${Math.max((cmp.serverless_3yr_tco / maxTCO) * 200, 20)}px`, background: 'linear-gradient(to top, #22c55e, #4ade80)' }}></div>
            <div className="tco-bar-label">Serverless</div>
          </div>
        </div>
      </div>

      {/* Migration Cost */}
      <div className="rec-info-box">
        <div className="rec-info-title"><Info size={16} /> Migration Cost</div>
        <p style={{ margin: '4px 0 0', fontSize: '13px', color: 'var(--color-text-secondary)' }}>
          One-time data transfer (GCP → AWS): <strong>{fmt(mig.total)}</strong> ({mig.data_volume_gb} GB). Included in Redshift 3-year totals above.
        </p>
      </div>
    </div>
  );
};
