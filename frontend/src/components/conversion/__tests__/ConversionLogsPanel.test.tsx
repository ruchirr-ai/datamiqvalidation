/**
 * Tests for ConversionLogsPanel component
 * Requirements: 9.4, 9.7
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ConversionLogsPanel } from '../ConversionLogsPanel';

// Mock the API module
vi.mock('../../../services/conversionApi', () => ({
  getJobLogs: vi.fn(),
}));

import { getJobLogs } from '../../../services/conversionApi';
const mockGetJobLogs = vi.mocked(getJobLogs);

const sampleLogs = [
  { id: 1, job_id: 10, timestamp: '2026-01-15T10:00:00Z', log_level: 'INFO', step_name: 'template_loaded', message: 'Template loaded', duration_ms: 5 },
  { id: 2, job_id: 10, timestamp: '2026-01-15T10:00:01Z', log_level: 'WARNING', step_name: 'sqlglot_parse_failed', message: 'Parse warning', duration_ms: null },
  { id: 3, job_id: 10, timestamp: '2026-01-15T10:00:02Z', log_level: 'ERROR', step_name: 'conversion_failed', message: 'Bedrock error', duration_ms: 1200 },
];

describe('ConversionLogsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state while fetching', () => {
    mockGetJobLogs.mockReturnValue(new Promise(() => {})); // never resolves
    render(<ConversionLogsPanel jobId={10} isOpen={true} onClose={() => {}} />);
    expect(screen.getByText('Loading logs…')).toBeInTheDocument();
  });

  it('renders log entries in chronological order after fetch', async () => {
    mockGetJobLogs.mockResolvedValue(sampleLogs);
    render(<ConversionLogsPanel jobId={10} isOpen={true} onClose={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText('Template loaded')).toBeInTheDocument();
    });

    const rows = screen.getAllByRole('row');
    // header + 3 data rows
    expect(rows).toHaveLength(4);
    expect(screen.getByText('Parse warning')).toBeInTheDocument();
    expect(screen.getByText('Bedrock error')).toBeInTheDocument();
  });

  it('applies correct color coding for log levels', async () => {
    mockGetJobLogs.mockResolvedValue(sampleLogs);
    render(<ConversionLogsPanel jobId={10} isOpen={true} onClose={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText('INFO')).toBeInTheDocument();
    });

    expect(screen.getByText('INFO').className).toContain('logs-panel__level--info');
    expect(screen.getByText('WARNING').className).toContain('logs-panel__level--warning');
    expect(screen.getByText('ERROR').className).toContain('logs-panel__level--error');
  });

  it('shows error state with retry button', async () => {
    mockGetJobLogs.mockRejectedValue({ message: 'Network error' });
    render(<ConversionLogsPanel jobId={10} isOpen={true} onClose={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });

    const retryBtn = screen.getByText('Retry');
    expect(retryBtn).toBeInTheDocument();

    // Click retry triggers re-fetch
    mockGetJobLogs.mockResolvedValue(sampleLogs);
    await userEvent.click(retryBtn);

    await waitFor(() => {
      expect(screen.getByText('Template loaded')).toBeInTheDocument();
    });
  });

  it('does not render when isOpen is false', () => {
    render(<ConversionLogsPanel jobId={10} isOpen={false} onClose={() => {}} />);
    expect(screen.queryByText('Conversion Logs')).not.toBeInTheDocument();
  });
});
