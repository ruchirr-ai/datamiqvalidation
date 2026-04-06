/**
 * SQL Server Assessment Report Page
 * 
 * This file contains ALL SQL Server-specific assessment report UI.
 * DO NOT add BigQuery code here. BigQuery lives in BigQueryReportPage.tsx.
 * 
 * Lazy-loads data per tab for fast initial render.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileSearch, ArrowLeft, Database, Table as TableIcon, Eye, Code,
  Activity, Shield, Users, TrendingUp, DollarSign,
  Zap, Server, Download
} from 'lucide-react';
import { Button, Badge } from '../components/ui';
import { Select } from '../components/ui/Select';
import {
  getAssessmentReport,
  getAssessmentRecommendations,
  getAssessmentTCO,
  getReportTables, PaginatedTablesResponse,
  getReportViews, PaginatedViewsResponse,
  getReportRoutines, RoutinesResponse,
  getReportSecurity, SecurityResponse,
  getReportUserInsights, UserInsightsResponse,
  ReportSummary, DatasetSummary,
  getReportAdditionalMetadata, AdditionalMetadata
} from '../services/assessmentsApi';
import QueryInsightsSection from '../components/assessments/QueryInsightsSection';
import { SQLServerTablesSection } from '../components/assessments/SQLServerTablesSection';
import { SQLServerViewsSection } from '../components/assessments/SQLServerViewsSection';
import { SQLServerRoutinesSection } from '../components/assessments/SQLServerRoutinesSection';
import { SQLServerSecuritySection } from '../components/assessments/SQLServerSecuritySection';
import { DownloadReportModal } from '../components/assessments/DownloadReportModal';
import { generatePDF } from '../utils/pdfReport';
import { TabSpinner, TabError, PaginationControls, formatSize, formatDate, formatNumber } from './reportUtils';
import './AssessmentReportPage.css';

// Transform security policies data for SQL Server Security Section
const transformSecurityDataForSQLServer = (securityPolicies: any[]) => {
  if (!securityPolicies || securityPolicies.length === 0) {
    return { users: [], permissions: [], roles: [], schemas: [], policies: [], logins: [], encryption: [], linkedServers: [] };
  }
  const users: any[] = [], permissions: any[] = [], roles: any[] = [], schemas: any[] = [];
  const policies: any[] = [], logins: any[] = [], encryption: any[] = [], linkedServers: any[] = [];
  securityPolicies.forEach((policy: any) => {
    const metadata = policy.security_metadata || {};
    switch (policy.security_type) {
      case 'USER': users.push({ user_name: metadata.user_name || policy.policy_name, user_type: metadata.user_type || 'SQL_USER', authentication_type: metadata.authentication_type || 'SQL Server Authentication', default_schema: metadata.default_schema || 'dbo', roles: metadata.roles || 'None', create_date: metadata.create_date, last_login: metadata.last_login, is_disabled: metadata.is_disabled || false, is_locked: metadata.is_locked || false, password_policy: metadata.password_policy }); break;
      case 'LOGIN': logins.push({ login_name: metadata.login_name || policy.policy_name, login_type: metadata.login_type || 'SQL_LOGIN', is_disabled: metadata.is_disabled || false, is_locked: metadata.is_locked || false, password_policy_enforced: metadata.password_policy_enforced || false, password_expiration_enforced: metadata.password_expiration_enforced || false, failed_login_attempts: metadata.failed_login_attempts || 0, last_successful_login: metadata.last_successful_login, server_roles: metadata.server_roles || [] }); break;
      case 'ROLE': roles.push({ role_name: metadata.role_name || policy.policy_name, role_category: metadata.role_category || 'User Defined', is_fixed_role: metadata.is_fixed_role || false, members_count: metadata.members_count || 0, description: metadata.description }); break;
      case 'PERMISSION': permissions.push({ schema_name: metadata.schema_name || 'dbo', object_name: metadata.object_name || '', object_type: metadata.object_type || 'TABLE', user_or_role: metadata.user_or_role || policy.policy_name, permission_name: metadata.permission_name || 'SELECT', permission_state: metadata.permission_state || 'GRANT', grantor: metadata.grantor || 'dbo', is_grantable: metadata.is_grantable || false }); break;
      case 'SCHEMA': schemas.push({ schema_name: metadata.schema_name || policy.policy_name, owner_name: metadata.owner_name || 'dbo', owner_type: metadata.owner_type || 'SQL_USER', created_date: metadata.created_date }); break;
      case 'SECURITY_POLICY': policies.push({ policy_name: metadata.policy_name || policy.policy_name, policy_type: metadata.policy_type || 'SECURITY', table_schema: metadata.table_schema || 'dbo', table_name: metadata.table_name || '', filter_predicate: metadata.filter_predicate || policy.filter_predicate, is_enabled: metadata.is_enabled !== undefined ? metadata.is_enabled : true, created_date: metadata.created_date }); break;
      case 'ENCRYPTION': encryption.push({ encryption_type: metadata.encryption_type || 'DATABASE_ENCRYPTION', key_name: metadata.key_name || policy.policy_name, algorithm: metadata.algorithm || 'AES', key_length: metadata.key_length || 256, encrypted_objects_count: metadata.encrypted_objects_count || 0, created_date: metadata.created_date }); break;
      case 'LINKED_SERVER': linkedServers.push({ server_name: metadata.server_name || policy.policy_name, product: metadata.product || '', provider_name: metadata.provider_name || '', data_source: metadata.data_source || '', default_catalog: metadata.default_catalog || '', is_remote_login_enabled: metadata.is_remote_login_enabled || false, is_rpc_out_enabled: metadata.is_rpc_out_enabled || false, is_data_access_enabled: metadata.is_data_access_enabled || false, mapped_logins: metadata.mapped_logins || '', modified_date: metadata.modified_date }); break;
    }
  });
  return { users, permissions, roles, schemas, policies, logins, encryption, linkedServers };
};

interface SQLServerReportPageProps {
  summary: ReportSummary;
  assessmentId: number;
}

export const SQLServerReportPage: React.FC<SQLServerReportPageProps> = ({ summary, assessmentId }) => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<string>('summary');
  const id = assessmentId;

  // Per-tab lazy-loaded data
  const [tablesData, setTablesData] = useState<PaginatedTablesResponse | null>(null);
  const [tablesLoading, setTablesLoading] = useState(false);
  const [tablesError, setTablesError] = useState<string | null>(null);
  const [tablesPage, setTablesPage] = useState(1);
  const [tablesPageSize, setTablesPageSize] = useState(50);

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

  const [userInsightsData, setUserInsightsData] = useState<UserInsightsResponse | null>(null);
  const [userInsightsLoading, setUserInsightsLoading] = useState(false);
  const [userInsightsError, setUserInsightsError] = useState<string | null>(null);

  const [additionalMeta, setAdditionalMeta] = useState<AdditionalMetadata | null>(null);
  const [additionalMetaLoading, setAdditionalMetaLoading] = useState(false);

  const [showDownloadModal, setShowDownloadModal] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const loadedTabsRef = useRef<Set<string>>(new Set(['summary']));

  const fetchTables = useCallback(async (page: number, pageSize: number) => {
    setTablesLoading(true); setTablesError(null);
    try { const data = await getReportTables(id, page, pageSize); setTablesData(data); loadedTabsRef.current.add('tables'); }
    catch (err: any) { setTablesError(err.detail || err.message || 'Failed to load tables'); }
    finally { setTablesLoading(false); }
  }, [id]);

  const fetchViews = useCallback(async (page: number, pageSize: number) => {
    setViewsLoading(true); setViewsError(null);
    try { const data = await getReportViews(id, page, pageSize); setViewsData(data); loadedTabsRef.current.add('views'); }
    catch (err: any) { setViewsError(err.detail || err.message || 'Failed to load views'); }
    finally { setViewsLoading(false); }
  }, [id]);

  // Lazy-load tab data on first activation
  useEffect(() => {
    const tab = activeTab;
    if (loadedTabsRef.current.has(tab) && tab !== 'tables' && tab !== 'views') return;
    switch (tab) {
      case 'tables': fetchTables(tablesPage, tablesPageSize); break;
      case 'views': fetchViews(viewsPage, viewsPageSize); break;
      case 'procedures': case 'functions': case 'triggers':
        if (!loadedTabsRef.current.has('routines')) {
          setRoutinesLoading(true);
          getReportRoutines(id).then(d => { setRoutinesData(d); loadedTabsRef.current.add('routines'); }).catch((e: any) => setRoutinesError(e.detail || e.message || 'Failed')).finally(() => setRoutinesLoading(false));
        }
        break;
      case 'security': case 'schemas':
        if (!loadedTabsRef.current.has('security')) {
          setSecurityLoading(true);
          getReportSecurity(id).then(d => { setSecurityData(d); loadedTabsRef.current.add('security'); }).catch((e: any) => setSecurityError(e.detail || e.message || 'Failed')).finally(() => setSecurityLoading(false));
        }
        // Also fetch tables for Custom Data Types in schemas tab
        if (tab === 'schemas' && !loadedTabsRef.current.has('tables')) {
          fetchTables(tablesPage, tablesPageSize);
        }
        // Also fetch additional metadata for security tab (certs, encryption, assemblies, policies)
        if (tab === 'security' && !loadedTabsRef.current.has('additional-meta')) {
          setAdditionalMetaLoading(true);
          getReportAdditionalMetadata(id).then(d => { setAdditionalMeta(d); loadedTabsRef.current.add('additional-meta'); }).catch(() => {}).finally(() => setAdditionalMetaLoading(false));
        }
        break;
      case 'user-insights':
        if (!loadedTabsRef.current.has('user-insights')) {
          setUserInsightsLoading(true);
          getReportUserInsights(id).then(d => { setUserInsightsData(d); loadedTabsRef.current.add('user-insights'); }).catch((e: any) => setUserInsightsError(e.detail || e.message || 'Failed')).finally(() => setUserInsightsLoading(false));
        }
        break;
      case 'agent-jobs':
        if (!loadedTabsRef.current.has('additional-meta')) {
          setAdditionalMetaLoading(true);
          getReportAdditionalMetadata(id).then(d => { setAdditionalMeta(d); loadedTabsRef.current.add('additional-meta'); }).catch(() => {}).finally(() => setAdditionalMetaLoading(false));
        }
        break;
    }
  }, [activeTab]);

  useEffect(() => { if (activeTab === 'tables') fetchTables(tablesPage, tablesPageSize); }, [tablesPage, tablesPageSize]);
  useEffect(() => { if (activeTab === 'views') fetchViews(viewsPage, viewsPageSize); }, [viewsPage, viewsPageSize]);

  const getStoredProcedures = () => routinesData ? routinesData.routines.filter(r => r.routine_type === 'PROCEDURE') : [];
  const getFunctions = () => routinesData ? routinesData.routines.filter(r => r.routine_type === 'FUNCTION') : [];
  const getTriggers = () => routinesData ? routinesData.routines.filter(r => r.routine_type === 'TRIGGER') : [];

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
    { id: 'schemas', label: 'Schemas', icon: Database },
    { id: 'tables', label: 'Tables', icon: TableIcon },
    { id: 'views', label: 'Views', icon: Eye },
    { id: 'procedures', label: 'Stored Procedures', icon: Code },
    { id: 'functions', label: 'Functions', icon: Code },
    { id: 'triggers', label: 'Triggers', icon: Zap },
    { id: 'agent-jobs', label: 'Agent Jobs', icon: Server },
    { id: 'query-insights', label: 'Query Insights', icon: Activity },
    { id: 'user-insights', label: 'Query Summary', icon: Users },
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
        {activeTab === 'summary' && <SQLServerSummarySection assessment={summary.assessment} datasets={summary.datasets} setActiveTab={setActiveTab} />}
        {activeTab === 'datasets' && <SQLServerDatasetsSection datasets={summary.datasets} tables={tablesData?.tables} />}
        {activeTab === 'schemas' && (
          securityLoading ? <TabSpinner message="Loading schemas..." /> :
          <SchemasSection schemas={transformSecurityDataForSQLServer(securityData?.security_policies || summary.security_policies_preview || []).schemas} columns={tablesData?.columns} tables={tablesData?.tables} />
        )}
        {activeTab === 'tables' && (
          tablesLoading ? <TabSpinner message="Loading tables..." /> :
          tablesError ? <TabError message={tablesError} onRetry={() => fetchTables(tablesPage, tablesPageSize)} /> :
          tablesData ? (
            <div className="section-content">
              <SQLServerTablesSection tables={tablesData.tables} columns={tablesData.columns} indexes={tablesData.indexes} formatSize={formatSize} formatDate={formatDate} formatNumber={formatNumber} />
              <PaginationControls page={tablesData.page} totalPages={tablesData.total_pages} total={tablesData.total} pageSize={tablesPageSize} onPageChange={setTablesPage} onPageSizeChange={(s) => { setTablesPageSize(s); setTablesPage(1); }} />
            </div>
          ) : <TabSpinner message="Loading tables..." />
        )}
        {activeTab === 'views' && (
          viewsLoading ? <TabSpinner message="Loading views..." /> :
          viewsError ? <TabError message={viewsError} onRetry={() => fetchViews(viewsPage, viewsPageSize)} /> :
          viewsData ? (
            <div className="section-content">
              <SQLServerViewsSection views={viewsData.views} indexes={[]} formatDate={formatDate} formatSize={formatSize} />
              <PaginationControls page={viewsData.page} totalPages={viewsData.total_pages} total={viewsData.total} pageSize={viewsPageSize} onPageChange={setViewsPage} onPageSizeChange={(s) => { setViewsPageSize(s); setViewsPage(1); }} />
            </div>
          ) : <TabSpinner message="Loading views..." />
        )}
        {activeTab === 'procedures' && (
          routinesLoading ? <TabSpinner message="Loading stored procedures..." /> :
          routinesError ? <TabError message={routinesError} /> :
          routinesData ? <SQLServerRoutinesSection routines={getStoredProcedures()} title="Stored Procedures" formatDate={formatDate} /> :
          <TabSpinner message="Loading stored procedures..." />
        )}
        {activeTab === 'functions' && (
          routinesLoading ? <TabSpinner message="Loading functions..." /> :
          routinesError ? <TabError message={routinesError} /> :
          routinesData ? <SQLServerRoutinesSection routines={getFunctions()} title="Functions" formatDate={formatDate} /> :
          <TabSpinner message="Loading functions..." />
        )}
        {activeTab === 'triggers' && (
          routinesLoading ? <TabSpinner message="Loading triggers..." /> :
          routinesData ? <SQLServerRoutinesSection routines={getTriggers()} title="Triggers" formatDate={formatDate} /> :
          <TabSpinner message="Loading triggers..." />
        )}
        {activeTab === 'agent-jobs' && (
          additionalMetaLoading ? <TabSpinner message="Loading agent jobs..." /> :
          additionalMeta ? <AgentJobsSection jobs={additionalMeta.agent_jobs || []} formatDate={formatDate} /> :
          <TabSpinner message="Loading agent jobs..." />
        )}
        {activeTab === 'query-insights' && <QueryInsightsSection assessmentId={id} isSQLServer={true} />}
        {activeTab === 'user-insights' && (
          userInsightsLoading ? <TabSpinner message="Loading query summary..." /> :
          userInsightsError ? <TabError message={userInsightsError} /> :
          userInsightsData ? <SQLServerUserInsightsSection queryStats={userInsightsData.query_stats} /> :
          <TabSpinner message="Loading query summary..." />
        )}
        {activeTab === 'security' && (
          securityLoading ? <TabSpinner message="Loading security data..." /> :
          securityError ? <TabError message={securityError} /> :
          securityData ? <SQLServerSecuritySection security={transformSecurityDataForSQLServer(securityData.security_policies)} formatDate={formatDate} additionalMeta={additionalMeta} /> :
          <TabSpinner message="Loading security data..." />
        )}
      </div>

      <DownloadReportModal isOpen={showDownloadModal} onClose={() => setShowDownloadModal(false)} assessmentName={summary.assessment.name} onDownload={handleDownloadPDF} downloading={downloading} />
    </div>
  );
};


// ============ SQL Server Summary Section ============
const SQLServerSummarySection: React.FC<{ assessment: ReportSummary['assessment']; datasets: DatasetSummary[]; setActiveTab: (t: string) => void }> = ({ assessment, datasets, setActiveTab }) => {
  const triggerCount = (assessment as any).trigger_count || 0;
  const schemasCount = (assessment as any).schemas_count || 0;
  const securityItemsCount = (assessment as any).security_items_count || 0;

  return (
  <div className="section-content">
    <h2 className="section-heading">Assessment Summary</h2>

    {/* SQL Server Instance Info Banner */}
    {datasets?.[0]?.dataset_metadata && (() => {
      const meta = datasets[0].dataset_metadata;
      const version = meta.version || '';
      const edition = meta.edition || '';
      const productLevel = meta.product_level || '';
      const instanceRole = meta.instance_role || '';
      const serverName = meta.server_name || meta.machine_name || datasets[0].location || '';
      const instanceName = meta.instance_name || '';
      const hasAnyInfo = version || edition || serverName;
      if (!hasAnyInfo) return null;
      const roleBadgeVariant = instanceRole === 'PRIMARY' ? 'success' : instanceRole === 'SECONDARY' ? 'warning' : 'default';
      return (
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap', background: '#f8fafc', border: '1px solid var(--color-divider)', borderRadius: '8px', padding: '14px 18px', marginBottom: '20px' }}>
          <Server size={18} style={{ color: 'var(--color-primary)', flexShrink: 0 }} />
          <div style={{ display: 'flex', alignItems: 'center', gap: '20px', flexWrap: 'wrap', fontSize: '13px' }}>
            {serverName && (<div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><span style={{ color: 'var(--color-text-secondary)' }}>Server:</span><span style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>{serverName}{instanceName && instanceName !== 'Default' ? `\\${instanceName}` : ''}</span></div>)}
            {version && (<div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><span style={{ color: 'var(--color-text-secondary)' }}>Version:</span><span style={{ fontWeight: 500, color: 'var(--color-text-primary)' }}>{version}</span></div>)}
            {edition && (<div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><span style={{ color: 'var(--color-text-secondary)' }}>Edition:</span><span style={{ fontWeight: 500, color: 'var(--color-text-primary)' }}>{edition}</span></div>)}
            {productLevel && (<div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><span style={{ color: 'var(--color-text-secondary)' }}>Level:</span><span style={{ fontWeight: 500, color: 'var(--color-text-primary)' }}>{productLevel}</span></div>)}
            {instanceRole && (<div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><span style={{ color: 'var(--color-text-secondary)' }}>Role:</span><Badge variant={roleBadgeVariant as any}>{instanceRole}</Badge></div>)}
          </div>
        </div>
      );
    })()}

    <div className="summary-grid">
      <div className="summary-card summary-card-clickable" onClick={() => setActiveTab('datasets')}>
        <div className="summary-icon" style={{ background: '#EFF6FF', color: '#2563EB' }}><Database size={24} /></div>
        <div className="summary-content"><div className="summary-value">{assessment.total_datasets}</div><div className="summary-label">Databases</div></div>
      </div>
      <div className="summary-card summary-card-clickable" onClick={() => setActiveTab('schemas')}>
        <div className="summary-icon" style={{ background: '#F0F9FF', color: '#0284C7' }}><Database size={24} /></div>
        <div className="summary-content"><div className="summary-value">{schemasCount}</div><div className="summary-label">Schemas</div></div>
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
      <div className="summary-card summary-card-clickable" onClick={() => setActiveTab('triggers')}>
        <div className="summary-icon" style={{ background: '#FFF7ED', color: '#EA580C' }}><Zap size={24} /></div>
        <div className="summary-content"><div className="summary-value">{triggerCount}</div><div className="summary-label">Triggers</div></div>
      </div>
      <div className="summary-card summary-card-clickable" onClick={() => setActiveTab('security')}>
        <div className="summary-icon" style={{ background: '#FEF2F2', color: '#DC2626' }}><Shield size={24} /></div>
        <div className="summary-content"><div className="summary-value">{securityItemsCount}</div><div className="summary-label">Security Items</div></div>
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
};

