/**
 * Tests for ConversionHistoryTable enhancements
 * Requirements: 1.1, 1.2, 1.3, 1.5, 1.6, 2.5, 5.5, 9.6
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ConversionHistoryTable } from '../ConversionHistoryTable';
import type { ConversionJob } from '../../../services/conversionApi';

// Mock the API module
vi.mock('../../../services/conversionApi', () => ({
  listJobs: vi.fn(),
  bulkDeleteJobs: vi.fn(),
  getJobLogs: vi.fn(),
}));

import { listJobs, bulkDeleteJobs, getJobLogs } from '../../../services/conversionApi';
const mockListJobs = vi.mocked(listJobs);
const mockBulkDeleteJobs = vi.mocked(bulkDeleteJobs);
const mockGetJobLogs = vi.mocked(getJobLogs);

/** Helper to create a sample ConversionJob */
const makeJob = (overrides: Partial<ConversionJob> = {}): ConversionJob => ({
  id: 1,
  workspace_id: 1,
  batch_id: null,
  source_code: 'SELECT 1',
  target_code: 'SELECT 1 -- converted',
  source_dialect: 'Bigquery',
  target_dialect: 'Redshift',
  asset_type: 'QUERY',
  asset_name: 'My Test Query',
  bedrock_model: 'claude',
  aws_region: 'us-east-1',
  status: 'completed',
  error_message: null,
  use_sqlglot: false,
  sqlglot_success: null,
  retry_count: 0,
  created_by: 'user',
  created_at: '2026-01-15T10:00:00Z',
  updated_at: '2026-01-15T10:00:00Z',
  ...overrides,
});

const sampleJobs: ConversionJob[] = [
  makeJob({ id: 1, asset_name: 'Alpha Query', asset_type: 'QUERY' }),
  makeJob({ id: 2, asset_name: 'Beta Proc', asset_type: 'STORED_PROCEDURE', status: 'failed' }),
  makeJob({ id: 3, asset_name: 'Gamma Query', asset_type: 'SCHEDULED_QUERY' }),
];

const defaultPaginatedResponse = {
  jobs: sampleJobs,
  total: 3,
  page: 1,
  page_size: 10,
};

