/**
 * Tests for ValidationDashboardPage
 * Covers: loading, empty, error states, runs table, status filter,
 * row navigation, new validation form toggle, delete, status badges,
 * pagination at bottom, no asterisks on labels, info pill tooltips,
 * per-table config table, sampling controls, bedrock info tooltip
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ValidationDashboardPage } from '../ValidationDashboardPage';
import type { ValidationRun } from '../../services/validationApi';

// Mocks
vi.mock('../../services/validationApi', () => ({
  listValidationRuns: vi.fn(),
  createValidationRun: vi.fn(),
  deleteValidationRun: vi.fn(),
  getMigrationInfo: vi.fn(),
  listValidationBedrockModels: vi.fn(),
  getValidationTableResults: vi.fn(),
}));

vi.mock('../../services/bqRedshiftApi', () => ({
  bqRedshiftApi: { listMigrations: vi.fn().mockResolvedValue([]) },
}));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

import {
  listValidationRuns,
  createValidationRun,
  deleteValidationRun,
  getMigrationInfo,
  listValidationBedrockModels,
} from '../../services/validationApi';
import { bqRedshiftApi } from '../../services/bqRedshiftApi';

const mockList = vi.mocked(listValidationRuns);
const mockCreate = vi.mocked(createValidationRun);
const mockDelete = vi.mocked(deleteValidationRun);
const mockGetMigInfo = vi.mocked(getMigrationInfo);
const mockListModels = vi.mocked(listValidationBedrockModels);
const mockListMigrations = vi.mocked(bqRedshiftApi.listMigrations);

const makeRun = (overrides: Partial<ValidationRun> = {}): ValidationRun => ({
  id: 1, workspace_id: 1, migration_id: 10,
  source_connection_id: 100, target_connection_id: 200,
  status: 'completed', progress_percentage: 100,
  tables_total: 3, tables_passed: 2, tables_failed: 1, tables_error: 0,
  started_at: '2026-03-11T10:00:00Z', completed_at: '2026-03-11T10:01:00Z',
  duration_seconds: 60, created_by: '1',
  created_at: '2026-03-11T10:00:00Z', updated_at: '2026-03-11T10:01:00Z',
  ...overrides,
});

function renderPage() {
  return render(<MemoryRouter><ValidationDashboardPage /></MemoryRouter>);
}

describe('ValidationDashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockList.mockResolvedValue({ runs: [], total: 0, page: 1, page_size: 20 });
    mockListModels.mockResolvedValue([]);
    mockListMigrations.mockResolvedValue([]);
  });

  // --- Loading / Empty / Error states ---

  it('renders loading state initially', () => {
    mockList.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByText(/loading validation runs/i)).toBeInTheDocument();
  });

  it('renders empty state when no runs', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/no validation runs found/i)).toBeInTheDocument();
    });
  });

  it('renders error state on API failure', async () => {
    mockList.mockRejectedValue(new Error('Network error'));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  // --- Runs table ---

  it('renders validation runs after loading', async () => {
    mockList.mockResolvedValue({
      runs: [makeRun({ id: 10 }), makeRun({ id: 20, status: 'failed' })],
      total: 2, page: 1, page_size: 20,
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('10')).toBeInTheDocument());
    expect(screen.getByText('20')).toBeInTheDocument();
    expect(screen.getByText('ID')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
  });

  it('status badges have correct CSS classes', async () => {
    mockList.mockResolvedValue({
      runs: [
        makeRun({ id: 1, status: 'completed' }),
        makeRun({ id: 2, status: 'failed' }),
        makeRun({ id: 3, status: 'running', progress_percentage: 50 }),
        makeRun({ id: 4, status: 'pending', progress_percentage: 0 }),
      ],
      total: 4, page: 1, page_size: 20,
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('completed')).toBeInTheDocument());
    expect(screen.getByText('completed')).toHaveClass('validation-status-badge', 'completed');
    expect(screen.getByText('failed')).toHaveClass('validation-status-badge', 'failed');
    expect(screen.getByText('running')).toHaveClass('validation-status-badge', 'running');
    expect(screen.getByText('pending')).toHaveClass('validation-status-badge', 'pending');
  });

  // --- Navigation ---

  it('clicking a row navigates to detail page', async () => {
    mockList.mockResolvedValue({
      runs: [makeRun({ id: 42 })], total: 1, page: 1, page_size: 20,
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('42')).toBeInTheDocument());
    await userEvent.click(screen.getByText('42'));
    expect(mockNavigate).toHaveBeenCalledWith('/validations/42');
  });

  // --- Status filter ---

  it('status filter triggers new API call', async () => {
    renderPage();
    await waitFor(() => expect(mockList).toHaveBeenCalledTimes(1));
    const filterSelect = screen.getByLabelText('Filter by status');
    await userEvent.selectOptions(filterSelect, 'completed');
    await waitFor(() => {
      expect(mockList).toHaveBeenCalledWith(1, 20, undefined, 'completed');
    });
  });

  // --- Delete ---

  it('delete button shows confirmation and deletes', async () => {
    mockList.mockResolvedValue({
      runs: [makeRun({ id: 5 })], total: 1, page: 1, page_size: 20,
    });
    mockDelete.mockResolvedValue(undefined);
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    renderPage();
    await waitFor(() => expect(screen.getByText('5')).toBeInTheDocument());
    await userEvent.click(screen.getByLabelText('Delete run 5'));
    expect(confirmSpy).toHaveBeenCalled();
    await waitFor(() => expect(mockDelete).toHaveBeenCalledWith(5));
    confirmSpy.mockRestore();
  });

  // --- Form toggle ---

  it('New Validation button toggles creation form', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('New Validation')).toBeInTheDocument());
    expect(screen.queryByText('New Validation Run')).not.toBeInTheDocument();
    await userEvent.click(screen.getByText('New Validation'));
    expect(screen.getByText('New Validation Run')).toBeInTheDocument();
    await userEvent.click(screen.getByText('New Validation'));
    expect(screen.queryByText('New Validation Run')).not.toBeInTheDocument();
  });

  // --- FIX 1: Pagination at bottom, not top ---

  it('pagination controls are at the bottom of the page, not in toolbar', async () => {
    mockList.mockResolvedValue({
      runs: [makeRun({ id: 1 })], total: 1, page: 1, page_size: 20,
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('1')).toBeInTheDocument());
    // Pagination should exist in bottom-pagination container
    const bottomPagination = document.querySelector('.validation-bottom-pagination');
    expect(bottomPagination).toBeInTheDocument();
    // Page size select should be inside bottom pagination
    const pageSizeSelect = screen.getByLabelText('Page size');
    expect(bottomPagination!.contains(pageSizeSelect)).toBe(true);
    // Toolbar right should be empty (no pagination there)
    const toolbarRight = document.querySelector('.validation-toolbar-right');
    expect(toolbarRight).toBeInTheDocument();
    expect(toolbarRight!.children.length).toBe(0);
  });

  // --- FIX 2: No asterisks on Migration / Tables labels ---

  it('Migration and Tables labels do not have asterisks', async () => {
    mockListMigrations.mockResolvedValue([
      { id: 1, migration_name: 'test-mig', source_type: 'bigquery', target_type: 'redshift' } as any,
    ]);
    mockGetMigInfo.mockResolvedValue({
      migration_id: 1, source_connection_id: 10, target_connection_id: 20,
      source_connection_name: 'src', target_connection_name: 'tgt',
      source_type: 'bigquery', target_type: 'redshift',
      tables: ['t1'], table_row_counts: { t1: 100 },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('New Validation')).toBeInTheDocument());
    await userEvent.click(screen.getByText('New Validation'));

    // Migration label should not contain asterisk
    const migLabel = screen.getByText('Migration');
    expect(migLabel.textContent).not.toContain('*');

    // Select migration to show tables
    const migSelect = screen.getByLabelText('Migration');
    await userEvent.selectOptions(migSelect, '1');

    await waitFor(() => {
      const tablesLabel = screen.getByText(/Tables/);
      expect(tablesLabel.textContent).not.toContain('*');
    });
  });

  // --- FIX 3: Info pill hover tooltips exist ---

  it('info pill tooltips use data-tooltip attribute for CSS hover', async () => {
    mockListMigrations.mockResolvedValue([
      { id: 1, migration_name: 'mig1' } as any,
    ]);
    mockGetMigInfo.mockResolvedValue({
      migration_id: 1, source_connection_id: 10, target_connection_id: 20,
      source_connection_name: 'src', target_connection_name: 'tgt',
      source_type: 'bigquery', target_type: 'redshift',
      tables: ['users'], table_row_counts: { users: 500 },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('New Validation')).toBeInTheDocument());
    await userEvent.click(screen.getByText('New Validation'));
    await userEvent.selectOptions(screen.getByLabelText('Migration'), '1');

    await waitFor(() => expect(screen.getByText('DDL')).toBeInTheDocument());

    // Check that info pills have data-tooltip attributes
    const ddlPill = screen.getByText('DDL').closest('.vtc-info-pill');
    expect(ddlPill).toBeInTheDocument();
    expect(ddlPill!.getAttribute('data-tooltip')).toContain('schema');

    const rowCountPill = screen.getByText('Row Count').closest('.vtc-info-pill');
    expect(rowCountPill).toBeInTheDocument();
    expect(rowCountPill!.getAttribute('data-tooltip')).toContain('rows');

    const dataMatchPill = screen.getByText('Data Match').closest('.vtc-info-pill');
    expect(dataMatchPill).toBeInTheDocument();
    expect(dataMatchPill!.getAttribute('data-tooltip')).toContain('comparison');
  });

  // --- FIX 4: Per-table config table with row counts, checkboxes, sampling ---

  it('per-table config shows HTML table with row counts and checkboxes', async () => {
    mockListMigrations.mockResolvedValue([
      { id: 1, migration_name: 'mig1' } as any,
    ]);
    mockGetMigInfo.mockResolvedValue({
      migration_id: 1, source_connection_id: 10, target_connection_id: 20,
      source_connection_name: 'src', target_connection_name: 'tgt',
      source_type: 'bigquery', target_type: 'redshift',
      tables: ['orders', 'users'], table_row_counts: { orders: 1500, users: 300 },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('New Validation')).toBeInTheDocument());
    await userEvent.click(screen.getByText('New Validation'));
    await userEvent.selectOptions(screen.getByLabelText('Migration'), '1');

    // Wait for table config to appear
    await waitFor(() => expect(screen.getByText('orders')).toBeInTheDocument());

    // Verify HTML table headers
    expect(screen.getByText('Total Rows')).toBeInTheDocument();
    expect(screen.getByText('Records to Validate')).toBeInTheDocument();

    // Verify row counts are displayed
    expect(screen.getByText('1,500')).toBeInTheDocument();
    expect(screen.getByText('300')).toBeInTheDocument();

    // Verify checkboxes exist (3 per table = 6 total in config table)
    const configTable = document.querySelector('.vtc-table');
    expect(configTable).toBeInTheDocument();
    const checkboxes = configTable!.querySelectorAll('input[type="checkbox"]');
    expect(checkboxes.length).toBe(6); // 3 checks x 2 tables

    // All checkboxes should be checked by default
    checkboxes.forEach((cb) => {
      expect((cb as HTMLInputElement).checked).toBe(true);
    });
  });

  it('sampling control has All button and number input per table', async () => {
    mockListMigrations.mockResolvedValue([
      { id: 1, migration_name: 'mig1' } as any,
    ]);
    mockGetMigInfo.mockResolvedValue({
      migration_id: 1, source_connection_id: 10, target_connection_id: 20,
      source_connection_name: 'src', target_connection_name: 'tgt',
      source_type: 'bigquery', target_type: 'redshift',
      tables: ['t1'], table_row_counts: { t1: 1000 },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('New Validation')).toBeInTheDocument());
    await userEvent.click(screen.getByText('New Validation'));
    await userEvent.selectOptions(screen.getByLabelText('Migration'), '1');

    await waitFor(() => expect(screen.getByText('t1')).toBeInTheDocument());

    // All button should be active by default
    const allBtn = screen.getByRole('button', { name: 'All' });
    expect(allBtn).toHaveClass('active');

    // Sample input should exist
    const sampleInput = screen.getByPlaceholderText('e.g. 5000');
    expect(sampleInput).toBeInTheDocument();
    expect((sampleInput as HTMLInputElement).value).toBe('');

    // Typing a number should deactivate All
    await userEvent.click(sampleInput);
    await userEvent.type(sampleInput, '500');
    expect(allBtn).not.toHaveClass('active');

    // Clicking All should clear the input
    await userEvent.click(allBtn);
    expect(allBtn).toHaveClass('active');
    expect((sampleInput as HTMLInputElement).value).toBe('');
  });

  // --- FIX 5: Bedrock model info tooltip ---

  it('Bedrock model section has info tooltip', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('New Validation')).toBeInTheDocument());
    await userEvent.click(screen.getByText('New Validation'));

    // Find the Info pill near Bedrock Model
    const infoPill = screen.getByText('Info').closest('.vtc-info-pill');
    expect(infoPill).toBeInTheDocument();
    expect(infoPill!.getAttribute('data-tooltip')).toContain('Bedrock');
    expect(infoPill!.getAttribute('data-tooltip')).toContain('AI model');
  });
});
