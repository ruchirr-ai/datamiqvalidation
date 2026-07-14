import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Badge, Alert, Modal, Input } from '../../components/ui';
import { useWorkspace } from '../../contexts/WorkspaceContext';
import './BQIcebergMigrationsPage.css';

// ---- Types ----

interface IcebergMigration {
  id: number;
  workspace_id: number;
  migration_name: string;
  pathway: 'A' | 'B' | 'C';
  destination_type: 'iceberg_s3' | 'iceberg_s3_tables';
  status: string;
  current_stage: string | null;
  progress_percentage: number;
  aws_region: string;
  glue_database_name: string;
  created_at: string | null;
  updated_at: string | null;
  // Detail fields (populated when editing)
  source_project_id?: string;
  source_dataset?: string;
  source_tables?: string[];
  s3_bucket?: string;
  s3_path_prefix?: string;
  table_bucket_arn?: string;
  s3_tables_namespace?: string;
  gcs_bucket?: string;
  gcs_path?: string;
  source_connection_id?: number;
}

interface CreateFormData {
  migration_name: string;
  pathway: 'A' | 'B' | 'C';
  destination_type: 'iceberg_s3' | 'iceberg_s3_tables';
  source_connection_id: string;
  source_project_id: string;
  source_dataset: string;
  source_tables_raw: string;
  aws_region: string;
  glue_database_name: string;
  s3_bucket: string;
  s3_path_prefix: string;
  table_bucket_arn: string;
  s3_tables_namespace: string;
  gcs_bucket: string;
  gcs_path: string;
  aws_access_key_id: string;
  aws_secret_access_key: string;
}

// ---- Helpers ----

const INITIAL_FORM: CreateFormData = {
  migration_name: '',
  pathway: 'A',
  destination_type: 'iceberg_s3',
  source_connection_id: '',
  source_project_id: '',
  source_dataset: '',
  source_tables_raw: '',
  aws_region: 'us-east-1',
  glue_database_name: '',
  s3_bucket: '',
  s3_path_prefix: 'iceberg/',
  table_bucket_arn: '',
  s3_tables_namespace: '',
  gcs_bucket: '',
  gcs_path: 'exports/',
  aws_access_key_id: '',
  aws_secret_access_key: '',
};

const STATUS_VARIANT: Record<string, 'success' | 'warning' | 'error' | 'info' | 'default'> = {
  completed: 'success',
  running: 'info',
  pending_review: 'warning',
  approved: 'info',
  pending: 'warning',
  paused: 'warning',
  failed: 'error',
  cancelled: 'error',
};

const STAGE_LABELS: Record<string, string> = {
  export: 'Exporting',
  transfer: 'Transferring',
  review: 'Awaiting Review',
  load: 'Loading',
};

const PATHWAY_LABELS: Record<string, string> = {
  A: 'GCS → S3 Transfer',
  B: 'DataSync (GCP VM)',
  C: 'Hybrid',
};

const DEST_LABELS: Record<string, string> = {
  iceberg_s3: 'Iceberg on S3',
  iceberg_s3_tables: 'S3 Tables',
};

function formatRelativeTime(dateStr: string | null): string {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr.endsWith('Z') ? dateStr : dateStr + 'Z');
    if (isNaN(d.getTime())) return dateStr;
    const diff = Date.now() - d.getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'Just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch {
    return dateStr;
  }
}

// ---- Main Component ----