// ============ Schemas Section ============
const SchemasSection: React.FC<{ schemas: any[]; columns?: any[]; tables?: any[] }> = ({ schemas, columns, tables }) => {
  // Extract custom data types from columns
  const udtColumns = (columns || []).filter((c: any) => c.column_metadata?.is_user_defined_type);
  const udtMap: Record<string, { udt_name: string; base_type: string; usages: { table_name: string; column_name: string }[] }> = {};
  udtColumns.forEach((c: any) => {
    const udtName = c.column_metadata.udt_name;
    if (!udtMap[udtName]) {
      udtMap[udtName] = { udt_name: udtName, base_type: c.column_metadata.base_type_name || c.data_type, usages: [] };
    }
    const table = (tables || []).find((t: any) => t.id === c.table_id);
    udtMap[udtName].usages.push({ table_name: table ? `${table.dataset_name}.${table.table_name}` : `table_id:${c.table_id}`, column_name: c.column_name });
  });
  const udts = Object.values(udtMap);

  return (
  <div className="section-content">
    <h2 className="section-heading">Schemas ({schemas.length})</h2>
    {schemas.length === 0 ? (
      <div className="empty-state"><Database size={48} /><p>No schemas found</p></div>
    ) : (
      <div className="table-container">
        <table className="data-table">
          <thead><tr><th style={{ textAlign: 'left' }}>Schema Name</th><th style={{ textAlign: 'left' }}>Owner</th><th style={{ textAlign: 'left' }}>Owner Type</th><th style={{ textAlign: 'left' }}>Created Date</th></tr></thead>
          <tbody>
            {schemas.map((schema: any, idx: number) => (
              <tr key={idx}>
                <td style={{ textAlign: 'left' }}><span style={{ fontWeight: 500 }}>{schema.schema_name}</span></td>
                <td style={{ textAlign: 'left' }}>{schema.owner_name || 'N/A'}</td>
                <td style={{ textAlign: 'left' }}>{schema.owner_type || 'N/A'}</td>
                <td style={{ textAlign: 'left' }}>{formatDate(schema.created_date)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )}

    {/* Custom Data Types Section */}
    {udts.length > 0 && (
      <>
        <h2 className="section-heading" style={{ marginTop: '32px' }}>Custom Data Types ({udts.length})</h2>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ textAlign: 'left' }}>Type Name</th>
                <th style={{ textAlign: 'left' }}>Base Type</th>
                <th style={{ textAlign: 'left' }}>Used In</th>
              </tr>
            </thead>
            <tbody>
              {udts.map((udt, idx) => (
                <tr key={idx}>
                  <td style={{ textAlign: 'left' }}><span style={{ fontWeight: 500 }}>{udt.udt_name}</span></td>
                  <td style={{ textAlign: 'left' }}><code style={{ background: '#F3F4F6', padding: '2px 6px', borderRadius: '4px', fontSize: '12px' }}>{udt.base_type}</code></td>
                  <td style={{ textAlign: 'left' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      {udt.usages.map((u, i) => (
                        <span key={i} style={{ fontSize: '13px' }}>
                          <span style={{ color: 'var(--color-text-secondary)' }}>{u.table_name}</span>
                          <span style={{ margin: '0 4px' }}>→</span>
                          <span style={{ fontWeight: 500 }}>{u.column_name}</span>
                        </span>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </>
    )}

    {/* Computed Columns Section */}
    {(() => {
      const computedCols = (columns || []).filter((c: any) => c.column_metadata?.is_computed);
      if (computedCols.length === 0) return null;
      return (
        <>
          <h2 className="section-heading" style={{ marginTop: '32px' }}>Computed Columns ({computedCols.length})</h2>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ textAlign: 'left' }}>Table</th>
                  <th style={{ textAlign: 'left' }}>Column Name</th>
                  <th style={{ textAlign: 'left' }}>Definition</th>
                  <th style={{ textAlign: 'left' }}>Data Type</th>
                </tr>
              </thead>
              <tbody>
                {computedCols.map((c: any, idx: number) => {
                  const table = (tables || []).find((t: any) => t.id === c.table_id);
                  return (
                    <tr key={idx}>
                      <td style={{ textAlign: 'left', color: 'var(--color-text-secondary)' }}>{table ? `${table.dataset_name}.${table.table_name}` : '-'}</td>
                      <td style={{ textAlign: 'left', fontWeight: 500 }}>{c.column_name}</td>
                      <td style={{ textAlign: 'left' }}><code style={{ background: '#F3F4F6', padding: '2px 6px', borderRadius: '4px', fontSize: '12px' }}>{c.column_metadata?.computed_definition || '-'}</code></td>
                      <td style={{ textAlign: 'left' }}>{c.data_type}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      );
    })()}
  </div>
  );
};

// ============ SQL Server Datasets Section ============
const SQLServerDatasetsSection: React.FC<{ datasets: DatasetSummary[]; tables?: any[] }> = ({ datasets, tables }) => {
  const getTableCount = (dataset: any) => {
    if (tables && tables.length > 0) return tables.filter((t: any) => t.table_type === 'BASE TABLE').length;
    return dataset.table_count;
  };
  return (
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
                <td>{getTableCount(dataset)}</td>
                <td>{formatSize(dataset.total_size_mb)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )}
  </div>
  );
};

// ============ SQL Server User Insights (Query Summary) ============
const SQLServerUserInsightsSection: React.FC<{ queryStats: any[] }> = ({ queryStats }) => {
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
  const formatCPUTime = (ms: number) => { if (ms === 0) return '0'; const s = ms / 1000; if (s >= 3600) return `${(s / 3600).toFixed(2)} hrs`; if (s >= 60) return `${(s / 60).toFixed(2)} mins`; return `${s.toFixed(2)} secs`; };

  return (
    <div className="section-content">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h2 className="section-heading">Query Summary ({users.length} sources)</h2>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{ fontSize: '14px', color: 'var(--color-text-secondary)' }}>Time Frame:</span>
          <Select value={timeFilter} onChange={(val) => setTimeFilter(val as string)} options={[{ value: 'all', label: 'All Time' }, { value: '24h', label: 'Last 24 Hours' }, { value: '7d', label: 'Last 7 Days' }, { value: '30d', label: 'Last 30 Days' }]} />
        </div>
      </div>
      {users.length === 0 ? <div className="empty-state"><Users size={48} /><p>No query data found for selected time frame</p></div> : (
        <div className="table-container">
          <table className="data-table">
            <thead><tr><th style={{ textAlign: 'left' }}>Source</th><th style={{ textAlign: 'right' }}>Queries Executed</th><th style={{ textAlign: 'right' }}>Total Data Scanned</th><th style={{ textAlign: 'right' }}>CPU Time</th><th style={{ textAlign: 'right' }}>Cache Hit Ratio</th></tr></thead>
            <tbody>{users.map((u, i) => (
              <tr key={i}>
                <td className="font-medium" style={{ textAlign: 'left' }}>{u.email}</td>
                <td style={{ textAlign: 'right' }}>{u.queryCount.toLocaleString()}</td>
                <td style={{ textAlign: 'right' }}>{formatBytes(u.totalBytesScanned)}</td>
                <td style={{ textAlign: 'right' }}>{formatCPUTime(u.totalSlotMilliseconds)}</td>
                <td style={{ textAlign: 'right' }}><Badge variant={parseFloat(u.cacheHitRate) > 50 ? 'success' : parseFloat(u.cacheHitRate) > 20 ? 'warning' : 'default'}>{u.cacheHitRate}%</Badge></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
    </div>
  );
};

// ============ Agent Jobs Section ============
const AgentJobsSection: React.FC<{ jobs: any[]; formatDate: (d: string | null) => string }> = ({ jobs, formatDate }) => {
  const [expandedJob, setExpandedJob] = useState<number | null>(null);
  return (
    <div className="section-content">
      <h2 className="section-heading">SQL Agent Jobs ({jobs.length})</h2>
      {jobs.length === 0 ? (
        <div className="empty-state"><Server size={48} /><p>No SQL Agent jobs found</p></div>
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead><tr><th style={{ textAlign: 'left' }}>Job Name</th><th style={{ textAlign: 'left' }}>Status</th><th style={{ textAlign: 'left' }}>Steps</th><th style={{ textAlign: 'left' }}>Created</th><th style={{ textAlign: 'left' }}>Modified</th></tr></thead>
            <tbody>
              {jobs.map((job: any, idx: number) => (
                <React.Fragment key={idx}>
                  <tr>
                    <td style={{ textAlign: 'left' }}>
                      <button className="table-name-link" onClick={() => setExpandedJob(expandedJob === idx ? null : idx)} style={{ textAlign: 'left' }}>{job.job_name}</button>
                    </td>
                    <td style={{ textAlign: 'left' }}><Badge variant={job.enabled ? 'success' : 'default'}>{job.enabled ? 'Enabled' : 'Disabled'}</Badge></td>
                    <td style={{ textAlign: 'left' }}>{job.step_count}</td>
                    <td style={{ textAlign: 'left' }} className="timestamp-value">{formatDate(job.date_created)}</td>
                    <td style={{ textAlign: 'left' }} className="timestamp-value">{formatDate(job.date_modified)}</td>
                  </tr>
                  {expandedJob === idx && job.steps && (
                    <tr className="expanded-row"><td colSpan={5}>
                      <div style={{ padding: '12px' }}>
                        <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginBottom: '8px' }}>{job.description || 'No description'}</p>
                        <table className="data-table compact" style={{ marginTop: '8px' }}>
                          <thead><tr><th>Step</th><th>Subsystem</th><th>Database</th><th>Command</th></tr></thead>
                          <tbody>
                            {job.steps.map((s: any, si: number) => (
                              <tr key={si}>
                                <td>{s.step_name}</td><td><Badge variant="info">{s.subsystem}</Badge></td><td>{s.database_name}</td>
                                <td><pre style={{ fontSize: '11px', maxWidth: '400px', overflow: 'auto', whiteSpace: 'pre-wrap', margin: 0 }}>{s.command}</pre></td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </td></tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

// ============ Recommendations Section (self-fetching, shared logic) ============
import { SearchableSelect } from '../components/ui/SearchableSelect';
import {
  RecommendationsData, TCOData, AWSRegion,
  getAssessmentRecommendations as fetchRecs,
  getAssessmentTCO as fetchTCO,
  getTCORegions
} from '../services/assessmentsApi';
import { Info, CheckCircle, AlertTriangle, BarChart3 } from 'lucide-react';

const RecommendationsPlaceholder: React.FC<{ assessmentId: number }> = ({ assessmentId }) => {
  const [data, setData] = useState<RecommendationsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDataset, setSelectedDataset] = useState<string | number>('all');
  const [selectedTable, setSelectedTable] = useState<string | number>('all');
  const [dskPage, setDskPage] = useState(1);
  const [dskPageSize, setDskPageSize] = useState<string | number>(20);

  useEffect(() => {
    (async () => { try { setLoading(true); setData(await fetchRecs(assessmentId)); } catch (err: any) { setError(err.detail || err.message || 'Failed'); } finally { setLoading(false); } })();
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
            <li>SORTKEY should align with WHERE clause filters and ORDER BY columns.</li>
            <li>Tables with fewer than 1M rows use EVEN distribution.</li>
            <li>Use COMPOUND sort keys when queries filter on multiple columns in a predictable order.</li>
          </ul>
        </div>
      </div>
      <div className="rec-section">
        <h3 className="rec-section-title"><Activity size={18} /> Query Classification & Architecture</h3>
        <div className="rec-cards-row">
          <div className="rec-card rec-card-blue"><div className="rec-card-icon"><Zap size={24} /></div><div className="rec-card-value">{qc.adhoc_count.toLocaleString()}</div><div className="rec-card-label">Ad-hoc Queries</div><div className="rec-card-pct">{qc.adhoc_pct}%</div></div>
          <div className="rec-card rec-card-purple"><div className="rec-card-icon"><TrendingUp size={24} /></div><div className="rec-card-value">{qc.bi_count.toLocaleString()}</div><div className="rec-card-label">BI / Scheduled Queries</div><div className="rec-card-pct">{qc.bi_pct}%</div></div>
          <div className="rec-card rec-card-green"><div className="rec-card-icon"><Activity size={24} /></div><div className="rec-card-value">{qc.total_queries.toLocaleString()}</div><div className="rec-card-label">Total Queries Analyzed</div></div>
        </div>
        {arch.strategies.map((s, i) => (
          <div key={i} className="rec-info-box"><div className="rec-info-title"><Info size={16} /> {s.title}</div><ul className="rec-info-list">{s.points.map((p, j) => <li key={j}>{p}</li>)}</ul></div>
        ))}
      </div>
    </div>
  );
};

// ============ TCO Analysis Section (self-fetching, shared logic) ============
const TCOPlaceholder: React.FC<{ assessmentId: number }> = ({ assessmentId }) => {
  const [data, setData] = useState<TCOData | null>(null);
  const [regions, setRegions] = useState<AWSRegion[]>([]);
  const [selectedRegion, setSelectedRegion] = useState('us-east-1');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { getTCORegions().then(r => setRegions(r.regions)).catch(() => {}); }, []);
  useEffect(() => {
    (async () => { try { setLoading(true); setData(await fetchTCO(assessmentId, selectedRegion)); } catch (err: any) { setError(err.detail || err.message || 'Failed'); } finally { setLoading(false); } })();
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
