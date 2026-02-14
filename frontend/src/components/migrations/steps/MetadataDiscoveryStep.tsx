import React, { useState, useEffect } from 'react';
import { Button, Input } from '../../ui';
import { discoverBigQueryMetadata, BigQueryDataset, BigQueryTable } from '../../../services/bqRedshiftApi';
import './StepStyles.css';
import './MetadataDiscoveryStep.css';

interface MetadataDiscoveryStepProps {
  formData: any;
  updateFormData: (updates: any) => void;
  isEditMode?: boolean;
}

export const MetadataDiscoveryStep: React.FC<MetadataDiscoveryStepProps> = ({
  formData,
  updateFormData,
  isEditMode = false,
}) => {
  const [datasets, setDatasets] = useState<BigQueryDataset[]>([]);
  const [expandedDatasets, setExpandedDatasets] = useState<Set<string>>(new Set());
  const [datasetTables, setDatasetTables] = useState<Record<string, BigQueryTable[]>>({});
  const [loading, setLoading] = useState(false);
  const [loadingTables, setLoadingTables] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (formData.sourceConnectionId) {
      fetchDatasets();
    }
  }, [formData.sourceConnectionId]);

  // Auto-expand dataset in edit mode if tables are selected
  useEffect(() => {
    if (isEditMode && formData.sourceDataset && formData.selectedTables.length > 0) {
      console.log('Edit mode: Auto-expanding dataset:', formData.sourceDataset);
      console.log('Selected tables:', formData.selectedTables);
      
      // Expand the dataset that contains the selected tables
      setExpandedDatasets(new Set([formData.sourceDataset]));
      
      // If we don't have tables loaded for this dataset yet, fetch them
      if (!datasetTables[formData.sourceDataset]) {
        fetchTablesForDataset(formData.sourceDataset);
      }
    }
  }, [isEditMode, formData.sourceDataset, formData.selectedTables, datasetTables]);

  const fetchDatasets = async () => {
    setLoading(true);
    setError(null);
    try {
      console.log('Fetching BigQuery metadata for connection:', formData.sourceConnectionId);
      const data = await discoverBigQueryMetadata(formData.sourceConnectionId);
      console.log('BigQuery metadata received:', data);
      
      // Check if we got tables data
      if (data.tables) {
        setDatasetTables(data.tables);
      }
      
      setDatasets(data.datasets || []);
      if (data.project_id) {
        updateFormData({ sourceProjectId: data.project_id });
      }
    } catch (err: any) {
      console.error('Failed to fetch datasets:', err);
      console.error('Error details:', err.message, err.response);
      
      // Check if it's an authentication error
      if (err.message && err.message.includes('401')) {
        setError('Authentication failed. Please log out and log back in, then try again.');
      } else {
        setError(`Failed to fetch BigQuery metadata: ${err.message}. Using sample data for testing.`);
      }
      
      // Use sample data on error
      const sampleData = getSampleMetadata();
      setDatasets(sampleData.datasets);
      setDatasetTables(sampleData.tables);
      updateFormData({ sourceProjectId: sampleData.project_id });
    } finally {
      setLoading(false);
    }
  };

  // Sample metadata for testing
  const getSampleMetadata = () => {
    return {
      project_id: 'my-gcp-project',
      datasets: [
        {
          dataset_id: 'analytics',
          location: 'US',
          description: 'Analytics and reporting data',
          created: '2025-01-15T10:00:00Z',
          modified: '2026-02-08T14:30:00Z',
          table_count: 5
        },
        {
          dataset_id: 'sales',
          location: 'US',
          description: 'Sales and revenue data',
          created: '2025-02-01T09:00:00Z',
          modified: '2026-02-08T12:00:00Z',
          table_count: 3
        },
        {
          dataset_id: 'marketing',
          location: 'EU',
          description: 'Marketing campaigns and metrics',
          created: '2025-03-10T11:00:00Z',
          modified: '2026-02-07T16:45:00Z',
          table_count: 4
        }
      ],
      tables: {
        'analytics': [
          {
            table_id: 'customers',
            dataset_id: 'analytics',
            type: 'TABLE',
            num_rows: 1250000,
            num_bytes: 450000000,
            created: '2025-01-15T10:30:00Z',
            modified: '2026-02-08T14:30:00Z',
            description: 'Customer master data'
          },
          {
            table_id: 'orders',
            dataset_id: 'analytics',
            type: 'TABLE',
            num_rows: 5800000,
            num_bytes: 2100000000,
            created: '2025-01-15T11:00:00Z',
            modified: '2026-02-08T14:25:00Z',
            description: 'Order transactions'
          },
          {
            table_id: 'products',
            dataset_id: 'analytics',
            type: 'TABLE',
            num_rows: 45000,
            num_bytes: 15000000,
            created: '2025-01-16T09:00:00Z',
            modified: '2026-02-05T10:00:00Z',
            description: 'Product catalog'
          },
          {
            table_id: 'user_activity',
            dataset_id: 'analytics',
            type: 'TABLE',
            num_rows: 12500000,
            num_bytes: 3200000000,
            created: '2025-01-20T14:00:00Z',
            modified: '2026-02-08T15:00:00Z',
            description: 'User activity logs'
          },
          {
            table_id: 'sessions',
            dataset_id: 'analytics',
            type: 'TABLE',
            num_rows: 8900000,
            num_bytes: 1800000000,
            created: '2025-01-22T10:00:00Z',
            modified: '2026-02-08T14:50:00Z',
            description: 'User session data'
          }
        ],
        'sales': [
          {
            table_id: 'revenue',
            dataset_id: 'sales',
            type: 'TABLE',
            num_rows: 890000,
            num_bytes: 280000000,
            created: '2025-02-01T09:30:00Z',
            modified: '2026-02-08T12:00:00Z',
            description: 'Revenue tracking'
          },
          {
            table_id: 'invoices',
            dataset_id: 'sales',
            type: 'TABLE',
            num_rows: 1200000,
            num_bytes: 450000000,
            created: '2025-02-01T10:00:00Z',
            modified: '2026-02-08T11:30:00Z',
            description: 'Invoice records'
          },
          {
            table_id: 'payments',
            dataset_id: 'sales',
            type: 'TABLE',
            num_rows: 1150000,
            num_bytes: 380000000,
            created: '2025-02-02T14:00:00Z',
            modified: '2026-02-08T10:15:00Z',
            description: 'Payment transactions'
          }
        ],
        'marketing': [
          {
            table_id: 'campaigns',
            dataset_id: 'marketing',
            type: 'TABLE',
            num_rows: 50000,
            num_bytes: 12000000,
            created: '2025-03-10T11:30:00Z',
            modified: '2026-02-07T16:45:00Z',
            description: 'Marketing campaigns'
          },
          {
            table_id: 'email_metrics',
            dataset_id: 'marketing',
            type: 'TABLE',
            num_rows: 2500000,
            num_bytes: 680000000,
            created: '2025-03-12T09:00:00Z',
            modified: '2026-02-08T09:30:00Z',
            description: 'Email campaign metrics'
          },
          {
            table_id: 'ad_performance',
            dataset_id: 'marketing',
            type: 'TABLE',
            num_rows: 1800000,
            num_bytes: 520000000,
            created: '2025-03-15T10:00:00Z',
            modified: '2026-02-07T18:00:00Z',
            description: 'Ad campaign performance'
          },
          {
            table_id: 'conversions',
            dataset_id: 'marketing',
            type: 'TABLE',
            num_rows: 450000,
            num_bytes: 125000000,
            created: '2025-03-20T14:00:00Z',
            modified: '2026-02-08T08:00:00Z',
            description: 'Conversion tracking'
          }
        ]
      }
    };
  };

  const fetchTablesForDataset = async (datasetId: string) => {
    if (datasetTables[datasetId]) {
      // Already loaded
      return;
    }

    setLoadingTables(prev => new Set(prev).add(datasetId));
    try {
      const data = await discoverBigQueryMetadata(
        formData.sourceConnectionId,
        formData.sourceProjectId,
        datasetId
      );
      setDatasetTables(prev => {
        const updated = { ...prev };
        // data.tables is Record<string, BigQueryTable[]>, so get the array for this dataset
        if (data.tables && data.tables[datasetId]) {
          updated[datasetId] = data.tables[datasetId];
        } else {
          updated[datasetId] = [];
        }
        return updated;
      });
    } catch (err: any) {
      console.error(`Failed to fetch tables for ${datasetId}:`, err);
    } finally {
      setLoadingTables(prev => {
        const next = new Set(prev);
        next.delete(datasetId);
        return next;
      });
    }
  };

  const toggleDataset = async (datasetId: string) => {
    const isExpanded = expandedDatasets.has(datasetId);
    
    if (isExpanded) {
      // Collapse
      setExpandedDatasets(prev => {
        const next = new Set(prev);
        next.delete(datasetId);
        return next;
      });
    } else {
      // Expand and fetch tables
      setExpandedDatasets(prev => new Set(prev).add(datasetId));
      await fetchTablesForDataset(datasetId);
    }
  };

  const isTableSelected = (datasetId: string, tableId: string): boolean => {
    const fullTableName = `${datasetId}.${tableId}`;
    return formData.selectedTables.includes(fullTableName);
  };

  const toggleTable = (datasetId: string, tableId: string) => {
    const fullTableName = `${datasetId}.${tableId}`;
    const isSelected = formData.selectedTables.includes(fullTableName);
    
    if (isSelected) {
      // Deselect table
      const newSelectedTables = formData.selectedTables.filter((t: string) => t !== fullTableName);
      
      // If no tables selected, clear sourceDataset
      // If tables from different dataset remain, keep the first dataset
      let newSourceDataset = formData.sourceDataset;
      if (newSelectedTables.length === 0) {
        newSourceDataset = '';
      } else {
        const remainingDatasets = new Set(newSelectedTables.map((t: string) => t.split('.')[0]));
        if (!remainingDatasets.has(datasetId) && remainingDatasets.size > 0) {
          newSourceDataset = Array.from(remainingDatasets)[0];
        }
      }
      
      updateFormData({
        selectedTables: newSelectedTables,
        sourceDataset: newSourceDataset,
      });
    } else {
      // Select table
      const newSelectedTables = [...formData.selectedTables, fullTableName];
      
      // Update sourceDataset to the dataset of the first selected table
      // or keep it if it matches the current selection
      const selectedDatasets = new Set(newSelectedTables.map((t: string) => t.split('.')[0]));
      const newSourceDataset = selectedDatasets.size === 1 ? datasetId : (formData.sourceDataset || datasetId);
      
      updateFormData({
        selectedTables: newSelectedTables,
        sourceDataset: newSourceDataset,
      });
    }
  };

  const toggleAllTablesInDataset = (datasetId: string) => {
    const tables = datasetTables[datasetId] || [];
    const tableNames = tables.map(t => `${datasetId}.${t.table_id}`);
    const allSelected = tableNames.every(name => formData.selectedTables.includes(name));
    
    if (allSelected) {
      // Deselect all tables in this dataset
      const newSelectedTables = formData.selectedTables.filter(
        (t: string) => !tableNames.includes(t)
      );
      
      // Update sourceDataset
      let newSourceDataset = formData.sourceDataset;
      if (newSelectedTables.length === 0) {
        newSourceDataset = '';
      } else {
        const remainingDatasets = new Set(newSelectedTables.map((t: string) => t.split('.')[0]));
        if (!remainingDatasets.has(datasetId) && remainingDatasets.size > 0) {
          newSourceDataset = Array.from(remainingDatasets)[0];
        }
      }
      
      updateFormData({
        selectedTables: newSelectedTables,
        sourceDataset: newSourceDataset,
      });
    } else {
      // Select all tables in this dataset
      const newTables = tableNames.filter(name => !formData.selectedTables.includes(name));
      const newSelectedTables = [...formData.selectedTables, ...newTables];
      
      // Update sourceDataset
      const selectedDatasets = new Set(newSelectedTables.map((t: string) => t.split('.')[0]));
      const newSourceDataset = selectedDatasets.size === 1 ? datasetId : (formData.sourceDataset || datasetId);
      
      updateFormData({
        selectedTables: newSelectedTables,
        sourceDataset: newSourceDataset,
      });
    }
  };

  const selectAllTables = () => {
    const allTableNames: string[] = [];
    Object.entries(datasetTables).forEach(([datasetId, tables]) => {
      tables.forEach(table => {
        allTableNames.push(`${datasetId}.${table.table_id}`);
      });
    });
    updateFormData({ selectedTables: allTableNames });
  };

  const deselectAllTables = () => {
    updateFormData({ selectedTables: [] });
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
  };

  const formatNumber = (num: number): string => {
    return num.toLocaleString();
  };

  const filteredDatasets = datasets.filter(ds =>
    ds.dataset_id.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getTotalStats = () => {
    let totalTables = 0;
    let totalRows = 0;
    let totalBytes = 0;

    formData.selectedTables.forEach((fullTableName: string) => {
      const [datasetId, tableId] = fullTableName.split('.');
      const tables = datasetTables[datasetId] || [];
      const table = tables.find(t => t.table_id === tableId);
      if (table) {
        totalTables++;
        totalRows += table.num_rows || 0;
        totalBytes += (table.num_bytes || table.size_bytes || 0);
      }
    });

    return { totalTables, totalRows, totalBytes };
  };

  const stats = getTotalStats();

  return (
    <div className="step-container">
      <div className="step-header">
        <h2>Select Tables to Migrate</h2>
        <p>Choose which BigQuery tables you want to migrate to Redshift</p>
      </div>

      <div className="step-content">
        {/* Read-only notice for edit mode */}
        {isEditMode && (
          <div className="info-box" style={{ marginBottom: '16px' }}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="8" cy="8" r="6" />
              <path d="M8 6v4M8 11h.01" strokeLinecap="round" />
            </svg>
            <div>
              <strong>Table Selection (Read-Only)</strong>
              <p>Tables and datasets cannot be changed after migration creation. The selected tables are displayed below.</p>
            </div>
          </div>
        )}

        {error && (
          <div className="warning-box">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M8 1l7 12H1L8 1z" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M8 6v3M8 11h.01" strokeLinecap="round" />
            </svg>
            <div>{error}</div>
          </div>
        )}

        {/* Summary Stats */}
        {formData.selectedTables.length > 0 && (
          <div className="metadata-summary">
            <div className="summary-stat">
              <div className="stat-label">Tables Selected</div>
              <div className="stat-value">{stats.totalTables}</div>
            </div>
            <div className="summary-stat">
              <div className="stat-label">Total Rows</div>
              <div className="stat-value">{formatNumber(stats.totalRows)}</div>
            </div>
            <div className="summary-stat">
              <div className="stat-label">Total Size</div>
              <div className="stat-value">{formatBytes(stats.totalBytes)}</div>
            </div>
          </div>
        )}

        {/* Search and Actions */}
        <div className="metadata-actions">
          <Input
            type="text"
            placeholder="Search datasets..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            disabled={isEditMode}
          />
          <div className="action-buttons">
            <Button variant="outline" size="sm" onClick={selectAllTables} disabled={isEditMode}>
              Select All
            </Button>
            <Button variant="outline" size="sm" onClick={deselectAllTables} disabled={isEditMode}>
              Deselect All
            </Button>
            <Button variant="outline" size="sm" onClick={fetchDatasets} disabled={isEditMode}>
              Refresh
            </Button>
          </div>
        </div>

        {/* Table View */}
        {loading ? (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Loading datasets...</p>
          </div>
        ) : filteredDatasets.length === 0 ? (
          <div className="empty-state">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="8" y="8" width="32" height="32" rx="4" />
              <path d="M16 20h16M16 28h16" strokeLinecap="round" />
            </svg>
            <p>No datasets found</p>
          </div>
        ) : (
          <div className="metadata-table-container">
            {filteredDatasets.map(dataset => {
              const isExpanded = expandedDatasets.has(dataset.dataset_id);
              const tables = datasetTables[dataset.dataset_id] || [];
              const isLoadingTables = loadingTables.has(dataset.dataset_id);

              return (
                <div key={dataset.dataset_id} className="dataset-section">
                  {/* Dataset Header */}
                  <div className="dataset-header" onClick={() => toggleDataset(dataset.dataset_id)}>
                    <div className="dataset-header-left">
                      <button className="expand-button">
                        <svg
                          width="16"
                          height="16"
                          viewBox="0 0 16 16"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          className={isExpanded ? 'expanded' : ''}
                        >
                          <path d="M6 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      </button>
                      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <path d="M3 5h14M3 5v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V5M6 5V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v1" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                      <span className="dataset-name">{dataset.dataset_id}</span>
                      <span className="dataset-location">{dataset.location}</span>
                    </div>
                    <div className="dataset-header-right">
                      <span className="dataset-table-count">{tables.length} tables</span>
                    </div>
                  </div>

                  {/* Tables Table */}
                  {isExpanded && (
                    <div className="tables-container">
                      {isLoadingTables ? (
                        <div className="loading-tables">
                          <div className="spinner-small"></div>
                          <span>Loading tables...</span>
                        </div>
                      ) : tables.length === 0 ? (
                        <div className="empty-tables">No tables found</div>
                      ) : (
                        <table className="tables-table">
                          <thead>
                            <tr>
                              <th style={{ width: '40px' }}>
                                <input
                                  type="checkbox"
                                  checked={tables.every(t => isTableSelected(dataset.dataset_id, t.table_id))}
                                  onChange={() => !isEditMode && toggleAllTablesInDataset(dataset.dataset_id)}
                                  disabled={isEditMode}
                                />
                              </th>
                              <th>Table Name</th>
                              <th style={{ textAlign: 'right' }}>Rows</th>
                              <th style={{ textAlign: 'right' }}>Size</th>
                            </tr>
                          </thead>
                          <tbody>
                            {tables.map(table => (
                              <tr key={table.table_id}>
                                <td>
                                  <input
                                    type="checkbox"
                                    checked={isTableSelected(dataset.dataset_id, table.table_id)}
                                    onChange={() => !isEditMode && toggleTable(dataset.dataset_id, table.table_id)}
                                    disabled={isEditMode}
                                  />
                                </td>
                                <td>
                                  <div className="table-name-cell">
                                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                                      <rect x="2" y="3" width="12" height="10" rx="1" />
                                      <path d="M2 6h12M6 3v10" />
                                    </svg>
                                    <span>{table.table_id}</span>
                                  </div>
                                </td>
                                <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                                  {formatNumber(table.num_rows || 0)}
                                </td>
                                <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                                  {formatBytes((table.num_bytes || table.size_bytes || 0))}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
