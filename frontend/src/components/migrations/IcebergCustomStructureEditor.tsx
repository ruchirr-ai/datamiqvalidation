/**
 * Custom Structure Editor for Iceberg tables
 * Allows users to define Iceberg table structure from scratch.
 * Requirements: 4.9
 */
import React, { useState } from 'react';
import { Button, Alert } from '../ui';
import type {
  CustomColumnDef,
  CustomPartitionSpec,
  CustomSortOrder,
  TableProperties,
  CustomStructureDefinition,
  CustomStructureValidation,
} from '../../types/bqIceberg';
import './IcebergCustomStructureEditor.css';

const ICEBERG_TYPE_OPTIONS: string[] = [
  'string', 'binary', 'boolean', 'int', 'long', 'float', 'double',
  'decimal', 'date', 'time', 'timestamp', 'timestamptz', 'uuid',
  'fixed', 'struct', 'list', 'map',
];

const TRANSFORM_OPTIONS: string[] = [
  'identity', 'day', 'hour', 'month', 'year', 'bucket', 'truncate',
];

interface IcebergCustomStructureEditorProps {
  tableName: string;
  existingColumns?: { name: string; iceberg_type: string; nullable: boolean }[];
  onSave: (definition: CustomStructureDefinition) => void;
  onCancel: () => void;
  onValidate?: (definition: CustomStructureDefinition) => Promise<CustomStructureValidation>;
}

