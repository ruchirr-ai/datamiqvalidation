/**
 * Client-side validators for Iceberg migration configuration fields.
 * Requirements: 1.2, 1.3, 1.5, 1.6, 9.4
 */

/** AWS regions allowed for Iceberg destinations */
export const AWS_REGIONS = [
  { value: 'us-east-1', label: 'US East (N. Virginia)' },
  { value: 'us-east-2', label: 'US East (Ohio)' },
  { value: 'us-west-1', label: 'US West (N. California)' },
  { value: 'us-west-2', label: 'US West (Oregon)' },
  { value: 'af-south-1', label: 'Africa (Cape Town)' },
  { value: 'ap-east-1', label: 'Asia Pacific (Hong Kong)' },
  { value: 'ap-south-1', label: 'Asia Pacific (Mumbai)' },
  { value: 'ap-south-2', label: 'Asia Pacific (Hyderabad)' },
  { value: 'ap-southeast-1', label: 'Asia Pacific (Singapore)' },
  { value: 'ap-southeast-2', label: 'Asia Pacific (Sydney)' },
  { value: 'ap-southeast-3', label: 'Asia Pacific (Jakarta)' },
  { value: 'ap-northeast-1', label: 'Asia Pacific (Tokyo)' },
  { value: 'ap-northeast-2', label: 'Asia Pacific (Seoul)' },
  { value: 'ap-northeast-3', label: 'Asia Pacific (Osaka)' },
  { value: 'ca-central-1', label: 'Canada (Central)' },
  { value: 'eu-central-1', label: 'Europe (Frankfurt)' },
  { value: 'eu-central-2', label: 'Europe (Zurich)' },
  { value: 'eu-west-1', label: 'Europe (Ireland)' },
  { value: 'eu-west-2', label: 'Europe (London)' },
  { value: 'eu-west-3', label: 'Europe (Paris)' },
  { value: 'eu-south-1', label: 'Europe (Milan)' },
  { value: 'eu-south-2', label: 'Europe (Spain)' },
  { value: 'eu-north-1', label: 'Europe (Stockholm)' },
  { value: 'me-south-1', label: 'Middle East (Bahrain)' },
  { value: 'me-central-1', label: 'Middle East (UAE)' },
  { value: 'sa-east-1', label: 'South America (São Paulo)' },
];

export const ALLOWED_AWS_REGION_VALUES = AWS_REGIONS.map(r => r.value);

export interface ValidationResult {
  valid: boolean;
  error?: string;
}

/**
 * Validates S3 bucket name format.
 * Rules: 3-63 chars, lowercase letters/numbers/hyphens, starts/ends with letter or number,
 * no consecutive periods, not formatted as IP address.
 */
export function validateS3BucketName(name: string): ValidationResult {
  if (!name) {
    return { valid: false, error: 'S3 bucket name is required' };
  }
  if (name.length < 3 || name.length > 63) {
    return { valid: false, error: 'S3 bucket name must be 3-63 characters' };
  }
  if (!/^[a-z0-9][a-z0-9.-]*[a-z0-9]$/.test(name)) {
    return { valid: false, error: 'Bucket name must start and end with a lowercase letter or number' };
  }
  if (/[A-Z]/.test(name)) {
    return { valid: false, error: 'Bucket name must be lowercase' };
  }
  if (/\.\./.test(name)) {
    return { valid: false, error: 'Bucket name cannot contain consecutive periods' };
  }
  if (/^\d+\.\d+\.\d+\.\d+$/.test(name)) {
    return { valid: false, error: 'Bucket name cannot be formatted as an IP address' };
  }
  if (!/^[a-z0-9][a-z0-9.-]*[a-z0-9]$/.test(name) && name.length >= 3) {
    return { valid: false, error: 'Bucket name can only contain lowercase letters, numbers, hyphens, and periods' };
  }
  return { valid: true };
}

/**
 * Validates AWS Glue Data Catalog database name.
 * Rules: 1-255 chars, lowercase alphanumeric and underscores only.
 */
export function validateGlueDatabaseName(name: string): ValidationResult {
  if (!name) {
    return { valid: false, error: 'Glue database name is required' };
  }
  if (name.length > 255) {
    return { valid: false, error: 'Glue database name must be 1-255 characters' };
  }
  if (!/^[a-z0-9_]+$/.test(name)) {
    return { valid: false, error: 'Glue database name must contain only lowercase letters, numbers, and underscores' };
  }
  return { valid: true };
}

/**
 * Validates S3 Table Bucket ARN format.
 * Pattern: arn:aws:s3tables:<region>:<account-id>:bucket/<bucket-name>
 */
