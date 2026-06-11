/**
 * Migration Progress Display for Iceberg parallel loading
 * Shows per-table progress, overall progress percentage, table-level status,
 * and current stage indicator.
 * Requirements: 5.8, 11.4, 11.5, 12.3
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Card, Badge, Button } from '../ui';
import './IcebergProgressDisplay.css';

// --- Types ---

export type TableLoadStatus = 'pending' | 'loading' | 'completed' | 'failed';
export type MigrationStage = 'export' | 'transfer' | 'review' | 'load';

export interface TableProgress {
  table_name: string;
  status: TableLoadStatus;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
}

export interface MigrationProgress {
  migration_id: number;
  status: string;
  current_stage: MigrationStage;
  progress_percentage: number;
  total_tables: number;
  completed_tables: number;
  failed_tables: number;
  tables: TableProgress[];
}

interface IcebergProgressDisplayProps {
  migrationId: number;
  progress: MigrationProgress | null;
  loading?: boolean;
  error?: string | null;
  onRefresh?: () => void;
}

// --- Stage Labels ---

const STAGE_LABELS: Record<MigrationStage, string> = {
  export: 'Exporting from BigQuery',
  transfer: 'Transferring to S3',
  review: 'Pending Review',
  load: 'Loading into Iceberg',
};

const STAGE_ORDER: MigrationStage[] = ['export', 'transfer', 'review', 'load'];

// --- Status Badge Mapping ---

const STATUS_BADGE_VARIANT: Record<TableLoadStatus, 'default' | 'info' | 'success' | 'error'> = {
  pending: 'default',
  loading: 'info',
  completed: 'success',
  failed: 'error',
};

const STATUS_LABELS: Record<TableLoadStatus, string> = {
  pending: 'Pending',
  loading: 'Loading',
  completed: 'Completed',
  failed: 'Failed',
};

// --- Component ---

export const IcebergProgressDisplay: React.FC<IcebergProgressDisplayProps> = ({
  migrationId,
  progress,
  loading = false,
  error = null,
  onRefresh,
}) => {
  if (loading && !progress) {
    return (
      <div className="iceberg-progress">
        <div className="iceberg-progress__loading">Loading migration progress...</div>
      </div>
    );
  }

  if (error && !progress) {
    return (
      <div className="iceberg-progress">
        <div className="iceberg-progress__error">
          <span>{error}</span>
          {onRefresh && (
            <Button variant="outline" size="sm" onClick={onRefresh}>
              Retry
            </Button>
          )}
        </div>
      </div>
    );
  }

  if (!progress) return null;

  return (
    <div className="iceberg-progress">
      {/* Header */}
      <div className="iceberg-progress__header">
        <h2 className="iceberg-progress__title">Migration Progress</h2>
        {onRefresh && (
          <Button variant="ghost" size="sm" onClick={onRefresh} aria-label="Refresh progress">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
              <path d="M2 8a6 6 0 0 1 10.47-4M14 8a6 6 0 0 1-10.47 4" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M12.47 1v3h-3M3.53 15v-3h3" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </Button>
        )}
      </div>

      {/* Stage Indicator */}
      <Card className="iceberg-progress__stage-card">
        <div className="iceberg-progress__stage-indicator">
          {STAGE_ORDER.map((stage, index) => {
            const isActive = stage === progress.current_stage;
            const isCompleted = STAGE_ORDER.indexOf(stage) < STAGE_ORDER.indexOf(progress.current_stage);
            return (
              <div
                key={stage}
                className={[
                  'iceberg-progress__stage-step',
                  isActive && 'iceberg-progress__stage-step--active',
                  isCompleted && 'iceberg-progress__stage-step--completed',
                ].filter(Boolean).join(' ')}
              >
                <div className="iceberg-progress__stage-dot">
                  {isCompleted ? (
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                      <path d="M2.5 6l2.5 2.5 4.5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  ) : (
                    <span>{index + 1}</span>
                  )}
                </div>
                <span className="iceberg-progress__stage-label">{STAGE_LABELS[stage]}</span>
                {index < STAGE_ORDER.length - 1 && (
                  <div className={[
                    'iceberg-progress__stage-connector',
                    isCompleted && 'iceberg-progress__stage-connector--completed',
                  ].filter(Boolean).join(' ')} />
                )}
              </div>
            );
          })}
        </div>
      </Card>

      {/* Overall Progress */}
      <Card className="iceberg-progress__overall-card">
        <div className="iceberg-progress__overall">
          <div className="iceberg-progress__overall-header">
            <span className="iceberg-progress__overall-label">Overall Progress</span>
            <span className="iceberg-progress__overall-percentage">{progress.progress_percentage}%</span>
          </div>
          <div className="iceberg-progress__progress-bar" role="progressbar" aria-valuenow={progress.progress_percentage} aria-valuemin={0} aria-valuemax={100} aria-label="Migration progress">
            <div
              className="iceberg-progress__progress-fill"
              style={{ width: `${progress.progress_percentage}%` }}
            />
          </div>
          <div className="iceberg-progress__overall-stats">
            <span className="iceberg-progress__stat">
              <span className="iceberg-progress__stat-value">{progress.completed_tables}</span>
              <span className="iceberg-progress__stat-label">Completed</span>
            </span>
            <span className="iceberg-progress__stat">
              <span className="iceberg-progress__stat-value">{progress.failed_tables}</span>
              <span className="iceberg-progress__stat-label">Failed</span>
            </span>
            <span className="iceberg-progress__stat">
              <span className="iceberg-progress__stat-value">{progress.total_tables}</span>
              <span className="iceberg-progress__stat-label">Total</span>
            </span>
          </div>
        </div>
      </Card>

      {/* Per-Table Progress */}
      <Card className="iceberg-progress__tables-card">
        <h3 className="iceberg-progress__tables-title">Table Progress</h3>
        <div className="iceberg-progress__tables-list">
          {progress.tables.map((table) => (
            <div key={table.table_name} className="iceberg-progress__table-row">
              <div className="iceberg-progress__table-info">
                <span className="iceberg-progress__table-name">{table.table_name}</span>
                {table.error_message && (
                  <span className="iceberg-progress__table-error">{table.error_message}</span>
                )}
              </div>
              <Badge variant={STATUS_BADGE_VARIANT[table.status]} size="sm">
                {STATUS_LABELS[table.status]}
              </Badge>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};
