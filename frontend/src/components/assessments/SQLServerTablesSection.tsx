/**
 * SQL Server Tables Section Component
 * 
 * Displays tables with SQL Server-specific columns including:
 * - Indexes and constraints
 * - Partitioning information
 * - Storage details
 * - Redshift compatibility
 */

import React, { useState } from 'react';
import { Table as TableIcon, AlertCircle, CheckCircle, Info, Database, HardDrive } from 'lucide-react';
import { Badge } from '../ui';
import { getRedshiftCompatibility } from '../../utils/dataTypeMapping';

interface SQLServerTablesSectionProps {
  tables: any[];
  columns: any[];
  indexes: any[];
  formatSize: (sizeMb: number) => string;
  formatDate: (dateString: string | null) => string;
  formatNumber: (num: number) => string;
}

export const SQLServerTablesSection: React.FC<SQLServerTablesSectionProps> = ({
  tables,
  columns,
  indexes,
  formatSize,
  formatDate,
  formatNumber
}) => {
  const [selectedTable, setSelectedTable] = useState<any | null>(null);
  const [showDetailsModal, setShowDetailsModal] = useState(false);
  const [activeDetailTab, setActiveDetailTab] = useState<'columns' | 'indexes' | 'partitions'>('columns');

  // Filter to show only BASE TABLEs (not views)
  const baseTables = tables.filter((t: any) => t.table_type === 'BASE TABLE');

  const handleTableClick = (table: any) => {
    setSelectedTable(table);
    setShowDetailsModal(true);
  };

  const getColumnsForTable = (tableId: number) => {
    return columns.filter((col: any) => col.table_id === tableId);
  };

  const getIndexesForTable = (tableId: number) => {
    return indexes?.filter((idx: any) => idx.table_id === tableId) || [];
  };

  return (
    <div className="section-content">
      <h2 className="section-heading">Tables ({baseTables.length})</h2>
      {baseTables.length === 0 ? (
        <div className="empty-state">
          <TableIcon size={48} />
          <p>No tables found</p>
        </div>
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Schema</th>
                <th>Table Name</th>
                <th>Created</th>
                <th>Row Count</th>
                <th>Size</th>
                <th>Partitioned</th>
              </tr>
            </thead>
            <tbody>
              {baseTables.map((table: any) => {
                const isPartitioned = table.partition_function || table.partitioning_columns?.length > 0;
                
                return (
                  <tr key={table.id}>
                    <td className="font-medium">{table.dataset_name}</td>
                    <td>
                      <button
                        className="table-name-link"
                        onClick={() => handleTableClick(table)}
                        title="Click to view table details"
                      >
                        {table.table_name}
                      </button>
                    </td>
                    <td className="timestamp-value">{formatDate(table.creation_time)}</td>
                    <td className="numeric-value">{formatNumber(table.row_count)}</td>
                    <td className="numeric-value">{formatSize(table.size_mb)}</td>
                    <td>
                      {isPartitioned ? (
                        <Badge variant="info">Yes</Badge>
                      ) : (
                        <Badge variant="default">No</Badge>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Table Details Modal */}
      {showDetailsModal && selectedTable && (
        <div className="modal-overlay" onClick={() => setShowDetailsModal(false)}>
          <div className="modal-content table-details-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">
                <TableIcon size={20} />
                {selectedTable.dataset_name}.{selectedTable.table_name}
              </h3>
              <button className="modal-close" onClick={() => setShowDetailsModal(false)}>
                ×
              </button>
            </div>
            
            {/* Table Info Summary */}
            <div className="table-summary" style={{ padding: '16px', borderBottom: '1px solid var(--color-divider)', background: 'var(--color-bg-secondary)' }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '16px' }}>
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '4px' }}>Rows</div>
                  <div style={{ fontSize: '16px', fontWeight: 600 }}>{formatNumber(selectedTable.row_count)}</div>
                </div>
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '4px' }}>Size</div>
                  <div style={{ fontSize: '16px', fontWeight: 600 }}>{formatSize(selectedTable.size_mb)}</div>
                </div>
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '4px' }}>Columns</div>
                  <div style={{ fontSize: '16px', fontWeight: 600 }}>{getColumnsForTable(selectedTable.id).length}</div>
                </div>
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '4px' }}>Indexes</div>
                  <div style={{ fontSize: '16px', fontWeight: 600 }}>{getIndexesForTable(selectedTable.id).length}</div>
                </div>
                {selectedTable.partition_function && (
                  <div>
                    <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '4px' }}>Partition Function</div>
                    <div style={{ fontSize: '14px', fontWeight: 500 }}>{selectedTable.partition_function}</div>
                  </div>
                )}
              </div>
            </div>

            {/* Detail Tabs */}
            <div className="detail-tabs" style={{ display: 'flex', gap: '8px', padding: '16px 16px 0', borderBottom: '1px solid var(--color-divider)' }}>
              <button
                className={`detail-tab ${activeDetailTab === 'columns' ? 'active' : ''}`}
                onClick={() => setActiveDetailTab('columns')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '8px 16px',
                  border: 'none',
                  background: 'none',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: 500,
                  color: activeDetailTab === 'columns' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
                  borderBottom: activeDetailTab === 'columns' ? '2px solid var(--color-primary)' : '2px solid transparent',
                  transition: 'all 0.2s ease'
                }}
              >
                <Database size={16} />
                Columns ({getColumnsForTable(selectedTable.id).length})
              </button>
              <button
                className={`detail-tab ${activeDetailTab === 'indexes' ? 'active' : ''}`}
                onClick={() => setActiveDetailTab('indexes')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '8px 16px',
                  border: 'none',
                  background: 'none',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: 500,
                  color: activeDetailTab === 'indexes' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
                  borderBottom: activeDetailTab === 'indexes' ? '2px solid var(--color-primary)' : '2px solid transparent',
                  transition: 'all 0.2s ease'
                }}
              >
                <HardDrive size={16} />
                Indexes ({getIndexesForTable(selectedTable.id).length})
              </button>
              <button
                className={`detail-tab ${activeDetailTab === 'partitions' ? 'active' : ''}`}
                onClick={() => setActiveDetailTab('partitions')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '8px 16px',
                  border: 'none',
                  background: 'none',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: 500,
                  color: activeDetailTab === 'partitions' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
                  borderBottom: activeDetailTab === 'partitions' ? '2px solid var(--color-primary)' : '2px solid transparent',
                  transition: 'all 0.2s ease'
                }}
              >
                <TableIcon size={16} />
                Partitioning
              </button>
            </div>

            <div className="modal-body">
              {/* Columns Tab */}
              {activeDetailTab === 'columns' && (
                <div className="table-container">
                  <table className="data-table compact">
                    <thead>
                      <tr>
                        <th>Column Name</th>
                        <th>SQL Server Type</th>
                        <th>Nullable</th>
                        <th>Position</th>
                        <th>Redshift Compatible</th>
                        <th>Redshift Type</th>
                      </tr>
                    </thead>
                    <tbody>
                      {getColumnsForTable(selectedTable.id).map((column: any, idx: number) => {
                        const compatibility = getRedshiftCompatibility(column.data_type);
                        
                        return (
                          <tr key={idx}>
                            <td className="font-medium">{column.column_name}</td>
                            <td className="font-mono text-sm">{column.data_type}</td>
                            <td>
                              {column.is_nullable ? (
                                <Badge variant="default">Yes</Badge>
                              ) : (
                                <Badge variant="error">No</Badge>
                              )}
                            </td>
                            <td>{column.ordinal_position}</td>
                            <td>
                              {compatibility.compatible ? (
                                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                  <CheckCircle size={16} color="#16A34A" />
                                  <span style={{ color: '#16A34A', fontSize: '13px' }}>Yes</span>
                                </div>
                              ) : (
                                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                  <AlertCircle size={16} color="#DC2626" />
                                  <span style={{ color: '#DC2626', fontSize: '13px' }}>No</span>
                                </div>
                              )}
                            </td>
                            <td className="text-sm">
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <code style={{ 
                                  background: '#F3F4F6', 
                                  padding: '2px 6px', 
                                  borderRadius: '4px',
                                  fontSize: '12px'
                                }}>
                                  {compatibility.redshiftType}
                                </code>
                                {compatibility.notes && (
                                  <div 
                                    style={{ 
                                      display: 'flex', 
                                      alignItems: 'center', 
                                      gap: '4px',
                                      cursor: 'help'
                                    }}
                                    title={compatibility.notes}
                                  >
                                    <Info size={14} color="#2563EB" />
                                  </div>
                                )}
                              </div>
                              {compatibility.notes && (
                                <div style={{ 
                                  fontSize: '11px', 
                                  color: '#6B7280', 
                                  marginTop: '4px',
                                  fontStyle: 'italic'
                                }}>
                                  {compatibility.notes}
                                </div>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Indexes Tab */}
              {activeDetailTab === 'indexes' && (
                <div className="table-container">
                  {getIndexesForTable(selectedTable.id).length === 0 ? (
                    <div className="empty-state">
                      <HardDrive size={48} />
                      <p>No indexes found</p>
                    </div>
                  ) : (
                    <table className="data-table compact">
                      <thead>
                        <tr>
                          <th>Index Name</th>
                          <th>Type</th>
                          <th>Columns</th>
                          <th>Unique</th>
                          <th>Clustered</th>
                          <th>Size (MB)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {getIndexesForTable(selectedTable.id).map((index: any, idx: number) => (
                          <tr key={idx}>
                            <td className="font-medium">{index.index_name}</td>
                            <td>
                              <Badge variant={index.index_type === 'CLUSTERED' ? 'success' : 'info'}>
                                {index.index_type}
                              </Badge>
                            </td>
                            <td className="text-sm">{index.key_columns}</td>
                            <td>
                              {index.is_unique ? (
                                <Badge variant="success">Yes</Badge>
                              ) : (
                                <Badge variant="default">No</Badge>
                              )}
                            </td>
                            <td>
                              {index.is_clustered ? (
                                <Badge variant="warning">Yes</Badge>
                              ) : (
                                <Badge variant="default">No</Badge>
                              )}
                            </td>
                            <td className="numeric-value">{formatSize(index.size_mb || 0)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}

              {/* Partitioning Tab */}
              {activeDetailTab === 'partitions' && (
                <div className="partition-info">
                  {selectedTable.partition_function ? (
                    <div>
                      <div className="info-section" style={{ marginBottom: '24px' }}>
                        <h4 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '12px' }}>Partition Information</h4>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
                          <div>
                            <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '4px' }}>Partition Function</div>
                            <div style={{ fontSize: '14px', fontWeight: 500 }}>{selectedTable.partition_function}</div>
                          </div>
                          {selectedTable.partition_scheme && (
                            <div>
                              <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '4px' }}>Partition Scheme</div>
                              <div style={{ fontSize: '14px', fontWeight: 500 }}>{selectedTable.partition_scheme}</div>
                            </div>
                          )}
                          {selectedTable.partitioning_columns?.length > 0 && (
                            <div>
                              <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '4px' }}>Partition Columns</div>
                              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                                {selectedTable.partitioning_columns.map((col: string, idx: number) => (
                                  <Badge key={idx} variant="info">{col}</Badge>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                      
                      {selectedTable.partition_details && (
                        <div className="info-section">
                          <h4 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '12px' }}>Partition Details</h4>
                          <div style={{ 
                            background: 'var(--color-bg-secondary)', 
                            padding: '12px', 
                            borderRadius: '6px',
                            fontSize: '13px',
                            fontFamily: 'monospace'
                          }}>
                            {JSON.stringify(selectedTable.partition_details, null, 2)}
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="empty-state">
                      <TableIcon size={48} />
                      <p>Table is not partitioned</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