describe('ConversionHistoryTable', () => {
  const onSelectJob = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockListJobs.mockResolvedValue(defaultPaginatedResponse);
  });

  // -----------------------------------------------------------------------
  // Requirement 1.1: Manage History button
  // -----------------------------------------------------------------------
  it('displays a "Manage History" button in the header area', async () => {
    render(<ConversionHistoryTable onSelectJob={onSelectJob} />);

    await waitFor(() => {
      expect(screen.getByText('Alpha Query')).toBeInTheDocument();
    });

    expect(screen.getByText('Manage History')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Requirement 1.2: Manage History toggles selection mode
  // -----------------------------------------------------------------------
  it('toggles selection mode when Manage History is clicked', async () => {
    render(<ConversionHistoryTable onSelectJob={onSelectJob} />);

    await waitFor(() => {
      expect(screen.getByText('Alpha Query')).toBeInTheDocument();
    });

    // No checkboxes initially
    expect(screen.queryAllByRole('checkbox')).toHaveLength(0);

    // Click Manage History to enter selection mode
    await userEvent.click(screen.getByText('Manage History'));

    // Checkboxes should now appear (one per job)
    expect(screen.getAllByRole('checkbox')).toHaveLength(3);

    // Button text changes to "Cancel"
    expect(screen.getByText('Cancel')).toBeInTheDocument();
    expect(screen.queryByText('Manage History')).not.toBeInTheDocument();

    // Click Cancel to exit selection mode
    await userEvent.click(screen.getByText('Cancel'));

    // Checkboxes gone
    expect(screen.queryAllByRole('checkbox')).toHaveLength(0);
    expect(screen.getByText('Manage History')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Requirement 1.2: Checkboxes appear in selection mode
  // -----------------------------------------------------------------------
  it('shows checkboxes on each row when in selection mode', async () => {
    render(<ConversionHistoryTable onSelectJob={onSelectJob} />);

    await waitFor(() => {
      expect(screen.getByText('Alpha Query')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText('Manage History'));

    const checkboxes = screen.getAllByRole('checkbox');
    expect(checkboxes).toHaveLength(3);

    // All unchecked initially
    checkboxes.forEach((cb) => {
      expect(cb).not.toBeChecked();
    });
  });

  // -----------------------------------------------------------------------
  // Requirement 1.3: Delete Selected enabled only with selections
  // -----------------------------------------------------------------------
  it('shows "Delete Selected" disabled when no jobs are selected', async () => {
    render(<ConversionHistoryTable onSelectJob={onSelectJob} />);

    await waitFor(() => {
      expect(screen.getByText('Alpha Query')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText('Manage History'));

    const deleteBtn = screen.getByText('Delete Selected');
    expect(deleteBtn).toBeDisabled();
  });

  it('enables "Delete Selected" when at least one job is selected', async () => {
    render(<ConversionHistoryTable onSelectJob={onSelectJob} />);

    await waitFor(() => {
      expect(screen.getByText('Alpha Query')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText('Manage History'));

    const checkboxes = screen.getAllByRole('checkbox');
    await userEvent.click(checkboxes[0]);

    const deleteBtn = screen.getByText('Delete Selected');
    expect(deleteBtn).not.toBeDisabled();
  });

  // -----------------------------------------------------------------------
  // Requirement 1.6: Confirmation dialog shows correct count
  // -----------------------------------------------------------------------
  it('shows confirmation dialog with correct count when Delete Selected is clicked', async () => {
    render(<ConversionHistoryTable onSelectJob={onSelectJob} />);

    await waitFor(() => {
      expect(screen.getByText('Alpha Query')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText('Manage History'));

    // Select 2 jobs
    const checkboxes = screen.getAllByRole('checkbox');
    await userEvent.click(checkboxes[0]);
    await userEvent.click(checkboxes[2]);

    await userEvent.click(screen.getByText('Delete Selected'));

    // Confirmation dialog should show count of 2
    expect(screen.getByText(/delete 2 selected jobs/i)).toBeInTheDocument();
  });

  it('shows singular text when 1 job is selected', async () => {
    render(<ConversionHistoryTable onSelectJob={onSelectJob} />);

    await waitFor(() => {
      expect(screen.getByText('Alpha Query')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText('Manage History'));

    const checkboxes = screen.getAllByRole('checkbox');
    await userEvent.click(checkboxes[0]);

    await userEvent.click(screen.getByText('Delete Selected'));

    expect(screen.getByText(/delete 1 selected job\b/i)).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Requirement 1.4, 1.5: Bulk delete removes jobs and exits selection mode
  // -----------------------------------------------------------------------
  it('calls bulkDeleteJobs, removes deleted jobs, and exits selection mode on confirm', async () => {
    mockBulkDeleteJobs.mockResolvedValue({ message: 'Deleted' });

    render(<ConversionHistoryTable onSelectJob={onSelectJob} />);

    await waitFor(() => {
      expect(screen.getByText('Alpha Query')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText('Manage History'));

    // Select first and third jobs (ids 1 and 3)
    const checkboxes = screen.getAllByRole('checkbox');
    await userEvent.click(checkboxes[0]);
    await userEvent.click(checkboxes[2]);

    await userEvent.click(screen.getByText('Delete Selected'));

    // Confirm deletion
    const dialog = screen.getByRole('dialog');
    const confirmBtn = within(dialog).getByText('Delete');
    await userEvent.click(confirmBtn);

    await waitFor(() => {
      // bulkDeleteJobs called with selected IDs
      expect(mockBulkDeleteJobs).toHaveBeenCalledWith(
        expect.arrayContaining([1, 3])
      );
    });

    // Deleted jobs removed from list
    expect(screen.queryByText('Alpha Query')).not.toBeInTheDocument();
    expect(screen.queryByText('Gamma Query')).not.toBeInTheDocument();
    // Remaining job still visible
    expect(screen.getByText('Beta Proc')).toBeInTheDocument();

    // Selection mode exited — no checkboxes
    expect(screen.queryAllByRole('checkbox')).toHaveLength(0);
    expect(screen.getByText('Manage History')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Requirement 9.6: View Logs opens ConversionLogsPanel
  // -----------------------------------------------------------------------
  it('opens ConversionLogsPanel when View Logs is clicked', async () => {
    mockGetJobLogs.mockResolvedValue([
      {
        id: 1,
        job_id: 1,
        timestamp: '2026-01-15T10:00:00Z',
        log_level: 'INFO',
        step_name: 'template_loaded',
        message: 'Template loaded successfully',
        duration_ms: 5,
      },
    ]);

    render(<ConversionHistoryTable onSelectJob={onSelectJob} />);

    await waitFor(() => {
      expect(screen.getByText('Alpha Query')).toBeInTheDocument();
    });

    // Click View Logs on first job
    const viewLogsBtns = screen.getAllByText('View Logs');
    expect(viewLogsBtns.length).toBeGreaterThanOrEqual(1);

    await userEvent.click(viewLogsBtns[0]);

    // ConversionLogsPanel should open
    await waitFor(() => {
      expect(screen.getByText('Conversion Logs')).toBeInTheDocument();
    });

    expect(mockGetJobLogs).toHaveBeenCalledWith(1);
  });

  // -----------------------------------------------------------------------
  // Requirement 2.5: asset_name column displayed
  // -----------------------------------------------------------------------
  it('displays asset_name column for each job', async () => {
    render(<ConversionHistoryTable onSelectJob={onSelectJob} />);

    await waitFor(() => {
      expect(screen.getByText('Alpha Query')).toBeInTheDocument();
    });

    expect(screen.getByText('Beta Proc')).toBeInTheDocument();
    expect(screen.getByText('Gamma Query')).toBeInTheDocument();

    // Column header
    expect(screen.getByText('Asset Name')).toBeInTheDocument();
  });

  it('displays "Untitled" for jobs without asset_name', async () => {
    mockListJobs.mockResolvedValue({
      jobs: [makeJob({ id: 10, asset_name: null })],
      total: 1,
      page: 1,
      page_size: 10,
    });

    render(<ConversionHistoryTable onSelectJob={onSelectJob} />);

    await waitFor(() => {
      expect(screen.getByText('Untitled')).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // Requirement 5.5: "Query" label for QUERY and SCHEDULED_QUERY
  // -----------------------------------------------------------------------
  it('displays "Query" label for QUERY asset type', async () => {
    render(<ConversionHistoryTable onSelectJob={onSelectJob} />);

    await waitFor(() => {
      expect(screen.getByText('Alpha Query')).toBeInTheDocument();
    });

    // Both QUERY (job 1) and SCHEDULED_QUERY (job 3) should show "Query"
    const queryLabels = screen.getAllByText('Query');
    expect(queryLabels.length).toBeGreaterThanOrEqual(2);
  });

  it('displays "Query" label for SCHEDULED_QUERY asset type', async () => {
    mockListJobs.mockResolvedValue({
      jobs: [makeJob({ id: 5, asset_type: 'SCHEDULED_QUERY', asset_name: 'Scheduled Job' })],
      total: 1,
      page: 1,
      page_size: 10,
    });

    render(<ConversionHistoryTable onSelectJob={onSelectJob} />);

    await waitFor(() => {
      expect(screen.getByText('Scheduled Job')).toBeInTheDocument();
    });

    expect(screen.getByText('Query')).toBeInTheDocument();
  });

  it('displays original asset type label for non-QUERY types', async () => {
    render(<ConversionHistoryTable onSelectJob={onSelectJob} />);

    await waitFor(() => {
      expect(screen.getByText('Beta Proc')).toBeInTheDocument();
    });

    expect(screen.getByText('STORED_PROCEDURE')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Confirmation dialog cancel
  // -----------------------------------------------------------------------
  it('closes confirmation dialog when Cancel is clicked', async () => {
    render(<ConversionHistoryTable onSelectJob={onSelectJob} />);

    await waitFor(() => {
      expect(screen.getByText('Alpha Query')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText('Manage History'));

    const checkboxes = screen.getAllByRole('checkbox');
    await userEvent.click(checkboxes[0]);

    await userEvent.click(screen.getByText('Delete Selected'));

    // Dialog visible
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    // Click Cancel in dialog
    const dialog = screen.getByRole('dialog');
    await userEvent.click(within(dialog).getByText('Cancel'));

    // Dialog dismissed, still in selection mode
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.getAllByRole('checkbox')).toHaveLength(3);
  });
});
