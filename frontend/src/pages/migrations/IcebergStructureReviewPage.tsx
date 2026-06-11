/**
 * Iceberg Structure Review Page
 * Displays the Iceberg Structure Design Report for user review and approval.
 * Accessible from the migration detail view when status is pending_review.
 * Requirements: 4.5, 4.6, 4.7, 4.8
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, Card, Alert, Input } from '../../components/ui';
import { bqIcebergApi } from '../../services/bqIcebergApi';
import type {
  StructureReport,
  TableStructure,
  PartitionSpec,
  SortOrderColumn,
  TableProperties,
  StructureOverrides,
  Warning,
  PrerequisiteItem,
} from '../../types/bqIceberg';
import './IcebergStructureReviewPage.css';

// --- Collapsible Table Section ---
interface TableSectionProps {
  table: TableStructure;
  overrides: StructureOverrides;
  onPartitionChange: (tableName: string, specs: PartitionSpec[]) => void;
  onSortOrderChange: (tableName: string, order: SortOrderColumn[]) => void;
  onExcludeToggle: (tableName: string) => void;
  onPropertiesChange: (tableName: string, props: TableProperties) => void;
  isExcluded: boolean;
}

const TableSection: React.FC<TableSectionProps> = ({
  table,
  overrides,
  onPartitionChange,
  onSortOrderChange,
  onExcludeToggle,
  onPropertiesChange,
  isExcluded,
}) => {
  const [expanded, setExpanded] = useState(false);
  const [editingPartition, setEditingPartition] = useState(false);
  const [editingSortOrder, setEditingSortOrder] = useState(false);
  const [editingProperties, setEditingProperties] = useState(false);
  const [localPartition, setLocalPartition] = useState<PartitionSpec[]>(table.partition_spec);
  const [localSortOrder, setLocalSortOrder] = useState<SortOrderColumn[]>(table.sort_order);
  const [localProperties, setLocalProperties] = useState<TableProperties>(table.properties);
  const [newPropKey, setNewPropKey] = useState('');
  const [newPropValue, setNewPropValue] = useState('');

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
  };

  return (
    <div className={`table-section ${isExcluded ? 'table-section--excluded' : ''}`}>
      <button
        className="table-section__header"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        aria-label={`Toggle ${table.iceberg_table_name} details`}
      >
        <div className="table-section__header-left">
          <svg
            className={`table-section__chevron ${expanded ? 'expanded' : ''}`}
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M6 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="table-section__name">{table.iceberg_table_name}</span>
          {table.is_custom && (
            <span className="table-section__badge table-section__badge--custom">Custom</span>
          )}
          {isExcluded && (
            <span className="table-section__badge table-section__badge--excluded">Excluded</span>
          )}
        </div>
        <div className="table-section__header-right">
          <span className="table-section__meta">
            {table.columns.length} cols
          </span>
          <span className="table-section__meta">
            {table.estimated_row_count.toLocaleString()} rows
          </span>
          <span className="table-section__meta">
            {formatBytes(table.estimated_data_size_bytes)}
          </span>
        </div>
      </button>

      {expanded && (
        <div className="table-section__body">
          {/* Exclude toggle */}
          <div className="table-section__actions">
            <label className="table-section__exclude-toggle">
              <input
                type="checkbox"
                checked={isExcluded}
                onChange={() => onExcludeToggle(table.iceberg_table_name)}
              />
              <span>Exclude from migration</span>
            </label>
          </div>

          {/* Columns */}
          <div className="table-section__subsection">
            <h4 className="table-section__subtitle">Columns</h4>
            <div className="table-section__columns-table">
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Source (BQ)</th>
                    <th>Iceberg Type</th>
                    <th>Nullable</th>
                    <th>Warnings</th>
                  </tr>
                </thead>
                <tbody>
                  {table.columns.map((col) => (
                    <tr key={col.name}>
                      <td className="col-name">{col.name}</td>
                      <td className="col-type">{col.source_bq_type}</td>
                      <td className="col-type">{col.iceberg_type}</td>
                      <td>{col.nullable ? 'Yes' : 'No'}</td>
                      <td>
                        {col.warnings.length > 0 && (
                          <span className="col-warning">{col.warnings.join(', ')}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Partition Spec */}
          <div className="table-section__subsection">
            <div className="table-section__subtitle-row">
              <h4 className="table-section__subtitle">Partition Spec</h4>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setEditingPartition(!editingPartition)}
              >
                {editingPartition ? 'Done' : 'Override'}
              </Button>
            </div>
            {!editingPartition ? (
              <div className="table-section__partition-list">
                {table.partition_spec.length === 0 ? (
                  <span className="table-section__empty">No partitioning</span>
                ) : (
                  table.partition_spec.map((p, i) => (
                    <span key={i} className="table-section__partition-item">
                      {p.transform}({p.column})
                      {p.rationale && (
                        <span className="table-section__rationale"> — {p.rationale}</span>
                      )}
                    </span>
                  ))
                )}
              </div>
            ) : (
              <div className="table-section__edit-partition">
                {localPartition.map((p, i) => (
                  <div key={i} className="table-section__edit-row">
                    <select
                      value={p.column}
                      onChange={(e) => {
                        const updated = [...localPartition];
                        updated[i] = { ...updated[i], column: e.target.value };
                        setLocalPartition(updated);
                      }}
                      aria-label={`Partition column ${i + 1}`}
                    >
                      {table.columns.map((col) => (
                        <option key={col.name} value={col.name}>
                          {col.name}
                        </option>
                      ))}
                    </select>
                    <select
                      value={p.transform}
                      onChange={(e) => {
                        const updated = [...localPartition];
                        updated[i] = { ...updated[i], transform: e.target.value as PartitionSpec['transform'] };
                        setLocalPartition(updated);
                      }}
                      aria-label={`Partition transform ${i + 1}`}
                    >
                      {['identity', 'day', 'hour', 'month', 'year', 'bucket', 'truncate'].map((t) => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setLocalPartition(localPartition.filter((_, idx) => idx !== i));
                      }}
                      aria-label={`Remove partition ${i + 1}`}
                    >
                      Remove
                    </Button>
                  </div>
                ))}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setLocalPartition([
                      ...localPartition,
                      { column: table.columns[0]?.name || '', transform: 'day' },
                    ]);
                  }}
                >
                  Add Partition
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => {
                    onPartitionChange(table.iceberg_table_name, localPartition);
                    setEditingPartition(false);
                  }}
                >
                  Apply
                </Button>
              </div>
            )}
          </div>

          {/* Sort Order */}
          <div className="table-section__subsection">
            <div className="table-section__subtitle-row">
              <h4 className="table-section__subtitle">Sort Order</h4>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setEditingSortOrder(!editingSortOrder)}
              >
                {editingSortOrder ? 'Done' : 'Override'}
              </Button>
            </div>
            {!editingSortOrder ? (
              <div className="table-section__sort-list">
                {table.sort_order.length === 0 ? (
                  <span className="table-section__empty">No sort order</span>
                ) : (
                  table.sort_order.map((s, i) => (
                    <span key={i} className="table-section__sort-item">
                      {s.column} ({s.direction})
                    </span>
                  ))
                )}
              </div>
            ) : (
              <div className="table-section__edit-sort">
                {localSortOrder.map((s, i) => (
                  <div key={i} className="table-section__edit-row">
                    <select
                      value={s.column}
                      onChange={(e) => {
                        const updated = [...localSortOrder];
                        updated[i] = { ...updated[i], column: e.target.value };
                        setLocalSortOrder(updated);
                      }}
                      aria-label={`Sort column ${i + 1}`}
                    >
                      {table.columns.map((col) => (
                        <option key={col.name} value={col.name}>
                          {col.name}
                        </option>
                      ))}
                    </select>
                    <select
                      value={s.direction}
                      onChange={(e) => {
                        const updated = [...localSortOrder];
                        updated[i] = { ...updated[i], direction: e.target.value as 'asc' | 'desc' };
                        setLocalSortOrder(updated);
                      }}
                      aria-label={`Sort direction ${i + 1}`}
                    >
                      <option value="asc">Ascending</option>
                      <option value="desc">Descending</option>
                    </select>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setLocalSortOrder(localSortOrder.filter((_, idx) => idx !== i));
                      }}
                      aria-label={`Remove sort ${i + 1}`}
                    >
                      Remove
                    </Button>
                  </div>
                ))}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setLocalSortOrder([
                      ...localSortOrder,
                      { column: table.columns[0]?.name || '', direction: 'asc' },
                    ]);
                  }}
                >
                  Add Sort Column
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => {
                    onSortOrderChange(table.iceberg_table_name, localSortOrder);
                    setEditingSortOrder(false);
                  }}
                >
                  Apply
                </Button>
              </div>
            )}
          </div>

          {/* Table Properties */}
          <div className="table-section__subsection">
            <div className="table-section__subtitle-row">
              <h4 className="table-section__subtitle">Table Properties</h4>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setEditingProperties(!editingProperties)}
              >
                {editingProperties ? 'Done' : 'Edit'}
              </Button>
            </div>
            <div className="table-section__properties">
              {Object.entries(localProperties).map(([key, value]) => (
                <div key={key} className="table-section__property-row">
                  <span className="table-section__property-key">{key}</span>
                  <span className="table-section__property-value">{value}</span>
                  {editingProperties && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        const updated = { ...localProperties };
                        delete updated[key];
                        setLocalProperties(updated);
                      }}
                      aria-label={`Remove property ${key}`}
                    >
                      Remove
                    </Button>
                  )}
                </div>
              ))}
              {editingProperties && (
                <div className="table-section__add-property">
                  <input
                    type="text"
                    placeholder="Key"
                    value={newPropKey}
                    onChange={(e) => setNewPropKey(e.target.value)}
                    aria-label="New property key"
                  />
                  <input
                    type="text"
                    placeholder="Value"
                    value={newPropValue}
                    onChange={(e) => setNewPropValue(e.target.value)}
                    aria-label="New property value"
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      if (newPropKey.trim()) {
                        const updated = { ...localProperties, [newPropKey.trim()]: newPropValue };
                        setLocalProperties(updated);
                        onPropertiesChange(table.iceberg_table_name, updated);
                        setNewPropKey('');
                        setNewPropValue('');
                      }
                    }}
                  >
                    Add
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// --- Prerequisites Checklist ---
interface PrerequisitesChecklistProps {
  prerequisites: PrerequisiteItem[];
}

