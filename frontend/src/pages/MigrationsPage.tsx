import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Badge, Dropdown, DropdownItem, Select, Avatar } from '../components/ui';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '../components/ui/DropdownMenu';
import { Play, XCircle, ClipboardList, Pencil, Trash2, MoreVertical } from 'lucide-react';
import { bqRedshiftApi, Migration as BQMigration } from '../services/bqRedshiftApi';
import { clickhouseMigrationApi } from '../services/clickhouseMigrationApi';
import { WorkspaceSelector } from '../components/WorkspaceSelector';
import { useWorkspace } from '../contexts/WorkspaceContext';
import { useLanguage } from '../contexts/LanguageContext';
import './MigrationsPage.css';

interface Migration {
  id: string;
  name: string;
  source: string;
  destination: string;
  createdBy: string;
  status: 'completed' | 'running' | 'failed' | 'pending' | 'paused' | 'cancelled' | 'ready';
  lastRunAt: string;
}

export const MigrationsPage: React.FC = () => {
  const navigate = useNavigate();
  const { selectedWorkspaceName } = useWorkspace();
  const { t } = useLanguage();
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(15);
  const [showCreateMenu, setShowCreateMenu] = useState(false);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [restartConfirmMigration, setRestartConfirmMigration] = useState<Migration | null>(null);
  const [editingMigration, setEditingMigration] = useState<Migration | null>(null);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showLogsModal, setShowLogsModal] = useState(false);
  const [logsData, setLogsData] = useState<any>(null);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [showRunOptions, setShowRunOptions] = useState(false);
  const [selectedMigrationForRun, setSelectedMigrationForRun] = useState<Migration | null>(null);
  const [migrations, setMigrations] = useState<Migration[]>([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);

  // Auto-dismiss toast after 4 seconds
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  // Fetch migrations on mount
  useEffect(() => {
    fetchMigrations();
  }, []);

  const fetchMigrations = async () => {
    try {
      setLoading(true);
      
      // Fetch both BQ-Redshift and ClickHouse migrations
      const [bqData, chData] = await Promise.allSettled([
        bqRedshiftApi.listMigrations(),
        clickhouseMigrationApi.listMigrations(),
      ]);
      
      // Transform BQ-Redshift migrations
      const bqMigrations: Migration[] = bqData.status === 'fulfilled' 
        ? bqData.value.map((m: BQMigration) => ({
            id: m.id.toString(),
            name: m.migration_name,
            source: m.source_connection_name || 'Unknown Connection',
            destination: m.target_connection_name || 'Unknown Connection',
            createdBy: 'System',
            status: mapStatus(m.status),
            lastRunAt: m.last_run_at || m.start_time || m.updated_at || m.created_at
          }))
        : [];
      
      // Transform ClickHouse migrations
      const chMigrations: Migration[] = chData.status === 'fulfilled'
        ? (chData.value.migrations || []).map((m: any) => ({
            id: `ch-${m.migration_id}`,
            name: m.name,
            source: 'BigQuery',
            destination: 'ClickHouse',
            createdBy: 'System',
            status: mapStatus(m.status),
            lastRunAt: m.completed_at || m.started_at || ''
          }))
        : [];
      
      setMigrations([...bqMigrations, ...chMigrations]);
    } catch (err: any) {
      setMigrations([]);
      setToast({ message: `Failed to load migrations: ${err.message}`, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const mapStatus = (apiStatus: string): 'completed' | 'running' | 'failed' | 'pending' | 'paused' | 'cancelled' | 'ready' => {
    const statusMap: Record<string, 'completed' | 'running' | 'failed' | 'pending' | 'paused' | 'cancelled' | 'ready'> = {
      'completed': 'completed',
      'success': 'completed',
      'running': 'running',
      'in_progress': 'running',
      'failed': 'failed',
      'error': 'failed',
      'pending': 'pending',
      'created': 'pending',
      'ready': 'ready',
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
      case 'ready':
        return <Badge variant="success">Ready</Badge>;
      case 'scheduled':
        return <Badge variant="info">Scheduled</Badge>;
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

  const handleCreateIcebergMigration = () => {
    setShowCreateMenu(false);
    navigate('/migrations/bq-iceberg');
  };

  const handleRunMigration = async (migration: Migration) => {
    setOpenMenuId(null);
    
    try {
      
      // Update status to running
      setMigrations(prev => prev.map(m => 
        m.id === migration.id ? { ...m, status: 'running' as const } : m
      ));
      
      // Call API to start migration
      await bqRedshiftApi.startMigration(parseInt(migration.id));
      
      setToast({ message: `Migration "${migration.name}" started`, type: 'success' });
      
      // Refresh migrations list
      await fetchMigrations();
      
    } catch (error: any) {
      setToast({ message: `Failed to start migration: ${error.message}`, type: 'error' });
      
      // Revert status
      setMigrations(prev => prev.map(m => 
        m.id === migration.id ? { ...m, status: migration.status } : m
      ));
    }
  };

  const handleRestartMigration = async (migration: Migration) => {
    setOpenMenuId(null);
    setShowRunOptions(false);
    
    // Show confirmation dialog instead of window.confirm
    setRestartConfirmMigration(migration);
  };

  const confirmRestartMigration = async () => {
    const migration = restartConfirmMigration;
    if (!migration) return;
    
    setRestartConfirmMigration(null);
    
    try {
      
      // Optimistically update status to running
      setMigrations(prev => prev.map(m => 
        m.id === migration.id ? { ...m, status: 'running' as const } : m
      ));
      
      // Call API to restart migration
      await bqRedshiftApi.restartMigration(parseInt(migration.id));
      
      setToast({ message: `Migration "${migration.name}" restarted and running`, type: 'success' });
      
      // Refresh migrations list
      await fetchMigrations();
      
    } catch (error: any) {
      setToast({ message: `Failed to restart migration: ${error.message}`, type: 'error' });
      
      // Revert status
      setMigrations(prev => prev.map(m => 
        m.id === migration.id ? { ...m, status: migration.status } : m
      ));
    }
  };

  const handleResumeMigration = async (migration: Migration) => {
    setOpenMenuId(null);
    
    try {
      
      // Update status to running
      setMigrations(prev => prev.map(m => 
        m.id === migration.id ? { ...m, status: 'running' as const } : m
      ));
      
      // Call API to resume migration
      await bqRedshiftApi.resumeMigration(parseInt(migration.id));
      
      setToast({ message: `Migration "${migration.name}" resumed`, type: 'success' });
      
      // Refresh migrations list
      await fetchMigrations();
      
    } catch (error: any) {
      setToast({ message: `Failed to resume migration: ${error.message}`, type: 'error' });
      
      // Revert status
      setMigrations(prev => prev.map(m => 
        m.id === migration.id ? { ...m, status: 'paused' as const } : m
      ));
    }
  };

  const [cancelConfirmMigration, setCancelConfirmMigration] = useState<Migration | null>(null);

  const handleCancelMigration = async (migration: Migration) => {
    setOpenMenuId(null);
    setCancelConfirmMigration(migration);
  };

  const confirmCancelMigration = async () => {
    const migration = cancelConfirmMigration;
    if (!migration) return;
    
    setCancelConfirmMigration(null);
    
    try {
      
      // Update status to cancelled
      setMigrations(prev => prev.map(m => 
        m.id === migration.id ? { ...m, status: 'cancelled' as const } : m
      ));
      
      // Call API to cancel migration
      await bqRedshiftApi.cancelMigration(parseInt(migration.id));
      
      setToast({ message: `Migration "${migration.name}" cancelled`, type: 'info' });
      
      // Refresh migrations list
      await fetchMigrations();
      
    } catch (error: any) {
      setToast({ message: `Failed to cancel migration: ${error.message}`, type: 'error' });
      
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
      
      // Call API to delete migration
      await bqRedshiftApi.deleteMigration(parseInt(migrationId));
      
      // Remove from local state
      setMigrations(prev => prev.filter(m => m.id !== migrationId));
      
      setDeleteConfirmId(null);
      
      setToast({ message: 'Migration deleted', type: 'success' });
    } catch (error: any) {
      setToast({ message: `Failed to delete migration: ${error.message}`, type: 'error' });
    }
  };

  const handleViewLogs = async (migration: Migration) => {
    setOpenMenuId(null);
    setLoadingLogs(true);
    setShowLogsModal(true);
    setLogsData(null);
    
    try {
      let logs: any;
      
      // Route to appropriate API based on migration type
      if (migration.id.startsWith('ch-')) {
        // ClickHouse migration
        const chId = migration.id.replace('ch-', '');
        const result = await clickhouseMigrationApi.getLogs(chId);
        logs = { logs: result.logs || [] };
      } else {
        // BQ-Redshift migration
        logs = await bqRedshiftApi.getMigrationLogs(parseInt(migration.id));
      }
      
      setLogsData({
        migrationName: migration.name,
        migrationId: migration.id,
        ...logs
      });
      
    } catch (error: any) {
      setLogsData({
        migrationName: migration.name,
        migrationId: migration.id,
        error: error.message || 'Failed to load logs',
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
      
      setToast({ message: `Migration "${editingMigration.name}" updated`, type: 'success' });
      setShowEditModal(false);
      setEditingMigration(null);
    }
  };

  const formatDateTime = (dateString: string | null) => {
    if (!dateString) return 'Never';
    try {
      // Backend returns UTC timestamps without 'Z' suffix — append it if missing
      let normalized = dateString;
      if (!normalized.endsWith('Z') && !normalized.includes('+') && !normalized.includes('T')) {
        normalized = normalized + 'Z';
      } else if (normalized.includes('T') && !normalized.endsWith('Z') && !normalized.includes('+')) {
        normalized = normalized + 'Z';
      }
      const date = new Date(normalized);
      if (isNaN(date.getTime())) return dateString;
      
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
      
      // Show formatted date for older timestamps (in IST)
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
            <span style={{ fontSize: 13, fontWeight: 400, color: '#6B7280', marginLeft: 8 }}>— {selectedWorkspaceName}</span>
          </h1>
          <div className="migrations-subheader">
            <span className="migrations-count">{totalMigrations} {t('migrations.count')}</span>
            
            <div className="migrations-actions">
              <WorkspaceSelector />
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
                  BQ → Redshift
                </DropdownItem>
                <DropdownItem onClick={handleCreateIcebergMigration}>
                  BQ → Iceberg
                </DropdownItem>
              </Dropdown>
            </div>
          </div>
        </div>
      </div>

      {/* Migration Type Hub */}
      <div className="migrations-hub">
        <button className="migrations-hub__card" onClick={() => navigate('/migrations/bq-redshift')}>
          <div className="migrations-hub__card-icon">
            <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
              <rect x="2" y="5" width="7" height="12" rx="2"/>
              <rect x="13" y="5" width="7" height="12" rx="2"/>
              <path d="M9 11h4M11 9l2 2-2 2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <div className="migrations-hub__card-body">
            <span className="migrations-hub__card-title">BigQuery → Redshift</span>
            <span className="migrations-hub__card-desc">GCS/S3 transfer with checkpointing</span>
          </div>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <path d="M5 3l4 4-4 4" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
        <button className="migrations-hub__card migrations-hub__card--iceberg" onClick={() => navigate('/migrations/bq-iceberg')}>
          <div className="migrations-hub__card-icon">
            <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
              <path d="M4 18l7-14 7 14H4z" strokeLinejoin="round"/>
              <path d="M4 18h14M7 12h8" strokeLinecap="round"/>
            </svg>
          </div>
          <div className="migrations-hub__card-body">
            <span className="migrations-hub__card-title">BigQuery → Iceberg</span>
            <span className="migrations-hub__card-desc">Apache Iceberg on S3 or S3 Tables</span>
          </div>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <path d="M5 3l4 4-4 4" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
        <button className="migrations-hub__card migrations-hub__card--clickhouse" onClick={() => navigate('/migrations/create')}>
          <div className="migrations-hub__card-icon">
            <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
              <rect x="3" y="3" width="3" height="16" rx="1"/>
              <rect x="8" y="6" width="3" height="13" rx="1"/>
              <rect x="13" y="9" width="3" height="10" rx="1"/>
              <rect x="18" y="3" width="1.5" height="16" rx="0.75"/>
            </svg>
          </div>
          <div className="migrations-hub__card-body">
            <span className="migrations-hub__card-title">BigQuery → ClickHouse</span>
            <span className="migrations-hub__card-desc">GCS export + ClickHouse direct load</span>
          </div>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <path d="M5 3l4 4-4 4" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
      </div>

      {/* Table */}
      <div className="migrations-table-container">
        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center' }}>
            <div className="spinner" style={{ margin: '0 auto' }}></div>
            <p style={{ marginTop: '16px', color: '#66748C' }}>{t('migrations.loading')}</p>
          </div>
        ) : migrations.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center' }}>
            <p style={{ color: '#66748C', marginBottom: '16px' }}>{t('migrations.noMigrations')}</p>
            <Button variant="primary" onClick={handleCreateMigration}>
              {t('migrations.createFirst')}
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
              <th>{t('migrations.source')}</th>
              <th>{t('migrations.destination')}</th>
              <th>{t('migrations.createdBy')}</th>
              <th>{t('migrations.status')}</th>
              <th>{t('migrations.lastRunAt')}</th>
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
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button className="row-menu-btn" aria-label="More options">
                          <MoreVertical size={16} />
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        {(migration.status === 'pending' || migration.status === 'ready') && (
                          <DropdownMenuItem onSelect={() => handleRunMigration(migration)}>
                            <Play size={15} /> Run Migration
                          </DropdownMenuItem>
                        )}
                        {(migration.status === 'paused' || migration.status === 'failed' || migration.status === 'cancelled' || migration.status === 'completed') && (
                          <DropdownMenuItem onSelect={() => {
                            setSelectedMigrationForRun(migration);
                            setShowRunOptions(true);
                          }}>
                            <Play size={15} /> Run Migration
                          </DropdownMenuItem>
                        )}
                        {migration.status === 'running' && (
                          <DropdownMenuItem onSelect={() => handleCancelMigration(migration)}>
                            <XCircle size={15} /> Cancel Migration
                          </DropdownMenuItem>
                        )}
                        <DropdownMenuItem onSelect={() => handleViewLogs(migration)}>
                          <ClipboardList size={15} /> View Logs
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => handleUpdateMigration(migration)}>
                          <Pencil size={15} /> Edit Migration
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          className="ddm-item-danger"
                          onSelect={() => setDeleteConfirmId(migration.id)}
                        >
                          <Trash2 size={15} /> Delete Migration
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
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

      {/* Restart Confirmation Dialog */}
      {restartConfirmMigration && (
        <div className="confirm-dialog-overlay" onClick={() => setRestartConfirmMigration(null)}>
          <div className="confirm-dialog" onClick={(e) => e.stopPropagation()}>
            <h3>Restart Migration</h3>
            <p>Restart "{restartConfirmMigration.name}" from the beginning? This will clear all progress and start fresh. Existing data from previous runs will be preserved.</p>
            <div className="confirm-actions">
              <Button variant="outline" onClick={() => setRestartConfirmMigration(null)}>
                Cancel
              </Button>
              <Button 
                variant="primary" 
                onClick={confirmRestartMigration}
              >
                Restart Migration
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Cancel Migration Confirmation Dialog */}
      {cancelConfirmMigration && (
        <div className="confirm-dialog-overlay" onClick={() => setCancelConfirmMigration(null)}>
          <div className="confirm-dialog" onClick={(e) => e.stopPropagation()}>
            <h3>Cancel Migration</h3>
            <p>Cancel "{cancelConfirmMigration.name}"? This will stop the migration process. You can resume it later if needed.</p>
            <div className="confirm-actions">
              <Button variant="outline" onClick={() => setCancelConfirmMigration(null)}>
                Keep Running
              </Button>
              <Button 
                variant="primary" 
                onClick={confirmCancelMigration}
                style={{ background: 'var(--color-error)', borderColor: 'var(--color-error)' }}
              >
                Cancel Migration
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
                            {new Date(log.created_at).toLocaleString('en-IN', {
                              timeZone: 'Asia/Kolkata',
                              year: 'numeric',
                              month: '2-digit',
                              day: '2-digit',
                              hour: '2-digit',
                              minute: '2-digit',
                              second: '2-digit',
                              hour12: true
                            })}
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

      {/* Toast Notification */}
      {toast && (
        <div
          style={{
            position: 'fixed',
            bottom: '24px',
            right: '24px',
            padding: '12px 20px',
            borderRadius: '8px',
            color: '#fff',
            fontSize: '14px',
            fontWeight: 500,
            zIndex: 9999,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            animation: 'slideIn 0.3s ease',
            background: toast.type === 'success' ? '#16a34a' : toast.type === 'error' ? '#dc2626' : '#2563eb',
          }}
          onClick={() => setToast(null)}
        >
          {toast.type === 'success' && (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 8l3 3 5-6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          )}
          {toast.type === 'error' && (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="8" cy="8" r="6" />
              <path d="M6 6l4 4M10 6l-4 4" strokeLinecap="round" />
            </svg>
          )}
          {toast.type === 'info' && (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="8" cy="8" r="6" />
              <path d="M8 5v0M8 7v4" strokeLinecap="round" />
            </svg>
          )}
          {toast.message}
        </div>
      )}
    </div>
  );
};
