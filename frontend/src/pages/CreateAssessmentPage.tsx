/**
 * Create Assessment Page - Migration Landscape Questionnaire
 * 
 * A full-page multi-section questionnaire that captures the complete
 * migration landscape before running the automated assessment.
 * 
 * Sections:
 * 1. Assessment Details (name, source connection, mode)
 * 2. Data Sources (upstream systems feeding into the warehouse)
 * 3. ETL / Data Pipelines (orchestration tools, scheduling)
 * 4. Downstream Consumers (BI tools, dashboards, APIs)
 */

import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft, Plus, Trash2, ChevronDown, ChevronUp, Database, GitBranch, BarChart3, Settings } from 'lucide-react';
import { Button, Badge, Input, Select } from '../components/ui';
import { listConnections, Connection } from '../services/api';
import { createAssessment } from '../services/assessmentsApi';
import './CreateAssessmentPage.css';

interface DataSource {
  name: string;
  type: string;
  otherType: string;
  hosting: string;
  otherHosting: string;
  volume: string;
  refreshFrequency: string;
}

interface ETLPipeline {
  tool: string;
  otherTool: string;
  transformLocation: string;
  pipelineCount: string;
  scheduling: string;
  notes: string;
}

interface DownstreamConsumer {
  tool: string;
  otherTool: string;
  dashboardCount: string;
  userCount: string;
  connectionType: string;
  notes: string;
}

interface LandscapeData {
  dataSources: { applicable: boolean; sources: DataSource[] };
  etlPipelines: { applicable: boolean; pipelines: ETLPipeline[] };
  downstreamConsumers: { applicable: boolean; consumers: DownstreamConsumer[] };
}

const SOURCE_TYPE_OPTIONS = [
  { value: '', label: 'Select type' },
  { value: 'mysql', label: 'MySQL' },
  { value: 'postgresql', label: 'PostgreSQL' },
  { value: 'oracle', label: 'Oracle' },
  { value: 'sqlserver', label: 'SQL Server' },
  { value: 'mongodb', label: 'MongoDB' },
  { value: 'sap', label: 'SAP' },
  { value: 'salesforce', label: 'Salesforce' },
  { value: 'api', label: 'REST API' },
  { value: 'flat_file', label: 'Flat Files (CSV/JSON)' },
  { value: 'gcs', label: 'Google Cloud Storage' },
  { value: 's3', label: 'Amazon S3' },
  { value: 'kafka', label: 'Kafka / Streaming' },
  { value: 'other', label: 'Other' },
];

const HOSTING_OPTIONS = [
  { value: '', label: 'Select hosting' },
  { value: 'on_prem', label: 'On-Premises' },
  { value: 'gcp', label: 'Google Cloud (GCP)' },
  { value: 'aws', label: 'Amazon Web Services (AWS)' },
  { value: 'azure', label: 'Microsoft Azure' },
  { value: 'saas', label: 'SaaS / Managed Service' },
  { value: 'hybrid', label: 'Hybrid' },
  { value: 'other', label: 'Other' },
];

const REFRESH_OPTIONS = [
  { value: '', label: 'Select frequency' },
  { value: 'realtime', label: 'Real-time / Streaming' },
  { value: 'hourly', label: 'Hourly' },
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
  { value: 'on_demand', label: 'On-demand / Manual' },
  { value: 'unknown', label: 'Unknown' },
];

const ETL_TOOL_OPTIONS = [
  { value: '', label: 'Select tool' },
  { value: 'airflow', label: 'Apache Airflow' },
  { value: 'dbt', label: 'dbt' },
  { value: 'dataflow', label: 'Google Dataflow (Beam)' },
  { value: 'dataproc', label: 'Google Dataproc (Python/PySpark)' },
  { value: 'composer', label: 'Cloud Composer' },
  { value: 'emr', label: 'Amazon EMR (Python/PySpark)' },
  { value: 'glue', label: 'AWS Glue' },
  { value: 'bigquery_scheduled', label: 'BigQuery Scheduled Queries' },
  { value: 'informatica', label: 'Informatica' },
  { value: 'fivetran', label: 'Fivetran' },
  { value: 'stitch', label: 'Stitch' },
  { value: 'talend', label: 'Talend' },
  { value: 'cloud_functions', label: 'Cloud Functions / Lambda' },
  { value: 'custom_scripts', label: 'Custom Scripts (Python/Shell)' },
  { value: 'other', label: 'Other' },
];