const PrerequisitesChecklist: React.FC<PrerequisitesChecklistProps> = ({ prerequisites }) => {
  const [checked, setChecked] = useState<Record<string, boolean>>({});

  return (
    <div className="prerequisites-checklist">
      <h3 className="prerequisites-checklist__title">Prerequisites Checklist</h3>
      <p className="prerequisites-checklist__description">
        Ensure the following are configured on your target AWS account before proceeding.
      </p>
      <div className="prerequisites-checklist__items">
        {prerequisites.map((item) => (
          <label key={item.id} className="prerequisites-checklist__item">
            <input
              type="checkbox"
              checked={checked[item.id] || false}
              onChange={() =>
                setChecked((prev) => ({ ...prev, [item.id]: !prev[item.id] }))
              }
              aria-label={item.label}
            />
            <div className="prerequisites-checklist__item-content">
              <span className="prerequisites-checklist__item-label">{item.label}</span>
              <span className="prerequisites-checklist__item-desc">{item.description}</span>
              <span className={`prerequisites-checklist__category prerequisites-checklist__category--${item.category}`}>
                {item.category}
              </span>
            </div>
          </label>
        ))}
      </div>
    </div>
  );
};

// --- Warnings Section ---
interface WarningsSectionProps {
  warnings: Warning[];
}

