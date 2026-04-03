import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Eye, Download, FileText, Database } from 'lucide-react';
import { listAssessments, Assessment } from '../../services/assessmentsApi';
import './AssessmentsPage.css';
import './AssessmentReportsPage.css';

export const AssessmentReportsPage: React.FC = () => {
  const navigate = useNavigate();
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [loading, setLoading] = useState(true);
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

  const handleDownload = async (assessment: Assessment) => {
    // Navigate to report page where the download modal is available
    navigate(`/assessments/${assessment.id}/report`);
  };

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
          <div className="reports-loading">
            Loading reports...
          </div>
        ) : assessments.length === 0 ? (
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
                  <th>DATABASE</th>
                  <th>TABLES</th>
                  <th>SIZE</th>
                  <th>COMPLETED AT</th>
                  <th>DURATION</th>
                  <th>ACTIONS</th>
                </tr>
              </thead>
              <tbody>
                {assessments.map(a => (
                  <tr key={a.id}>
                    <td>
                      <div className="report-name-cell">
                        <FileText size={16} style={{ color: '#66748C', flexShrink: 0 }} />
                        <span className="report-name">{a.name}</span>
                      </div>
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
                        <button
                          className="report-action-btn report-action-download"
                          onClick={() => handleDownload(a)}
                          title="Download PDF"
                        >
                          <Download size={15} />
                          PDF
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="reports-footer">
              Showing {assessments.length} report{assessments.length !== 1 ? 's' : ''}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
