import React, { useState, useEffect, useRef } from 'react';
import {
  CheckCircle, AlertTriangle, XCircle, Info, Zap, Database,
  Shield, Code, Brain, ArrowRight, ChevronDown, ChevronUp,
  Loader
} from 'lucide-react';
import { Button, Select } from '../../components/ui';
import {
  listAssessments, Assessment,
  runCompatibilityCheck, CompatibilityReport
} from '../../services/assessmentsApi';
import './AssessmentsPage.css';
import './CompatibilityCheckPage.css';

export const CompatibilityCheckPage: React.FC = () => {
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [selectedAssessmentId, setSelectedAssessmentId] = useState<number | ''>('');
  const [loading, setLoading] = useState(false);
  const [loadingAssessments, setLoadingAssessments] = useState(true);
  const [report, setReport] = useState<CompatibilityReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    dataTypes: true, featureGaps: true, sqlSyntax: true, llmInsights: true,
  });
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
      const data = await listAssessments();
      // Only show completed assessments
      setAssessments(data.assessments.filter(a => a.status === 'completed'));
    } catch (err: any) {
      console.error('Failed to fetch assessments:', err);
    } finally {
      setLoadingAssessments(false);
    }
  };

  const handleRunCheck = async () => {
    if (!selectedAssessmentId) return;
    try {
      setLoading(true);
      setError(null);
      setReport(null);
      const result = await runCompatibilityCheck(selectedAssessmentId as number);
      setReport(result);
    } catch (err: any) {
      setError(err.detail || err.message || 'Compatibility check failed');
    } finally {
      setLoading(false);
    }
  };

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

  const assessmentOptions = assessments.map(a => ({
    value: a.id,
    label: `${a.name} (${a.total_tables} tables, ${a.total_size_mb.toFixed(1)} MB)`,
  }));

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Compatibility Check</h1>
        <p className="page-description">
          Analyze BigQuery → Redshift compatibility: data types, feature gaps, SQL syntax, and AI-powered insights
        </p>
      </div>

      <div className="page-content">
        {/* Selection Panel */}
        <div className="compat-selection-panel">
          <div className="compat-selection-row">
            <div className="compat-select-group">
              <label>Select Completed Assessment</label>
              {loadingAssessments ? (
                <div className="compat-loading-inline"><Loader size={16} className="spin" /> Loading assessments...</div>
              ) : (
                <Select
                  value={selectedAssessmentId}
                  onChange={(val) => setSelectedAssessmentId(val as number)}
                  options={assessmentOptions}
                  disabled={loading}
                />
              )}
            </div>
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
          </div>
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
                <div className="compat-score-circle" style={{ borderColor: getScoreColor(report.overall_score) }}>
                  <span className="compat-score-value" style={{ color: getScoreColor(report.overall_score) }}>
                    {report.overall_score}
                  </span>
                  <span className="compat-score-label">/ 100</span>
                </div>
                <div className="compat-score-info">
                  <h2>Overall Compatibility Score</h2>
                  <p className="compat-assessment-name">{report.assessment_name}</p>
                  <div className="compat-score-bars">
                    {[
                      { label: 'Data Types', score: report.score_breakdown.data_types, icon: <Database size={14} /> },
                      { label: 'Feature Gaps', score: report.score_breakdown.feature_gaps, icon: <Shield size={14} /> },
                      { label: 'SQL Syntax', score: report.score_breakdown.sql_syntax, icon: <Code size={14} /> },
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
                  { label: 'Tables', value: report.summary.total_tables },
                  { label: 'Columns', value: report.summary.total_columns },
                  { label: 'Views', value: report.summary.total_views },
                  { label: 'Routines', value: report.summary.total_routines },
                  { label: 'ML Models', value: report.summary.total_ml_models },
                  { label: 'Security Policies', value: report.summary.total_security_policies },
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
                  <span className="compat-section-count">{report.data_type_analysis.total_columns} columns</span>
                </div>
                {expandedSections.dataTypes ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
              </button>
              {expandedSections.dataTypes && (
                <div className="compat-section-body">
                  <div className="compat-type-stats">
                    {Object.entries(report.data_type_analysis.stats).map(([key, count]) => (
                      count > 0 && (
                        <div key={key} className="compat-type-stat">
                          {getCompatBadge(key)} <span>{count} column{count !== 1 ? 's' : ''}</span>
                        </div>
                      )
                    ))}
                  </div>
                  <div className="compat-table-wrapper">
                    <table className="compat-table">
                      <thead>
                        <tr>
                          <th>Table</th>
                          <th>Column</th>
                          <th>BigQuery Type</th>
                          <th><ArrowRight size={14} /></th>
                          <th>Redshift Type</th>
                          <th>Status</th>
                          <th>Notes</th>
                        </tr>
                      </thead>
                      <tbody>
                        {report.data_type_analysis.mappings
                          .filter(m => m.compatibility !== 'full')
                          .slice(0, 100)
                          .map((m, i) => (
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
                    {report.data_type_analysis.mappings.filter(m => m.compatibility !== 'full').length === 0 && (
                      <div className="compat-all-good">
                        <CheckCircle size={20} /> All columns have full compatibility
                      </div>
                    )}
                    {report.data_type_analysis.stats.full > 0 && (
                      <div className="compat-full-note">
                        <Info size={14} /> {report.data_type_analysis.stats.full} fully compatible column(s) hidden
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* AI-Powered Insights (after Data Type Mappings) */}
            {report.llm_insights && (
              <div className="compat-section compat-ai-section">
                <button className="compat-section-header compat-ai-header" onClick={() => toggleSection('llmInsights')}>
                  <div className="compat-section-title"><Brain size={18} /> AI-Powered Insights</div>
                  {expandedSections.llmInsights ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                </button>
                {expandedSections.llmInsights && (
                  <div className="compat-section-body">
                    {/* Executive Summary */}
                    <div className="llm-executive-summary">
                      <h4>Executive Summary</h4>
                      <p>{report.llm_insights.executive_summary}</p>
                    </div>

                    {/* Migration Approach + Effort Level side by side */}
                    <div className="llm-grid">
                      <div className="llm-card llm-approach-card">
                        <div className="llm-card-icon"><ArrowRight size={16} /></div>
                        <h4>Migration Approach</h4>
                        <p>{report.llm_insights.migration_approach}</p>
                      </div>
                      <div className="llm-card llm-effort-card">
                        <div className="llm-card-icon"><Zap size={16} /></div>
                        <h4>Effort Level</h4>
                        <p className="llm-effort-value">{report.llm_insights.effort_level}</p>
                        <p className="llm-effort-detail">{report.llm_insights.effort_justification}</p>
                      </div>
                    </div>

                    {/* Critical Risks */}
                    {report.llm_insights.critical_risks?.length > 0 && (
                      <div className="llm-risks">
                        <h4>Critical Risks</h4>
                        <div className="llm-risks-grid">
                          {report.llm_insights.critical_risks.map((r, i) => (
                            <div key={i} className="llm-risk-card">
                              <div className="llm-risk-icon"><AlertTriangle size={16} /></div>
                              <div className="llm-risk-content">
                                <div className="llm-risk-title">{r.risk}</div>
                                <div className="llm-risk-row"><span className="llm-risk-label">Impact:</span> {r.impact}</div>
                                <div className="llm-risk-row"><span className="llm-risk-label">Mitigation:</span> {r.mitigation}</div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Additional Recommendations */}
                    {report.llm_insights.additional_recommendations?.length > 0 && (
                      <div className="llm-recommendations">
                        <h4>Additional Recommendations</h4>
                        <div className="llm-rec-list">
                          {report.llm_insights.additional_recommendations.map((r, i) => (
                            <div key={i} className="llm-rec-item">
                              <CheckCircle size={14} className="llm-rec-icon" />
                              <span>{r}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Feature Gaps */}
            <div className="compat-section">
              <button className="compat-section-header" onClick={() => toggleSection('featureGaps')}>
                <div className="compat-section-title">
                  <Shield size={18} /> Feature Gaps
                  <span className="compat-section-count">{report.feature_gaps.length} issue{report.feature_gaps.length !== 1 ? 's' : ''}</span>
                </div>
                {expandedSections.featureGaps ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
              </button>
              {expandedSections.featureGaps && (
                <div className="compat-section-body">
                  {report.feature_gaps.length === 0 ? (
                    <div className="compat-all-good"><CheckCircle size={20} /> No feature gaps detected</div>
                  ) : (
                    <div className="compat-gaps-list">
                      {report.feature_gaps.map((gap, i) => (
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
                  <span className="compat-section-count">{report.sql_syntax_issues.length} pattern{report.sql_syntax_issues.length !== 1 ? 's' : ''}</span>
                </div>
                {expandedSections.sqlSyntax ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
              </button>
              {expandedSections.sqlSyntax && (
                <div className="compat-section-body">
                  {report.sql_syntax_issues.length === 0 ? (
                    <div className="compat-all-good"><CheckCircle size={20} /> No SQL syntax issues detected</div>
                  ) : (
                    <div className="compat-table-wrapper">
                      <table className="compat-table">
                        <thead>
                          <tr>
                            <th>BQ Pattern</th>
                            <th>Severity</th>
                            <th>Affected</th>
                            <th>Redshift Fix</th>
                            <th>Items</th>
                          </tr>
                        </thead>
                        <tbody>
                          {report.sql_syntax_issues.map((issue, i) => (
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

        {/* Empty state when no report */}
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
              Select a completed assessment above and click "Run Compatibility Check" to analyze
              data type mappings, feature gaps, SQL syntax differences, and get AI-powered migration insights.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
