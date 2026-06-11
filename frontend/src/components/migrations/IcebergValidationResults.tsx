/**
 * Validation Results Display for Iceberg migrations
 * Shows per-table validation results (passed/failed/skipped),
 * source vs target row counts, timestamps, and manual validation trigger.
 * Requirements: 10.1, 10.4, 10.5
 */
import React, { useState } from 'react';
import { Card, Badge, Button, Alert } from '../ui';
import './IcebergValidationResults.css';

// --- Types ---

export type ValidationStatus = 'passed' | 'failed' | 'skipped';

export interface TableValidationResult {
  table_name: string;
  source_row_count: number;
  target_row_count: number;
  status: ValidationStatus;
  validated_at: string;
  error_reason?: string;
}

export interface ValidationResultsData {
  migration_id: number;
  overall_status: ValidationStatus;
  results: TableValidationResult[];
  validated_at: string;
}

interface IcebergValidationResultsProps {
  migrationId: number;
  validationData: ValidationResultsData | null;
  loading?: boolean;
  error?: string | null;
  onTriggerValidation?: () => void;
  validating?: boolean;
}

// --- Status Badge Mapping ---

const VALIDATION_BADGE_VARIANT: Record<ValidationStatus, 'success' | 'error' | 'warning'> = {
  passed: 'success',
  failed: 'error',
  skipped: 'warning',
};

const VALIDATION_STATUS_LABELS: Record<ValidationStatus, string> = {
  passed: 'Passed',
  failed: 'Failed',
  skipped: 'Skipped',
};

// --- Helpers ---

const formatNumber = (num: number): string => {
  return new Intl.NumberFormat('en-US').format(num);
};

const formatTimestamp = (timestamp: string): string => {
  try {
    return new Intl.DateTimeFormat('en-US', {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(timestamp));
  } catch {
    return timestamp;
  }
};

// --- Component ---

export const IcebergValidationResults: React.FC<IcebergValidationResultsProps> = ({
  migrationId,
  validationData,
  loading = false,
  error = null,
  onTriggerValidation,
  validating = false,
}) => {
  if (loading && !validationData) {
    return (
      <div className="iceberg-validation">
        <div className="iceberg-validation__loading">Loading validation results...</div>
      </div>
    );
  }

  if (error && !validationData) {
    return (
      <div className="iceberg-validation">
        <Alert variant="error">{error}</Alert>
      </div>
    );
  }

  const passedCount = validationData?.results.filter((r) => r.status === 'passed').length ?? 0;
  const failedCount = validationData?.results.filter((r) => r.status === 'failed').length ?? 0;
  const skippedCount = validationData?.results.filter((r) => r.status === 'skipped').length ?? 0;

  return (
    <div className="iceberg-validation">
      {/* Header */}
      <div className="iceberg-validation__header">
        <div>
          <h2 className="iceberg-validation__title">Validation Results</h2>
          {validationData?.validated_at && (
            <p className="iceberg-validation__timestamp">
              Last validated: {formatTimestamp(validationData.validated_at)}
            </p>
          )}
        </div>
        {onTriggerValidation && (
          <Button
            variant="outline"
            size="sm"
            onClick={onTriggerValidation}
            loading={validating}
            disabled={validating}
            aria-label="Run validation"
          >
            Run Validation
          </Button>
        )}
      </div>

      {/* Summary */}
      {validationData && (
        <Card className="iceberg-validation__summary-card">
          <div className="iceberg-validation__summary">
            <div className="iceberg-validation__summary-item iceberg-validation__summary-item--passed">
              <span className="iceberg-validation__summary-value">{passedCount}</span>
              <span className="iceberg-validation__summary-label">Passed</span>
            </div>
            <div className="iceberg-validation__summary-item iceberg-validation__summary-item--failed">
              <span className="iceberg-validation__summary-value">{failedCount}</span>
              <span className="iceberg-validation__summary-label">Failed</span>
            </div>
            <div className="iceberg-validation__summary-item iceberg-validation__summary-item--skipped">
              <span className="iceberg-validation__summary-value">{skippedCount}</span>
              <span className="iceberg-validation__summary-label">Skipped</span>
            </div>
          </div>
        </Card>
      )}

      {/* Results Table */}
      {validationData && validationData.results.length > 0 && (
        <Card className="iceberg-validation__results-card">
          <div className="iceberg-validation__table-container">
            <table className="iceberg-validation__table">
              <thead>
                <tr>
                  <th>Table Name</th>
                  <th>Source Rows</th>
                  <th>Target Rows</th>
                  <th>Status</th>
                  <th>Validated At</th>
                  <th>Error</th>
                </tr>
              </thead>
              <tbody>
                {validationData.results.map((result) => (
                  <tr key={result.table_name} className={`iceberg-validation__row--${result.status}`}>
                    <td className="iceberg-validation__cell-name">{result.table_name}</td>
                    <td className="iceberg-validation__cell-count">{formatNumber(result.source_row_count)}</td>
                    <td className="iceberg-validation__cell-count">{formatNumber(result.target_row_count)}</td>
                    <td>
                      <Badge variant={VALIDATION_BADGE_VARIANT[result.status]} size="sm">
                        {VALIDATION_STATUS_LABELS[result.status]}
                      </Badge>
                    </td>
                    <td className="iceberg-validation__cell-timestamp">
                      {formatTimestamp(result.validated_at)}
                    </td>
                    <td className="iceberg-validation__cell-error">
                      {result.error_reason || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Empty State */}
      {!validationData && !loading && !error && (
        <Card className="iceberg-validation__empty">
          <p className="iceberg-validation__empty-text">
            No validation results available. Run validation to check data integrity.
          </p>
          {onTriggerValidation && (
            <Button variant="primary" size="sm" onClick={onTriggerValidation} loading={validating}>
              Run Validation
            </Button>
          )}
        </Card>
      )}
    </div>
  );
};
