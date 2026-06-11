/**
 * Tests for IcebergStructureReviewPage
 * Covers: structure report rendering, collapsible sections, override controls,
 * form submission, download report, approve/request changes flow.
 * Requirements: 4.5, 4.9, 13.1, 13.5
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { IcebergStructureReviewPage } from '../IcebergStructureReviewPage';
import type { StructureReport } from '../../../types/bqIceberg';

// Mock the API
vi.mock('../../../services/bqIcebergApi', () => ({
  bqIcebergApi: {
    getStructureReport: vi.fn(),
    approveStructure: vi.fn(),
    requestChanges: vi.fn(),
    downloadReport: vi.fn(),
  },
}));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

import { bqIcebergApi } from '../../../services/bqIcebergApi';

const mockGetReport = vi.mocked(bqIcebergApi.getStructureReport);
const mockApprove = vi.mocked(bqIcebergApi.approveStructure);
const mockRequestChanges = vi.mocked(bqIcebergApi.requestChanges);
const mockDownload = vi.mocked(bqIcebergApi.downloadReport);

// Sample data
const sampleReport: StructureReport = {
  migration_id: 1,
  tables: [
    {
      table_name: 'users',
      iceberg_table_name: 'users',
      columns: [
        { name: 'id', source_bq_type: 'INT64', iceberg_type: 'long', nullable: false, warnings: [] },
        { name: 'name', source_bq_type: 'STRING', iceberg_type: 'string', nullable: true, warnings: [] },
        { name: 'email', source_bq_type: 'STRING', iceberg_type: 'string', nullable: true, warnings: [] },
        { name: 'created_at', source_bq_type: 'TIMESTAMP', iceberg_type: 'timestamptz', nullable: true, warnings: [] },
      ],
      partition_spec: [{ column: 'created_at', transform: 'day', rationale: 'Based on BQ DATE partitioning' }],
      sort_order: [{ column: 'id', direction: 'asc' }],
      properties: {
        'write.format.default': 'parquet',
        'write.parquet.compression-codec': 'zstd',
        'format-version': '2',
      },
      estimated_row_count: 50000,
      estimated_data_size_bytes: 10485760,
      is_custom: false,
    },
    {
      table_name: 'orders',
      iceberg_table_name: 'orders',
      columns: [
        { name: 'order_id', source_bq_type: 'INT64', iceberg_type: 'long', nullable: false, warnings: [] },
        { name: 'user_id', source_bq_type: 'INT64', iceberg_type: 'long', nullable: false, warnings: [] },
        { name: 'amount', source_bq_type: 'NUMERIC', iceberg_type: 'decimal(38,9)', nullable: true, warnings: [] },
        { name: 'geo_data', source_bq_type: 'GEOGRAPHY', iceberg_type: 'string', nullable: true, warnings: ['Mapped to fallback type: string'] },
      ],
      partition_spec: [],
      sort_order: [],
      properties: { 'format-version': '2' },
      estimated_row_count: 200000,
      estimated_data_size_bytes: 52428800,
      is_custom: false,
    },
  ],
  prerequisites: [
    {
      id: 'iam-s3',
      label: 'S3 Write Access',
      description: 'IAM role must have s3:PutObject, s3:GetObject permissions on the target bucket.',
      category: 'iam',
      required: true,
    },
    {
      id: 'glue-db',
      label: 'Glue Database',
      description: 'Glue Data Catalog database must exist or IAM must have glue:CreateDatabase permission.',
      category: 'glue',
      required: true,
    },
    {
      id: 'athena-wg',
      label: 'Athena Workgroup',
      description: 'Athena workgroup must be configured for verification queries.',
      category: 'athena',
      required: false,
    },
  ],
  warnings: [
    {
      severity: 'warning',
      table_name: 'orders',
      message: 'Table has no partitioning defined. Consider adding partitioning for tables > 1GB.',
      recommendation: 'Add day(order_date) partition for better query performance.',
    },
    {
      severity: 'info',
      message: 'Estimated total storage footprint: 60 MB (compressed with ZSTD).',
    },
  ],
  dataset_to_db_mapping: { analytics: 'analytics_db' },
  s3_tables_namespace: 'my-namespace',
  generated_at: '2026-01-25T10:00:00Z',
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/migrations/bq-iceberg/1/structure-review']}>
      <Routes>
        <Route
          path="/migrations/bq-iceberg/:migrationId/structure-review"
          element={<IcebergStructureReviewPage />}
        />
      </Routes>
    </MemoryRouter>
  );
}

describe('IcebergStructureReviewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetReport.mockResolvedValue(sampleReport);
  });

  // --- Loading and Error States ---

  it('renders loading state initially', () => {
    mockGetReport.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByText('Loading structure report...')).toBeInTheDocument();
  });

  it('renders error state on API failure', async () => {
    mockGetReport.mockRejectedValue(new Error('Network error'));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  // --- Structure Report Rendering ---

  it('renders page title and subtitle after loading', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Iceberg Structure Review')).toBeInTheDocument();
    });
    expect(screen.getByText(/Review the proposed Iceberg table structures/)).toBeInTheDocument();
  });

  it('renders all table sections with names', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('users')).toBeInTheDocument();
    });
    expect(screen.getByText('orders')).toBeInTheDocument();
  });

  it('displays table metadata (columns, rows, size)', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('4 cols')).toBeInTheDocument();
    });
    expect(screen.getByText('50,000 rows')).toBeInTheDocument();
  });

  // --- Collapsible Sections ---

  it('table sections are collapsed by default', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('users')).toBeInTheDocument();
    });
    // Column names should not be visible when collapsed
    expect(screen.queryByText('source_bq_type')).not.toBeInTheDocument();
  });

  it('clicking table header expands the section', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('users')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByLabelText('Toggle users details'));

    // Column table should now be visible
    await waitFor(() => {
      expect(screen.getByText('id')).toBeInTheDocument();
    });
    expect(screen.getByText('INT64')).toBeInTheDocument();
    expect(screen.getByText('long')).toBeInTheDocument();
  });

  it('expanded section shows partition spec', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('users')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByLabelText('Toggle users details'));

    await waitFor(() => {
      expect(screen.getByText(/day\(created_at\)/)).toBeInTheDocument();
    });
  });

  it('expanded section shows sort order', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('users')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByLabelText('Toggle users details'));

    await waitFor(() => {
      expect(screen.getByText(/id \(asc\)/)).toBeInTheDocument();
    });
  });

  it('expanded section shows table properties', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('users')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByLabelText('Toggle users details'));

    await waitFor(() => {
      expect(screen.getByText('write.format.default')).toBeInTheDocument();
    });
    expect(screen.getByText('parquet')).toBeInTheDocument();
  });

  // --- Prerequisites Checklist ---

  it('renders prerequisites checklist', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Prerequisites Checklist')).toBeInTheDocument();
    });
    expect(screen.getByText('S3 Write Access')).toBeInTheDocument();
    expect(screen.getByText('Glue Database')).toBeInTheDocument();
    expect(screen.getByText('Athena Workgroup')).toBeInTheDocument();
  });

  it('prerequisites checkboxes are interactive', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('S3 Write Access')).toBeInTheDocument();
    });

    const checkbox = screen.getByLabelText('S3 Write Access');
    expect(checkbox).not.toBeChecked();
    await userEvent.click(checkbox);
    expect(checkbox).toBeChecked();
  });

  // --- Warnings Section ---

  it('renders warnings and recommendations', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Warnings and Recommendations')).toBeInTheDocument();
    });
    expect(screen.getByText(/Table has no partitioning defined/)).toBeInTheDocument();
    expect(screen.getByText(/Estimated total storage footprint/)).toBeInTheDocument();
  });

  // --- Override Controls ---

  it('exclude toggle marks table as excluded', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('users')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByLabelText('Toggle users details'));

    await waitFor(() => {
      expect(screen.getByText('Exclude from migration')).toBeInTheDocument();
    });

    const excludeCheckbox = screen.getByRole('checkbox', { name: /exclude from migration/i });
    await userEvent.click(excludeCheckbox);

    // Table should show excluded badge
    expect(screen.getByText('Excluded')).toBeInTheDocument();
  });

  it('partition override button shows edit controls', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('users')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByLabelText('Toggle users details'));

    await waitFor(() => {
      expect(screen.getByText('Partition Spec')).toBeInTheDocument();
    });

    // Click Override button
    const overrideButtons = screen.getAllByText('Override');
    await userEvent.click(overrideButtons[0]);

    // Should show partition editing controls
    await waitFor(() => {
      expect(screen.getByLabelText('Partition column 1')).toBeInTheDocument();
    });
    expect(screen.getByLabelText('Partition transform 1')).toBeInTheDocument();
  });

  // --- Dataset to Database Mapping ---

  it('renders dataset to database mapping inputs', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Dataset to Database Mapping')).toBeInTheDocument();
    });
    expect(screen.getByText('analytics')).toBeInTheDocument();
    const input = screen.getByLabelText('Database name for analytics');
    expect(input).toHaveValue('analytics_db');
  });

  it('dataset mapping input is editable', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByLabelText('Database name for analytics')).toBeInTheDocument();
    });

    const input = screen.getByLabelText('Database name for analytics');
    await userEvent.clear(input);
    await userEvent.type(input, 'new_db_name');
    expect(input).toHaveValue('new_db_name');
  });

  // --- S3 Tables Namespace ---

  it('renders namespace input for S3 Tables', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('S3 Tables Namespace')).toBeInTheDocument();
    });
    const input = screen.getByLabelText('S3 Tables namespace name');
    expect(input).toHaveValue('my-namespace');
  });

  // --- Approve & Proceed ---

  it('Approve & Proceed button calls API and navigates', async () => {
    mockApprove.mockResolvedValue({ message: 'Approved', migration_id: 1, status: 'approved' });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Approve & Proceed')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText('Approve & Proceed'));

    await waitFor(() => {
      expect(mockApprove).toHaveBeenCalledWith(1, expect.objectContaining({
        dataset_to_db_mapping: { analytics: 'analytics_db' },
        s3_tables_namespace: 'my-namespace',
      }));
    });
    expect(screen.getByText(/Structure approved/)).toBeInTheDocument();
  });

  it('Approve & Proceed shows error on failure', async () => {
    mockApprove.mockRejectedValue(new Error('Permission denied'));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Approve & Proceed')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText('Approve & Proceed'));

    await waitFor(() => {
      expect(screen.getByText('Permission denied')).toBeInTheDocument();
    });
  });

  // --- Request Changes ---

  it('Request Changes button calls API', async () => {
    mockRequestChanges.mockResolvedValue({ message: 'Changes submitted' });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Request Changes')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText('Request Changes'));

    await waitFor(() => {
      expect(mockRequestChanges).toHaveBeenCalledWith(1, expect.any(Object));
    });
  });

  // --- Download Report ---

  it('Download Report button triggers download', async () => {
    const mockBlob = new Blob(['# Report'], { type: 'text/markdown' });
    mockDownload.mockResolvedValue(mockBlob);

    // Mock URL.createObjectURL and revokeObjectURL
    const mockCreateObjectURL = vi.fn().mockReturnValue('blob:test');
    const mockRevokeObjectURL = vi.fn();
    global.URL.createObjectURL = mockCreateObjectURL;
    global.URL.revokeObjectURL = mockRevokeObjectURL;

    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Download Report')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText('Download Report'));

    await waitFor(() => {
      expect(mockDownload).toHaveBeenCalledWith(1);
    });
  });

  // --- Column Warnings ---

  it('displays column mapping warnings', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('orders')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByLabelText('Toggle orders details'));

    await waitFor(() => {
      expect(screen.getByText('Mapped to fallback type: string')).toBeInTheDocument();
    });
  });

  // --- Table count display ---

  it('displays total table count in section header', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('Table Structures (2 tables)')).toBeInTheDocument();
    });
  });
});
