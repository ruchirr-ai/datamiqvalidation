/**
 * Validation Dashboard Page
 *
 * Overhauled UI with:
 * 1. Compact side visual instead of stats cards
 * 2. Tables dropdown from migration (multi-select)
 * 3. Per-table validation type selection (DDL, row count, data sampling)
 * 4. Sampling mode (all / random) with sample limit
 * 5. Bedrock model dropdown (like conversion module)
 * 6. Source/target connections filtered by type
 * 7. Auto-fill connections from selected migration
 * 8. View Logs button + improved progress bar
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CreateValidationRunRequest,
  TableValidationConfig,
  ValidationRun,
  BedrockModel,
  MigrationInfo,
  createValidationRun,
  listValidationRuns,
  deleteValidationRun,
  getMigrationInfo,
  listValidationBedrockModels,
  getValidationTableResults,
} from '../services/validationApi';
import { bqRedshiftApi } from '../services/bqRedshiftApi';
import './ValidationDashboardPage.css';

const AUTO_REFRESH_MS = 5000;
const STATUS_OPTIONS = ['all', 'pending', 'running', 'completed', 'failed'];
const PAGE_SIZE_OPTIONS = [10, 20, 50];

import { useLanguage } from '../contexts/LanguageContext';

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function formatDuration(seconds: number | null): string {
  if (seconds == null) return '—';
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}m ${s}s`;
}

export const ValidationDashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const { t } = useLanguage();

  // --- Data state ---
  const [runs, setRuns] = useState<ValidationRun[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // --- Filters & pagination ---
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(20);

  // --- Create form ---
  const [showForm, setShowForm] = useState(false);
  const [formMigrationId, setFormMigrationId] = useState<number>(0);
  const [selectedTables, setSelectedTables] = useState<string[]>([]);
  const [tableConfigs, setTableConfigs] = useState<Record<string, { ddl: boolean; row_count: boolean; data_match: boolean; sampling_mode: 'all' | 'random'; sample_limit: number | undefined; batch_size: number }>>({});
  const [bedrockModel, setBedrockModel] = useState<string>('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // --- Migration info (auto-fill) ---
  const [migrationInfo, setMigrationInfo] = useState<MigrationInfo | null>(null);
  const [migrationInfoLoading, setMigrationInfoLoading] = useState(false);

  // --- Dropdown data ---
  const [migrations, setMigrations] = useState<{ id: number; migration_name: string }[]>([]);
  const [bedrockModels, setBedrockModels] = useState<BedrockModel[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);

  // --- Tables dropdown ---
  const [showTablesDropdown, setShowTablesDropdown] = useState(false);
  const tablesDropdownRef = useRef<HTMLDivElement>(null);

  // --- Logs modal ---
  const [logsRunId, setLogsRunId] = useState<number | null>(null);
  const [logsData, setLogsData] = useState<any[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);

  // --- Auto-refresh ---
  const refreshRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // --- Fetch dropdown data when form opens ---
  useEffect(() => {
    if (!showForm) return;
    bqRedshiftApi
      .listMigrations()
      .then((m) => setMigrations(m.map((x) => ({ id: x.id, migration_name: x.migration_name }))))
      .catch(() => setMigrations([]));
  }, [showForm]);

  // --- Load bedrock models ---
  useEffect(() => {
    if (!showForm) return;
    const fetchModels = async () => {
      try {
        setModelsLoading(true);
        const data = await listValidationBedrockModels('us-east-1');
        setBedrockModels(data);
      } catch {
        setBedrockModels([]);
      } finally {
        setModelsLoading(false);
      }
    };
    fetchModels();
  }, [showForm]);

  // --- When migration changes, auto-fill connections + tables ---
  useEffect(() => {
    if (!formMigrationId) {
      setMigrationInfo(null);
      setSelectedTables([]);
      setTableConfigs({});
      return;
    }
    const fetchInfo = async () => {
      try {
        setMigrationInfoLoading(true);
        const info = await getMigrationInfo(formMigrationId);
        setMigrationInfo(info);
        // Auto-select all tables
        setSelectedTables(info.tables || []);
        // Initialize per-table configs with all checks enabled + default sampling
        const configs: Record<string, { ddl: boolean; row_count: boolean; data_match: boolean; sampling_mode: 'all' | 'random'; sample_limit: number | undefined; batch_size: number }> = {};
        (info.tables || []).forEach((t) => {
          const rowCount = info.table_row_counts?.[t] ?? 0;
          const defaultBatch = Math.min(10000, rowCount || 10000);
          configs[t] = { ddl: true, row_count: true, data_match: true, sampling_mode: 'all', sample_limit: undefined, batch_size: defaultBatch };
        });
        setTableConfigs(configs);
      } catch {
        setMigrationInfo(null);
      } finally {
        setMigrationInfoLoading(false);
      }
    };
    fetchInfo();
  }, [formMigrationId]);

  // --- Close tables dropdown on outside click ---
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (tablesDropdownRef.current && !tablesDropdownRef.current.contains(e.target as Node)) {
        setShowTablesDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  // --- Fetch runs ---
  const fetchRuns = useCallback(async () => {
    try {
      const filterValue = statusFilter === 'all' ? undefined : statusFilter;
      const data = await listValidationRuns(page, pageSize, undefined, filterValue);
      setRuns(data.runs);
      setTotal(data.total);
      setError(null);
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'message' in err
          ? String((err as { message: unknown }).message)
          : 'Failed to load validation runs';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, statusFilter]);

  useEffect(() => {
    setLoading(true);
    fetchRuns();
  }, [fetchRuns]);

  // Auto-refresh when any run is running or pending
  useEffect(() => {
    const hasActive = runs.some((r) => r.status === 'running' || r.status === 'pending');
    if (hasActive) {
      refreshRef.current = setInterval(fetchRuns, AUTO_REFRESH_MS);
    }
    return () => {
      if (refreshRef.current) {
        clearInterval(refreshRef.current);
        refreshRef.current = null;
      }
    };
  }, [runs, fetchRuns]);

  // --- Summary stats ---
  const passedRuns = runs.filter((r) => r.status === 'completed').length;
  const failedRuns = runs.filter((r) => r.status === 'failed').length;
  const runningRuns = runs.filter((r) => r.status === 'running' || r.status === 'pending').length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  // --- Handlers ---
  const handleRowClick = (runId: number) => navigate(`/validations/${runId}`);

  const handleDelete = async (e: React.MouseEvent, runId: number) => {
    e.stopPropagation();
    if (!window.confirm('Delete this validation run? This cannot be undone.')) return;
    try {
      await deleteValidationRun(runId);
      fetchRuns();
    } catch {
      fetchRuns();
    }
  };

  const handleViewLogs = async (e: React.MouseEvent, runId: number) => {
    e.stopPropagation();
    setLogsRunId(runId);
    setLogsLoading(true);
    try {
      const results = await getValidationTableResults(runId);
      setLogsData(results);
    } catch {
      setLogsData([]);
    } finally {
      setLogsLoading(false);
    }
  };

  const toggleTable = (tableName: string) => {
    setSelectedTables((prev) => {
      if (prev.includes(tableName)) {
        const next = prev.filter((t) => t !== tableName);
        setTableConfigs((c) => {
          const copy = { ...c };
          delete copy[tableName];
          return copy;
        });
        return next;
      } else {
        setTableConfigs((c) => ({
          ...c,
          [tableName]: { ddl: true, row_count: true, data_match: true, sampling_mode: 'all' as const, sample_limit: undefined, batch_size: 10000 },
        }));
        return [...prev, tableName];
      }
    });
  };

  const toggleAllTables = () => {
    const allTables = migrationInfo?.tables || [];
    if (selectedTables.length === allTables.length) {
      setSelectedTables([]);
      setTableConfigs({});
    } else {
      setSelectedTables([...allTables]);
      const configs: Record<string, { ddl: boolean; row_count: boolean; data_match: boolean; sampling_mode: 'all' | 'random'; sample_limit: number | undefined; batch_size: number }> = {};
      allTables.forEach((t) => {
        const rowCount = migrationInfo?.table_row_counts?.[t] ?? 0;
        const defaultBatch = Math.min(10000, rowCount || 10000);
        configs[t] = { ddl: true, row_count: true, data_match: true, sampling_mode: 'all', sample_limit: undefined, batch_size: defaultBatch };
      });
      setTableConfigs(configs);
    }
  };

  const toggleTableCheck = (tableName: string, check: 'ddl' | 'row_count' | 'data_match') => {
    setTableConfigs((prev) => ({
      ...prev,
      [tableName]: { ...prev[tableName], [check]: !prev[tableName]?.[check] },
    }));
  };

  const handleCreate = async () => {
    if (creating) return;
    setCreating(true);
    setCreateError(null);

    const tableConfigsList: TableValidationConfig[] = selectedTables.map((t) => ({
      table_name: t,
      ddl_check: tableConfigs[t]?.ddl ?? true,
      row_count_check: tableConfigs[t]?.row_count ?? true,
      data_match_check: tableConfigs[t]?.data_match ?? true,
      sampling_mode: tableConfigs[t]?.sampling_mode ?? 'all',
      sample_limit: tableConfigs[t]?.sampling_mode === 'random' ? tableConfigs[t]?.sample_limit : undefined,
    }));

    const payload: CreateValidationRunRequest = {
      migration_id: formMigrationId,
      tables: selectedTables.length > 0 ? selectedTables : undefined,
      table_configs: tableConfigsList.length > 0 ? tableConfigsList : undefined,
      bedrock_model: bedrockModel || undefined,
    };

    // Auto-fill connections from migration info
    if (migrationInfo?.source_connection_id) {
      payload.source_connection_id = migrationInfo.source_connection_id;
    }
    if (migrationInfo?.target_connection_id) {
      payload.target_connection_id = migrationInfo.target_connection_id;
    }

    try {
      await createValidationRun(payload);
      setShowForm(false);
      resetForm();
      fetchRuns();
    } catch (err: unknown) {
      let msg = 'Failed to create validation run';
      if (err && typeof err === 'object') {
        if ('detail' in err) {
          const detail = (err as { detail: unknown }).detail;
          msg = typeof detail === 'string' ? detail : JSON.stringify(detail);
        } else if ('message' in err) {
          msg = String((err as { message: unknown }).message);
        }
      }
      setCreateError(msg);
    } finally {
      setCreating(false);
    }
  };

  const resetForm = () => {
    setFormMigrationId(0);
    setSelectedTables([]);
    setTableConfigs({});
    setBedrockModel('');
    setMigrationInfo(null);
    setCreateError(null);
  };

  const canSubmit = formMigrationId > 0 && selectedTables.length > 0;

  // --- Render ---
  return (
    <div className="validation-dashboard">
      {/* Header + Compact Side Visual */}
      <div className="validation-header-row">
        <div className="validation-header">
          <h1 className="validation-title">
            <svg width="22" height="22" viewBox="0 0 22 22" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
              <path d="M9 11l2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
              <circle cx="11" cy="11" r="8" />
            </svg>
            Data Validation
          </h1>
          <p className="validation-subtitle">{t('validation.subtitle')}</p>
        </div>
        <div className="validation-compact-stats">
          <div className="compact-stat">
            <span className="compact-stat-dot completed" />
            <span className="compact-stat-value">{passedRuns}</span>
            <span className="compact-stat-label">{t('validation.passed')}</span>
          </div>
          <div className="compact-stat">
            <span className="compact-stat-dot failed" />
            <span className="compact-stat-value">{failedRuns}</span>
            <span className="compact-stat-label">{t('validation.failed')}</span>
          </div>
          <div className="compact-stat">
            <span className="compact-stat-dot running" />
            <span className="compact-stat-value">{runningRuns}</span>
            <span className="compact-stat-label">{t('validation.active')}</span>
          </div>
        </div>
      </div>

      {/* Toolbar */}
      <div className="validation-toolbar">
        <div className="validation-toolbar-left">
          <button className="validation-new-btn" onClick={() => setShowForm((v) => !v)} type="button">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M7 1v12M1 7h12" strokeLinecap="round" />
            </svg>
            {t('validation.newValidation')}
          </button>
          <select
            className="validation-filter-select"
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            aria-label="Filter by status"
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>{s === 'all' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}</option>
            ))}
          </select>
        </div>
        <div className="validation-toolbar-right" />
      </div>

      {/* Create Form */}
      {showForm && (
        <div className="validation-create-form">
          <h3 className="validation-create-title">{t('validation.newRun')}</h3>

          {/* Row 1: Migration selector */}
          <div className="validation-form-grid">
            <div className="validation-form-field validation-form-field-wide">
              <label className="validation-form-label" htmlFor="vf-migration-id">{t('validation.migration')}</label>
              <select
                id="vf-migration-id"
                className="validation-form-input"
                value={formMigrationId || ''}
                onChange={(e) => setFormMigrationId(Number(e.target.value) || 0)}
              >
                <option value="">{t('validation.selectMigration')}</option>
                {migrations.map((m) => (
                  <option key={m.id} value={m.id}>{m.migration_name}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Auto-filled connection info */}
          {migrationInfo && (
            <div className="validation-autofill-info">
              <div className="autofill-chip">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
                  <circle cx="7" cy="7" r="5.5" />
                  <path d="M7 4.5v3l2 1" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                Source: {migrationInfo.source_connection_name || 'N/A'}
              </div>
              <div className="autofill-chip">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
                  <path d="M2 7h10M8 3l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                Target: {migrationInfo.target_connection_name || 'N/A'}
              </div>
            </div>
          )}
          {migrationInfoLoading && (
            <div className="validation-autofill-info">
              <span className="autofill-loading">{t('validation.loadingMigration')}</span>
            </div>
          )}

          {/* Tables multi-select dropdown */}
          {migrationInfo && migrationInfo.tables.length > 0 && (
            <div className="validation-form-field" ref={tablesDropdownRef}>
              <label className="validation-form-label">
                {t('validation.tables')} ({selectedTables.length} of {migrationInfo.tables.length} selected)
              </label>
              <button
                type="button"
                className="validation-form-input validation-tables-trigger"
                onClick={() => setShowTablesDropdown((v) => !v)}
              >
                {selectedTables.length === 0
                  ? t('validation.selectTables')
                  : selectedTables.length === migrationInfo.tables.length
                    ? t('validation.allTablesSelected')
                    : selectedTables.join(', ')}
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <path d="M3 4.5l3 3 3-3" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
              {showTablesDropdown && (
                <div className="validation-tables-dropdown">
                  <div className="validation-tables-dropdown-header">
                    <label className="validation-table-check-row">
                      <input
                        type="checkbox"
                        checked={selectedTables.length === migrationInfo.tables.length}
                        onChange={toggleAllTables}
                      />
                      <span className="table-check-name">{t('validation.selectAll')}</span>
                    </label>
                  </div>
                  <div className="validation-tables-dropdown-list">
                    {migrationInfo.tables.map((t) => (
                      <label key={t} className="validation-table-check-row">
                        <input
                          type="checkbox"
                          checked={selectedTables.includes(t)}
                          onChange={() => toggleTable(t)}
                        />
                        <span className="table-check-name">{t}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Per-table validation config — using HTML table for reliable layout */}
          {selectedTables.length > 0 && (
            <div className="validation-table-configs">
              <div className="vtc-label-row">
                <span className="validation-form-label">{t('validation.checksPerTable')}</span>
                <div className="vtc-info-pills">
                  <span className="vtc-info-pill">
                    <svg width="12" height="12" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><circle cx="7" cy="7" r="5.5" /><path d="M7 6v3M7 4.5h.01" strokeLinecap="round" /></svg>
                    DDL
                    <span className="vtc-tooltip">Compares the schema (DDL) of source and target tables. Checks column names, data types, nullability, and constraints to ensure the target structure matches the source after migration.</span>
                  </span>
                  <span className="vtc-info-pill">
                    <svg width="12" height="12" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><circle cx="7" cy="7" r="5.5" /><path d="M7 6v3M7 4.5h.01" strokeLinecap="round" /></svg>
                    Row Count
                    <span className="vtc-tooltip">Counts total rows in both source and target tables and compares them. A mismatch indicates missing or extra records. Fast, lightweight check that runs before deeper data matching.</span>
                  </span>
                  <span className="vtc-info-pill">
                    <svg width="12" height="12" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><circle cx="7" cy="7" r="5.5" /><path d="M7 6v3M7 4.5h.01" strokeLinecap="round" /></svg>
                    Data Match
                    <span className="vtc-tooltip">Record-by-record comparison between source and target data. Fetches rows in batches and compares field values to detect mismatches, truncation, or encoding issues. Toggle All or type a sample count per table.</span>
                  </span>
                </div>
              </div>

              <table className="vtc-table">
                <thead>
                  <tr>
                    <th className="vtc-th-name">{t('taskHistory.table')}</th>
                    <th className="vtc-th-rows">{t('validation.totalRows')}</th>
                    <th className="vtc-th-center">DDL</th>
                    <th className="vtc-th-center">Row Count</th>
                    <th className="vtc-th-center">Data Match</th>
                    <th className="vtc-th-sampling">{t('validation.recordsToValidate')}</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedTables.map((t) => {
                    const rowCount = migrationInfo?.table_row_counts?.[t];
                    const cfg = tableConfigs[t];
                    const isAll = (cfg?.sampling_mode ?? 'all') === 'all';
                    return (
                      <tr key={t}>
                        <td className="vtc-td-name" title={t}>{t}</td>
                        <td className="vtc-td-rows">{rowCount != null ? rowCount.toLocaleString() : '—'}</td>
                        <td className="vtc-td-center">
                          <input type="checkbox" checked={cfg?.ddl ?? true} onChange={() => toggleTableCheck(t, 'ddl')} />
                        </td>
                        <td className="vtc-td-center">
                          <input type="checkbox" checked={cfg?.row_count ?? true} onChange={() => toggleTableCheck(t, 'row_count')} />
                        </td>
                        <td className="vtc-td-center">
                          <input type="checkbox" checked={cfg?.data_match ?? true} onChange={() => toggleTableCheck(t, 'data_match')} />
                        </td>
                        <td className="vtc-td-sampling">
                          <div className="vtc-sampling-control">
                            <button
                              type="button"
                              className={`vtc-all-btn ${isAll ? 'active' : ''}`}
                              onClick={() => setTableConfigs((prev) => ({
                                ...prev,
                                [t]: { ...prev[t], sampling_mode: 'all', sample_limit: undefined },
                              }))}
                            >All</button>
                            <input
                              type="number"
                              className="vtc-sample-input"
                              placeholder="e.g. 5000"
                              min={1}
                              max={rowCount ?? 10000000}
                              value={isAll ? '' : (cfg?.sample_limit ?? '')}
                              onChange={(e) => {
                                const val = e.target.value ? Number(e.target.value) : undefined;
                                setTableConfigs((prev) => ({
                                  ...prev,
                                  [t]: { ...prev[t], sampling_mode: val ? 'random' : 'all', sample_limit: val },
                                }));
                              }}
                              onFocus={() => {
                                if (isAll) {
                                  setTableConfigs((prev) => ({
                                    ...prev,
                                    [t]: { ...prev[t], sampling_mode: 'random' },
                                  }));
                                }
                              }}
                            />
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Bedrock model selector with info tooltip */}
          <div className="validation-form-grid">
            <div className="validation-form-field validation-form-field-wide">
              <div className="vtc-label-row">
                <label className="validation-form-label" htmlFor="vf-bedrock-model">
                  {t('validation.bedrockModel')}
                </label>
                <span className="vtc-info-pill">
                  <svg width="12" height="12" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><circle cx="7" cy="7" r="5.5" /><path d="M7 6v3M7 4.5h.01" strokeLinecap="round" /></svg>
                  Info
                  <span className="vtc-tooltip">When selected, an AI model from Amazon Bedrock analyzes validation mismatches and provides intelligent explanations for data differences. Helps identify root causes like encoding issues, type casting, or truncation. Leave empty to skip AI analysis.</span>
                </span>
              </div>
              <select
                id="vf-bedrock-model"
                className="validation-form-input"
                value={bedrockModel}
                onChange={(e) => setBedrockModel(e.target.value)}
                disabled={modelsLoading}
              >
                <option value="">
                  {modelsLoading ? t('validation.loadingModels') : t('validation.noneSkipAi')}
                </option>
                {bedrockModels.map((m) => (
                  <option key={m.model_id} value={m.model_id}>
                    {m.model_name} ({m.provider})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {createError && (
            <p className="validation-error-text" style={{ margin: 0 }}>{createError}</p>
          )}

          <div className="validation-form-actions">
            <button
              className="validation-form-submit"
              disabled={!canSubmit || creating}
              onClick={handleCreate}
              type="button"
            >
              {creating ? t('validation.creating') : t('validation.createStart')}
            </button>
            <button
              className="validation-form-cancel"
              onClick={() => { setShowForm(false); resetForm(); }}
              type="button"
            >
              {t('common.cancel')}
            </button>
          </div>
        </div>
      )}

      {/* Content */}
      {loading ? (
        <div className="validation-loading">
          <div className="validation-spinner" />
          {t('validation.loading')}
        </div>
      ) : error ? (
        <div className="validation-error">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 8v4M12 16h.01" strokeLinecap="round" />
          </svg>
          <p className="validation-error-text">{error}</p>
        </div>
      ) : runs.length === 0 ? (
        <div className="validation-empty">
          <svg className="validation-empty-icon" width="36" height="36" viewBox="0 0 36 36" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <rect x="6" y="6" width="24" height="24" rx="3" />
            <path d="M14 18h8M18 14v8" strokeLinecap="round" />
          </svg>
          <p className="validation-empty-text">{t('validation.noRunsDesc')}</p>
        </div>
      ) : (
        <div className="validation-table-wrapper">
          <table className="validation-table">
            <thead>
              <tr>
                <th>{t('validation.id')}</th>
                <th>{t('jobs.status')}</th>
                <th>{t('validation.progress')}</th>
                <th>{t('validation.tables')}</th>
                <th>{t('validation.started')}</th>
                <th>{t('validation.duration')}</th>
                <th>{t('validation.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id} onClick={() => handleRowClick(run.id)}>
                  <td>{run.id}</td>
                  <td>
                    <span className={`validation-status-badge ${run.status}`}>{run.status}</span>
                  </td>

                  <td>
                    {run.status === 'running' ? (
                      <div className="validation-progress-cell">
                        <div className="validation-progress-bar-enhanced">
                          <div
                            className="validation-progress-fill-enhanced"
                            style={{ width: `${run.progress_percentage}%` }}
                          />
                        </div>
                        <span className="validation-progress-text">{run.progress_percentage}%</span>
                      </div>
                    ) : run.status === 'completed' || run.status === 'failed' ? (
                      <span className="validation-progress-text">100%</span>
                    ) : (
                      <span className="validation-progress-text">—</span>
                    )}
                  </td>
                  <td>
                    <div className="validation-tables-cell">
                      <span className="passed-count">{run.tables_passed}p</span>
                      <span className="separator">/</span>
                      <span className="failed-count">{run.tables_failed}f</span>
                      <span className="separator">/</span>
                      <span className="error-count">{run.tables_error}e</span>
                    </div>
                  </td>
                  <td>{formatDate(run.started_at)}</td>
                  <td>{formatDuration(run.duration_seconds)}</td>
                  <td>
                    <div className="validation-actions-cell">
                      <button
                        className="validation-logs-btn"
                        onClick={(e) => handleViewLogs(e, run.id)}
                        aria-label={`View logs for run ${run.id}`}
                        title="View Logs"
                        type="button"
                      >
                        <svg width="15" height="15" viewBox="0 0 15 15" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
                          <path d="M3 3h9M3 6h9M3 9h6M3 12h4" strokeLinecap="round" />
                        </svg>
                      </button>
                      <button
                        className="validation-delete-btn"
                        onClick={(e) => handleDelete(e, run.id)}
                        aria-label={`Delete run ${run.id}`}
                        title="Delete"
                        type="button"
                      >
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
                          <path d="M3 4h10M6 4V3a1 1 0 011-1h2a1 1 0 011 1v1M5 4v8a1 1 0 001 1h4a1 1 0 001-1V4" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Bottom Pagination */}
      {!loading && !error && runs.length > 0 && (
        <div className="validation-bottom-pagination">
          <select
            className="validation-page-size-select"
            value={pageSize}
            onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
            aria-label="Page size"
          >
            {PAGE_SIZE_OPTIONS.map((s) => (
              <option key={s} value={s}>{s} / page</option>
            ))}
          </select>
          <div className="validation-pagination">
            <button className="validation-page-btn" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))} aria-label="Previous page" type="button">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M8 3L4 7l4 4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            <span className="validation-pagination-info">{page} / {totalPages}</span>
            <button className="validation-page-btn" disabled={page >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))} aria-label="Next page" type="button">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M6 3l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* Logs Modal */}
      {logsRunId !== null && (
        <div className="validation-logs-overlay" onClick={() => setLogsRunId(null)}>
          <div className="validation-logs-modal" onClick={(e) => e.stopPropagation()}>
            <div className="validation-logs-modal-header">
              <h3>Validation Run #{logsRunId} — Table Progress</h3>
              <button type="button" className="validation-logs-close" onClick={() => setLogsRunId(null)} aria-label="Close logs">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <path d="M4 4l8 8M12 4l-8 8" strokeLinecap="round" />
                </svg>
              </button>
            </div>
            <div className="validation-logs-modal-body">
              {logsLoading ? (
                <div className="validation-loading"><div className="validation-spinner" /> Loading...</div>
              ) : logsData.length === 0 ? (
                <p className="validation-empty-text">No table results yet.</p>
              ) : (
                <table className="validation-logs-table">
                  <thead>
                    <tr>
                      <th>Table</th>
                      <th>DDL</th>
                      <th>Row Count</th>
                      <th>Data Match</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logsData.map((r: any) => (
                      <tr key={r.id}>
                        <td className="logs-table-name">{r.table_name}</td>
                        <td><span className={`log-step-badge ${r.ddl_status || 'pending'}`}>{r.ddl_status || '—'}</span></td>
                        <td><span className={`log-step-badge ${r.row_count_status || 'pending'}`}>{r.row_count_status || '—'}</span></td>
                        <td><span className={`log-step-badge ${r.data_match_status || 'pending'}`}>{r.data_match_status || '—'}</span></td>
                        <td><span className={`validation-status-badge ${r.status}`}>{r.status}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ValidationDashboardPage;