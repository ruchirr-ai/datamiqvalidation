/**
 * Tests for ValidationDashboardPage
 * Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7, 13.8, 13.9, 13.10
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ValidationDashboardPage } from '../ValidationDashboardPage';
import type { ValidationRun } from '../../services/validationApi';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('../../services/validationApi', () => ({
  listValidationRuns: vi.fn(),
  createValidationRun: vi.fn(),
  deleteValidationRun: vi.fn(),
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
} from '../../services/validationApi';

const mockListValidationRuns = vi.mocked(listValidationRuns);
const mockCreateValidationRun = vi.mocked(createValidationRun);
const mockDeleteValidationRun = vi.mocked(deleteValidationRun);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const makeRun = (overrides: Partial<ValidationRun> = {}): ValidationRun => ({
  id: 1,
  workspace_id: 1,
  migration_id: 10,
  source_connection_id: 100,
  target_connection_id: 200,
  status: 'completed',
  progress_percentage: 100,
  tables_total: 3,
  tables_passed: 2,
  tables_failed: 1,
  tables_error: 0,
  started_at: '2026-03-11T10:00:00Z',
  completed_at: '2026-03-11T10:01:00Z',
  duration_seconds: 60,
  created_by: '1',
  created_at: '2026-03-11T10:00:00Z',
  updated_at: '2026-03-11T10:01:00Z',
  ...overrides,
});

function renderPage() {
  return render(
    <MemoryRouter>
      <ValidationDashboardPage />
    </MemoryRouter>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ValidationDashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListValidationRuns.mockResolvedValue({
      runs: [],
      total: 0,
      page: 1,
      page_size: 20,
    });
  });

  // 1. Loading state
  it('renders loading state initially', () => {
    // Never resolve so loading stays visible
    mockListValidationRuns.mockReturnValue(new Promise(() => {}));
    renderPage();

    expect(screen.getByText(/loading validation runs/i)).toBeInTheDocument();
  });

  // 2. Renders runs after loading
  it('renders validation runs after loading', async () => {
    const runs = [
      makeRun({ id: 10, status: 'completed' }),
      makeRun({ id: 20, status: 'failed', tables_passed: 0, tables_failed: 3 }),
    ];
    mockListValidationRuns.mockResolvedValue({
      runs,
      total: 2,
      page: 1,
      page_size: 20,
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('10')).toBeInTheDocument();
    });
    expect(screen.getByText('20')).toBeInTheDocument();
    // Verify table headers rendered
    expect(screen.getByText('ID')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
    expect(mockListValidationRuns).toHaveBeenCalled();
  });

  // 3. Empty state
  it('renders empty state when no runs', async () => {
    mockListValidationRuns.mockResolvedValue({
      runs: [],
      total: 0,
      page: 1,
      page_size: 20,
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/no validation runs found/i)).toBeInTheDocument();
    });
  });

  // 4. Error state
  it('renders error state on API failure', async () => {
    mockListValidationRuns.mockRejectedValue(new Error('Network error'));

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  // 5. Status filter triggers new API call
  it('status filter changes trigger new API call', async () => {
    mockListValidationRuns.mockResolvedValue({
      runs: [],
      total: 0,
      page: 1,
      page_size: 20,
    });

    renderPage();

    await waitFor(() => {
      expect(mockListValidationRuns).toHaveBeenCalledTimes(1);
    });

    const filterSelect = screen.getByLabelText('Filter by status');
    await userEvent.selectOptions(filterSelect, 'completed');

    await waitFor(() => {
      expect(mockListValidationRuns).toHaveBeenCalledWith(1, 20, undefined, 'completed');
    });
  });

  // 6. Clicking a row navigates to detail page
  it('clicking a row navigates to detail page', async () => {
    mockListValidationRuns.mockResolvedValue({
      runs: [makeRun({ id: 42 })],
      total: 1,
      page: 1,
      page_size: 20,
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('42')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText('42'));

    expect(mockNavigate).toHaveBeenCalledWith('/validations/42');
  });

  // 7. New Validation button toggles creation form
  it('New Validation button toggles creation form', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('New Validation')).toBeInTheDocument();
    });

    // Form not visible initially
    expect(screen.queryByText('New Validation Run')).not.toBeInTheDocument();

    await userEvent.click(screen.getByText('New Validation'));

    expect(screen.getByText('New Validation Run')).toBeInTheDocument();

    // Toggle off
    await userEvent.click(screen.getByText('New Validation'));

    expect(screen.queryByText('New Validation Run')).not.toBeInTheDocument();
  });

  // 8. Creation form submits with valid data
  it('creation form submits with valid data', async () => {
    const createdRun = makeRun({ id: 99, status: 'pending' });
    mockCreateValidationRun.mockResolvedValue(createdRun);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('New Validation')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText('New Validation'));

    // Fill required fields
    await userEvent.type(screen.getByLabelText(/migration id/i), '10');
    await userEvent.type(screen.getByLabelText(/source connection id/i), '100');
    await userEvent.type(screen.getByLabelText(/target connection id/i), '200');

    await userEvent.click(screen.getByText('Create & Start'));

    await waitFor(() => {
      expect(mockCreateValidationRun).toHaveBeenCalledWith(
        expect.objectContaining({
          migration_id: 10,
          source_connection_id: 100,
          target_connection_id: 200,
        })
      );
    });
  });

  // 9. Delete button shows confirmation and deletes
  it('delete button shows confirmation and deletes', async () => {
    mockListValidationRuns.mockResolvedValue({
      runs: [makeRun({ id: 5 })],
      total: 1,
      page: 1,
      page_size: 20,
    });
    mockDeleteValidationRun.mockResolvedValue(undefined);

    // Mock window.confirm to return true
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('5')).toBeInTheDocument();
    });

    const deleteBtn = screen.getByLabelText('Delete run 5');
    await userEvent.click(deleteBtn);

    expect(confirmSpy).toHaveBeenCalled();
    await waitFor(() => {
      expect(mockDeleteValidationRun).toHaveBeenCalledWith(5);
    });

    confirmSpy.mockRestore();
  });

  // 10. Status badges have correct CSS classes
  it('renders status badges with correct classes', async () => {
    const runs = [
      makeRun({ id: 1, status: 'completed' }),
      makeRun({ id: 2, status: 'failed' }),
      makeRun({ id: 3, status: 'running', progress_percentage: 50 }),
      makeRun({ id: 4, status: 'pending', progress_percentage: 0 }),
    ];
    mockListValidationRuns.mockResolvedValue({
      runs,
      total: 4,
      page: 1,
      page_size: 20,
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('completed')).toBeInTheDocument();
    });

    const completedBadge = screen.getByText('completed');
    expect(completedBadge).toHaveClass('validation-status-badge', 'completed');

    const failedBadge = screen.getByText('failed');
    expect(failedBadge).toHaveClass('validation-status-badge', 'failed');

    const runningBadge = screen.getByText('running');
    expect(runningBadge).toHaveClass('validation-status-badge', 'running');

    const pendingBadge = screen.getByText('pending');
    expect(pendingBadge).toHaveClass('validation-status-badge', 'pending');
  });
});
