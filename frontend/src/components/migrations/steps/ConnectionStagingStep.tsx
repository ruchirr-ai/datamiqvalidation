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

// Database logo components
const BigQueryLogo = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
    {/* Blue hexagon */}
    <path d="M12 1.5L21.5 7v10L12 22.5 2.5 17V7L12 1.5z" fill="#4387F6"/>
    {/* Magnifying glass circle */}
    <circle cx="10.5" cy="10.5" r="4.5" stroke="white" strokeWidth="1.6" fill="none"/>
    {/* Handle */}
    <path d="M14 14l3.5 3.5" stroke="white" strokeWidth="1.8" strokeLinecap="round"/>
    {/* Bar chart inside glass */}
    <rect x="8.2" y="10" width="1.2" height="3" rx="0.3" fill="white"/>
    <rect x="10" y="8.5" width="1.2" height="4.5" rx="0.3" fill="white"/>
    <rect x="11.8" y="9.2" width="1.2" height="3.8" rx="0.3" fill="white"/>
  </svg>
);

const RedshiftLogo = () => (
  <img src="/redshift-icon.svg" alt="Redshift" width="24" height="24" style={{ objectFit: 'contain' }} />
);

const MongoDBLogo = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
    {/* Left half of leaf */}
    <path d="M12 2C12 2 7 7.5 7 13c0 3.5 2.5 6.5 5 7.5V2z" fill="#4FAA41"/>
    {/* Right half of leaf (darker) */}
    <path d="M12 2c0 0 5 5.5 5 11 0 3.5-2.5 6.5-5 7.5V2z" fill="#3F9A35"/>
    {/* Stem */}
    <path d="M11.5 20.5c0 0 .2 1.5.5 2 .3-.5.5-2 .5-2h-1z" fill="#C4B59A"/>
  </svg>
);

const DocumentDBLogo = () => (
  <img src="/documentdb-icon.svg" alt="DocumentDB" width="24" height="24" style={{ objectFit: 'contain' }} />
);

const getDbLogo = (db: string) => {
  switch (db.toLowerCase()) {
    case 'bigquery': return <BigQueryLogo />;
    case 'redshift': return <RedshiftLogo />;
    case 'mongodb': return <MongoDBLogo />;
    case 'documentdb': return <DocumentDBLogo />;
    default: return null;
  }
};

const getDbColor = (db: string) => {
  switch (db.toLowerCase()) {
    case 'bigquery': return '#4285F4';
    case 'redshift': return '#8C4FFF';
    case 'mongodb': return '#00684A';
    case 'documentdb': return '#C925D1';
    default: return '#6B7280';
  }
};

export const ConnectionStagingStep: React.FC<ConnectionStagingStepProps> = ({
  formData,
  updateFormData,
  isEditMode = false,
}) => {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchConnections();
  }, []);

  const fetchConnections = async () => {
    setLoading(true);
    try {
      const data = await listConnections();
      if (data && data.length > 0) {
        setConnections(data);
      } else {
        setConnections([]);
      }
    } catch (error) {
      console.error('Failed to fetch connections:', error);
      setConnections([]);
    } finally {
      setLoading(false);
    }
  };

  const getMigrationTypeConfig = () => {
    if (formData.migrationType === 'bigquery-redshift') {
      return { sourceDb: 'bigquery', targetDb: 'redshift', label: 'BigQuery to Redshift' };
    } else if (formData.migrationType === 'mongodb-documentdb') {
      return { sourceDb: 'mongodb', targetDb: 'documentdb', label: 'MongoDB to DocumentDB' };
    }
    return null;
  };

  const migrationConfig = getMigrationTypeConfig();

  const sourceConnections = migrationConfig
    ? connections.filter(c => c.type === 'source' && c.database.toLowerCase() === migrationConfig.sourceDb)
    : connections.filter(c => c.type === 'source');

  const targetConnections = migrationConfig
    ? connections.filter(c => c.type === 'target' && c.database.toLowerCase() === migrationConfig.targetDb)
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

        {/* Migration Type Cards */}
        <div className="form-section">
          <label className="form-label">
            Migration Type <span className="required">*</span>
          </label>
          <div className="migration-type-cards">
            <button
              type="button"
              className={`migration-type-card ${formData.migrationType === 'bigquery-redshift' ? 'selected' : ''}`}
              onClick={() => updateFormData({
                migrationType: 'bigquery-redshift',
                sourceConnectionId: null,
                targetConnectionId: null,
              })}
            >
              <div className="migration-type-logos">
                <BigQueryLogo />
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#9CA3AF" strokeWidth="1.5" className="migration-arrow-icon">
                  <path d="M3 8h10M10 5l3 3-3 3" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                <RedshiftLogo />
              </div>
              <span className="migration-type-label">BigQuery to Redshift</span>
            </button>

            <button
              type="button"
              className={`migration-type-card ${formData.migrationType === 'mongodb-documentdb' ? 'selected' : ''}`}
              onClick={() => updateFormData({
                migrationType: 'mongodb-documentdb',
                sourceConnectionId: null,
                targetConnectionId: null,
              })}
            >
              <div className="migration-type-logos">
                <MongoDBLogo />
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#9CA3AF" strokeWidth="1.5" className="migration-arrow-icon">
                  <path d="M3 8h10M10 5l3 3-3 3" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                <DocumentDBLogo />
              </div>
              <span className="migration-type-label">MongoDB to DocumentDB</span>
            </button>
          </div>
        </div>

        {/* Connection Selection */}
        {formData.migrationType && (
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
                  {migrationConfig && (
                    <div className="connection-card-db-info">
                      {getDbLogo(migrationConfig.sourceDb)}
                      <span style={{ color: getDbColor(migrationConfig.sourceDb) }}>
                        {migrationConfig.sourceDb === 'bigquery' ? 'BigQuery' : 'MongoDB'}
                      </span>
                    </div>
                  )}
                </div>
                <div className="connection-card-body">
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
                          icon: getDbLogo(conn.database),
                        })),
                      ]}
                      disabled={isEditMode}
                    />
                  )}
                  {sourceConnections.length === 0 && !loading && (
                    <p className="form-error">
                      No {migrationConfig?.sourceDb.toUpperCase()} source connections found. Create one in Connections page.
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
                  {migrationConfig && (
                    <div className="connection-card-db-info">
                      {getDbLogo(migrationConfig.targetDb)}
                      <span style={{ color: getDbColor(migrationConfig.targetDb) }}>
                        {migrationConfig.targetDb === 'redshift' ? 'Redshift' : 'DocumentDB'}
                      </span>
                    </div>
                  )}
                </div>
                <div className="connection-card-body">
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
                          icon: getDbLogo(conn.database),
                        })),
                      ]}
                      disabled={isEditMode}
                    />
                  )}
                  {targetConnections.length === 0 && !loading && (
                    <p className="form-error">
                      No {migrationConfig?.targetDb.toUpperCase()} target connections found. Create one in Connections page.
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
