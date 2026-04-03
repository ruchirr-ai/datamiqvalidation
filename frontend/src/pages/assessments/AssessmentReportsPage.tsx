import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Eye, Download, FileText, Database, ChevronDown, ChevronRight } from 'lucide-react';
import { listAssessments, Assessment } from '../../services/assessmentsApi';
import './AssessmentsPage.css';
import './AssessmentReportsPage.css';

interface AssessmentGroup {
  name: string;
  versions: Assessment[];
}

export const AssessmentReportsPage: React.FC = () => {
  const navigate = useNavigate();
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const hasFetched = useRef(false);

  useEffect(() => {
    if (!hasFetched.current) {
      hasFetched.current = true;
      fetchAssessments();
    }
  }, []);

  const fetchAssessments = async () => {
    try {
      setLoading(true);
      const data = await listAssessments();
      setAssessments(data.assessments.filter(a => a.status === 'completed'));
    } catch (err) {
      // silently fail
    } finally {
      setLoading(false);
    }
  };

  // Group assessments by name, sorted by version desc within each group
  const groupedAssessments: AssessmentGroup[] = React.useMemo(() => {
    const groups: Record<string, Assessment[]> = {};
    for (const a of assessments) {
      const key = a.name;
      if (!groups[key]) groups[key] = [];
      groups[key].push(a);
    }
    // Sort each group by version desc (latest first)
    return Object.entries(groups).map(([name, versions]) => ({
      name,
      versions: versions.sort((a, b) => (b.version || 1) - (a.version || 1)),
    })).sort((a, b) => {
      // Sort groups by latest completion date
      const aDate = a.versions[0]?.completed_at || '';
      const bDate = b.versions[0]?.completed_at || '';
      return bDate.localeCompare(aDate);
    });
  }, [assessments]);

  const toggleGroup = (name: string) => {
    setExpandedGroups(prev => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const formatDateTime = (dateString: string | null) => {
    if (!dateString) return 'N/A';
    try {
      const normalized = dateString.endsWith('Z') ? dateString : dateString + 'Z';
      const date = new Date(normalized);
      return date.toLocaleString('en-IN', {
        timeZone: 'Asia/Kolkata',
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
      });
    } catch {
      return 'Invalid date';
    }
  };

  const formatSize = (sizeMb: number) => {
    if (sizeMb < 1024) return `${sizeMb.toFixed(1)} MB`;
    return `${(sizeMb / 1024).toFixed(2)} GB`;
  };

  const getDuration = (start: string | null, end: string | null) => {
    if (!start || !end) return 'N/A';
    const s = new Date(start.endsWith('Z') ? start : start + 'Z').getTime();
    const e = new Date(end.endsWith('Z') ? end : end + 'Z').getTime();
    const sec = Math.floor((e - s) / 1000);
    if (sec < 60) return `${sec}s`;
    if (sec < 3600) return `${Math.floor(sec / 60)}m ${sec % 60}s`;
    return `${Math.floor(sec / 3600)}h ${Math.floor((sec % 3600) / 60)}m`;
  };

  const handleView = (id: number) => {
    navigate(`/assessments/${id}/report`);
  };

  const handleDownload = (assessment: Assessment) => {
    navigate(`/assessments/${assessment.id}/report`);
  };

  const renderRow = (a: Assessment, isChild: boolean = false) => (
    <tr key={a.id} className={isChild ? 'report-version-row' : ''}>
      <td>
        <div className="report-name-cell" style={isChild ? { paddingLeft: 28 } : {}}>
          {!isChild && <FileText size={16} style={{ color: '#66748C', flexShrink: 0 }} />}
          <span className={isChild ? 'report-name report-name-muted' : 'report-name'}>
            {isChild ? '' : a.name}
          </span>
        </div>
      </td>
      <td>
        <span className={`report-version-badge ${!isChild ? 'report-version-latest' : ''}`}>
          v{a.version || 1}
        </span>
      </td>
      <td>
        <span className="report-db-badge">
          <Database size={13} /> {a.total_datasets} dataset{a.total_datasets !== 1 ? 's' : ''}
        </span>
      </td>
      <td>{a.total_tables}</td>
      <td>{formatSize(a.total_size_mb)}</td>
      <td className="report-time">{formatDateTime(a.completed_at)}</td>
      <td className="report-time">{getDuration(a.started_at, a.completed_at)}</td>
      <td>
        <div className="report-actions">
          <button className="report-action-btn" onClick={() => handleView(a.id)} title="View Report">
            <Eye size={15} /> View
          </button>
          <button className="report-action-btn report-action-download" onClick={() => handleDownload(a)} title="Download PDF">
            <Download size={15} /> PDF
          </button>
        </div>
      </td>
    </tr>
  );

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Assessment Reports</h1>
        <p className="page-description">
          View and download completed assessment reports
        </p>
      </div>

      <div className="page-content">
        {loading ? (
          <div className="reports-loading">Loading reports...</div>
        ) : groupedAssessments.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">
              <svg width="64" height="64" viewBox="0 0 64 64" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="12" y="8" width="40" height="48" rx="2" />
                <path d="M20 20h24M20 28h24M20 36h16" strokeLinecap="round" />
              </svg>
            </div>
            <h2>No Reports Yet</h2>
            <p>Run an assessment from the Assessments page to generate reports.</p>
          </div>
        ) : (
          <div className="reports-table-container">
            <table className="reports-table">
              <thead>
                <tr>
                  <th>REPORT NAME</th>
                  <th>VERSION</th>
                  <th>DATABASE</th>
                  <th>TABLES</th>
                  <th>SIZE</th>
                  <th>COMPLETED AT</th>
                  <th>DURATION</th>
                  <th>ACTIONS</th>
                </tr>
              </thead>
              <tbody>
                {groupedAssessments.map(group => {
                  const latest = group.versions[0];
                  const olderVersions = group.versions.slice(1);
                  const hasOlder = olderVersions.length > 0;
                  const isExpanded = expandedGroups.has(group.name);

                  return (
                    <React.Fragment key={group.name}>
                      {/* Latest version row */}
                      <tr>
                        <td>
                          <div className="report-name-cell">
                            {hasOlder ? (
                              <button
                                className="report-expand-btn"
                                onClick={() => toggleGroup(group.name)}
                                aria-label={isExpanded ? 'Collapse versions' : 'Expand versions'}
                              >
                                {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                              </button>
                            ) : (
                              <FileText size={16} style={{ color: '#66748C', flexShrink: 0 }} />
                            )}
                            <span className="report-name">{latest.name}</span>
                            {hasOlder && (
                              <span className="report-versions-count" onClick={() => toggleGroup(group.name)}>
                                {group.versions.length} versions
                              </span>
                            )}
                          </div>
                        </td>
                        <td><span className="report-version-badge report-version-latest">v{latest.version || 1}</span></td>
                        <td><span className="report-db-badge"><Database size={13} /> {latest.total_datasets} dataset{latest.total_datasets !== 1 ? 's' : ''}</span></td>
                        <td>{latest.total_tables}</td>
                        <td>{formatSize(latest.total_size_mb)}</td>
                        <td className="report-time">{formatDateTime(latest.completed_at)}</td>
                        <td className="report-time">{getDuration(latest.started_at, latest.completed_at)}</td>
                        <td>
                          <div className="report-actions">
                            <button className="report-action-btn" onClick={() => handleView(latest.id)} title="View Report"><Eye size={15} /> View</button>
                            <button className="report-action-btn report-action-download" onClick={() => handleDownload(latest)} title="Download PDF"><Download size={15} /> PDF</button>
                          </div>
                        </td>
                      </tr>
                      {/* Older versions */}
                      {isExpanded && olderVersions.map(a => renderRow(a, true))}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
            <div className="reports-footer">
              Showing {groupedAssessments.length} assessment{groupedAssessments.length !== 1 ? 's' : ''} ({assessments.length} total version{assessments.length !== 1 ? 's' : ''})
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
