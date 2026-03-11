/**
 * Tests for ValidationDetailPage
 * Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7, 14.8, 14.9, 14.10
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ValidationDetailPage } from '../ValidationDetailPage';
import type { ValidationReport, ValidationTableDetail } from '../../services/validationApi';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('../../services/validationApi', () => ({
  getValidationReport: vi.fn(),
  deleteValidationRun: vi.fn(),
}));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

import { getValidationReport, deleteValidationRun } from '../../services/validationApi';

const mockGetValidationReport = vi.mocked(getValidationReport);
const mockDeleteValidationRun = vi.mocked(deleteValidationRun);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const makeTableDetail = (overrides: Partial<ValidationTableDetail> = {}): ValidationTableDetail => ({
  id: 1,
  run_id: 5,
  table_name: 'users',
  dataset_name: 'my_dataset',
  ddl_status: 'passed',
  row_count_status: 'passed',
  data_match_status: 'passed',
  status: 'completed',
  error_message: null,
  started_at: '2026-03-11T10:00:00Z',
  completed_at: '2026-03-11T10:00:30Z',
  duration_seconds: 30,
  ddl_comparison_result: {
    discrepancies: [],
    source_column_count: 5,
    target_column_count: 5,
    columns_compared: 5,
  },
  row_count_result: {
    source_count: 1000,
    target_count: 1000,
    difference: 0,
    percentage_difference: 0,
  },
  data_match_result: {
    total_compared: 1000,
    matched_count: 1000,
    missing_count: 0,
    extra_count: 0,
    mismatch_count: 0,
    sample_discrepancies: [],
  },
  ai_analysis: null,
  ...overrides,
});

const makeReport = (overrides: Partial<ValidationReport> = {}): ValidationReport => ({
  run_id: 5,
  migration_id: 10,
  source_connection_name: 'BigQuery Prod',
  target_connection_name: 'Redshift Prod',
  overall_status: 'completed',
  total_tables: 2,
  tables_passed: 1,
  tables_failed: 1,
  tables_error: 0,
  started_at: '2026-03-11T10:00:00Z',
  completed_at: '2026-03-11T10:01:00Z',
  duration_seconds: 60,
  tables: [
    makeTableDetail({ table_name: 'users', ddl_status: 'passed', row_count_status: 'passed', data_match_status: 'passed' }),
    makeTableDetail({
      id: 2,
      table_name: 'orders',
      ddl_status: 'failed',
      row_count_status: 'failed',
      data_match_status: 'failed',
      status: 'completed',
      ddl_comparison_result: {
        discrepancies: [
          { type: 'type_mismatch', column_name: 'amount', source_type: 'NUMERIC', target_type: 'VARCHAR', expected_type: 'DECIMAL' },
        ],
        source_column_count: 4,
        target_column_count: 4,
        columns_compared: 4,
      },
      row_count_result: {
        source_count: 5000,
        target_count: 4998,
        difference: 2,
        percentage_difference: 0.04,
      },
      data_match_result: {
        total_compared: 5000,
        matched_count: 4995,
        missing_count: 2,
        extra_count: 0,
        mismatch_count: 3,
        sample_discrepancies: [
          { type: 'missing_in_target', primary_key: { id: 42 }, details: null },
          { type: 'value_mismatch', primary_key: { id: 99 }, details: { column: 'amount', source_value: '100.50', target_value: '100.5' } },
        ],
      },
      ai_analysis: {
        root_cause: 'Timestamp precision loss during AVRO export',
        impact_assessment: 'Affects 3 records with sub-millisecond timestamps',
        recommended_workarounds: [
          'Truncate source timestamps to microsecond precision before migration',
          'Apply post-migration UPDATE to fix affected records',
        ],
      },
    }),
  ],
  ...overrides,
});

function renderPage(runId = '5') {
  return render(
    <MemoryRouter initialEntries={[`/validations/${runId}`]}>
      <Routes>
        <Route path="/validations/:runId" element={<ValidationDetailPage />} />
      </Routes>
    </MemoryRouter>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ValidationDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetValidationReport.mockResolvedValue(makeReport());
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  // 1. Loading state renders spinner
  it('renders loading spinner while fetching', () => {
    mockGetValidationReport.mockReturnValue(new Promise(() => {}));
    renderPage();

    expect(screen.getByText(/loading validation run/i)).toBeInTheDocument();
    expect(document.querySelector('.validation-detail-spinner')).toBeInTheDocument();
  });

  // 2. Error state renders error message
  it('renders error message on API failure', async () => {
    mockGetValidationReport.mockRejectedValue(new Error('Network error'));
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
    expect(screen.getByText('Network error')).toHaveClass('validation-detail-error-text');
  });

  // 3. Renders run summary with correct data
  it('renders run summary with correct data', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/Validation Run #5/)).toBeInTheDocument();
    });

    // Status badge
    expect(screen.getByText('completed')).toBeInTheDocument();

    // Summary stat cards
    expect(screen.getByText('Total Tables')).toBeInTheDocument();
    expect(screen.getByText('Passed')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
    expect(screen.getByText('Errors')).toBeInTheDocument();
    expect(screen.getByText('Duration')).toBeInTheDocument();
    expect(screen.getByText('1m')).toBeInTheDocument(); // 60s = 1m
  });

  // 4. Table results list renders with status icons
  it('renders table results list with status icons', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('users')).toBeInTheDocument();
    });

    expect(screen.getByText('orders')).toBeInTheDocument();

    // Table headers
    expect(screen.getByText('Table Name')).toBeInTheDocument();
    expect(screen.getByText('DDL')).toBeInTheDocument();
    expect(screen.getByText('Row Count')).toBeInTheDocument();
    expect(screen.getByText('Data Match')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();

    // Status icons should be present (passed and failed)
    const passedIcons = screen.getAllByLabelText('Passed');
    expect(passedIcons.length).toBeGreaterThan(0);

    const failedIcons = screen.getAllByLabelText('Failed');
    expect(failedIcons.length).toBeGreaterThan(0);
  });

  // 5. Expanding a table row shows DDL, row count, and record match panels
  it('expanding a table row shows DDL, row count, and record match panels', async () => {
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('orders')).toBeInTheDocument();
    });

    // Click the orders row to expand
    await user.click(screen.getByText('orders'));

    // DDL section
    expect(screen.getByText('DDL Comparison')).toBeInTheDocument();
    expect(screen.getByText('type_mismatch')).toBeInTheDocument();
    expect(screen.getByText('amount')).toBeInTheDocument();

    // Row count section - use getAllByText since '5,000' appears in both row count and data match
    expect(screen.getByText('Source Count')).toBeInTheDocument();
    expect(screen.getByText('Target Count')).toBeInTheDocument();
    const fiveThousandElements = screen.getAllByText('5,000');
    expect(fiveThousandElements.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('4,998')).toBeInTheDocument();

    // Data match section
    expect(screen.getByText('Total Compared')).toBeInTheDocument();
    expect(screen.getByText('Matched')).toBeInTheDocument();
    expect(screen.getByText('Missing')).toBeInTheDocument();
  });

  // 6. AI Analysis section renders when available
  it('renders AI Analysis section for failed table with analysis', async () => {
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('orders')).toBeInTheDocument();
    });

    await user.click(screen.getByText('orders'));

    expect(screen.getByText('AI Analysis')).toBeInTheDocument();
    expect(screen.getByText('Root Cause')).toBeInTheDocument();
    expect(screen.getByText('Timestamp precision loss during AVRO export')).toBeInTheDocument();
    expect(screen.getByText('Impact Assessment')).toBeInTheDocument();
    expect(screen.getByText('Recommended Workarounds')).toBeInTheDocument();
    expect(screen.getByText('Truncate source timestamps to microsecond precision before migration')).toBeInTheDocument();
  });

  // 7. AI Analysis section does NOT render for passed table
  it('does not render AI Analysis section for passed table', async () => {
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('users')).toBeInTheDocument();
    });

    await user.click(screen.getByText('users'));

    // DDL section should appear but not AI Analysis
    expect(screen.getByText('DDL Comparison')).toBeInTheDocument();
    expect(screen.queryByText('AI Analysis')).not.toBeInTheDocument();
  });

  // 8. Download Report button triggers JSON download
  it('Download Report button triggers JSON download', async () => {
    const user = userEvent.setup();

    const createObjectURLMock = vi.fn().mockReturnValue('blob:mock-url');
    const revokeObjectURLMock = vi.fn();
    global.URL.createObjectURL = createObjectURLMock;
    global.URL.revokeObjectURL = revokeObjectURLMock;

    const clickMock = vi.fn();
    const origCreateElement = document.createElement.bind(document);
    vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
      if (tag === 'a') {
        const anchor = origCreateElement('a');
        anchor.click = clickMock;
        return anchor;
      }
      return origCreateElement(tag);
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Download Report')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Download Report'));

    expect(createObjectURLMock).toHaveBeenCalled();
    expect(clickMock).toHaveBeenCalled();
    expect(revokeObjectURLMock).toHaveBeenCalled();
  });

  // 9. Auto-refresh while status is 'running'
  it('auto-refreshes while status is running', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });

    const runningReport = makeReport({ overall_status: 'running' });
    mockGetValidationReport.mockResolvedValue(runningReport);

    await act(async () => {
      renderPage();
    });

    await waitFor(() => {
      expect(mockGetValidationReport).toHaveBeenCalledTimes(1);
    });

    // Advance past the 10s auto-refresh interval
    await act(async () => {
      vi.advanceTimersByTime(10_500);
    });

    await waitFor(() => {
      expect(mockGetValidationReport).toHaveBeenCalledTimes(2);
    });
  });

  // 10. No auto-refresh when status is 'completed'
  it('does not auto-refresh when status is completed', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });

    mockGetValidationReport.mockResolvedValue(makeReport({ overall_status: 'completed' }));

    await act(async () => {
      renderPage();
    });

    await waitFor(() => {
      expect(mockGetValidationReport).toHaveBeenCalledTimes(1);
    });

    await act(async () => {
      vi.advanceTimersByTime(15_000);
    });

    // Should still be 1 call — no refresh
    expect(mockGetValidationReport).toHaveBeenCalledTimes(1);
  });

  // 11. Delete button triggers confirmation and navigation
  it('delete button triggers confirmation and navigates on confirm', async () => {
    const user = userEvent.setup();
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    mockDeleteValidationRun.mockResolvedValue(undefined);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Delete')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Delete'));

    expect(confirmSpy).toHaveBeenCalledWith('Delete this validation run? This cannot be undone.');

    await waitFor(() => {
      expect(mockDeleteValidationRun).toHaveBeenCalledWith(5);
    });

    expect(mockNavigate).toHaveBeenCalledWith('/validations');
  });

  // 12. Delete cancelled when user declines confirmation
  it('does not delete when user cancels confirmation', async () => {
    const user = userEvent.setup();
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Delete')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Delete'));

    expect(confirmSpy).toHaveBeenCalled();
    expect(mockDeleteValidationRun).not.toHaveBeenCalled();
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  // 13. Progress bar visible when running
  it('shows progress bar when status is running', async () => {
    mockGetValidationReport.mockResolvedValue(
      makeReport({ overall_status: 'running', tables_passed: 1, tables_failed: 0, tables_error: 0, total_tables: 2 })
    );

    renderPage();

    await waitFor(() => {
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });
  });

  // 14. Progress bar hidden when completed
  it('hides progress bar when status is completed', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/Validation Run #5/)).toBeInTheDocument();
    });

    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });
});
