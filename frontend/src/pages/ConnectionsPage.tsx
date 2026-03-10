import React, { useState, useEffect } from 'react';
import { SiMongodb, SiAmazondocumentdb, SiPostgresql, SiMysql, SiOracle, SiGooglecloud, SiAmazonredshift } from 'react-icons/si';
import { Cable, Database } from 'lucide-react';
import { Button, Badge, Dropdown, DropdownItem, Select, Avatar } from '../components/ui';
import { CreateConnectionModal, ConnectionFormData } from '../components/connections/CreateConnectionModal';
import { listConnections, createConnection, Connection, testConnection, api } from '../services/api';
import { WorkspaceSelector } from '../components/WorkspaceSelector';
import { useWorkspace } from '../contexts/WorkspaceContext';
import './ConnectionsPage.css';

export const ConnectionsPage: React.FC = () => {
  const { selectedWorkspaceName } = useWorkspace();
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(15);
  const [showCreateMenu, setShowCreateMenu] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [connectionType, setConnectionType] = useState<'source' | 'target'>('source');
  const [connections, setConnections] = useState<Connection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openMenuId, setOpenMenuId] = useState<number | null>(null);
  const [menuPosition, setMenuPosition] = useState<{ top?: number; bottom?: number; right: number }>({ right: 0 });
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);
  const [testingConnectionId, setTestingConnectionId] = useState<number | null>(null);
  const [testResult, setTestResult] = useState<{ connectionId: number; success: boolean; message: string; details?: any } | null>(null);
  const [editingConnection, setEditingConnection] = useState<Connection | null>(null);
  const [showEditModal, setShowEditModal] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Auto-dismiss toast
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  // Fetch connections on mount
  useEffect(() => {
    fetchConnections();
  }, []);

  const fetchConnections = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Try to fetch from API
      try {
        const data = await listConnections();
        
        // If no connections, add sample data
        if (data.length === 0) {
          setConnections(getSampleConnections());
        } else {
          setConnections(data);
        }
      } catch (apiError) {
        // If API fails, use sample data
        setConnections(getSampleConnections());
      }
    } catch (err: any) {
      setError(err.detail || err.message || 'Failed to load connections');
      // Still show sample data on error
      setConnections(getSampleConnections());
    } finally {
      setLoading(false);
    }
  };

  // Sample connections for testing
  const getSampleConnections = (): Connection[] => {
    return [
      {
        id: 1,
        name: 'Production BigQuery',
        type: 'source',
        database: 'bigquery',
        connection_params: {},
        connection_string: '',
        created_by: 'John Doe',
        status: 'connected',
        last_tested_at: '2026-02-08 14:30:00',
        created_at: '2026-01-15 10:00:00',
        updated_at: '2026-02-08 14:30:00',
        is_active: true,
        workspace_id: 1
      },
      {
        id: 2,
        name: 'Production Redshift',
        type: 'target',
        database: 'redshift',
        connection_params: {},
        connection_string: '',
        created_by: 'Jane Smith',
        status: 'connected',
        last_tested_at: '2026-02-08 15:00:00',
        created_at: '2026-01-15 11:00:00',
        updated_at: '2026-02-08 15:00:00',
        is_active: true,
        workspace_id: 1
      },
      {
        id: 3,
        name: 'Analytics MongoDB',
        type: 'source',
        database: 'mongodb',
        connection_params: {},
        connection_string: '',
        created_by: 'John Doe',
        status: 'connected',
        last_tested_at: '2026-02-07 09:15:00',
        created_at: '2026-01-20 14:00:00',
        updated_at: '2026-02-07 09:15:00',
        is_active: true,
        workspace_id: 1
      },
      {
        id: 4,
        name: 'Staging PostgreSQL',
        type: 'target',
        database: 'postgresql',
        connection_params: {},
        connection_string: '',
        created_by: 'Jane Smith',
        status: 'disconnected',
        last_tested_at: null,
        created_at: '2026-02-01 16:00:00',
        updated_at: '2026-02-01 16:00:00',
        is_active: true,
        workspace_id: 1
      },
      {
        id: 5,
        name: 'Legacy Oracle DB',
        type: 'source',
        database: 'oracle',
        connection_params: {},
        connection_string: '',
        created_by: 'Mike Johnson',
        status: 'testing',
        last_tested_at: '2026-02-08 16:00:00',
        created_at: '2026-01-25 10:30:00',
        updated_at: '2026-02-08 16:00:00',
        is_active: true,
        workspace_id: 1
      }
    ];
  };

  const totalConnections = connections.length;
  const totalPages = Math.ceil(totalConnections / rowsPerPage);

  const getDatabaseIcon = (database: string) => {
    const dbLower = database.toLowerCase();
    switch (dbLower) {
      case 'mongodb':
        return <SiMongodb className="db-icon mongodb" />;
      case 'documentdb':
        return <SiAmazondocumentdb className="db-icon documentdb" />;
      case 'postgresql':
        return <SiPostgresql className="db-icon postgresql" />;
      case 'mysql':
        return <SiMysql className="db-icon mysql" />;
      case 'oracle':
        return <SiOracle className="db-icon oracle" />;
      case 'bigquery':
        return <SiGooglecloud className="db-icon bigquery" />;
      case 'redshift':
        return <SiAmazonredshift className="db-icon redshift" />;
      case 'sqlserver':
        return <Database className="db-icon sqlserver" size={16} />;
      default:
        return <Database className="db-icon" size={16} />;
    }
  };

  const getDatabaseLabel = (database: string) => {
    const labels: Record<string, string> = {
      'mongodb': 'MongoDB',
      'documentdb': 'DocumentDB',
      'postgresql': 'PostgreSQL',
      'mysql': 'MySQL',
      'oracle': 'Oracle',
      'bigquery': 'BigQuery',
      'redshift': 'Redshift',
      'sqlserver': 'SQL Server'
    };
    return labels[database.toLowerCase()] || database;
  };

  const getStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case 'connected':
      case 'success':
        return <Badge variant="success">Connected</Badge>;
      case 'disconnected':
      case 'failed':
        return <Badge variant="error">Disconnected</Badge>;
      case 'testing':
        return <Badge variant="warning">Testing</Badge>;
      default:
        return <Badge>{status}</Badge>;
    }
  };

  const handleCreateConnection = (type: 'source' | 'target') => {
    setConnectionType(type);
    setShowCreateMenu(false);
    setShowCreateModal(true);
  };

  const handleSubmitConnection = async (data: ConnectionFormData) => {
    try {
      
      // Extract connection params (all fields except name, type, database)
      const { name, type, database, ...connectionParams } = data;
      
      // Create connection with initial status as 'connected' since test was successful
      const response = await createConnection({
        name,
        type,
        database,
        connection_params: connectionParams,
        created_by: 'current_user', // TODO: Get from auth context
        status: 'connected', // Set initial status as connected
        last_tested_at: new Date().toISOString() // Set current time as last tested
      });
      
      
      // Refresh the connections list
      await fetchConnections();
      
      // Show success message
      setToast({ message: `${type} connection created`, type: 'success' });
    } catch (error: any) {
      setToast({ message: `Failed to create connection: ${error.detail || error.message}`, type: 'error' });
      throw error; // Re-throw so modal can handle it
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
      return 'Invalid date';
    }
  };

  const handleDeleteConnection = async (connectionId: number) => {
    try {
      await api.delete(`/api/connections/${connectionId}`);
      await fetchConnections();
      setDeleteConfirmId(null);
    } catch (error: any) {
      setToast({ message: `Failed to delete connection: ${error.detail || error.message}`, type: 'error' });
    }
  };

  const handleUpdateConnection = (connection: Connection) => {
    setEditingConnection(connection);
    setShowEditModal(true);
    setOpenMenuId(null);
  };

  const handleSaveConnection = async (updatedData: ConnectionFormData) => {
    if (!editingConnection) return;

    try {
      
      // Extract connection params (all fields except name, type, database)
      const { name, type, database, ...connectionParams } = updatedData;
      
      // Update connection
      const response = await api.put<Connection>(`/api/connections/${editingConnection.id}`, {
        name,
        type,
        database,
        connection_params: connectionParams,
        status: 'connected', // Set as connected since test was successful
        last_tested_at: new Date().toISOString()
      });
      
      
      // Refresh the connections list
      await fetchConnections();
      
      // Close modal
      setShowEditModal(false);
      setEditingConnection(null);
      
      // Show success message
      setToast({ message: 'Connection updated', type: 'success' });
    } catch (error: any) {
      setToast({ message: `Failed to update connection: ${error.detail || error.message}`, type: 'error' });
      throw error; // Re-throw so modal can handle it
    }
  };

  const handleTestConnection = async (connection: Connection) => {
    try {
      setTestingConnectionId(connection.id);
      setTestResult(null);
      
      // Update status to testing
      setConnections(prev => prev.map(c => 
        c.id === connection.id ? { ...c, status: 'testing' } : c
      ));
      
      
      // Use the new endpoint that tests by ID (handles decryption server-side)
      const result = await api.post<any>(`/api/connections/${connection.id}/test`, {});
      
      // Store test result for display
      setTestResult({
        connectionId: connection.id,
        success: result.success,
        message: result.message,
        details: result.details
      });
      
      // The backend endpoint already updates the status, so just refresh the connection
      // Fetch the updated connection from the backend
      await fetchConnections();
      
    } catch (error: any) {
      
      // Store error result
      setTestResult({
        connectionId: connection.id,
        success: false,
        message: error.detail || error.message || 'Connection test failed',
        details: error
      });
      
      // Update status to disconnected on error
      setConnections(prev => prev.map(c => 
        c.id === connection.id ? { ...c, status: 'disconnected' } : c
      ));
    } finally {
      setTestingConnectionId(null);
    }
  };

  // Close dropdown when clicking outside
  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (openMenuId !== null && !target.closest('.connection-menu-container')) {
        setOpenMenuId(null);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [openMenuId]);

  return (
    <div className="connections-page">
      {/* Header */}
      <div className="connections-header">
        <div className="connections-title-section">
          <h1 className="connections-title">
            <Cable size={20} strokeWidth={2} className="page-title-icon" />
            Data Connections
            <span style={{ fontSize: 13, fontWeight: 400, color: '#6B7280', marginLeft: 8 }}>— {selectedWorkspaceName}</span>
          </h1>
          <div className="connections-subheader">
            <span className="connections-count">{totalConnections} Connections</span>
            
            <div className="connections-actions">
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
                <DropdownItem onClick={() => handleCreateConnection('source')}>
                  Source Connection
                </DropdownItem>
                <DropdownItem onClick={() => handleCreateConnection('target')}>
                  Target Connection
                </DropdownItem>
              </Dropdown>
            </div>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="connections-table-container">
        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center' }}>
            <div className="spinner" style={{ margin: '0 auto' }}></div>
            <p style={{ marginTop: '16px', color: '#66748C' }}>Loading connections...</p>
          </div>
        ) : error ? (
          <div style={{ padding: '40px', textAlign: 'center' }}>
            <p style={{ color: '#DC2626', marginBottom: '16px' }}>{error}</p>
            <Button variant="primary" onClick={fetchConnections}>
              Retry
            </Button>
          </div>
        ) : connections.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center' }}>
            <p style={{ color: '#66748C', marginBottom: '16px' }}>No connections found</p>
            <Button variant="primary" onClick={() => setShowCreateMenu(true)}>
              Create Your First Connection
            </Button>
          </div>
        ) : (
          <table className="connections-table">
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
                <th>TYPE</th>
                <th>DATABASE</th>
                <th>CREATED BY</th>
                <th>CONNECTION STATUS</th>
                <th>LAST TESTED AT</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {connections.map((connection) => (
                <tr key={connection.id}>
                  <td>
                    <div className="name-cell-with-icon">
                      {getDatabaseIcon(connection.database)}
                      <span className="name-cell">{connection.name}</span>
                    </div>
                  </td>
                  <td>
                    <span className={`type-badge ${connection.type}`}>
                      {connection.type.charAt(0).toUpperCase() + connection.type.slice(1)}
                    </span>
                  </td>
                  <td>{getDatabaseLabel(connection.database)}</td>
                  <td>
                    <div className="created-by-cell">
                      <Avatar name={connection.created_by} size="sm" />
                      <span>{connection.created_by}</span>
                    </div>
                  </td>
                  <td>{getStatusBadge(connection.status)}</td>
                  <td className="timestamp-cell">{formatDateTime(connection.last_tested_at)}</td>
                  <td>
                    <div className="connection-menu-container">
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
                          
                          setMenuPosition(position);
                          setOpenMenuId(openMenuId === connection.id ? null : connection.id);
                        }}
                      >
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                          <circle cx="8" cy="3" r="1.5" />
                          <circle cx="8" cy="8" r="1.5" />
                          <circle cx="8" cy="13" r="1.5" />
                        </svg>
                      </button>
                      
                      {openMenuId === connection.id && (
                        <div 
                          className={`connection-dropdown-menu ${menuPosition.bottom ? 'open-upward' : ''}`}
                          style={{
                            top: menuPosition.top ? `${menuPosition.top}px` : 'auto',
                            bottom: menuPosition.bottom ? `${menuPosition.bottom}px` : 'auto',
                            right: `${menuPosition.right}px`
                          }}
                        >
                          <button
                            className="dropdown-menu-item"
                            onClick={() => {
                              handleTestConnection(connection);
                              setOpenMenuId(null);
                            }}
                          >
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                              <path d="M14 8A6 6 0 1 1 2 8a6 6 0 0 1 12 0z" />
                              <path d="M8 5v3l2 2" strokeLinecap="round" />
                            </svg>
                            Test Connection
                          </button>
                          <button
                            className="dropdown-menu-item"
                            onClick={() => handleUpdateConnection(connection)}
                          >
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                              <path d="M11.5 2.5l2 2L6 12H4v-2l7.5-7.5z" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                            Update Connection
                          </button>
                          <div className="dropdown-divider" />
                          <button
                            className="dropdown-menu-item dropdown-menu-item-danger"
                            onClick={() => {
                              setDeleteConfirmId(connection.id);
                              setOpenMenuId(null);
                            }}
                          >
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                              <path d="M3 4h10M5 4V3a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v1M6 7v4M10 7v4M4 4h8v9a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V4z" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                            Delete Connection
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
      <div className="connections-pagination">
        <div className="pagination-info">
          Showing {((currentPage - 1) * rowsPerPage) + 1} to {Math.min(currentPage * rowsPerPage, totalConnections)} of {totalConnections} connections
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

      {/* Create Connection Modal */}
      <CreateConnectionModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        connectionType={connectionType}
        onSubmit={handleSubmitConnection}
      />

      {/* Edit Connection Modal */}
      {editingConnection && (
        <CreateConnectionModal
          isOpen={showEditModal}
          onClose={() => {
            setShowEditModal(false);
            setEditingConnection(null);
          }}
          connectionType={editingConnection.type as 'source' | 'target'}
          onSubmit={handleSaveConnection}
          initialData={{
            name: editingConnection.name,
            type: editingConnection.type as 'source' | 'target',
            database: editingConnection.database,
            ...editingConnection.connection_params
          }}
          isEditMode={true}
        />
      )}

      {/* Delete Confirmation Dialog */}
      {deleteConfirmId && (
        <div className="confirm-dialog-overlay" onClick={() => setDeleteConfirmId(null)}>
          <div className="confirm-dialog" onClick={(e) => e.stopPropagation()}>
            <h3>Delete Connection</h3>
            <p>Are you sure you want to delete this connection? This action cannot be undone.</p>
            <div className="confirm-actions">
              <Button variant="outline" onClick={() => setDeleteConfirmId(null)}>
                Cancel
              </Button>
              <Button 
                variant="primary" 
                onClick={() => handleDeleteConnection(deleteConfirmId)}
                style={{ background: 'var(--color-error)', borderColor: 'var(--color-error)' }}
              >
                Delete Connection
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Connection Test Result Notification */}
      {testResult && (
        <div className="test-result-notification-overlay" onClick={() => setTestResult(null)}>
          <div className="test-result-notification" onClick={(e) => e.stopPropagation()}>
            <div className={`test-result-header ${testResult.success ? 'success' : 'error'}`}>
              {testResult.success ? (
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M9 12l2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              ) : (
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M15 9l-6 6M9 9l6 6" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
              <h3>{testResult.success ? 'Connection Successful' : 'Connection Failed'}</h3>
            </div>
            
            <div className="test-result-body">
              <div className="test-result-message">
                <strong>Message:</strong>
                <p>{testResult.message}</p>
              </div>
              
              {testResult.details && (
                <div className="test-result-details">
                  <strong>Details:</strong>
                  <pre>{JSON.stringify(testResult.details, null, 2)}</pre>
                </div>
              )}
              
              {!testResult.success && (
                <div className="test-result-help">
                  <strong>Troubleshooting Tips:</strong>
                  <ul>
                    <li>Verify all connection parameters are correct</li>
                    <li>Check network connectivity to the database server</li>
                    <li>Ensure firewall rules allow connections</li>
                    <li>Verify credentials have proper permissions</li>
                    <li>Check if the database service is running</li>
                  </ul>
                </div>
              )}
            </div>
            
            <div className="test-result-footer">
              <Button variant="primary" onClick={() => setTestResult(null)}>
                Close
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
