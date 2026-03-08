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
import { FileSearch, Database } from 'lucide-react';
import { Button, Badge, Select } from '../components/ui';
import { CreateAssessmentModal, EditAssessmentModal, ViewLogsModal } from '../components/assessments';
import { listAssessments, deleteAssessment, runAssessment, Assessment } from '../services/assessmentsApi';
import './AssessmentsPage.css';

export const AssessmentsPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(15);
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

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  useEffect(() => {
    fetchAssessments();
  }, []);

  const fetchAssessments = async () => {
    try {
      setLoading(true);
      setError(null);
      
      console.log('Fetching assessments...');
      const data = await listAssessments();
      console.log('Assessments data received:', data);
      
      setAssessments(data.assessments || []);
    } catch (err: any) {
      console.error('Failed to fetch assessments:', err);
      
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
      console.error('Failed to delete assessment:', error);
      setToast({ message: `Failed to delete assessment: ${error.detail || error.message}`, type: 'error' });
    }
  };

  const handleRunAssessment = async (assessmentId: number) => {
    try {
      await runAssessment(assessmentId);
      setToast({ message: 'Assessment started', type: 'success' });
      // Immediately refresh to show 'running' status
      await fetchAssessments();
      
      // Poll for status updates every 3 seconds
      const pollInterval = setInterval(async () => {
        await fetchAssessments();
      }, 3000);
      
      // Stop polling after 5 minutes (adjust as needed)
      setTimeout(() => {
        clearInterval(pollInterval);
      }, 300000);
      
    } catch (error: any) {
      console.error('Failed to run assessment:', error);
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

  const handleViewReport = (assessmentId: number) => {
    // Navigate to report view using React Router
    navigate(`/assessments/${assessmentId}/report`);
  };

  const getStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
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
      const date = new Date(dateString);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMs / 3600000);
      const diffDays = Math.floor(diffMs / 86400000);
      
      if (diffMins < 1) return 'Just now';
      if (diffMins < 60) return `${diffMins} min${diffMins > 1 ? 's' : ''} ago`;
      if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
      if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
      
      return date.toLocaleString('en-US', {
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
          </h1>
          <div className="assessments-subheader">
            <span className="assessments-count">{totalAssessments} Assessments</span>
            
            <div className="assessments-actions">
              <div className="search-box">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="7" cy="7" r="5" />
                  <path d="M11 11l3 3" strokeLinecap="round" />
                </svg>
                <input
                  type="text"
                  placeholder="Search assessments"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>

              <Button variant="primary" onClick={() => setShowCreateModal(true)}>
                + New
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
            <p style={{ marginTop: '16px', color: '#66748C' }}>Loading assessments...</p>
          </div>
        ) : error ? (
          <div style={{ padding: '40px', textAlign: 'center' }}>
            <p style={{ color: '#DC2626', marginBottom: '16px' }}>{error}</p>
            <Button variant="primary" onClick={fetchAssessments}>
              Retry
            </Button>
          </div>
        ) : assessments.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center' }}>
            <FileSearch size={48} style={{ color: '#9AA6B2', margin: '0 auto 16px' }} />
            <p style={{ color: '#66748C', marginBottom: '8px', fontSize: '16px', fontWeight: 500 }}>No assessments yet</p>
            <p style={{ color: '#9AA6B2', marginBottom: '16px', fontSize: '14px' }}>Create your first BigQuery assessment to analyze your data</p>
            <Button variant="primary" onClick={() => setShowCreateModal(true)}>
              Create Your First Assessment
            </Button>
          </div>
        ) : (
          <table className="assessments-table">
            <thead>
              <tr>
                <th>NAME</th>
                <th>STATUS</th>
                <th>DATASETS</th>
                <th>TABLES</th>
                <th>TOTAL SIZE</th>
                <th>STARTED AT</th>
                <th>COMPLETED AT</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {assessments.map((assessment) => (
                <tr key={assessment.id}>
                  <td>
                    <div className="assessment-name-cell">
                      <FileSearch size={16} style={{ color: '#66748C', flexShrink: 0 }} />
                      {assessment.status === 'completed' ? (
                        <span 
                          className="assessment-name assessment-name-link"
                          onClick={() => handleViewReport(assessment.id)}
                          title="Click to view report"
                        >
                          {assessment.name}
                        </span>
                      ) : (
                        <span className="assessment-name">{assessment.name}</span>
                      )}
                    </div>
                  </td>
                  <td>{getStatusBadge(assessment.status)}</td>
                  <td>{assessment.total_datasets}</td>
                  <td>{assessment.total_tables}</td>
                  <td>{formatSize(assessment.total_size_mb)}</td>
                  <td className="timestamp-cell">{formatDateTime(assessment.started_at)}</td>
                  <td className="timestamp-cell">{formatDateTime(assessment.completed_at)}</td>
                  <td>
                    <div className="assessment-menu-container">
                      <button 
                        className="row-menu-btn" 
                        aria-label="More options"
                        onClick={(e) => {
                          const button = e.currentTarget;
                          const rect = button.getBoundingClientRect();
                          const windowHeight = window.innerHeight;
                          const menuHeight = 120;
                          
                          const spaceBelow = windowHeight - rect.bottom;
                          const shouldOpenUpward = spaceBelow < menuHeight;
                          
                          const position = {
                            right: window.innerWidth - rect.right,
                            ...(shouldOpenUpward 
                              ? { bottom: windowHeight - rect.top + 4 }
                              : { top: rect.bottom + 4 }
                            )
                          };
                          
                          setMenuPosition(position);
                          setOpenMenuId(openMenuId === assessment.id ? null : assessment.id);
                        }}
                      >
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                          <circle cx="8" cy="3" r="1.5" />
                          <circle cx="8" cy="8" r="1.5" />
                          <circle cx="8" cy="13" r="1.5" />
                        </svg>
                      </button>
                      
                      {openMenuId === assessment.id && (
                        <div 
                          className={`assessment-dropdown-menu ${menuPosition.bottom ? 'open-upward' : ''}`}
                          style={{
                            top: menuPosition.top ? `${menuPosition.top}px` : 'auto',
                            bottom: menuPosition.bottom ? `${menuPosition.bottom}px` : 'auto',
                            right: `${menuPosition.right}px`
                          }}
                        >
                          <button
                            className="dropdown-menu-item"
                            onClick={() => {
                              handleRunAssessment(assessment.id);
                              setOpenMenuId(null);
                            }}
                            disabled={assessment.status === 'running'}
                          >
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                              <path d="M5 3l8 5-8 5V3z" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                            Run Assessment
                          </button>
                          <button
                            className="dropdown-menu-item"
                            onClick={() => {
                              handleViewLogs(assessment.id);
                              setOpenMenuId(null);
                            }}
                          >
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                              <path d="M2 4h12M2 8h12M2 12h8" strokeLinecap="round" />
                            </svg>
                            View Logs
                          </button>
                          <button
                            className="dropdown-menu-item"
                            onClick={() => {
                              handleViewReport(assessment.id);
                              setOpenMenuId(null);
                            }}
                            disabled={assessment.status !== 'completed'}
                          >
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                              <path d="M9 2H4a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V7M9 2l4 4M9 2v4h4" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                            View Report
                          </button>
                          <button
                            className="dropdown-menu-item"
                            onClick={() => {
                              handleEditAssessment(assessment.id);
                              setOpenMenuId(null);
                            }}
                          >
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                              <path d="M11 2l3 3-9 9H2v-3l9-9z" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                            Edit Assessment
                          </button>
                          <div className="dropdown-divider" />
                          <button
                            className="dropdown-menu-item dropdown-menu-item-danger"
                            onClick={() => {
                              setDeleteConfirmId(assessment.id);
                              setOpenMenuId(null);
                            }}
                          >
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                              <path d="M3 4h10M5 4V3a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v1M6 7v4M10 7v4M4 4h8v9a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V4z" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                            Delete Assessment
                          </button>
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination - Design pattern from Connections Page */}
      <div className="assessments-pagination">
        <div className="pagination-info">
          Showing {((currentPage - 1) * rowsPerPage) + 1} to {Math.min(currentPage * rowsPerPage, totalAssessments)} of {totalAssessments} assessments
        </div>

        <div className="pagination-controls">
          <div className="rows-per-page">
            <span>Rows per page:</span>
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
            <h3>Delete Assessment</h3>
            <p>Are you sure you want to delete this assessment? This action cannot be undone.</p>
            <div className="confirm-actions">
              <Button variant="outline" onClick={() => setDeleteConfirmId(null)}>
                Cancel
              </Button>
              <Button 
                variant="primary" 
                onClick={() => handleDeleteAssessment(deleteConfirmId)}
                style={{ background: 'var(--color-error)', borderColor: 'var(--color-error)' }}
              >
                Delete Assessment
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