export function validateTableBucketArn(arn: string): ValidationResult {
  if (!arn) {
    return { valid: false, error: 'Table bucket ARN is required' };
  }
  const arnPattern = /^arn:aws:s3tables:[a-z0-9-]+:\d{12}:bucket\/[a-z0-9][a-z0-9.-]*[a-z0-9]$/;
  if (!arnPattern.test(arn)) {
    return { valid: false, error: 'Invalid table bucket ARN format. Expected: arn:aws:s3tables:<region>:<account-id>:bucket/<bucket-name>' };
  }
  return { valid: true };
}

/**
 * Validates AWS region from allowed list.
 */
export function validateAwsRegion(region: string): ValidationResult {
  if (!region) {
    return { valid: false, error: 'AWS region is required' };
  }
  if (!ALLOWED_AWS_REGION_VALUES.includes(region)) {
    return { valid: false, error: 'Invalid AWS region selected' };
  }
  return { valid: true };
}

/**
 * Validates IAM Role ARN format.
 * Pattern: arn:aws:iam::<account-id>:role/<role-name>
 */
export function validateIamRoleArn(arn: string): ValidationResult {
  if (!arn) {
    // IAM Role ARN is optional (alternative to access keys)
    return { valid: true };
  }
  const arnPattern = /^arn:aws:iam::\d{12}:role\/[\w+=,.@/-]+$/;
  if (!arnPattern.test(arn)) {
    return { valid: false, error: 'Invalid IAM Role ARN format. Expected: arn:aws:iam::<account-id>:role/<role-name>' };
  }
  return { valid: true };
}

/**
 * Validates S3 path prefix.
 * Rules: 0-512 chars, no leading slash required.
 */
export function validateS3PathPrefix(prefix: string): ValidationResult {
  if (prefix.length > 512) {
    return { valid: false, error: 'S3 path prefix must be 0-512 characters' };
  }
  return { valid: true };
}

export type IcebergDestinationType = 'iceberg_s3' | 'iceberg_s3_tables';

export interface IcebergConfigData {
  destinationType: IcebergDestinationType | null;
  s3Bucket: string;
  s3PathPrefix: string;
  tableBucketArn: string;
  awsRegion: string;
  glueDatabaseName: string;
  awsAccessKeyId: string;
  awsSecretAccessKey: string;
  awsRoleArn: string;
  useIamRole: boolean;
}

export interface IcebergValidationErrors {
  destinationType?: string;
  s3Bucket?: string;
  s3PathPrefix?: string;
  tableBucketArn?: string;
  awsRegion?: string;
  glueDatabaseName?: string;
  awsAccessKeyId?: string;
  awsSecretAccessKey?: string;
  awsRoleArn?: string;
}

/**
 * Validates all Iceberg configuration fields based on the selected destination type.
 * Returns an object with field-level errors.
 */
export function validateIcebergConfig(config: IcebergConfigData): IcebergValidationErrors {
  const errors: IcebergValidationErrors = {};

  if (!config.destinationType) {
    errors.destinationType = 'Please select an Iceberg destination type';
    return errors;
  }

  // Validate fields based on destination type
  if (config.destinationType === 'iceberg_s3') {
    const bucketResult = validateS3BucketName(config.s3Bucket);
    if (!bucketResult.valid) errors.s3Bucket = bucketResult.error;

    const prefixResult = validateS3PathPrefix(config.s3PathPrefix);
    if (!prefixResult.valid) errors.s3PathPrefix = prefixResult.error;
  }

  if (config.destinationType === 'iceberg_s3_tables') {
    const arnResult = validateTableBucketArn(config.tableBucketArn);
    if (!arnResult.valid) errors.tableBucketArn = arnResult.error;
  }

  // Common fields
  const regionResult = validateAwsRegion(config.awsRegion);
  if (!regionResult.valid) errors.awsRegion = regionResult.error;

  const glueResult = validateGlueDatabaseName(config.glueDatabaseName);
  if (!glueResult.valid) errors.glueDatabaseName = glueResult.error;

  // Credential validation
  if (config.useIamRole) {
    const roleResult = validateIamRoleArn(config.awsRoleArn);
    if (!roleResult.valid) errors.awsRoleArn = roleResult.error;
    if (!config.awsRoleArn) {
      errors.awsRoleArn = 'IAM Role ARN is required when using IAM Role authentication';
    }
  } else {
    if (!config.awsAccessKeyId) {
      errors.awsAccessKeyId = 'AWS Access Key ID is required';
    }
    if (!config.awsSecretAccessKey) {
      errors.awsSecretAccessKey = 'AWS Secret Access Key is required';
    }
  }

  return errors;
}
