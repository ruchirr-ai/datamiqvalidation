/**
 * Quick Validation Test
 *
 * A lightweight panel that runs validation checks directly between two
 * connected databases (no migration required). Intended for verifying the
 * validation module works across engines (e.g. SQL Server -> Redshift).
 *
 * Minimal inputs: pick source + target connection, pick a table from each
 * (discovered automatically), tick the checks, run. Schema comes with the
 * discovered table so there is nothing to type.
 */

import React, { useEffect, useState } from 'react';
import { listConnections, Connection } from '../services/api';
import {
  runDirectValidationTest,
  getConnectionTables,
  getConnectionColumns,
  DirectValidationResponse,
  DiscoveredTable,
  DiscoveredColumn,
} from '../services/validationApi';
import './QuickValidationTest.css';

// Engines supported by the direct test path (matches backend validation_engines.py)
const SUPPORTED_TYPES = ['sqlserver', 'mssql', 'redshift', 'postgresql', 'postgres'];

function isSupportedConnection(c: Connection): boolean {
  const t = (c.type || '').toLowerCase();
  const d = (c.database || '').toLowerCase();
  return SUPPORTED_TYPES.includes(t) || SUPPORTED_TYPES.includes(d);
}

function engineLabel(c: Connection): string {
  return (c.type || c.database || 'unknown').toLowerCase();
}

function tableKey(t: DiscoveredTable): string {
  return `${t.schema}.${t.table}`;
}

function StatusBadge({ status }: { status?: string }) {
  const s = status || 'pending';
  const label =
    s === 'passed' ? 'Passed'
      : s === 'failed' ? 'Failed'
        : s === 'error' ? 'Error'
          : s === 'no_checks' ? 'No checks'
            : 'Pending';
  return <span className={`vd-status-badge ${s}`}>{label}</span>;
}

/** Column picker dropdown, populated from discovered source columns. */
function ColumnSelect({
  value,
  onChange,
  disabled,
  columns,
  loading,
  placeholder = 'column…',
}: {
  value: string;
  onChange: (v: string) => void;
  disabled: boolean;
  columns: DiscoveredColumn[];
  loading: boolean;
  placeholder?: string;
}) {
  return (
    <select
      className="validation-form-input quick-test-col"
      disabled={disabled || loading}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="">{loading ? 'Loading columns…' : placeholder}</option>
      {columns.map((c) => (
        <option key={c.column_name} value={c.column_name}>
          {c.column_name} ({c.data_type})
        </option>
      ))}
    </select>
  );
}

