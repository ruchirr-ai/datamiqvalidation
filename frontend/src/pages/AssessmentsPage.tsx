/**
 * Assessments Page
 * 
 * UI Design: Based on Connections Page design pattern
 * Purpose: List and manage BigQuery assessments
 * 
 * Features:
 * - List all assessments with status, metadata counts, and timestamps
 * - Create new assessments for BigQuery connections
 * - View detailed assessment reports
 * - Delete assessments
 * - Pagination and search
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileSearch, Database, Play, FileText, Download, Pencil, Trash2, MoreVertical, ClipboardList, TrendingUp } from 'lucide-react';
import { Button, Badge, Select } from '../components/ui';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '../components/ui/DropdownMenu';
import { CreateAssessmentModal, EditAssessmentModal, ViewLogsModal } from '../components/assessments';
import { listAssessments, deleteAssessment, runAssessment, Assessment } from '../services/assessmentsApi';
import { WorkspaceSelector } from '../components/WorkspaceSelector';
import { useWorkspace } from '../contexts/WorkspaceContext';
import { useLanguage } from '../contexts/LanguageContext';
import './AssessmentsPage.css';

export const AssessmentsPage: React.FC = () => {
  const navigate = useNavigate();
  const { selectedWorkspaceName } = useWorkspace();
  const { t } = useLanguage();
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(15);
  const [assessmentMode, setAssessmentMode] = useState<'assess' | 'analyze'>('assess');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showLogsModal, setShowLogsModal] = useState(false);
  const [selectedAssessmentId, setSelectedAssessmentId] = useState<number | null>(null);
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openMenuId, setOpenMenuId] = useState<number | null>(null);
  const [menuPosition, setMenuPosition] = useState<{ top?: number; bottom?: number; right: number }>({ right: 0 });
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const [selectedVersions, setSelectedVersions] = useState<Record<string, number>>({});

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  useEffect(() => {
    fetchAssessments();
  }, []);

  // Smart polling: only poll when there are running/pending assessments
  // Polls the API (not a page reload) every 10s, stops when all done
  useEffect(() => {
    const hasRunning = assessments.some(a =>
      a.status?.trim().toLowerCase() === 'running' || a.status?.trim().toLowerCase() === 'pending'
    );
    if (!hasRunning) return;

    const pollInterval = setInterval(async () => {
      try {
        const data = await listAssessments();
        setAssessments(data.assessments || []);
        // If none are running anymore, the next effect cycle will clear the interval
      } catch {
        // Silently ignore poll errors
      }
    }, 10000);

    return () => clearInterval(pollInterval);
  }, [assessments]);

  const fetchAssessments = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const data = await listAssessments();
      
      setAssessments(data.assessments || []);
    } catch (err: any) {
      // Handle different error types
      if (err.status === 401) {
        setError('Authentication failed. Please logout and login again.');
      } else if (err.message?.includes('Failed to fetch') || err.message?.includes('NetworkError')) {
        setError('Cannot connect to server. Please ensure the backend is running on port 8000.');
      } else {
        setError(err.detail || err.message || 'Failed to load assessments');
      }
      
      setAssessments([]);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteAssessment = async (assessmentId: number) => {
    try {
      await deleteAssessment(assessmentId);
      await fetchAssessments();
      setDeleteConfirmId(null);
    } catch (error: any) {
      setToast({ message: `Failed to delete assessment: ${error.detail || error.message}`, type: 'error' });
    }
  };

  const handleRunAssessment = async (assessmentId: number) => {
    try {
      const result = await runAssessment(assessmentId);
      setToast({ message: result.message || 'Assessment started', type: 'success' });
      // Refresh to show new versioned assessment
      await fetchAssessments();
    } catch (error: any) {
      setToast({ message: `Failed to run assessment: ${error.detail || error.message}`, type: 'error' });
    }
  };

  const handleViewLogs = (assessmentId: number) => {
    setSelectedAssessmentId(assessmentId);
    setShowLogsModal(true);
  };

  const handleEditAssessment = (assessmentId: number) => {
    setSelectedAssessmentId(assessmentId);
    setShowEditModal(true);
  };

  const handleViewReport = (assessmentId: number, assessment?: Assessment) => {
    const isAnalyze = assessment?.assessment_data?.mode === 'analyze';
    navigate(`/assessments/${assessmentId}/report${isAnalyze ? '?mode=analyze' : ''}`);
  };

  const handleDownloadReport = (assessment: Assessment) => {
    // Navigate to report page with download query param to auto-open modal
    navigate(`/assessments/${assessment.id}/report?download=true`);
  };

  const getStatusBadge = (status: string) => {
    switch (status.trim().toLowerCase()) {
      case 'completed':
        return <Badge variant="success">Completed</Badge>;
      case 'running':
        return <Badge variant="warning">Running</Badge>;
      case 'failed':
        return <Badge variant="error">Failed</Badge>;
      case 'pending':
        return <Badge>Pending</Badge>;
      default:
        return <Badge>{status}</Badge>;
    }
  };

  const formatDateTime = (dateString: string | null) => {
    if (!dateString) return 'N/A';
    try {
      // API returns UTC timestamps without Z suffix — normalize
      const normalized = dateString.endsWith('Z') ? dateString : dateString + 'Z';
      const date = new Date(normalized);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMs / 3600000);
      const diffDays = Math.floor(diffMs / 86400000);
      
      if (diffMins < 1) return 'Just now';
      if (diffMins < 60) return `${diffMins} min${diffMins > 1 ? 's' : ''} ago`;
      if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
      if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
      
      return date.toLocaleString('en-IN', {
        timeZone: 'Asia/Kolkata',
        month: 'short',
        day: 'numeric',
        year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
      });
    } catch {
      return 'Invalid date';
    }
  };

  const formatSize = (sizeMb: number) => {
    if (sizeMb < 1024) return `${sizeMb} MB`;
    const sizeGb = sizeMb / 1024;
    if (sizeGb < 1024) return `${sizeGb.toFixed(2)} GB`;
    const sizeTb = sizeGb / 1024;
    return `${sizeTb.toFixed(2)} TB`;
  };

  const totalAssessments = assessments.length;
  const totalPages = Math.ceil(totalAssessments / rowsPerPage);

  // Group assessments by name, latest version first
  const groupedAssessments = React.useMemo(() => {
    // Filter by assessment mode
    const filtered = assessments.filter(a => {
      const mode = a.assessment_data?.mode;
      if (assessmentMode === 'analyze') return mode === 'analyze';
      // 'assess' mode: show assessments with mode='assess' or no mode set
      return !mode || mode === 'assess';
    });

    const groups: Record<string, Assessment[]> = {};
    for (const a of filtered) {
      if (!groups[a.name]) groups[a.name] = [];
      groups[a.name].push(a);
    }
    // Sort each group by version desc
    Object.values(groups).forEach(g => g.sort((a, b) => (b.version || 1) - (a.version || 1)));
    // Return as array sorted by latest completion
    return Object.entries(groups)
      .map(([name, versions]) => ({ name, versions }))
      .sort((a, b) => {
        const aDate = a.versions[0]?.completed_at || a.versions[0]?.started_at || '';
        const bDate = b.versions[0]?.completed_at || b.versions[0]?.started_at || '';
        return bDate.localeCompare(aDate);
      });
  }, [assessments, assessmentMode]);

  // Get the currently selected assessment for each group
  const getSelectedAssessment = (group: { name: string; versions: Assessment[] }) => {
    const selectedId = selectedVersions[group.name];
    if (selectedId) {
      const found = group.versions.find(v => v.id === selectedId);
      if (found) return found;
    }
    return group.versions[0]; // default to latest
  };

  // Close dropdown when clicking outside
  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (openMenuId !== null && !target.closest('.assessment-menu-container')) {
        setOpenMenuId(null);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [openMenuId]);

  return (
    <div className="assessments-page">
      {/* Header - Design pattern from Connections Page */}
      <div className="assessments-header">
        <div className="assessments-title-section">
          <h1 className="assessments-title">
            <FileSearch size={20} strokeWidth={2} className="page-title-icon" />
            Assessments
            <span style={{ fontSize: 13, fontWeight: 400, color: '#6B7280', marginLeft: 8 }}>— {selectedWorkspaceName}</span>
          </h1>
          <div className="assessments-mode-toggle">
            <button
              className={`mode-toggle-btn ${assessmentMode === 'assess' ? 'active' : ''}`}
              onClick={() => setAssessmentMode('assess')}
            >
              <FileSearch size={16} /> Assess
            </button>
            <button
              className={`mode-toggle-btn ${assessmentMode === 'analyze' ? 'active' : ''}`}
              onClick={() => setAssessmentMode('analyze')}
            >
              <TrendingUp size={16} /> Analyze
            </button>
          </div>
          <p className="assessments-mode-desc">
            {assessmentMode === 'assess'
              ? 'Collect and review source database metadata — tables, views, queries, and more.'
              : 'Assess your source database and get TCO comparison, migration recommendations, and Redshift sizing.'}
          </p>
          <div className="assessments-subheader">
            <span className="assessments-count">{totalAssessments} {t('assessments.title')}</span>
            
            <div className="assessments-actions">
              <WorkspaceSelector />
              <div className="search-box">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="7" cy="7" r="5" />
                  <path d="M11 11l3 3" strokeLinecap="round" />
                </svg>
                <input
                  type="text"
                  placeholder={t('assessments.search')}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>

              <Button variant="primary" onClick={() => navigate(`/assessments/new?mode=${assessmentMode}`)}>
                {assessmentMode === 'analyze' ? '+ New Analysis' : '+ New Assessment'}
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Table - Design pattern from Connections Page */}
      <div className="assessments-table-container">
        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center' }}>
            <div className="spinner" style={{ margin: '0 auto' }}></div>
            <p style={{ marginTop: '16px', color: '#66748C' }}>{t('assessments.loading')}</p>
          </div>
        ) : error ? (
          <div style={{ padding: '40px', textAlign: 'center' }}>
            <p style={{ color: '#DC2626', marginBottom: '16px' }}>{error}</p>
            <Button variant="primary" onClick={fetchAssessments}>
              {t('common.retry')}
            </Button>
          </div>
        ) : assessments.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center' }}>
            <FileSearch size={48} style={{ color: '#9AA6B2', margin: '0 auto 16px' }} />
            <p style={{ color: '#66748C', marginBottom: '8px', fontSize: '16px', fontWeight: 500 }}>{t('assessments.noAssessments')}</p>
            <p style={{ color: '#9AA6B2', marginBottom: '16px', fontSize: '14px' }}>{t('assessments.noAssessmentsDesc')}</p>
            <Button variant="primary" onClick={() => setShowCreateModal(true)}>
              {t('assessments.createFirst')}
            </Button>
          </div>
        ) : (
          <table className="assessments-table">
            <thead>
              <tr>
                <th>{t('assessments.name')}</th>
                <th>TYPE</th>
                <th>VERSION</th>
                <th>{t('assessments.status')}</th>
                <th>{t('assessments.datasets')}</th>
                <th>{t('assessments.tables')}</th>
                <th>{t('assessments.totalSize')}</th>
                <th>{t('assessments.startedAt')}</th>
                <th>{t('assessments.completedAt')}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {groupedAssessments.map((group) => {
                const assessment = getSelectedAssessment(group);
                const hasMultipleVersions = group.versions.length > 1;
                return (
                <tr key={assessment.id}>
                  <td>
                    <div className="assessment-name-cell">
                      <FileSearch size={16} style={{ color: '#66748C', flexShrink: 0 }} />
                      {assessment.status?.trim() === 'completed' ? (
                        <span 
                          className="assessment-name assessment-name-link"
                          onClick={() => handleViewReport(assessment.id, assessment)}
                          title="Click to view report"
                        >
                          {assessment.name}
                        </span>
                      ) : (
                        <span className="assessment-name">{assessment.name}</span>
                      )}
                    </div>
                  </td>
                  <td>
                    <span style={{ 
                      fontSize: '12px', 
                      fontWeight: 500, 
                      padding: '2px 8px', 
                      borderRadius: '4px',
                      background: assessment.assessment_data?.mode === 'analyze' ? '#EFF6FF' : '#F3F4F6',
                      color: assessment.assessment_data?.mode === 'analyze' ? '#2563EB' : '#6B7280'
                    }}>
                      {assessment.assessment_data?.mode === 'analyze' ? 'Analyze' : 'Assess'}
                    </span>
                  </td>
                  <td>
                    {hasMultipleVersions ? (
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <button className="version-dropdown-trigger">
                            v{assessment.version || 1}{assessment.id === group.versions[0].id ? ' (latest)' : ''}
                            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                              <path d="M3 4l2 2 2-2" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                          </button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="start">
                          {group.versions.map(v => (
                            <DropdownMenuItem
                              key={v.id}
                              onSelect={() => setSelectedVersions(prev => ({ ...prev, [group.name]: v.id }))}
                            >
                              <span style={{ fontWeight: v.id === assessment.id ? 600 : 400 }}>
                                v{v.version || 1}{v.id === group.versions[0].id ? ' (latest)' : ''}
                              </span>
                            </DropdownMenuItem>
                          ))}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    ) : (
                      <span className="report-version-badge">v{assessment.version || 1}</span>
                    )}
                  </td>
                  <td>{getStatusBadge(assessment.status)}</td>
                  <td>{assessment.total_datasets}</td>
                  <td>{assessment.total_tables}</td>
                  <td>{formatSize(assessment.total_size_mb)}</td>
                  <td className="timestamp-cell">{formatDateTime(assessment.started_at)}</td>
                  <td className="timestamp-cell">{formatDateTime(assessment.completed_at)}</td>
                  <td>
                    <div className="assessment-menu-container">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <button className="row-menu-btn" aria-label="More options">
                            <MoreVertical size={16} />
                          </button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            disabled={assessment.status === 'running'}
                            onSelect={() => handleRunAssessment(assessment.id)}
                          >
                            <Play size={15} /> {t('assessments.run')}
                          </DropdownMenuItem>
                          <DropdownMenuItem onSelect={() => handleViewLogs(assessment.id)}>
                            <ClipboardList size={15} /> {t('assessments.viewLogs')}
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            disabled={assessment.status?.trim() !== 'completed'}
                            onSelect={() => handleViewReport(assessment.id, assessment)}
                          >
                            <FileText size={15} /> {t('assessments.viewReport')}
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            disabled={assessment.status?.trim() !== 'completed'}
                            onSelect={() => handleDownloadReport(assessment)}
                          >
                            <Download size={15} /> {t('assessments.downloadReport')}
                          </DropdownMenuItem>
                          <DropdownMenuItem onSelect={() => handleEditAssessment(assessment.id)}>
                            <Pencil size={15} /> {t('assessments.edit')}
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            className="ddm-item-danger"
                            onSelect={() => setDeleteConfirmId(assessment.id)}
                          >
                            <Trash2 size={15} /> {t('assessments.delete')}
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </td>
                </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination - Design pattern from Connections Page */}
      <div className="assessments-pagination">
        <div className="pagination-info">
          {t('assessments.showing')} {((currentPage - 1) * rowsPerPage) + 1} to {Math.min(currentPage * rowsPerPage, groupedAssessments.length)} {t('common.of')} {groupedAssessments.length}
        </div>

        <div className="pagination-controls">
          <div className="rows-per-page">
            <span>{t('assessments.rowsPerPage')}</span>
            <Select
              value={rowsPerPage}
              onChange={(value) => {
                setRowsPerPage(Number(value));
                setCurrentPage(1);
              }}
              options={[
                { value: 10, label: '10' },
                { value: 15, label: '15' },
                { value: 20, label: '20' },
                { value: 30, label: '30' },
                { value: 60, label: '60' },
                { value: 100, label: '100' },
              ]}
            />
          </div>

          <div className="pagination-buttons">
            <button
              className="pagination-btn"
              onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
              disabled={currentPage === 1}
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M10 4L6 8l4 4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            <span className="page-number">{currentPage} / {totalPages}</span>
            <button
              className="pagination-btn"
              onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
              disabled={currentPage === totalPages}
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M6 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* Create Assessment Modal */}
      <CreateAssessmentModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onSuccess={() => {
          setShowCreateModal(false);
          fetchAssessments();
        }}
        mode={assessmentMode}
      />

      {/* Edit Assessment Modal */}
      {selectedAssessmentId && (
        <EditAssessmentModal
          isOpen={showEditModal}
          assessmentId={selectedAssessmentId}
          onClose={() => {
            setShowEditModal(false);
            setSelectedAssessmentId(null);
          }}
          onSuccess={() => {
            setShowEditModal(false);
            setSelectedAssessmentId(null);
            fetchAssessments();
          }}
        />
      )}

      {/* View Logs Modal */}
      {selectedAssessmentId && (
        <ViewLogsModal
          isOpen={showLogsModal}
          assessmentId={selectedAssessmentId}
          onClose={() => {
            setShowLogsModal(false);
            setSelectedAssessmentId(null);
          }}
        />
      )}

      {/* Delete Confirmation Dialog - Design pattern from Connections Page */}
      {deleteConfirmId && (
        <div className="confirm-dialog-overlay" onClick={() => setDeleteConfirmId(null)}>
          <div className="confirm-dialog" onClick={(e) => e.stopPropagation()}>
            <h3>{t('assessments.deleteConfirm')}</h3>
            <p>{t('assessments.deleteConfirmMsg')}</p>
            <div className="confirm-actions">
              <Button variant="outline" onClick={() => setDeleteConfirmId(null)}>
                {t('assessments.cancel')}
              </Button>
              <Button 
                variant="primary" 
                onClick={() => handleDeleteAssessment(deleteConfirmId)}
                style={{ background: 'var(--color-error)', borderColor: 'var(--color-error)' }}
              >
                {t('assessments.delete')}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div
          onClick={() => setToast(null)}
          style={{
            position: 'fixed', bottom: 24, right: 24, padding: '12px 20px', borderRadius: 8,
            color: '#fff', fontSize: 14, fontWeight: 500, zIndex: 9999, cursor: 'pointer',
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            background: toast.type === 'success' ? '#16a34a' : '#dc2626',
          }}
        >
          {toast.message}
        </div>
      )}
    </div>
  );
};