export const IcebergCustomStructureEditor: React.FC<IcebergCustomStructureEditorProps> = ({
  tableName,
  existingColumns,
  onSave,
  onCancel,
  onValidate,
}) => {
  const [columns, setColumns] = useState<CustomColumnDef[]>(
    existingColumns?.map((c) => ({ name: c.name, iceberg_type: c.iceberg_type, nullable: c.nullable })) || [
      { name: '', iceberg_type: 'string', nullable: true },
    ]
  );
  const [partitionSpec, setPartitionSpec] = useState<CustomPartitionSpec[]>([]);
  const [sortOrder, setSortOrder] = useState<CustomSortOrder[]>([]);
  const [properties, setProperties] = useState<TableProperties>({});
  const [newPropKey, setNewPropKey] = useState('');
  const [newPropValue, setNewPropValue] = useState('');
  const [validation, setValidation] = useState<CustomStructureValidation | null>(null);
  const [validating, setValidating] = useState(false);

  const addColumn = () => {
    setColumns([...columns, { name: '', iceberg_type: 'string', nullable: true }]);
  };

  const removeColumn = (index: number) => {
    setColumns(columns.filter((_, i) => i !== index));
  };

  const updateColumn = (index: number, field: keyof CustomColumnDef, value: any) => {
    const updated = [...columns];
    updated[index] = { ...updated[index], [field]: value };
    setColumns(updated);
  };

  const addPartition = () => {
    const firstCol = columns[0]?.name || '';
    setPartitionSpec([...partitionSpec, { column: firstCol, transform: 'identity' }]);
  };

  const removePartition = (index: number) => {
    setPartitionSpec(partitionSpec.filter((_, i) => i !== index));
  };

  const updatePartition = (index: number, field: keyof CustomPartitionSpec, value: string) => {
    const updated = [...partitionSpec];
    updated[index] = { ...updated[index], [field]: value };
    setPartitionSpec(updated);
  };

  const addSortColumn = () => {
    const firstCol = columns[0]?.name || '';
    setSortOrder([...sortOrder, { column: firstCol, direction: 'asc' }]);
  };

  const removeSortColumn = (index: number) => {
    setSortOrder(sortOrder.filter((_, i) => i !== index));
  };

  const updateSortColumn = (index: number, field: keyof CustomSortOrder, value: string) => {
    const updated = [...sortOrder];
    updated[index] = { ...updated[index], [field]: value as any };
    setSortOrder(updated);
  };

  const addProperty = () => {
    if (newPropKey.trim()) {
      setProperties({ ...properties, [newPropKey.trim()]: newPropValue });
      setNewPropKey('');
      setNewPropValue('');
    }
  };

  const removeProperty = (key: string) => {
    const updated = { ...properties };
    delete updated[key];
    setProperties(updated);
  };

  const buildDefinition = (): CustomStructureDefinition => ({
    table_name: tableName,
    columns,
    partition_spec: partitionSpec,
    sort_order: sortOrder,
    properties,
  });

  const handleValidate = async () => {
    if (!onValidate) return;
    setValidating(true);
    try {
      const result = await onValidate(buildDefinition());
      setValidation(result);
    } catch (err: any) {
      setValidation({ valid: false, warnings: [], errors: [err.message] });
    } finally {
      setValidating(false);
    }
  };

  const handleSave = () => {
    onSave(buildDefinition());
  };

  const hasEmptyColumnNames = columns.some((c) => !c.name.trim());

  return (
    <div className="custom-structure-editor">
      <div className="custom-structure-editor__header">
        <h3 className="custom-structure-editor__title">
          Define Custom Structure: <code>{tableName}</code>
        </h3>
        <p className="custom-structure-editor__desc">
          Define the Iceberg table structure from scratch. Column names and types must be compatible with the source data.
        </p>
      </div>

      {/* Validation Results */}
      {validation && (
        <div className="custom-structure-editor__validation">
          {validation.errors.length > 0 && (
            <Alert variant="error" title="Validation Errors">
              <ul>
                {validation.errors.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            </Alert>
          )}
          {validation.warnings.length > 0 && (
            <Alert variant="warning" title="Validation Warnings">
              <ul>
                {validation.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </Alert>
          )}
          {validation.valid && validation.errors.length === 0 && (
            <Alert variant="success">Structure is valid and compatible with source data.</Alert>
          )}
        </div>
      )}

      {/* Column Definitions */}
      <div className="custom-structure-editor__section">
        <h4 className="custom-structure-editor__section-title">Column Definitions</h4>
        <div className="custom-structure-editor__columns">
          <div className="custom-structure-editor__col-header">
            <span>Name</span>
            <span>Iceberg Type</span>
            <span>Nullable</span>
            <span></span>
          </div>
          {columns.map((col, i) => (
            <div key={i} className="custom-structure-editor__col-row">
              <input
                type="text"
                value={col.name}
                onChange={(e) => updateColumn(i, 'name', e.target.value)}
                placeholder="column_name"
                aria-label={`Column ${i + 1} name`}
                className="custom-structure-editor__input"
              />
              <select
                value={col.iceberg_type}
                onChange={(e) => updateColumn(i, 'iceberg_type', e.target.value)}
                aria-label={`Column ${i + 1} type`}
                className="custom-structure-editor__select"
              >
                {ICEBERG_TYPE_OPTIONS.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
              <label className="custom-structure-editor__checkbox-label">
                <input
                  type="checkbox"
                  checked={col.nullable}
                  onChange={(e) => updateColumn(i, 'nullable', e.target.checked)}
                  aria-label={`Column ${i + 1} nullable`}
                />
                <span>Nullable</span>
              </label>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => removeColumn(i)}
                disabled={columns.length <= 1}
                aria-label={`Remove column ${i + 1}`}
              >
                Remove
              </Button>
            </div>
          ))}
          <Button variant="outline" size="sm" onClick={addColumn}>
            Add Column
          </Button>
        </div>
      </div>

      {/* Partition Spec */}
      <div className="custom-structure-editor__section">
        <h4 className="custom-structure-editor__section-title">Partition Spec</h4>
        <div className="custom-structure-editor__partitions">
          {partitionSpec.map((p, i) => (
            <div key={i} className="custom-structure-editor__edit-row">
              <select
                value={p.column}
                onChange={(e) => updatePartition(i, 'column', e.target.value)}
                aria-label={`Partition ${i + 1} column`}
                className="custom-structure-editor__select"
              >
                {columns.filter((c) => c.name.trim()).map((c) => (
                  <option key={c.name} value={c.name}>{c.name}</option>
                ))}
              </select>
              <select
                value={p.transform}
                onChange={(e) => updatePartition(i, 'transform', e.target.value)}
                aria-label={`Partition ${i + 1} transform`}
                className="custom-structure-editor__select"
              >
                {TRANSFORM_OPTIONS.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => removePartition(i)}
                aria-label={`Remove partition ${i + 1}`}
              >
                Remove
              </Button>
            </div>
          ))}
          <Button variant="outline" size="sm" onClick={addPartition}>
            Add Partition
          </Button>
        </div>
      </div>

      {/* Sort Order */}
      <div className="custom-structure-editor__section">
        <h4 className="custom-structure-editor__section-title">Sort Order</h4>
        <div className="custom-structure-editor__sort">
          {sortOrder.map((s, i) => (
            <div key={i} className="custom-structure-editor__edit-row">
              <select
                value={s.column}
                onChange={(e) => updateSortColumn(i, 'column', e.target.value)}
                aria-label={`Sort ${i + 1} column`}
                className="custom-structure-editor__select"
              >
                {columns.filter((c) => c.name.trim()).map((c) => (
                  <option key={c.name} value={c.name}>{c.name}</option>
                ))}
              </select>
              <select
                value={s.direction}
                onChange={(e) => updateSortColumn(i, 'direction', e.target.value)}
                aria-label={`Sort ${i + 1} direction`}
                className="custom-structure-editor__select"
              >
                <option value="asc">Ascending</option>
                <option value="desc">Descending</option>
              </select>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => removeSortColumn(i)}
                aria-label={`Remove sort ${i + 1}`}
              >
                Remove
              </Button>
            </div>
          ))}
          <Button variant="outline" size="sm" onClick={addSortColumn}>
            Add Sort Column
          </Button>
        </div>
      </div>

      {/* Table Properties */}
      <div className="custom-structure-editor__section">
        <h4 className="custom-structure-editor__section-title">Table Properties</h4>
        <div className="custom-structure-editor__properties">
          {Object.entries(properties).map(([key, value]) => (
            <div key={key} className="custom-structure-editor__prop-row">
              <span className="custom-structure-editor__prop-key">{key}</span>
              <span className="custom-structure-editor__prop-value">{value}</span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => removeProperty(key)}
                aria-label={`Remove property ${key}`}
              >
                Remove
              </Button>
            </div>
          ))}
          <div className="custom-structure-editor__add-prop">
            <input
              type="text"
              value={newPropKey}
              onChange={(e) => setNewPropKey(e.target.value)}
              placeholder="Key"
              aria-label="New property key"
              className="custom-structure-editor__input"
            />
            <input
              type="text"
              value={newPropValue}
              onChange={(e) => setNewPropValue(e.target.value)}
              placeholder="Value"
              aria-label="New property value"
              className="custom-structure-editor__input"
            />
            <Button variant="outline" size="sm" onClick={addProperty}>
              Add
            </Button>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="custom-structure-editor__footer">
        <Button variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        {onValidate && (
          <Button variant="secondary" onClick={handleValidate} loading={validating}>
            Validate
          </Button>
        )}
        <Button
          variant="primary"
          onClick={handleSave}
          disabled={hasEmptyColumnNames}
        >
          Save Custom Structure
        </Button>
      </div>
    </div>
  );
};
