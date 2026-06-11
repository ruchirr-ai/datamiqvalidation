/**
 * Tests for IcebergProgressDisplay
 * Covers: progress bar updates, per-table status rendering, stage indicator,
 * loading/error states, and refresh functionality.
 * Requirements: 5.8, 11.4, 12.3
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {
  IcebergProgressDisplay,
  type MigrationProgress,
  type TableProgress,
} from '../IcebergProgressDisplay';

// --- Sample Data ---

const sampleTables: TableProgress[] = [
  { table_name: 'users', status: 'completed', started_at: '2026-01-25T10:00:00Z', completed_at: '2026-01-25T10:05:00Z' },
  { table_name: 'orders', status: 'loading', started_at: '2026-01-25T10:02:00Z' },
  { table_name: 'products', status: 'pending' },
  { table_name: 'events', status: 'failed', error_message: 'S3 access denied' },
];

const sampleProgress: MigrationProgress = {
  migration_id: 1,
  status: 'running',
  current_stage: 'load',
  progress_percentage: 50,
  total_tables: 4,
  completed_tables: 2,
  failed_tables: 1,
  tables: sampleTables,
};

describe('IcebergProgressDisplay', () => {
  // --- Loading State ---

  it('renders loading state when loading and no progress data', () => {
    render(
      <IcebergProgressDisplay
        migrationId={1}
        progress={null}
        loading={true}
      />
    );
    expect(screen.getByText('Loading migration progress...')).toBeInTheDocument();
  });

  it('does not render loading when progress data is available', () => {
    render(
      <IcebergProgressDisplay
        migrationId={1}
        progress={sampleProgress}
        loading={true}
      />
    );
    expect(screen.queryByText('Loading migration progress...')).not.toBeInTheDocument();
    expect(screen.getByText('Migration Progress')).toBeInTheDocument();
  });

  // --- Error State ---

  it('renders error state when error and no progress data', () => {
    render(
      <IcebergProgressDisplay
        migrationId={1}
        progress={null}
        error="Failed to fetch progress"
      />
    );
    expect(screen.getByText('Failed to fetch progress')).toBeInTheDocument();
  });

  it('renders retry button in error state when onRefresh is provided', () => {
    const onRefresh = vi.fn();
    render(
      <IcebergProgressDisplay
        migrationId={1}
        progress={null}
        error="Network error"
        onRefresh={onRefresh}
      />
    );
    expect(screen.getByText('Retry')).toBeInTheDocument();
  });

  it('calls onRefresh when retry button is clicked', async () => {
    const user = userEvent.setup();
    const onRefresh = vi.fn();
    render(
      <IcebergProgressDisplay
        migrationId={1}
        progress={null}
        error="Network error"
        onRefresh={onRefresh}
      />
    );
    await user.click(screen.getByText('Retry'));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  // --- Null State ---

  it('renders nothing when progress is null and not loading/error', () => {
    const { container } = render(
      <IcebergProgressDisplay migrationId={1} progress={null} />
    );
    expect(container.firstChild).toBeNull();
  });

  // --- Stage Indicator ---

  it('renders all four stage labels', () => {
    render(<IcebergProgressDisplay migrationId={1} progress={sampleProgress} />);
    expect(screen.getByText('Exporting from BigQuery')).toBeInTheDocument();
    expect(screen.getByText('Transferring to S3')).toBeInTheDocument();
    expect(screen.getByText('Pending Review')).toBeInTheDocument();
    expect(screen.getByText('Loading into Iceberg')).toBeInTheDocument();
  });

  it('marks current stage as active', () => {
    render(<IcebergProgressDisplay migrationId={1} progress={sampleProgress} />);
    const loadLabel = screen.getByText('Loading into Iceberg');
    const stepElement = loadLabel.closest('.iceberg-progress__stage-step');
    expect(stepElement).toHaveClass('iceberg-progress__stage-step--active');
  });

  it('marks previous stages as completed', () => {
    render(<IcebergProgressDisplay migrationId={1} progress={sampleProgress} />);
    const exportLabel = screen.getByText('Exporting from BigQuery');
    const exportStep = exportLabel.closest('.iceberg-progress__stage-step');
    expect(exportStep).toHaveClass('iceberg-progress__stage-step--completed');
  });

  it('renders export stage as active when current_stage is export', () => {
    const exportProgress: MigrationProgress = {
      ...sampleProgress,
      current_stage: 'export',
      progress_percentage: 10,
    };
    render(<IcebergProgressDisplay migrationId={1} progress={exportProgress} />);
    const exportLabel = screen.getByText('Exporting from BigQuery');
    const exportStep = exportLabel.closest('.iceberg-progress__stage-step');
    expect(exportStep).toHaveClass('iceberg-progress__stage-step--active');
    expect(exportStep).not.toHaveClass('iceberg-progress__stage-step--completed');
  });

  // --- Overall Progress ---

  it('displays overall progress percentage', () => {
    render(<IcebergProgressDisplay migrationId={1} progress={sampleProgress} />);
    expect(screen.getByText('50%')).toBeInTheDocument();
  });

  it('renders progress bar with correct aria attributes', () => {
    render(<IcebergProgressDisplay migrationId={1} progress={sampleProgress} />);
    const progressBar = screen.getByRole('progressbar');
    expect(progressBar).toHaveAttribute('aria-valuenow', '50');
    expect(progressBar).toHaveAttribute('aria-valuemin', '0');
    expect(progressBar).toHaveAttribute('aria-valuemax', '100');
  });

  it('displays completed, failed, and total table counts', () => {
    render(<IcebergProgressDisplay migrationId={1} progress={sampleProgress} />);
    expect(screen.getByText('Completed')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
    expect(screen.getByText('Total')).toBeInTheDocument();
    // Values
    expect(screen.getByText('2')).toBeInTheDocument(); // completed
    expect(screen.getByText('1')).toBeInTheDocument(); // failed
    expect(screen.getByText('4')).toBeInTheDocument(); // total
  });

  it('updates progress bar width based on percentage', () => {
    const { container } = render(
      <IcebergProgressDisplay migrationId={1} progress={sampleProgress} />
    );
    const fill = container.querySelector('.iceberg-progress__progress-fill');
    expect(fill).toHaveStyle({ width: '50%' });
  });

  it('renders 0% progress correctly', () => {
    const zeroProgress: MigrationProgress = {
      ...sampleProgress,
      progress_percentage: 0,
      completed_tables: 0,
      failed_tables: 0,
    };
    render(<IcebergProgressDisplay migrationId={1} progress={zeroProgress} />);
    expect(screen.getByText('0%')).toBeInTheDocument();
    const progressBar = screen.getByRole('progressbar');
    expect(progressBar).toHaveAttribute('aria-valuenow', '0');
  });

  it('renders 100% progress correctly', () => {
    const fullProgress: MigrationProgress = {
      ...sampleProgress,
      progress_percentage: 100,
      completed_tables: 4,
      failed_tables: 0,
    };
    render(<IcebergProgressDisplay migrationId={1} progress={fullProgress} />);
    expect(screen.getByText('100%')).toBeInTheDocument();
  });

  // --- Per-Table Status ---

  it('renders all table names', () => {
    render(<IcebergProgressDisplay migrationId={1} progress={sampleProgress} />);
    expect(screen.getByText('users')).toBeInTheDocument();
    expect(screen.getByText('orders')).toBeInTheDocument();
    expect(screen.getByText('products')).toBeInTheDocument();
    expect(screen.getByText('events')).toBeInTheDocument();
  });

  it('renders correct status badges for each table', () => {
    render(<IcebergProgressDisplay migrationId={1} progress={sampleProgress} />);
    expect(screen.getByText('Completed')).toBeInTheDocument();
    expect(screen.getByText('Loading')).toBeInTheDocument();
    expect(screen.getByText('Pending')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
  });

  it('displays error message for failed tables', () => {
    render(<IcebergProgressDisplay migrationId={1} progress={sampleProgress} />);
    expect(screen.getByText('S3 access denied')).toBeInTheDocument();
  });

  it('does not display error message for non-failed tables', () => {
    const noErrorProgress: MigrationProgress = {
      ...sampleProgress,
      tables: [
        { table_name: 'users', status: 'completed' },
        { table_name: 'orders', status: 'loading' },
      ],
    };
    render(<IcebergProgressDisplay migrationId={1} progress={noErrorProgress} />);
    expect(screen.queryByText('S3 access denied')).not.toBeInTheDocument();
  });

  // --- Refresh Button ---

  it('renders refresh button when onRefresh is provided', () => {
    const onRefresh = vi.fn();
    render(
      <IcebergProgressDisplay
        migrationId={1}
        progress={sampleProgress}
        onRefresh={onRefresh}
      />
    );
    expect(screen.getByLabelText('Refresh progress')).toBeInTheDocument();
  });

  it('calls onRefresh when refresh button is clicked', async () => {
    const user = userEvent.setup();
    const onRefresh = vi.fn();
    render(
      <IcebergProgressDisplay
        migrationId={1}
        progress={sampleProgress}
        onRefresh={onRefresh}
      />
    );
    await user.click(screen.getByLabelText('Refresh progress'));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it('does not render refresh button when onRefresh is not provided', () => {
    render(<IcebergProgressDisplay migrationId={1} progress={sampleProgress} />);
    expect(screen.queryByLabelText('Refresh progress')).not.toBeInTheDocument();
  });

  // --- Title ---

  it('renders the title "Migration Progress"', () => {
    render(<IcebergProgressDisplay migrationId={1} progress={sampleProgress} />);
    expect(screen.getByText('Migration Progress')).toBeInTheDocument();
  });

  it('renders "Table Progress" section title', () => {
    render(<IcebergProgressDisplay migrationId={1} progress={sampleProgress} />);
    expect(screen.getByText('Table Progress')).toBeInTheDocument();
  });
});