const WarningsSection: React.FC<WarningsSectionProps> = ({ warnings }) => {
  if (warnings.length === 0) return null;

  return (
    <div className="warnings-section">
      <h3 className="warnings-section__title">Warnings and Recommendations</h3>
      <div className="warnings-section__list">
        {warnings.map((w, i) => (
          <div key={i} className={`warnings-section__item warnings-section__item--${w.severity}`}>
            <div className="warnings-section__item-header">
              <span className={`warnings-section__severity warnings-section__severity--${w.severity}`}>
                {w.severity}
              </span>
              {w.table_name && (
                <span className="warnings-section__table">{w.table_name}</span>
              )}
            </div>
            <p className="warnings-section__message">{w.message}</p>
            {w.recommendation && (
              <p className="warnings-section__recommendation">{w.recommendation}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

// --- Main Page Component ---
export const IcebergStructureReviewPage: React.FC = () => {
  const { migrationId } = useParams<{ migrationId: string }>();
  const navigate = useNavigate();
  const [report, setReport] = useState<StructureReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [approving, setApproving] = useState(false);
  const [overrides, setOverrides] = useState<StructureOverrides>({});
  const [datasetMapping, setDatasetMapping] = useState<Record<string, string>>({});
  const [namespace, setNamespace] = useState('');
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const id = Number(migrationId);

  const fetchReport = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await bqIcebergApi.getStructureReport(id);
      setReport(data);
      setDatasetMapping(data.dataset_to_db_mapping || {});
      setNamespace(data.s3_tables_namespace || '');
    } catch (err: any) {
      setError(err.message || 'Failed to load structure report');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (id) fetchReport();
  }, [id, fetchReport]);

  const handlePartitionChange = (tableName: string, specs: PartitionSpec[]) => {
    setOverrides((prev) => ({
      ...prev,
      partition_overrides: { ...prev.partition_overrides, [tableName]: specs },
    }));
  };

  const handleSortOrderChange = (tableName: string, order: SortOrderColumn[]) => {
    setOverrides((prev) => ({
      ...prev,
      sort_order_overrides: { ...prev.sort_order_overrides, [tableName]: order },
    }));
  };

  const handleExcludeToggle = (tableName: string) => {
    setOverrides((prev) => {
      const excluded = prev.excluded_tables || [];
      const isExcluded = excluded.includes(tableName);
      return {
        ...prev,
        excluded_tables: isExcluded
          ? excluded.filter((t) => t !== tableName)
          : [...excluded, tableName],
      };
    });
  };

  const handlePropertiesChange = (tableName: string, props: TableProperties) => {
    setOverrides((prev) => ({
      ...prev,
      custom_properties: { ...prev.custom_properties, [tableName]: props },
    }));
  };

  const handleApprove = async () => {
    try {
      setApproving(true);
      setError(null);
      await bqIcebergApi.approveStructure(id, {
        overrides,
        dataset_to_db_mapping: datasetMapping,
        s3_tables_namespace: namespace || undefined,
      });
      setSuccessMessage('Structure approved. Migration will proceed to load stage.');
      setTimeout(() => navigate(`/migrations/bq-iceberg/${id}`), 2000);
    } catch (err: any) {
      setError(err.message || 'Failed to approve structure');
    } finally {
      setApproving(false);
    }
  };

  const handleRequestChanges = async () => {
    try {
      setError(null);
      await bqIcebergApi.requestChanges(id, {
        overrides,
        dataset_to_db_mapping: datasetMapping,
        s3_tables_namespace: namespace || undefined,
      });
      setSuccessMessage('Changes submitted. Report will be regenerated.');
      fetchReport();
    } catch (err: any) {
      setError(err.message || 'Failed to submit changes');
    }
  };

  const handleDownloadReport = async () => {
    try {
      const blob = await bqIcebergApi.downloadReport(id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `iceberg-structure-report-${id}.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.message || 'Failed to download report');
    }
  };

  if (loading) {
    return (
      <div className="structure-review-page">
        <div className="structure-review-page__loading">Loading structure report...</div>
      </div>
    );
  }

  if (error && !report) {
    return (
      <div className="structure-review-page">
        <Alert variant="error">{error}</Alert>
      </div>
    );
  }

  if (!report) return null;

  return (
    <div className="structure-review-page">
      <div className="structure-review-page__header">
        <div className="structure-review-page__header-left">
          <h1 className="structure-review-page__title">Iceberg Structure Review</h1>
          <p className="structure-review-page__subtitle">
            Review the proposed Iceberg table structures before proceeding with migration.
          </p>
        </div>
        <div className="structure-review-page__header-actions">
          <Button variant="outline" size="sm" onClick={handleDownloadReport}>
            Download Report
          </Button>
        </div>
      </div>

      {successMessage && (
        <Alert variant="success" onClose={() => setSuccessMessage(null)}>
          {successMessage}
        </Alert>
      )}
      {error && (
        <Alert variant="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Dataset to Database Mapping */}
      <Card className="structure-review-page__section">
        <h3 className="structure-review-page__section-title">Dataset to Database Mapping</h3>
        <p className="structure-review-page__section-desc">
          Map BigQuery datasets to Glue Data Catalog database names.
        </p>
        <div className="structure-review-page__mapping-grid">
          {Object.entries(datasetMapping).map(([dataset, dbName]) => (
            <div key={dataset} className="structure-review-page__mapping-row">
              <span className="structure-review-page__mapping-label">{dataset}</span>
              <Input
                value={dbName}
                onChange={(e) =>
                  setDatasetMapping((prev) => ({ ...prev, [dataset]: e.target.value }))
                }
                placeholder="Glue database name"
                aria-label={`Database name for ${dataset}`}
              />
            </div>
          ))}
        </div>
      </Card>

      {/* Namespace for S3 Tables */}
      {report.s3_tables_namespace !== undefined && (
        <Card className="structure-review-page__section">
          <h3 className="structure-review-page__section-title">S3 Tables Namespace</h3>
          <p className="structure-review-page__section-desc">
            Specify the namespace name for S3 Tables. This will be created in your table bucket.
          </p>
          <Input
            value={namespace}
            onChange={(e) => setNamespace(e.target.value)}
            placeholder="e.g., my-analytics-namespace"
            label="Namespace Name"
            aria-label="S3 Tables namespace name"
          />
        </Card>
      )}

      {/* Prerequisites */}
      <Card className="structure-review-page__section">
        <PrerequisitesChecklist prerequisites={report.prerequisites} />
      </Card>

      {/* Warnings */}
      <Card className="structure-review-page__section">
        <WarningsSection warnings={report.warnings} />
      </Card>

      {/* Table Structures */}
      <Card className="structure-review-page__section">
        <h3 className="structure-review-page__section-title">
          Table Structures ({report.tables.length} tables)
        </h3>
        <div className="structure-review-page__tables">
          {report.tables.map((table) => (
            <TableSection
              key={table.iceberg_table_name}
              table={table}
              overrides={overrides}
              onPartitionChange={handlePartitionChange}
              onSortOrderChange={handleSortOrderChange}
              onExcludeToggle={handleExcludeToggle}
              onPropertiesChange={handlePropertiesChange}
              isExcluded={overrides.excluded_tables?.includes(table.iceberg_table_name) || false}
            />
          ))}
        </div>
      </Card>

      {/* Action Buttons */}
      <div className="structure-review-page__footer">
        <Button variant="outline" onClick={handleRequestChanges}>
          Request Changes
        </Button>
        <Button variant="primary" onClick={handleApprove} loading={approving}>
          Approve &amp; Proceed
        </Button>
      </div>
    </div>
  );
};
