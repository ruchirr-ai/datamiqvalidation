import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Table, Badge, Modal, Input, Select, Alert } from '../../components/ui';
import { bqRedshiftApi, Migration, CreateMigrationRequest } from '../../services/bqRedshiftApi';
import './BQRedshiftMigrationsPage.css';

export const BQRedshiftMigrationsPage: React.FC = () => {
  const navigate = useNavigate();
  const [migrations, setMigrations] = useState<Migration[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Form state
  const [formData, setFormData] = useState<CreateMigrationRequest>({
    migration_name: '',
    pathway: 'A',
    source_project_id: '',
    source_dataset: '',
    source_tables: [],
    target_cluster: '',
    target_database: '',
    target_schema: 'public',
    gcs_bucket: '',
    gcs_path: '',
    s3_bucket: '',
    s3_path: ''
  });
  const [tablesInput, setTablesInput] = useState('');

  useEffect(() => {
    fetchMigrations();
  }, [filter]);

  const fetchMigrations = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await bqRedshiftApi.listMigrations(filter !== 'all' ? filter : undefined);
      setMigrations(data);
    } catch (err) {
      console.error('Failed to fetch migrations:', err);
      setError('Failed to load migrations. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateMigration = async () => {
    try {
      setCreating(true);
      setError(null);

      // Parse tables from comma-separated input
      const tables = tablesInput.split(',').map(t => t.trim()).filter(t => t);
      
      if (tables.length === 0) {
        setError('Please enter at least one table name');
        return;
      }

      const data: CreateMigrationRequest = {
        ...formData,
        source_tables: tables
      };

      await bqRedshiftApi.createMigration(data);
      setSuccess('Migration created successfully!');
      setShowCreateModal(false);
      
      // Reset form
      setFormData({
        migration_name: '',
        pathway: 'A',
        source_project_id: '',
        source_dataset: '',
        source_tables: [],
        target_cluster: '',
        target_database: '',
        target_schema: 'public',
        gcs_bucket: '',
        gcs_path: '',
        s3_bucket: '',
        s3_path: ''
      });
      setTablesInput('');
      
      // Refresh list
      fetchMigrations();
      
      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to create migration');
    } finally {
      setCreating(false);
    }
  };

  const handleStartMigration = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await bqRedshiftApi.startMigration(id);
      setSuccess('Migration started successfully!');
      fetchMigrations();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to start migration');
    }
  };

  const handleDeleteMigration = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this migration?')) {
      return;
    }
    try {
      await bqRedshiftApi.deleteMigration(id);
      setSuccess('Migration deleted successfully!');
      fetchMigrations();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to delete migration');
    }
  };

  const getStatusBadge = (status: string) => {
    const variants: Record<string, 'success' | 'warning' | 'error' | 'info'> = {
      completed: 'success',
      running: 'info',
      scheduled: 'info',
      paused: 'warning',
      failed: 'error',
      pending: 'warning',
      cancelled: 'error'
    };
    return <Badge variant={variants[status] || 'info'}>{status}</Badge>;
  };

  const getPathwayName = (pathway: string) => {
    const names: Record<string, string> = {
      A: 'GCP Native',
      B: 'AWS Native',
      C: 'Hybrid Sync',
      D: 'CLI/Legacy'
    };
    return names[pathway] || pathway;
  };

  const getPathwayDescription = (pathway: string) => {
    const descriptions: Record<string, string> = {
      A: 'BigQuery → GCS → S3 (Storage Transfer) → Redshift',
      B: 'BigQuery → Redshift (via AWS DMS)',
      C: 'BigQuery → GCS → S3 (DataSync) → Redshift',
      D: 'BigQuery → GCS → S3 (gsutil/aws cli) → Redshift'
    };
    return descriptions[pathway] || '';
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1>BigQuery → Redshift Migrations</h1>
          <p className="page-description">
            Manage large-scale data migrations with granular checkpointing and resumability
          </p>
        </div>
        <Button
          variant="primary"
          onClick={() => setShowCreateModal(true)}
        >
          Create Migration
        </Button>
      </div>

      {success && (
        <Alert variant="success" style={{ marginBottom: '16px' }}>
          {success}
        </Alert>
      )}

      {error && (
        <Alert variant="error" style={{ marginBottom: '16px' }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <div className="page-content">
        <div className="filters">
          <button
            className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
            onClick={() => setFilter('all')}
          >
            All
          </button>
          <button
            className={`filter-btn ${filter === 'pending' ? 'active' : ''}`}
            onClick={() => setFilter('pending')}
          >
            Pending
          </button>
          <button
            className={`filter-btn ${filter === 'running' ? 'active' : ''}`}
            onClick={() => setFilter('running')}
          >
            Running
          </button>
          <button
            className={`filter-btn ${filter === 'completed' ? 'active' : ''}`}
            onClick={() => setFilter('completed')}
          >
            Completed
          </button>
          <button
            className={`filter-btn ${filter === 'failed' ? 'active' : ''}`}
            onClick={() => setFilter('failed')}
          >
            Failed
          </button>
        </div>

        {loading ? (
          <div className="loading">Loading migrations...</div>
        ) : migrations.length === 0 ? (
          <div className="empty-state">
            <svg width="64" height="64" viewBox="0 0 64 64" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M16 32h32M32 16v32" strokeLinecap="round" strokeLinejoin="round"/>
              <rect x="8" y="8" width="20" height="20" rx="4"/>
              <rect x="36" y="36" width="20" height="20" rx="4"/>
            </svg>
            <h2>No Migrations Found</h2>
            <p>Create your first BigQuery to Redshift migration to get started</p>
            <Button variant="primary" onClick={() => setShowCreateModal(true)}>
              Create Migration
            </Button>
          </div>
        ) : (
          <Table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Pathway</th>
                <th>Status</th>
                <th>Stage</th>
                <th>Source</th>
                <th>Target</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {migrations.map((migration) => (
                <tr key={migration.id}>
                  <td style={{ fontWeight: 500 }}>{migration.migration_name}</td>
                  <td>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <span style={{ fontWeight: 500 }}>{getPathwayName(migration.pathway)}</span>
                      <span style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>
                        Path {migration.pathway}
                      </span>
                    </div>
                  </td>
                  <td>{getStatusBadge(migration.status)}</td>
                  <td>{migration.current_stage || '-'}</td>
                  <td>
                    <div style={{ fontSize: '13px' }}>
                      <div>{migration.source_project_id}</div>
                      <div style={{ color: 'var(--color-text-secondary)' }}>{migration.source_dataset}</div>
                    </div>
                  </td>
                  <td>
                    <div style={{ fontSize: '13px' }}>
                      <div>{migration.target_database}</div>
                      <div style={{ color: 'var(--color-text-secondary)' }}>{migration.target_schema}</div>
                    </div>
                  </td>
                  <td>{new Date(migration.created_at).toLocaleDateString()}</td>
                  <td>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      {migration.status === 'pending' && (
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={(e) => handleStartMigration(migration.id, e)}
                        >
                          Start
                        </Button>
                      )}
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          console.log(`Details page coming soon for migration ${migration.id}`);
                        }}
                      >
                        View
                      </Button>
                      {migration.status === 'pending' && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={(e) => handleDeleteMigration(migration.id, e)}
                        >
                          Delete
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </div>

      {/* Create Migration Modal */}
      {showCreateModal && (
        <Modal
          isOpen={showCreateModal}
          onClose={() => setShowCreateModal(false)}
          title="Create BigQuery → Redshift Migration"
          size="lg"
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* Migration Name */}
            <div>
              <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>
                Migration Name *
              </label>
              <Input
                value={formData.migration_name}
                onChange={(e) => setFormData({ ...formData, migration_name: e.target.value })}
                placeholder="e.g., Production Data Migration"
              />
            </div>

            {/* Pathway Selection */}
            <div>
              <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>
                Migration Pathway *
              </label>
              <Select
                value={formData.pathway}
                onChange={(e) => setFormData({ ...formData, pathway: e.target.value as any })}
              >
                <option value="A">Path A - GCP Native (Recommended)</option>
                <option value="B">Path B - AWS Native</option>
                <option value="C">Path C - Hybrid Sync</option>
                <option value="D">Path D - CLI/Legacy</option>
              </Select>
              <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginTop: '4px' }}>
                {getPathwayDescription(formData.pathway)}
              </p>
            </div>

            {/* Source Configuration */}
            <div style={{ padding: '16px', background: 'var(--color-bg-secondary)', borderRadius: '8px' }}>
              <h3 style={{ marginBottom: '16px', fontSize: '16px', fontWeight: 600 }}>Source (BigQuery)</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div>
                  <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>
                    GCP Project ID *
                  </label>
                  <Input
                    value={formData.source_project_id}
                    onChange={(e) => setFormData({ ...formData, source_project_id: e.target.value })}
                    placeholder="my-gcp-project"
                  />
                </div>
                <div>
                  <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>
                    Dataset *
                  </label>
                  <Input
                    value={formData.source_dataset}
                    onChange={(e) => setFormData({ ...formData, source_dataset: e.target.value })}
                    placeholder="production_data"
                  />
                </div>
                <div>
                  <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>
                    Tables (comma-separated) *
                  </label>
                  <Input
                    value={tablesInput}
                    onChange={(e) => setTablesInput(e.target.value)}
                    placeholder="users, orders, products"
                  />
                </div>
              </div>
            </div>

            {/* Target Configuration */}
            <div style={{ padding: '16px', background: 'var(--color-bg-secondary)', borderRadius: '8px' }}>
              <h3 style={{ marginBottom: '16px', fontSize: '16px', fontWeight: 600 }}>Target (Redshift)</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div>
                  <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>
                    Cluster Endpoint *
                  </label>
                  <Input
                    value={formData.target_cluster}
                    onChange={(e) => setFormData({ ...formData, target_cluster: e.target.value })}
                    placeholder="my-cluster.redshift.amazonaws.com"
                  />
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                  <div>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>
                      Database *
                    </label>
                    <Input
                      value={formData.target_database}
                      onChange={(e) => setFormData({ ...formData, target_database: e.target.value })}
                      placeholder="analytics"
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>
                      Schema *
                    </label>
                    <Input
                      value={formData.target_schema}
                      onChange={(e) => setFormData({ ...formData, target_schema: e.target.value })}
                      placeholder="public"
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Storage Configuration */}
            <div style={{ padding: '16px', background: 'var(--color-bg-secondary)', borderRadius: '8px' }}>
              <h3 style={{ marginBottom: '16px', fontSize: '16px', fontWeight: 600 }}>Storage</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                  <div>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>
                      GCS Bucket *
                    </label>
                    <Input
                      value={formData.gcs_bucket}
                      onChange={(e) => setFormData({ ...formData, gcs_bucket: e.target.value })}
                      placeholder="my-gcs-bucket"
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>
                      GCS Path *
                    </label>
                    <Input
                      value={formData.gcs_path}
                      onChange={(e) => setFormData({ ...formData, gcs_path: e.target.value })}
                      placeholder="migrations/prod-2026"
                    />
                  </div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                  <div>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>
                      S3 Bucket *
                    </label>
                    <Input
                      value={formData.s3_bucket}
                      onChange={(e) => setFormData({ ...formData, s3_bucket: e.target.value })}
                      placeholder="my-s3-bucket"
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>
                      S3 Path *
                    </label>
                    <Input
                      value={formData.s3_path}
                      onChange={(e) => setFormData({ ...formData, s3_path: e.target.value })}
                      placeholder="migrations/prod-2026"
                    />
                  </div>
                </div>
              </div>
            </div>

            {error && (
              <Alert variant="error" onClose={() => setError(null)}>
                {error}
              </Alert>
            )}

            {/* Actions */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '8px' }}>
              <Button
                variant="outline"
                onClick={() => setShowCreateModal(false)}
                disabled={creating}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={handleCreateMigration}
                disabled={creating}
              >
                {creating ? 'Creating...' : 'Create Migration'}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