const BI_TOOL_OPTIONS = [
  { value: '', label: 'Select tool' },
  { value: 'looker', label: 'Looker / Looker Studio' },
  { value: 'tableau', label: 'Tableau' },
  { value: 'powerbi', label: 'Power BI' },
  { value: 'quicksight', label: 'Amazon QuickSight' },
  { value: 'metabase', label: 'Metabase' },
  { value: 'superset', label: 'Apache Superset' },
  { value: 'grafana', label: 'Grafana' },
  { value: 'datastudio', label: 'Google Data Studio' },
  { value: 'qlik', label: 'Qlik' },
  { value: 'custom_app', label: 'Custom Application' },
  { value: 'api_consumer', label: 'API / Service' },
  { value: 'data_export', label: 'Scheduled Data Export' },
  { value: 'other', label: 'Other' },
];

const EMPTY_SOURCE: DataSource = { name: '', type: '', otherType: '', hosting: '', otherHosting: '', volume: '', refreshFrequency: '' };
const EMPTY_PIPELINE: ETLPipeline = { tool: '', otherTool: '', transformLocation: '', pipelineCount: '', scheduling: '', notes: '' };
const EMPTY_CONSUMER: DownstreamConsumer = { tool: '', otherTool: '', dashboardCount: '', userCount: '', connectionType: '', notes: '' };

