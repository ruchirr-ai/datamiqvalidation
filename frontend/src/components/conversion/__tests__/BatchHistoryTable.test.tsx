/**
 * Tests for BatchHistoryTable enhancements
 * Requirements: 2.6, 5.6, 9.5, 13.2, 13.3, 13.4, 13.5
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BatchHistoryTable } from '../BatchHistoryTable';
import type { ConversionBatch, ConversionJob } from '../../../services/conversionApi';

// Mock the API module
vi.mock('../../../services/conversionApi', () => ({
  listBatches: vi.fn(),
  deleteBatch: vi.fn(),
  listBatchJobs: vi.fn(),
  getJobLogs: vi.fn(),
}));

import { listBatches, deleteBatch, listBatchJobs, getJobLogs } from '../../../services/conversionApi';
const mockListBatches = vi.mocked(listBatches);
const mockDeleteBatch = vi.mocked(deleteBatch);
const mockListBatchJobs = vi.mocked(listBatchJobs);
const mockGetJobLogs = vi.mocked(getJobLogs);

/** Helper to create a sample ConversionBatch */
const makeBatch = (overrides: Partial<ConversionBatch> = {}): ConversionBatch => ({
  id: 1,
  workspace_id: 1,
  batch_name: null,
  migration_project_id: 10,
  source_connection_id: 1,
  target_connection_id: 2,
  status: 'completed',
  total_assets: 5,
  completed_assets: 4,
  failed_assets: 1,
  bedrock_model: 'claude',
  aws_region: 'us-east-1',
  use_sqlglot: false,
  max_retries: 2,
  created_by: 'user',
  created_at: '2026-02-01T10:00:00Z',
  updated_at: '2026-02-01T10:05:00Z',
  ...overrides,
});

/** Helper to create a sample ConversionJob */
const makeJob = (overrides: Partial<ConversionJob> = {}): ConversionJob => ({
  id: 1,
  workspace_id: 1,
  batch_id: 1,
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
  created_at: '2026-02-01T10:00:00Z',
  updated_at: '2026-02-01T10:00:00Z',
  ...overrides,
});

const sampleBatches: ConversionBatch[] = [
  makeBatch({ id: 1, status: 'completed', total_assets: 5, completed_assets: 4, failed_assets: 1 }),
  makeBatch({ id: 2, status: 'in_progress', total_assets: 3, completed_assets: 1, failed_assets: 0 }),
  makeBatch({ id: 3, status: 'failed', total_assets: 2, completed_assets: 0, failed_assets: 2 }),
];

const sampleJobs: ConversionJob[] = [
  makeJob({ id: 10, batch_id: 1, asset_name: 'Alpha Query', asset_type: 'QUERY', status: 'completed' }),
  makeJob({ id: 11, batch_id: 1, asset_name: 'Beta View', asset_type: 'VIEW', status: 'completed' }),
  makeJob({ id: 12, batch_id: 1, asset_name: 'Gamma Scheduled', asset_type: 'SCHEDULED_QUERY', status: 'failed' }),
];

const defaultBatchesResponse = {
  batches: sampleBatches,
  total: 3,
};

