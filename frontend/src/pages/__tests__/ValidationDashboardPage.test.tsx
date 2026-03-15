/**
 * Tests for ValidationDashboardPage
 * Covers: loading, empty, error states, runs table, status filter,
 * row navigation, new validation form toggle, delete, status badges,
 * pagination at bottom, no asterisks on labels, info pill tooltips,
 * per-table config table, sampling controls, bedrock info tooltip
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ValidationDashboardPage, formatTableSummary } from '../ValidationDashboardPage';
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

// Mock LanguageContext to return English translations
vi.mock('../../contexts/LanguageContext', () => {
  const translations: Record<string, string> = {
    'validation.subtitle': 'Post-migration data integrity verification',
    'validation.passed': 'Passed', 'validation.failed': 'Failed', 'validation.active': 'Active',
    'validation.newValidation': 'New Validation', 'validation.createStart': 'Create & Start',
    'validation.newRun': 'New Validation Run', 'validation.migration': 'Migration',
    'validation.selectMigration': 'Select a migration', 'validation.tables': 'Tables',
    'validation.selectTables': 'Select tables...', 'validation.allTablesSelected': 'All tables selected',
    'validation.selectAll': 'Select All', 'validation.checksPerTable': 'Validation Checks per Table',
    'validation.totalRows': 'Total Rows', 'validation.recordsToValidate': 'Records to Validate',
    'validation.bedrockModel': 'Bedrock Model (optional)', 'validation.noneSkipAi': 'None (skip AI analysis)',
    'validation.loadingModels': 'Loading models...', 'validation.loadingMigration': 'Loading migration details...',
    'validation.creating': 'Creating…', 'validation.loading': 'Loading validation runs...',
    'validation.noRunsDesc': 'No validation runs found. Click "New Validation" to get started.',
    'validation.id': 'ID', 'validation.progress': 'Progress', 'validation.started': 'Started',
    'validation.duration': 'Duration', 'validation.actions': 'Actions',
    'jobs.status': 'Status', 'common.cancel': 'Cancel', 'taskHistory.table': 'Table',
  };
  return {
    useLanguage: () => ({
      language: 'en',
      setLanguage: () => {},
      t: (key: string) => translations[key] || key,
    }),
  };
});

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
  getValidationTableResults,
} from '../../services/validationApi';
import { bqRedshiftApi } from '../../services/bqRedshiftApi';

const mockList = vi.mocked(listValidationRuns);
const mockCreate = vi.mocked(createValidationRun);
const mockDelete = vi.mocked(deleteValidationRun);
const mockGetMigInfo = vi.mocked(getMigrationInfo);
const mockListModels = vi.mocked(listValidationBedrockModels);
const mockListMigrations = vi.mocked(bqRedshiftApi.listMigrations);
const mockGetTableResults = vi.mocked(getValidationTableResults);

const makeRun = (overrides: Partial<ValidationRun> = {}): ValidationRun => ({
  id: 1, workspace_id: 1, migration_id: 10,
  source_connection_id: 100, target_connection_id: 200,
  status: 'completed', progress_percentage: 100,
  tables_total: 3, tables_passed: 2, tables_failed: 1, tables_error: 0,
  started_at: '2026-03-11T10:00:00Z', completed_at: '2026-03-11T10:01:00Z',
  duration_seconds: 60, created_by: '1',
  created_at: '2026-03-11T10:00:00Z', updated_at: '2026-03-11T10:01:00Z',
  run_name: null,
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
    await waitFor(() => expect(screen.getByText('Run #10')).toBeInTheDocument());
    expect(screen.getByText('Run #20')).toBeInTheDocument();
    expect(screen.getByText('Name')).toBeInTheDocument();
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
    await waitFor(() => expect(screen.getByText('Run #42')).toBeInTheDocument());
    await userEvent.click(screen.getByText('Run #42'));
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
    await waitFor(() => expect(screen.getByText('Run #5')).toBeInTheDocument());
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
    await waitFor(() => expect(screen.getByText('Run #1')).toBeInTheDocument());
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
      migration_name: 'test-mig',
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

  it('info pill tooltips show tooltip content on hover', async () => {
    mockListMigrations.mockResolvedValue([
      { id: 1, migration_name: 'mig1' } as any,
    ]);
    mockGetMigInfo.mockResolvedValue({
      migration_id: 1, source_connection_id: 10, target_connection_id: 20,
      source_connection_name: 'src', target_connection_name: 'tgt',
      migration_name: 'mig1',
      tables: ['users'], table_row_counts: { users: 500 },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('New Validation')).toBeInTheDocument());
    await userEvent.click(screen.getByText('New Validation'));
    await userEvent.selectOptions(screen.getByLabelText('Migration'), '1');

    await waitFor(() => expect(screen.getByText('Validation Checks per Table')).toBeInTheDocument());

    // Check that info pills have tooltip child spans with relevant content
    const infoPills = document.querySelectorAll('.vtc-info-pill');
    // Find DDL pill (first info pill)
    const ddlPill = Array.from(infoPills).find(el => el.textContent?.includes('DDL') && el.querySelector('.vtc-tooltip'));
    expect(ddlPill).toBeTruthy();
    expect(ddlPill!.querySelector('.vtc-tooltip')!.textContent).toContain('schema');

    const rowCountPill = Array.from(infoPills).find(el => el.textContent?.includes('Row Count') && el.querySelector('.vtc-tooltip'));
    expect(rowCountPill).toBeTruthy();
    expect(rowCountPill!.querySelector('.vtc-tooltip')!.textContent).toContain('rows');

    const dataMatchPill = Array.from(infoPills).find(el => el.textContent?.includes('Data Match') && el.querySelector('.vtc-tooltip'));
    expect(dataMatchPill).toBeTruthy();
    expect(dataMatchPill!.querySelector('.vtc-tooltip')!.textContent).toContain('comparison');
  });

  // --- FIX 4: Per-table config table with row counts, checkboxes, sampling ---

  it('per-table config shows HTML table with row counts and checkboxes', async () => {
    mockListMigrations.mockResolvedValue([
      { id: 1, migration_name: 'mig1' } as any,
    ]);
    mockGetMigInfo.mockResolvedValue({
      migration_id: 1, source_connection_id: 10, target_connection_id: 20,
      source_connection_name: 'src', target_connection_name: 'tgt',
      migration_name: 'mig1',
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
      migration_name: 'mig1',
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

  // --- Run Name input in create form ---

  it('create form includes optional Run Name text input before migration selector', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('New Validation')).toBeInTheDocument());
    await userEvent.click(screen.getByText('New Validation'));

    const runNameInput = screen.getByLabelText('Run Name');
    expect(runNameInput).toBeInTheDocument();
    expect(runNameInput).toHaveAttribute('type', 'text');
    expect(runNameInput).toHaveAttribute('maxLength', '255');
    expect((runNameInput as HTMLInputElement).value).toBe('');
  });

  it('run_name is included in create payload when provided', async () => {
    mockListMigrations.mockResolvedValue([
      { id: 1, migration_name: 'mig1' } as any,
    ]);
    mockGetMigInfo.mockResolvedValue({
      migration_id: 1, source_connection_id: 10, target_connection_id: 20,
      source_connection_name: 'src', target_connection_name: 'tgt',
      migration_name: 'mig1',
      tables: ['t1'], table_row_counts: { t1: 100 },
    });
    mockCreate.mockResolvedValue(makeRun());
    renderPage();
    await waitFor(() => expect(screen.getByText('New Validation')).toBeInTheDocument());
    await userEvent.click(screen.getByText('New Validation'));

    // Type a run name
    const runNameInput = screen.getByLabelText('Run Name');
    await userEvent.type(runNameInput, 'Pre-release check');

    // Select migration
    await userEvent.selectOptions(screen.getByLabelText('Migration'), '1');
    await waitFor(() => expect(screen.getByText('t1')).toBeInTheDocument());

    // Submit
    await userEvent.click(screen.getByText('Create & Start'));
    await waitFor(() => expect(mockCreate).toHaveBeenCalledTimes(1));
    expect(mockCreate.mock.calls[0][0].run_name).toBe('Pre-release check');
  });

  it('run_name is omitted from create payload when empty', async () => {
    mockListMigrations.mockResolvedValue([
      { id: 1, migration_name: 'mig1' } as any,
    ]);
    mockGetMigInfo.mockResolvedValue({
      migration_id: 1, source_connection_id: 10, target_connection_id: 20,
      source_connection_name: 'src', target_connection_name: 'tgt',
      migration_name: 'mig1',
      tables: ['t1'], table_row_counts: { t1: 100 },
    });
    mockCreate.mockResolvedValue(makeRun());
    renderPage();
    await waitFor(() => expect(screen.getByText('New Validation')).toBeInTheDocument());
    await userEvent.click(screen.getByText('New Validation'));

    // Select migration without typing run name
    await userEvent.selectOptions(screen.getByLabelText('Migration'), '1');
    await waitFor(() => expect(screen.getByText('t1')).toBeInTheDocument());

    // Submit
    await userEvent.click(screen.getByText('Create & Start'));
    await waitFor(() => expect(mockCreate).toHaveBeenCalledTimes(1));
    expect(mockCreate.mock.calls[0][0].run_name).toBeUndefined();
  });

  // --- FIX 5: Bedrock model info tooltip ---

  it('Bedrock model section has info tooltip', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('New Validation')).toBeInTheDocument());
    await userEvent.click(screen.getByText('New Validation'));

    // Find the Info pill near Bedrock Model
    const infoPill = screen.getByText('Info').closest('.vtc-info-pill');
    expect(infoPill).toBeInTheDocument();
    const tooltip = infoPill!.querySelector('.vtc-tooltip');
    expect(tooltip).toBeInTheDocument();
    expect(tooltip!.textContent).toContain('Bedrock');
    expect(tooltip!.textContent).toContain('AI model');
  });

  // --- Task 5: Run naming and table column redesign ---

  it('renders run_name as primary identifier when available', async () => {
    mockList.mockResolvedValue({
      runs: [
        makeRun({ id: 10, run_name: 'Pre-release check' }),
        makeRun({ id: 20, run_name: 'Nightly validation' }),
      ],
      total: 2, page: 1, page_size: 20,
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('Pre-release check')).toBeInTheDocument());
    expect(screen.getByText('Nightly validation')).toBeInTheDocument();
    // Should NOT show "Run #10" or "Run #20" since run_name is set
    expect(screen.queryByText('Run #10')).not.toBeInTheDocument();
    expect(screen.queryByText('Run #20')).not.toBeInTheDocument();
  });

  it('renders "Run #id" fallback when run_name is null', async () => {
    mockList.mockResolvedValue({
      runs: [
        makeRun({ id: 15, run_name: null }),
        makeRun({ id: 25, run_name: '' }),
      ],
      total: 2, page: 1, page_size: 20,
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('Run #15')).toBeInTheDocument());
    // Empty string is falsy, so should also fall back
    expect(screen.getByText('Run #25')).toBeInTheDocument();
  });

  it('human-readable table summary renders correct counts with colors', async () => {
    mockList.mockResolvedValue({
      runs: [makeRun({ id: 1, tables_passed: 3, tables_failed: 1, tables_error: 2 })],
      total: 1, page: 1, page_size: 20,
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('3 Passed')).toBeInTheDocument());
    expect(screen.getByText('1 Failed')).toBeInTheDocument();
    expect(screen.getByText('2 Errors')).toBeInTheDocument();

    // Verify color classes
    expect(screen.getByText('3 Passed')).toHaveClass('summary-passed');
    expect(screen.getByText('1 Failed')).toHaveClass('summary-failed');
    expect(screen.getByText('2 Errors')).toHaveClass('summary-error');
  });

  it('table summary omits zero-count categories', async () => {
    mockList.mockResolvedValue({
      runs: [makeRun({ id: 1, tables_passed: 5, tables_failed: 0, tables_error: 0 })],
      total: 1, page: 1, page_size: 20,
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('5 Passed')).toBeInTheDocument());
    // Zero-count categories should not appear in the summary
    expect(document.querySelector('.summary-failed')).not.toBeInTheDocument();
    expect(document.querySelector('.summary-error')).not.toBeInTheDocument();
  });

  it('table summary shows dash when all counts are zero', async () => {
    mockList.mockResolvedValue({
      runs: [makeRun({ id: 1, tables_passed: 0, tables_failed: 0, tables_error: 0 })],
      total: 1, page: 1, page_size: 20,
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('Run #1')).toBeInTheDocument());
    const dashEl = document.querySelector('.summary-none');
    expect(dashEl).toBeInTheDocument();
    expect(dashEl!.textContent).toBe('—');
  });

  it('table has Name column header and chevron column', async () => {
    mockList.mockResolvedValue({
      runs: [makeRun({ id: 1 })],
      total: 1, page: 1, page_size: 20,
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('Name')).toBeInTheDocument());
    // Chevron placeholder should exist
    const chevron = document.querySelector('.validation-chevron-btn');
    expect(chevron).toBeInTheDocument();
  });
});

// --- formatTableSummary unit tests ---

describe('formatTableSummary', () => {
  it('renders all categories when all non-zero', () => {
    const { container } = render(formatTableSummary(2, 1, 3));
    expect(container.querySelector('.summary-passed')!.textContent).toBe('2 Passed');
    expect(container.querySelector('.summary-failed')!.textContent).toBe('1 Failed');
    expect(container.querySelector('.summary-error')!.textContent).toBe('3 Errors');
  });

  it('omits zero-count categories', () => {
    const { container } = render(formatTableSummary(4, 0, 0));
    expect(container.querySelector('.summary-passed')!.textContent).toBe('4 Passed');
    expect(container.querySelector('.summary-failed')).toBeNull();
    expect(container.querySelector('.summary-error')).toBeNull();
  });

  it('renders dash when all counts are zero', () => {
    const { container } = render(formatTableSummary(0, 0, 0));
    expect(container.querySelector('.summary-none')!.textContent).toBe('—');
  });

  it('renders only failed and errors when passed is zero', () => {
    const { container } = render(formatTableSummary(0, 2, 1));
    expect(container.querySelector('.summary-passed')).toBeNull();
    expect(container.querySelector('.summary-failed')!.textContent).toBe('2 Failed');
    expect(container.querySelector('.summary-error')!.textContent).toBe('1 Errors');
  });
});

// --- Task 6: Expandable rows and navigation tests ---

const mockTableResults = [
  {
    id: 101, run_id: 1, table_name: 'users', dataset_name: null,
    ddl_status: 'passed', row_count_status: 'passed', data_match_status: 'failed',
    status: 'failed', error_message: null, started_at: null, completed_at: null, duration_seconds: null,
  },
  {
    id: 102, run_id: 1, table_name: 'orders', dataset_name: null,
    ddl_status: 'passed', row_count_status: 'passed', data_match_status: 'passed',
    status: 'completed', error_message: null, started_at: null, completed_at: null, duration_seconds: null,
  },
];

describe('Expandable rows and navigation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockList.mockResolvedValue({
      runs: [makeRun({ id: 1 }), makeRun({ id: 2, status: 'failed' })],
      total: 2, page: 1, page_size: 20,
    });
    mockListModels.mockResolvedValue([]);
    mockListMigrations.mockResolvedValue([]);
    mockGetTableResults.mockResolvedValue(mockTableResults);
  });

  it('chevron click expands row and shows nested table with correct data', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('Run #1')).toBeInTheDocument());

    const chevron = screen.getByLabelText('Expand run 1');
    await userEvent.click(chevron);

    await waitFor(() => expect(screen.getByText('users')).toBeInTheDocument());
    expect(screen.getByText('orders')).toBeInTheDocument();
    // Verify nested table headers
    expect(screen.getByText('Table Name')).toBeInTheDocument();
    expect(screen.getByText('Overall')).toBeInTheDocument();
    // Verify API was called
    expect(mockGetTableResults).toHaveBeenCalledWith(1);
  });

  it('chevron click on expanded row collapses it', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('Run #1')).toBeInTheDocument());

    const chevron = screen.getByLabelText('Expand run 1');
    await userEvent.click(chevron);
    await waitFor(() => expect(screen.getByText('users')).toBeInTheDocument());

    // Click again to collapse
    await userEvent.click(chevron);
    await waitFor(() => expect(screen.queryByText('Table Name')).not.toBeInTheDocument());
  });

  it('chevron click does NOT trigger navigation', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('Run #1')).toBeInTheDocument());

    const chevron = screen.getByLabelText('Expand run 1');
    await userEvent.click(chevron);

    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('row click (outside chevron/actions) navigates to detail page', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('Run #1')).toBeInTheDocument());

    // Click on the run name cell (not chevron or actions)
    await userEvent.click(screen.getByText('Run #1'));
    expect(mockNavigate).toHaveBeenCalledWith('/validations/1');
  });

  it('delete button click does NOT navigate', async () => {
    mockDelete.mockResolvedValue(undefined);
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    renderPage();
    await waitFor(() => expect(screen.getByText('Run #1')).toBeInTheDocument());

    await userEvent.click(screen.getByLabelText('Delete run 1'));
    expect(mockNavigate).not.toHaveBeenCalled();
    vi.restoreAllMocks();
  });

  it('loading spinner shows while fetching table results', async () => {
    // Make the API call hang
    mockGetTableResults.mockReturnValue(new Promise(() => {}));
    renderPage();
    await waitFor(() => expect(screen.getByText('Run #1')).toBeInTheDocument());

    await userEvent.click(screen.getByLabelText('Expand run 1'));
    await waitFor(() => expect(screen.getByText('Loading table results...')).toBeInTheDocument());
  });

  it('error message with retry shows on fetch failure', async () => {
    mockGetTableResults.mockRejectedValue(new Error('Network error'));
    renderPage();
    await waitFor(() => expect(screen.getByText('Run #1')).toBeInTheDocument());

    await userEvent.click(screen.getByLabelText('Expand run 1'));
    await waitFor(() => expect(screen.getByText('Network error')).toBeInTheDocument());
    expect(screen.getByText('Retry')).toBeInTheDocument();
  });

  it('retry button re-fetches table results', async () => {
    mockGetTableResults.mockRejectedValueOnce(new Error('Network error'));
    renderPage();
    await waitFor(() => expect(screen.getByText('Run #1')).toBeInTheDocument());

    await userEvent.click(screen.getByLabelText('Expand run 1'));
    await waitFor(() => expect(screen.getByText('Retry')).toBeInTheDocument());

    // Now make it succeed on retry
    mockGetTableResults.mockResolvedValueOnce(mockTableResults);
    await userEvent.click(screen.getByText('Retry'));
    await waitFor(() => expect(screen.getByText('users')).toBeInTheDocument());
  });

  it('re-expanding a previously expanded row uses cached data (no redundant API call)', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('Run #1')).toBeInTheDocument());

    // Expand
    await userEvent.click(screen.getByLabelText('Expand run 1'));
    await waitFor(() => expect(screen.getByText('users')).toBeInTheDocument());
    expect(mockGetTableResults).toHaveBeenCalledTimes(1);

    // Collapse
    await userEvent.click(screen.getByLabelText('Expand run 1'));
    await waitFor(() => expect(screen.queryByText('Table Name')).not.toBeInTheDocument());

    // Re-expand — should NOT call API again
    await userEvent.click(screen.getByLabelText('Expand run 1'));
    await waitFor(() => expect(screen.getByText('users')).toBeInTheDocument());
    expect(mockGetTableResults).toHaveBeenCalledTimes(1); // Still 1, cached
  });

  it('keyboard activation (Enter) on chevron expands row', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('Run #1')).toBeInTheDocument());

    const chevron = screen.getByLabelText('Expand run 1');
    chevron.focus();
    await userEvent.keyboard('{Enter}');

    await waitFor(() => expect(screen.getByText('users')).toBeInTheDocument());
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('keyboard activation (Space) on chevron expands row', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('Run #1')).toBeInTheDocument());

    const chevron = screen.getByLabelText('Expand run 1');
    chevron.focus();
    await userEvent.keyboard(' ');

    await waitFor(() => expect(screen.getByText('users')).toBeInTheDocument());
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('chevron has aria-expanded attribute', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('Run #1')).toBeInTheDocument());

    const chevron = screen.getByLabelText('Expand run 1');
    expect(chevron).toHaveAttribute('aria-expanded', 'false');

    await userEvent.click(chevron);
    await waitFor(() => expect(chevron).toHaveAttribute('aria-expanded', 'true'));
  });
});
