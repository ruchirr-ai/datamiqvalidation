import React, { useState, useEffect } from 'react';
import { Input, Select } from '../../ui';
import { listConnections, Connection } from '../../../services/api';
import './StepStyles.css';
import './ConnectionStagingStep.css';

interface ConnectionStagingStepProps {
  formData: any;
  updateFormData: (updates: any) => void;
  isEditMode?: boolean;
}

const DB_OPTIONS = [
  { value: '', label: 'Select database type' },
  { value: 'bigquery', label: 'BigQuery' },
  { value: 'redshift', label: 'Amazon Redshift' },
  { value: 'postgresql', label: 'PostgreSQL' },
  { value: 'mysql', label: 'MySQL' },
  { value: 'oracle', label: 'Oracle' },
  { value: 'sqlserver', label: 'SQL Server' },
  { value: 'mongodb', label: 'MongoDB' },
  { value: 'documentdb', label: 'Amazon DocumentDB' },
  { value: 'db2', label: 'IBM Db2' },
  { value: 'sybase', label: 'SAP Sybase' },
];

export const ConnectionStagingStep: React.FC<ConnectionStagingStepProps> = ({
  formData,
  updateFormData,
  isEditMode = false,
}) => {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [loading, setLoading] = useState(true);
  const [sourceDbType, setSourceDbType] = useState<string>(formData.sourceDbType || '');
  const [targetDbType, setTargetDbType] = useState<string>(formData.targetDbType || '');

  useEffect(() => {
    fetchConnections();
  }, []);

  // Derive migrationType from db selections for backward compat
  useEffect(() => {
    if (sourceDbType === 'bigquery' && targetDbType === 'redshift') {
      updateFormData({ migrationType: 'bigquery-redshift', sourceDbType, targetDbType });
    } else if (sourceDbType === 'mongodb' && targetDbType === 'documentdb') {
      updateFormData({ migrationType: 'mongodb-documentdb', sourceDbType, targetDbType });
    } else if (sourceDbType && targetDbType) {
      updateFormData({ migrationType: `${sourceDbType}-${targetDbType}`, sourceDbType, targetDbType });
    }
  }, [sourceDbType, targetDbType]);

  const fetchConnections = async () => {
    setLoading(true);
    try {
      const data = await listConnections();
      setConnections(data && data.length > 0 ? data : []);
    } catch (error) {
      setConnections([]);
    } finally {
      setLoading(false);
    }
  };

  const sourceConnections = sourceDbType
    ? connections.filter(c => c.type === 'source' && c.database.toLowerCase() === sourceDbType)
    : connections.filter(c => c.type === 'source');

  const targetConnections = targetDbType
    ? connections.filter(c => c.type === 'target' && c.database.toLowerCase() === targetDbType)
    : connections.filter(c => c.type === 'target');

  const selectedSource = connections.find(c => c.id === formData.sourceConnectionId);
  const selectedTarget = connections.find(c => c.id === formData.targetConnectionId);

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
        </div>

        {/* Source and Target DB Type Selection */}
        <div className="form-section">
          <label className="form-label">
            Migration Type <span className="required">*</span>
          </label>
          <div className="db-type-selection">
            <div className="db-type-group">
              <label className="db-type-label">Source Database</label>
              <Select
                value={sourceDbType}
                onChange={(val) => {
                  setSourceDbType(val as string);
                  updateFormData({ sourceConnectionId: null });
                }}
                options={DB_OPTIONS}
                disabled={isEditMode}
              />
            </div>
            <div className="db-type-arrow">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#9CA3AF" strokeWidth="2">
                <path d="M5 12h14M15 8l4 4-4 4" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <div className="db-type-group">
              <label className="db-type-label">Target Database</label>
              <Select
                value={targetDbType}
                onChange={(val) => {
                  setTargetDbType(val as string);
                  updateFormData({ targetConnectionId: null });
                }}
                options={DB_OPTIONS}
                disabled={isEditMode}
              />
            </div>
          </div>
        </div>

        {/* Connection Selection */}
        {sourceDbType && targetDbType && (
          <>
            {isEditMode && (
              <div className="info-box" style={{ marginBottom: '0' }}>
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

            <div className="connection-flow">
              {/* Source Connection */}
              <div className="connection-card">
                <div className="connection-card-header">
                  <div className="connection-card-badge source">SOURCE</div>
                  <span style={{ fontSize: 13, color: '#6B7280' }}>{sourceDbType.charAt(0).toUpperCase() + sourceDbType.slice(1)}</span>
                </div>
                <div className="connection-card-body">
                  <label className="form-label">
                    Source Connection <span className="required">*</span>
                  </label>
                  {loading ? (
                    <div className="loading-state">Loading connections...</div>
                  ) : (
                    <Select
                      value={formData.sourceConnectionId || ''}
                      onChange={(value) => !isEditMode && updateFormData({ sourceConnectionId: Number(value) })}
                      options={[
                        { value: '', label: `Select ${sourceDbType.toUpperCase()} connection` },
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
                      No {sourceDbType.toUpperCase()} source connections found. Create one in Connections page.
                    </p>
                  )}
                  {selectedSource && (
                    <div className="connection-meta">
                      <span className={`connection-status-dot ${selectedSource.status === 'connected' ? 'online' : 'offline'}`} />
                      <span>{selectedSource.status === 'connected' ? 'Connected' : 'Disconnected'}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Flow Arrow */}
              <div className="connection-flow-arrow">
                <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                  <circle cx="20" cy="20" r="18" fill="#F3F4F6" stroke="#E5E7EB" strokeWidth="1"/>
                  <path d="M14 20h12M22 16l4 4-4 4" stroke="#6B7280" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>

              {/* Target Connection */}
              <div className="connection-card">
                <div className="connection-card-header">
                  <div className="connection-card-badge target">TARGET</div>
                  <span style={{ fontSize: 13, color: '#6B7280' }}>{targetDbType.charAt(0).toUpperCase() + targetDbType.slice(1)}</span>
                </div>
                <div className="connection-card-body">
                  <label className="form-label">
                    Target Connection <span className="required">*</span>
                  </label>
                  {loading ? (
                    <div className="loading-state">Loading connections...</div>
                  ) : (
                    <Select
                      value={formData.targetConnectionId || ''}
                      onChange={(value) => !isEditMode && updateFormData({ targetConnectionId: Number(value) })}
                      options={[
                        { value: '', label: `Select ${targetDbType.toUpperCase()} connection` },
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
                      No {targetDbType.toUpperCase()} target connections found. Create one in Connections page.
                    </p>
                  )}
                  {selectedTarget && (
                    <div className="connection-meta">
                      <span className={`connection-status-dot ${selectedTarget.status === 'connected' ? 'online' : 'offline'}`} />
                      <span>{selectedTarget.status === 'connected' ? 'Connected' : 'Disconnected'}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