export const QuickValidationTest: React.FC = () => {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [sourceId, setSourceId] = useState<number>(0);
  const [targetId, setTargetId] = useState<number>(0);

  // Discovered tables per side
  const [sourceTables, setSourceTables] = useState<DiscoveredTable[]>([]);
  const [targetTables, setTargetTables] = useState<DiscoveredTable[]>([]);
  const [sourceTablesLoading, setSourceTablesLoading] = useState(false);
  const [targetTablesLoading, setTargetTablesLoading] = useState(false);
  const [discoveryError, setDiscoveryError] = useState<string | null>(null);

  // Selected table (schema.table) per side
  const [sourceSel, setSourceSel] = useState<string>('');
  const [targetSel, setTargetSel] = useState<string>('');

  // Discovered columns for the selected source table (used by check pickers)
  const [columns, setColumns] = useState<DiscoveredColumn[]>([]);
  const [columnsLoading, setColumnsLoading] = useState(false);

  // Checks
  const [rowCount, setRowCount] = useState(true);
  const [nullCheck, setNullCheck] = useState(false);
  const [nullColumn, setNullColumn] = useState('');
  const [duplicateCheck, setDuplicateCheck] = useState(false);
  const [duplicateKey, setDuplicateKey] = useState('');
  const [sumCheck, setSumCheck] = useState(false);
  const [sumColumn, setSumColumn] = useState('');
  const [averageCheck, setAverageCheck] = useState(false);
  const [averageColumn, setAverageColumn] = useState('');

  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DirectValidationResponse | null>(null);

  // Load connections
  useEffect(() => {
    listConnections()
      .then((conns) => {
        const all = conns || [];
        const supported = all.filter(isSupportedConnection);
        setConnections(supported.length > 0 ? supported : all);
      })
      .catch(() => setConnections([]));
  }, []);

  // Discover tables when source connection changes
  useEffect(() => {
    setSourceTables([]);
    setSourceSel('');
    if (!sourceId) return;
    setSourceTablesLoading(true);
    setDiscoveryError(null);
    getConnectionTables(sourceId)
      .then((res) => setSourceTables(res.tables || []))
      .catch((e) => setDiscoveryError(e?.detail || e?.message || 'Failed to load source tables'))
      .finally(() => setSourceTablesLoading(false));
  }, [sourceId]);

  // Discover tables when target connection changes
  useEffect(() => {
    setTargetTables([]);
    setTargetSel('');
    if (!targetId) return;
    setTargetTablesLoading(true);
    setDiscoveryError(null);
    getConnectionTables(targetId)
      .then((res) => setTargetTables(res.tables || []))
      .catch((e) => setDiscoveryError(e?.detail || e?.message || 'Failed to load target tables'))
      .finally(() => setTargetTablesLoading(false));
  }, [targetId]);

  const sourceTable = sourceTables.find((t) => tableKey(t) === sourceSel);
  const targetTable = targetTables.find((t) => tableKey(t) === targetSel);

  // Discover columns from the source table for the check pickers
  useEffect(() => {
    setColumns([]);
    setNullColumn('');
    setDuplicateKey('');
    setSumColumn('');
    setAverageColumn('');
    if (!sourceId || !sourceTable) return;
    setColumnsLoading(true);
    getConnectionColumns(sourceId, sourceTable.schema, sourceTable.table)
      .then((res) => setColumns(res.columns || []))
      .catch(() => setColumns([]))
      .finally(() => setColumnsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceId, sourceSel]);

  const canRun =
    sourceId > 0 &&
    targetId > 0 &&
    !!sourceTable &&
    !!targetTable &&
    (rowCount || nullCheck || duplicateCheck || sumCheck || averageCheck);

  const handleRun = async () => {
    if (!canRun || running || !sourceTable || !targetTable) return;
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const res = await runDirectValidationTest({
        source_connection_id: sourceId,
        target_connection_id: targetId,
        source_schema: sourceTable.schema,
        target_schema: targetTable.schema,
        table_name: sourceTable.table,
        row_count: rowCount,
        null_check: nullCheck,
        null_column: nullColumn.trim() || undefined,
        duplicate_check: duplicateCheck,
        duplicate_match_key: duplicateKey.trim() || undefined,
        sum_check: sumCheck,
        sum_column: sumColumn.trim() || undefined,
        average_check: averageCheck,
        average_column: averageColumn.trim() || undefined,
      });
      setResult(res);
    } catch (err: unknown) {
      let msg = 'Direct validation test failed';
      if (err && typeof err === 'object') {
        if ('detail' in err) {
          const d = (err as { detail: unknown }).detail;
          msg = typeof d === 'string' ? d : JSON.stringify(d);
        } else if ('message' in err) {
          msg = String((err as { message: unknown }).message);
        }
      }
      setError(msg);
    } finally {
      setRunning(false);
    }
  };

  const checkRows = result ? Object.entries(result.checks) : [];

  return (
    <div className="quick-test-panel">
      <div className="quick-test-header">
        <h3 className="quick-test-title">Quick Validation Test</h3>
        <p className="quick-test-subtitle">
          Run checks directly between two connected databases — no migration required.
        </p>
      </div>

      <div className="quick-test-section-label">Source &amp; target</div>
      <div className="quick-test-form-grid">
        {/* Source */}
        <div className="quick-test-field">
          <label className="validation-form-label">Source connection</label>
          <select
            className="validation-form-input"
            value={sourceId}
            onChange={(e) => setSourceId(Number(e.target.value))}
          >
            <option value={0}>Select source…</option>
            {connections.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({engineLabel(c)})
              </option>
            ))}
          </select>
        </div>

        <div className="quick-test-field">
          <label className="validation-form-label">Source table</label>
          <select
            className="validation-form-input"
            value={sourceSel}
            onChange={(e) => setSourceSel(e.target.value)}
            disabled={!sourceId || sourceTablesLoading}
          >
            <option value="">
              {sourceTablesLoading ? 'Loading tables…' : sourceId ? 'Select table…' : 'Pick a connection first'}
            </option>
            {sourceTables.map((t) => (
              <option key={tableKey(t)} value={tableKey(t)}>
                {t.schema}.{t.table}
              </option>
            ))}
          </select>
        </div>

        {/* Target */}
        <div className="quick-test-field">
          <label className="validation-form-label">Target connection</label>
          <select
            className="validation-form-input"
            value={targetId}
            onChange={(e) => setTargetId(Number(e.target.value))}
          >
            <option value={0}>Select target…</option>
            {connections.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({engineLabel(c)})
              </option>
            ))}
          </select>
        </div>

        <div className="quick-test-field">
          <label className="validation-form-label">Target table</label>
          <select
            className="validation-form-input"
            value={targetSel}
            onChange={(e) => setTargetSel(e.target.value)}
            disabled={!targetId || targetTablesLoading}
          >
            <option value="">
              {targetTablesLoading ? 'Loading tables…' : targetId ? 'Select table…' : 'Pick a connection first'}
            </option>
            {targetTables.map((t) => (
              <option key={tableKey(t)} value={tableKey(t)}>
                {t.schema}.{t.table}
              </option>
            ))}
          </select>
        </div>
      </div>

      {discoveryError && <p className="validation-error-text quick-test-error">{discoveryError}</p>}

      {/* Checks */}
      <div className="quick-test-section-label">Checks to run</div>
      <div className="quick-test-checks">
        <div className="quick-test-check-row">
          <label className="quick-test-check">
            <input type="checkbox" checked={rowCount} onChange={() => setRowCount((v) => !v)} />
            <span>Row Count</span>
          </label>
        </div>

        <div className="quick-test-check-row">
          <label className="quick-test-check">
            <input type="checkbox" checked={nullCheck} onChange={() => setNullCheck((v) => !v)} />
            <span>NULL</span>
          </label>
          <ColumnSelect
            value={nullColumn}
            onChange={setNullColumn}
            disabled={!nullCheck}
            columns={columns}
            loading={columnsLoading}
          />
        </div>

        <div className="quick-test-check-row">
          <label className="quick-test-check">
            <input type="checkbox" checked={duplicateCheck} onChange={() => setDuplicateCheck((v) => !v)} />
            <span>Duplicate</span>
          </label>
          <ColumnSelect
            value={duplicateKey}
            onChange={setDuplicateKey}
            disabled={!duplicateCheck}
            columns={columns}
            loading={columnsLoading}
            placeholder="match key…"
          />
        </div>

        <div className="quick-test-check-row">
          <label className="quick-test-check">
            <input type="checkbox" checked={sumCheck} onChange={() => setSumCheck((v) => !v)} />
            <span>SUM</span>
          </label>
          <ColumnSelect
            value={sumColumn}
            onChange={setSumColumn}
            disabled={!sumCheck}
            columns={columns}
            loading={columnsLoading}
          />
        </div>

        <div className="quick-test-check-row">
          <label className="quick-test-check">
            <input type="checkbox" checked={averageCheck} onChange={() => setAverageCheck((v) => !v)} />
            <span>AVERAGE</span>
          </label>
          <ColumnSelect
            value={averageColumn}
            onChange={setAverageColumn}
            disabled={!averageCheck}
            columns={columns}
            loading={columnsLoading}
          />
        </div>
      </div>

      {error && <p className="validation-error-text quick-test-error">{error}</p>}

      <div className="quick-test-actions">
        <button
          type="button"
          className="validation-form-submit"
          disabled={!canRun || running}
          onClick={handleRun}
        >
          {running ? 'Running…' : 'Run Test'}
        </button>
      </div>

      {/* Results */}
      {result && (
        <div className="quick-test-results">
          <div className="quick-test-results-header">
            <span>
              {result.source_connection} ({result.source_engine}) →{' '}
              {result.target_connection} ({result.target_engine}) · {result.table_name}
            </span>
            <StatusBadge status={result.overall_status} />
          </div>
          <table className="quick-test-results-table">
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
              {checkRows.map(([name, r]) => (
                <tr key={name}>
                  <td>{name}</td>
                  <td>{r.error_message ? '—' : String(r.source_value ?? '—')}</td>
                  <td>{r.error_message ? '—' : String(r.target_value ?? '—')}</td>
                  <td>{r.error_message ? '—' : String(r.difference ?? '—')}</td>
                  <td>
                    <StatusBadge status={r.status} />
                    {r.error_message && (
                      <span className="quick-test-err-msg" title={r.error_message}>
                        {r.error_message}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default QuickValidationTest;
