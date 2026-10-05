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
  getMigrationTableColumns,
  MigrationColumn,
} from '../services/validationApi';
import { bqRedshiftApi } from '../services/bqRedshiftApi';
import { QuickValidationTest } from './QuickValidationTest';
import './ValidationDashboardPage.css';

const AUTO_REFRESH_MS = 5000;
const STATUS_OPTIONS = ['all', 'pending', 'running', 'completed', 'failed'];
const PAGE_SIZE_OPTIONS = [10, 20, 50];

/**
 * Per-table validation configuration held in dashboard form state.
 * Extends the base DDL/row-count/data-match checks with the column-based
 * checks (NULL, duplicate, SUM, AVERAGE, specific row).
 */
interface TableConfig {
  ddl: boolean;
  row_count: boolean;
  data_match: boolean;
  sampling_mode: 'all' | 'random';
  sample_limit: number | undefined;
  batch_size: number;
  // New column-based checks
  null_check: boolean;
  null_column: string;
  duplicate_check: boolean;
  duplicate_match_key: string;
  sum_check: boolean;
  sum_column: string;
  average_check: boolean;
  average_column: string;
  specific_row_check: boolean;
  specific_row_match_key: string;
  specific_row_start: number | undefined;
  specific_row_end: number | undefined;
}

/** Factory for a default per-table config (all base checks on, new checks off). */
function makeDefaultTableConfig(batchSize: number): TableConfig {
  return {
    ddl: true,
    row_count: true,
    data_match: true,
    sampling_mode: 'all',
    sample_limit: undefined,
    batch_size: batchSize,
    null_check: false,
    null_column: '',
    duplicate_check: false,
    duplicate_match_key: '',
    sum_check: false,
    sum_column: '',
    average_check: false,
    average_column: '',
    specific_row_check: false,
    specific_row_match_key: '',
    specific_row_start: undefined,
    specific_row_end: undefined,
  };
}

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

export function formatTableSummary(passed: number, failed: number, errors: number): JSX.Element {
  const parts: JSX.Element[] = [];
  if (passed > 0) parts.push(<span key="passed" className="summary-passed">{passed} Passed</span>);
  if (failed > 0) parts.push(<span key="failed" className="summary-failed">{failed} Failed</span>);
  if (errors > 0) parts.push(<span key="error" className="summary-error">{errors} Errors</span>);
  if (parts.length === 0) return <span className="summary-none">—</span>;
  return <>{parts.reduce<JSX.Element[]>((acc, el, i) => i === 0 ? [el] : [...acc, <span key={`sep-${i}`} className="summary-separator">, </span>, el], [])}</>;
}

