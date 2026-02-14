import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Badge, Dropdown, DropdownItem, Select, Avatar } from '../components/ui';
import { bqRedshiftApi, Migration as BQMigration } from '../services/bqRedshiftApi';
import './MigrationsPage.css';

interface Migration {
  id: string;
  name: string;
  source: string;
  destination: string;
  createdBy: string;
  status: 'completed' | 'running' | 'failed' | 'pending' | 'paused' | 'cancelled';
  lastRunAt: string;
}

export const MigrationsPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(15);
  const [showCreateMenu, setShowCreateMenu] = useState(false);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [menuPosition, setMenuPosition] = useState<{ top?: number; bottom?: number; right: number }>({ right: 0 });
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [editingMigration, setEditingMigration] = useState<Migration | null>(null);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showLogsModal, setShowLogsModal] = useState(false);
  const [logsData, setLogsData] = useState<any>(null);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [showRunOptions, setShowRunOptions] = useState(false);
  const [selectedMigrationForRun, setSelectedMigrationForRun] = useState<Migration | null>(null);
  const [migrations, setMigrations] = useState<Migration[]>([]);
  const [loading, setLoading] = useState(true);

  // Fetch migrations on mount
  useEffect(() => {
    fetchMigrations();
  }, []);

  const fetchMigrations = async () => {
    try {
      setLoading(true);
      
      const data = await bqRedshiftApi.listMigrations();
      console.log('Fetched migrations from API:', data);
      
      // Transform API data to UI format
      const transformedMigrations: Migration[] = data.map((m: BQMigration) => ({
        id: m.id.toString(),
        name: m.migration_name,
        source: m.source_connection_name || 'Unknown Connection',
        destination: m.target_connection_name || 'Unknown Connection',
        createdBy: 'System', // TODO: Get from actual user data
        status: mapStatus(m.status),
        lastRunAt: m.last_run_at || m.start_time || m.updated_at || m.created_at
      }));
      
      setMigrations(transformedMigrations);
      console.log(`✓ Loaded ${transformedMigrations.length} migrations from database`);
    } catch (err: any) {
      console.error('Failed to fetch migrations:', err);
      setMigrations([]);
      alert(`Failed to load migrations: ${err.message}\n\nPlease check the console for details.`);
    } finally {
      setLoading(false);
    }
  };

  const mapStatus = (apiStatus: string): 'completed' | 'running' | 'failed' | 'pending' | 'paused' | 'cancelled' => {
    const statusMap: Record<string, 'completed' | 'running' | 'failed' | 'pending' | 'paused' | 'cancelled'> = {
      'completed': 'completed',
      'success': 'completed',
      'running': 'running',
      'in_progress': 'running',
      'failed': 'failed',
      'error': 'failed',
      'pending': 'pending',
      'created': 'pending',
      'paused': 'paused',
      'cancelled': 'cancelled'
    };
    return statusMap[apiStatus.toLowerCase()] || 'pending';
  };

  const totalMigrations = migrations.length;
  const totalPages = Math.ceil(totalMigrations / rowsPerPage);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <Badge variant="success">Success</Badge>;
      case 'failed':
        return <Badge variant="error">Failed</Badge>;
      case 'running':
        return <Badge variant="info">Running</Badge>;
      case 'pending':
        return <Badge variant="warning">Pending</Badge>;
      case 'paused':
        return <Badge variant="warning">Paused</Badge>;
      case 'cancelled':
        return <Badge variant="error">Cancelled</Badge>;
      default:
        return <Badge>{status}</Badge>;
    }
  };

  const handleCreateMigration = () => {
    setShowCreateMenu(false);
    navigate('/migrations/create');
  };

  const handleRunMigration = async (migration: Migration) => {
    setOpenMenuId(null);
    
    try {
      console.log('Running migration:', migration.id);
      
      // Update status to running
      setMigrations(prev => prev.map(m => 
        m.id === migration.id ? { ...m, status: 'running' as const } : m
      ));
      
      // Call API to start migration
      await bqRedshiftApi.startMigration(parseInt(migration.id));
      
      alert(`Migration "${migration.name}" started successfully!\n\nThe migration is now running. You can monitor its progress in the migrations list.`);
      
      // Refresh migrations list
      await fetchMigrations();
      
    } catch (error: any) {
      console.error('Failed to run migration:', error);
      alert(`Failed to start migration: ${error.message}`);
      
      // Revert status
      setMigrations(prev => prev.map(m => 
        m.id === migration.id ? { ...m, status: 'pending' as const } : m
      ));
    }
  };

  const handleRestartMigration = async (migration: Migration) => {
    setOpenMenuId(null);
    setShowRunOptions(false);
    
    const confirmed = window.confirm(
      `Restart migration "${migration.name}" from the beginning?\n\n` +
      `This will reset the migration to pending status and clear all progress. ` +
      `Any existing data from previous runs will be preserved but the migration will start fresh.`
    );
    
    if (!confirmed) return;
    
    try {
      console.log('Restarting migration:', migration.id);
      
      // Call API to restart migration
      await bqRedshiftApi.restartMigration(parseInt(migration.id));
      
      alert(`Migration "${migration.name}" has been reset to pending status!\n\nYou can now run it again from the beginning.`);
      
      // Refresh migrations list
      await fetchMigrations();
      
    } catch (error: any) {
      console.error('Failed to restart migration:', error);
      alert(`Failed to restart migration: ${error.message}`);
    }
  };

  const handleResumeMigration = async (migration: Migration) => {
    setOpenMenuId(null);
    
    try {
      console.log('Resuming migration:', migration.id);
      
      // Update status to running
      setMigrations(prev => prev.map(m => 
        m.id === migration.id ? { ...m, status: 'running' as const } : m
      ));
      
      // Call API to resume migration
      await bqRedshiftApi.resumeMigration(parseInt(migration.id));
      
      alert(`Migration "${migration.name}" resumed successfully!\n\nThe migration is now running. You can monitor its progress in the migrations list.`);
      
      // Refresh migrations list
      await fetchMigrations();
      
    } catch (error: any) {
      console.error('Failed to resume migration:', error);
      alert(`Failed to resume migration: ${error.message}`);
      
      // Revert status
      setMigrations(prev => prev.map(m => 
        m.id === migration.id ? { ...m, status: 'paused' as const } : m
      ));
    }
  };

  const handleCancelMigration = async (migration: Migration) => {
    setOpenMenuId(null);
    
    const confirmed = window.confirm(
      `Cancel migration "${migration.name}"?\n\n` +
      `This will stop the migration process. You can resume it later if needed.`
    );
    
    if (!confirmed) return;
    
    try {
      console.log('Cancelling migration:', migration.id);
      
      // Update status to cancelled
      setMigrations(prev => prev.map(m => 
        m.id === migration.id ? { ...m, status: 'cancelled' as const } : m
      ));
      
      // Call API to cancel migration
      await bqRedshiftApi.cancelMigration(parseInt(migration.id));
      
      alert(`Migration "${migration.name}" cancelled successfully!`);
      
      // Refresh migrations list
      await fetchMigrations();
      
    } catch (error: any) {
      console.error('Failed to cancel migration:', error);
      alert(`Failed to cancel migration: ${error.message}`);
      
      // Revert status
      setMigrations(prev => prev.map(m => 
        m.id === migration.id ? { ...m, status: 'running' as const } : m
      ));
    }
  };

  const handleUpdateMigration = (migration: Migration) => {
    // Navigate to create page with migration ID for editing
    navigate(`/migrations/create?edit=${migration.id}`);
    setOpenMenuId(null);
  };

  const handleDeleteMigration = async (migrationId: string) => {
    try {
      console.log('Deleting migration:', migrationId);
      
      // Call API to delete migration
      await bqRedshiftApi.deleteMigration(parseInt(migrationId));
      
      // Remove from local state
      setMigrations(prev => prev.filter(m => m.id !== migrationId));
      
      setDeleteConfirmId(null);
      
      alert(`Migration deleted successfully!`);
    } catch (error: any) {
      console.error('Failed to delete migration:', error);
      alert(`Failed to delete migration: ${error.message}`);
    }
  };

  const handleViewLogs = async (migration: Migration) => {
    setOpenMenuId(null);
    setLoadingLogs(true);
    setShowLogsModal(true);
    setLogsData(null);
    
    try {
      console.log('Fetching logs for migration:', migration.id);
      
      // Call API to get logs
      const logs = await bqRedshiftApi.getMigrationLogs(parseInt(migration.id));
      
      setLogsData({
        migrationName: migration.name,
        migrationId: migration.id,
        ...logs
      });
      
    } catch (error: any) {
      console.error('Failed to fetch logs:', error);
      setLogsData({
        migrationName: migration.name,
        migrationId: migration.id,
        error: error.message,
        logs: []
      });
    } finally {
      setLoadingLogs(false);
    }
  };

  const handleSaveEdit = () => {
    if (editingMigration) {
      // Update local state
      setMigrations(prev => prev.map(m => 
        m.id === editingMigration.id ? editingMigration : m
      ));
      
      alert(`Migration updated: ${editingMigration.name}\n\nChanges saved successfully!`);
      setShowEditModal(false);
      setEditingMigration(null);
    }
  };

  const formatDateTime = (dateString: string | null) => {
    if (!dateString) return 'Never';
    try {
      const date = new Date(dateString);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMs / 3600000);
      const diffDays = Math.floor(diffMs / 86400000);
      
      // Show relative time for recent timestamps
      if (diffMins < 1) return 'Just now';
      if (diffMins < 60) return `${diffMins} min${diffMins > 1 ? 's' : ''} ago`;
      if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
      if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
      
      // Show formatted date for older timestamps
      return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
      });
    } catch {
      return dateString;
    }
  };

  // Close dropdown when clicking outside
  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (openMenuId !== null && !target.closest('.migration-menu-container')) {
        setOpenMenuId(null);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [openMenuId]);

  return (
    <div className="migrations-page">
      {/* Header */}
      <div className="migrations-header">
        <div className="migrations-title-section">
          <h1 className="migrations-title">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" className="page-title-icon">
              <path d="M3 10h14M14 6l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Data Migrations
          </h1>
          <div className="migrations-subheader">
            <span className="migrations-count">{totalMigrations} Migrations</span>
            
            <div className="migrations-actions">
              <div className="search-box">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="7" cy="7" r="5" />
                  <path d="M11 11l3 3" strokeLinecap="round" />
                </svg>
                <input
                  type="text"
                  placeholder="Search"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>

              <Dropdown
                trigger={
                  <Button variant="primary">
                    + New
                  </Button>
                }
                isOpen={showCreateMenu}
                onToggle={() => setShowCreateMenu(!showCreateMenu)}
                align="right"
              >
                <DropdownItem onClick={handleCreateMigration}>
                  Create
                </DropdownItem>
              </Dropdown>
            </div>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="migrations-table-container">
        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center' }}>
            <div className="spinner" style={{ margin: '0 auto' }}></div>
            <p style={{ marginTop: '16px', color: '#66748C' }}>Loading migrations...</p>
          </div>
        ) : migrations.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center' }}>
            <p style={{ color: '#66748C', marginBottom: '16px' }}>No migrations found</p>
            <Button variant="primary" onClick={handleCreateMigration}>
              Create Your First Migration
            </Button>
          </div>
        ) : (
          <table className="migrations-table">
          <thead>
            <tr>
              <th>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <span style={{ color: '#006eef' }}>NAME</span>
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="#006eef" strokeWidth="2">
                    <path d="M6 9V3M6 3L3 6M6 3l3 3" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>
              </th>
              <th>SOURCE</th>
              <th>DESTINATION</th>
              <th>CREATED BY</th>
              <th>STATUS</th>
              <th>LAST RUN AT</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {migrations.map((migration) => (
              <tr key={migration.id}>
                <td>
                  <span className="name-cell">{migration.name}</span>
                </td>
                <td>
                  <span>{migration.source}</span>
                </td>
                <td>
                  <span>{migration.destination}</span>
                </td>
                <td>
                  <div className="created-by-cell">
                    <Avatar name={migration.createdBy} size="sm" />
                    <span>{migration.createdBy}</span>
                  </div>
                </td>
                <td>{getStatusBadge(migration.status)}</td>
                <td className="timestamp-cell">{formatDateTime(migration.lastRunAt)}</td>
                <td>
                  <div className="migration-menu-container">
                    <button 
                      className="row-menu-btn" 
                      aria-label="More options"
                      onClick={(e) => {
                        const button = e.currentTarget;
                        const rect = button.getBoundingClientRect();
                        const windowHeight = window.innerHeight;
                        const menuHeight = 180; // Approximate menu height
                        
                        // Check if there's enough space below
                        const spaceBelow = windowHeight - rect.bottom;
                        const shouldOpenUpward = spaceBelow < menuHeight;
                        
                        // Calculate position
                        const position = {
                          right: window.innerWidth - rect.right,
                          ...(shouldOpenUpward 
                            ? { bottom: windowHeight - rect.top + 4 }
                            : { top: rect.bottom + 4 }
                          )
                        };
                        
                        console.log('Migration dropdown:', { 
                          rect, 
                          windowHeight, 
                          spaceBelow, 
                          shouldOpenUpward,
                          position
                        });
                        
                        setMenuPosition(position);
                        setOpenMenuId(openMenuId === migration.id ? null : migration.id);
                      }}
                    >
                      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                        <circle cx="8" cy="3" r="1.5" />
                        <circle cx="8" cy="8" r="1.5" />
                        <circle cx="8" cy="13" r="1.5" />
                      </svg>
                    </button>
                    
                    {openMenuId === migration.id && (
                      <div 
                        className={`migration-dropdown-menu ${menuPosition.bottom ? 'open-upward' : ''}`}
                        style={{
                          top: menuPosition.top ? `${menuPosition.top}px` : 'auto',
                          bottom: menuPosition.bottom ? `${menuPosition.bottom}px` : 'auto',
                          right: `${menuPosition.right}px`
                        }}
                      >
                        {migration.status === 'pending' && (
                          <button
                            className="dropdown-menu-item"
                            onClick={() => handleRunMigration(migration)}
                          >
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                              <path d="M5 3l8 5-8 5V3z" fill="currentColor" />
                            </svg>
                            Run Migration
                          </button>
                        )}
                        {(migration.status === 'paused' || migration.status === 'failed' || migration.status === 'cancelled' || migration.status === 'completed') && (
                          <button
                            className="dropdown-menu-item"
                            onClick={() => {
                              setSelectedMigrationForRun(migration);
                              setShowRunOptions(true);
                              setOpenMenuId(null);
                            }}
                          >
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                              <path d="M5 3l8 5-8 5V3z" fill="currentColor" />
                            </svg>
                            Run Migration
                          </button>
                        )}
                        {migration.status === 'running' && (
                          <button
                            className="dropdown-menu-item"
                            onClick={() => handleCancelMigration(migration)}
                          >
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                              <circle cx="8" cy="8" r="6" />
                              <path d="M6 6l4 4M10 6l-4 4" strokeLinecap="round" />
                            </svg>
                            Cancel Migration
                          </button>
                        )}
                        <button
                          className="dropdown-menu-item"
                          onClick={() => handleViewLogs(migration)}
                        >
                          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                            <path d="M3 4h10M3 8h10M3 12h6" strokeLinecap="round" strokeLinejoin="round" />
                          </svg>
                          View Logs
                        </button>
                        <button
                          className="dropdown-menu-item"
                          onClick={() => handleUpdateMigration(migration)}
                        >
                          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                            <path d="M11.5 2.5l2 2L6 12H4v-2l7.5-7.5z" strokeLinecap="round" strokeLinejoin="round" />
                          </svg>
                          Edit Migration
                        </button>
                        <div className="dropdown-divider" />
                        <button
                          className="dropdown-menu-item dropdown-menu-item-danger"
                          onClick={() => {
                            setDeleteConfirmId(migration.id);
                            setOpenMenuId(null);
                          }}
                        >
                          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                            <path d="M3 4h10M5 4V3a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v1M6 7v4M10 7v4M4 4h8v9a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V4z" strokeLinecap="round" strokeLinejoin="round" />
                          </svg>
                          Delete Migration
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

      {/* Pagination */}
      <div className="migrations-pagination">
        <div className="pagination-info">
          Showing {((currentPage - 1) * rowsPerPage) + 1} to {Math.min(currentPage * rowsPerPage, totalMigrations)} of {totalMigrations} migrations
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

      {/* Edit Migration Modal */}
      {showEditModal && editingMigration && (
        <div className="modal-overlay" onClick={() => setShowEditModal(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Update Migration</h3>
              <button className="modal-close" onClick={() => setShowEditModal(false)}>
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M5 5l10 10M15 5L5 15" strokeLinecap="round" />
                </svg>
              </button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>Migration Name</label>
                <input
                  type="text"
                  className="form-input"
                  value={editingMigration.name}
                  onChange={(e) => setEditingMigration({...editingMigration, name: e.target.value})}
                />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Source</label>
                  <input
                    type="text"
                    className="form-input"
                    value={editingMigration.source}
                    onChange={(e) => setEditingMigration({...editingMigration, source: e.target.value})}
                  />
                </div>
                <div className="form-group">
                  <label>Destination</label>
                  <input
                    type="text"
                    className="form-input"
                    value={editingMigration.destination}
                    onChange={(e) => setEditingMigration({...editingMigration, destination: e.target.value})}
                  />
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <Button variant="outline" onClick={() => setShowEditModal(false)}>
                Cancel
              </Button>
              <Button variant="primary" onClick={handleSaveEdit}>
                Save Changes
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      {deleteConfirmId && (
        <div className="confirm-dialog-overlay" onClick={() => setDeleteConfirmId(null)}>
          <div className="confirm-dialog" onClick={(e) => e.stopPropagation()}>
            <h3>Delete Migration</h3>
            <p>Are you sure you want to delete this migration? This action cannot be undone and will stop any running migration processes.</p>
            <div className="confirm-actions">
              <Button variant="outline" onClick={() => setDeleteConfirmId(null)}>
                Cancel
              </Button>
              <Button 
                variant="primary" 
                onClick={() => handleDeleteMigration(deleteConfirmId)}
                style={{ background: 'var(--color-error)', borderColor: 'var(--color-error)' }}
              >
                Delete Migration
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Logs Modal */}
      {showLogsModal && (
        <div className="modal-overlay" onClick={() => setShowLogsModal(false)}>
          <div className="modal-dialog logs-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Migration Logs</h3>
              <button className="modal-close" onClick={() => setShowLogsModal(false)}>
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M6 6l8 8M14 6l-8 8" strokeLinecap="round" />
                </svg>
              </button>
            </div>
            <div className="modal-body logs-modal-body">
              {loadingLogs ? (
                <div className="logs-loading">
                  <div className="spinner"></div>
                  <p>Loading logs...</p>
                </div>
              ) : logsData?.error ? (
                <div className="logs-error">
                  <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="var(--color-error)" strokeWidth="2">
                    <circle cx="24" cy="24" r="20" />
                    <path d="M18 18l12 12M30 18l-12 12" strokeLinecap="round" />
                  </svg>
                  <h4>Failed to Load Logs</h4>
                  <p>{logsData.error}</p>
                </div>
              ) : logsData?.logs && logsData.logs.length > 0 ? (
                <div className="logs-container">
                  <div className="logs-header-info">
                    <p><strong>Migration:</strong> {logsData.migrationName}</p>
                  </div>
                  <div className="logs-list">
                    {logsData.logs.map((log: any, index: number) => (
                      <div key={index} className={`log-entry log-level-${log.log_level?.toLowerCase()}`}>
                        <div className="log-header">
                          <span className={`log-level ${log.log_level?.toLowerCase()}`}>
                            {log.log_level}
                          </span>
                          <span className="log-stage">{log.stage}</span>
                          <span className="log-time">
                            {new Date(log.created_at).toLocaleString()}
                          </span>
                        </div>
                        <div className="log-message">{log.message}</div>
                        {log.error_code && (
                          <div className="log-error-code">Error Code: {log.error_code}</div>
                        )}
                        {log.stack_trace && (
                          <details className="log-stack-trace">
                            <summary>Stack Trace</summary>
                            <pre>{log.stack_trace}</pre>
                          </details>
                        )}
                        {log.log_metadata && Object.keys(log.log_metadata).length > 0 && (
                          <details className="log-metadata">
                            <summary>Metadata</summary>
                            <pre>{JSON.stringify(log.log_metadata, null, 2)}</pre>
                          </details>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="logs-empty">
                  <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="var(--color-text-secondary)" strokeWidth="2">
                    <path d="M12 12h24M12 20h24M12 28h16" strokeLinecap="round" />
                  </svg>
                  <h4>No Logs Available</h4>
                  <p>This migration hasn't generated any logs yet.</p>
                </div>
              )}
            </div>
            <div className="modal-footer">
              <Button variant="outline" onClick={() => setShowLogsModal(false)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Run Options Modal */}
      {showRunOptions && selectedMigrationForRun && (
        <div className="modal-overlay" onClick={() => setShowRunOptions(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '450px' }}>
            <div className="modal-header">
              <h3>Run Migration</h3>
              <button className="modal-close" onClick={() => setShowRunOptions(false)}>
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M6 6l8 8M14 6l-8 8" strokeLinecap="round" />
                </svg>
              </button>
            </div>
            <div className="modal-body">
              <p style={{ marginBottom: '20px', color: 'var(--color-text-secondary)' }}>
                Choose how to run the migration "{selectedMigrationForRun.name}":
              </p>
              
              <button
                className="run-option-button"
                onClick={() => {
                  handleResumeMigration(selectedMigrationForRun);
                  setShowRunOptions(false);
                }}
              >
                <div className="run-option-icon">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M7 4l12 8-12 8V4z" fill="currentColor" />
                  </svg>
                </div>
                <div className="run-option-content">
                  <div className="run-option-title">Resume</div>
                  <div className="run-option-description">
                    Continue from where it left off. Preserves existing progress and checkpoints.
                  </div>
                </div>
              </button>

              <button
                className="run-option-button"
                onClick={() => {
                  handleRestartMigration(selectedMigrationForRun);
                  setShowRunOptions(false);
                }}
              >
                <div className="run-option-icon">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
                    <path d="M21 3v5h-5" />
                    <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
                    <path d="M3 21v-5h5" />
                  </svg>
                </div>
                <div className="run-option-content">
                  <div className="run-option-title">Restart</div>
                  <div className="run-option-description">
                    Start fresh from the beginning. Resets migration to pending status.
                  </div>
                </div>
              </button>
            </div>
            <div className="modal-footer">
              <Button variant="outline" onClick={() => setShowRunOptions(false)}>
                Cancel
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
