/**
 * CompactionStrategySelector component for per-table compaction strategy selection
 * during structure review.
 *
 * Allows users to select binpack, sort, or z-order compaction strategies
 * and specify sort columns when applicable.
 *
 * Requirements: 3.1, 3.2, 3.3, 3.4, 3.7
 */
import React, { useState, useCallback } from 'react';
import { Select, Alert } from '../ui';
import type { CompactionConfig, CompactionStrategy } from '../../types/bqIceberg';
import './CompactionStrategySelector.css';

/** Strategy descriptions per Requirement 3.7 */
const STRATEGY_DESCRIPTIONS: Record<CompactionStrategy, string> = {
  binpack: 'Combines small files without reordering (best for append-heavy workloads)',
  sort: 'Reorders data by specified columns (best for range queries on specific columns)',
  'z-order': 'Interleaves multiple columns (best for queries filtering on multiple columns simultaneously)',
};

const STRATEGY_OPTIONS = [
  { value: 'binpack', label: 'Binpack' },
  { value: 'sort', label: 'Sort' },
  { value: 'z-order', label: 'Z-Order' },
];

export interface CompactionStrategySelectorProps {
  /** Current compaction configuration */
  config: CompactionConfig;
  /** Callback when configuration changes */
  onChange: (config: CompactionConfig) => void;
  /** Available columns from the table schema for sort column selection */
  availableColumns: string[];
  /** Whether to show validation errors */
  showErrors?: boolean;
}