export const ValidationDashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const { t } = useLanguage();

  // --- Data state ---
  const [runs, setRuns] = useState<ValidationRun[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // --- Expandable rows ---
  const [expandedRunId, setExpandedRunId] = useState<number | null>(null);
  const [expandedTableResults, setExpandedTableResults] = useState<Record<number, import('../services/validationApi').ValidationTableResult[]>>({});
  const [expandedLoading, setExpandedLoading] = useState<Record<number, boolean>>({});
  const [expandedError, setExpandedError] = useState<Record<number, string | null>>({});

  // --- Filters & pagination ---
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(20);

  // --- Create form ---
  const [showForm, setShowForm] = useState(false);
  // --- Quick direct-test panel ---
  const [showQuickTest, setShowQuickTest] = useState(false);
  const [runName, setRunName] = useState<string>('');
  const [formMigrationId, setFormMigrationId] = useState<number>(0);
  const [selectedTables, setSelectedTables] = useState<string[]>([]);
  const [tableConfigs, setTableConfigs] = useState<Record<string, TableConfig>>({});
  // Per-table available columns (source), lazily fetched for column-based checks
  const [tableColumns, setTableColumns] = useState<Record<string, MigrationColumn[]>>({});
  const [columnsLoading, setColumnsLoading] = useState<Record<string, boolean>>({});
  // Which tables have their advanced (column-based) checks panel expanded
  const [expandedConfigTables, setExpandedConfigTables] = useState<Record<string, boolean>>({});
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
        // Initialize per-table configs with base checks enabled + default sampling
        const configs: Record<string, TableConfig> = {};
        (info.tables || []).forEach((t) => {
          const rowCount = info.table_row_counts?.[t] ?? 0;
          const defaultBatch = Math.min(10000, rowCount || 10000);
          configs[t] = makeDefaultTableConfig(defaultBatch);
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



  const handleChevronClick = async (e: React.MouseEvent | React.KeyboardEvent, runId: number) => {
    e.stopPropagation();
    if (expandedRunId === runId) {
      setExpandedRunId(null);
      return;
    }
    setExpandedRunId(runId);
    // If already cached, don't re-fetch
    if (expandedTableResults[runId]) return;
    // Fetch table results
    setExpandedLoading((prev) => ({ ...prev, [runId]: true }));
    setExpandedError((prev) => ({ ...prev, [runId]: null }));
    try {
      const results = await getValidationTableResults(runId);
      setExpandedTableResults((prev) => ({ ...prev, [runId]: results }));
    } catch (err: unknown) {
      const msg = err && typeof err === 'object' && 'message' in err ? String((err as { message: unknown }).message) : 'Failed to load table results';
      setExpandedError((prev) => ({ ...prev, [runId]: msg }));
    } finally {
      setExpandedLoading((prev) => ({ ...prev, [runId]: false }));
    }
  };

  const handleRetryExpand = async (e: React.MouseEvent, runId: number) => {
    e.stopPropagation();
    setExpandedLoading((prev) => ({ ...prev, [runId]: true }));
    setExpandedError((prev) => ({ ...prev, [runId]: null }));
    try {
      const results = await getValidationTableResults(runId);
      setExpandedTableResults((prev) => ({ ...prev, [runId]: results }));
    } catch (err: unknown) {
      const msg = err && typeof err === 'object' && 'message' in err ? String((err as { message: unknown }).message) : 'Failed to load table results';
      setExpandedError((prev) => ({ ...prev, [runId]: msg }));
    } finally {
      setExpandedLoading((prev) => ({ ...prev, [runId]: false }));
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
          [tableName]: makeDefaultTableConfig(10000),
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
      const configs: Record<string, TableConfig> = {};
      allTables.forEach((t) => {
        const rowCount = migrationInfo?.table_row_counts?.[t] ?? 0;
        const defaultBatch = Math.min(10000, rowCount || 10000);
        configs[t] = makeDefaultTableConfig(defaultBatch);
      });
      setTableConfigs(configs);
    }
  };

  const toggleTableCheck = (
    tableName: string,
    check: 'ddl' | 'row_count' | 'data_match' | 'null_check' | 'duplicate_check' | 'sum_check' | 'average_check' | 'specific_row_check'
  ) => {
    setTableConfigs((prev) => ({
      ...prev,
      [tableName]: { ...prev[tableName], [check]: !prev[tableName]?.[check] },
    }));
  };

  // Update an arbitrary field on a table's config (used by column pickers / row inputs)
  const setTableConfigField = <K extends keyof TableConfig>(
    tableName: string,
    field: K,
    value: TableConfig[K]
  ) => {
    setTableConfigs((prev) => ({
      ...prev,
      [tableName]: { ...prev[tableName], [field]: value },
    }));
  };

  // Toggle the advanced (column-based) checks panel for a table, lazily fetching columns
  const toggleAdvancedConfig = (tableName: string) => {
    setExpandedConfigTables((prev) => {
      const next = { ...prev, [tableName]: !prev[tableName] };
      return next;
    });
    // Fetch columns on first expand
    if (!tableColumns[tableName] && !columnsLoading[tableName] && formMigrationId) {
      setColumnsLoading((prev) => ({ ...prev, [tableName]: true }));
      getMigrationTableColumns(formMigrationId, tableName)
        .then((res) => {
          setTableColumns((prev) => ({ ...prev, [tableName]: res.source_columns || [] }));
        })
        .catch(() => {
          setTableColumns((prev) => ({ ...prev, [tableName]: [] }));
        })
        .finally(() => {
          setColumnsLoading((prev) => ({ ...prev, [tableName]: false }));
        });
    }
  };

  const handleCreate = async () => {
    if (creating) return;
    setCreating(true);
    setCreateError(null);

    const tableConfigsList: TableValidationConfig[] = selectedTables.map((t) => {
      const cfg = tableConfigs[t];
      return {
        table_name: t,
        ddl_check: cfg?.ddl ?? true,
        row_count_check: cfg?.row_count ?? true,
        data_match_check: cfg?.data_match ?? true,
        sampling_mode: cfg?.sampling_mode ?? 'all',
        sample_limit: cfg?.sampling_mode === 'random' ? cfg?.sample_limit : undefined,
        // New column-based checks (only send column params when the check is enabled)
        null_check: cfg?.null_check ?? false,
        null_column: cfg?.null_check ? (cfg?.null_column || undefined) : undefined,
        duplicate_check: cfg?.duplicate_check ?? false,
        duplicate_match_key: cfg?.duplicate_check ? (cfg?.duplicate_match_key || undefined) : undefined,
        sum_check: cfg?.sum_check ?? false,
        sum_column: cfg?.sum_check ? (cfg?.sum_column || undefined) : undefined,
        average_check: cfg?.average_check ?? false,
        average_column: cfg?.average_check ? (cfg?.average_column || undefined) : undefined,
        specific_row_check: cfg?.specific_row_check ?? false,
        specific_row_match_key: cfg?.specific_row_check ? (cfg?.specific_row_match_key || undefined) : undefined,
        specific_row_start: cfg?.specific_row_check ? cfg?.specific_row_start : undefined,
        specific_row_end: cfg?.specific_row_check ? cfg?.specific_row_end : undefined,
      };
    });

    const payload: CreateValidationRunRequest = {
      migration_id: formMigrationId,
      tables: selectedTables.length > 0 ? selectedTables : undefined,
      table_configs: tableConfigsList.length > 0 ? tableConfigsList : undefined,
      bedrock_model: bedrockModel || undefined,
      run_name: runName.trim() || undefined,
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
    setRunName('');
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

      </div>

      {/* Toolbar */}
      <div className="validation-toolbar">
        <div className="validation-toolbar-left">
          <button className="validation-new-btn" onClick={() => navigate('/validations/new')} type="button">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M7 1v12M1 7h12" strokeLinecap="round" />
            </svg>
            {t('validation.newValidation')}
          </button>
          <button
            className="validation-filter-select"
            onClick={() => setShowQuickTest((v) => !v)}
            type="button"
            style={{ cursor: 'pointer' }}
          >
            {showQuickTest ? 'Hide Quick Test' : 'Quick Test'}
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

      {/* Quick direct-test panel (SQL Server / Redshift, no migration) */}
      {showQuickTest && <QuickValidationTest />}

      {/* Create Form */}
      {showForm && (
        <div className="validation-create-form">
          <h3 className="validation-create-title">{t('validation.newRun')}</h3>

          {/* Run Name (optional) */}
          <div className="validation-form-grid">
            <div className="validation-form-field validation-form-field-wide">
              <label className="validation-form-label" htmlFor="vf-run-name">Run Name</label>
              <input
                id="vf-run-name"
                type="text"
                className="validation-form-input"
                placeholder="e.g. Pre-release check (optional)"
                maxLength={255}
                value={runName}
                onChange={(e) => setRunName(e.target.value)}
              />
            </div>
          </div>

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
                    const advancedOpen = !!expandedConfigTables[t];
                    const advancedCount = [cfg?.null_check, cfg?.duplicate_check, cfg?.sum_check, cfg?.average_check, cfg?.specific_row_check].filter(Boolean).length;
                    const cols = tableColumns[t] || [];
                    const colsLoading = !!columnsLoading[t];
                    return (
                      <React.Fragment key={t}>
                      <tr>
                        <td className="vtc-td-name" title={t}>
                          <button
                            type="button"
                            className={`vtc-advanced-toggle ${advancedOpen ? 'open' : ''}`}
                            onClick={() => toggleAdvancedConfig(t)}
                            aria-expanded={advancedOpen}
                            aria-label="Toggle advanced checks"
                          >
                            <svg width="10" height="10" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                              <path d="M3 4.5l3 3 3-3" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                          </button>
                          <span className="vtc-td-name-text">{t}</span>
                          {advancedCount > 0 && <span className="vtc-advanced-badge">+{advancedCount}</span>}
                        </td>
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
                      {advancedOpen && (
                        <tr className="vtc-advanced-row">
                          <td colSpan={6}>
                            <div className="vtc-advanced-panel">
                              {colsLoading && <span className="vtc-advanced-hint">Loading columns…</span>}
                              <div className="vtc-advanced-grid">
                                {/* NULL check */}
                                <div className="vtc-advanced-item">
                                  <label className="vtc-advanced-check">
                                    <input type="checkbox" checked={cfg?.null_check ?? false} onChange={() => toggleTableCheck(t, 'null_check')} />
                                    <span>NULL</span>
                                  </label>
                                  <select
                                    className="vtc-advanced-select"
                                    disabled={!cfg?.null_check}
                                    value={cfg?.null_column ?? ''}
                                    onChange={(e) => setTableConfigField(t, 'null_column', e.target.value)}
                                  >
                                    <option value="">Select column…</option>
                                    {cols.map((c) => <option key={c.column_name} value={c.column_name}>{c.column_name}</option>)}
                                  </select>
                                </div>
                                {/* Duplicate check */}
                                <div className="vtc-advanced-item">
                                  <label className="vtc-advanced-check">
                                    <input type="checkbox" checked={cfg?.duplicate_check ?? false} onChange={() => toggleTableCheck(t, 'duplicate_check')} />
                                    <span>Duplicate</span>
                                  </label>
                                  <select
                                    className="vtc-advanced-select"
                                    disabled={!cfg?.duplicate_check}
                                    value={cfg?.duplicate_match_key ?? ''}
                                    onChange={(e) => setTableConfigField(t, 'duplicate_match_key', e.target.value)}
                                  >
                                    <option value="">Match key column…</option>
                                    {cols.map((c) => <option key={c.column_name} value={c.column_name}>{c.column_name}</option>)}
                                  </select>
                                </div>
                                {/* SUM check */}
                                <div className="vtc-advanced-item">
                                  <label className="vtc-advanced-check">
                                    <input type="checkbox" checked={cfg?.sum_check ?? false} onChange={() => toggleTableCheck(t, 'sum_check')} />
                                    <span>SUM</span>
                                  </label>
                                  <select
                                    className="vtc-advanced-select"
                                    disabled={!cfg?.sum_check}
                                    value={cfg?.sum_column ?? ''}
                                    onChange={(e) => setTableConfigField(t, 'sum_column', e.target.value)}
                                  >
                                    <option value="">Numeric column…</option>
                                    {cols.map((c) => <option key={c.column_name} value={c.column_name}>{c.column_name}</option>)}
                                  </select>
                                </div>
                                {/* AVERAGE check */}
                                <div className="vtc-advanced-item">
                                  <label className="vtc-advanced-check">
                                    <input type="checkbox" checked={cfg?.average_check ?? false} onChange={() => toggleTableCheck(t, 'average_check')} />
                                    <span>AVERAGE</span>
                                  </label>
                                  <select
                                    className="vtc-advanced-select"
                                    disabled={!cfg?.average_check}
                                    value={cfg?.average_column ?? ''}
                                    onChange={(e) => setTableConfigField(t, 'average_column', e.target.value)}
                                  >
                                    <option value="">Numeric column…</option>
                                    {cols.map((c) => <option key={c.column_name} value={c.column_name}>{c.column_name}</option>)}
                                  </select>
                                </div>
                                {/* Specific row check */}
                                <div className="vtc-advanced-item vtc-advanced-item-wide">
                                  <label className="vtc-advanced-check">
                                    <input type="checkbox" checked={cfg?.specific_row_check ?? false} onChange={() => toggleTableCheck(t, 'specific_row_check')} />
                                    <span>Specific Row</span>
                                  </label>
                                  <div className="vtc-advanced-row-inputs">
                                    <select
                                      className="vtc-advanced-select"
                                      disabled={!cfg?.specific_row_check}
                                      value={cfg?.specific_row_match_key ?? ''}
                                      onChange={(e) => setTableConfigField(t, 'specific_row_match_key', e.target.value)}
                                    >
                                      <option value="">Match key…</option>
                                      {cols.map((c) => <option key={c.column_name} value={c.column_name}>{c.column_name}</option>)}
                                    </select>
                                    <input
                                      type="number"
                                      className="vtc-advanced-num"
                                      placeholder="Start"
                                      min={1}
                                      disabled={!cfg?.specific_row_check}
                                      value={cfg?.specific_row_start ?? ''}
                                      onChange={(e) => setTableConfigField(t, 'specific_row_start', e.target.value ? Number(e.target.value) : undefined)}
                                    />
                                    <input
                                      type="number"
                                      className="vtc-advanced-num"
                                      placeholder="End"
                                      min={1}
                                      disabled={!cfg?.specific_row_check}
                                      value={cfg?.specific_row_end ?? ''}
                                      onChange={(e) => setTableConfigField(t, 'specific_row_end', e.target.value ? Number(e.target.value) : undefined)}
                                    />
                                  </div>
                                </div>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                      </React.Fragment>
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
                <th style={{ width: 36 }} />
                <th>Name</th>
                <th>{t('jobs.status')}</th>
                <th>{t('validation.progress')}</th>
                <th>{t('validation.tables')}</th>
                <th>{t('validation.started')}</th>
                <th>{t('validation.duration')}</th>
                <th>{t('validation.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => {
                const isExpanded = expandedRunId === run.id;
                return (
                  <React.Fragment key={run.id}>
                    <tr onClick={() => handleRowClick(run.id)} style={{ cursor: 'pointer' }}>
                      <td className="validation-chevron-cell" style={{ cursor: 'default' }}>
                        <button
                          type="button"
                          role="button"
                          className={`validation-chevron-btn${isExpanded ? ' expanded' : ''}`}
                          aria-label={`Expand run ${run.id}`}
                          aria-expanded={isExpanded}
                          onClick={(e) => handleChevronClick(e, run.id)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault();
                              handleChevronClick(e, run.id);
                            }
                          }}
                        >
                          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" style={{ transition: 'transform 0.2s ease', transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)' }}>
                            <path d="M3 5l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
                          </svg>
                        </button>
                      </td>
                      <td className="validation-name-cell" data-testid={`run-name-${run.id}`}>
                        {run.run_name || `Run #${run.id}`}
                      </td>
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
                          {formatTableSummary(run.tables_passed, run.tables_failed, run.tables_error)}
                        </div>
                      </td>
                      <td>{formatDate(run.started_at)}</td>
                      <td>{formatDuration(run.duration_seconds)}</td>
                      <td style={{ cursor: 'default' }}>
                        <div className="validation-actions-cell" style={{ justifyContent: 'center' }}>
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
                    {isExpanded && (
                      <tr className="validation-expanded-row">
                        <td colSpan={8}>
                          {expandedLoading[run.id] ? (
                            <div className="validation-expanded-loading">
                              <div className="validation-spinner" />
                              Loading table results...
                            </div>
                          ) : expandedError[run.id] ? (
                            <div className="validation-expanded-error">
                              <span>{expandedError[run.id]}</span>
                              <button type="button" onClick={(e) => handleRetryExpand(e, run.id)}>Retry</button>
                            </div>
                          ) : expandedTableResults[run.id] ? (
                            <table className="validation-nested-table">
                              <thead>
                                <tr>
                                  <th>Table Name</th>
                                  <th>DDL</th>
                                  <th>Row Count</th>
                                  <th>Data Match</th>
                                  <th>Overall</th>
                                </tr>
                              </thead>
                              <tbody>
                                {expandedTableResults[run.id].map((tr) => (
                                  <tr key={tr.id}>
                                    <td>{tr.table_name}</td>
                                    <td><span className={`mini-status-badge ${tr.ddl_status || 'pending'}`}>{tr.ddl_status || 'pending'}</span></td>
                                    <td><span className={`mini-status-badge ${tr.row_count_status || 'pending'}`}>{tr.row_count_status || 'pending'}</span></td>
                                    <td><span className={`mini-status-badge ${tr.data_match_status || 'pending'}`}>{tr.data_match_status || 'pending'}</span></td>
                                    <td><span className={`mini-status-badge ${tr.status || 'pending'}`}>{tr.status || 'pending'}</span></td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          ) : null}
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
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

    </div>
  );
};

export default ValidationDashboardPage;