export const CreateAssessmentPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const mode = (searchParams.get('mode') as 'assess' | 'analyze') || 'assess';

  // Assessment details
  const [name, setName] = useState('');
  const [sourceConnectionId, setSourceConnectionId] = useState<number | null>(null);
  const [targetDb, setTargetDb] = useState('redshift');
  const [connections, setConnections] = useState<Connection[]>([]);
  const [loadingConnections, setLoadingConnections] = useState(true);

  // Landscape data
  const [landscape, setLandscape] = useState<LandscapeData>({
    dataSources: { applicable: true, sources: [{ ...EMPTY_SOURCE }] },
    etlPipelines: { applicable: true, pipelines: [{ ...EMPTY_PIPELINE }] },
    downstreamConsumers: { applicable: true, consumers: [{ ...EMPTY_CONSUMER }] },
  });

  // UI state
  const [expandedSection, setExpandedSection] = useState<number>(0);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadConnections();
  }, []);

  const loadConnections = async () => {
    try {
      const data = await listConnections();
      setConnections(data);
    } catch {
      setError('Failed to load connections');
    } finally {
      setLoadingConnections(false);
    }
  };

  const sourceConnections = connections.filter(c => c.type === 'source');

  // Section toggle
  const toggleSection = (idx: number) => {
    setExpandedSection(expandedSection === idx ? -1 : idx);
  };

  // Data Sources handlers
  const addSource = () => {
    setLandscape(prev => ({
      ...prev,
      dataSources: { ...prev.dataSources, sources: [...prev.dataSources.sources, { ...EMPTY_SOURCE }] }
    }));
  };
  const removeSource = (idx: number) => {
    setLandscape(prev => ({
      ...prev,
      dataSources: { ...prev.dataSources, sources: prev.dataSources.sources.filter((_, i) => i !== idx) }
    }));
  };
  const updateSource = (idx: number, field: keyof DataSource, value: string) => {
    setLandscape(prev => {
      const sources = [...prev.dataSources.sources];
      sources[idx] = { ...sources[idx], [field]: value };
      return { ...prev, dataSources: { ...prev.dataSources, sources } };
    });
  };

  // ETL handlers
  const addPipeline = () => {
    setLandscape(prev => ({
      ...prev,
      etlPipelines: { ...prev.etlPipelines, pipelines: [...prev.etlPipelines.pipelines, { ...EMPTY_PIPELINE }] }
    }));
  };
  const removePipeline = (idx: number) => {
    setLandscape(prev => ({
      ...prev,
      etlPipelines: { ...prev.etlPipelines, pipelines: prev.etlPipelines.pipelines.filter((_, i) => i !== idx) }
    }));
  };
  const updatePipeline = (idx: number, field: keyof ETLPipeline, value: string) => {
    setLandscape(prev => {
      const pipelines = [...prev.etlPipelines.pipelines];
      pipelines[idx] = { ...pipelines[idx], [field]: value };
      return { ...prev, etlPipelines: { ...prev.etlPipelines, pipelines } };
    });
  };

  // Downstream handlers
  const addConsumer = () => {
    setLandscape(prev => ({
      ...prev,
      downstreamConsumers: { ...prev.downstreamConsumers, consumers: [...prev.downstreamConsumers.consumers, { ...EMPTY_CONSUMER }] }
    }));
  };
  const removeConsumer = (idx: number) => {
    setLandscape(prev => ({
      ...prev,
      downstreamConsumers: { ...prev.downstreamConsumers, consumers: prev.downstreamConsumers.consumers.filter((_, i) => i !== idx) }
    }));
  };
  const updateConsumer = (idx: number, field: keyof DownstreamConsumer, value: string) => {
    setLandscape(prev => {
      const consumers = [...prev.downstreamConsumers.consumers];
      consumers[idx] = { ...consumers[idx], [field]: value };
      return { ...prev, downstreamConsumers: { ...prev.downstreamConsumers, consumers } };
    });
  };

  const handleSubmit = async () => {
    if (!name.trim()) { setError('Please enter an assessment name'); return; }
    if (!sourceConnectionId) { setError('Please select a source connection'); return; }

    try {
      setSubmitting(true);
      setError(null);

      // Build landscape payload — mark sections as not_applicable if toggled off
      const landscapePayload = {
        data_sources: landscape.dataSources.applicable
          ? landscape.dataSources.sources.filter(s => s.name || s.type).map(s => ({
              ...s,
              type: s.type === 'other' && s.otherType ? s.otherType : s.type,
              hosting: s.hosting === 'other' && s.otherHosting ? s.otherHosting : s.hosting,
            }))
          : 'not_applicable',
        etl_pipelines: landscape.etlPipelines.applicable
          ? landscape.etlPipelines.pipelines.filter(p => p.tool).map(p => ({
              ...p,
              tool: p.tool === 'other' && p.otherTool ? p.otherTool : p.tool,
            }))
          : 'not_applicable',
        downstream_consumers: landscape.downstreamConsumers.applicable
          ? landscape.downstreamConsumers.consumers.filter(c => c.tool).map(c => ({
              ...c,
              tool: c.tool === 'other' && c.otherTool ? c.otherTool : c.tool,
            }))
          : 'not_applicable',
      };

      await createAssessment({
        name: name.trim(),
        source_connection_id: sourceConnectionId,
        assessment_mode: mode,
        target_db: mode === 'analyze' ? targetDb : undefined,
        landscape: landscapePayload,
      });

      navigate('/assessments');
    } catch (err: any) {
      setError(err.detail || err.message || 'Failed to create assessment');
    } finally {
      setSubmitting(false);
    }
  };

  const sections = [
    { title: 'Assessment Details', icon: <Settings size={18} />, required: true },
    { title: 'Data Sources', icon: <Database size={18} />, subtitle: 'Upstream systems feeding into your data warehouse' },
    { title: 'ETL / Data Pipelines', icon: <GitBranch size={18} />, subtitle: 'Tools and processes that move and transform data' },
    { title: 'Downstream Consumers', icon: <BarChart3 size={18} />, subtitle: 'BI tools, dashboards, reports, and applications' },
  ];

  return (
    <div className="create-assessment-page">
      <div className="create-assessment-header">
        <Button variant="outline" onClick={() => navigate('/assessments')}>
          <ArrowLeft size={16} /> Back to Assessments
        </Button>
        <div>
          <h1 className="create-assessment-title">
            {mode === 'analyze' ? 'New Analysis' : 'New Assessment'}
          </h1>
          <p className="create-assessment-subtitle">
            Complete the migration landscape questionnaire to provide context for a comprehensive assessment.
          </p>
        </div>
      </div>

      {error && (
        <div className="create-assessment-error">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="8" cy="8" r="6" /><path d="M8 5v3M8 11h.01" strokeLinecap="round" />
          </svg>
          {error}
        </div>
      )}

      <div className="questionnaire-sections">
        {sections.map((section, sIdx) => (
          <div key={sIdx} className={`questionnaire-section ${expandedSection === sIdx ? 'expanded' : ''}`}>
            <div className="section-header" onClick={() => toggleSection(sIdx)}>
              <div className="section-header-left">
                <span className="section-step">{sIdx + 1}</span>
                {section.icon}
                <div>
                  <span className="section-title">{section.title}</span>
                  {section.subtitle && <span className="section-subtitle">{section.subtitle}</span>}
                </div>
              </div>
              {expandedSection === sIdx ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
            </div>

            {expandedSection === sIdx && (
              <div className="section-body">
                {/* Section 0: Assessment Details */}
                {sIdx === 0 && (
                  <div className="section-fields">
                    <div className="form-group">
                      <label>Assessment Name <span className="required">*</span></label>
                      <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g., Production BigQuery Migration Assessment" />
                    </div>
                    <div className="form-group">
                      <label>Source Database / Data Warehouse <span className="required">*</span></label>
                      {loadingConnections ? (
                        <div className="loading-select">Loading connections...</div>
                      ) : (
                        <Select
                          value={sourceConnectionId || ''}
                          onChange={(v) => setSourceConnectionId(Number(v))}
                          options={[
                            { value: '', label: 'Select source connection' },
                            ...sourceConnections.map(c => ({ value: c.id, label: `${c.name} (${c.database})` }))
                          ]}
                        />
                      )}
                    </div>
                    {mode === 'analyze' && (
                      <div className="form-group">
                        <label>Target Data Warehouse</label>
                        <Select value={targetDb} onChange={(v) => setTargetDb(String(v))} options={[{ value: 'redshift', label: 'Amazon Redshift' }]} />
                      </div>
                    )}
                  </div>
                )}

                {/* Section 1: Data Sources */}
                {sIdx === 1 && (
                  <div className="section-fields">
                    <div className="na-toggle">
                      <label className="toggle-label">
                        <input
                          type="checkbox"
                          checked={!landscape.dataSources.applicable}
                          onChange={(e) => setLandscape(prev => ({ ...prev, dataSources: { ...prev.dataSources, applicable: !e.target.checked } }))}
                        />
                        Not Applicable
                      </label>
                    </div>
                    {landscape.dataSources.applicable && (
                      <>
                        {landscape.dataSources.sources.map((src, idx) => (
                          <div key={idx} className="repeatable-row">
                            <div className="row-fields">
                              <Input placeholder="Source name" value={src.name} onChange={(e) => updateSource(idx, 'name', e.target.value)} />
                              <div>
                                <Select value={src.type} onChange={(v) => updateSource(idx, 'type', String(v))} options={SOURCE_TYPE_OPTIONS} />
                                {src.type === 'other' && <Input placeholder="Specify type" value={src.otherType} onChange={(e) => updateSource(idx, 'otherType', e.target.value)} style={{ marginTop: '6px' }} />}
                              </div>
                              <div>
                                <Select value={src.hosting} onChange={(v) => updateSource(idx, 'hosting', String(v))} options={HOSTING_OPTIONS} />
                                {src.hosting === 'other' && <Input placeholder="Specify hosting" value={src.otherHosting} onChange={(e) => updateSource(idx, 'otherHosting', e.target.value)} style={{ marginTop: '6px' }} />}
                              </div>
                              <Input placeholder="Volume (e.g., 50 GB)" value={src.volume} onChange={(e) => updateSource(idx, 'volume', e.target.value)} />
                              <Select value={src.refreshFrequency} onChange={(v) => updateSource(idx, 'refreshFrequency', String(v))} options={REFRESH_OPTIONS} />
                            </div>
                            {landscape.dataSources.sources.length > 1 && (
                              <button className="remove-row-btn" onClick={() => removeSource(idx)}><Trash2 size={14} /></button>
                            )}
                          </div>
                        ))}
                        <Button variant="outline" onClick={addSource}><Plus size={14} /> Add Data Source</Button>
                      </>
                    )}
                  </div>
                )}

                {/* Section 2: ETL Pipelines */}
                {sIdx === 2 && (
                  <div className="section-fields">
                    <div className="na-toggle">
                      <label className="toggle-label">
                        <input
                          type="checkbox"
                          checked={!landscape.etlPipelines.applicable}
                          onChange={(e) => setLandscape(prev => ({ ...prev, etlPipelines: { ...prev.etlPipelines, applicable: !e.target.checked } }))}
                        />
                        Not Applicable
                      </label>
                    </div>
                    {landscape.etlPipelines.applicable && (
                      <>
                        {landscape.etlPipelines.pipelines.map((pipe, idx) => (
                          <div key={idx} className="repeatable-row">
                            <div className="row-fields">
                              <div>
                                <Select value={pipe.tool} onChange={(v) => updatePipeline(idx, 'tool', String(v))} options={ETL_TOOL_OPTIONS} />
                                {pipe.tool === 'other' && <Input placeholder="Specify tool" value={pipe.otherTool} onChange={(e) => updatePipeline(idx, 'otherTool', e.target.value)} style={{ marginTop: '6px' }} />}
                              </div>
                              <Select value={pipe.transformLocation} onChange={(v) => updatePipeline(idx, 'transformLocation', String(v))} options={[
                                { value: '', label: 'Transform location' },
                                { value: 'in_warehouse', label: 'Inside Warehouse (BQ)' },
                                { value: 'outside_warehouse', label: 'Outside Warehouse' },
                                { value: 'both', label: 'Both' },
                              ]} />
                              <Input placeholder="Number of pipelines" value={pipe.pipelineCount} onChange={(e) => updatePipeline(idx, 'pipelineCount', e.target.value)} />
                              <Select value={pipe.scheduling} onChange={(v) => updatePipeline(idx, 'scheduling', String(v))} options={[
                                { value: '', label: 'Scheduling type' },
                                { value: 'cron', label: 'Cron / Time-based' },
                                { value: 'event_driven', label: 'Event-driven' },
                                { value: 'manual', label: 'Manual' },
                                { value: 'mixed', label: 'Mixed' },
                              ]} />
                              <Input placeholder="Notes (optional)" value={pipe.notes} onChange={(e) => updatePipeline(idx, 'notes', e.target.value)} />
                            </div>
                            {landscape.etlPipelines.pipelines.length > 1 && (
                              <button className="remove-row-btn" onClick={() => removePipeline(idx)}><Trash2 size={14} /></button>
                            )}
                          </div>
                        ))}
                        <Button variant="outline" onClick={addPipeline}><Plus size={14} /> Add Pipeline</Button>
                      </>
                    )}
                  </div>
                )}

                {/* Section 3: Downstream Consumers */}
                {sIdx === 3 && (
                  <div className="section-fields">
                    <div className="na-toggle">
                      <label className="toggle-label">
                        <input
                          type="checkbox"
                          checked={!landscape.downstreamConsumers.applicable}
                          onChange={(e) => setLandscape(prev => ({ ...prev, downstreamConsumers: { ...prev.downstreamConsumers, applicable: !e.target.checked } }))}
                        />
                        Not Applicable
                      </label>
                    </div>
                    {landscape.downstreamConsumers.applicable && (
                      <>
                        {landscape.downstreamConsumers.consumers.map((consumer, idx) => (
                          <div key={idx} className="repeatable-row">
                            <div className="row-fields">
                              <div>
                                <Select value={consumer.tool} onChange={(v) => updateConsumer(idx, 'tool', String(v))} options={BI_TOOL_OPTIONS} />
                                {consumer.tool === 'other' && <Input placeholder="Specify tool name" value={consumer.otherTool} onChange={(e) => updateConsumer(idx, 'otherTool', e.target.value)} style={{ marginTop: '6px' }} />}
                              </div>
                              <Input placeholder="Dashboards / reports" value={consumer.dashboardCount} onChange={(e) => updateConsumer(idx, 'dashboardCount', e.target.value)} />
                              <Input placeholder="Number of users" value={consumer.userCount} onChange={(e) => updateConsumer(idx, 'userCount', e.target.value)} />
                              <Select value={consumer.connectionType} onChange={(v) => updateConsumer(idx, 'connectionType', String(v))} options={[
                                { value: '', label: 'Connection type' },
                                { value: 'direct', label: 'Direct Query (Live)' },
                                { value: 'extract', label: 'Extract / Import' },
                                { value: 'api', label: 'API' },
                                { value: 'export', label: 'Scheduled Export' },
                              ]} />
                              <Input placeholder="Notes (optional)" value={consumer.notes} onChange={(e) => updateConsumer(idx, 'notes', e.target.value)} />
                            </div>
                            {landscape.downstreamConsumers.consumers.length > 1 && (
                              <button className="remove-row-btn" onClick={() => removeConsumer(idx)}><Trash2 size={14} /></button>
                            )}
                          </div>
                        ))}
                        <Button variant="outline" onClick={addConsumer}><Plus size={14} /> Add Consumer</Button>
                      </>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="create-assessment-footer">
        <Button variant="outline" onClick={() => navigate('/assessments')}>Cancel</Button>
        <Button variant="primary" onClick={handleSubmit} disabled={submitting || !name.trim() || !sourceConnectionId}>
          {submitting ? 'Creating...' : 'Start Assessment'}
        </Button>
      </div>
    </div>
  );
};
