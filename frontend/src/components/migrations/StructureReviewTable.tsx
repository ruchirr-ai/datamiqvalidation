/**
 * StructureReviewTable - Displays per-table structure review with compaction strategy,
 * partition transforms, Lake Formation prerequisites, and glue.id validation.
 * Requirements: 3.1, 5.1, 5.7, 7.6, 2.4
 */
import React from 'react';
import { Badge, Card } from '../ui';
import type {
  TableStructure,
  CompactionConfig,
  LakeFormationPrerequisite,
  PartitionSpec,
} from '../../types/bqIceberg';
import './StructureReviewTable.css';

/** Descriptions for each compaction strategy */
const COMPACTION_STRATEGY_LABELS: Record<string, string> = {
  binpack: 'Binpack',
  sort: 'Sort',
  'z-order': 'Z-Order',
};

const COMPACTION_STRATEGY_DESCRIPTIONS: Record<string, string> = {
  binpack: 'Combines small files without reordering (best for append-heavy workloads)',
  sort: 'Reorders data by specified columns (best for range queries on specific columns)',
  'z-order': 'Interleaves multiple columns (best for queries filtering on multiple columns simultaneously)',
};

export interface GlueIdInfo {
  value: string;
  isValid: boolean;
}

export interface StructureReviewTableProps {
  /** List of table structures to display */
  tables: TableStructure[];
  /** Per-table compaction configuration, keyed by table name */
  compactionConfigs?: Record<string, CompactionConfig>;
  /** Lake Formation prerequisites (only for S3 Tables destinations) */
  lakeFormationPrerequisites?: LakeFormationPrerequisite[];
  /** Derived glue.id with validation status */
  glueId?: GlueIdInfo;
  /** Destination type to conditionally show S3 Tables sections */
  destinationType: 'iceberg_s3' | 'iceberg_s3_tables';
}

/**
 * Formats a partition spec as a human-readable string.
 * e.g., "days(event_timestamp)" for transform=day, column=event_timestamp
 */
export function formatPartitionTransform(spec: PartitionSpec): string {
  const transformDisplayMap: Record<string, string> = {
    day: 'days',
    hour: 'hours',
    month: 'months',
    year: 'years',
    identity: 'identity',
    bucket: 'bucket',
    truncate: 'truncate',
  };

  const displayTransform = transformDisplayMap[spec.transform] || spec.transform;
  return `${displayTransform}(${spec.column})`;
}

export const StructureReviewTable: React.FC<StructureReviewTableProps> = ({
  tables,
  compactionConfigs = {},
  lakeFormationPrerequisites = [],
  glueId,
  destinationType,
}) => {
  const isS3Tables = destinationType === 'iceberg_s3_tables';

  return (
    <div className="structure-review-table">
      {/* Glue ID Section - S3 Tables only */}
      {isS3Tables && glueId && (
        <Card className="structure-review-table__glue-section" padding="sm">
          <div className="structure-review-table__glue-header">
            <h4 className="structure-review-table__section-title">Glue Catalog Identifier</h4>
          </div>
          <div className="structure-review-table__glue-content">
            <code className="structure-review-table__glue-value">{glueId.value}</code>
            {glueId.isValid ? (
              <Badge variant="success" size="sm">
                <span className="structure-review-table__validation-icon" aria-hidden="true">
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M2 6l3 3 5-5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </span>
                Valid
              </Badge>
            ) : (
              <Badge variant="error" size="sm">
                <span className="structure-review-table__validation-icon" aria-hidden="true">
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M3 3l6 6M9 3l-6 6" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </span>
                Invalid
              </Badge>
            )}
          </div>
        </Card>
      )}

      {/* Per-Table Structure Review */}
      <div className="structure-review-table__tables">
        <h4 className="structure-review-table__section-title">Table Structure Review</h4>
        {tables.map((table) => {
          const compaction = compactionConfigs[table.table_name];
          return (
            <Card
              key={table.table_name}
              className="structure-review-table__table-card"
              padding="sm"
            >
              <div className="structure-review-table__table-header">
                <h5 className="structure-review-table__table-name">{table.iceberg_table_name}</h5>
                <span className="structure-review-table__table-meta">
                  {table.columns.length} columns
                </span>
              </div>

              {/* Partition Transforms */}
              {table.partition_spec.length > 0 && (
                <div className="structure-review-table__field">
                  <span className="structure-review-table__field-label">Partitioning</span>
                  <div className="structure-review-table__partition-list">
                    {table.partition_spec.map((spec, idx) => (
                      <code key={idx} className="structure-review-table__partition-value">
                        {formatPartitionTransform(spec)}
                      </code>
                    ))}
                  </div>
                </div>
              )}

              {/* Compaction Strategy */}
              {compaction && (
                <div className="structure-review-table__field">
                  <span className="structure-review-table__field-label">Compaction Strategy</span>
                  <div className="structure-review-table__compaction-info">
                    <Badge variant="info" size="sm">
                      {COMPACTION_STRATEGY_LABELS[compaction.strategy] || compaction.strategy}
                    </Badge>
                    <span className="structure-review-table__compaction-desc">
                      {COMPACTION_STRATEGY_DESCRIPTIONS[compaction.strategy]}
                    </span>
                  </div>
                  {(compaction.strategy === 'sort' || compaction.strategy === 'z-order') &&
                    compaction.sort_columns.length > 0 && (
                      <div className="structure-review-table__sort-columns">
                        <span className="structure-review-table__sort-label">Sort columns:</span>
                        {compaction.sort_columns.map((col) => (
                          <code key={col} className="structure-review-table__sort-column">
                            {col}
                          </code>
                        ))}
                      </div>
                    )}
                  {compaction.recommended_strategy &&
                    compaction.recommended_strategy !== compaction.strategy && (
                      <div className="structure-review-table__recommendation">
                        <svg
                          width="14"
                          height="14"
                          viewBox="0 0 14 14"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="1.5"
                          aria-hidden="true"
                        >
                          <circle cx="7" cy="7" r="6" />
                          <path d="M7 4v3M7 9.5v.5" strokeLinecap="round" />
                        </svg>
                        <span>
                          Recommended: {COMPACTION_STRATEGY_LABELS[compaction.recommended_strategy]}
                          {compaction.recommended_sort_columns &&
                            compaction.recommended_sort_columns.length > 0 &&
                            ` on ${compaction.recommended_sort_columns.join(', ')}`}
                        </span>
                      </div>
                    )}
                </div>
              )}
            </Card>
          );
        })}
      </div>

      {/* Lake Formation Prerequisites - S3 Tables only */}
      {isS3Tables && lakeFormationPrerequisites.length > 0 && (
        <div className="structure-review-table__lf-section">
          <h4 className="structure-review-table__section-title">Lake Formation Prerequisites</h4>
          <p className="structure-review-table__lf-desc">
            The following permissions must be configured in AWS Lake Formation before starting the migration.
          </p>
          <ul className="structure-review-table__lf-list" role="list">
            {lakeFormationPrerequisites.map((prereq, idx) => (
              <li key={idx} className="structure-review-table__lf-item">
                <div className="structure-review-table__lf-item-header">
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 16 16"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    aria-hidden="true"
                    className="structure-review-table__lf-icon"
                  >
                    <rect x="2" y="2" width="12" height="12" rx="2" />
                  </svg>
                  <span className="structure-review-table__lf-description">
                    {prereq.description}
                  </span>
                </div>
                <code className="structure-review-table__lf-permission">
                  {prereq.arn_or_permission}
                </code>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