export const CompactionStrategySelector: React.FC<CompactionStrategySelectorProps> = ({
  config,
  onChange,
  availableColumns,
  showErrors = false,
}) => {
  const [sortColumnInput, setSortColumnInput] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleStrategyChange = useCallback(
    (value: string | number) => {
      const strategy = String(value) as CompactionStrategy;
      const updatedConfig: CompactionConfig = {
        ...config,
        strategy,
        // Clear sort columns when switching to binpack
        sort_columns: strategy === 'binpack' ? [] : config.sort_columns,
      };
      onChange(updatedConfig);
      setValidationError(null);
    },
    [config, onChange]
  );

  const handleAddSortColumn = useCallback(() => {
    const column = sortColumnInput.trim();
    if (!column) return;

    if (!availableColumns.includes(column)) {
      setValidationError(`Column "${column}" does not exist in the table schema.`);
      return;
    }

    if (config.sort_columns.includes(column)) {
      setValidationError(`Column "${column}" is already added.`);
      return;
    }

    onChange({
      ...config,
      sort_columns: [...config.sort_columns, column],
    });
    setSortColumnInput('');
    setValidationError(null);
  }, [sortColumnInput, availableColumns, config, onChange]);

  const handleRemoveSortColumn = useCallback(
    (column: string) => {
      onChange({
        ...config,
        sort_columns: config.sort_columns.filter((c) => c !== column),
      });
    },
    [config, onChange]
  );

  const handleSortColumnInputKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleAddSortColumn();
      }
    },
    [handleAddSortColumn]
  );

  const handleSelectColumn = useCallback(
    (value: string | number) => {
      const column = String(value);
      if (!column) return;

      if (config.sort_columns.includes(column)) {
        setValidationError(`Column "${column}" is already added.`);
        return;
      }

      onChange({
        ...config,
        sort_columns: [...config.sort_columns, column],
      });
      setValidationError(null);
    },
    [config, onChange]
  );

  const showSortColumns = config.strategy === 'sort' || config.strategy === 'z-order';
  const hasRecommendation = !!config.recommended_strategy;
  const sortColumnsError =
    showErrors && showSortColumns && config.sort_columns.length === 0
      ? 'At least one sort column is required for this strategy.'
      : null;

  const columnOptions = [
    { value: '', label: 'Select a column to add...' },
    ...availableColumns
      .filter((col) => !config.sort_columns.includes(col))
      .map((col) => ({ value: col, label: col })),
  ];

  return (
    <div className="compaction-strategy-selector">
      <div className="compaction-strategy-selector__header">
        <label className="compaction-strategy-selector__label">Compaction Strategy</label>
      </div>

      {/* Recommendation alert */}
      {hasRecommendation && (
        <div className="compaction-strategy-selector__recommendation">
          <Alert variant="info">
            Recommended: <strong>{config.recommended_strategy}</strong> compaction
            {config.recommended_sort_columns && config.recommended_sort_columns.length > 0 && (
              <> with columns: <code>{config.recommended_sort_columns.join(', ')}</code></>
            )}
            {' '}(source has clustering columns)
          </Alert>
        </div>
      )}

      {/* Strategy dropdown */}
      <div className="compaction-strategy-selector__select">
        <Select
          value={config.strategy}
          onChange={handleStrategyChange}
          options={STRATEGY_OPTIONS}
        />
      </div>

      {/* Strategy descriptions */}
      <div className="compaction-strategy-selector__descriptions">
        {(Object.entries(STRATEGY_DESCRIPTIONS) as [CompactionStrategy, string][]).map(
          ([strategy, description]) => (
            <div
              key={strategy}
              className={`compaction-strategy-selector__description ${
                config.strategy === strategy ? 'compaction-strategy-selector__description--active' : ''
              }`}
            >
              <span className="compaction-strategy-selector__description-name">
                {strategy === 'z-order' ? 'Z-Order' : strategy.charAt(0).toUpperCase() + strategy.slice(1)}:
              </span>{' '}
              <span className="compaction-strategy-selector__description-text">{description}</span>
            </div>
          )
        )}
      </div>

      {/* Sort columns input (shown for sort and z-order) */}
      {showSortColumns && (
        <div className="compaction-strategy-selector__sort-columns">
          <label className="compaction-strategy-selector__sort-label">
            Sort Columns <span className="required">*</span>
          </label>

          <div className="compaction-strategy-selector__sort-input-row">
            <Select
              value=""
              onChange={handleSelectColumn}
              options={columnOptions}
              className="compaction-strategy-selector__column-select"
            />
            <span className="compaction-strategy-selector__or-text">or</span>
            <div className="compaction-strategy-selector__manual-input">
              <input
                type="text"
                className="compaction-strategy-selector__text-input"
                placeholder="Type column name..."
                value={sortColumnInput}
                onChange={(e) => {
                  setSortColumnInput(e.target.value);
                  setValidationError(null);
                }}
                onKeyDown={handleSortColumnInputKeyDown}
                aria-label="Sort column name"
              />
              <button
                type="button"
                className="compaction-strategy-selector__add-btn"
                onClick={handleAddSortColumn}
                disabled={!sortColumnInput.trim()}
                aria-label="Add sort column"
              >
                Add
              </button>
            </div>
          </div>

          {/* Validation error */}
          {validationError && (
            <p className="compaction-strategy-selector__error" role="alert">
              {validationError}
            </p>
          )}
          {sortColumnsError && (
            <p className="compaction-strategy-selector__error" role="alert">
              {sortColumnsError}
            </p>
          )}

          {/* Selected sort columns */}
          {config.sort_columns.length > 0 && (
            <div className="compaction-strategy-selector__selected-columns">
              {config.sort_columns.map((column, index) => (
                <span key={column} className="compaction-strategy-selector__column-tag">
                  <span className="compaction-strategy-selector__column-order">{index + 1}</span>
                  <span className="compaction-strategy-selector__column-name">{column}</span>
                  <button
                    type="button"
                    className="compaction-strategy-selector__column-remove"
                    onClick={() => handleRemoveSortColumn(column)}
                    aria-label={`Remove column ${column}`}
                  >
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M9 3L3 9M3 3l6 6" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </button>
                </span>
              ))}
            </div>
          )}

          <p className="compaction-strategy-selector__help">
            Columns are used in the order listed. Drag or reorder as needed.
          </p>
        </div>
      )}
    </div>
  );
};
