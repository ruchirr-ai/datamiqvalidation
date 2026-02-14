import React, { useState, useEffect } from 'react';
import { Input, Select } from '../../ui';
import { listConnections, Connection } from '../../../services/api';
import './StepStyles.css';

interface ConnectionStagingStepProps {
  formData: any;
  updateFormData: (updates: any) => void;
  isEditMode?: boolean;
}

export const ConnectionStagingStep: React.FC<ConnectionStagingStepProps> = ({
  formData,
  updateFormData,
  isEditMode = false,
}) => {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [loading, setLoading] = useState(true);

  // Sample connections for testing the wizard
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
        name: 'Production DocumentDB',
        type: 'target',
        database: 'documentdb',
        connection_params: {},
        connection_string: '',
        created_by: 'Jane Smith',
        status: 'connected',
        last_tested_at: '2026-02-08 12:00:00',
        created_at: '2026-02-01 16:00:00',
        updated_at: '2026-02-08 12:00:00',
        is_active: true,
        workspace_id: 1
      },
      {
        id: 5,
        name: 'Dev BigQuery',
        type: 'source',
        database: 'bigquery',
        connection_params: {},
        connection_string: '',
        created_by: 'Mike Johnson',
        status: 'connected',
        last_tested_at: '2026-02-08 10:00:00',
        created_at: '2026-01-25 10:30:00',
        updated_at: '2026-02-08 10:00:00',
        is_active: true,
        workspace_id: 1
      },
      {
        id: 6,
        name: 'Staging Redshift',
        type: 'target',
        database: 'redshift',
        connection_params: {},
        connection_string: '',
        created_by: 'Mike Johnson',
        status: 'connected',
        last_tested_at: '2026-02-08 11:00:00',
        created_at: '2026-01-28 14:00:00',
        updated_at: '2026-02-08 11:00:00',
        is_active: true,
        workspace_id: 1
      },
      {
        id: 7,
        name: 'Dev MongoDB',
        type: 'source',
        database: 'mongodb',
        connection_params: {},
        connection_string: '',
        created_by: 'Sarah Lee',
        status: 'connected',
        last_tested_at: '2026-02-08 09:00:00',
        created_at: '2026-02-03 11:00:00',
        updated_at: '2026-02-08 09:00:00',
        is_active: true,
        workspace_id: 1
      },
      {
        id: 8,
        name: 'Staging DocumentDB',
        type: 'target',
        database: 'documentdb',
        connection_params: {},
        connection_string: '',
        created_by: 'Sarah Lee',
        status: 'connected',
        last_tested_at: '2026-02-08 09:30:00',
        created_at: '2026-02-03 12:00:00',
        updated_at: '2026-02-08 09:30:00',
        is_active: true,
        workspace_id: 1
      }
    ];
  };

  useEffect(() => {
    console.log('ConnectionStagingStep mounted, fetching connections...');
    fetchConnections();
  }, []);

  const fetchConnections = async () => {
    setLoading(true);
    try {
      const data = await listConnections();
      
      // If no connections, use sample data
      if (!data || data.length === 0) {
        console.log('No connections from API, using sample data');
        setConnections(getSampleConnections());
      } else {
        console.log('Loaded connections from API:', data);
        setConnections(data);
      }
    } catch (error) {
      console.error('Failed to fetch connections, using sample data:', error);
      // Always use sample data on error
      setConnections(getSampleConnections());
    } finally {
      setLoading(false);
    }
  };

  // Get migration type configuration
  const getMigrationTypeConfig = () => {
    if (formData.migrationType === 'bigquery-redshift') {
      return {
        sourceDb: 'bigquery',
        targetDb: 'redshift',
        label: 'BigQuery to Redshift'
      };
    } else if (formData.migrationType === 'mongodb-documentdb') {
      return {
        sourceDb: 'mongodb',
        targetDb: 'documentdb',
        label: 'MongoDB to DocumentDB'
      };
    }
    return null;
  };

  const migrationConfig = getMigrationTypeConfig();

  // Filter connections based on migration type
  const sourceConnections = migrationConfig
    ? connections.filter(c => 
        c.type === 'source' && 
        c.database.toLowerCase() === migrationConfig.sourceDb
      )
    : connections.filter(c => c.type === 'source');

  const targetConnections = migrationConfig
    ? connections.filter(c => 
        c.type === 'target' && 
        c.database.toLowerCase() === migrationConfig.targetDb
      )
    : connections.filter(c => c.type === 'target');

  return (
    <div className="step-container">
      <div className="step-header">
        <h2>Connection Configuration</h2>
        <p>Select source and target connections for your migration</p>
      </div>

      <div className="step-content">
        {/* Migration Name */}
        <div className="form-section">
          <label className="form-label">
            Migration Name <span className="required">*</span>
          </label>
          <Input
            type="text"
            placeholder="e.g., Customer Data Migration"
            value={formData.migrationName}
            onChange={(e) => updateFormData({ migrationName: e.target.value })}
          />
          <p className="form-help">A descriptive name for this migration</p>
        </div>

        {/* Migration Type */}
        <div className="form-section">
          <label className="form-label">
            Migration Type <span className="required">*</span>
          </label>
          <Select
            value={formData.migrationType || ''}
            onChange={(value) => {
              updateFormData({ 
                migrationType: value as 'bigquery-redshift' | 'mongodb-documentdb',
                // Reset connections when migration type changes
                sourceConnectionId: null,
                targetConnectionId: null
              });
            }}
            options={[
              { value: '', label: 'Select migration type' },
              { value: 'bigquery-redshift', label: 'BigQuery to Redshift' },
              { value: 'mongodb-documentdb', label: 'MongoDB to DocumentDB' },
            ]}
          />
          <p className="form-help">Choose the type of database migration</p>
        </div>

        {/* Show connection dropdowns only after migration type is selected */}
        {formData.migrationType && (
          <>
            {/* Read-only notice for edit mode */}
            {isEditMode && (
              <div className="info-box" style={{ marginBottom: '16px' }}>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="8" cy="8" r="6" />
                  <path d="M8 6v4M8 11h.01" strokeLinecap="round" />
                </svg>
                <div>
                  <strong>Connection Details</strong>
                  <p>Source and target connections cannot be changed after creation.</p>
                </div>
              </div>
            )}

            {/* Connections */}
            <div className="form-row">
              <div className="form-section">
                <label className="form-label">
                  Source Connection <span className="required">*</span>
                  {isEditMode && <span className="read-only-badge">Read-only</span>}
                </label>
                {loading ? (
                  <div className="loading-state">Loading connections...</div>
                ) : (
                  <Select
                    value={formData.sourceConnectionId || ''}
                    onChange={(value) => !isEditMode && updateFormData({ sourceConnectionId: Number(value) })}
                    options={[
                      { value: '', label: `Select ${migrationConfig?.sourceDb.toUpperCase()} connection` },
                      ...sourceConnections.map(conn => ({
                        value: conn.id,
                        label: `${conn.name} (${conn.database})`,
                      })),
                    ]}
                    disabled={isEditMode}
                  />
                )}
                {sourceConnections.length === 0 && !loading && (
                  <p className="form-error">
                    No {migrationConfig?.sourceDb.toUpperCase()} source connections available. 
                    Please create one first.
                  </p>
                )}
              </div>

              <div className="form-section">
                <label className="form-label">
                  Target Connection <span className="required">*</span>
                  {isEditMode && <span className="read-only-badge">Read-only</span>}
                </label>
                {loading ? (
                  <div className="loading-state">Loading connections...</div>
                ) : (
                  <Select
                    value={formData.targetConnectionId || ''}
                    onChange={(value) => !isEditMode && updateFormData({ targetConnectionId: Number(value) })}
                    options={[
                      { value: '', label: `Select ${migrationConfig?.targetDb.toUpperCase()} connection` },
                      ...targetConnections.map(conn => ({
                        value: conn.id,
                        label: `${conn.name} (${conn.database})`,
                      })),
                    ]}
                    disabled={isEditMode}
                  />
                )}
                {targetConnections.length === 0 && !loading && (
                  <p className="form-error">
                    No {migrationConfig?.targetDb.toUpperCase()} target connections available. 
                    Please create one first.
                  </p>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
