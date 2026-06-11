/**
 * Tests for IcebergCostAnalysisTab
 * Covers: cost analysis rendering, growth rate adjustment, recalculation,
 * TCO comparison, projections display.
 * Requirements: 13.1, 13.5
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { IcebergCostAnalysisTab } from '../IcebergCostAnalysisTab';
import type { CostAnalysisReport } from '../../../types/bqIceberg';

// Mock the API
vi.mock('../../../services/bqIcebergApi', () => ({
  bqIcebergApi: {
    getCostAnalysis: vi.fn(),
    recalculateCost: vi.fn(),
  },
}));

import { bqIcebergApi } from '../../../services/bqIcebergApi';

const mockGetCost = vi.mocked(bqIcebergApi.getCostAnalysis);
const mockRecalculate = vi.mocked(bqIcebergApi.recalculateCost);

// Sample cost analysis data
const sampleCostReport: CostAnalysisReport = {
  migration_id: 1,
  destination_type: 'iceberg_s3',
  data_size_bytes: 1073741824, // 1 GB
  table_count: 5,
  setup_costs: {
    s3_storage_initial: 0.023,
    glue_api_calls: 0.005,
    data_transfer: 0.09,
    total: 0.118,
  },
  recurring_costs: {
    s3_storage_monthly: 0.023,
    glue_catalog_monthly: 0.001,
    athena_queries_monthly: 0.05,
    total_monthly: 0.074,
  },
  projections_optimistic: {
    month_3: 0.21,
    month_6: 0.45,
    month_12: 1.02,
  },
  projections_conservative: {
    month_3: 0.35,
    month_6: 0.75,
    month_12: 1.70,
  },
  tco_comparison: {
    bigquery_monthly: 5.0,
    iceberg_monthly: 0.074,
    savings_monthly: 4.926,
    savings_percentage: 98.5,
  },
  growth_rate_monthly: 0.05,
  compression_ratio_optimistic: 5.0,
  compression_ratio_conservative: 3.0,
  generated_at: '2026-01-25T10:00:00Z',
};

describe('IcebergCostAnalysisTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetCost.mockResolvedValue(sampleCostReport);
  });

  // --- Loading and Error States ---

  it('renders loading state initially', () => {
    mockGetCost.mockReturnValue(new Promise(() => {}));
    render(<IcebergCostAnalysisTab migrationId={1} />);
    expect(screen.getByText('Loading cost analysis...')).toBeInTheDocument();
  });

  it('renders error state on API failure', async () => {
    mockGetCost.mockRejectedValue(new Error('Service unavailable'));
    render(<IcebergCostAnalysisTab migrationId={1} />);
    await waitFor(() => {
      expect(screen.getByText('Service unavailable')).toBeInTheDocument();
    });
  });

  // --- Cost Analysis Rendering ---

  it('renders title and subtitle with table count and data size', async () => {
    render(<IcebergCostAnalysisTab migrationId={1} />);
    await waitFor(() => {
      expect(screen.getByText('Cost Analysis')).toBeInTheDocument();
    });
    expect(screen.getByText(/5 tables/)).toBeInTheDocument();
    expect(screen.getByText(/1 GB/)).toBeInTheDocument();
    expect(screen.getByText(/Apache Iceberg on S3/)).toBeInTheDocument();
  });

  it('renders S3 Tables destination type correctly', async () => {
    mockGetCost.mockResolvedValue({
      ...sampleCostReport,
      destination_type: 'iceberg_s3_tables',
      recurring_costs: {
        ...sampleCostReport.recurring_costs,
        s3_tables_monthly: 0.028,
      },
    });
    render(<IcebergCostAnalysisTab migrationId={1} />);
    await waitFor(() => {
      expect(screen.getByText(/AWS S3 Tables/)).toBeInTheDocument();
    });
    expect(screen.getByText('S3 Tables Premium')).toBeInTheDocument();
  });

  // --- Setup Costs ---

  it('displays setup costs section', async () => {
    render(<IcebergCostAnalysisTab migrationId={1} />);
    await waitFor(() => {
      expect(screen.getByText('One-Time Setup Costs')).toBeInTheDocument();
    });
    expect(screen.getByText('S3 Storage (Initial)')).toBeInTheDocument();
    expect(screen.getByText('Glue API Calls')).toBeInTheDocument();
    expect(screen.getByText('Data Transfer')).toBeInTheDocument();
    expect(screen.getByText('Total Setup')).toBeInTheDocument();
  });

  it('displays formatted setup cost values', async () => {
    render(<IcebergCostAnalysisTab migrationId={1} />);
    await waitFor(() => {
      expect(screen.getByText('$0.12')).toBeInTheDocument(); // total rounded
    });
  });

  // --- Recurring Costs ---

  it('displays recurring costs section', async () => {
    render(<IcebergCostAnalysisTab migrationId={1} />);
    await waitFor(() => {
      expect(screen.getByText('Recurring Monthly Costs')).toBeInTheDocument();
    });
    expect(screen.getByText('S3 Storage')).toBeInTheDocument();
    expect(screen.getByText('Glue Data Catalog')).toBeInTheDocument();
    expect(screen.getByText('Athena Queries')).toBeInTheDocument();
    expect(screen.getByText('Total Monthly')).toBeInTheDocument();
  });

  // --- Projections ---

  it('displays cost projections table with optimistic and conservative', async () => {
    render(<IcebergCostAnalysisTab migrationId={1} />);
    await waitFor(() => {
      expect(screen.getByText('Cost Projections')).toBeInTheDocument();
    });
    expect(screen.getByText('3 Months')).toBeInTheDocument();
    expect(screen.getByText('6 Months')).toBeInTheDocument();
    expect(screen.getByText('12 Months')).toBeInTheDocument();
    expect(screen.getByText('Optimistic')).toBeInTheDocument();
    expect(screen.getByText('Conservative')).toBeInTheDocument();
  });

  it('displays compression ratio info', async () => {
    render(<IcebergCostAnalysisTab migrationId={1} />);
    await waitFor(() => {
      expect(screen.getByText(/5:1 \(optimistic\)/)).toBeInTheDocument();
    });
    expect(screen.getByText(/3:1 \(conservative\)/)).toBeInTheDocument();
  });

  // --- TCO Comparison ---

  it('displays TCO comparison when available', async () => {
    render(<IcebergCostAnalysisTab migrationId={1} />);
    await waitFor(() => {
      expect(screen.getByText('TCO Comparison: BigQuery vs Iceberg')).toBeInTheDocument();
    });
    expect(screen.getByText('BigQuery (Current)')).toBeInTheDocument();
    expect(screen.getByText('Iceberg (Projected)')).toBeInTheDocument();
    expect(screen.getByText('Monthly Savings')).toBeInTheDocument();
  });

  it('does not render TCO comparison when not available', async () => {
    mockGetCost.mockResolvedValue({
      ...sampleCostReport,
      tco_comparison: undefined,
    });
    render(<IcebergCostAnalysisTab migrationId={1} />);
    await waitFor(() => {
      expect(screen.getByText('Cost Analysis')).toBeInTheDocument();
    });
    expect(screen.queryByText('TCO Comparison')).not.toBeInTheDocument();
  });

  it('shows savings when Iceberg is cheaper', async () => {
    render(<IcebergCostAnalysisTab migrationId={1} />);
    await waitFor(() => {
      expect(screen.getByText('Monthly Savings')).toBeInTheDocument();
    });
    expect(screen.getByText(/98.5%/)).toBeInTheDocument();
  });

  it('shows additional cost when Iceberg is more expensive', async () => {
    mockGetCost.mockResolvedValue({
      ...sampleCostReport,
      tco_comparison: {
        bigquery_monthly: 0.05,
        iceberg_monthly: 0.074,
        savings_monthly: -0.024,
        savings_percentage: -48.0,
      },
    });
    render(<IcebergCostAnalysisTab migrationId={1} />);
    await waitFor(() => {
      expect(screen.getByText('Additional Cost')).toBeInTheDocument();
    });
  });

  // --- Growth Rate Adjustment ---

  it('renders growth rate slider with initial value', async () => {
    render(<IcebergCostAnalysisTab migrationId={1} />);
    await waitFor(() => {
      expect(screen.getByText('Growth Rate Adjustment')).toBeInTheDocument();
    });
    const slider = screen.getByLabelText('Monthly growth rate percentage');
    expect(slider).toHaveValue('5');
    expect(screen.getByText('5% / month')).toBeInTheDocument();
  });

  it('changing growth rate triggers recalculation', async () => {
    const updatedReport = {
      ...sampleCostReport,
      growth_rate_monthly: 0.10,
      projections_optimistic: { month_3: 0.25, month_6: 0.55, month_12: 1.30 },
      projections_conservative: { month_3: 0.42, month_6: 0.92, month_12: 2.10 },
    };
    mockRecalculate.mockResolvedValue(updatedReport);

    render(<IcebergCostAnalysisTab migrationId={1} />);
    await waitFor(() => {
      expect(screen.getByLabelText('Monthly growth rate percentage')).toBeInTheDocument();
    });

    const slider = screen.getByLabelText('Monthly growth rate percentage');
    // Simulate changing the slider value
    await userEvent.clear(slider);
    // fireEvent is needed for range inputs
    Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set?.call(slider, '10');
    slider.dispatchEvent(new Event('change', { bubbles: true }));

    await waitFor(() => {
      expect(mockRecalculate).toHaveBeenCalledWith(1, { growth_rate_monthly: 0.10 });
    });
  });

  it('shows recalculating indicator during API call', async () => {
    mockRecalculate.mockReturnValue(new Promise(() => {}));

    render(<IcebergCostAnalysisTab migrationId={1} />);
    await waitFor(() => {
      expect(screen.getByLabelText('Monthly growth rate percentage')).toBeInTheDocument();
    });

    const slider = screen.getByLabelText('Monthly growth rate percentage');
    Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set?.call(slider, '15');
    slider.dispatchEvent(new Event('change', { bubbles: true }));

    await waitFor(() => {
      expect(screen.getByText(/recalculating/)).toBeInTheDocument();
    });
  });

  // --- API calls ---

  it('calls getCostAnalysis with correct migration ID', async () => {
    render(<IcebergCostAnalysisTab migrationId={42} />);
    await waitFor(() => {
      expect(mockGetCost).toHaveBeenCalledWith(42);
    });
  });
});