export const BQIcebergMigrationsPage: React.FC = () => {
  const navigate = useNavigate();
  const { selectedWorkspaceName } = useWorkspace();

  const [migrations, setMigrations] = useState<IcebergMigration[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [destFilter, setDestFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [formData, setFormData] = useState<CreateFormData>(INITIAL_FORM);
  const [formError, setFormError] = useState<string | null>(null);

  // Source connections list for dropdown
  const [sourceConnections, setSourceConnections] = useState<{id: number; name: string}[]>([]);
  useEffect(() => {
    const token = localStorage.getItem('auth_token') || localStorage.getItem('access_token');
    fetch('/api/connections?type=source', { headers: { ...(token && { Authorization: `Bearer ${token}` }) } })
      .then(r => r.ok ? r.json() : { connections: [] })
      .then(d => setSourceConnections((d.connections || d || []).filter((c: any) => c.type === 'source' || c.database === 'bigquery')))
      .catch(() => {});
  }, []);

  // Edit modal state
  const [showEdit, setShowEdit] = useState(false);
  const [editingMigration, setEditingMigration] = useState<IcebergMigration | null>(null);
  const [editFormData, setEditFormData] = useState<CreateFormData>(INITIAL_FORM);
  const [editFormError, setEditFormError] = useState<string | null>(null);
  const [editSaving, setEditSaving] = useState(false);

  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' | 'info' } | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Auto-dismiss toast
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  const fetchMigrations = useCallback(async () => {
    try {
      setLoading(true);
      const params: Record<string, string> = {};
      if (statusFilter !== 'all') params.status = statusFilter;
      if (destFilter !== 'all') params.destination_type = destFilter;
      const qs = new URLSearchParams(params).toString();
      const url = `/api/migrations/bq-iceberg/list${qs ? `?${qs}` : ''}`;
      const token = localStorage.getItem('auth_token') || localStorage.getItem('access_token');
      const res = await fetch(url, {
        headers: { ...(token && { Authorization: `Bearer ${token}` }) },
      });
      if (!res.ok) throw new Error('Failed to load migrations');
      const data = await res.json();
      setMigrations(data.migrations || []);
    } catch (err: any) {
      setToast({ msg: err.message || 'Failed to load migrations', type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [statusFilter, destFilter]);

  useEffect(() => { fetchMigrations(); }, [fetchMigrations]);

  // Auto-poll every 3s when any migration is running or pending_review
  useEffect(() => {
    const hasActiveJob = migrations.some(m =>
      ['running', 'pending_review', 'approved'].includes(m.status)
    );
    if (!hasActiveJob) return;
    const interval = setInterval(() => { fetchMigrations(); }, 3000);
    return () => clearInterval(interval);
  }, [migrations, fetchMigrations]);

  // ---- Actions ----

  const handleCreate = async () => {
    setFormError(null);
    if (!formData.migration_name.trim()) return setFormError('Migration name is required');
    if (!formData.source_project_id.trim()) return setFormError('GCP Project ID is required');
    if (!formData.source_dataset.trim()) return setFormError('BQ Dataset is required');
    if (!formData.source_tables_raw.trim()) return setFormError('At least one table name is required');
    if (!formData.glue_database_name.trim()) return setFormError('Glue database name is required');
    if (!/^[a-z0-9_]+$/.test(formData.glue_database_name)) {
      return setFormError('Glue database name: lowercase letters, numbers, underscores only');
    }
    if (formData.destination_type === 'iceberg_s3' && !formData.s3_bucket.trim()) {
      return setFormError('S3 bucket is required for Iceberg on S3');
    }
    if (formData.destination_type === 'iceberg_s3_tables' && !formData.table_bucket_arn.trim()) {
      return setFormError('Table Bucket ARN is required for S3 Tables');
    }
    if (!formData.gcs_bucket.trim()) return setFormError('GCS bucket is required');

    try {
      setCreating(true);
      const token = localStorage.getItem('auth_token') || localStorage.getItem('access_token');
      const tables = formData.source_tables_raw.split(',').map(t => t.trim()).filter(Boolean);
      const body: Record<string, unknown> = {
        migration_name: formData.migration_name,
        pathway: formData.pathway,
        destination_type: formData.destination_type,
        source_project_id: formData.source_project_id,
        source_dataset: formData.source_dataset,
        source_tables: tables,
        aws_region: formData.aws_region,
        glue_database_name: formData.glue_database_name,
        gcs_bucket: formData.gcs_bucket,
        gcs_path: formData.gcs_path || undefined,
        export_format: 'PARQUET',
        compression: 'ZSTD',
      };
      if (formData.source_connection_id) body.source_connection_id = Number(formData.source_connection_id);
      if (formData.destination_type === 'iceberg_s3') {
        body.s3_bucket = formData.s3_bucket;
        if (formData.s3_path_prefix) body.s3_path_prefix = formData.s3_path_prefix;
      } else {
        body.table_bucket_arn = formData.table_bucket_arn;
        if (formData.s3_tables_namespace) body.s3_tables_namespace = formData.s3_tables_namespace;
      }
      if (formData.aws_access_key_id) body.aws_access_key_id = formData.aws_access_key_id;
      if (formData.aws_secret_access_key) body.aws_secret_access_key = formData.aws_secret_access_key;

      const res = await fetch('/api/migrations/bq-iceberg/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { Authorization: `Bearer ${token}` }),
        },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const detail = err.detail;
        let msg: string;
        if (typeof detail === 'string') {
          msg = detail;
        } else if (Array.isArray(detail)) {
          // Pydantic validation errors: [{loc, msg, type}]
          msg = detail.map((e: any) => `${e.loc?.slice(-1)[0] ?? 'field'}: ${e.msg}`).join('; ');
        } else if (detail && typeof detail === 'object') {
          msg = JSON.stringify(detail);
        } else {
          msg = 'Failed to create migration';
        }
        throw new Error(msg);
      }
      setShowCreate(false);
      setFormData(INITIAL_FORM);
      setToast({ msg: 'Migration created successfully', type: 'success' });
      fetchMigrations();
    } catch (err: any) {
      setFormError(err.message);
    } finally {
      setCreating(false);
    }
  };

  const callLifecycle = async (id: number, action: string) => {
    const token = localStorage.getItem('auth_token') || localStorage.getItem('access_token');
    const res = await fetch(`/api/migrations/bq-iceberg/${id}/${action}`, {
      method: 'POST',
      headers: { ...(token && { Authorization: `Bearer ${token}` }) },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Failed to ${action}`);
    }
  };

  const handleStart = async (m: IcebergMigration) => {
    try {
      await callLifecycle(m.id, 'start');
      setToast({ msg: `"${m.migration_name}" started`, type: 'success' });
      fetchMigrations();
    } catch (err: any) {
      setToast({ msg: err.message, type: 'error' });
    }
  };

  const handlePause = async (m: IcebergMigration) => {
    try {
      await callLifecycle(m.id, 'pause');
      setToast({ msg: `"${m.migration_name}" paused`, type: 'info' });
      fetchMigrations();
    } catch (err: any) {
      setToast({ msg: err.message, type: 'error' });
    }
  };

  const handleResume = async (m: IcebergMigration) => {
    try {
      await callLifecycle(m.id, 'resume');
      setToast({ msg: `"${m.migration_name}" resumed`, type: 'success' });
      fetchMigrations();
    } catch (err: any) {
      setToast({ msg: err.message, type: 'error' });
    }
  };

  const handleRetry = async (m: IcebergMigration) => {
    try {
      // Step 1: Call /retry to reset state (preserves export checkpoint)
      await callLifecycle(m.id, 'retry');
      // Step 2: Immediately start the migration (resumes from transfer stage)
      await callLifecycle(m.id, 'start');
      setToast({ msg: `"${m.migration_name}" retrying from transfer stage`, type: 'success' });
      fetchMigrations();
    } catch (err: any) {
      setToast({ msg: err.message, type: 'error' });
    }
  };

  const handleCancel = async (m: IcebergMigration) => {
    try {
      await callLifecycle(m.id, 'cancel');
      setToast({ msg: `"${m.migration_name}" cancelled`, type: 'info' });
      fetchMigrations();
    } catch (err: any) {
      setToast({ msg: err.message, type: 'error' });
    }
  };

  const confirmDelete = async () => {
    if (deleteConfirmId === null) return;
    try {
      setDeleting(true);
      const token = localStorage.getItem('auth_token') || localStorage.getItem('access_token');
      const res = await fetch(`/api/migrations/bq-iceberg/${deleteConfirmId}`, {
        method: 'DELETE',
        headers: { ...(token && { Authorization: `Bearer ${token}` }) },
      });
      if (!res.ok) throw new Error('Failed to delete migration');
      setToast({ msg: 'Migration deleted', type: 'success' });
      setDeleteConfirmId(null);
      fetchMigrations();
    } catch (err: any) {
      setToast({ msg: err.message, type: 'error' });
    } finally {
      setDeleting(false);
    }
  };

  // ---- Edit handlers ----

  const handleEditOpen = async (m: IcebergMigration) => {
    // Fetch full detail to get all fields (list API returns a subset)
    try {
      const token = localStorage.getItem('auth_token') || localStorage.getItem('access_token');
      const res = await fetch(`/api/migrations/bq-iceberg/${m.id}`, {
        headers: { ...(token && { Authorization: `Bearer ${token}` }) },
      });
      const detail: IcebergMigration = res.ok ? await res.json() : m;
      setEditingMigration(detail);
      setEditFormData({
        migration_name: detail.migration_name,
        pathway: detail.pathway,
        destination_type: detail.destination_type,
        source_connection_id: detail.source_connection_id ? String(detail.source_connection_id) : '',
        source_project_id: detail.source_project_id || '',
        source_dataset: detail.source_dataset || '',
        source_tables_raw: Array.isArray(detail.source_tables)
          ? detail.source_tables.join(', ')
          : '',
        aws_region: detail.aws_region,
        glue_database_name: detail.glue_database_name,
        s3_bucket: detail.s3_bucket || '',
        s3_path_prefix: detail.s3_path_prefix || 'iceberg/',
        table_bucket_arn: detail.table_bucket_arn || '',
        s3_tables_namespace: detail.s3_tables_namespace || '',
        gcs_bucket: detail.gcs_bucket || '',
        gcs_path: detail.gcs_path || 'exports/',
        aws_access_key_id: '',
        aws_secret_access_key: '',
      });
    } catch {
      // Fallback to what we have
      setEditingMigration(m);
      setEditFormData({
        migration_name: m.migration_name,
        pathway: m.pathway,
        destination_type: m.destination_type,
        source_connection_id: '',
        source_project_id: '',
        source_dataset: '',
        source_tables_raw: '',
        aws_region: m.aws_region,
        glue_database_name: m.glue_database_name,
        s3_bucket: '',
        s3_path_prefix: 'iceberg/',
        table_bucket_arn: '',
        s3_tables_namespace: '',
        gcs_bucket: '',
        gcs_path: 'exports/',
        aws_access_key_id: '',
        aws_secret_access_key: '',
      });
    }
    setEditFormError(null);
    setShowEdit(true);
  };

  const handleEditSave = async () => {
    if (!editingMigration) return;
    setEditFormError(null);
    if (!editFormData.migration_name.trim()) return setEditFormError('Migration name is required');
    if (!editFormData.source_project_id.trim()) return setEditFormError('GCP Project ID is required');
    if (!editFormData.source_dataset.trim()) return setEditFormError('BQ Dataset is required');
    if (!editFormData.source_tables_raw.trim()) return setEditFormError('At least one table name is required');
    if (!editFormData.glue_database_name.trim()) return setEditFormError('Glue database name is required');
    if (!/^[a-z0-9_]+$/.test(editFormData.glue_database_name)) {
      return setEditFormError('Glue database name: lowercase letters, numbers, underscores only');
    }
    if (editFormData.destination_type === 'iceberg_s3' && !editFormData.s3_bucket.trim()) {
      return setEditFormError('S3 bucket is required for Iceberg on S3');
    }
    if (editFormData.destination_type === 'iceberg_s3_tables' && !editFormData.table_bucket_arn.trim()) {
      return setEditFormError('Table Bucket ARN is required for S3 Tables');
    }
    if (!editFormData.gcs_bucket.trim()) return setEditFormError('GCS bucket is required');

    try {
      setEditSaving(true);
      const token = localStorage.getItem('auth_token') || localStorage.getItem('access_token');
      const tables = editFormData.source_tables_raw.split(',').map(t => t.trim()).filter(Boolean);
      const body: Record<string, unknown> = {
        migration_name: editFormData.migration_name,
        pathway: editFormData.pathway,
        destination_type: editFormData.destination_type,
        source_project_id: editFormData.source_project_id,
        source_dataset: editFormData.source_dataset,
        source_tables: tables,
        aws_region: editFormData.aws_region,
        glue_database_name: editFormData.glue_database_name,
        gcs_bucket: editFormData.gcs_bucket,
        gcs_path: editFormData.gcs_path || undefined,
      };
      if (editFormData.destination_type === 'iceberg_s3') {
        body.s3_bucket = editFormData.s3_bucket;
        if (editFormData.s3_path_prefix) body.s3_path_prefix = editFormData.s3_path_prefix;
      } else {
        body.table_bucket_arn = editFormData.table_bucket_arn;
        if (editFormData.s3_tables_namespace) body.s3_tables_namespace = editFormData.s3_tables_namespace;
      }
      if (editFormData.aws_access_key_id) body.aws_access_key_id = editFormData.aws_access_key_id;
      if (editFormData.aws_secret_access_key) body.aws_secret_access_key = editFormData.aws_secret_access_key;

      const res = await fetch(`/api/migrations/bq-iceberg/${editingMigration.id}/update`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { Authorization: `Bearer ${token}` }),
        },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const detail = err.detail;
        let msg: string;
        if (typeof detail === 'string') {
          msg = detail;
        } else if (Array.isArray(detail)) {
          msg = detail.map((e: any) => `${e.loc?.slice(-1)[0] ?? 'field'}: ${e.msg}`).join('; ');
        } else if (detail && typeof detail === 'object') {
          msg = JSON.stringify(detail);
        } else {
          msg = 'Failed to update migration';
        }
        throw new Error(msg);
      }
      setShowEdit(false);
      setEditingMigration(null);
      setToast({ msg: 'Migration updated successfully', type: 'success' });
      fetchMigrations();
    } catch (err: any) {
      setEditFormError(err.message);
    } finally {
      setEditSaving(false);
    }
  };

  // ---- Derived state ----

  const filtered = migrations.filter(m =>
    !searchQuery || m.migration_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // ---- Render ----

  return (
    <div className="bqi-page">

      {/* Toast */}
      {toast && (
        <div className={`bqi-toast bqi-toast--${toast.type}`}>
          {toast.msg}
          <button className="bqi-toast__close" onClick={() => setToast(null)} aria-label="Dismiss">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 3l8 8M11 3l-8 8" strokeLinecap="round"/>
            </svg>
          </button>
        </div>
      )}

      {/* Page Header */}
      <div className="bqi-header">
        <div className="bqi-header__left">
          <div className="bqi-header__title-row">
            <svg className="bqi-header__icon" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
              <path d="M4 10h12M13 6l4 4-4 4" strokeLinecap="round" strokeLinejoin="round"/>
              <rect x="2" y="5" width="6" height="10" rx="2"/>
            </svg>
            <h1 className="bqi-header__title">BigQuery → Iceberg</h1>
            {selectedWorkspaceName && (
              <span className="bqi-header__workspace">— {selectedWorkspaceName}</span>
            )}
          </div>
          <p className="bqi-header__desc">
            Migrate BigQuery datasets to Apache Iceberg on S3 or AWS S3 Tables
          </p>
        </div>
        <Button variant="primary" onClick={() => { setFormData(INITIAL_FORM); setFormError(null); setShowCreate(true); }}>
          + New Migration
        </Button>
      </div>

      {/* Filters Bar */}
      <div className="bqi-filters">
        <div className="bqi-filters__left">
          <div className="bqi-filters__group">
            {['all', 'pending', 'running', 'pending_review', 'approved', 'completed', 'failed', 'cancelled'].map(s => (
              <button
                key={s}
                className={`bqi-filter-btn ${statusFilter === s ? 'bqi-filter-btn--active' : ''}`}
                onClick={() => setStatusFilter(s)}
              >
                {s === 'all' ? 'All' : s === 'pending_review' ? 'Pending Review' : s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>
          <div className="bqi-filters__dest">
            <select
              className="bqi-dest-select"
              value={destFilter}
              onChange={e => setDestFilter(e.target.value)}
              aria-label="Filter by destination type"
            >
              <option value="all">All destinations</option>
              <option value="iceberg_s3">Iceberg on S3</option>
              <option value="iceberg_s3_tables">S3 Tables</option>
            </select>
          </div>
        </div>
        <div className="bqi-search">
          <svg width="15" height="15" viewBox="0 0 15 15" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <circle cx="6.5" cy="6.5" r="4.5"/>
            <path d="M10 10l3 3" strokeLinecap="round"/>
          </svg>
          <input
            type="text"
            placeholder="Search migrations…"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="bqi-search__input"
            aria-label="Search migrations"
          />
        </div>
      </div>

      {/* Table */}
      <div className="bqi-table-wrap">
        {loading ? (
          <div className="bqi-state bqi-state--loading">
            <div className="bqi-spinner" aria-label="Loading" />
            <span>Loading migrations…</span>
          </div>
        ) : filtered.length === 0 ? (
          <div className="bqi-state bqi-state--empty">
            <svg width="52" height="52" viewBox="0 0 52 52" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
              <rect x="6" y="14" width="40" height="28" rx="4"/>
              <path d="M14 26h24M22 20l4 6 4-6" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <h3>No migrations found</h3>
            <p>
              {searchQuery
                ? `No results for "${searchQuery}"`
                : statusFilter !== 'all' || destFilter !== 'all'
                  ? 'Try adjusting your filters'
                  : 'Create your first BigQuery to Iceberg migration'}
            </p>
            {!searchQuery && statusFilter === 'all' && destFilter === 'all' && (
              <Button variant="primary" onClick={() => { setFormData(INITIAL_FORM); setFormError(null); setShowCreate(true); }}>
                Create Migration
              </Button>
            )}
          </div>
        ) : (
          <table className="bqi-table" aria-label="Iceberg migrations">
            <thead>
              <tr>
                <th>Name</th>
                <th>Destination</th>
                <th>Pathway</th>
                <th>Region / Glue DB</th>
                <th>Status</th>
                <th>Stage</th>
                <th>Progress</th>
                <th>Updated</th>
                <th aria-label="Actions"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(m => (
                <tr
                  key={m.id}
                  className="bqi-table__row"
                  onClick={() => navigate(`/migrations/bq-iceberg/${m.id}`)}
                >
                  <td className="bqi-table__name-cell">
                    <span className="bqi-table__name">{m.migration_name}</span>
                    <span className="bqi-table__id">#{m.id}</span>
                  </td>
                  <td>
                    <span className={`bqi-dest-badge bqi-dest-badge--${m.destination_type}`}>
                      {DEST_LABELS[m.destination_type] ?? m.destination_type}
                    </span>
                  </td>
                  <td>
                    <span className="bqi-pathway-badge">Path {m.pathway}</span>
                    <span className="bqi-pathway-label">{PATHWAY_LABELS[m.pathway]}</span>
                  </td>
                  <td>
                    <div className="bqi-region-cell">
                      <span className="bqi-region-cell__region">{m.aws_region}</span>
                      <span className="bqi-region-cell__db">{m.glue_database_name}</span>
                    </div>
                  </td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                      <Badge variant={(STATUS_VARIANT[m.status] ?? 'default') as any}>
                        {m.status === 'pending_review' ? 'Pending Review' : m.status}
                      </Badge>
                      {m.status === 'approved' && (
                        <span className="bqi-ready-badge" title="Structure approved — ready to begin loading data">
                          Ready to load
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="bqi-table__stage">
                    {m.current_stage ? (STAGE_LABELS[m.current_stage] ?? m.current_stage) : '—'}
                  </td>
                  <td className="bqi-table__progress-cell">
                    {m.status === 'running' || m.progress_percentage > 0 ? (
                      <div className="bqi-progress" title={`${m.progress_percentage}%`}>
                        <div className="bqi-progress__bar">
                          <div className="bqi-progress__fill" style={{ width: `${m.progress_percentage}%` }} />
                        </div>
                        <span className="bqi-progress__label">{m.progress_percentage}%</span>
                      </div>
                    ) : '—'}
                  </td>
                  <td className="bqi-table__ts">{formatRelativeTime(m.updated_at)}</td>
                  <td onClick={e => e.stopPropagation()}>
                    <div className="bqi-row-actions">
                      {(m.status === 'pending' || m.status === 'approved') && (
                        <button
                          className="bqi-action-btn bqi-action-btn--primary"
                          onClick={() => handleStart(m)}
                          title={m.status === 'approved' ? 'Structure approved — click to begin loading data' : 'Start'}
                        >
                          <svg width="13" height="13" viewBox="0 0 13 13" fill="currentColor" aria-hidden="true">
                            <path d="M3 2l8 4.5L3 11V2z"/>
                          </svg>
                          {m.status === 'approved' ? 'Start Load' : 'Start'}
                        </button>
                      )}
                      {m.status === 'running' && (
                        <button className="bqi-action-btn" onClick={() => handlePause(m)} title="Pause">
                          <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                            <rect x="3" y="2" width="2.5" height="9"/>
                            <rect x="7.5" y="2" width="2.5" height="9"/>
                          </svg>
                          Pause
                        </button>
                      )}
                      {m.status === 'paused' && (
                        <button className="bqi-action-btn bqi-action-btn--primary" onClick={() => handleResume(m)} title="Resume">
                          <svg width="13" height="13" viewBox="0 0 13 13" fill="currentColor" aria-hidden="true">
                            <path d="M3 2l8 4.5L3 11V2z"/>
                          </svg>
                          Resume
                        </button>
                      )}
                      {m.status === 'failed' && (
                        <button
                          className="bqi-action-btn bqi-action-btn--primary"
                          onClick={() => handleRetry(m)}
                          title="Retry from last failed stage — export will not be repeated"
                        >
                          <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
                            <path d="M2 7a5 5 0 1 0 1-3M2 4V1M2 4h3" strokeLinecap="round" strokeLinejoin="round"/>
                          </svg>
                          Retry
                        </button>
                      )}
                      {m.status === 'pending_review' && (
                        <button
                          className="bqi-action-btn bqi-action-btn--review"
                          onClick={() => navigate(`/migrations/bq-iceberg/${m.id}/structure-review`)}
                          title="Review structure"
                        >
                          <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
                            <path d="M2 4h9M2 7h6M2 10h4" strokeLinecap="round"/>
                          </svg>
                          Review
                        </button>
                      )}
                      {(m.status === 'running' || m.status === 'paused') && (
                        <button className="bqi-action-btn bqi-action-btn--danger" onClick={() => handleCancel(m)} title="Cancel">
                          <svg width="13" height="13" viewBox="0 0 13 13" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
                            <circle cx="6.5" cy="6.5" r="4.5"/>
                            <path d="M4.5 4.5l4 4M8.5 4.5l-4 4" strokeLinecap="round"/>
                          </svg>
                          Cancel
                        </button>
                      )}
                      {(['pending', 'failed', 'cancelled'] as string[]).includes(m.status) && (
                        <button
                          className="bqi-action-btn bqi-action-btn--icon"
                          onClick={() => handleEditOpen(m)}
                          title="Edit migration"
                          aria-label="Edit migration"
                        >
                          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
                            <path d="M9.5 2.5l2 2L4 12H2v-2L9.5 2.5z" strokeLinecap="round" strokeLinejoin="round"/>
                          </svg>
                        </button>
                      )}
                      {!['running'].includes(m.status) && (
                        <button className="bqi-action-btn bqi-action-btn--icon" onClick={() => setDeleteConfirmId(m.id)} title="Delete" aria-label="Delete migration">
                          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
                            <path d="M2 3.5h10M5.5 3.5v-1.5h3v1.5M5 3.5l.5 7.5h3l.5-7.5" strokeLinecap="round" strokeLinejoin="round"/>
                          </svg>
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="bqi-footer">
        <span className="bqi-footer__count">
          {filtered.length} migration{filtered.length !== 1 ? 's' : ''}
          {searchQuery || statusFilter !== 'all' || destFilter !== 'all' ? ` (filtered from ${migrations.length})` : ''}
        </span>
      </div>

      {/* Create Migration Modal */}
      {showCreate && (
        <Modal isOpen={showCreate} onClose={() => setShowCreate(false)} title="Create BQ → Iceberg Migration" size="lg">
          <div className="bqi-form">

            {formError && (
              <Alert variant="error" onClose={() => setFormError(null)}>
                {formError}
              </Alert>
            )}

            {/* Basic */}
            <div className="bqi-form__row">
              <label className="bqi-form__label">Migration Name *</label>
              <Input
                value={formData.migration_name}
                onChange={e => setFormData(p => ({ ...p, migration_name: e.target.value }))}
                placeholder="e.g., prod-analytics-iceberg"
              />
            </div>

            <div className="bqi-form__two-col">
              <div className="bqi-form__row">
                <label className="bqi-form__label">Pathway *</label>
                <select className="bqi-form__select" value={formData.pathway} onChange={e => setFormData(p => ({ ...p, pathway: e.target.value as 'A' | 'B' | 'C' }))}>
                  <option value="A">Path A — GCS → S3 Storage Transfer</option>
                  <option value="B">Path B — DataSync (GCP VM)</option>
                  <option value="C">Path C — Hybrid</option>
                </select>
              </div>
              <div className="bqi-form__row">
                <label className="bqi-form__label">Destination Type *</label>
                <select className="bqi-form__select" value={formData.destination_type} onChange={e => setFormData(p => ({ ...p, destination_type: e.target.value as 'iceberg_s3' | 'iceberg_s3_tables' }))}>
                  <option value="iceberg_s3">Apache Iceberg on S3</option>
                  <option value="iceberg_s3_tables">AWS S3 Tables (Managed)</option>
                </select>
              </div>
            </div>

            {/* Source */}
            <div className="bqi-form__section-label">Source — BigQuery</div>
            <div className="bqi-form__row">
              <label className="bqi-form__label">BigQuery Connection <span style={{color:'var(--color-text-secondary)', fontWeight:400}}>(provides GCP credentials)</span></label>
              <select
                className="bqi-form__select"
                value={formData.source_connection_id}
                onChange={e => setFormData(p => ({ ...p, source_connection_id: e.target.value }))}
              >
                <option value="">— Select a BigQuery connection —</option>
                {sourceConnections.map(c => (
                  <option key={c.id} value={String(c.id)}>{c.name}</option>
                ))}
              </select>
            </div>
            <div className="bqi-form__two-col">
              <div className="bqi-form__row">
                <label className="bqi-form__label">GCP Project ID *</label>
                <Input value={formData.source_project_id} onChange={e => setFormData(p => ({ ...p, source_project_id: e.target.value }))} placeholder="my-gcp-project" />
              </div>
              <div className="bqi-form__row">
                <label className="bqi-form__label">Dataset *</label>
                <Input value={formData.source_dataset} onChange={e => setFormData(p => ({ ...p, source_dataset: e.target.value }))} placeholder="production_data" />
              </div>
            </div>
            <div className="bqi-form__row">
              <label className="bqi-form__label">Tables (comma-separated) *</label>
              <Input value={formData.source_tables_raw} onChange={e => setFormData(p => ({ ...p, source_tables_raw: e.target.value }))} placeholder="orders, users, events" />
            </div>

            {/* Target */}
            <div className="bqi-form__section-label">Target — AWS</div>
            <div className="bqi-form__two-col">
              <div className="bqi-form__row">
                <label className="bqi-form__label">AWS Region *</label>
                <Input value={formData.aws_region} onChange={e => setFormData(p => ({ ...p, aws_region: e.target.value }))} placeholder="us-east-1" />
              </div>
              <div className="bqi-form__row">
                <label className="bqi-form__label">Glue Database Name *</label>
                <Input value={formData.glue_database_name} onChange={e => setFormData(p => ({ ...p, glue_database_name: e.target.value }))} placeholder="analytics_iceberg" />
              </div>
            </div>

            {formData.destination_type === 'iceberg_s3' ? (
              <div className="bqi-form__two-col">
                <div className="bqi-form__row">
                  <label className="bqi-form__label">S3 Bucket *</label>
                  <Input value={formData.s3_bucket} onChange={e => setFormData(p => ({ ...p, s3_bucket: e.target.value }))} placeholder="my-iceberg-bucket" />
                </div>
                <div className="bqi-form__row">
                  <label className="bqi-form__label">S3 Path Prefix</label>
                  <Input value={formData.s3_path_prefix} onChange={e => setFormData(p => ({ ...p, s3_path_prefix: e.target.value }))} placeholder="iceberg/" />
                </div>
              </div>
            ) : (
              <div className="bqi-form__two-col">
                <div className="bqi-form__row">
                  <label className="bqi-form__label">Table Bucket ARN *</label>
                  <Input value={formData.table_bucket_arn} onChange={e => setFormData(p => ({ ...p, table_bucket_arn: e.target.value }))} placeholder="arn:aws:s3tables:us-east-1:123456789012:bucket/my-bucket" />
                </div>
                <div className="bqi-form__row">
                  <label className="bqi-form__label">Namespace</label>
                  <Input value={formData.s3_tables_namespace} onChange={e => setFormData(p => ({ ...p, s3_tables_namespace: e.target.value }))} placeholder="analytics_ns" />
                </div>
              </div>
            )}

            {/* Intermediate */}
            <div className="bqi-form__section-label">Intermediate Storage — GCS</div>
            <div className="bqi-form__two-col">
              <div className="bqi-form__row">
                <label className="bqi-form__label">GCS Bucket *</label>
                <Input value={formData.gcs_bucket} onChange={e => setFormData(p => ({ ...p, gcs_bucket: e.target.value }))} placeholder="my-export-bucket" />
              </div>
              <div className="bqi-form__row">
                <label className="bqi-form__label">GCS Path</label>
                <Input value={formData.gcs_path} onChange={e => setFormData(p => ({ ...p, gcs_path: e.target.value }))} placeholder="exports/" />
              </div>
            </div>

            {/* AWS Credentials */}
            <div className="bqi-form__section-label">AWS Credentials (optional — uses IAM role if omitted)</div>
            <div className="bqi-form__two-col">
              <div className="bqi-form__row">
                <label className="bqi-form__label">Access Key ID</label>
                <Input value={formData.aws_access_key_id} onChange={e => setFormData(p => ({ ...p, aws_access_key_id: e.target.value }))} placeholder="AKIA…" autoComplete="off" />
              </div>
              <div className="bqi-form__row">
                <label className="bqi-form__label">Secret Access Key</label>
                <Input type="password" value={formData.aws_secret_access_key} onChange={e => setFormData(p => ({ ...p, aws_secret_access_key: e.target.value }))} placeholder="••••••••" autoComplete="new-password" />
              </div>
            </div>

            <div className="bqi-form__footer">
              <Button variant="outline" onClick={() => setShowCreate(false)} disabled={creating}>Cancel</Button>
              <Button variant="primary" onClick={handleCreate} disabled={creating}>
                {creating ? 'Creating…' : 'Create Migration'}
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Edit Migration Modal */}
      {showEdit && editingMigration && (
        <Modal
          isOpen={showEdit}
          onClose={() => { setShowEdit(false); setEditingMigration(null); }}
          title={`Edit Migration — ${editingMigration.migration_name}`}
          size="lg"
        >
          <div className="bqi-form">
            {editFormError && (
              <Alert variant="error" onClose={() => setEditFormError(null)}>
                {editFormError}
              </Alert>
            )}

            {/* Basic */}
            <div className="bqi-form__row">
              <label className="bqi-form__label">Migration Name *</label>
              <Input
                value={editFormData.migration_name}
                onChange={e => setEditFormData(p => ({ ...p, migration_name: e.target.value }))}
                placeholder="e.g., prod-analytics-iceberg"
              />
            </div>

            <div className="bqi-form__two-col">
              <div className="bqi-form__row">
                <label className="bqi-form__label">Pathway *</label>
                <select className="bqi-form__select" value={editFormData.pathway} onChange={e => setEditFormData(p => ({ ...p, pathway: e.target.value as 'A' | 'B' | 'C' }))}>
                  <option value="A">Path A — GCS → S3 Storage Transfer</option>
                  <option value="B">Path B — DataSync (GCP VM)</option>
                  <option value="C">Path C — Hybrid</option>
                </select>
              </div>
              <div className="bqi-form__row">
                <label className="bqi-form__label">Destination Type *</label>
                <select className="bqi-form__select" value={editFormData.destination_type} onChange={e => setEditFormData(p => ({ ...p, destination_type: e.target.value as 'iceberg_s3' | 'iceberg_s3_tables' }))}>
                  <option value="iceberg_s3">Apache Iceberg on S3</option>
                  <option value="iceberg_s3_tables">AWS S3 Tables (Managed)</option>
                </select>
              </div>
            </div>

            {/* Source */}
            <div className="bqi-form__section-label">Source — BigQuery</div>
            <div className="bqi-form__two-col">
              <div className="bqi-form__row">
                <label className="bqi-form__label">GCP Project ID *</label>
                <Input value={editFormData.source_project_id} onChange={e => setEditFormData(p => ({ ...p, source_project_id: e.target.value }))} placeholder="my-gcp-project" />
              </div>
              <div className="bqi-form__row">
                <label className="bqi-form__label">Dataset *</label>
                <Input value={editFormData.source_dataset} onChange={e => setEditFormData(p => ({ ...p, source_dataset: e.target.value }))} placeholder="production_data" />
              </div>
            </div>
            <div className="bqi-form__row">
              <label className="bqi-form__label">Tables (comma-separated) *</label>
              <Input value={editFormData.source_tables_raw} onChange={e => setEditFormData(p => ({ ...p, source_tables_raw: e.target.value }))} placeholder="orders, users, events" />
            </div>

            {/* Target */}
            <div className="bqi-form__section-label">Target — AWS</div>
            <div className="bqi-form__two-col">
              <div className="bqi-form__row">
                <label className="bqi-form__label">AWS Region *</label>
                <Input value={editFormData.aws_region} onChange={e => setEditFormData(p => ({ ...p, aws_region: e.target.value }))} placeholder="us-east-1" />
              </div>
              <div className="bqi-form__row">
                <label className="bqi-form__label">Glue Database Name *</label>
                <Input value={editFormData.glue_database_name} onChange={e => setEditFormData(p => ({ ...p, glue_database_name: e.target.value }))} placeholder="analytics_iceberg" />
              </div>
            </div>

            {editFormData.destination_type === 'iceberg_s3' ? (
              <div className="bqi-form__two-col">
                <div className="bqi-form__row">
                  <label className="bqi-form__label">S3 Bucket *</label>
                  <Input value={editFormData.s3_bucket} onChange={e => setEditFormData(p => ({ ...p, s3_bucket: e.target.value }))} placeholder="my-iceberg-bucket" />
                </div>
                <div className="bqi-form__row">
                  <label className="bqi-form__label">S3 Path Prefix</label>
                  <Input value={editFormData.s3_path_prefix} onChange={e => setEditFormData(p => ({ ...p, s3_path_prefix: e.target.value }))} placeholder="iceberg/" />
                </div>
              </div>
            ) : (
              <div className="bqi-form__two-col">
                <div className="bqi-form__row">
                  <label className="bqi-form__label">Table Bucket ARN *</label>
                  <Input value={editFormData.table_bucket_arn} onChange={e => setEditFormData(p => ({ ...p, table_bucket_arn: e.target.value }))} placeholder="arn:aws:s3tables:us-east-1:123456789012:bucket/my-bucket" />
                </div>
                <div className="bqi-form__row">
                  <label className="bqi-form__label">Namespace</label>
                  <Input value={editFormData.s3_tables_namespace} onChange={e => setEditFormData(p => ({ ...p, s3_tables_namespace: e.target.value }))} placeholder="analytics_ns" />
                </div>
              </div>
            )}

            {/* Intermediate */}
            <div className="bqi-form__section-label">Intermediate Storage — GCS</div>
            <div className="bqi-form__two-col">
              <div className="bqi-form__row">
                <label className="bqi-form__label">GCS Bucket *</label>
                <Input value={editFormData.gcs_bucket} onChange={e => setEditFormData(p => ({ ...p, gcs_bucket: e.target.value }))} placeholder="my-export-bucket" />
              </div>
              <div className="bqi-form__row">
                <label className="bqi-form__label">GCS Path</label>
                <Input value={editFormData.gcs_path} onChange={e => setEditFormData(p => ({ ...p, gcs_path: e.target.value }))} placeholder="exports/" />
              </div>
            </div>

            {/* AWS Credentials */}
            <div className="bqi-form__section-label">AWS Credentials (optional — uses IAM role if omitted)</div>
            <div className="bqi-form__two-col">
              <div className="bqi-form__row">
                <label className="bqi-form__label">Access Key ID</label>
                <Input value={editFormData.aws_access_key_id} onChange={e => setEditFormData(p => ({ ...p, aws_access_key_id: e.target.value }))} placeholder="AKIA…" autoComplete="off" />
              </div>
              <div className="bqi-form__row">
                <label className="bqi-form__label">Secret Access Key</label>
                <Input type="password" value={editFormData.aws_secret_access_key} onChange={e => setEditFormData(p => ({ ...p, aws_secret_access_key: e.target.value }))} placeholder="••••••••" autoComplete="new-password" />
              </div>
            </div>

            <div className="bqi-form__footer">
              <Button variant="outline" onClick={() => { setShowEdit(false); setEditingMigration(null); }} disabled={editSaving}>Cancel</Button>
              <Button variant="primary" onClick={handleEditSave} disabled={editSaving}>
                {editSaving ? 'Saving…' : 'Save Changes'}
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Delete Confirmation */}
      {deleteConfirmId !== null && (
        <div className="bqi-confirm-overlay" onClick={() => setDeleteConfirmId(null)}>
          <div className="bqi-confirm" onClick={e => e.stopPropagation()} role="dialog" aria-modal="true">
            <h3>Delete Migration</h3>
            <p>This will permanently delete the migration and all associated logs and validation results. This cannot be undone.</p>
            <div className="bqi-confirm__actions">
              <Button variant="outline" onClick={() => setDeleteConfirmId(null)} disabled={deleting}>Cancel</Button>
              <Button
                variant="primary"
                onClick={confirmDelete}
                disabled={deleting}
                style={{ background: 'var(--color-error)', borderColor: 'var(--color-error)' }}
              >
                {deleting ? 'Deleting…' : 'Delete'}
              </Button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};