describe('BatchHistoryTable', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListBatches.mockResolvedValue(defaultBatchesResponse);
    mockListBatchJobs.mockResolvedValue(sampleJobs);
    mockDeleteBatch.mockResolvedValue({ message: 'Deleted' });
  });

  // -----------------------------------------------------------------------
  // Requirement 13.3: Fetches batches from API on mount
  // -----------------------------------------------------------------------
  it('fetches batches from API on mount and displays them', async () => {
    render(<BatchHistoryTable />);

    await waitFor(() => {
      expect(screen.getByText('#1')).toBeInTheDocument();
    });

    expect(mockListBatches).toHaveBeenCalledWith(1, 10);
    expect(screen.getByText('#2')).toBeInTheDocument();
    expect(screen.getByText('#3')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Requirement 13.4: Manage History toggles selection mode
  // -----------------------------------------------------------------------
  it('displays a "Manage History" button and toggles selection mode', async () => {
    render(<BatchHistoryTable />);

    await waitFor(() => {
      expect(screen.getByText('#1')).toBeInTheDocument();
    });

    expect(screen.getByText('Manage History')).toBeInTheDocument();

    // No checkboxes initially
    expect(screen.queryAllByRole('checkbox')).toHaveLength(0);

    // Enter selection mode
    await userEvent.click(screen.getByText('Manage History'));
    expect(screen.getAllByRole('checkbox')).toHaveLength(3);
    expect(screen.getByText('Cancel')).toBeInTheDocument();

    // Exit selection mode
    await userEvent.click(screen.getByText('Cancel'));
    expect(screen.queryAllByRole('checkbox')).toHaveLength(0);
    expect(screen.getByText('Manage History')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Requirement 13.4: Delete Selected disabled when none selected
  // -----------------------------------------------------------------------
  it('shows "Delete Selected" disabled when no batches are selected', async () => {
    render(<BatchHistoryTable />);

    await waitFor(() => {
      expect(screen.getByText('#1')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText('Manage History'));

    const deleteBtn = screen.getByText('Delete Selected');
    expect(deleteBtn).toBeDisabled();
  });

  it('enables "Delete Selected" when at least one batch is selected', async () => {
    render(<BatchHistoryTable />);

    await waitFor(() => {
      expect(screen.getByText('#1')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText('Manage History'));

    const checkboxes = screen.getAllByRole('checkbox');
    await userEvent.click(checkboxes[0]);

    const deleteBtn = screen.getByText('Delete Selected');
    expect(deleteBtn).not.toBeDisabled();
  });

  // -----------------------------------------------------------------------
  // Requirement 13.5: Delete Selected calls deleteBatch for each selected
  // -----------------------------------------------------------------------
  it('calls deleteBatch for each selected batch on confirm', async () => {
    render(<BatchHistoryTable />);

    await waitFor(() => {
      expect(screen.getByText('#1')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText('Manage History'));

    // Select first and third batches
    const checkboxes = screen.getAllByRole('checkbox');
    await userEvent.click(checkboxes[0]);
    await userEvent.click(checkboxes[2]);

    await userEvent.click(screen.getByText('Delete Selected'));

    // Confirmation dialog should show
    expect(screen.getByText(/delete 2 selected batches/i)).toBeInTheDocument();

    // Confirm
    const dialog = screen.getByRole('dialog');
    await userEvent.click(within(dialog).getByText('Delete'));

    await waitFor(() => {
      expect(mockDeleteBatch).toHaveBeenCalledWith(1);
      expect(mockDeleteBatch).toHaveBeenCalledWith(3);
      expect(mockDeleteBatch).toHaveBeenCalledTimes(2);
    });

    // Deleted batches removed from list
    expect(screen.queryByText('#1')).not.toBeInTheDocument();
    expect(screen.queryByText('#3')).not.toBeInTheDocument();
    expect(screen.getByText('#2')).toBeInTheDocument();

    // Selection mode exited
    expect(screen.queryAllByRole('checkbox')).toHaveLength(0);
  });

  it('shows singular text when 1 batch is selected for deletion', async () => {
    render(<BatchHistoryTable />);

    await waitFor(() => {
      expect(screen.getByText('#1')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText('Manage History'));

    const checkboxes = screen.getAllByRole('checkbox');
    await userEvent.click(checkboxes[0]);

    await userEvent.click(screen.getByText('Delete Selected'));

    expect(screen.getByText(/delete 1 selected batch\b/i)).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Requirement 2.6: Asset names displayed in job detail views
  // -----------------------------------------------------------------------
  it('displays asset names in job detail views when batch row is clicked', async () => {
    render(<BatchHistoryTable />);

    await waitFor(() => {
      expect(screen.getByText('#1')).toBeInTheDocument();
    });

    // Click on first batch row to expand job details
    await userEvent.click(screen.getByText('#1'));

    await waitFor(() => {
      expect(screen.getByText('Alpha Query')).toBeInTheDocument();
    });

    expect(screen.getByText('Beta View')).toBeInTheDocument();
    expect(screen.getByText('Gamma Scheduled')).toBeInTheDocument();
    expect(mockListBatchJobs).toHaveBeenCalledWith(1);
  });

  // -----------------------------------------------------------------------
  // Requirement 9.5: View Logs opens ConversionLogsPanel
  // -----------------------------------------------------------------------
  it('opens ConversionLogsPanel when View Logs is clicked on a job', async () => {
    mockGetJobLogs.mockResolvedValue([
      {
        id: 1,
        job_id: 10,
        timestamp: '2026-02-01T10:00:00Z',
        log_level: 'INFO',
        step_name: 'template_loaded',
        message: 'Template loaded successfully',
        duration_ms: 5,
      },
    ]);

    render(<BatchHistoryTable />);

    await waitFor(() => {
      expect(screen.getByText('#1')).toBeInTheDocument();
    });

    // Expand batch to see jobs
    await userEvent.click(screen.getByText('#1'));

    await waitFor(() => {
      expect(screen.getByText('Alpha Query')).toBeInTheDocument();
    });

    // Click View Logs on first job (skip batch-level View Logs buttons)
    const jobsTable = screen.getByLabelText('Jobs in batch 1');
    const jobViewLogsBtns = within(jobsTable).getAllByText('View Logs');
    await userEvent.click(jobViewLogsBtns[0]);

    // ConversionLogsPanel should open
    await waitFor(() => {
      expect(screen.getByText('Conversion Logs')).toBeInTheDocument();
    });

    expect(mockGetJobLogs).toHaveBeenCalledWith(10);
  });

  // -----------------------------------------------------------------------
  // Requirement 5.6: "Query" label for QUERY and SCHEDULED_QUERY
  // -----------------------------------------------------------------------
  it('displays "Query" label for QUERY and SCHEDULED_QUERY asset types in job details', async () => {
    render(<BatchHistoryTable />);

    await waitFor(() => {
      expect(screen.getByText('#1')).toBeInTheDocument();
    });

    // Expand batch
    await userEvent.click(screen.getByText('#1'));

    await waitFor(() => {
      expect(screen.getByText('Alpha Query')).toBeInTheDocument();
    });

    // Both QUERY (job 10) and SCHEDULED_QUERY (job 12) should show "Query"
    const queryLabels = screen.getAllByText('Query');
    expect(queryLabels.length).toBeGreaterThanOrEqual(2);

    // VIEW (job 11) should show "VIEW"
    expect(screen.getByText('VIEW')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Error state with retry
  // -----------------------------------------------------------------------
  it('shows error state with retry option if batch fetch fails', async () => {
    mockListBatches.mockRejectedValue(new Error('Network error'));

    render(<BatchHistoryTable />);

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });

    expect(screen.getByText('Retry')).toBeInTheDocument();

    // Click retry — should call listBatches again
    mockListBatches.mockResolvedValue(defaultBatchesResponse);
    await userEvent.click(screen.getByText('Retry'));

    await waitFor(() => {
      expect(screen.getByText('#1')).toBeInTheDocument();
    });

    // listBatches called twice: initial + retry
    expect(mockListBatches).toHaveBeenCalledTimes(2);
  });

  // -----------------------------------------------------------------------
  // Empty state
  // -----------------------------------------------------------------------
  it('shows empty state when no batches exist', async () => {
    mockListBatches.mockResolvedValue({ batches: [], total: 0 });

    render(<BatchHistoryTable />);

    await waitFor(() => {
      expect(screen.getByText(/no batch conversions yet/i)).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // Confirmation dialog cancel
  // -----------------------------------------------------------------------
  it('closes confirmation dialog when Cancel is clicked', async () => {
    render(<BatchHistoryTable />);

    await waitFor(() => {
      expect(screen.getByText('#1')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText('Manage History'));

    const checkboxes = screen.getAllByRole('checkbox');
    await userEvent.click(checkboxes[0]);

    await userEvent.click(screen.getByText('Delete Selected'));

    expect(screen.getByRole('dialog')).toBeInTheDocument();

    const dialog = screen.getByRole('dialog');
    await userEvent.click(within(dialog).getByText('Cancel'));

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    // Still in selection mode
    expect(screen.getAllByRole('checkbox')).toHaveLength(3);
  });
});
