import React, { useState, useEffect, useRef } from 'react';
import {
  CheckCircle, XCircle, Info, Zap, Database,
  Shield, Code, Brain, ArrowRight, ChevronDown, ChevronUp,
  Loader
} from 'lucide-react';
import { Button, Select } from '../../components/ui';
import { SearchableSelect } from '../../components/ui/SearchableSelect';
import {
  listAssessments, Assessment,
  runCompatibilityCheck, CompatibilityReport,
  saveCompatibilityResult, getSavedCompatibility
} from '../../services/assessmentsApi';
import { listConnections, Connection } from '../../services/api';
import './AssessmentsPage.css';
import './CompatibilityCheckPage.css';

export const CompatibilityCheckPage: React.FC = () => {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [selectedSourceId, setSelectedSourceId] = useState<number | ''>('');
  const [selectedTarget, setSelectedTarget] = useState<string>('redshift');
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [selectedAssessmentId, setSelectedAssessmentId] = useState<number | ''>('');
  const [selectedAssessmentName, setSelectedAssessmentName] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [loadingConnections, setLoadingConnections] = useState(true);
  const [loadingAssessments, setLoadingAssessments] = useState(false);
  const [report, setReport] = useState<CompatibilityReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saved' | 'error'>('idle');
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    dataTypes: true, featureGaps: true, sqlSyntax: true, llmInsights: true,
  });
  const [compatDataset, setCompatDataset] = useState<string | number>('all');
  const [compatTable, setCompatTable] = useState<string | number>('all');
  const hasFetched = useRef(false);

  useEffect(() => {
    if (!hasFetched.current) {
      hasFetched.current = true;
      fetchConnections();
    }
  }, []);

  const fetchConnections = async () => {
    try {
      setLoadingConnections(true);
      const data = await listConnections();
      setConnections(data.filter(c => c.type === 'source'));
    } catch (err: any) {
      // silently fail
    } finally {
      setLoadingConnections(false);
    }
  };

  // When source connection changes, find matching assessments
  useEffect(() => {
    if (selectedSourceId) {
      setSelectedAssessmentId('');
      setReport(null);
      setSaveStatus('idle');
      fetchAssessmentsForConnection(selectedSourceId as number);
    } else {
      setAssessments([]);
      setSelectedAssessmentId('');
      setReport(null);
    }
  }, [selectedSourceId]);

  const fetchAssessmentsForConnection = async (connectionId: number) => {
    try {
      setLoadingAssessments(true);
      const data = await listAssessments();
      const filtered = data.assessments.filter(
        a => a.source_connection_id === connectionId && a.status === 'completed'
      );
      setAssessments(filtered);
      // Auto-select if only one assessment
      if (filtered.length === 1) {
        setSelectedAssessmentId(filtered[0].id);
        setSelectedAssessmentName(filtered[0].name);
      }
    } catch (err: any) {
      // silently fail
    } finally {
      setLoadingAssessments(false);
    }
  };

  // Group assessments by name for the dropdown, and get versions for selected name
  const assessmentNames = React.useMemo(() => {
    const names = new Set<string>();
    assessments.forEach(a => names.add(a.name));
    return Array.from(names).sort();
  }, [assessments]);

  const versionsForSelected = React.useMemo(() => {
    if (!selectedAssessmentName) return [];
    return assessments
      .filter(a => a.name === selectedAssessmentName)
      .sort((a, b) => (b.version || 1) - (a.version || 1));
  }, [assessments, selectedAssessmentName]);

  const assessmentNameOptions = assessmentNames.map(name => {
    const latest = assessments.filter(a => a.name === name).sort((a, b) => (b.version || 1) - (a.version || 1))[0];
    return { value: name, label: `${name} (${latest.total_tables} tables, ${latest.total_size_mb.toFixed(1)} MB)` };
  });

  const versionOptions = versionsForSelected.map(a => ({
    value: a.id,
    label: `v${a.version || 1}${a.id === versionsForSelected[0]?.id ? ' (latest)' : ''}`,
  }));

  const handleRunCheck = async () => {
    if (!selectedAssessmentId) return;
    try {
      setLoading(true);
      setError(null);
      setReport(null);
      const result = await runCompatibilityCheck(selectedAssessmentId as number);
      if (result && result.summary) {
        result.summary.total_security_policies = result.summary.total_security_policies ?? 0;
        result.summary.total_sharded_tables = result.summary.total_sharded_tables ?? 0;
      }
      setReport(result);
      try {
        await saveCompatibilityResult(selectedAssessmentId as number, result);
        setSaveStatus('saved');
      } catch (saveErr) {
        setSaveStatus('error');
      }
    } catch (err: any) {
      setError(err.detail || err.message || 'Compatibility check failed');
    } finally {
      setLoading(false);
    }
  };

  // Auto-load saved result when assessment is selected
  useEffect(() => {
    if (selectedAssessmentId) {
      setSaveStatus('idle');
      const loadSaved = async () => {
        try {
          const saved = await getSavedCompatibility(selectedAssessmentId as number);
          if (saved.found && saved.report) {
            setReport(saved.report);
            setSaveStatus('saved');
          }
        } catch (err) {
          // Silently fail
        }
      };
      loadSaved();
    } else {
      setReport(null);
      setSaveStatus('idle');
    }
  }, [selectedAssessmentId]);

  const toggleSection = (key: string) => {
    setExpandedSections(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return '#10b981';
    if (score >= 60) return '#f59e0b';
    if (score >= 40) return '#f97316';
    return '#ef4444';
  };

  const getSeverityBadge = (severity: string) => {
    const colors: Record<string, string> = { high: '#ef4444', medium: '#f59e0b', low: '#3b82f6' };
    return (
      <span className="severity-badge" style={{ background: colors[severity] || '#6b7280' }}>
        {severity.toUpperCase()}
      </span>
    );
  };

  const getCompatBadge = (compat: string) => {
    const map: Record<string, { bg: string; label: string }> = {
      full: { bg: '#10b981', label: 'Full' },
      partial: { bg: '#f59e0b', label: 'Partial' },
      lossy: { bg: '#f97316', label: 'Lossy' },
      unsupported: { bg: '#ef4444', label: 'Unsupported' },
      unknown: { bg: '#6b7280', label: 'Unknown' },
    };
    const m = map[compat] || map.unknown;
    return <span className="compat-badge" style={{ background: m.bg }}>{m.label}</span>;
  };

  const sourceOptions = connections.map(c => ({
    value: c.id,
    label: c.name,
  }));

  const targetOptions = [
    { value: 'redshift', label: 'Amazon Redshift' },
  ];

  const selectedSourceName = connections.find(c => c.id === selectedSourceId)?.name || '';

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Analyze</h1>
        <p className="page-description">
          Select an assessment and target system to analyze compatibility: data types, feature gaps, SQL syntax, and AI-powered insights
        </p>
      </div>

      <div className="page-content">
        {/* Selection Panel */}
        <div className="compat-selection-panel">
          <div className="compat-selection-row">
            <div className="compat-select-group">
              <label>Source Connection</label>
              {loadingConnections ? (
                <div className="compat-loading-inline"><Loader size={16} className="spin" /> Loading connections...</div>
              ) : (
                <SearchableSelect
                  value={selectedSourceId}
                  onChange={(val) => setSelectedSourceId(val as number)}
                  options={sourceOptions}
                  placeholder="Select source connection"
                />
              )}
            </div>
            <div className="compat-select-group">
              <label>Target System</label>
              <Select
                value={selectedTarget}
                onChange={(val) => setSelectedTarget(val as string)}
                options={targetOptions}
                disabled={true}
              />
            </div>
          </div>

          {/* Assessment selection - shown when source is selected */}
          {selectedSourceId && (
            <div className="compat-selection-row" style={{ marginTop: 12 }}>
              <div className="compat-select-group">
                <label>Select Assessment</label>
                {loadingAssessments ? (
                  <div className="compat-loading-inline"><Loader size={16} className="spin" /> Loading assessments...</div>
                ) : assessmentNames.length === 0 ? (
                  <div className="compat-no-assessments">
                    <Info size={14} /> No completed assessments found for this connection. Run an Assessment first.
                  </div>
                ) : (
                  <SearchableSelect
                    value={selectedAssessmentName}
                    onChange={(val) => {
                      const name = val as string;
                      setSelectedAssessmentName(name);
                      // Auto-select latest version
                      const latest = assessments.filter(a => a.name === name).sort((a, b) => (b.version || 1) - (a.version || 1))[0];
                      if (latest) setSelectedAssessmentId(latest.id);
                    }}
                    options={assessmentNameOptions}
                    placeholder="Select assessment"
                  />
                )}
              </div>
              {selectedAssessmentName && versionsForSelected.length > 1 && (
                <div className="compat-select-group" style={{ maxWidth: 160 }}>
                  <label>Version</label>
                  <SearchableSelect
                    value={selectedAssessmentId}
                    onChange={(val) => setSelectedAssessmentId(val as number)}
                    options={versionOptions}
                    placeholder="Version"
                  />
                </div>
              )}
              <Button
                onClick={handleRunCheck}
                disabled={!selectedAssessmentId || loading}
                className="compat-run-btn"
              >
                {loading ? (
                  <><Loader size={16} className="spin" /> Analyzing...</>
                ) : (
                  <><Zap size={16} /> Run Compatibility Check</>
                )}
              </Button>
              {saveStatus === 'saved' && (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#10b981', marginLeft: 12 }}>
                  <CheckCircle size={14} /> Saved
                </span>
              )}
            </div>
          )}

          {error && (
            <div className="compat-error">
              <XCircle size={16} /> {error}
            </div>
          )}
        </div>

        {/* Results */}
        {report && (
          <div className="compat-results">
            {/* Score Overview */}
            <div className="compat-score-overview">
              <div className="compat-score-main">
                <div className="compat-score-circle" style={{ borderColor: getScoreColor(report.overall_score || 0) }}>
                  <span className="compat-score-value" style={{ color: getScoreColor(report.overall_score || 0) }}>
                    {report.overall_score ?? 0}
                  </span>
                  <span className="compat-score-label">/ 100</span>
                </div>
                <div className="compat-score-info">
                  <h2>Overall Compatibility Score</h2>
                  <p className="compat-assessment-name">
                    {selectedSourceName} → Amazon Redshift
                  </p>
                  <div className="compat-score-bars">
                    {[
                      { label: 'Data Types', score: report.score_breakdown?.data_types ?? 0, icon: <Database size={14} /> },
                      { label: 'Feature Gaps', score: report.score_breakdown?.feature_gaps ?? 0, icon: <Shield size={14} /> },
                      { label: 'SQL Syntax', score: report.score_breakdown?.sql_syntax ?? 0, icon: <Code size={14} /> },
                    ].map(item => (
                      <div key={item.label} className="compat-score-bar-row">
                        <div className="compat-score-bar-label">{item.icon} {item.label}</div>
                        <div className="compat-score-bar-track">
                          <div
                            className="compat-score-bar-fill"
                            style={{ width: `${item.score}%`, background: getScoreColor(item.score) }}
                          />
                        </div>
                        <span className="compat-score-bar-value">{item.score}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              <div className="compat-summary-stats">
                {[
                  { label: 'Tables', value: report.summary?.total_tables ?? 0 },
                  { label: 'Columns', value: report.summary?.total_columns ?? 0 },
                  { label: 'Views', value: report.summary?.total_views ?? 0 },
                  { label: 'Routines', value: report.summary?.total_routines ?? 0 },
                  { label: 'ML Models', value: report.summary?.total_ml_models ?? 0 },
                  { label: 'Security Policies', value: report.summary?.total_security_policies ?? 0 },
                ].map(s => (
                  <div key={s.label} className="compat-stat-card">
                    <span className="compat-stat-value">{s.value}</span>
                    <span className="compat-stat-label">{s.label}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Data Type Mappings */}
            <div className="compat-section">
              <button className="compat-section-header" onClick={() => toggleSection('dataTypes')}>
                <div className="compat-section-title">
                  <Database size={18} /> Data Type Mappings
                  <span className="compat-section-count">{report.data_type_analysis?.total_columns ?? 0} columns</span>
                </div>
                {expandedSections.dataTypes ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
              </button>
              {expandedSections.dataTypes && (
                <div className="compat-section-body">
                  <div className="compat-type-stats">
                    {Object.entries(report.data_type_analysis?.stats || {}).map(([key, count]) => (
                      (count as number) > 0 && (
                        <div key={key} className="compat-type-stat">
                        {getCompatBadge(key)} <span>{count as number} column{(count as number) !== 1 ? 's' : ''}</span>
                        </div>
                      )
                    ))}
                  </div>
                  {(() => {
                    const allMappings = (report.data_type_analysis?.mappings || []).filter(m => m.compatibility !== 'full');
                    const getDs = (name: string) => name.includes('.') ? name.split('.')[0] : 'Unknown';
                    const datasets = Array.from(new Set(allMappings.map(m => getDs(m.table_name)))).sort();
                    const dsOptions = [
                      { value: 'all', label: `All Datasets (${datasets.length})` },
                      ...datasets.map(ds => ({ value: ds, label: ds })),
                    ];
                    const filteredByDs = compatDataset === 'all' ? allMappings : allMappings.filter(m => getDs(m.table_name) === compatDataset);
                    const tables = Array.from(new Set(filteredByDs.map(m => m.table_name))).sort();
                    const tblOptions = [
                      { value: 'all', label: `All Tables (${tables.length})` },
                      ...tables.map(t => ({ value: t, label: t })),
                    ];
                    const filtered = compatTable === 'all' ? filteredByDs : filteredByDs.filter(m => m.table_name === compatTable);
                    return (
                      <>
                        <div className="section-filters" style={{ marginBottom: 'var(--spacing-4)' }}>
                          <SearchableSelect
                            value={compatDataset}
                            onChange={(v) => { setCompatDataset(v); setCompatTable('all'); }}
                            options={dsOptions}
                            placeholder="All Datasets"
                          />
                          <SearchableSelect
                            value={compatTable}
                            onChange={setCompatTable}
                            options={tblOptions}
                            placeholder="All Tables"
                          />
                        </div>
                        <div className="compat-table-wrapper">
                          <table className="compat-table">
                            <thead>
                              <tr>
                                <th>Table</th>
                                <th>Column</th>
                                <th>Source Type</th>
                                <th><ArrowRight size={14} /></th>
                                <th>Redshift Type</th>
                                <th>Status</th>
                                <th>Notes</th>
                              </tr>
                            </thead>
                            <tbody>
                              {filtered.slice(0, 100).map((m, i) => (
                                <tr key={i} className={`compat-row-${m.compatibility}`}>
                                  <td className="compat-cell-table">{m.table_name}</td>
                                  <td>{m.column_name}</td>
                                  <td className="compat-cell-type">{m.bq_type}</td>
                                  <td className="compat-cell-arrow"><ArrowRight size={12} /></td>
                                  <td className="compat-cell-type">{m.redshift_type}</td>
                                  <td>{getCompatBadge(m.compatibility)}</td>
                                  <td className="compat-cell-notes">{m.notes}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          {filtered.length === 0 && (
                            <div className="compat-all-good">
                              <CheckCircle size={20} /> All columns have full compatibility
                            </div>
                          )}
                          {(report.data_type_analysis?.stats?.full ?? 0) > 0 && (
                            <div className="compat-full-note">
                              <Info size={14} /> {report.data_type_analysis?.stats?.full ?? 0} fully compatible column(s) hidden
                            </div>
                          )}
                        </div>
                      </>
                    );
                  })()}
                </div>
              )}
            </div>

            {/* AI-Powered Insights */}
            {report.llm_insights && (
              <div className="compat-section compat-ai-section">
                <button className="compat-section-header compat-ai-header" onClick={() => toggleSection('llmInsights')}>
                  <div className="compat-section-title"><Brain size={18} /> AI Migration Strategy</div>
                  {expandedSections.llmInsights ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                </button>
                {expandedSections.llmInsights && (
                  <div className="compat-section-body">
                    <div className="llm-top-row">
                      <div className="llm-summary-text">{report.llm_insights.executive_summary}</div>
                      <div className="llm-meta-pills">
                        <span className={`llm-effort-pill llm-effort-${(report.llm_insights.effort_level || '').toLowerCase()}`}>
                          {report.llm_insights.effort_level}
                        </span>
                        {report.llm_insights.estimated_timeline && (
                          <span className="llm-timeline-pill">⏱ {report.llm_insights.estimated_timeline}</span>
                        )}
                      </div>
                    </div>
                    <div className="llm-strategy-grid">
                      <div className="llm-strategy-card">
                        <div className="llm-strategy-label">Approach</div>
                        <div className="llm-strategy-value">{report.llm_insights.migration_approach}</div>
                      </div>
                      {report.llm_insights.rollback_plan && (
                        <div className="llm-strategy-card">
                          <div className="llm-strategy-label">Rollback Plan</div>
                          <div className="llm-strategy-value">{report.llm_insights.rollback_plan}</div>
                        </div>
                      )}
                    </div>
                    <div className="llm-details-grid">
                      {report.llm_insights.team_requirements && report.llm_insights.team_requirements.length > 0 && (
                        <div className="llm-detail-col">
                          <div className="llm-detail-title">Team Needed</div>
                          {report.llm_insights.team_requirements.map((t, i) => (
                            <div key={i} className="llm-detail-item">
                              <span className="llm-detail-role">{t.role}</span>
                              <span className="llm-detail-reason">{t.reason}</span>
                            </div>
                          ))}
                        </div>
                      )}
                      {report.llm_insights.testing_strategy && report.llm_insights.testing_strategy.length > 0 && (
                        <div className="llm-detail-col">
                          <div className="llm-detail-title">Testing Strategy</div>
                          {report.llm_insights.testing_strategy.map((s, i) => (
                            <div key={i} className="llm-detail-step">{i + 1}. {s}</div>
                          ))}
                        </div>
                      )}
                      {report.llm_insights.cost_considerations && report.llm_insights.cost_considerations.length > 0 && (
                        <div className="llm-detail-col">
                          <div className="llm-detail-title">Cost Factors</div>
                          {report.llm_insights.cost_considerations.map((c, i) => (
                            <div key={i} className="llm-detail-step">{c}</div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Feature Gaps */}
            <div className="compat-section">
              <button className="compat-section-header" onClick={() => toggleSection('featureGaps')}>
                <div className="compat-section-title">
                  <Shield size={18} /> Feature Gaps
                  <span className="compat-section-count">{(report.feature_gaps || []).length} issue{(report.feature_gaps || []).length !== 1 ? 's' : ''}</span>
                </div>
                {expandedSections.featureGaps ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
              </button>
              {expandedSections.featureGaps && (
                <div className="compat-section-body">
                  {(report.feature_gaps || []).length === 0 ? (
                    <div className="compat-all-good"><CheckCircle size={20} /> No feature gaps detected</div>
                  ) : (
                    <div className="compat-gaps-list">
                      {(report.feature_gaps || []).map((gap, i) => (
                        <div key={i} className={`compat-gap-card severity-${gap.severity}`}>
                          <div className="compat-gap-header">
                            <span className="compat-gap-category">{gap.category}</span>
                            {getSeverityBadge(gap.severity)}
                            <span className="compat-gap-count">{gap.count} item{gap.count !== 1 ? 's' : ''}</span>
                          </div>
                          <p className="compat-gap-desc">{gap.description}</p>
                          <div className="compat-gap-recommendation">
                            <strong>Recommendation:</strong> {gap.recommendation}
                          </div>
                          {gap.items.length > 0 && (
                            <div className="compat-gap-items">
                              {gap.items.slice(0, 5).map((item, j) => (
                                <span key={j} className="compat-gap-item-tag">{item}</span>
                              ))}
                              {gap.items.length > 5 && <span className="compat-gap-more">+{gap.items.length - 5} more</span>}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* SQL Syntax Issues */}
            <div className="compat-section">
              <button className="compat-section-header" onClick={() => toggleSection('sqlSyntax')}>
                <div className="compat-section-title">
                  <Code size={18} /> SQL Syntax Issues
                  <span className="compat-section-count">{(report.sql_syntax_issues || []).length} pattern{(report.sql_syntax_issues || []).length !== 1 ? 's' : ''}</span>
                </div>
                {expandedSections.sqlSyntax ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
              </button>
              {expandedSections.sqlSyntax && (
                <div className="compat-section-body">
                  {(report.sql_syntax_issues || []).length === 0 ? (
                    <div className="compat-all-good"><CheckCircle size={20} /> No SQL syntax issues detected</div>
                  ) : (
                    <div className="compat-table-wrapper">
                      <table className="compat-table">
                        <thead>
                          <tr>
                            <th>Source Pattern</th>
                            <th>Severity</th>
                            <th>Affected</th>
                            <th>Redshift Fix</th>
                            <th>Items</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(report.sql_syntax_issues || []).map((issue, i) => (
                            <tr key={i}>
                              <td><code className="compat-code">{issue.pattern}</code></td>
                              <td>{getSeverityBadge(issue.severity)}</td>
                              <td className="compat-cell-center">{issue.affected_count}</td>
                              <td>{issue.fix}</td>
                              <td className="compat-cell-items">
                                {issue.affected_items.slice(0, 3).map((item, j) => (
                                  <span key={j} className="compat-gap-item-tag">{item}</span>
                                ))}
                                {issue.affected_items.length > 3 && (
                                  <span className="compat-gap-more">+{issue.affected_items.length - 3} more</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Empty state */}
        {!report && !loading && !error && (
          <div className="empty-state">
            <div className="empty-state-icon">
              <svg width="64" height="64" viewBox="0 0 64 64" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="20" cy="32" r="12" />
                <circle cx="44" cy="32" r="12" />
                <path d="M32 32h0" strokeWidth="4" strokeLinecap="round" />
              </svg>
            </div>
            <h2>Run a Compatibility Check</h2>
            <p>
              Select a source connection and target system above, then choose an assessment to analyze
              data type mappings, feature gaps, SQL syntax differences, and get AI-powered migration insights.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
