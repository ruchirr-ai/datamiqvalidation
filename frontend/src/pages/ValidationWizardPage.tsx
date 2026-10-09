import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import './ValidationWizardPage.css';

import { bqRedshiftApi } from '../services/bqRedshiftApi';
import { listConnections, Connection } from '../services/api';
import {
  downloadCsv,
  downloadValidationPdf,
  ValidationReportRow,
  ReportDiscrepancy,
  extractRecordDiscrepancies,
  extractDirectSchemaDiscrepancies,
} from '../utils/validationReport';

import {
  createValidationRun,
  getMigrationInfo,
  getMigrationTableColumns,
  getConnectionTables,
  getConnectionColumns,
  runDirectValidationTest,
  saveDirectConfig,
  listDirectConfigs,
  deleteDirectConfig,
  type CreateValidationRunRequest,
  type DiscoveredTable,
  type DirectValidationResponse,
  type DirectConfig,
} from '../services/validationApi';

// Engines the direct connection-to-connection path supports
const SUPPORTED_CONN_TYPES = ['sqlserver', 'mssql', 'redshift', 'postgresql', 'postgres'];

type ValidationMode = 'migration' | 'connection';

const STEPS = [
  'Connections',
  'Table Selection',
  'Validation Checks',
  'Configuration',
  'Results',
];

const CHECKS = [
  'Row Count Validation',
  'NULL Validation',
  'Schema Validation',
  'Duplicate Validation',
  'SUM Validation',
  'AVERAGE Validation',
  'Specific Row Validation',
];

/** Per-pair check configuration (connection mode). Each table pair carries
 *  its own set of selected checks, column params, and discovered columns. */
interface PairCheckConfig {
  checks: string[];
  nullColumn: string;
  duplicateMatchKey: string;
  sumColumn: string;
  averageColumn: string;
  specificRowMatchKey: string;
  specificRowStart: string;
  specificRowEnd: string;
  columns: string[];
  columnsLoading: boolean;
}

interface TablePair {
  source: string;     // "schema.table"
  target: string;     // "schema.table"
  config: PairCheckConfig;
}

// Default checks that are always on unless the user turns them off.
const DEFAULT_CHECKS = ['Row Count Validation', 'Schema Validation'];

function makeDefaultPairConfig(): PairCheckConfig {
  return {
    checks: [...DEFAULT_CHECKS],
    nullColumn: '',
    duplicateMatchKey: '',
    sumColumn: '',
    averageColumn: '',
    specificRowMatchKey: '',
    specificRowStart: '',
    specificRowEnd: '',
    columns: [],
    columnsLoading: false,
  };
}

function makeDefaultPair(): TablePair {
  return { source: '', target: '', config: makeDefaultPairConfig() };
}

