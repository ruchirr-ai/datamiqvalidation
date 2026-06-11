/**
 * Tests for IcebergValidationResults
 * Covers: validation results table, per-table status, source/target row counts,
 * manual validation trigger, loading/error states.
 * Requirements: 10.1, 10.4, 10.5
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {
  IcebergValidationResults,
  type ValidationResultsData,
  type TableValidationResult,
} from '../IcebergValidationResults';

// --- Sample Data ---

const sampleResults: TableValidationResult[] = [
  {
    table_name: 'users',
    source_row_count: 10000,
    target_row_count: 10000,
    status: 'passed',
    validated_at: '2026-01-25T10:30:00Z',
  },
  {
    table_name: 'orders',
    source_row_count: 50000,
    target_row_count: 49998,
    status: 'failed',
    validated_at: '2026-01-25T10:30:00Z',
    error_reason: 'Row count mismatch: expected 50000, got 49998',
  },
  {
    table_name: 'events',
    source_row_count: 100000,
    target_row_count: 0,
    status: 'skipped',
    validated_at: '2026-01-25T10:30:00Z',
    error_reason: 'Athena query execution failed',
  },
];

const sampleValidationData: ValidationResultsData = {
  migration_id: 1,
  overall_status: 'failed',
  results: sampleResults,
  validated_at: '2026-01-25T10:30:00Z',
};

describe('IcebergValidationResults', () => {
  // --- Loading State ---

  it('renders loading state when loading and no data', () => {
    render(
      <IcebergValidationResults
        migrationId={1}
        validationData={null}
        loading={true}
      />
    );
    expect(screen.getByText('Loading validation results...')).toBeInTheDocument();
  });

  it('does not render loading when data is available', () => {
    render(
      <IcebergValidationResults
        migrationId={1}
        validationData={sampleValidationData}
        loading={true}
      />
    );
    expect(screen.queryByText('Loading validation results...')).not.toBeInTheDocument();
    expect(screen.getByText('Validation Results')).toBeInTheDocument();
  });

  // --- Error State ---

  it('renders error state when error and no data', () => {
    render(
      <IcebergValidationResults
        migrationId={1}
        validationData={null}
        error="Failed to load validation results"
      />
    );
    expect(screen.getByText('Failed to load validation results')).toBeInTheDocument();
  });

  // --- Empty State ---

  it('renders empty state when no data and not loading/error', () => {
    render(
      <IcebergValidationResults migrationId={1} validationData={null} />
    );
    expect(screen.getByText(/No validation results available/)).toBeInTheDocument();
  });

  it('renders Run Validation button in empty state when onTriggerValidation is provided', () => {
    const onTrigger = vi.fn();
    render(
      <IcebergValidationResults
        migrationId={1}
        validationData={null}
        onTriggerValidation={onTrigger}
      />
    );
    expect(screen.getByText('Run Validation')).toBeInTheDocument();
  });

  // --- Header ---

  it('renders the title "Validation Results"', () => {
    render(
      <IcebergValidationResults migrationId={1} validationData={sampleValidationData} />
    );
    expect(screen.getByText('Validation Results')).toBeInTheDocument();
  });

  it('displays last validated timestamp', () => {
    render(
      <IcebergValidationResults migrationId={1} validationData={sampleValidationData} />
    );
    expect(screen.getByText(/Last validated:/)).toBeInTheDocument();
  });

  // --- Summary ---

  it('displays summary counts for passed, failed, and skipped', () => {
    render(
      <IcebergValidationResults migrationId={1} validationData={sampleValidationData} />
    );
    // Summary labels
    expect(screen.getByText('Passed')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
    expect(screen.getByText('Skipped')).toBeInTheDocument();
  });

  it('displays correct summary values', () => {
    render(
      <IcebergValidationResults migrationId={1} validationData={sampleValidationData} />
    );
    // 1 passed, 1 failed, 1 skipped
    const summaryItems = document.querySelectorAll('.iceberg-validation__summary-value');
    const values = Array.from(summaryItems).map((el) => el.textContent);
    expect(values).toContain('1'); // passed
  });

  // --- Results Table ---

  it('renders table headers', () => {
    render(
      <IcebergValidationResults migrationId={1} validationData={sampleValidationData} />
    );
    expect(screen.getByText('Table Name')).toBeInTheDocument();
    expect(screen.getByText('Source Rows')).toBeInTheDocument();
    expect(screen.getByText('Target Rows')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
    expect(screen.getByText('Validated At')).toBeInTheDocument();
    expect(screen.getByText('Error')).toBeInTheDocument();
  });

  it('renders all table names in results', () => {
    render(
      <IcebergValidationResults migrationId={1} validationData={sampleValidationData} />
    );
    expect(screen.getByText('users')).toBeInTheDocument();
    expect(screen.getByText('orders')).toBeInTheDocument();
    expect(screen.getByText('events')).toBeInTheDocument();
  });

  it('displays formatted source and target row counts', () => {
    render(
      <IcebergValidationResults migrationId={1} validationData={sampleValidationData} />
    );
    expect(screen.getByText('10,000')).toBeInTheDocument(); // users source
    expect(screen.getByText('50,000')).toBeInTheDocument(); // orders source
    expect(screen.getByText('49,998')).toBeInTheDocument(); // orders target
    expect(screen.getByText('100,000')).toBeInTheDocument(); // events source
  });

  it('displays error reason for failed tables', () => {
    render(
      <IcebergValidationResults migrationId={1} validationData={sampleValidationData} />
    );
    expect(screen.getByText(/Row count mismatch/)).toBeInTheDocument();
  });

  it('displays error reason for skipped tables', () => {
    render(
      <IcebergValidationResults migrationId={1} validationData={sampleValidationData} />
    );
    expect(screen.getByText(/Athena query execution failed/)).toBeInTheDocument();
  });

  it('displays dash for tables without error reason', () => {
    render(
      <IcebergValidationResults migrationId={1} validationData={sampleValidationData} />
    );
    // The 'users' table has no error, should show '—'
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  // --- Status Badges ---

  it('renders correct badge variants for each status', () => {
    render(
      <IcebergValidationResults migrationId={1} validationData={sampleValidationData} />
    );
    // Check badge text content
    const badges = screen.getAllByText(/^(Passed|Failed|Skipped)$/);
    expect(badges.length).toBeGreaterThanOrEqual(3);
  });

  // --- Manual Validation Trigger ---

  it('renders Run Validation button when onTriggerValidation is provided', () => {
    const onTrigger = vi.fn();
    render(
      <IcebergValidationResults
        migrationId={1}
        validationData={sampleValidationData}
        onTriggerValidation={onTrigger}
      />
    );
    expect(screen.getByLabelText('Run validation')).toBeInTheDocument();
  });

  it('calls onTriggerValidation when button is clicked', async () => {
    const user = userEvent.setup();
    const onTrigger = vi.fn();
    render(
      <IcebergValidationResults
        migrationId={1}
        validationData={sampleValidationData}
        onTriggerValidation={onTrigger}
      />
    );
    await user.click(screen.getByLabelText('Run validation'));
    expect(onTrigger).toHaveBeenCalledTimes(1);
  });

  it('disables button and shows loading when validating', () => {
    const onTrigger = vi.fn();
    render(
      <IcebergValidationResults
        migrationId={1}
        validationData={sampleValidationData}
        onTriggerValidation={onTrigger}
        validating={true}
      />
    );
    const button = screen.getByLabelText('Run validation');
    expect(button).toBeDisabled();
  });

  it('does not render Run Validation button when onTriggerValidation is not provided', () => {
    render(
      <IcebergValidationResults migrationId={1} validationData={sampleValidationData} />
    );
    expect(screen.queryByLabelText('Run validation')).not.toBeInTheDocument();
  });

  // --- Edge Cases ---

  it('handles empty results array', () => {
    const emptyData: ValidationResultsData = {
      ...sampleValidationData,
      results: [],
    };
    render(
      <IcebergValidationResults migrationId={1} validationData={emptyData} />
    );
    expect(screen.getByText('Validation Results')).toBeInTheDocument();
    // Table should not render
    expect(screen.queryByText('Table Name')).not.toBeInTheDocument();
  });

  it('handles all tables passed', () => {
    const allPassed: ValidationResultsData = {
      migration_id: 1,
      overall_status: 'passed',
      results: [
        { table_name: 'users', source_row_count: 100, target_row_count: 100, status: 'passed', validated_at: '2026-01-25T10:30:00Z' },
        { table_name: 'orders', source_row_count: 200, target_row_count: 200, status: 'passed', validated_at: '2026-01-25T10:30:00Z' },
      ],
      validated_at: '2026-01-25T10:30:00Z',
    };
    render(
      <IcebergValidationResults migrationId={1} validationData={allPassed} />
    );
    // Should show 2 passed, 0 failed, 0 skipped
    const summaryItems = document.querySelectorAll('.iceberg-validation__summary-value');
    const values = Array.from(summaryItems).map((el) => el.textContent);
    expect(values).toEqual(['2', '0', '0']);
  });

  it('handles large row counts with proper formatting', () => {
    const largeData: ValidationResultsData = {
      migration_id: 1,
      overall_status: 'passed',
      results: [
        { table_name: 'big_table', source_row_count: 1234567890, target_row_count: 1234567890, status: 'passed', validated_at: '2026-01-25T10:30:00Z' },
      ],
      validated_at: '2026-01-25T10:30:00Z',
    };
    render(
      <IcebergValidationResults migrationId={1} validationData={largeData} />
    );
    expect(screen.getAllByText('1,234,567,890').length).toBe(2);
  });
});
