/**
 * Tests for BatchPreviewWindow component
 * Requirements: 11.2, 11.3, 11.5
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BatchPreviewWindow } from '../BatchPreviewWindow';
import { ConversionJob } from '../../../services/conversionApi';

const makeJob = (overrides: Partial<ConversionJob> = {}): ConversionJob => ({
  id: 1,
  workspace_id: 1,
  batch_id: 100,
  source_code: 'SELECT 1',
  target_code: 'SELECT 1 -- converted',
  source_dialect: 'Bigquery',
  target_dialect: 'Redshift',
  asset_type: 'QUERY',
  asset_name: 'Test Query',
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
  makeJob({ id: 1, asset_name: 'Query A', status: 'completed' }),
  makeJob({ id: 2, asset_name: 'Query B', status: 'failed', error_message: 'Timeout', target_code: null }),
  makeJob({ id: 3, asset_name: 'Query C', status: 'completed' }),
];

describe('BatchPreviewWindow', () => {
  it('renders all jobs with correct columns', () => {
    render(<BatchPreviewWindow jobs={sampleJobs} />);

    expect(screen.getByText('Query A')).toBeInTheDocument();
    expect(screen.getByText('Query B')).toBeInTheDocument();
    expect(screen.getByText('Query C')).toBeInTheDocument();
    // Status badges
    expect(screen.getAllByText('completed')).toHaveLength(2);
    expect(screen.getByText('failed')).toBeInTheDocument();
  });

  it('shows Preview button for completed jobs and error for failed', () => {
    render(<BatchPreviewWindow jobs={sampleJobs} />);

    const previewBtns = screen.getAllByText('Preview');
    expect(previewBtns).toHaveLength(2); // 2 completed jobs

    expect(screen.getByText('Timeout')).toBeInTheDocument(); // failed job error
  });

  it('expands side-by-side view on Preview click', async () => {
    render(<BatchPreviewWindow jobs={sampleJobs} />);

    const previewBtns = screen.getAllByText('Preview');
    await userEvent.click(previewBtns[0]);

    expect(screen.getByText('Source')).toBeInTheDocument();
    expect(screen.getByText('Target')).toBeInTheDocument();
    expect(screen.getByText('SELECT 1')).toBeInTheDocument();
    expect(screen.getByText('SELECT 1 -- converted')).toBeInTheDocument();
  });

  it('collapses one preview when opening another', async () => {
    render(<BatchPreviewWindow jobs={sampleJobs} />);

    const previewBtns = screen.getAllByText('Preview');
    await userEvent.click(previewBtns[0]); // expand first

    expect(screen.getByText('Source')).toBeInTheDocument();

    // Click second preview — first should collapse
    // After first click, first button becomes "Hide", second is still "Preview"
    const secondPreview = screen.getByText('Preview'); // only one left
    await userEvent.click(secondPreview);

    // Should still have exactly one Source/Target pair (the second job)
    expect(screen.getAllByText('Source')).toHaveLength(1);
    expect(screen.getAllByText('Target')).toHaveLength(1);
  });
});
