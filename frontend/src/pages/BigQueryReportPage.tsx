/**
 * BigQuery Assessment Report Page
 * 
 * This file contains ALL BigQuery-specific assessment report UI.
 * DO NOT add SQL Server code here. SQL Server lives in SQLServerReportPage.tsx.
 * 
 * Lazy-loads data per tab for fast initial render.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileSearch, ArrowLeft, Database, Table as TableIcon, Eye, Code,
  Brain, Activity, Shield, Users, TrendingUp, Lock, DollarSign,
  Zap, Info, Server, Download, CheckCircle, AlertTriangle, BarChart3
} from 'lucide-react';
import { Button, Badge } from '../components/ui';
import { Select } from '../components/ui/Select';
import { SearchableSelect } from '../components/ui/SearchableSelect';
import {
  getAssessmentReport,
  getAssessmentRecommendations, RecommendationsData,
  getAssessmentTCO, TCOData,
  getTCORegions, AWSRegion,
  ReportSummary,
  getReportTables, PaginatedTablesResponse,
  getReportViews, PaginatedViewsResponse,
  getReportRoutines, RoutinesResponse,
  getReportSecurity, SecurityResponse,
  getReportMLModels, MLModelsResponse,
  getReportUserInsights, UserInsightsResponse,
  AssessmentReportTable, AssessmentReportColumn, AssessmentReportView,
  AssessmentReportRoutine, DatasetSummary,
  getAllReportTables, getAllReportViews
} from '../services/assessmentsApi';
import QueryInsightsSection from '../components/assessments/QueryInsightsSection';
import { DownloadReportModal } from '../components/assessments/DownloadReportModal';
import { generatePDF } from '../utils/pdfReport';
import { downloadCsv } from '../utils/csvExport';
import { TabSpinner, TabError, PaginationControls, formatSize, formatDate, formatNumber } from './reportUtils';
import './AssessmentReportPage.css';

interface BigQueryReportPageProps {
  summary: ReportSummary;
  assessmentId: number;
}

export const BigQueryReportPage: React.FC<BigQueryReportPageProps> = ({ summary, assessmentId }) => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<string>('summary');
  const id = assessmentId;

  // Per-tab lazy-loaded data
  const [tablesData, setTablesData] = useState<PaginatedTablesResponse | null>(null);
  const [tablesLoading, setTablesLoading] = useState(false);
  const [tablesError, setTablesError] = useState<string | null>(null);
  const [tablesPage, setTablesPage] = useState(1);
  const [tablesPageSize, setTablesPageSize] = useState(50);
  const [tablesDataset, setTablesDataset] = useState<string>('all');

  const [viewsData, setViewsData] = useState<PaginatedViewsResponse | null>(null);
  const [viewsLoading, setViewsLoading] = useState(false);
  const [viewsError, setViewsError] = useState<string | null>(null);
  const [viewsPage, setViewsPage] = useState(1);
  const [viewsPageSize, setViewsPageSize] = useState(50);

  const [routinesData, setRoutinesData] = useState<RoutinesResponse | null>(null);
  const [routinesLoading, setRoutinesLoading] = useState(false);
  const [routinesError, setRoutinesError] = useState<string | null>(null);

  const [securityData, setSecurityData] = useState<SecurityResponse | null>(null);
  const [securityLoading, setSecurityLoading] = useState(false);
  const [securityError, setSecurityError] = useState<string | null>(null);

  const [mlModelsData, setMLModelsData] = useState<MLModelsResponse | null>(null);
  const [mlModelsLoading, setMLModelsLoading] = useState(false);
  const [mlModelsError, setMLModelsError] = useState<string | null>(null);

  const [userInsightsData, setUserInsightsData] = useState<UserInsightsResponse | null>(null);
  const [userInsightsLoading, setUserInsightsLoading] = useState(false);
  const [userInsightsError, setUserInsightsError] = useState<string | null>(null);

  const [showDownloadModal, setShowDownloadModal] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const loadedTabsRef = useRef<Set<string>>(new Set(['summary']));

  const fetchTables = useCallback(async (page: number, pageSize: number, dataset?: string) => {
    setTablesLoading(true); setTablesError(null);
    try { const data = await getReportTables(id, page, pageSize, dataset); setTablesData(data); loadedTabsRef.current.add('tables'); }
    catch (err: any) { setTablesError(err.detail || err.message || 'Failed to load tables'); }
    finally { setTablesLoading(false); }
  }, [id]);

  const fetchViews = useCallback(async (page: number, pageSize: number) => {
    setViewsLoading(true); setViewsError(null);
    try { const data = await getReportViews(id, page, pageSize); setViewsData(data); loadedTabsRef.current.add('views'); }
    catch (err: any) { setViewsError(err.detail || err.message || 'Failed to load views'); }
    finally { setViewsLoading(false); }
  }, [id]);

  useEffect(() => {
    const tab = activeTab;
    if (loadedTabsRef.current.has(tab) && tab !== 'tables' && tab !== 'views') return;
    switch (tab) {
      case 'tables': fetchTables(tablesPage, tablesPageSize, tablesDataset); break;
      case 'views': fetchViews(viewsPage, viewsPageSize); break;
      case 'procedures': case 'functions':
        if (!loadedTabsRef.current.has('routines')) {
          setRoutinesLoading(true);
          getReportRoutines(id).then(d => { setRoutinesData(d); loadedTabsRef.current.add('routines'); }).catch((e: any) => setRoutinesError(e.detail || e.message || 'Failed')).finally(() => setRoutinesLoading(false));
        }
        break;
      case 'security':
        if (!loadedTabsRef.current.has('security')) {
          setSecurityLoading(true);
          getReportSecurity(id).then(d => { setSecurityData(d); loadedTabsRef.current.add('security'); }).catch((e: any) => setSecurityError(e.detail || e.message || 'Failed')).finally(() => setSecurityLoading(false));
        }
        break;
      case 'ml-models':
        if (!loadedTabsRef.current.has('ml-models')) {
          setMLModelsLoading(true);
          getReportMLModels(id).then(d => { setMLModelsData(d); loadedTabsRef.current.add('ml-models'); }).catch((e: any) => setMLModelsError(e.detail || e.message || 'Failed')).finally(() => setMLModelsLoading(false));
        }
        break;
      case 'user-insights':
        if (!loadedTabsRef.current.has('user-insights')) {
          setUserInsightsLoading(true);
          getReportUserInsights(id).then(d => { setUserInsightsData(d); loadedTabsRef.current.add('user-insights'); }).catch((e: any) => setUserInsightsError(e.detail || e.message || 'Failed')).finally(() => setUserInsightsLoading(false));
        }
        break;
    }
  }, [activeTab]);

  useEffect(() => { if (activeTab === 'tables') fetchTables(tablesPage, tablesPageSize, tablesDataset); }, [tablesPage, tablesPageSize, tablesDataset]);
  useEffect(() => { if (activeTab === 'views') fetchViews(viewsPage, viewsPageSize); }, [viewsPage, viewsPageSize]);

  const getStoredProcedures = () => routinesData ? routinesData.routines.filter(r => r.routine_type === 'PROCEDURE') : [];
  const getFunctions = () => routinesData ? routinesData.routines.filter(r => r.routine_type === 'FUNCTION') : [];

  // CSV Export handlers
  const [csvExporting, setCsvExporting] = useState<string | null>(null);

  const handleExportTablesCsv = async () => {
    setCsvExporting('tables');
    try {
      const data = await getAllReportTables(id, tablesDataset !== 'all' ? tablesDataset : undefined);
      const tables = data.tables.filter((t: any) => t.table_type === 'BASE TABLE');
      downloadCsv(tables, [
        { key: 'dataset_name', header: 'Dataset Name' },
        { key: 'table_name', header: 'Table Name' },
        { key: 'creation_time', header: 'Creation Time' },
        { key: 'row_count', header: 'Row Count' },
        { key: 'size_mb', header: 'Size (MB)' },
        { key: 'partitioning_columns', header: 'Partitioning' },
        { key: 'clustering_columns', header: 'Clustering' },
      ], `tables_export.csv`);
    } catch (err) { console.error('CSV export failed:', err); }
    finally { setCsvExporting(null); }
  };

  const handleExportViewsCsv = async () => {
    setCsvExporting('views');
    try {
      const data = await getAllReportViews(id);
      downloadCsv(data.views, [
        { key: 'view_name', header: 'View Name' },
        { key: 'view_type', header: 'Type' },
        { key: 'creation_time', header: 'Creation Time' },
        { key: 'dependent_tables', header: 'Dependent Tables' },
        { key: 'dependent_views', header: 'Dependent Views' },
        { key: 'dependent_functions', header: 'Dependent Functions' },
      ], `views_export.csv`);
    } catch (err) { console.error('CSV export failed:', err); }
    finally { setCsvExporting(null); }
  };

  const handleExportRoutinesCsv = (type: 'procedures' | 'functions') => {
    const routines = type === 'procedures' ? getStoredProcedures() : getFunctions();
    downloadCsv(routines, [
      { key: 'routine_name', header: 'Name' },
      { key: 'routine_type', header: 'Type' },
      { key: 'external_language', header: 'Language' },
      { key: 'return_type', header: 'Return Type' },
      { key: 'creation_time', header: 'Creation Time' },
      { key: 'dependent_tables', header: 'Dependent Tables' },
      { key: 'dependent_views', header: 'Dependent Views' },
    ], `${type}_export.csv`);
  };

  const handleExportMLModelsCsv = () => {
    if (!mlModelsData) return;
    if (mlModelsData.ml_models.length > 0) {
      downloadCsv(mlModelsData.ml_models, [
        { key: 'model_name', header: 'Model Name' },
        { key: 'model_type', header: 'Model Type' },
        { key: 'dataset_name', header: 'Dataset' },
        { key: 'creation_time', header: 'Created' },
        { key: 'last_modified_time', header: 'Last Modified' },
      ], `ml_models_export.csv`);
    }
    if (mlModelsData.spark_models.length > 0) {
      downloadCsv(mlModelsData.spark_models, [
        { key: 'routine_name', header: 'Routine Name' },
        { key: 'routine_type', header: 'Type' },
        { key: 'external_language', header: 'Language' },
        { key: 'creation_time', header: 'Created' },
      ], `spark_models_export.csv`);
    }
  };

  const handleDownloadPDF = async (selectedSections: string[]) => {
    setDownloading(true);
    try {
      const report = await getAssessmentReport(id);
      let recommendations = null; let tcoData = null; let queryInsightsData = null;
      if (selectedSections.includes('recommendations')) { try { recommendations = await getAssessmentRecommendations(id); } catch (e) { console.warn('Could not fetch recommendations:', e); } }
      if (selectedSections.includes('tco')) { try { tcoData = await getAssessmentTCO(id); } catch (e) { console.warn('Could not fetch TCO:', e); } }
      if (selectedSections.includes('query-insights')) { try { const resp = await fetch(`/api/assessments/${id}/query-insights?timeframe=all&page_size=10&sort_by=slot_milliseconds`); if (resp.ok) queryInsightsData = await resp.json(); } catch (e) { console.warn('Could not fetch query insights:', e); } }
      await generatePDF({ report, selectedSections, assessmentId: id, recommendations, tcoData, queryInsightsData });
    } catch (err) { console.error('PDF generation failed:', err); alert('Failed to generate PDF. Please try again.'); }
    finally { setDownloading(false); setShowDownloadModal(false); }
  };

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
  ];

  return (
    <div className="assessment-report-page">
      <div className="report-header">
        <Button variant="outline" onClick={() => navigate('/assessments')}><ArrowLeft size={16} /> Back</Button>
        <div className="report-title-section">
          <h1 className="report-title"><FileSearch size={24} /> {summary.assessment.name}</h1>
          <Badge variant={summary.assessment.status?.trim() === 'completed' ? 'success' : 'warning'}>{summary.assessment.status}</Badge>
        </div>
        <Button variant="outline" onClick={() => setShowDownloadModal(true)}><Download size={16} /> Download Report</Button>
      </div>

      <div className="report-tabs">
        {tabs.map(tab => { const Icon = tab.icon; return (
          <button key={tab.id} className={`report-tab ${activeTab === tab.id ? 'active' : ''}`} onClick={() => setActiveTab(tab.id)}>
            <Icon size={16} /> <span>{tab.label}</span>
          </button>
        ); })}
      </div>

      <div className="report-content">
        {activeTab === 'summary' && <BQSummarySection assessment={summary.assessment} datasets={summary.datasets} setActiveTab={setActiveTab} />}
        {activeTab === 'datasets' && <BQDatasetsSection datasets={summary.datasets} />}
        {activeTab === 'tables' && (
          tablesLoading ? <TabSpinner message="Loading tables..." /> :
          tablesError ? <TabError message={tablesError} onRetry={() => fetchTables(tablesPage, tablesPageSize, tablesDataset)} /> :
          tablesData ? (
            <div className="section-content">
              <TablesSection tables={tablesData.tables} columns={tablesData.columns} datasets={tablesData.datasets || []} selectedDataset={tablesDataset} onDatasetChange={(ds: string) => { setTablesDataset(ds); setTablesPage(1); }} onExportCsv={handleExportTablesCsv} csvExporting={csvExporting === 'tables'} />
              <PaginationControls page={tablesData.page} totalPages={tablesData.total_pages} total={tablesData.total} pageSize={tablesPageSize} onPageChange={setTablesPage} onPageSizeChange={(s) => { setTablesPageSize(s); setTablesPage(1); }} />
            </div>
          ) : <TabSpinner message="Loading tables..." />
        )}
        {activeTab === 'views' && (
          viewsLoading ? <TabSpinner message="Loading views..." /> :
          viewsError ? <TabError message={viewsError} onRetry={() => fetchViews(viewsPage, viewsPageSize)} /> :
          viewsData ? (
            <div className="section-content">
              <ViewsSection views={viewsData.views} onExportCsv={handleExportViewsCsv} csvExporting={csvExporting === 'views'} />
              <PaginationControls page={viewsData.page} totalPages={viewsData.total_pages} total={viewsData.total} pageSize={viewsPageSize} onPageChange={setViewsPage} onPageSizeChange={(s) => { setViewsPageSize(s); setViewsPage(1); }} />
            </div>
          ) : <TabSpinner message="Loading views..." />
        )}
        {activeTab === 'procedures' && (
          routinesLoading ? <TabSpinner message="Loading stored procedures..." /> :
          routinesError ? <TabError message={routinesError} /> :
          routinesData ? <RoutinesSection routines={getStoredProcedures()} title="Stored Procedures" onExportCsv={() => handleExportRoutinesCsv('procedures')} /> :
          <TabSpinner message="Loading stored procedures..." />
        )}
        {activeTab === 'functions' && (
          routinesLoading ? <TabSpinner message="Loading functions..." /> :
          routinesError ? <TabError message={routinesError} /> :
          routinesData ? <RoutinesSection routines={getFunctions()} title="Functions" onExportCsv={() => handleExportRoutinesCsv('functions')} /> :
          <TabSpinner message="Loading functions..." />
        )}
        {activeTab === 'ml-models' && (
          mlModelsLoading ? <TabSpinner message="Loading ML models..." /> :
          mlModelsError ? <TabError message={mlModelsError} /> :
          mlModelsData ? <MLModelsSection mlModels={mlModelsData.ml_models} sparkModels={mlModelsData.spark_models} onExportCsv={handleExportMLModelsCsv} /> :
          <TabSpinner message="Loading ML models..." />
        )}
        {activeTab === 'query-insights' && <QueryInsightsSection assessmentId={id} isSQLServer={false} />}
        {activeTab === 'user-insights' && (
          userInsightsLoading ? <TabSpinner message="Loading user insights..." /> :
          userInsightsError ? <TabError message={userInsightsError} /> :
          userInsightsData ? <UserInsightsSection queryStats={userInsightsData.query_stats} /> :
          <TabSpinner message="Loading user insights..." />
        )}
        {activeTab === 'security' && (
          securityLoading ? <TabSpinner message="Loading security data..." /> :
          securityError ? <TabError message={securityError} /> :
          securityData ? <SecuritySection securityPolicies={securityData.security_policies} columns={securityData.columns} tables={securityData.tables} /> :
          <TabSpinner message="Loading security data..." />
        )}
      </div>

      <DownloadReportModal isOpen={showDownloadModal} onClose={() => setShowDownloadModal(false)} assessmentName={summary.assessment.name} onDownload={handleDownloadPDF} downloading={downloading} />
    </div>
  );
};


// ============ BigQuery Summary Section ============
const BQSummarySection: React.FC<{ assessment: ReportSummary['assessment']; datasets: DatasetSummary[]; setActiveTab: (t: string) => void }> = ({ assessment, setActiveTab }) => (
  <div className="section-content">
    <h2 className="section-heading">Assessment Summary</h2>
    <div className="summary-grid">
      <div className="summary-card summary-card-clickable" onClick={() => setActiveTab('datasets')}>
        <div className="summary-icon" style={{ background: '#EFF6FF', color: '#2563EB' }}><Database size={24} /></div>
        <div className="summary-content"><div className="summary-value">{assessment.total_datasets}</div><div className="summary-label">Datasets</div></div>
      </div>
      <div className="summary-card summary-card-clickable" onClick={() => setActiveTab('tables')}>
        <div className="summary-icon" style={{ background: '#F0FDF4', color: '#16A34A' }}><TableIcon size={24} /></div>
        <div className="summary-content"><div className="summary-value">{assessment.total_tables}</div><div className="summary-label">Tables</div></div>
      </div>
      <div className="summary-card summary-card-clickable" onClick={() => setActiveTab('views')}>
        <div className="summary-icon" style={{ background: '#FEF3C7', color: '#CA8A04' }}><Eye size={24} /></div>
        <div className="summary-content"><div className="summary-value">{assessment.total_views}</div><div className="summary-label">Views</div></div>
      </div>
      <div className="summary-card summary-card-clickable" onClick={() => setActiveTab('procedures')}>
        <div className="summary-icon" style={{ background: '#FCE7F3', color: '#DB2777' }}><Code size={24} /></div>
        <div className="summary-content"><div className="summary-value">{assessment.total_routines}</div><div className="summary-label">SPs & Functions</div></div>
      </div>
      <div className="summary-card summary-card-clickable" onClick={() => setActiveTab('ml-models')}>
        <div className="summary-icon" style={{ background: '#EDE9FE', color: '#7C3AED' }}><Brain size={24} /></div>
        <div className="summary-content"><div className="summary-value">{assessment.total_ml_models}</div><div className="summary-label">ML Models</div></div>
      </div>
      <div className="summary-card">
        <div className="summary-icon" style={{ background: '#F3F4F6', color: '#6B7280' }}><Database size={24} /></div>
        <div className="summary-content"><div className="summary-value">{formatSize(assessment.total_size_mb)}</div><div className="summary-label">Total Data Size</div></div>
      </div>
    </div>
    <div className="details-section">
      <h3 className="subsection-heading">Assessment Details</h3>
      <div className="details-grid">
        <div className="detail-item"><span className="detail-label">Assessment Name:</span><span className="detail-value">{assessment.name}</span></div>
        <div className="detail-item"><span className="detail-label">Version:</span><span className="detail-value">v{assessment.version || 1}</span></div>
        <div className="detail-item"><span className="detail-label">Project ID:</span><span className="detail-value">{assessment.project_id}</span></div>
        <div className="detail-item"><span className="detail-label">Status:</span><span className="detail-value" style={{ textTransform: 'capitalize' }}>{assessment.status}</span></div>
        <div className="detail-item"><span className="detail-label">Started At:</span><span className="detail-value">{formatDate(assessment.started_at)}</span></div>
        <div className="detail-item"><span className="detail-label">Completed At:</span><span className="detail-value">{formatDate(assessment.completed_at)}</span></div>
        <div className="detail-item"><span className="detail-label">Duration:</span><span className="detail-value">{(() => {
          if (!assessment.started_at || !assessment.completed_at) return 'N/A';
          const s = new Date(assessment.started_at).getTime();
          const e = new Date(assessment.completed_at).getTime();
          const sec = Math.floor((e - s) / 1000);
          if (sec < 60) return `${sec}s`;
          if (sec < 3600) return `${Math.floor(sec / 60)}m ${sec % 60}s`;
          return `${Math.floor(sec / 3600)}h ${Math.floor((sec % 3600) / 60)}m`;
        })()}</span></div>
        <div className="detail-item"><span className="detail-label">Total Data Size:</span><span className="detail-value">{formatSize(assessment.total_size_mb)}</span></div>
        <div className="detail-item"><span className="detail-label">Created By:</span><span className="detail-value">{assessment.created_by || 'System'}</span></div>
        <div className="detail-item"><span className="detail-label">Workspace ID:</span><span className="detail-value">{assessment.workspace_id}</span></div>
      </div>
    </div>
  </div>
);

// ============ BigQuery Datasets Section ============
const BQDatasetsSection: React.FC<{ datasets: DatasetSummary[] }> = ({ datasets }) => (
  <div className="section-content">
    <h2 className="section-heading">Datasets ({datasets.length})</h2>
    {datasets.length === 0 ? (
      <div className="empty-state"><Database size={48} /><p>No datasets found</p></div>
    ) : (
      <div className="table-container">
        <table className="data-table">
          <thead><tr><th>Dataset Name</th><th>Region</th><th>Created Date</th><th>Number of Tables</th><th>Tables Size</th></tr></thead>
          <tbody>
            {datasets.map((dataset, index) => (
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


// ============ Tables Section ============
const TablesSection: React.FC<{
  tables: AssessmentReportTable[];
  columns: AssessmentReportColumn[];
  datasets: string[];
  selectedDataset: string;
  onDatasetChange: (ds: string) => void;
  onExportCsv?: () => void;
  csvExporting?: boolean;
}> = ({ tables, columns, datasets, selectedDataset, onDatasetChange, onExportCsv, csvExporting }) => {
  const [selectedTable, setSelectedTable] = useState<AssessmentReportTable | null>(null);
  const [showColumnsModal, setShowColumnsModal] = useState(false);

  const baseTables = tables.filter(t => t.table_type === 'BASE TABLE');
  const datasetOptions = [
    { value: 'all', label: `All Datasets (${datasets.length})` },
    ...datasets.map(ds => ({ value: ds, label: ds })),
  ];

  const formatColumnArray = (arr: any) => {
    if (!arr) return 'None';
    if (!Array.isArray(arr)) {
      if (typeof arr === 'string') { try { const p = JSON.parse(arr); if (Array.isArray(p)) arr = p; else return 'None'; } catch { return 'None'; } } else return 'None';
    }
    const filtered = arr.filter((item: any) => item && typeof item === 'string' && item.length > 1 && item !== '[]' && item !== '""');
    return filtered.length === 0 ? 'None' : filtered.join(', ');
  };

  return (
    <div className="section-content">
      <div className="section-header-row">
        <h2 className="section-heading">Tables ({baseTables.length})</h2>
        <div className="section-filters">
          {onExportCsv && <Button variant="outline" onClick={onExportCsv} disabled={csvExporting}><Download size={14} /> {csvExporting ? 'Exporting...' : 'Export CSV'}</Button>}
          <Select value={selectedDataset} onChange={(v: any) => onDatasetChange(v)} options={datasetOptions} />
        </div>
      </div>
      {baseTables.length === 0 ? (
        <div className="empty-state"><TableIcon size={48} /><p>No tables found</p></div>
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead><tr><th>Dataset Name</th><th>Table Name</th><th>Creation Time</th><th>Row Count</th><th>Size</th><th>Partitioning</th><th>Clustering</th></tr></thead>
            <tbody>
              {baseTables.map(table => (
                <tr key={table.id}>
                  <td className="font-medium">{table.dataset_name}</td>
                  <td><button className="table-name-link" onClick={() => { setSelectedTable(table); setShowColumnsModal(true); }} title="Click to view columns">{table.table_name}</button></td>
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
      {showColumnsModal && selectedTable && (
        <div className="modal-overlay" onClick={() => setShowColumnsModal(false)}>
          <div className="modal-content columns-modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title"><TableIcon size={20} />{selectedTable.dataset_name}.{selectedTable.table_name}</h3>
              <button className="modal-close" onClick={() => setShowColumnsModal(false)}>×</button>
            </div>
            <div className="modal-body">
              <div className="table-container">
                <table className="data-table compact">
                  <thead><tr><th>Column Name</th><th>Data Type</th><th>Nullable</th><th>Position</th><th>Partitioning</th><th>Clustering</th><th>Policy Tags</th></tr></thead>
                  <tbody>
                    {columns.filter(c => c.table_id === selectedTable.id).map((column, idx) => (
                      <tr key={idx}>
                        <td className="font-medium">{column.column_name}</td>
                        <td className="font-mono text-sm">{column.data_type}</td>
                        <td className="text-center">{column.is_nullable ? <Badge variant="default">Yes</Badge> : <Badge variant="error">No</Badge>}</td>
                        <td className="text-center">{column.ordinal_position}</td>
                        <td className="text-center">{column.is_partitioning_column ? <Badge variant="info">Yes</Badge> : <span className="text-muted">-</span>}</td>
                        <td className="text-center">{column.clustering_ordinal_position !== null ? <Badge variant="info">{column.clustering_ordinal_position}</Badge> : <span className="text-muted">-</span>}</td>
                        <td className="text-sm">{column.policy_tags && column.policy_tags.length > 0 ? formatColumnArray(column.policy_tags) : <span className="text-muted">None</span>}</td>
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


// ============ Views Section ============
const ViewsSection: React.FC<{ views: AssessmentReportView[]; onExportCsv?: () => void; csvExporting?: boolean }> = ({ views, onExportCsv, csvExporting }) => {
  const [expandedView, setExpandedView] = useState<number | null>(null);
  const [selectedDataset, setSelectedDataset] = useState<string | number>('all');
  const [selectedViewType, setSelectedViewType] = useState<string | number>('all');

  const getDataset = (v: any) => { const name = v.view_name || ''; return name.includes('.') ? name.split('.')[0] : 'Unknown'; };
  const datasetOptions = [
    { value: 'all', label: `All Datasets (${views.length})` },
    ...Array.from(new Set(views.map(v => getDataset(v)))).sort().map((ds: any) => ({ value: ds, label: `${ds} (${views.filter(v => getDataset(v) === ds).length})` })),
  ];
  const viewTypeOptions = [
    { value: 'all', label: `All Types (${views.length})` },
    ...Array.from(new Set(views.map(v => v.view_type || 'VIEW'))).sort().map((vt: any) => ({ value: vt, label: `${vt === 'MATERIALIZED_VIEW' ? 'Materialized View' : 'View'} (${views.filter(v => (v.view_type || 'VIEW') === vt).length})` })),
  ];
  const filteredViews = views.filter(v => {
    const dsMatch = selectedDataset === 'all' || getDataset(v) === selectedDataset;
    const vtMatch = selectedViewType === 'all' || (v.view_type || 'VIEW') === selectedViewType;
    return dsMatch && vtMatch;
  });

  return (
    <div className="section-content">
      <div className="section-header-row">
        <h2 className="section-heading">Views ({filteredViews.length})</h2>
        <div className="section-filters">
          {onExportCsv && <Button variant="outline" onClick={onExportCsv} disabled={csvExporting}><Download size={14} /> {csvExporting ? 'Exporting...' : 'Export CSV'}</Button>}
          <Select value={selectedDataset} onChange={setSelectedDataset} options={datasetOptions} />
          <Select value={selectedViewType} onChange={setSelectedViewType} options={viewTypeOptions} />
        </div>
      </div>
      {filteredViews.length === 0 ? (
        <div className="empty-state"><Eye size={48} /><p>No views found</p></div>
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead><tr><th>Dataset</th><th>Name</th><th>Type</th><th>Created Time</th></tr></thead>
            <tbody>
              {filteredViews.map((view: any, index: number) => {
                const isExpanded = expandedView === index;
                const totalDeps = (view.dependent_tables?.length || 0) + (view.dependent_views?.length || 0) + (view.dependent_functions?.length || 0);
                const dataset = getDataset(view);
                const viewName = view.view_name?.includes('.') ? view.view_name.split('.').slice(1).join('.') : view.view_name;
                return (
                  <React.Fragment key={index}>
                    <tr>
                      <td className="font-medium">{dataset}</td>
                      <td><button className="table-name-link" onClick={() => setExpandedView(isExpanded ? null : index)} title="Click to view dependencies">{viewName}</button></td>
                      <td><Badge variant={view.view_type === 'MATERIALIZED_VIEW' ? 'info' : 'default'}>{view.view_type === 'MATERIALIZED_VIEW' ? 'Materialized' : 'View'}</Badge></td>
                      <td className="text-sm">{formatDate(view.creation_time)}</td>
                    </tr>
                    {isExpanded && (
                      <tr className="expanded-row">
                        <td colSpan={4}>
                          <div className="dependency-details">
                            {view.view_definition && (
                              <div className="dependency-section">
                                <h4 className="dependency-section-title"><Code size={16} />SQL Definition</h4>
                                <pre className="sql-code"><code>{view.view_definition}</code></pre>
                              </div>
                            )}
                            {totalDeps > 0 ? (
                              <div className="dependency-section">
                                <h4 className="dependency-section-title"><Database size={16} />Dependencies ({totalDeps})</h4>
                                {view.dependent_tables?.length > 0 && (
                                  <div className="dependency-group"><h5 className="dependency-group-title"><TableIcon size={14} />Tables ({view.dependent_tables.length})</h5><div className="dependency-list">{view.dependent_tables.map((t: string, i: number) => <Badge key={i} variant="default" className="dependency-badge">{t}</Badge>)}</div></div>
                                )}
                                {view.dependent_views?.length > 0 && (
                                  <div className="dependency-group"><h5 className="dependency-group-title"><Eye size={14} />Views ({view.dependent_views.length})</h5><div className="dependency-list">{view.dependent_views.map((v: string, i: number) => <Badge key={i} variant="info" className="dependency-badge">{v}</Badge>)}</div></div>
                                )}
                                {view.dependent_functions?.length > 0 && (
                                  <div className="dependency-group"><h5 className="dependency-group-title"><Code size={14} />Functions ({view.dependent_functions.length})</h5><div className="dependency-list">{view.dependent_functions.map((f: string, i: number) => <Badge key={i} variant="warning" className="dependency-badge">{f}</Badge>)}</div></div>
                                )}
                              </div>
                            ) : (
                              <div className="dependency-section"><h4 className="dependency-section-title"><Database size={16} />Dependencies</h4><p className="text-muted">No dependencies found</p></div>
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

// ============ Routines Section ============
const RoutinesSection: React.FC<{ routines: AssessmentReportRoutine[]; title: string; onExportCsv?: () => void }> = ({ routines, title, onExportCsv }) => {
  const [expandedRoutine, setExpandedRoutine] = useState<number | null>(null);
  const [selectedDataset, setSelectedDataset] = useState<string | number>('all');

  const getDataset = (r: any) => { const name = r.routine_name || ''; return name.includes('.') ? name.split('.')[0] : 'Unknown'; };
  const datasetOptions = [
    { value: 'all', label: `All Datasets (${routines.length})` },
    ...Array.from(new Set(routines.map(r => getDataset(r)))).sort().map((ds: any) => ({ value: ds, label: `${ds} (${routines.filter(r => getDataset(r) === ds).length})` })),
  ];
  const filteredRoutines = selectedDataset === 'all' ? routines : routines.filter(r => getDataset(r) === selectedDataset);

  return (
    <div className="section-content">
      <div className="section-header-row">
        <h2 className="section-heading">{title} ({filteredRoutines.length})</h2>
        <div className="section-filters">
          {onExportCsv && <Button variant="outline" onClick={onExportCsv}><Download size={14} /> Export CSV</Button>}
          <Select value={selectedDataset} onChange={setSelectedDataset} options={datasetOptions} />
        </div>
      </div>
      {filteredRoutines.length === 0 ? (
        <div className="empty-state"><Code size={48} /><p>No {title.toLowerCase()} found</p></div>
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead><tr><th>Dataset</th><th>Name</th><th>Type</th><th>Language</th><th>Created Time</th></tr></thead>
            <tbody>
              {filteredRoutines.map((routine: any, index: number) => {
                const isExpanded = expandedRoutine === index;
                const totalDeps = (routine.dependent_tables?.length || 0) + (routine.dependent_views?.length || 0) + (routine.dependent_functions?.length || 0) + (routine.calls_procedures?.length || 0);
                const dataset = getDataset(routine);
                const routineName = routine.routine_name?.includes('.') ? routine.routine_name.split('.').slice(1).join('.') : routine.routine_name;
                return (
                  <React.Fragment key={index}>
                    <tr>
                      <td className="font-medium">{dataset}</td>
                      <td><button className="table-name-link" onClick={() => setExpandedRoutine(isExpanded ? null : index)} title="Click to view dependencies">{routineName}</button></td>
                      <td><Badge variant="default">{routine.routine_type}</Badge></td>
                      <td>{routine.external_language ? <Badge variant="info">{routine.external_language}</Badge> : <span className="text-muted">SQL</span>}</td>
                      <td className="text-sm">{formatDate(routine.creation_time)}</td>
                    </tr>
                    {isExpanded && (
                      <tr className="expanded-row">
                        <td colSpan={5}>
                          <div className="dependency-details">
                            {(routine.return_type || routine.external_language) && (
                              <div className="dependency-section">
                                <h4 className="dependency-section-title"><Code size={16} />Routine Information</h4>
                                <div className="routine-metadata">
                                  {routine.return_type && <div className="metadata-item"><span className="metadata-label">Return Type:</span><code className="metadata-value">{routine.return_type}</code></div>}
                                  {routine.external_language && <div className="metadata-item"><span className="metadata-label">Language:</span><Badge variant="info">{routine.external_language}</Badge></div>}
                                </div>
                              </div>
                            )}
                            {routine.definition && (
                              <div className="dependency-section"><h4 className="dependency-section-title"><Code size={16} />Definition</h4><pre className="sql-code"><code>{routine.definition}</code></pre></div>
                            )}
                            {totalDeps > 0 ? (
                              <div className="dependency-section">
                                <h4 className="dependency-section-title"><Database size={16} />Dependencies ({totalDeps})</h4>
                                {routine.dependent_tables?.length > 0 && <div className="dependency-group"><h5 className="dependency-group-title"><TableIcon size={14} />Tables ({routine.dependent_tables.length})</h5><div className="dependency-list">{routine.dependent_tables.map((t: string, i: number) => <Badge key={i} variant="default" className="dependency-badge">{t}</Badge>)}</div></div>}
                                {routine.dependent_views?.length > 0 && <div className="dependency-group"><h5 className="dependency-group-title"><Eye size={14} />Views ({routine.dependent_views.length})</h5><div className="dependency-list">{routine.dependent_views.map((v: string, i: number) => <Badge key={i} variant="info" className="dependency-badge">{v}</Badge>)}</div></div>}
                                {routine.dependent_functions?.length > 0 && <div className="dependency-group"><h5 className="dependency-group-title"><Code size={14} />Functions ({routine.dependent_functions.length})</h5><div className="dependency-list">{routine.dependent_functions.map((f: string, i: number) => <Badge key={i} variant="warning" className="dependency-badge">{f}</Badge>)}</div></div>}
                                {routine.calls_procedures?.length > 0 && <div className="dependency-group"><h5 className="dependency-group-title"><Code size={14} />Calls Procedures ({routine.calls_procedures.length})</h5><div className="dependency-list">{routine.calls_procedures.map((p: string, i: number) => <Badge key={i} variant="error" className="dependency-badge">{p}</Badge>)}</div></div>}
                              </div>
                            ) : (
                              <div className="dependency-section"><h4 className="dependency-section-title"><Database size={16} />Dependencies</h4><p className="text-muted">No dependencies found</p></div>
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


// ============ ML Models Section ============
const MLModelsSection: React.FC<{ mlModels: any[]; sparkModels: any[]; onExportCsv?: () => void }> = ({ mlModels, sparkModels, onExportCsv }) => (
  <div className="section-content">
    <div className="section-header-row">
      <h2 className="section-heading">ML & Spark Models</h2>
      {onExportCsv && (mlModels.length > 0 || sparkModels.length > 0) && (
        <div className="section-filters"><Button variant="outline" onClick={onExportCsv}><Download size={14} /> Export CSV</Button></div>
      )}
    </div>
    <div className="subsection">
      <h3 className="subsection-heading">BigQuery ML Models ({mlModels.length})</h3>
      {mlModels.length === 0 ? <div className="empty-state-small"><p>No ML models found</p></div> : (
        <div className="table-container">
          <table className="data-table">
            <thead><tr><th>Model Name</th><th>Model Type</th><th>Dataset</th><th>Created</th><th>Last Modified</th></tr></thead>
            <tbody>{mlModels.map((m, i) => <tr key={i}><td className="font-medium">{m.model_name}</td><td><Badge variant="info">{m.model_type}</Badge></td><td>{m.dataset_name}</td><td className="text-sm">{formatDate(m.creation_time)}</td><td className="text-sm">{formatDate(m.last_modified_time)}</td></tr>)}</tbody>
          </table>
        </div>
      )}
    </div>
    <div className="subsection">
      <h3 className="subsection-heading">Spark Models ({sparkModels.length})</h3>
      {sparkModels.length === 0 ? <div className="empty-state-small"><p>No Spark models found</p></div> : (
        <div className="table-container">
          <table className="data-table">
            <thead><tr><th>Routine Name</th><th>Type</th><th>Language</th><th>Created</th></tr></thead>
            <tbody>{sparkModels.map((m, i) => <tr key={i}><td className="font-medium">{m.routine_name}</td><td><Badge variant="warning">Spark</Badge></td><td><Badge variant="default">{m.external_language}</Badge></td><td className="text-sm">{formatDate(m.creation_time)}</td></tr>)}</tbody>
          </table>
        </div>
      )}
    </div>
  </div>
);

// ============ User Insights Section ============
const UserInsightsSection: React.FC<{ queryStats: any[] }> = ({ queryStats }) => {
  const [timeFilter, setTimeFilter] = useState('all');
  const getFilteredQueries = () => {
    if (timeFilter === 'all') return queryStats;
    const now = new Date(); const cutoff = new Date();
    switch (timeFilter) { case '24h': cutoff.setHours(now.getHours() - 24); break; case '7d': cutoff.setDate(now.getDate() - 7); break; case '30d': cutoff.setDate(now.getDate() - 30); break; default: return queryStats; }
    return queryStats.filter((q: any) => q.execution_time && new Date(q.execution_time) >= cutoff);
  };
  const filteredQueries = getFilteredQueries();
  const userStats = filteredQueries.reduce((acc: any, q: any) => {
    const user = q.user_email || 'Unknown';
    if (!acc[user]) acc[user] = { queryCount: 0, totalBytesScanned: 0, totalSlotMilliseconds: 0, cacheHits: 0, totalQueries: 0 };
    acc[user].queryCount++; acc[user].totalQueries++; acc[user].totalBytesScanned += q.bytes_scanned || 0; acc[user].totalSlotMilliseconds += q.slot_milliseconds || 0; if (q.cache_hit) acc[user].cacheHits++;
    return acc;
  }, {});
  const users = Object.entries(userStats).map(([email, stats]: [string, any]) => ({
    email, queryCount: stats.queryCount, totalBytesScanned: stats.totalBytesScanned, totalSlotMilliseconds: stats.totalSlotMilliseconds,
    cacheHitRate: stats.totalQueries > 0 ? (stats.cacheHits / stats.totalQueries * 100).toFixed(1) : '0.0',
  })).sort((a, b) => b.queryCount - a.queryCount);

  const formatBytes = (bytes: number) => { if (bytes === 0) return '0 B'; const gb = bytes / (1024**3); if (gb >= 1) return `${gb.toFixed(2)} GB`; const mb = bytes / (1024**2); if (mb >= 1) return `${mb.toFixed(2)} MB`; return `${(bytes / 1024).toFixed(2)} KB`; };
  const formatSlots = (ms: number) => { if (ms === 0) return '0'; const s = ms / 1000; if (s >= 3600) return `${(s / 3600).toFixed(2)} slot-hrs`; if (s >= 60) return `${(s / 60).toFixed(2)} slot-mins`; return `${s.toFixed(2)} slot-secs`; };

  return (
    <div className="section-content">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h2 className="section-heading">User Insights ({users.length} users)</h2>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{ fontSize: '14px', color: 'var(--color-text-secondary)' }}>Time Frame:</span>
          <Select value={timeFilter} onChange={(val) => setTimeFilter(val as string)} options={[{ value: 'all', label: 'All Time' }, { value: '24h', label: 'Last 24 Hours' }, { value: '7d', label: 'Last 7 Days' }, { value: '30d', label: 'Last 30 Days' }]} />
        </div>
      </div>
      {users.length === 0 ? <div className="empty-state"><Users size={48} /><p>No user data found for selected time frame</p></div> : (
        <div className="table-container">
          <table className="data-table">
            <thead><tr><th style={{ textAlign: 'left' }}>User Email</th><th style={{ textAlign: 'right' }}>Queries Executed</th><th style={{ textAlign: 'right' }}>Total Data Scanned</th><th style={{ textAlign: 'right' }}>Slots Utilized</th><th style={{ textAlign: 'right' }}>Cache Hit Ratio</th></tr></thead>
            <tbody>{users.map((u, i) => (
              <tr key={i}>
                <td className="font-medium" style={{ textAlign: 'left' }}>{u.email}</td>
                <td style={{ textAlign: 'right' }}>{u.queryCount.toLocaleString()}</td>
                <td style={{ textAlign: 'right' }}>{formatBytes(u.totalBytesScanned)}</td>
                <td style={{ textAlign: 'right' }}>{formatSlots(u.totalSlotMilliseconds)}</td>
                <td style={{ textAlign: 'right' }}><Badge variant={parseFloat(u.cacheHitRate) > 50 ? 'success' : parseFloat(u.cacheHitRate) > 20 ? 'warning' : 'default'}>{u.cacheHitRate}%</Badge></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
    </div>
  );
};


// ============ Security Section ============
const SecuritySection: React.FC<{ securityPolicies: any[]; columns: any[]; tables: any[] }> = ({ securityPolicies, columns, tables }) => {
  const [expandedPolicy, setExpandedPolicy] = useState<number | null>(null);
  const rlsPolicies = securityPolicies.filter((p: any) => p.security_type === 'RLS');
  const tableIdToName = tables.reduce((acc: any, t: any) => { acc[t.id] = `${t.dataset_name}.${t.table_name}`; return acc; }, {});

  const parsePolicyTags = (pt: any): string[] => {
    if (!pt) return []; if (Array.isArray(pt)) return pt;
    if (typeof pt === 'string') { if (pt.trim() === '' || pt === '[]') return []; try { const p = JSON.parse(pt); return Array.isArray(p) ? p : []; } catch { return []; } }
    return [];
  };

  const clsColumns = columns.map((col: any) => ({ ...col, policy_tags: parsePolicyTags(col.policy_tags), table_name: tableIdToName[col.table_id] || 'Unknown' })).filter((c: any) => c.policy_tags.length > 0);
  const clsFromPolicies = securityPolicies.filter((p: any) => p.security_type === 'CLS').map((p: any) => ({ column_name: p.security_metadata?.column_name || p.policy_name?.replace('policy_tag_', '') || 'Unknown', data_type: 'N/A', policy_tags: [p.security_metadata?.policy_tag || p.policy_name || 'Policy Tag'], table_name: p.table_name || 'Unknown' }));
  const allClsColumns = [...clsColumns];
  const existingKeys = new Set(clsColumns.map((c: any) => `${c.table_name}.${c.column_name}`));
  for (const cp of clsFromPolicies) { if (!existingKeys.has(`${cp.table_name}.${cp.column_name}`)) allClsColumns.push(cp); }
  const clsByTable = allClsColumns.reduce((acc: any, col: any) => { if (!acc[col.table_name]) acc[col.table_name] = []; acc[col.table_name].push(col); return acc; }, {});
  const totalSecurityItems = rlsPolicies.length + Object.keys(clsByTable).length;

  return (
    <div className="section-content">
      <h2 className="section-heading">Security Policies</h2>
      {totalSecurityItems === 0 ? <div className="empty-state"><Shield size={48} /><p>No security policies found</p></div> : (
        <div className="security-sections">
          {rlsPolicies.length > 0 && (
            <div className="security-subsection">
              <h3 className="subsection-heading"><Shield size={20} />Row-Level Security (RLS) Policies ({rlsPolicies.length})</h3>
              <div className="rls-policies-list">
                {rlsPolicies.map((policy: any, index: number) => {
                  const isExpanded = expandedPolicy === index;
                  const hasDDL = policy.security_metadata?.ddl;
                  return (
                    <div key={index} className="rls-policy-card">
                      <div className="rls-policy-header">
                        <div className="rls-policy-info">
                          <h4 className="rls-policy-name"><Shield size={16} />{policy.policy_name}</h4>
                          <div className="rls-policy-meta"><Badge variant="info"><Database size={12} />{policy.table_name}</Badge></div>
                        </div>
                        {hasDDL && <Button variant="outline" size="sm" onClick={() => setExpandedPolicy(isExpanded ? null : index)}>{isExpanded ? 'Hide' : 'Show'} DDL</Button>}
                      </div>
                      <div className="rls-policy-details">
                        <div className="rls-detail-row"><span className="rls-detail-label">Filter Predicate:</span><code className="rls-detail-value">{policy.filter_predicate || 'N/A'}</code></div>
                        <div className="rls-detail-row"><span className="rls-detail-label">Grantees:</span><div className="rls-grantees">{policy.grantees?.length > 0 ? policy.grantees.map((g: string, i: number) => <Badge key={i} variant="success" className="grantee-badge"><Users size={12} />{g.trim()}</Badge>) : <span className="text-muted">No grantees specified</span>}</div></div>
                      </div>
                      {isExpanded && hasDDL && <div className="rls-ddl-section"><div className="rls-ddl-header"><Code size={14} /><span>Policy DDL</span></div><pre className="rls-ddl-code"><code>{policy.security_metadata.ddl}</code></pre></div>}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          {Object.keys(clsByTable).length > 0 && (
            <div className="security-subsection">
              <h3 className="subsection-heading"><Lock size={20} />Column-Level Security (CLS) - Policy Tags ({Object.keys(clsByTable).length} tables)</h3>
              <div className="cls-tables">
                {Object.entries(clsByTable).map(([tableName, cols]: [string, any], tableIdx: number) => (
                  <div key={tableIdx} className="cls-table-group">
                    <h4 className="cls-table-name"><Database size={16} />{tableName}<Badge variant="default" className="cls-column-count">{cols.length} {cols.length === 1 ? 'column' : 'columns'}</Badge></h4>
                    <div className="table-container">
                      <table className="data-table cls-table">
                        <thead><tr><th>Column Name</th><th>Data Type</th><th>Policy Tags</th></tr></thead>
                        <tbody>{cols.map((col: any, i: number) => (
                          <tr key={i}>
                            <td className="font-medium"><Lock size={14} className="inline-icon" />{col.column_name}</td>
                            <td><Badge variant="default">{col.data_type}</Badge></td>
                            <td><div className="policy-tags-list">{col.policy_tags?.length > 0 ? col.policy_tags.map((tag: string, j: number) => <Badge key={j} variant="warning" className="policy-tag"><Shield size={12} />{tag}</Badge>) : <span className="text-muted">No tags</span>}</div></td>
                          </tr>
                        ))}</tbody>
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


// ============ Recommendations Section (self-fetching) ============
export const RecommendationsSection: React.FC<{ assessmentId: number }> = ({ assessmentId }) => {
  const [data, setData] = useState<RecommendationsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDataset, setSelectedDataset] = useState<string | number>('all');
  const [selectedTable, setSelectedTable] = useState<string | number>('all');
  const [dskPage, setDskPage] = useState(1);
  const [dskPageSize, setDskPageSize] = useState<string | number>(20);
  const [expandedArch, setExpandedArch] = useState<number | null>(null);

  useEffect(() => {
    (async () => {
      try { setLoading(true); setData(await getAssessmentRecommendations(assessmentId)); } catch (err: any) { setError(err.detail || err.message || 'Failed'); } finally { setLoading(false); }
    })();
  }, [assessmentId]);

  if (loading) return <TabSpinner message="Generating recommendations..." />;
  if (error || !data) return <TabError message={error || 'No data'} />;

  const { query_classification: qc, dist_sort_keys: dsk, architecture: arch } = data;
  const getDatasetFromTable = (name: string) => name.includes('.') ? name.split('.')[0] : 'Unknown';
  const dskDatasets = Array.from(new Set(dsk.map(r => getDatasetFromTable(r.table_name)))).sort();
  const datasetOptions = [{ value: 'all', label: `All Datasets (${dskDatasets.length})` }, ...dskDatasets.map(ds => ({ value: ds, label: ds }))];
  const filteredDsk = dsk.filter(r => { const ds = getDatasetFromTable(r.table_name); return (selectedDataset === 'all' || ds === selectedDataset) && (selectedTable === 'all' || r.table_name === selectedTable); });
  const tableOptions = [{ value: 'all', label: `All Tables (${(selectedDataset === 'all' ? dsk : dsk.filter(r => getDatasetFromTable(r.table_name) === selectedDataset)).length})` }, ...(selectedDataset === 'all' ? dsk : dsk.filter(r => getDatasetFromTable(r.table_name) === selectedDataset)).map(r => ({ value: r.table_name, label: r.table_name }))];

  return (
    <div className="section-content">
      <h2 className="section-heading">Migration Recommendations</h2>

      {/* Assessment Insights Summary */}
      {arch.insights_summary && arch.insights_summary.length > 0 && (
        <div className="rec-section">
          <h3 className="rec-section-title"><Info size={18} /> Assessment Insights</h3>
          <div style={{ background: '#F8FAFC', border: '1px solid var(--color-divider)', borderRadius: '8px', padding: '16px 20px' }}>
            {arch.insights_summary.map((insight: string, i: number) => (
              <p key={i} style={{ fontSize: '14px', color: 'var(--color-text-primary)', lineHeight: '1.6', margin: i === 0 ? '0' : '10px 0 0' }}>{insight}</p>
            ))}
          </div>
        </div>
      )}

      <div className="rec-section">
        <h3 className="rec-section-title"><TableIcon size={18} /> Distribution & Sort Key Recommendations</h3>
        <div className="section-filters" style={{ marginBottom: 'var(--spacing-4)' }}>
          <SearchableSelect value={selectedDataset} onChange={(v) => { setSelectedDataset(v); setSelectedTable('all'); setDskPage(1); }} options={datasetOptions} placeholder="All Datasets" />
          <SearchableSelect value={selectedTable} onChange={(v) => { setSelectedTable(v); setDskPage(1); }} options={tableOptions} placeholder="All Tables" />
          <SearchableSelect value={dskPageSize} onChange={(v) => { setDskPageSize(v); setDskPage(1); }} options={[{ value: 20, label: '20 rows' }, { value: 50, label: '50 rows' }, { value: 100, label: '100 rows' }, { value: 200, label: '200 rows' }]} placeholder="Rows per page" />
        </div>
        {filteredDsk.length === 0 ? <div className="empty-state-small"><p>No table-level recommendations available.</p></div> : (
          <>
            <div style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginBottom: '8px' }}>Showing {Math.min((dskPage - 1) * Number(dskPageSize) + 1, filteredDsk.length)}–{Math.min(dskPage * Number(dskPageSize), filteredDsk.length)} of {filteredDsk.length} tables</div>
            <div className="table-container">
              <table className="data-table">
                <thead><tr><th>Table</th><th>DISTKEY</th><th>SORTKEY</th><th>Reasoning</th></tr></thead>
                <tbody>{filteredDsk.slice((dskPage - 1) * Number(dskPageSize), dskPage * Number(dskPageSize)).map((row, i) => (
                  <tr key={i}><td className="font-mono font-medium">{row.table_name}</td><td><Badge variant={row.distkey === 'EVEN' ? 'default' : 'info'}>{row.distkey}</Badge></td><td><Badge variant={row.sortkey === 'AUTO' ? 'default' : 'info'}>{row.sortkey}</Badge></td><td><ul className="rec-reasoning-list">{row.reasoning.map((r, j) => <li key={j}>{r}</li>)}</ul></td></tr>
                ))}</tbody>
              </table>
            </div>
            {Math.ceil(filteredDsk.length / Number(dskPageSize)) > 1 && (
              <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '12px', marginTop: '16px' }}>
                <button className="filter-btn" disabled={dskPage <= 1} onClick={() => setDskPage(dskPage - 1)} style={{ padding: '6px 16px', cursor: dskPage <= 1 ? 'not-allowed' : 'pointer', opacity: dskPage <= 1 ? 0.5 : 1 }}>← Previous</button>
                <span style={{ fontSize: '13px', color: 'var(--color-text-secondary)' }}>Page {dskPage} of {Math.ceil(filteredDsk.length / Number(dskPageSize))}</span>
                <button className="filter-btn" disabled={dskPage >= Math.ceil(filteredDsk.length / Number(dskPageSize))} onClick={() => setDskPage(dskPage + 1)} style={{ padding: '6px 16px', cursor: dskPage >= Math.ceil(filteredDsk.length / Number(dskPageSize)) ? 'not-allowed' : 'pointer', opacity: dskPage >= Math.ceil(filteredDsk.length / Number(dskPageSize)) ? 0.5 : 1 }}>Next →</button>
              </div>
            )}
          </>
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
      <div className="rec-section">
        <h3 className="rec-section-title"><Activity size={18} /> Query Classification</h3>
        <div className="rec-cards-row">
          <div className="rec-card rec-card-blue"><div className="rec-card-icon"><Zap size={24} /></div><div className="rec-card-value">{qc.adhoc_count.toLocaleString()}</div><div className="rec-card-label">Ad-hoc Queries</div><div className="rec-card-pct">{qc.adhoc_pct}%</div></div>
          <div className="rec-card rec-card-purple"><div className="rec-card-icon"><TrendingUp size={24} /></div><div className="rec-card-value">{qc.bi_count.toLocaleString()}</div><div className="rec-card-label">BI / Scheduled Queries</div><div className="rec-card-pct">{qc.bi_pct}%</div></div>
          <div className="rec-card rec-card-green"><div className="rec-card-icon"><Activity size={24} /></div><div className="rec-card-value">{qc.total_queries.toLocaleString()}</div><div className="rec-card-label">Total Queries Analyzed</div></div>
        </div>
      </div>

      {/* Workload Categories */}
      {arch.workloads && arch.workloads.length > 0 && (
        <div className="rec-section">
          <h3 className="rec-section-title"><Activity size={18} /> Identified Workload Categories</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
            {arch.workloads.map((w, i) => (
              <div key={i} style={{ background: 'var(--color-bg-surface)', border: '1px solid var(--color-divider)', borderRadius: '8px', padding: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span style={{ fontWeight: 600, fontSize: '14px' }}>{w.name}</span>
                  <Badge variant={w.priority === 'high' ? 'error' : w.priority === 'medium' ? 'warning' : 'default'}>{w.priority}</Badge>
                </div>
                <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginBottom: '10px' }}>{w.description}</p>
                <div style={{ display: 'flex', gap: '12px', fontSize: '12px', color: 'var(--color-text-secondary)' }}>
                  <span>{w.percentage}% of workload</span>
                  <span>{w.query_count.toLocaleString()} queries</span>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '8px' }}>
                  {w.characteristics.map((c, j) => (
                    <span key={j} style={{ fontSize: '11px', padding: '2px 8px', background: '#F3F4F6', borderRadius: '4px', color: 'var(--color-text-secondary)' }}>{c}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Architecture Patterns */}
      {arch.architecture_patterns && arch.architecture_patterns.length > 0 && (
        <div className="rec-section">
          <h3 className="rec-section-title"><Database size={18} /> Architecture Patterns</h3>
          {arch.recommendation && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '12px 16px', marginBottom: '16px', background: arch.recommendation.type === 'combination' ? '#EFF6FF' : '#F0FDF4', border: `1px solid ${arch.recommendation.type === 'combination' ? '#93C5FD' : '#86EFAC'}`, borderRadius: '8px' }}>
              <CheckCircle size={18} color={arch.recommendation.type === 'combination' ? '#2563EB' : '#16A34A'} />
              <span style={{ fontSize: '14px', fontWeight: 500 }}>{arch.recommendation.summary}</span>
            </div>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {arch.architecture_patterns.map((p, i) => {
              const isRecommended = arch.recommendation && (
                arch.recommendation.primary_architecture_id === p.id ||
                (arch.workload_mappings || []).some(m => m.architecture_id === p.id)
              );
              const isExpanded = expandedArch === i;
              return (
                <div key={i} style={{
                  background: isRecommended ? '#FAFFF9' : 'var(--color-bg-surface)',
                  border: `1px solid ${isRecommended ? '#BBF7D0' : 'var(--color-divider)'}`,
                  borderRadius: '8px', padding: '14px 18px', cursor: 'pointer',
                  transition: 'all 0.2s ease'
                }} onClick={() => setExpandedArch(isExpanded ? null : i)}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1 }}>
                      <span style={{ fontSize: '14px', fontWeight: 600 }}>{p.short_name}</span>
                      {isRecommended && <Badge variant="success">Recommended</Badge>}
                      <span style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>{p.description}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <span style={{ fontSize: '20px', fontWeight: 700, color: p.suitability_score >= 70 ? '#16A34A' : p.suitability_score >= 50 ? '#CA8A04' : '#6B7280' }}>{p.suitability_score}%</span>
                      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" style={{ color: 'var(--color-text-secondary)', transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}>
                        <path d="M4 6l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    </div>
                  </div>
                  {isExpanded && (
                    <div style={{ marginTop: '14px', paddingTop: '14px', borderTop: '1px solid var(--color-divider)' }} onClick={e => e.stopPropagation()}>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px' }}>
                        <div>
                          <div style={{ fontSize: '12px', fontWeight: 600, marginBottom: '6px', color: '#16A34A' }}>Strengths</div>
                          {p.strengths.map((s, j) => (
                            <div key={j} style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '3px', display: 'flex', gap: '4px' }}>
                              <span style={{ color: '#16A34A' }}>✓</span> {s}
                            </div>
                          ))}
                        </div>
                        <div>
                          <div style={{ fontSize: '12px', fontWeight: 600, marginBottom: '6px', color: '#DC2626' }}>Limitations</div>
                          {p.limitations.map((l, j) => (
                            <div key={j} style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '3px', display: 'flex', gap: '4px' }}>
                              <span style={{ color: '#DC2626' }}>✗</span> {l}
                            </div>
                          ))}
                        </div>
                        <div>
                          <div style={{ fontSize: '12px', fontWeight: 600, marginBottom: '6px' }}>Components</div>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                            {p.components.map((c, j) => (
                              <span key={j} style={{ fontSize: '11px', padding: '2px 8px', background: '#F3F4F6', borderRadius: '4px', color: 'var(--color-text-secondary)' }}>{c}</span>
                            ))}
                          </div>
                          <div style={{ fontSize: '12px', fontWeight: 600, marginTop: '10px', marginBottom: '4px' }}>Cost Profile</div>
                          <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>{p.cost_profile}</div>
                        </div>
                      </div>
                      <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
                        <span style={{ fontSize: '11px', padding: '2px 8px', background: '#DBEAFE', borderRadius: '4px', color: '#1E40AF' }}>Hot: {p.data_placement.hot}</span>
                        <span style={{ fontSize: '11px', padding: '2px 8px', background: '#FEF3C7', borderRadius: '4px', color: '#92400E' }}>Warm: {p.data_placement.warm}</span>
                        <span style={{ fontSize: '11px', padding: '2px 8px', background: '#F3F4F6', borderRadius: '4px', color: '#6B7280' }}>Cold: {p.data_placement.cold}</span>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Workload-to-Architecture Mapping */}
      {arch.workload_mappings && arch.workload_mappings.length > 0 && (
        <div className="rec-section">
          <h3 className="rec-section-title"><TableIcon size={18} /> Workload → Architecture Mapping</h3>
          <div className="table-container">
            <table className="data-table">
              <thead><tr><th style={{ textAlign: 'left' }}>Workload</th><th style={{ textAlign: 'left' }}>Recommended Architecture</th><th style={{ textAlign: 'left' }}>Score</th><th style={{ textAlign: 'left' }}>Justification</th></tr></thead>
              <tbody>
                {arch.workload_mappings.map((m, i) => (
                  <tr key={i}>
                    <td style={{ textAlign: 'left', fontWeight: 500 }}>{m.workload}</td>
                    <td style={{ textAlign: 'left' }}><Badge variant="info">{m.recommended_architecture}</Badge></td>
                    <td style={{ textAlign: 'left' }}>{m.suitability_score}%</td>
                    <td style={{ textAlign: 'left', fontSize: '13px', color: 'var(--color-text-secondary)' }}>{m.justification}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Data Placement Strategy */}
      {arch.data_placement && (
        <div className="rec-section">
          <h3 className="rec-section-title"><Database size={18} /> Data Placement Strategy</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
            {Object.entries(arch.data_placement).map(([tier, info]: [string, any]) => (
              <div key={tier} style={{ background: tier === 'hot' ? '#FEF2F2' : tier === 'warm' ? '#FFFBEB' : '#F9FAFB', border: '1px solid var(--color-divider)', borderRadius: '8px', padding: '16px' }}>
                <div style={{ fontWeight: 600, fontSize: '14px', marginBottom: '6px', textTransform: 'capitalize' }}>{tier} Data</div>
                <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginBottom: '8px' }}>{info.description}</p>
                <div style={{ fontSize: '13px', fontWeight: 500, marginBottom: '6px' }}>{info.recommendation}</div>
                <ul style={{ fontSize: '12px', margin: 0, paddingLeft: '16px', color: 'var(--color-text-secondary)' }}>
                  {info.criteria.map((c: string, j: number) => <li key={j}>{c}</li>)}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};


// ============ TCO Analysis Section (self-fetching) ============
export const TCOAnalysisSection: React.FC<{ assessmentId: number }> = ({ assessmentId }) => {
  const [data, setData] = useState<TCOData | null>(null);
  const [regions, setRegions] = useState<AWSRegion[]>([]);
  const [selectedRegion, setSelectedRegion] = useState('us-east-1');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { getTCORegions().then(r => setRegions(r.regions)).catch(() => {}); }, []);
  useEffect(() => {
    (async () => { try { setLoading(true); setData(await getAssessmentTCO(assessmentId, selectedRegion)); } catch (err: any) { setError(err.detail || err.message || 'Failed'); } finally { setLoading(false); } })();
  }, [assessmentId, selectedRegion]);

  const fmt = (n: number) => `${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  if (loading) return <TabSpinner message="Calculating TCO..." />;
  if (error || !data) return <TabError message={error || 'No data'} />;

  const { bigquery_costs: bq, provisioned_costs: prov, serverless_costs: svls, comparison: cmp, recommendation: rec, workload_summary: wl } = data;
  const ri1yr3yr = cmp.provisioned_ri1yr_3yr_tco ?? cmp.provisioned_3yr_tco;
  const ri3yr3yr = cmp.provisioned_ri3yr_3yr_tco ?? cmp.provisioned_3yr_tco;
  const maxTCO = Math.max(cmp.bq_3yr_tco, cmp.provisioned_3yr_tco, cmp.serverless_3yr_tco, ri1yr3yr, ri3yr3yr) || 1;

  return (
    <div className="section-content">
      <div className="tco-header-row">
        <h2 className="section-heading" style={{ margin: 0 }}>TCO Analysis</h2>
        <div className="tco-region-select">
          <label>AWS Region:</label>
          <SearchableSelect value={selectedRegion} onChange={(val) => setSelectedRegion(val as string)} options={regions.map(r => ({ value: r.value, label: r.label }))} placeholder="Select region..." />
        </div>
      </div>
      <div className={`tco-savings-box ${cmp.savings_pct > 0 ? 'tco-savings-positive' : 'tco-savings-neutral'}`}>
        <div className="tco-savings-icon"><DollarSign size={28} /></div>
        <div className="tco-savings-content">
          <div className="tco-savings-title">{cmp.savings_pct > 0 ? `${cmp.savings_pct}% Cost Optimization Opportunity` : 'Cost Comparison'}</div>
          <div className="tco-savings-detail">
            BigQuery 3-Year: <strong>{fmt(cmp.bq_3yr_tco)}</strong> → Best Redshift ({cmp.best_option}): <strong>{fmt(cmp.best_option === 'serverless' ? cmp.serverless_3yr_tco : cmp.provisioned_3yr_tco)}</strong>
            {cmp.savings_pct > 0 && <> — Savings: <strong>{fmt(cmp.savings_amount)}</strong></>}
          </div>
        </div>
      </div>
      {cmp.provisioned_viable === false && cmp.provisioned_note && (
        <div className="rec-info-box" style={{ borderLeft: '4px solid #f59e0b', background: '#fffbeb' }}>
          <div className="rec-info-title" style={{ color: '#b45309' }}><AlertTriangle size={16} /> Light Workload Detected</div>
          <p style={{ margin: '4px 0 0', color: '#92400e', fontSize: '13px' }}>{cmp.provisioned_note}</p>
        </div>
      )}
      <div className="tco-section">
        <h3 className="rec-section-title"><Database size={18} /> Monthly Cost Summary</h3>
        <div className="tco-cost-grid">
          <div className="tco-cost-card"><div className="tco-cost-label">BigQuery (Current)</div><div className="tco-cost-value">{fmt(bq.monthly)}<span>/mo</span></div><div className="tco-cost-detail">Storage {fmt(bq.storage.monthly)} + Query {fmt(bq.query.monthly)}</div></div>
          <div className="tco-cost-card"><div className="tco-cost-label">Redshift Provisioned</div><div className="tco-cost-value">{fmt(prov.monthly)}<span>/mo</span></div><div className="tco-cost-detail">{prov.num_nodes}× {prov.node_type}</div></div>
          <div className="tco-cost-card"><div className="tco-cost-label">Redshift Serverless</div><div className="tco-cost-value">{fmt(svls.monthly)}<span>/mo</span></div><div className="tco-cost-detail">{svls.est_rpu_hours_monthly} RPU-hrs/mo</div></div>
        </div>
      </div>
      <div className="tco-section">
        <h3 className="rec-section-title"><Server size={18} /> Redshift Cost Details</h3>
        <div className="rec-config-grid">
          <div className={`rec-config-card ${cmp.best_option === 'provisioned' ? 'rec-config-recommended' : ''}`}>
            {cmp.best_option === 'provisioned' && <div className="rec-badge">Best Value</div>}
            {cmp.provisioned_viable === false && <div className="rec-badge" style={{ background: '#f59e0b' }}>Not Recommended</div>}
            <div className="rec-config-header"><Server size={20} /><span>Provisioned Cluster</span></div>
            <div className="rec-config-details">
              <div className="rec-config-row"><span>Node Type</span><span className="font-mono">{prov.node_type}</span></div>
              <div className="rec-config-row"><span>Nodes</span><span>{prov.num_nodes}</span></div>
              {prov.vcpu_total && <div className="rec-config-row"><span>Total vCPUs</span><span>{prov.vcpu_total}</span></div>}
              {prov.memory_gb_total && <div className="rec-config-row"><span>Total Memory</span><span>{prov.memory_gb_total} GB</span></div>}
              {prov.concurrency_scaling && <div className="rec-config-row"><span>Concurrency Scaling</span><span style={{ color: '#22c55e' }}>Enabled</span></div>}
              <div className="rec-config-row"><span>Compute</span><span>{fmt(prov.compute_monthly)}/mo</span></div>
              <div className="rec-config-row"><span>Storage</span><span>{fmt(prov.storage_monthly)}/mo</span></div>
              <div className="rec-config-row rec-config-row-total"><span>On-Demand</span><span>{fmt(prov.monthly)}/mo</span></div>
              <div className="rec-config-row"><span>Annual (On-Demand)</span><span>{fmt(prov.annual)}</span></div>
              {prov.ri_1yr_monthly != null && <div className="rec-config-row"><span>1-Year RI</span><span>{fmt(prov.ri_1yr_monthly)}/mo</span></div>}
              {prov.ri_3yr_monthly != null && <div className="rec-config-row"><span>3-Year RI</span><span>{fmt(prov.ri_3yr_monthly)}/mo</span></div>}
            </div>
            {prov.sizing_rationale && prov.sizing_rationale.length > 0 && (
              <div className="rec-sizing-rationale"><div className="rec-sizing-rationale-title">Sizing Rationale</div><ul className="rec-sizing-rationale-list">{prov.sizing_rationale.map((r: string, i: number) => <li key={i}>{r}</li>)}</ul></div>
            )}
          </div>
          <div className={`rec-config-card ${cmp.best_option === 'serverless' ? 'rec-config-recommended' : ''}`}>
            {cmp.best_option === 'serverless' && <div className="rec-badge">Best Value</div>}
            <div className="rec-config-header"><Zap size={20} /><span>Serverless</span></div>
            <div className="rec-config-details">
              <div className="rec-config-row"><span>Base RPU</span><span>{svls.base_rpu}</span></div>
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
      <div className="tco-section">
        <h3 className="rec-section-title"><TrendingUp size={18} /> 3-Year TCO Comparison</h3>
        <div className="tco-bar-chart">
          {[
            { label: 'BigQuery', value: cmp.bq_3yr_tco, color: '#4285F4' },
            { label: 'Provisioned (On-Demand)', value: cmp.provisioned_3yr_tco, color: '#34A853' },
            { label: 'Provisioned (1yr RI)', value: ri1yr3yr, color: '#0F9D58' },
            { label: 'Provisioned (3yr RI)', value: ri3yr3yr, color: '#0B8043' },
            { label: 'Serverless', value: cmp.serverless_3yr_tco, color: '#FBBC04' },
          ].map((item, i) => (
            <div key={i} className="tco-bar-item">
              <div className="tco-bar-label-top">{fmt(item.value)}</div>
              <div className="tco-bar" style={{ height: `${Math.max((item.value / maxTCO) * 200, 20)}px`, background: item.color }}></div>
              <div className="tco-bar-label">{item.label}</div>
            </div>
          ))}
        </div>
      </div>
      {rec && (
        <div className="tco-section">
          <h3 className="rec-section-title"><CheckCircle size={18} /> Recommendation</h3>
          <div className={`tco-recommendation-box ${rec.confidence === 'high' ? 'tco-rec-high' : rec.confidence === 'medium' ? 'tco-rec-medium' : 'tco-rec-low'}`}>
            <div className="tco-rec-header"><div className="tco-rec-title">{rec.title}</div><Badge variant={rec.confidence === 'high' ? 'success' : rec.confidence === 'medium' ? 'warning' : 'default'}>{rec.confidence} confidence</Badge></div>
            <ul className="tco-rec-reasons">{rec.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
            {rec.annual_savings_vs_bq > 0 && <div className="tco-rec-savings">Estimated annual savings vs BigQuery: <strong>${fmt(rec.annual_savings_vs_bq)}</strong></div>}
          </div>
        </div>
      )}
      {wl && (
        <div className="tco-section">
          <h3 className="rec-section-title"><BarChart3 size={18} /> Workload Summary</h3>
          <div className="tco-workload-grid">
            <div className="tco-workload-item"><span>Query Time Span</span><span>{wl.query_time_span_days} days</span></div>
            <div className="tco-workload-item"><span>Monthly Slot Hours</span><span>{wl.monthly_slot_hours?.toLocaleString()}</span></div>
            <div className="tco-workload-item"><span>Monthly TB Scanned</span><span>{wl.monthly_tb_scanned?.toFixed(2)}</span></div>
            <div className="tco-workload-item"><span>Total Queries</span><span>{wl.total_queries?.toLocaleString()}</span></div>
            {wl.avg_concurrent_slots != null && <div className="tco-workload-item"><span>Avg Concurrent Slots</span><span>{wl.avg_concurrent_slots?.toFixed(1)}</span></div>}
            {wl.estimated_peak_slots != null && <div className="tco-workload-item"><span>Peak Slots</span><span>{wl.estimated_peak_slots?.toLocaleString()}</span></div>}
            {wl.active_hours_per_day != null && <div className="tco-workload-item"><span>Active Hours/Day</span><span>{wl.active_hours_per_day?.toFixed(1)}</span></div>}
            <div className="tco-workload-item"><span>Workload Pattern</span><span><Badge variant="info">{wl.workload_type?.label || wl.workload_type?.pattern}</Badge></span></div>
          </div>
        </div>
      )}
      {data.cost_notes && data.cost_notes.length > 0 && (
        <div className="rec-info-box" style={{ marginTop: 'var(--spacing-4)' }}>
          <div className="rec-info-title"><Info size={16} /> Cost Notes</div>
          <ul className="rec-info-list">{data.cost_notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </div>
      )}
    </div>
  );
};