export default function ValidationWizardPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // A saved config id passed from the dashboard (?config=<id>) to auto-load.
  const presetConfigId = searchParams.get('config');
  const presetConfigApplied = useRef(false);

  const [currentStep, setCurrentStep] = useState(0);

  // Create mode: validate a completed migration (persisted) or two
  // connections directly (ephemeral, inline results, not saved).
  // Default to connection mode when arriving with a preset config to load.
  const [mode, setMode] = useState<ValidationMode>(
    presetConfigId ? 'connection' : 'migration'
  );

  // =========================================================
  // CONNECTION MODE STATE
  // =========================================================

  const [connections, setConnections] = useState<Connection[]>([]);
  const [sourceConnectionId, setSourceConnectionId] = useState<number>(0);
  const [targetConnectionId, setTargetConnectionId] = useState<number>(0);

  const [sourceConnTables, setSourceConnTables] = useState<DiscoveredTable[]>([]);
  const [targetConnTables, setTargetConnTables] = useState<DiscoveredTable[]>([]);
  const [sourceConnTablesLoading, setSourceConnTablesLoading] = useState(false);
  const [targetConnTablesLoading, setTargetConnTablesLoading] = useState(false);

  // Table pairs to validate: each is a source + target "schema.table"
  // with its OWN check configuration and discovered columns.
  const [tablePairs, setTablePairs] = useState<TablePair[]>([
    makeDefaultPair(),
  ]);

  const [connError, setConnError] = useState('');

  // Direct (ephemeral) run state — one DirectValidationResponse per pair
  const [directRunning, setDirectRunning] = useState(false);
  const [directResults, setDirectResults] = useState<DirectValidationResponse[]>([]);

  // Saved direct-validation configurations (setup only, re-runnable)
  const [savedConfigs, setSavedConfigs] = useState<DirectConfig[]>([]);
  const [savedConfigsLoading, setSavedConfigsLoading] = useState(false);
  const [savingConfig, setSavingConfig] = useState(false);
  const [saveConfigName, setSaveConfigName] = useState('');
  const [saveConfigMessage, setSaveConfigMessage] = useState('');
  const [loadedConfigId, setLoadedConfigId] = useState<number | null>(null);

  // =========================================================
  // STEP 1 - CONNECTIONS
  // =========================================================

  const [runName, setRunName] = useState('');
  const [migration, setMigration] = useState('');
  const [migrationId, setMigrationId] = useState<number | null>(null);
  const [bedrockModel, setBedrockModel] = useState('');

  const [migrations, setMigrations] = useState<any[]>([]);
  const [loadingMigrations, setLoadingMigrations] = useState(false);

  const [sourceName, setSourceName] = useState('');
  const [targetName, setTargetName] = useState('');

  // =========================================================
  // STEP 2 - DATA DEFINITION
  // =========================================================

  const [availableTables, setAvailableTables] = useState<string[]>([]);
  const [selectedTables, setSelectedTables] = useState<string[]>([]);

  const [loadingTables, setLoadingTables] = useState(false);
  const [tableError, setTableError] = useState('');

  const [availableColumns, setAvailableColumns] = useState<string[]>([]);
  const [, setLoadingColumns] = useState(false);

  // =========================================================
  // STEP 3 - VALIDATION CHECKS
  // =========================================================

  const [selectedChecks, setSelectedChecks] = useState<string[]>([]);

  const [nullColumn, setNullColumn] = useState('');
  const [duplicateMatchKey, setDuplicateMatchKey] = useState('');
  const [sumColumn, setSumColumn] = useState('');
  const [averageColumn, setAverageColumn] = useState('');

  const [specificRowMatchKey, setSpecificRowMatchKey] = useState('');
  const [specificRowStart, setSpecificRowStart] = useState('');
  const [specificRowEnd, setSpecificRowEnd] = useState('');

  // =========================================================
  // GENERAL
  // =========================================================

  const [error, setError] = useState('');

  // =========================================================
  // STEP 5 - RUN
  // =========================================================

  const [runSubmitting, setRunSubmitting] = useState(false);
  const [runError, setRunError] = useState('');

  // =========================================================
  // LOAD MIGRATIONS
  // =========================================================

  useEffect(() => {
    loadMigrations();
  }, []);

  const loadMigrations = async () => {
    setLoadingMigrations(true);
    setError('');

    try {
      const response = await bqRedshiftApi.listMigrations();

      const migrationList = Array.isArray(response)
  ? response
  : [];

      setMigrations(migrationList);
    } catch (err: any) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          'Unable to load migrations.'
      );
    } finally {
      setLoadingMigrations(false);
    }
  };

  // =========================================================
  // CONNECTION MODE: load connections + discover tables/columns
  // =========================================================

  useEffect(() => {
    if (mode !== 'connection' || connections.length > 0) return;
    listConnections()
      .then((conns) => {
        const all = conns || [];
        const supported = all.filter((c) =>
          SUPPORTED_CONN_TYPES.includes((c.type || '').toLowerCase()) ||
          SUPPORTED_CONN_TYPES.includes((c.database || '').toLowerCase())
        );
        setConnections(supported.length > 0 ? supported : all);
      })
      .catch(() => setConnections([]));
  }, [mode, connections.length]);

  // Load saved direct-validation configs when entering connection mode
  useEffect(() => {
    if (mode !== 'connection') return;
    void fetchSavedConfigs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  const fetchSavedConfigs = async () => {
    setSavedConfigsLoading(true);
    try {
      const configs = await listDirectConfigs();
      setSavedConfigs(configs || []);
    } catch {
      setSavedConfigs([]);
    } finally {
      setSavedConfigsLoading(false);
    }
  };

  // When arriving from the dashboard with ?config=<id>, auto-load that saved
  // config into the form once the list has been fetched (runs once).
  useEffect(() => {
    if (!presetConfigId || presetConfigApplied.current) return;
    if (savedConfigsLoading) return;
    const match = savedConfigs.find((c) => String(c.id) === String(presetConfigId));
    if (match) {
      presetConfigApplied.current = true;
      handleLoadConfig(match);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [presetConfigId, savedConfigs, savedConfigsLoading]);

  // Save the current connection-mode setup (connections + table pairs + checks)
  // as a re-runnable configuration. Stores setup only, never results.
  const handleSaveConfig = async () => {
    setSaveConfigMessage('');
    setConnError('');

    if (!sourceConnectionId || !targetConnectionId) {
      setConnError('Select both a source and a target connection before saving.');
      return;
    }
    const name = saveConfigName.trim() || runName.trim();
    if (!name) {
      setConnError('Enter a name for this saved validation.');
      return;
    }
    // Persist only pairs that have a source selected, with their check config.
    const pairsToSave = tablePairs
      .filter((p) => p.source)
      .map((p) => ({
        source: p.source,
        target: p.target,
        config: {
          checks: p.config.checks,
          nullColumn: p.config.nullColumn,
          duplicateMatchKey: p.config.duplicateMatchKey,
          sumColumn: p.config.sumColumn,
          averageColumn: p.config.averageColumn,
          specificRowMatchKey: p.config.specificRowMatchKey,
          specificRowStart: p.config.specificRowStart,
          specificRowEnd: p.config.specificRowEnd,
        },
      }));

    if (pairsToSave.length === 0) {
      setConnError('Add at least one table pair before saving (set it up in Steps 2–3).');
      return;
    }

    setSavingConfig(true);
    try {
      await saveDirectConfig({
        name,
        source_connection_id: sourceConnectionId,
        target_connection_id: targetConnectionId,
        config: { runName: runName.trim(), tablePairs: pairsToSave },
      });
      setSaveConfigName('');
      setSaveConfigMessage(`Saved "${name}".`);
      await fetchSavedConfigs();
    } catch (err: any) {
      setConnError(
        err?.response?.data?.detail ||
          err?.detail ||
          err?.message ||
          'Unable to save this configuration.'
      );
    } finally {
      setSavingConfig(false);
    }
  };

  // Load a saved configuration back into the wizard form. Repopulates the
  // connections and table pairs/checks; does NOT auto-run.
  const handleLoadConfig = (cfg: DirectConfig) => {
    setConnError('');
    setSaveConfigMessage('');
    setDirectResults([]);

    const raw: any = cfg.config || {};
    const savedPairs: any[] = Array.isArray(raw.tablePairs) ? raw.tablePairs : [];

    // Set connections first; the table-discovery effects will fire on change.
    setSourceConnectionId(cfg.source_connection_id);
    setTargetConnectionId(cfg.target_connection_id);
    if (typeof raw.runName === 'string' && raw.runName) {
      setRunName(raw.runName);
    } else {
      setRunName(cfg.name);
    }

    // Rebuild table pairs with their saved check config. Columns are left
    // empty so the per-pair discovery effect refetches them for the pickers.
    const rebuilt: TablePair[] = savedPairs.length > 0
      ? savedPairs.map((p) => {
          const base = makeDefaultPairConfig();
          const c = p.config || {};
          return {
            source: p.source || '',
            target: p.target || '',
            config: {
              ...base,
              checks: Array.isArray(c.checks) ? c.checks : [...DEFAULT_CHECKS],
              nullColumn: c.nullColumn || '',
              duplicateMatchKey: c.duplicateMatchKey || '',
              sumColumn: c.sumColumn || '',
              averageColumn: c.averageColumn || '',
              specificRowMatchKey: c.specificRowMatchKey || '',
              specificRowStart: c.specificRowStart || '',
              specificRowEnd: c.specificRowEnd || '',
              columns: [],
              columnsLoading: false,
            },
          };
        })
      : [makeDefaultPair()];

    // The source-connection effect resets tablePairs to a default pair, so
    // apply the rebuilt pairs on the next tick to win that race.
    setTimeout(() => setTablePairs(rebuilt), 0);

    setLoadedConfigId(cfg.id);
    setSaveConfigMessage(`Loaded "${cfg.name}". Review Steps 2–3, then run.`);
  };

  const handleDeleteConfig = async (configId: number) => {
    try {
      await deleteDirectConfig(configId);
      if (loadedConfigId === configId) setLoadedConfigId(null);
      await fetchSavedConfigs();
    } catch (err: any) {
      setConnError(
        err?.response?.data?.detail ||
          err?.detail ||
          err?.message ||
          'Unable to delete this configuration.'
      );
    }
  };

  const connectionNameById = (id: number) =>
    connections.find((c) => c.id === id)?.name || `Connection ${id}`;

  // Discover tables when source connection changes
  useEffect(() => {
    setSourceConnTables([]);
    setTablePairs([makeDefaultPair()]);
    if (!sourceConnectionId) return;
    setSourceConnTablesLoading(true);
    setConnError('');
    getConnectionTables(sourceConnectionId)
      .then((res) => setSourceConnTables(res.tables || []))
      .catch((e) => setConnError(e?.detail || e?.message || 'Failed to load source tables'))
      .finally(() => setSourceConnTablesLoading(false));
  }, [sourceConnectionId]);

  // Discover tables when target connection changes
  useEffect(() => {
    setTargetConnTables([]);
    setTablePairs((prev) => prev.map((p) => ({ ...p, target: '' })));
    if (!targetConnectionId) return;
    setTargetConnTablesLoading(true);
    setConnError('');
    getConnectionTables(targetConnectionId)
      .then((res) => setTargetConnTables(res.tables || []))
      .catch((e) => setConnError(e?.detail || e?.message || 'Failed to load target tables'))
      .finally(() => setTargetConnTablesLoading(false));
  }, [targetConnectionId]);

  // Per-pair column discovery: whenever a pair has a source table selected
  // but its config has no columns loaded yet, fetch that table's columns
  // into THAT pair's config (so each pair's check pickers use its own cols).
  const pairSourcesKey = tablePairs.map((p) => p.source).join('|');
  useEffect(() => {
    if (mode !== 'connection' || !sourceConnectionId) return;
    tablePairs.forEach((pair, index) => {
      if (!pair.source) return;
      if (pair.config.columns.length > 0 || pair.config.columnsLoading) return;
      const found = sourceConnTables.find((t) => `${t.schema}.${t.table}` === pair.source);
      if (!found) return;
      // mark loading for this pair
      setTablePairs((prev) => prev.map((p, i) =>
        i === index ? { ...p, config: { ...p.config, columnsLoading: true } } : p));
      getConnectionColumns(sourceConnectionId, found.schema, found.table)
        .then((res) => {
          const cols = (res.columns || []).map((c) => c.column_name);
          setTablePairs((prev) => prev.map((p, i) =>
            i === index ? { ...p, config: { ...p.config, columns: cols, columnsLoading: false } } : p));
        })
        .catch(() => {
          setTablePairs((prev) => prev.map((p, i) =>
            i === index ? { ...p, config: { ...p.config, columns: [], columnsLoading: false } } : p));
        });
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, sourceConnectionId, pairSourcesKey, sourceConnTables]);

  // Fully-specified pairs (both sides chosen), resolved to table objects
  const resolvedPairs = tablePairs
    .map((p) => ({
      source: sourceConnTables.find((t) => `${t.schema}.${t.table}` === p.source),
      target: targetConnTables.find((t) => `${t.schema}.${t.table}` === p.target),
      sourceSel: p.source,
      targetSel: p.target,
      config: p.config,
    }))
    .filter((p) => p.source && p.target);

  // Pair row helpers
  const addTablePair = () => setTablePairs((prev) => [...prev, makeDefaultPair()]);
  const removeTablePair = (index: number) =>
    setTablePairs((prev) => prev.filter((_, i) => i !== index));
  const updateTablePair = (index: number, side: 'source' | 'target', value: string) =>
    setTablePairs((prev) => prev.map((p, i) => {
      if (i !== index) return p;
      if (side === 'source' && value !== p.source) {
        // Source changed → reset that pair's columns so they're re-fetched
        return { ...p, source: value, config: { ...p.config, columns: [], columnsLoading: false } };
      }
      return { ...p, [side]: value };
    }));

  // Per-pair check config helpers
  const togglePairCheck = (index: number, check: string) => {
    setTablePairs((prev) => prev.map((p, i) => {
      if (i !== index) return p;
      const checks = p.config.checks.includes(check)
        ? p.config.checks.filter((c) => c !== check)
        : [...p.config.checks, check];
      return { ...p, config: { ...p.config, checks } };
    }));
  };

  const updatePairConfigField = (index: number, field: keyof PairCheckConfig, value: any) => {
    setTablePairs((prev) => prev.map((p, i) => {
      if (i !== index) return p;
      return { ...p, config: { ...p.config, [field]: value } };
    }));
  };

  // Set every table pair to just the default checks (Row Count + Schema).
  const runDefaultsForAll = () => {
    setTablePairs((prev) => prev.map((p) => ({
      ...p,
      config: {
        ...p.config,
        checks: [...DEFAULT_CHECKS],
        // defaults don't need columns; leave column params as-is
      },
    })));
  };

  // Copy the FIRST pair's check config (checks + column params) to all pairs.
  const applyFirstPairToAll = () => {
    setTablePairs((prev) => {
      if (prev.length === 0) return prev;
      const src = prev[0].config;
      return prev.map((p, i) => {
        if (i === 0) return p;
        return {
          ...p,
          config: {
            ...p.config,          // keep this pair's own discovered columns + loading
            checks: [...src.checks],
            nullColumn: src.nullColumn,
            duplicateMatchKey: src.duplicateMatchKey,
            sumColumn: src.sumColumn,
            averageColumn: src.averageColumn,
            specificRowMatchKey: src.specificRowMatchKey,
            specificRowStart: src.specificRowStart,
            specificRowEnd: src.specificRowEnd,
          },
        };
      });
    });
  };

  // =========================================================
  // MIGRATION CHANGE
  // =========================================================

  const handleMigrationChange = async (value: string) => {
    setMigration(value);
    setError('');
    setTableError('');

    if (!value) {
      setMigrationId(null);
      setSourceName('');
      setTargetName('');
      setAvailableTables([]);
      setSelectedTables([]);
      setAvailableColumns([]);
      return;
    }

    const id = Number(value);

    if (!Number.isFinite(id)) {
      setError('Invalid migration selected.');
      return;
    }

    setMigrationId(id);
    setLoadingTables(true);

    try {
      const info = await getMigrationInfo(id);

      /*
       * The backend may return additional migration fields
       * that are not included in the TypeScript interface.
       *
       * Casting here prevents TypeScript errors for fields such as:
       * target_name, target_type, source_tables, etc.
       */
      const migrationInfo: any = info;

      setSourceName(
        migrationInfo?.source_name ||
          migrationInfo?.source_connection_name ||
          migrationInfo?.source_type ||
          ''
      );

      setTargetName(
        migrationInfo?.target_name ||
          migrationInfo?.target_connection_name ||
          migrationInfo?.target_type ||
          ''
      );

      const tables =
        migrationInfo?.tables ??
        migrationInfo?.source_tables ??
        migrationInfo?.available_tables ??
        [];

      const normalizedTables = Array.isArray(tables)
        ? tables
            .map((table: any) => {
              if (typeof table === 'string') {
                return table;
              }

              return (
                table?.table_name ||
                table?.name ||
                ''
              );
            })
            .filter(Boolean)
        : [];

      setAvailableTables(normalizedTables);
    } catch (err: any) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          'Unable to load migration information.'
      );

      setAvailableTables([]);
    } finally {
      setLoadingTables(false);
    }
  };

  // =========================================================
  // TABLE CHANGE
  // =========================================================

  const handleTableChange = async (tableName: string) => {
    setTableError('');
    setAvailableColumns([]);

    if (!tableName || !migrationId) {
      return;
    }

    setLoadingColumns(true);

    try {
      const response = await getMigrationTableColumns(
        migrationId,
        tableName
      );

      const responseData: any = response;

      const columns =
        responseData?.columns ??
        responseData?.source_columns ??
        responseData ??
        [];

      const normalizedColumns = Array.isArray(columns)
        ? columns
            .map((column: any) => {
              if (typeof column === 'string') {
                return column;
              }

              return (
                column?.column_name ||
                column?.name ||
                column?.column ||
                ''
              );
            })
            .filter(Boolean)
        : [];

      setAvailableColumns(normalizedColumns);
    } catch (err: any) {
      setTableError(
        err?.response?.data?.detail ||
          err?.message ||
          'Unable to load columns for the selected table.'
      );
    } finally {
      setLoadingColumns(false);
    }
  };

  // =========================================================
  // DEMO DATA (for previewing the end-user experience without live DBs)
  // =========================================================

  const loadDemoData = () => {
    setError('');
    setTableError('');
    setRunError('');

    const demoMigrations = [
      { id: 9001, migration_name: 'Demo: SQL Server → Redshift (sales)' },
      { id: 9002, migration_name: 'Demo: BigQuery → Redshift (analytics)' },
    ];
    const demoTables = ['customers', 'orders', 'order_items', 'products'];
    const demoColumns = [
      'id',
      'customer_id',
      'order_id',
      'email',
      'amount',
      'quantity',
      'created_at',
      'status',
    ];

    setMigrations(demoMigrations);
    setMigration(String(demoMigrations[0].id));
    setMigrationId(demoMigrations[0].id);
    setRunName('Demo validation run');
    setSourceName('Demo SQL Server (sales_db)');
    setTargetName('Demo Redshift (analytics_dw)');
    setBedrockModel('anthropic.claude-3-5-sonnet');

    setAvailableTables(demoTables);
    setSelectedTables(['customers', 'orders']);
    setAvailableColumns(demoColumns);

    // Pre-select a representative mix of checks + their columns
    setSelectedChecks([
      'Row Count Validation',
      'Schema Validation',
      'NULL Validation',
      'Duplicate Validation',
      'SUM Validation',
    ]);
    setNullColumn('email');
    setDuplicateMatchKey('id');
    setSumColumn('amount');
    setAverageColumn('amount');
    setSpecificRowMatchKey('id');
    setSpecificRowStart('1');
    setSpecificRowEnd('100');

    setCurrentStep(0);
  };

  // =========================================================
  // CHECK SELECTION
  // =========================================================

  const toggleCheck = (check: string) => {
    setSelectedChecks((previous) =>
      previous.includes(check)
        ? previous.filter((item) => item !== check)
        : [...previous, check]
    );

    setError('');
  };

  const isCheckSelected = (check: string) =>
    selectedChecks.includes(check);

  // =========================================================
  // VALIDATE CURRENT STEP
  // =========================================================

  // =========================================================
// VALIDATE CURRENT STEP
// =========================================================

const validateCurrentStep = (): boolean => {
  setError('');

  // Step 1 - Source
  if (currentStep === 0) {
    if (mode === 'connection') {
      if (!sourceConnectionId || !targetConnectionId) {
        setError('Select both a source and a target connection.');
        return false;
      }
    } else if (!migrationId) {
      setError('Select a migration.');
      return false;
    }
    return true;
  }

  // Step 2 - Table selection
  if (currentStep === 1) {
    if (mode === 'connection') {
      if (resolvedPairs.length === 0) {
        setError('Select at least one complete source → target table pair.');
        return false;
      }
    } else if (selectedTables.length === 0) {
      setError('Select at least one table.');
      return false;
    }
    return true;
  }

  // Step 3 - Validation Checks
  if (currentStep === 2) {
    if (mode === 'connection') {
      // Per-pair: every pair must have at least one check
      const unconfigured = tablePairs.findIndex((p) => p.source && p.config.checks.length === 0);
      if (unconfigured >= 0) {
        setError(`"${tablePairs[unconfigured].source}" has no checks selected.`);
        return false;
      }
    } else if (selectedChecks.length === 0) {
      setError('Please select at least one validation check.');
      return false;
    }
    return true;
  }

  // Step 4 and Step 5
  return true;
};
  // =========================================================
  // NEXT / PREVIOUS
  // =========================================================

  const nextStep = () => {
    if (!validateCurrentStep()) {
      return;
    }

    setCurrentStep((previous) =>
      Math.min(
        previous + 1,
        STEPS.length - 1
      )
    );
  };

  const previousStep = () => {
    setError('');
    setRunError('');

    setCurrentStep((previous) =>
      Math.max(previous - 1, 0)
    );
  };

  // =========================================================
  // SELECTED MIGRATION NAME
  // =========================================================

  const selectedMigrationName =
    migrations.find(
      (item) =>
        String(
          item?.id ?? item?.migration_id
        ) === String(migration)
    )?.name ??
    migrations.find(
      (item) =>
        String(
          item?.id ?? item?.migration_id
        ) === String(migration)
    )?.migration_name ??
    migration;

  const toggleTableSelection = (tableName: string) => {
    setTableError('');

    if (selectedTables.includes(tableName)) {
      const next = selectedTables.filter(
        (table) => table !== tableName
      );
      setSelectedTables(next);

      if (next.length === 0) {
        setAvailableColumns([]);
      }
      return;
    }

    setSelectedTables([
      ...selectedTables,
      tableName,
    ]);

    // Load columns for the newly selected table so the validation
    // parameter controls continue to use real source columns.
    void handleTableChange(tableName);
  };

  // =========================================================
  // BUILD BACKEND REQUEST
  // =========================================================

  const buildValidationRequest =
    (): CreateValidationRunRequest => {
      if (!migrationId) {
        throw new Error(
          'Migration is required.'
        );
      }

      if (selectedTables.length === 0) {
        throw new Error(
          'At least one table is required.'
        );
      }

      return {
        migration_id: migrationId,

        tables: selectedTables,

        table_configs: selectedTables.map((tableName) => ({
          table_name: tableName,

          ddl_check: isCheckSelected(
            'Schema Validation'
          ),

          row_count_check: isCheckSelected(
            'Row Count Validation'
          ),

          data_match_check: false,

          null_check: isCheckSelected(
            'NULL Validation'
          ),

          null_column:
            nullColumn || undefined,

          duplicate_check: isCheckSelected(
            'Duplicate Validation'
          ),

          duplicate_match_key:
            duplicateMatchKey || undefined,

          sum_check: isCheckSelected(
            'SUM Validation'
          ),

          sum_column:
            sumColumn || undefined,

          average_check: isCheckSelected(
            'AVERAGE Validation'
          ),

          average_column:
            averageColumn || undefined,

          specific_row_check:
            isCheckSelected(
              'Specific Row Validation'
            ),

          specific_row_match_key:
            specificRowMatchKey || undefined,

          specific_row_start:
            specificRowStart
              ? Number(specificRowStart)
              : undefined,

          specific_row_end:
            specificRowEnd
              ? Number(specificRowEnd)
              : undefined,

          sampling_mode: 'all',
        })),

        bedrock_model:
          bedrockModel.trim() || undefined,

        run_name:
          runName.trim() || undefined,
      };
    };

  // =========================================================
  // RUN DIRECT VALIDATION (connection mode, ephemeral)
  // =========================================================

  const runConnectionValidation = async () => {
    setRunError('');
    setError('');
    setDirectResults([]);

    if (resolvedPairs.length === 0) {
      setRunError('Select at least one complete source → target table pair.');
      return;
    }
    // Verify every pair has at least one check
    const unconfigured = resolvedPairs.findIndex((p) => p.config.checks.length === 0);
    if (unconfigured >= 0) {
      setRunError(`Table pair "${resolvedPairs[unconfigured].sourceSel}" has no checks selected.`);
      return;
    }

    setDirectRunning(true);
    try {
      // Run each table pair through the direct-test endpoint with THAT PAIR's
      // own check config. Pairs run sequentially; one failure doesn't abort.
      const results: DirectValidationResponse[] = [];
      for (const pair of resolvedPairs) {
        const cfg = pair.config;
        try {
          const res = await runDirectValidationTest({
            source_connection_id: sourceConnectionId,
            target_connection_id: targetConnectionId,
            source_schema: pair.source!.schema,
            target_schema: pair.target!.schema,
            table_name: pair.source!.table,
            row_count: cfg.checks.includes('Row Count Validation'),
            ddl_check: cfg.checks.includes('Schema Validation'),
            null_check: cfg.checks.includes('NULL Validation'),
            null_column: cfg.nullColumn || undefined,
            duplicate_check: cfg.checks.includes('Duplicate Validation'),
            duplicate_match_key: cfg.duplicateMatchKey || undefined,
            sum_check: cfg.checks.includes('SUM Validation'),
            sum_column: cfg.sumColumn || undefined,
            average_check: cfg.checks.includes('AVERAGE Validation'),
            average_column: cfg.averageColumn || undefined,
            specific_row_check: cfg.checks.includes('Specific Row Validation'),
            specific_row_match_key: cfg.specificRowMatchKey || undefined,
            specific_row_start: cfg.specificRowStart ? Number(cfg.specificRowStart) : undefined,
            specific_row_end: cfg.specificRowEnd ? Number(cfg.specificRowEnd) : undefined,
          });
          results.push(res);
        } catch (err: any) {
          // Record a failed entry for this pair but keep going
          results.push({
            overall_status: 'error',
            source_engine: '',
            target_engine: '',
            source_connection: pair.sourceSel,
            target_connection: pair.targetSel,
            table_name: `${pair.source!.table} → ${pair.target!.table}`,
            checks: {
              _error: {
                status: 'error',
                error_message:
                  err?.response?.data?.detail ||
                  err?.detail ||
                  err?.message ||
                  'Validation failed for this table.',
              },
            },
          } as DirectValidationResponse);
        }
        // Progressive update so the user sees results fill in
        setDirectResults([...results]);
      }
    } catch (err: any) {
      setRunError(
        err?.response?.data?.detail ||
          err?.detail ||
          err?.message ||
          'Unable to run validation.'
      );
    } finally {
      setDirectRunning(false);
    }
  };

  // Convert direct (connection-mode) results into normalized report rows
  // Friendly labels for the direct-path check keys returned by the backend.
  const DIRECT_CHECK_LABELS: Record<string, string> = {
    row_count: 'Row Count',
    schema_check: 'Schema',
    null_check: 'NULL',
    duplicate_check: 'Duplicate',
    sum_check: 'SUM',
    average_check: 'AVERAGE',
    specific_row_check: 'Specific Row',
  };

  // Convert direct (connection-mode) results into normalized report rows.
  // For failed checks we also surface the exact row/column-level mismatches:
  //  - Schema: columns missing/extra/with type mismatches between source & target.
  //  - Specific Row: the sampled rows (by match key) whose values differ, plus
  //    rows missing in the target — including the differing column and values.
  const buildDirectReportRows = (): ValidationReportRow[] => {
    const rows: ValidationReportRow[] = [];
    directResults.forEach((result) => {
      const tableName = `${result.source_connection} → ${result.target_connection} · ${result.table_name}`;
      Object.entries(result.checks).forEach(([checkName, r]) => {
        const label =
          checkName === '_error' ? 'Error' : (DIRECT_CHECK_LABELS[checkName] || checkName);

        // Pull structured discrepancies out of the per-check details.
        let discrepancies: ReportDiscrepancy[] | undefined;
        const details = (r.details || null) as Record<string, any> | null;
        if (checkName === 'schema_check') {
          const d = extractDirectSchemaDiscrepancies(details);
          if (d.length > 0) discrepancies = d;
        } else if (
          checkName === 'specific_row_check' ||
          checkName === 'null_check' ||
          checkName === 'duplicate_check'
        ) {
          // These carry row/column-level mismatch samples in details.sample_discrepancies.
          const d = extractRecordDiscrepancies(details);
          if (d.length > 0) discrepancies = d;
        }

        // Readable one-line summary.
        let detailsText: string;
        if (r.error_message) {
          detailsText = `error: ${r.error_message}`;
        } else if (checkName === 'schema_check' && details) {
          const missing = (details.missing_in_target || []).length;
          const extra = (details.extra_in_target || []).length;
          const typeMism = (details.type_mismatches || []).length;
          detailsText = `source cols=${r.source_value ?? '—'}, target cols=${r.target_value ?? '—'}, missing=${missing}, extra=${extra}, type mismatches=${typeMism}`;
        } else if (checkName === 'specific_row_check' && details) {
          detailsText = `compared=${r.source_value ?? '—'}, matched=${details.matched ?? '—'}, missing=${details.missing ?? '—'}, mismatched=${details.mismatched ?? '—'}`;
        } else {
          detailsText = `source=${r.source_value ?? '—'}, target=${r.target_value ?? '—'}, diff=${r.difference ?? '—'}`;
        }

        rows.push({
          tableName,
          check: label,
          status: r.status,
          details: detailsText,
          discrepancies,
        });
      });
    });
    return rows;
  };

  const directReportFilename = () => `validation-direct-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}`;

  const handleDirectCsv = () => {
    if (directResults.length === 0) return;
    downloadCsv(directReportFilename(), buildDirectReportRows());
  };

  const handleDirectPdf = () => {
    if (directResults.length === 0) return;
    const overall = directResults.some((r) => r.overall_status === 'error')
      ? 'error'
      : directResults.some((r) => r.overall_status === 'failed')
        ? 'failed'
        : 'passed';
    downloadValidationPdf(
      directReportFilename(),
      {
        title: runName.trim() || 'Direct Connection Validation',
        subtitle: `${connections.find((c) => c.id === sourceConnectionId)?.name || 'Source'} -> ${connections.find((c) => c.id === targetConnectionId)?.name || 'Target'}`,
        overallStatus: overall,
        summary: [
          { label: 'Table pairs', value: directResults.length },
          { label: 'Passed', value: directResults.filter((r) => r.overall_status === 'passed').length },
          { label: 'Failed', value: directResults.filter((r) => r.overall_status === 'failed').length },
          { label: 'Errors', value: directResults.filter((r) => r.overall_status === 'error').length },
        ],
      },
      buildDirectReportRows(),
    );
  };

  // =========================================================
  // RUN VALIDATION
  // =========================================================

  const runValidation = async () => {
    setRunError('');
    setError('');

    if (!migrationId) {
      setRunError(
        'Migration is required.'
      );
      return;
    }

    if (selectedTables.length === 0) {
      setRunError(
        'At least one table is required.'
      );
      return;
    }

    setRunSubmitting(true);

    try {
      const request =
        buildValidationRequest();

      const createdRun =
        await createValidationRun(
          request
        );

      if (!createdRun?.id) {
        throw new Error(
          'Validation run was created but no run ID was returned.'
        );
      }

      navigate(
        `/validations/${createdRun.id}`
      );
    } catch (err: any) {
      setRunError(
        err?.response?.data?.detail ||
          err?.message ||
          'Unable to create validation run.'
      );
    } finally {
      setRunSubmitting(false);
    }
  };

  // =========================================================
  // STEP INDICATOR
  // =========================================================

  const renderStepIndicator = () => (
    <div className="validation-wizard-steps">
      {STEPS.map((step, index) => (
        <div
          key={step}
          className={`validation-wizard-step ${
            index === currentStep
              ? 'active'
              : index < currentStep
              ? 'completed'
              : ''
          }`}
        >
          <div className="validation-wizard-step-number">
            {index + 1}
          </div>

          <div className="validation-wizard-step-label">
            {step}
          </div>
        </div>
      ))}
    </div>
  );

  // =========================================================
  // STEP 1 - CONNECTIONS
  // =========================================================

  const renderConnectionsStep = () => (
    <div className="validation-wizard-content">
      <h2>Source</h2>

      <p className="validation-wizard-description">
        Choose how to set up this validation: from a completed migration
        (saved to your dashboard) or directly between two connections
        (a quick test — results shown here, not saved).
      </p>

      {/* Mode toggle */}
      <div className="validation-mode-toggle">
        <button
          type="button"
          className={`validation-mode-option ${mode === 'migration' ? 'active' : ''}`}
          onClick={() => { setMode('migration'); setError(''); }}
        >
          <span className="validation-mode-title">From Migration</span>
          <span className="validation-mode-desc">Validate a completed migration · saved to dashboard</span>
        </button>
        <button
          type="button"
          className={`validation-mode-option ${mode === 'connection' ? 'active' : ''}`}
          onClick={() => { setMode('connection'); setError(''); }}
        >
          <span className="validation-mode-title">From Connections</span>
          <span className="validation-mode-desc">Quick test between two connections · results not saved</span>
        </button>
      </div>

      <div className="validation-form-group">
        <label htmlFor="runName">
          Run Name
        </label>

        <input
          id="runName"
          type="text"
          value={runName}
          onChange={(event) =>
            setRunName(event.target.value)
          }
          placeholder="Enter validation run name"
        />
      </div>

      {mode === 'connection' ? (
        <>
          <div className="validation-form-group">
            <label htmlFor="sourceConn">Source connection *</label>
            <select
              id="sourceConn"
              value={sourceConnectionId}
              onChange={(e) => setSourceConnectionId(Number(e.target.value))}
            >
              <option value={0}>Select source connection</option>
              {connections.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({(c.type || c.database || '').toLowerCase()})
                </option>
              ))}
            </select>
          </div>

          <div className="validation-form-group">
            <label htmlFor="targetConn">Target connection *</label>
            <select
              id="targetConn"
              value={targetConnectionId}
              onChange={(e) => setTargetConnectionId(Number(e.target.value))}
            >
              <option value={0}>Select target connection</option>
              {connections.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({(c.type || c.database || '').toLowerCase()})
                </option>
              ))}
            </select>
          </div>

          {connError && <div className="validation-error">{connError}</div>}

          {/* Previously saved validations — click to repopulate the form */}
          <div className="validation-saved-list">
            <div className="validation-saved-list-head">
              <h3>Saved validations</h3>
              {savedConfigsLoading && (
                <span className="validation-saved-list-loading">Loading…</span>
              )}
            </div>

            {!savedConfigsLoading && savedConfigs.length === 0 ? (
              <div className="validation-saved-empty">
                No saved validations yet. Set one up and click “Save this
                configuration” to reuse it later.
              </div>
            ) : (
              <ul className="validation-saved-items">
                {savedConfigs.map((cfg) => (
                  <li
                    key={cfg.id}
                    className={`validation-saved-item ${loadedConfigId === cfg.id ? 'loaded' : ''}`}
                  >
                    <button
                      type="button"
                      className="validation-saved-item-main"
                      onClick={() => handleLoadConfig(cfg)}
                      title="Load this setup into the wizard"
                    >
                      <span className="validation-saved-item-name">{cfg.name}</span>
                      <span className="validation-saved-item-meta">
                        {connectionNameById(cfg.source_connection_id)} →{' '}
                        {connectionNameById(cfg.target_connection_id)}
                        {Array.isArray((cfg.config as any)?.tablePairs)
                          ? ` · ${(cfg.config as any).tablePairs.length} pair${(cfg.config as any).tablePairs.length === 1 ? '' : 's'}`
                          : ''}
                      </span>
                    </button>
                    <button
                      type="button"
                      className="validation-saved-item-delete"
                      onClick={() => handleDeleteConfig(cfg.id)}
                      aria-label={`Delete saved validation ${cfg.name}`}
                      title="Delete this saved validation"
                    >
                      ✕
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      ) : (
      <>
      <div className="validation-form-group">
        <label htmlFor="migration">
          Migration *
        </label>

        <select
          id="migration"
          value={migration}
          onChange={(event) =>
            handleMigrationChange(
              event.target.value
            )
          }
          disabled={loadingMigrations}
        >
          <option value="">
            {loadingMigrations
              ? 'Loading migrations...'
              : 'Select a migration'}
          </option>

          {migrations.map((item) => {
            const id =
              item?.id ??
              item?.migration_id;

            const name =
              item?.name ??
              item?.migration_name ??
              `Migration ${id}`;

            return (
              <option
                key={id}
                value={id}
              >
                {name}
              </option>
            );
          })}
        </select>
      </div>

      <div className="validation-form-group">
        <label htmlFor="bedrockModel">
          Bedrock Model
          <span className="optional-label">
            Optional
          </span>
        </label>

        <select
  value={bedrockModel}
  onChange={(e) => setBedrockModel(e.target.value)}
>
  <option value="">Select a Bedrock model</option>
  <option value="amazon.nova-lite-v1:0">Amazon Nova Lite</option>
  <option value="amazon.nova-pro-v1:0">Amazon Nova Pro</option>
  <option value="anthropic.claude-3-5-sonnet">Claude 3.5 Sonnet</option>
  <option value="anthropic.claude-3-haiku">Claude 3 Haiku</option>
</select>
      </div>

      {migrationId && (
        <div className="validation-connection-summary">
          <div>
            <strong>Migration:</strong>{' '}
            {selectedMigrationName}
          </div>

          {sourceName && (
            <div>
              <strong>Source:</strong>{' '}
              {sourceName}
            </div>
          )}

          {targetName && (
            <div>
              <strong>Target:</strong>{' '}
              {targetName}
            </div>
          )}
        </div>
      )}
      </>
      )}
    </div>
  );

  // =========================================================
  // STEP 2 - DATA DEFINITION
  // =========================================================

  const renderConnectionTableStep = () => (
    <div className="validation-wizard-content">
      <h2>Table Selection</h2>
      <p className="validation-wizard-description">
        Map one or more source tables to their target tables. Each pair is
        validated with the checks you select next.
      </p>

      <div className="validation-pair-list">
        <div className="validation-pair-head">
          <span>Source table</span>
          <span />
          <span>Target table</span>
          <span />
        </div>

        {tablePairs.map((pair, index) => (
          <div className="validation-pair-row" key={index}>
            <select
              value={pair.source}
              onChange={(e) => updateTablePair(index, 'source', e.target.value)}
              disabled={!sourceConnectionId || sourceConnTablesLoading}
            >
              <option value="">
                {sourceConnTablesLoading
                  ? 'Loading…'
                  : sourceConnectionId ? 'Select source table' : 'Pick a source connection'}
              </option>
              {sourceConnTables.map((t) => (
                <option key={`${t.schema}.${t.table}`} value={`${t.schema}.${t.table}`}>
                  {t.schema}.{t.table}
                </option>
              ))}
            </select>

            <span className="validation-pair-arrow">→</span>

            <select
              value={pair.target}
              onChange={(e) => updateTablePair(index, 'target', e.target.value)}
              disabled={!targetConnectionId || targetConnTablesLoading}
            >
              <option value="">
                {targetConnTablesLoading
                  ? 'Loading…'
                  : targetConnectionId ? 'Select target table' : 'Pick a target connection'}
              </option>
              {targetConnTables.map((t) => (
                <option key={`${t.schema}.${t.table}`} value={`${t.schema}.${t.table}`}>
                  {t.schema}.{t.table}
                </option>
              ))}
            </select>

            <button
              type="button"
              className="validation-pair-remove"
              onClick={() => removeTablePair(index)}
              disabled={tablePairs.length === 1}
              aria-label="Remove table pair"
              title={tablePairs.length === 1 ? 'At least one pair is required' : 'Remove'}
            >
              ✕
            </button>
          </div>
        ))}
      </div>

      <button
        type="button"
        className="validation-secondary-btn validation-pair-add"
        onClick={addTablePair}
      >
        + Add table pair
      </button>

      <div className="validation-pair-count">
        {resolvedPairs.length} table pair{resolvedPairs.length === 1 ? '' : 's'} ready
      </div>

      {connError && <div className="validation-error">{connError}</div>}
    </div>
  );

  const renderDataDefinitionStep = () => (
  <div className="validation-wizard-content">
    <h2>Table Selection</h2>

    <p className="validation-wizard-description">
      Select a source table. The matching target table will be mapped
      automatically for validation.
    </p>

    <div className="validation-table-mapping">

      {/* SOURCE */}
      <div className="validation-table-card source-card">
        <div className="validation-table-card-header">
          <div>
            <span className="validation-table-card-eyebrow">
              SOURCE
            </span>

            <h3>Source Table</h3>
          </div>

          <div className="validation-table-badge source-badge">
            Source
          </div>
        </div>

        <div className="validation-table-card-body">
          <label>
            Select tables
          </label>

          <div className="validation-table-multi-select">
            {loadingTables ? (
              <div className="validation-table-loading">
                Loading tables...
              </div>
            ) : availableTables.length === 0 ? (
              <div className="validation-table-empty">
                No source tables available.
              </div>
            ) : (
              availableTables.map((table) => (
                <label
                  key={table}
                  className={`validation-table-option ${
                    selectedTables.includes(table)
                      ? 'selected'
                      : ''
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selectedTables.includes(table)}
                    onChange={() => toggleTableSelection(table)}
                    disabled={loadingTables}
                  />
                  <span>{table}</span>
                </label>
              ))
            )}
          </div>

          <p className="validation-table-help">
            Select one or more source tables. The matching target tables will be mapped automatically.
          </p>

          <div className="validation-table-selection-count">
            {selectedTables.length} table{selectedTables.length === 1 ? '' : 's'} selected
          </div>
        </div>
      </div>

      {/* MAPPING CONNECTOR */}
      <div className="validation-table-connector">
        <div className="validation-table-connector-line" />

        <div className="validation-table-connector-icon">
          →
        </div>

        <div className="validation-table-connector-line" />
      </div>

      {/* TARGET */}
      <div className="validation-table-card target-card">
        <div className="validation-table-card-header">
          <div>
            <span className="validation-table-card-eyebrow">
              TARGET
            </span>

            <h3>Target Table</h3>
          </div>

          <div className="validation-table-badge target-badge">
            Mapped
          </div>
        </div>

        <div className="validation-table-card-body">
          <label>
            Mapped tables
          </label>

          {selectedTables.length === 0 ? (
            <div className="validation-table-target-empty">
              Target tables will appear here after selection.
            </div>
          ) : (
            <div className="validation-table-target-list">
              {selectedTables.map((table) => (
                <div key={table} className="validation-table-target-item">
                  <span>{table}</span>
                  <span className="validation-table-mapped-check">
                    ✓
                  </span>
                </div>
              ))}
            </div>
          )}

          <div className="validation-table-mapped-status">
            <span className="validation-table-mapped-check">
              ✓
            </span>

            <span>
              Each selected source table is mapped to the same table name in the target.
            </span>
          </div>
        </div>
      </div>

    </div>

    {tableError && (
      <div className="validation-error">
        {tableError}
      </div>
    )}
  </div>
);
  // =========================================================
  // STEP 3 - VALIDATION CHECKS (connection mode: per-pair)
  // =========================================================

  const renderPerPairChecksStep = () => {
    return (
      <div className="validation-wizard-content">
        <h2>Validation Checks</h2>
        <p className="validation-wizard-description">
          Configure which checks to run on each table pair. Row Count and Schema
          run by default; you can turn them off or add more per pair.
        </p>

        {/* Quick actions */}
        <div className="validation-checks-toolbar">
          <button
            type="button"
            className="validation-secondary-btn"
            onClick={runDefaultsForAll}
            title="Set every table pair to Row Count + Schema only"
          >
            Run default (Row + Schema for all)
          </button>
        </div>

        {tablePairs.map((pair, index) => {
          if (!pair.source) return null;
          const cfg = pair.config;
          const cols = cfg.columns;
          const pairLabel = pair.source
            ? `${pair.source} → ${pair.target || '(no target)'}`
            : `Pair ${index + 1}`;
          const isFirstConfigurable = tablePairs.findIndex((p) => p.source) === index;
          const configurablePairCount = tablePairs.filter((p) => p.source).length;

          return (
            <div key={index} className="validation-pair-check-card">
              <div className="validation-pair-check-header">
                <span className="validation-pair-check-label">{pairLabel}</span>
                <div className="validation-pair-check-header-right">
                  {isFirstConfigurable && configurablePairCount > 1 && (
                    <button
                      type="button"
                      className="validation-apply-all-btn"
                      onClick={applyFirstPairToAll}
                      title="Copy this pair's checks and columns to all other pairs"
                    >
                      Apply to all
                    </button>
                  )}
                  <span className="validation-pair-check-count">
                    {cfg.checks.length} check{cfg.checks.length === 1 ? '' : 's'}
                  </span>
                </div>
              </div>

              <div className="validation-pair-checks-grid">
                {CHECKS.map((check) => {
                  const selected = cfg.checks.includes(check);
                  return (
                    <div key={check} className="validation-pair-check-item">
                      <label className="validation-check-item">
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={() => togglePairCheck(index, check)}
                        />
                        <span>{check}</span>
                      </label>

                      {/* Column pickers for checks that need them */}
                      {check === 'NULL Validation' && selected && (
                        <select
                          className="validation-pair-col-select"
                          value={cfg.nullColumn}
                          onChange={(e) => updatePairConfigField(index, 'nullColumn', e.target.value)}
                        >
                          <option value="">Select column</option>
                          {cols.map((c) => <option key={c} value={c}>{c}</option>)}
                        </select>
                      )}

                      {check === 'Duplicate Validation' && selected && (
                        <select
                          className="validation-pair-col-select"
                          value={cfg.duplicateMatchKey}
                          onChange={(e) => updatePairConfigField(index, 'duplicateMatchKey', e.target.value)}
                        >
                          <option value="">Select match key</option>
                          {cols.map((c) => <option key={c} value={c}>{c}</option>)}
                        </select>
                      )}

                      {check === 'SUM Validation' && selected && (
                        <select
                          className="validation-pair-col-select"
                          value={cfg.sumColumn}
                          onChange={(e) => updatePairConfigField(index, 'sumColumn', e.target.value)}
                        >
                          <option value="">Select numeric column</option>
                          {cols.map((c) => <option key={c} value={c}>{c}</option>)}
                        </select>
                      )}

                      {check === 'AVERAGE Validation' && selected && (
                        <select
                          className="validation-pair-col-select"
                          value={cfg.averageColumn}
                          onChange={(e) => updatePairConfigField(index, 'averageColumn', e.target.value)}
                        >
                          <option value="">Select numeric column</option>
                          {cols.map((c) => <option key={c} value={c}>{c}</option>)}
                        </select>
                      )}

                      {check === 'Specific Row Validation' && selected && (
                        <div className="validation-pair-specific-row">
                          <select
                            className="validation-pair-col-select"
                            value={cfg.specificRowMatchKey}
                            onChange={(e) => updatePairConfigField(index, 'specificRowMatchKey', e.target.value)}
                          >
                            <option value="">Select match key</option>
                            {cols.map((c) => <option key={c} value={c}>{c}</option>)}
                          </select>
                          <input
                            type="number"
                            min="1"
                            placeholder="Start"
                            value={cfg.specificRowStart}
                            onChange={(e) => updatePairConfigField(index, 'specificRowStart', e.target.value)}
                            className="validation-pair-num-input"
                          />
                          <input
                            type="number"
                            min="1"
                            placeholder="End"
                            value={cfg.specificRowEnd}
                            onChange={(e) => updatePairConfigField(index, 'specificRowEnd', e.target.value)}
                            className="validation-pair-num-input"
                          />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {cfg.columnsLoading && (
                <div className="validation-pair-loading">Loading columns…</div>
              )}
            </div>
          );
        })}

        {tablePairs.every((p) => !p.source) && (
          <div className="validation-error">
            Go back to Step 2 and select at least one table pair.
          </div>
        )}
      </div>
    );
  };

  // =========================================================
  // STEP 3 - VALIDATION CHECKS (migration mode: global)
  // =========================================================

  const renderValidationChecksStep = () => (
  <div className="validation-wizard-content">
    <h2>Validation Checks</h2>

    <p className="validation-wizard-description">
      Select the checks you want to execute for the selected table.
    </p>

    <div className="validation-checks-list">
      {CHECKS.map((check) => (
        <div
          key={check}
          className="validation-check-wrapper"
        >
          <label className="validation-check-item">
            <input
              type="checkbox"
              checked={isCheckSelected(check)}
              onChange={() => toggleCheck(check)}
            />

            <span>{check}</span>
          </label>

          {/* NULL VALIDATION */}
          {check === 'NULL Validation' &&
            isCheckSelected(check) && (
              <div className="validation-check-config">
                <label htmlFor="nullColumn">
                  NULL Validation — Column
                </label>

                <select
                  id="nullColumn"
                  value={nullColumn}
                  onChange={(event) =>
                    setNullColumn(event.target.value)
                  }
                >
                  <option value="">Select column</option>

                  {availableColumns.map((column) => (
                    <option
                      key={column}
                      value={column}
                    >
                      {column}
                    </option>
                  ))}
                </select>
              </div>
            )}

          {/* DUPLICATE VALIDATION */}
          {check === 'Duplicate Validation' &&
            isCheckSelected(check) && (
              <div className="validation-check-config">
                <label htmlFor="duplicateMatchKey">
                  Duplicate Validation — Match Key
                </label>

                <select
                  id="duplicateMatchKey"
                  value={duplicateMatchKey}
                  onChange={(event) =>
                    setDuplicateMatchKey(event.target.value)
                  }
                >
                  <option value="">
                    Select Match Key
                  </option>

                  {availableColumns.map((column) => (
                    <option
                      key={column}
                      value={column}
                    >
                      {column}
                    </option>
                  ))}
                </select>
              </div>
            )}

          {/* SUM VALIDATION */}
          {check === 'SUM Validation' &&
            isCheckSelected(check) && (
              <div className="validation-check-config">
                <label htmlFor="sumColumn">
                  SUM Validation — Column
                </label>

                <select
                  id="sumColumn"
                  value={sumColumn}
                  onChange={(event) =>
                    setSumColumn(event.target.value)
                  }
                >
                  <option value="">
                    Select numeric column
                  </option>

                  {availableColumns.map((column) => (
                    <option
                      key={column}
                      value={column}
                    >
                      {column}
                    </option>
                  ))}
                </select>
              </div>
            )}

          {/* AVERAGE VALIDATION */}
          {check === 'AVERAGE Validation' &&
            isCheckSelected(check) && (
              <div className="validation-check-config">
                <label htmlFor="averageColumn">
                  AVERAGE Validation — Column
                </label>

                <select
                  id="averageColumn"
                  value={averageColumn}
                  onChange={(event) =>
                    setAverageColumn(event.target.value)
                  }
                >
                  <option value="">
                    Select numeric column
                  </option>

                  {availableColumns.map((column) => (
                    <option
                      key={column}
                      value={column}
                    >
                      {column}
                    </option>
                  ))}
                </select>
              </div>
            )}

          {/* SPECIFIC ROW VALIDATION */}
          {check === 'Specific Row Validation' &&
            isCheckSelected(check) && (
              <div className="validation-check-config">
                <label htmlFor="specificRowMatchKey">
                  Specific Row Validation — Match Key
                </label>

                <select
                  id="specificRowMatchKey"
                  value={specificRowMatchKey}
                  onChange={(event) =>
                    setSpecificRowMatchKey(
                      event.target.value
                    )
                  }
                >
                  <option value="">
                    Select Match Key
                  </option>

                  {availableColumns.map((column) => (
                    <option
                      key={column}
                      value={column}
                    >
                      {column}
                    </option>
                  ))}
                </select>

                <div className="validation-row-range">
                  <div>
                    <label htmlFor="specificRowStart">
                      Start Row
                    </label>

                    <input
                      id="specificRowStart"
                      type="number"
                      min="1"
                      value={specificRowStart}
                      onChange={(event) =>
                        setSpecificRowStart(
                          event.target.value
                        )
                      }
                      placeholder="1"
                    />
                  </div>

                  <div>
                    <label htmlFor="specificRowEnd">
                      End Row
                    </label>

                    <input
                      id="specificRowEnd"
                      type="number"
                      min="1"
                      value={specificRowEnd}
                      onChange={(event) =>
                        setSpecificRowEnd(
                          event.target.value
                        )
                      }
                      placeholder="100"
                    />
                  </div>
                </div>
              </div>
            )}
        </div>
      ))}
    </div>
  </div>
);

  // =========================================================
  // STEP 4 - CONFIGURATION
  // =========================================================

  const renderConfigurationStep = () => (
  <div className="validation-wizard-content">
    <h2>Configuration</h2>

    <p className="validation-wizard-description">
      Review the migration, table, and validation
      configuration before starting the run.
    </p>

    {/* Validation Run */}
    <div className="validation-config-section">
      <div className="validation-config-section-header">
        <h3>Validation Run</h3>
        <span>Run information</span>
      </div>

      <div className="validation-config-grid">
        <div className="validation-config-item">
          <span className="validation-config-label">
            Run Name
          </span>
          <span className="validation-config-value">
            {runName || 'Not specified'}
          </span>
        </div>

        <div className="validation-config-item">
          <span className="validation-config-label">
            {mode === 'connection' ? 'Mode' : 'Migration'}
          </span>
          <span className="validation-config-value">
            {mode === 'connection'
              ? 'Direct connection test (not saved)'
              : (selectedMigrationName || 'Not selected')}
          </span>
        </div>
      </div>
    </div>

    {/* Data Mapping */}
    <div className="validation-config-section">
      <div className="validation-config-section-header">
        <h3>Data Mapping</h3>
        <span>Source and target information</span>
      </div>

      <div className="validation-config-grid">
        <div className="validation-config-item">
          <span className="validation-config-label">
            Source
          </span>
          <span className="validation-config-value">
            {mode === 'connection'
              ? (connections.find((c) => c.id === sourceConnectionId)?.name || 'Not selected')
              : (sourceName || 'From migration')}
          </span>
        </div>

        <div className="validation-config-item">
          <span className="validation-config-label">
            Target
          </span>
          <span className="validation-config-value">
            {mode === 'connection'
              ? (connections.find((c) => c.id === targetConnectionId)?.name || 'Not selected')
              : (targetName || 'From migration')}
          </span>
        </div>

        <div className="validation-config-item validation-config-item-full">
          <span className="validation-config-label">
            Table
          </span>
          <span className="validation-config-value validation-config-table">
            {mode === 'connection'
              ? (resolvedPairs.length
                  ? resolvedPairs.map((p) => `${p.sourceSel} → ${p.targetSel}`).join(', ')
                  : 'Not selected')
              : (selectedTables.length ? selectedTables.join(', ') : 'Not selected')}
          </span>
        </div>
      </div>
    </div>

    {/* Validation Checks */}
    <div className="validation-config-section">
      <div className="validation-config-section-header">
        <h3>Validation Checks</h3>
        <span>
          {mode === 'connection'
            ? `${tablePairs.filter((p) => p.source).length} table(s), per-pair config`
            : `${selectedChecks.length} check${selectedChecks.length === 1 ? '' : 's'} selected`}
        </span>
      </div>

      {mode === 'connection' ? (
        tablePairs.filter((p) => p.source).length === 0 ? (
          <div className="validation-config-empty">No table pairs configured.</div>
        ) : (
          <div className="validation-config-checks">
            {tablePairs.filter((p) => p.source).map((p, i) => (
              <div key={i} className="validation-config-check">
                <span className="validation-config-check-icon">✓</span>
                <span>{p.source}: {p.config.checks.length > 0 ? p.config.checks.join(', ') : 'no checks'}</span>
              </div>
            ))}
          </div>
        )
      ) : selectedChecks.length === 0 ? (
        <div className="validation-config-empty">
          No validation checks selected.
        </div>
      ) : (
        <div className="validation-config-checks">
          {selectedChecks.map((check) => (
            <div
              key={check}
              className="validation-config-check"
            >
              <span className="validation-config-check-icon">
                ✓
              </span>

              <span>{check}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  </div>
);

  // =========================================================
  // STEP 5 - RESULTS
  // =========================================================

  const renderResultsStep = () => (
    <div className="validation-wizard-content">
      <h2>Results</h2>

      {mode === 'connection' ? (
        <>
          <p className="validation-wizard-description">
            Run the checks directly between the selected connections. Results
            appear below and are not saved to the dashboard.
          </p>

          {/* Save this setup as a re-runnable configuration (setup only,
              never results). Appears in the Saved validations list in Step 1. */}
          <div className="validation-save-config">
            <div className="validation-save-config-row">
              <input
                type="text"
                className="validation-save-config-input"
                placeholder="Name this validation (e.g. Nightly sales check)"
                value={saveConfigName}
                onChange={(e) => setSaveConfigName(e.target.value)}
              />
              <button
                type="button"
                className="validation-secondary-btn"
                onClick={handleSaveConfig}
                disabled={savingConfig}
                title="Save connections + table pairs + checks so you can re-run later"
              >
                {savingConfig ? 'Saving…' : 'Save this configuration'}
              </button>
            </div>
            {saveConfigMessage && (
              <div className="validation-save-config-msg">{saveConfigMessage}</div>
            )}
            {connError && <div className="validation-error">{connError}</div>}
            <p className="validation-save-config-help">
              Saves the setup only (connections, table pairs, and checks) so you
              can load and re-run it from Step 1 later. Results are never stored.
            </p>
          </div>

          {directResults.length === 0 && (
            <div className="validation-ready-card">
              <h3>Ready to Run Validation</h3>
              <p>
                Click <strong>Run Validation</strong> to validate{' '}
                <strong>{resolvedPairs.length}</strong> table
                {resolvedPairs.length === 1 ? '' : 's'} between the selected connections.
              </p>
              <div className="validation-ready-summary">
                <div><strong>Table pairs:</strong> {resolvedPairs.length}</div>
                <div><strong>Checks:</strong> {resolvedPairs.reduce((sum, p) => sum + p.config.checks.length, 0)} total across all pairs</div>
              </div>
            </div>
          )}

          {directResults.length > 0 && (
            <div className="validation-direct-export">
              <span className="validation-direct-export-label">
                Save these results (they are not stored in the dashboard):
              </span>
              <div className="validation-direct-export-btns">
                <button type="button" className="validation-secondary-btn" onClick={handleDirectCsv}>
                  Download CSV
                </button>
                <button type="button" className="validation-secondary-btn" onClick={handleDirectPdf}>
                  Download PDF
                </button>
              </div>
            </div>
          )}

          {directResults.map((result, idx) => (
            <div className="validation-direct-results" key={idx}>
              <div className="validation-direct-results-header">
                <span>
                  {result.source_connection}
                  {result.source_engine ? ` (${result.source_engine})` : ''} →{' '}
                  {result.target_connection}
                  {result.target_engine ? ` (${result.target_engine})` : ''} ·{' '}
                  {result.table_name}
                </span>
                <span className={`validation-direct-badge ${result.overall_status}`}>
                  {result.overall_status}
                </span>
              </div>
              <table className="validation-direct-table">
                <thead>
                  <tr>
                    <th>Check</th>
                    <th>Source</th>
                    <th>Target</th>
                    <th>Difference</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(result.checks).map(([name, r]) => (
                    <tr key={name}>
                      <td>{name === '_error' ? 'Error' : name}</td>
                      <td>{r.error_message ? '—' : String(r.source_value ?? '—')}</td>
                      <td>{r.error_message ? '—' : String(r.target_value ?? '—')}</td>
                      <td>{r.error_message ? '—' : String(r.difference ?? '—')}</td>
                      <td>
                        <span className={`validation-direct-badge ${r.status}`}>{r.status}</span>
                        {r.error_message && (
                          <div className="validation-direct-err" title={r.error_message}>
                            {r.error_message}
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </>
      ) : (
        <>
          <p className="validation-wizard-description">
            The validation run is ready to start with
            the configuration selected above.
          </p>

          <div className="validation-ready-card">
            <h3>
              Ready to Run Validation
            </h3>

            <p>
              Click{' '}
              <strong>
                Run Validation
              </strong>{' '}
              to create the validation run and
              execute the selected checks.
            </p>

            <div className="validation-ready-summary">
              <div>
                <strong>Table:</strong>{' '}
                {selectedTables.length ? selectedTables.join(', ') : 'Not selected'}
              </div>

              <div>
                <strong>Checks:</strong>{' '}
                {selectedChecks.length}
              </div>
            </div>
          </div>
        </>
      )}

      {runError && (
        <div className="validation-error">
          {runError}
        </div>
      )}
    </div>
  );

  // =========================================================
  // RENDER CURRENT STEP
  // =========================================================

  const renderCurrentStep = () => {
    switch (currentStep) {
      case 0:
        return renderConnectionsStep();

      case 1:
        return mode === 'connection'
          ? renderConnectionTableStep()
          : renderDataDefinitionStep();

      case 2:
        return mode === 'connection'
          ? renderPerPairChecksStep()
          : renderValidationChecksStep();

      case 3:
        return renderConfigurationStep();

      case 4:
        return renderResultsStep();

      default:
        return null;
    }
  };

  // =========================================================
  // MAIN UI
  // =========================================================
    return (
  <div className="validation-wizard-page">

    <div className="validation-wizard-header">
      <button
        type="button"
        className="validation-back-link"
        onClick={() => navigate('/validations')}
      >
        ← Back to Validations
      </button>

      <h1>New Data Validation</h1>

      <p>
        Configure and run post-migration data integrity validation.
      </p>

      <button
        type="button"
        className="validation-secondary-btn"
        onClick={loadDemoData}
        style={{ marginTop: 8 }}
      >
        Load demo data
      </button>
    </div>

    {renderStepIndicator()}

    {error && (
      <div className="validation-error">
        {error}
      </div>
    )}

    <div className="validation-wizard-card">

      {renderCurrentStep()}

      <div className="validation-wizard-actions">

        <button
          type="button"
          className="validation-secondary-btn"
          onClick={() =>
            currentStep === 0
              ? navigate('/validations')
              : previousStep()
          }
        >
          {currentStep === 0 ? 'Cancel' : 'Previous'}
        </button>

        {currentStep < STEPS.length - 1 ? (
          <button
            type="button"
            className="validation-primary-btn"
            onClick={nextStep}
          >
            Continue
          </button>
        ) : (
          <button
            type="button"
            className="validation-primary-btn"
            onClick={mode === 'connection' ? runConnectionValidation : runValidation}
            disabled={mode === 'connection' ? directRunning : runSubmitting}
          >
            {mode === 'connection'
              ? (directRunning ? 'Running…' : (directResults.length > 0 ? 'Run Again' : 'Run Validation'))
              : (runSubmitting ? 'Starting Validation...' : 'Run Validation')}
          </button>
        )}

        {/* Clear exit back to the validations dashboard — always available on
            the final step so there's somewhere to go after running. */}
        {currentStep === STEPS.length - 1 && (
          <button
            type="button"
            className="validation-secondary-btn validation-return-btn"
            onClick={() => navigate('/validations')}
          >
            Return to Validations
          </button>
        )}

      </div>
    </div>
  </div>
);

}
export { ValidationWizardPage };