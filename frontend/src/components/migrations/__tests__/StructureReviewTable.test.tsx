/**
 * Tests for StructureReviewTable
 * Covers: compaction strategy display, partition transforms, Lake Formation prerequisites,
 * glue.id validation indicator.
 * Requirements: 3.1, 5.1, 5.7, 7.6, 2.4
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  StructureReviewTable,
  formatPartitionTransform,
} from '../StructureReviewTable';
import type {
  TableStructure,
  CompactionConfig,
  LakeFormationPrerequisite,
  PartitionSpec,
} from '../../../types/bqIceberg';

// --- Sample Data ---

const sampleTable: TableStructure = {
  table_name: 'orders',
  iceberg_table_name: 'orders',
  columns: [
    { name: 'id', source_bq_type: 'INT64', iceberg_type: 'long', nullable: false, warnings: [] },
    { name: 'event_timestamp', source_bq_type: 'TIMESTAMP', iceberg_type: 'timestamptz', nullable: true, warnings: [] },
    { name: 'amount', source_bq_type: 'FLOAT64', iceberg_type: 'double', nullable: true, warnings: [] },
  ],
  partition_spec: [{ column: 'event_timestamp', transform: 'day' }],
  sort_order: [{ column: 'id', direction: 'asc' }],
  properties: {},
  estimated_row_count: 1000000,
  estimated_data_size_bytes: 500000000,
  is_custom: false,
};

const sampleCompactionConfig: CompactionConfig = {
  strategy: 'sort',
  sort_columns: ['order_date', 'customer_id'],
  recommended_strategy: 'sort',
  recommended_sort_columns: ['order_date'],
};

const sampleLakeFormationPrereqs: LakeFormationPrerequisite[] = [
  {
    description: 'Data location permission on S3 Tables bucket',
    arn_or_permission: 'arn:aws:s3tables:us-east-1:123456789012:bucket/my-table-bucket',
    action_type: 'data_location',
  },
  {
    description: 'DESCRIBE permission on Glue catalog database',
    arn_or_permission: 'DESCRIBE on database: my_database',
    action_type: 'glue_database',
  },
  {
    description: 'SELECT permission on Glue catalog tables',
    arn_or_permission: 'SELECT on tables in database: my_database',
    action_type: 'glue_tables',
  },
  {
    description: 'IAM permission for Lake Formation data access',
    arn_or_permission: 'lakeformation:GetDataAccess',
    action_type: 'iam',
  },
];

// --- formatPartitionTransform Tests ---

describe('formatPartitionTransform', () => {
  it('formats day transform as days(column)', () => {
    const spec: PartitionSpec = { column: 'event_timestamp', transform: 'day' };
    expect(formatPartitionTransform(spec)).toBe('days(event_timestamp)');
  });

  it('formats hour transform as hours(column)', () => {
    const spec: PartitionSpec = { column: 'created_at', transform: 'hour' };
    expect(formatPartitionTransform(spec)).toBe('hours(created_at)');
  });

  it('formats month transform as months(column)', () => {
    const spec: PartitionSpec = { column: 'order_date', transform: 'month' };
    expect(formatPartitionTransform(spec)).toBe('months(order_date)');
  });

  it('formats year transform as years(column)', () => {
    const spec: PartitionSpec = { column: 'fiscal_year', transform: 'year' };
    expect(formatPartitionTransform(spec)).toBe('years(fiscal_year)');
  });

  it('formats identity transform as identity(column)', () => {
    const spec: PartitionSpec = { column: 'region', transform: 'identity' };
    expect(formatPartitionTransform(spec)).toBe('identity(region)');
  });

  it('formats bucket transform as bucket(column)', () => {
    const spec: PartitionSpec = { column: 'user_id', transform: 'bucket' };
    expect(formatPartitionTransform(spec)).toBe('bucket(user_id)');
  });
});

// --- StructureReviewTable Component Tests ---

describe('StructureReviewTable', () => {
  const defaultProps = {
    tables: [sampleTable],
    destinationType: 'iceberg_s3_tables' as const,
  };

  // --- Table Structure Display ---

  it('renders table name', () => {
    render(<StructureReviewTable {...defaultProps} />);
    expect(screen.getByText('orders')).toBeInTheDocument();
  });

  it('renders column count', () => {
    render(<StructureReviewTable {...defaultProps} />);
    expect(screen.getByText('3 columns')).toBeInTheDocument();
  });

  it('renders partition transform as human-readable format', () => {
    render(<StructureReviewTable {...defaultProps} />);
    expect(screen.getByText('days(event_timestamp)')).toBeInTheDocument();
  });

  it('renders multiple tables', () => {
    const secondTable: TableStructure = {
      ...sampleTable,
      table_name: 'customers',
      iceberg_table_name: 'customers',
      columns: [
        { name: 'id', source_bq_type: 'INT64', iceberg_type: 'long', nullable: false, warnings: [] },
      ],
      partition_spec: [{ column: 'created_at', transform: 'month' }],
    };
    render(<StructureReviewTable {...defaultProps} tables={[sampleTable, secondTable]} />);
    expect(screen.getByText('orders')).toBeInTheDocument();
    expect(screen.getByText('customers')).toBeInTheDocument();
    expect(screen.getByText('months(created_at)')).toBeInTheDocument();
  });

  // --- Compaction Strategy Display ---

  it('displays compaction strategy badge', () => {
    render(
      <StructureReviewTable
        {...defaultProps}
        compactionConfigs={{ orders: sampleCompactionConfig }}
      />
    );
    expect(screen.getByText('Sort')).toBeInTheDocument();
  });

  it('displays compaction strategy description', () => {
    render(
      <StructureReviewTable
        {...defaultProps}
        compactionConfigs={{ orders: sampleCompactionConfig }}
      />
    );
    expect(
      screen.getByText('Reorders data by specified columns (best for range queries on specific columns)')
    ).toBeInTheDocument();
  });

  it('displays sort columns for sort strategy', () => {
    render(
      <StructureReviewTable
        {...defaultProps}
        compactionConfigs={{ orders: sampleCompactionConfig }}
      />
    );
    expect(screen.getByText('order_date')).toBeInTheDocument();
    expect(screen.getByText('customer_id')).toBeInTheDocument();
  });

  it('does not display sort columns for binpack strategy', () => {
    const binpackConfig: CompactionConfig = {
      strategy: 'binpack',
      sort_columns: [],
    };
    render(
      <StructureReviewTable
        {...defaultProps}
        compactionConfigs={{ orders: binpackConfig }}
      />
    );
    expect(screen.getByText('Binpack')).toBeInTheDocument();
    expect(screen.queryByText('Sort columns:')).not.toBeInTheDocument();
  });

  it('displays recommendation when different from selected strategy', () => {
    const config: CompactionConfig = {
      strategy: 'binpack',
      sort_columns: [],
      recommended_strategy: 'sort',
      recommended_sort_columns: ['order_date'],
    };
    render(
      <StructureReviewTable
        {...defaultProps}
        compactionConfigs={{ orders: config }}
      />
    );
    expect(screen.getByText(/Recommended: Sort/)).toBeInTheDocument();
    expect(screen.getByText(/order_date/)).toBeInTheDocument();
  });

  it('does not display recommendation when same as selected strategy', () => {
    render(
      <StructureReviewTable
        {...defaultProps}
        compactionConfigs={{ orders: sampleCompactionConfig }}
      />
    );
    // recommended_strategy is 'sort' and strategy is 'sort', so no recommendation shown
    expect(screen.queryByText(/Recommended:/)).not.toBeInTheDocument();
  });

  it('displays z-order strategy with sort columns', () => {
    const zOrderConfig: CompactionConfig = {
      strategy: 'z-order',
      sort_columns: ['region', 'category'],
    };
    render(
      <StructureReviewTable
        {...defaultProps}
        compactionConfigs={{ orders: zOrderConfig }}
      />
    );
    expect(screen.getByText('Z-Order')).toBeInTheDocument();
    expect(screen.getByText('region')).toBeInTheDocument();
    expect(screen.getByText('category')).toBeInTheDocument();
  });

  // --- Glue ID Display ---

  it('displays glue.id with valid indicator for S3 Tables', () => {
    render(
      <StructureReviewTable
        {...defaultProps}
        glueId={{ value: '123456789012:s3tablescatalog/my-bucket', isValid: true }}
      />
    );
    expect(screen.getByText('123456789012:s3tablescatalog/my-bucket')).toBeInTheDocument();
    expect(screen.getByText('Valid')).toBeInTheDocument();
  });

  it('displays glue.id with invalid indicator', () => {
    render(
      <StructureReviewTable
        {...defaultProps}
        glueId={{ value: 'invalid-format', isValid: false }}
      />
    );
    expect(screen.getByText('invalid-format')).toBeInTheDocument();
    expect(screen.getByText('Invalid')).toBeInTheDocument();
  });

  it('does not display glue.id section for standard S3 destinations', () => {
    render(
      <StructureReviewTable
        {...defaultProps}
        destinationType="iceberg_s3"
        glueId={{ value: '123456789012:s3tablescatalog/my-bucket', isValid: true }}
      />
    );
    expect(screen.queryByText('Glue Catalog Identifier')).not.toBeInTheDocument();
  });

  it('does not display glue.id section when glueId prop is not provided', () => {
    render(<StructureReviewTable {...defaultProps} />);
    expect(screen.queryByText('Glue Catalog Identifier')).not.toBeInTheDocument();
  });

  // --- Lake Formation Prerequisites ---

  it('displays Lake Formation prerequisites for S3 Tables', () => {
    render(
      <StructureReviewTable
        {...defaultProps}
        lakeFormationPrerequisites={sampleLakeFormationPrereqs}
      />
    );
    expect(screen.getByText('Lake Formation Prerequisites')).toBeInTheDocument();
    expect(screen.getByText('Data location permission on S3 Tables bucket')).toBeInTheDocument();
    expect(
      screen.getByText('arn:aws:s3tables:us-east-1:123456789012:bucket/my-table-bucket')
    ).toBeInTheDocument();
  });

  it('displays all prerequisite items with permissions', () => {
    render(
      <StructureReviewTable
        {...defaultProps}
        lakeFormationPrerequisites={sampleLakeFormationPrereqs}
      />
    );
    expect(screen.getByText('DESCRIBE permission on Glue catalog database')).toBeInTheDocument();
    expect(screen.getByText('DESCRIBE on database: my_database')).toBeInTheDocument();
    expect(screen.getByText('SELECT permission on Glue catalog tables')).toBeInTheDocument();
    expect(screen.getByText('lakeformation:GetDataAccess')).toBeInTheDocument();
  });

  it('does not display Lake Formation section for standard S3 destinations', () => {
    render(
      <StructureReviewTable
        {...defaultProps}
        destinationType="iceberg_s3"
        lakeFormationPrerequisites={sampleLakeFormationPrereqs}
      />
    );
    expect(screen.queryByText('Lake Formation Prerequisites')).not.toBeInTheDocument();
  });

  it('does not display Lake Formation section when no prerequisites provided', () => {
    render(<StructureReviewTable {...defaultProps} lakeFormationPrerequisites={[]} />);
    expect(screen.queryByText('Lake Formation Prerequisites')).not.toBeInTheDocument();
  });

  // --- Conditional Rendering ---

  it('renders without compaction configs gracefully', () => {
    render(<StructureReviewTable {...defaultProps} />);
    expect(screen.getByText('orders')).toBeInTheDocument();
    expect(screen.queryByText('Compaction Strategy')).not.toBeInTheDocument();
  });

  it('renders table without partition spec gracefully', () => {
    const tableNoPartition: TableStructure = {
      ...sampleTable,
      partition_spec: [],
    };
    render(<StructureReviewTable {...defaultProps} tables={[tableNoPartition]} />);
    expect(screen.getByText('orders')).toBeInTheDocument();
    expect(screen.queryByText('Partitioning')).not.toBeInTheDocument();
  });
});
