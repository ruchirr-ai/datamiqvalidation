/**
 * Tests for IcebergDestinationStep component and validators.
 * Requirements: 9.1, 9.2, 9.4, 9.5
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { IcebergDestinationStep } from '../IcebergDestinationStep';
import {
  IcebergConfigData,
  validateS3BucketName,
  validateGlueDatabaseName,
  validateTableBucketArn,
  validateAwsRegion,
  validateIamRoleArn,
  validateS3PathPrefix,
  validateIcebergConfig,
} from '../validators';

// Default empty config for tests
const makeConfig = (overrides: Partial<IcebergConfigData> = {}): IcebergConfigData => ({
  destinationType: null,
  s3Bucket: '',
  s3PathPrefix: '',
  tableBucketArn: '',
  awsRegion: '',
  glueDatabaseName: '',
  awsAccessKeyId: '',
  awsSecretAccessKey: '',
  awsRoleArn: '',
  useIamRole: false,
  ...overrides,
});

describe('IcebergDestinationStep', () => {
  describe('Destination card selection (Req 9.1)', () => {
    it('renders both destination cards (Redshift and Iceberg)', () => {
      const onChange = vi.fn();
      render(<IcebergDestinationStep config={makeConfig()} onChange={onChange} />);

      expect(screen.getByText('Amazon Redshift')).toBeInTheDocument();
      expect(screen.getByText('Apache Iceberg')).toBeInTheDocument();
    });

    it('shows Redshift card as disabled', () => {
      const onChange = vi.fn();
      render(<IcebergDestinationStep config={makeConfig()} onChange={onChange} />);

      const redshiftCard = screen.getByText('Amazon Redshift').closest('.destination-card');
      expect(redshiftCard).toHaveClass('disabled');
    });

    it('selects Iceberg destination on card click', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      render(<IcebergDestinationStep config={makeConfig()} onChange={onChange} />);

      const icebergCard = screen.getByText('Apache Iceberg').closest('.destination-card');
      await user.click(icebergCard!);

      expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ destinationType: 'iceberg_s3' }));
    });

    it('shows check mark when Iceberg is selected', () => {
      const onChange = vi.fn();
      render(
        <IcebergDestinationStep
          config={makeConfig({ destinationType: 'iceberg_s3' })}
          onChange={onChange}
        />
      );

      const icebergCard = screen.getByText('Apache Iceberg').closest('.destination-card');
      expect(icebergCard).toHaveClass('selected');
    });
  });

  describe('Sub-type toggle (Req 9.2)', () => {
    it('shows sub-type toggle when Iceberg is selected', () => {
      const onChange = vi.fn();
      render(
        <IcebergDestinationStep
          config={makeConfig({ destinationType: 'iceberg_s3' })}
          onChange={onChange}
        />
      );

      expect(screen.getByText('Standard S3')).toBeInTheDocument();
      expect(screen.getByText('AWS S3 Tables')).toBeInTheDocument();
    });

    it('does not show sub-type toggle when no destination selected', () => {
      const onChange = vi.fn();
      render(<IcebergDestinationStep config={makeConfig()} onChange={onChange} />);

      expect(screen.queryByText('Standard S3')).not.toBeInTheDocument();
      expect(screen.queryByText('AWS S3 Tables')).not.toBeInTheDocument();
    });

    it('switches to S3 Tables sub-type on click', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      render(
        <IcebergDestinationStep
          config={makeConfig({ destinationType: 'iceberg_s3' })}
          onChange={onChange}
        />
      );

      await user.click(screen.getByText('AWS S3 Tables'));
      expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ destinationType: 'iceberg_s3_tables' }));
    });

    it('highlights active sub-type', () => {
      const onChange = vi.fn();
      render(
        <IcebergDestinationStep
          config={makeConfig({ destinationType: 'iceberg_s3_tables' })}
          onChange={onChange}
        />
      );

      const s3TablesBtn = screen.getByText('AWS S3 Tables').closest('.subtype-option');
      expect(s3TablesBtn).toHaveClass('active');
    });
  });

  describe('Form field rendering for each destination type (Req 9.2)', () => {
    it('shows S3 bucket and path prefix fields for Standard S3', () => {
      const onChange = vi.fn();
      render(
        <IcebergDestinationStep
          config={makeConfig({ destinationType: 'iceberg_s3' })}
          onChange={onChange}
        />
      );

      expect(screen.getByPlaceholderText('my-iceberg-bucket')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('iceberg/tables')).toBeInTheDocument();
      expect(screen.queryByPlaceholderText(/arn:aws:s3tables/)).not.toBeInTheDocument();
    });

    it('shows table bucket ARN field for S3 Tables', () => {
      const onChange = vi.fn();
      render(
        <IcebergDestinationStep
          config={makeConfig({ destinationType: 'iceberg_s3_tables' })}
          onChange={onChange}
        />
      );

      expect(screen.getByPlaceholderText(/arn:aws:s3tables/)).toBeInTheDocument();
      expect(screen.queryByPlaceholderText('my-iceberg-bucket')).not.toBeInTheDocument();
    });

    it('shows common fields (region, Glue DB) for both types', () => {
      const onChange = vi.fn();
      render(
        <IcebergDestinationStep
          config={makeConfig({ destinationType: 'iceberg_s3' })}
          onChange={onChange}
        />
      );

      expect(screen.getByPlaceholderText('my_iceberg_db')).toBeInTheDocument();
      expect(screen.getByText('AWS Region')).toBeInTheDocument();
    });

    it('shows access key fields by default', () => {
      const onChange = vi.fn();
      render(
        <IcebergDestinationStep
          config={makeConfig({ destinationType: 'iceberg_s3', useIamRole: false })}
          onChange={onChange}
        />
      );

      expect(screen.getByPlaceholderText('AKIAIOSFODNN7EXAMPLE')).toBeInTheDocument();
    });

    it('shows IAM Role ARN field when IAM Role is selected', () => {
      const onChange = vi.fn();
      render(
        <IcebergDestinationStep
          config={makeConfig({ destinationType: 'iceberg_s3', useIamRole: true })}
          onChange={onChange}
        />
      );

      expect(screen.getByPlaceholderText(/arn:aws:iam/)).toBeInTheDocument();
      expect(screen.queryByPlaceholderText('AKIAIOSFODNN7EXAMPLE')).not.toBeInTheDocument();
    });

    it('toggles between Access Keys and IAM Role', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      render(
        <IcebergDestinationStep
          config={makeConfig({ destinationType: 'iceberg_s3', useIamRole: false })}
          onChange={onChange}
        />
      );

      await user.click(screen.getByText('IAM Role'));
      expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ useIamRole: true }));
    });
  });

  describe('Back navigation preserves values (Req 9.5)', () => {
    it('preserves all config values when re-rendered with same config', () => {
      const onChange = vi.fn();
      const config = makeConfig({
        destinationType: 'iceberg_s3',
        s3Bucket: 'my-test-bucket',
        s3PathPrefix: 'data/iceberg',
        awsRegion: 'us-west-2',
        glueDatabaseName: 'test_db',
        awsAccessKeyId: 'AKIATEST',
        awsSecretAccessKey: 'secret123',
      });

      const { rerender } = render(
        <IcebergDestinationStep config={config} onChange={onChange} />
      );

      // Simulate back navigation by re-rendering with same config
      rerender(<IcebergDestinationStep config={config} onChange={onChange} />);

      expect(screen.getByDisplayValue('my-test-bucket')).toBeInTheDocument();
      expect(screen.getByDisplayValue('data/iceberg')).toBeInTheDocument();
      expect(screen.getByDisplayValue('test_db')).toBeInTheDocument();
      expect(screen.getByDisplayValue('AKIATEST')).toBeInTheDocument();
    });
  });

  describe('Summary panel display (Req 9.3)', () => {
    it('shows summary panel after successful validation', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      const config = makeConfig({
        destinationType: 'iceberg_s3',
        s3Bucket: 'my-valid-bucket',
        s3PathPrefix: '',
        awsRegion: 'us-east-1',
        glueDatabaseName: 'my_db',
        awsAccessKeyId: 'AKIAIOSFODNN7EXAMPLE',
        awsSecretAccessKey: 'wJalrXUtnFEMI',
        useIamRole: false,
      });

      render(<IcebergDestinationStep config={config} onChange={onChange} />);

      await user.click(screen.getByText('Validate Configuration'));

      expect(screen.getByText('Configuration Summary')).toBeInTheDocument();
      expect(screen.getByText('Apache Iceberg on S3')).toBeInTheDocument();
      expect(screen.getByText('my-valid-bucket')).toBeInTheDocument();
      expect(screen.getByText('my_db')).toBeInTheDocument();
      expect(screen.getByText('us-east-1')).toBeInTheDocument();
    });

    it('shows S3 Tables info in summary when S3 Tables selected', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      const config = makeConfig({
        destinationType: 'iceberg_s3_tables',
        tableBucketArn: 'arn:aws:s3tables:us-east-1:123456789012:bucket/my-bucket',
        awsRegion: 'us-east-1',
        glueDatabaseName: 'my_db',
        awsAccessKeyId: 'AKIAIOSFODNN7EXAMPLE',
        awsSecretAccessKey: 'wJalrXUtnFEMI',
        useIamRole: false,
      });

      render(<IcebergDestinationStep config={config} onChange={onChange} />);

      await user.click(screen.getByText('Validate Configuration'));

      expect(screen.getByText('Configuration Summary')).toBeInTheDocument();
      expect(screen.getByText('AWS S3 Tables (Managed)')).toBeInTheDocument();
    });

    it('does not show summary when validation fails', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      const config = makeConfig({
        destinationType: 'iceberg_s3',
        s3Bucket: '', // invalid - empty
        awsRegion: 'us-east-1',
        glueDatabaseName: 'my_db',
        awsAccessKeyId: 'AKIAIOSFODNN7EXAMPLE',
        awsSecretAccessKey: 'secret',
        useIamRole: false,
      });

      render(<IcebergDestinationStep config={config} onChange={onChange} showErrors />);

      await user.click(screen.getByText('Validate Configuration'));

      expect(screen.queryByText('Configuration Summary')).not.toBeInTheDocument();
    });

    it('shows selected table count in summary', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      const config = makeConfig({
        destinationType: 'iceberg_s3',
        s3Bucket: 'my-valid-bucket',
        awsRegion: 'us-east-1',
        glueDatabaseName: 'my_db',
        awsAccessKeyId: 'AKIAIOSFODNN7EXAMPLE',
        awsSecretAccessKey: 'secret',
        useIamRole: false,
      });

      render(
        <IcebergDestinationStep config={config} onChange={onChange} selectedTableCount={5} />
      );

      await user.click(screen.getByText('Validate Configuration'));

      expect(screen.getByText('5 table(s) selected')).toBeInTheDocument();
    });
  });
});

describe('Iceberg Validators (Req 9.4)', () => {
  describe('validateS3BucketName', () => {
    it('accepts valid bucket names', () => {
      expect(validateS3BucketName('my-bucket').valid).toBe(true);
      expect(validateS3BucketName('my.bucket.name').valid).toBe(true);
      expect(validateS3BucketName('bucket123').valid).toBe(true);
      expect(validateS3BucketName('a-b').valid).toBe(true);
    });

    it('rejects empty bucket name', () => {
      const result = validateS3BucketName('');
      expect(result.valid).toBe(false);
      expect(result.error).toContain('required');
    });

    it('rejects bucket names shorter than 3 chars', () => {
      const result = validateS3BucketName('ab');
      expect(result.valid).toBe(false);
      expect(result.error).toContain('3-63');
    });

    it('rejects bucket names longer than 63 chars', () => {
      const result = validateS3BucketName('a'.repeat(64));
      expect(result.valid).toBe(false);
      expect(result.error).toContain('3-63');
    });

    it('rejects uppercase letters', () => {
      const result = validateS3BucketName('MyBucket');
      expect(result.valid).toBe(false);
    });

    it('rejects consecutive periods', () => {
      const result = validateS3BucketName('my..bucket');
      expect(result.valid).toBe(false);
      expect(result.error).toContain('consecutive periods');
    });

    it('rejects IP address format', () => {
      const result = validateS3BucketName('192.168.1.1');
      expect(result.valid).toBe(false);
      expect(result.error).toContain('IP address');
    });
  });

  describe('validateGlueDatabaseName', () => {
    it('accepts valid database names', () => {
      expect(validateGlueDatabaseName('my_database').valid).toBe(true);
      expect(validateGlueDatabaseName('db123').valid).toBe(true);
      expect(validateGlueDatabaseName('a').valid).toBe(true);
      expect(validateGlueDatabaseName('test_db_01').valid).toBe(true);
    });

    it('rejects empty name', () => {
      const result = validateGlueDatabaseName('');
      expect(result.valid).toBe(false);
      expect(result.error).toContain('required');
    });

    it('rejects names longer than 255 chars', () => {
      const result = validateGlueDatabaseName('a'.repeat(256));
      expect(result.valid).toBe(false);
      expect(result.error).toContain('1-255');
    });

    it('rejects uppercase letters', () => {
      const result = validateGlueDatabaseName('MyDatabase');
      expect(result.valid).toBe(false);
      expect(result.error).toContain('lowercase');
    });

    it('rejects hyphens', () => {
      const result = validateGlueDatabaseName('my-database');
      expect(result.valid).toBe(false);
    });

    it('rejects spaces', () => {
      const result = validateGlueDatabaseName('my database');
      expect(result.valid).toBe(false);
    });
  });

  describe('validateTableBucketArn', () => {
    it('accepts valid ARN', () => {
      const result = validateTableBucketArn('arn:aws:s3tables:us-east-1:123456789012:bucket/my-bucket');
      expect(result.valid).toBe(true);
    });

    it('rejects empty ARN', () => {
      const result = validateTableBucketArn('');
      expect(result.valid).toBe(false);
      expect(result.error).toContain('required');
    });

    it('rejects invalid ARN format', () => {
      const result = validateTableBucketArn('arn:aws:s3:us-east-1:123456789012:bucket/my-bucket');
      expect(result.valid).toBe(false);
      expect(result.error).toContain('Invalid table bucket ARN');
    });

    it('rejects ARN with wrong account ID length', () => {
      const result = validateTableBucketArn('arn:aws:s3tables:us-east-1:12345:bucket/my-bucket');
      expect(result.valid).toBe(false);
    });
  });

  describe('validateAwsRegion', () => {
    it('accepts valid regions', () => {
      expect(validateAwsRegion('us-east-1').valid).toBe(true);
      expect(validateAwsRegion('eu-west-1').valid).toBe(true);
      expect(validateAwsRegion('ap-southeast-1').valid).toBe(true);
    });

    it('rejects empty region', () => {
      const result = validateAwsRegion('');
      expect(result.valid).toBe(false);
      expect(result.error).toContain('required');
    });

    it('rejects invalid region', () => {
      const result = validateAwsRegion('us-invalid-99');
      expect(result.valid).toBe(false);
      expect(result.error).toContain('Invalid');
    });
  });

  describe('validateIamRoleArn', () => {
    it('accepts valid IAM Role ARN', () => {
      const result = validateIamRoleArn('arn:aws:iam::123456789012:role/MyRole');
      expect(result.valid).toBe(true);
    });

    it('accepts empty ARN (optional field)', () => {
      const result = validateIamRoleArn('');
      expect(result.valid).toBe(true);
    });

    it('rejects invalid IAM Role ARN format', () => {
      const result = validateIamRoleArn('arn:aws:iam::12345:role/MyRole');
      expect(result.valid).toBe(false);
      expect(result.error).toContain('Invalid IAM Role ARN');
    });

    it('accepts role ARN with path', () => {
      const result = validateIamRoleArn('arn:aws:iam::123456789012:role/service-role/MyRole');
      expect(result.valid).toBe(true);
    });
  });

  describe('validateS3PathPrefix', () => {
    it('accepts empty prefix', () => {
      expect(validateS3PathPrefix('').valid).toBe(true);
    });

    it('accepts valid prefix', () => {
      expect(validateS3PathPrefix('iceberg/tables').valid).toBe(true);
    });

    it('rejects prefix longer than 512 chars', () => {
      const result = validateS3PathPrefix('a'.repeat(513));
      expect(result.valid).toBe(false);
      expect(result.error).toContain('0-512');
    });
  });

  describe('validateIcebergConfig (full form validation)', () => {
    it('returns error when no destination type selected', () => {
      const errors = validateIcebergConfig(makeConfig());
      expect(errors.destinationType).toBeDefined();
    });

    it('returns no errors for valid Standard S3 config', () => {
      const errors = validateIcebergConfig(makeConfig({
        destinationType: 'iceberg_s3',
        s3Bucket: 'my-valid-bucket',
        s3PathPrefix: 'data',
        awsRegion: 'us-east-1',
        glueDatabaseName: 'my_db',
        awsAccessKeyId: 'AKIAIOSFODNN7EXAMPLE',
        awsSecretAccessKey: 'secret',
        useIamRole: false,
      }));
      expect(Object.keys(errors)).toHaveLength(0);
    });

    it('returns no errors for valid S3 Tables config', () => {
      const errors = validateIcebergConfig(makeConfig({
        destinationType: 'iceberg_s3_tables',
        tableBucketArn: 'arn:aws:s3tables:us-east-1:123456789012:bucket/my-bucket',
        awsRegion: 'us-east-1',
        glueDatabaseName: 'my_db',
        awsAccessKeyId: 'AKIAIOSFODNN7EXAMPLE',
        awsSecretAccessKey: 'secret',
        useIamRole: false,
      }));
      expect(Object.keys(errors)).toHaveLength(0);
    });

    it('returns no errors for valid IAM Role config', () => {
      const errors = validateIcebergConfig(makeConfig({
        destinationType: 'iceberg_s3',
        s3Bucket: 'my-valid-bucket',
        awsRegion: 'us-east-1',
        glueDatabaseName: 'my_db',
        awsRoleArn: 'arn:aws:iam::123456789012:role/MyRole',
        useIamRole: true,
      }));
      expect(Object.keys(errors)).toHaveLength(0);
    });

    it('requires IAM Role ARN when useIamRole is true', () => {
      const errors = validateIcebergConfig(makeConfig({
        destinationType: 'iceberg_s3',
        s3Bucket: 'my-valid-bucket',
        awsRegion: 'us-east-1',
        glueDatabaseName: 'my_db',
        awsRoleArn: '',
        useIamRole: true,
      }));
      expect(errors.awsRoleArn).toBeDefined();
    });

    it('requires access keys when useIamRole is false', () => {
      const errors = validateIcebergConfig(makeConfig({
        destinationType: 'iceberg_s3',
        s3Bucket: 'my-valid-bucket',
        awsRegion: 'us-east-1',
        glueDatabaseName: 'my_db',
        awsAccessKeyId: '',
        awsSecretAccessKey: '',
        useIamRole: false,
      }));
      expect(errors.awsAccessKeyId).toBeDefined();
      expect(errors.awsSecretAccessKey).toBeDefined();
    });
  });
});
