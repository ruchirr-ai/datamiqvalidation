# AWS KMS Encryption Setup Guide

## Overview

This guide explains how to set up and use AWS KMS encryption for DataMIQ. The application uses AWS KMS for encrypting sensitive data (passwords, connection strings, AWS secrets) with the KMS key ID stored in AWS Secrets Manager.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Application Code                         │
│  (encrypt/decrypt operations)                                │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│           KMS Encryption Service                             │
│  - Fetches KMS key ID from Secrets Manager                   │
│  - Calls AWS KMS for encryption/decryption                   │
│  - Includes encryption context for audit trail               │
└────────────────┬────────────────────────────────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
┌──────────────┐  ┌──────────────┐
│   AWS KMS    │  │   Secrets    │
│              │  │   Manager    │
│ (Encryption) │  │ (Key ID)     │
└──────────────┘  └──────────────┘
```

## Prerequisites

1. AWS Account with appropriate permissions
2. AWS CLI configured with credentials
3. Python environment with boto3 installed

## Step 1: Create KMS Key

### Using AWS Console

1. Navigate to AWS KMS Console
2. Click "Create key"
3. Select "Symmetric" key type
4. Select "Encrypt and decrypt" key usage
5. Configure key:
   - Alias: `datamiq-encryption-key`
   - Description: `Encryption key for DataMIQ sensitive data`
6. Define key administrative permissions (select IAM users/roles)
7. Define key usage permissions (select IAM roles for your application)
8. Review and create key
9. Copy the Key ID (format: `arn:aws:kms:region:account:key/key-id`)

### Using AWS CLI

```bash
# Create KMS key
aws kms create-key \
  --description "DataMIQ encryption key" \
  --key-usage ENCRYPT_DECRYPT \
  --origin AWS_KMS \
  --region us-east-1

# Create alias for easier reference
aws kms create-alias \
  --alias-name alias/datamiq-encryption-key \
  --target-key-id <KEY_ID_FROM_PREVIOUS_COMMAND> \
  --region us-east-1
```

## Step 2: Store KMS Key ID in Secrets Manager

### Using AWS Console

1. Navigate to AWS Secrets Manager Console
2. Click "Store a new secret"
3. Select "Other type of secret"
4. Add key-value pair:
   - Key: `kms_key_id`
   - Value: `<YOUR_KMS_KEY_ID>` (the full ARN)
5. Secret name: `datamiq/encryption/kms-key-id`
6. Description: `KMS key ID for DataMIQ encryption`
7. Configure automatic rotation: Disabled (key ID doesn't change)
8. Review and store

### Using AWS CLI

```bash
# Store KMS key ID in Secrets Manager
aws secretsmanager create-secret \
  --name datamiq/encryption/kms-key-id \
  --description "KMS key ID for DataMIQ encryption" \
  --secret-string '{"kms_key_id":"arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"}' \
  --region us-east-1
```

## Step 3: Configure IAM Permissions

Your application's IAM role needs permissions to:
1. Access the KMS key for encryption/decryption
2. Read the secret from Secrets Manager

### KMS Policy

Attach this policy to your application's IAM role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowKMSEncryptDecrypt",
      "Effect": "Allow",
      "Action": [
        "kms:Encrypt",
        "kms:Decrypt",
        "kms:DescribeKey",
        "kms:GenerateDataKey"
      ],
      "Resource": "arn:aws:kms:us-east-1:123456789012:key/*"
    }
  ]
}
```

### Secrets Manager Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowSecretsManagerRead",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:123456789012:secret:datamiq/encryption/*"
    }
  ]
}
```

### Combined Policy Example

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowKMSEncryptDecrypt",
      "Effect": "Allow",
      "Action": [
        "kms:Encrypt",
        "kms:Decrypt",
        "kms:DescribeKey",
        "kms:GenerateDataKey"
      ],
      "Resource": "arn:aws:kms:us-east-1:123456789012:key/*"
    },
    {
      "Sid": "AllowSecretsManagerRead",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:123456789012:secret:datamiq/encryption/*"
    }
  ]
}
```

## Step 4: Configure Application

Update your `.env` file:

```bash
# AWS Region
AWS_REGION=us-east-1

# KMS Encryption Configuration
ENCRYPTION_SECRET_NAME=datamiq/encryption/kms-key-id
ENCRYPTION_AWS_REGION=us-east-1
```

## Step 5: Test KMS Encryption

### Test Script

```python
# test_kms_encryption.py
from services.kms_encryption_service import get_kms_encryption_service

# Initialize service
kms_service = get_kms_encryption_service()

# Test data
test_secret = "my-super-secret-password"
encryption_context = {
    'test': 'true',
    'purpose': 'testing'
}

# Encrypt
print("Encrypting...")
encrypted = kms_service.encrypt(test_secret, encryption_context)
print(f"Encrypted: {encrypted[:50]}...")

# Decrypt
print("\nDecrypting...")
decrypted = kms_service.decrypt(encrypted, encryption_context)
print(f"Decrypted: {decrypted}")

# Verify
assert decrypted == test_secret
print("\n✓ Encryption/Decryption test passed!")
```

Run the test:

```bash
cd backend
source .venv/bin/activate
python test_kms_encryption.py
```

## Step 6: Migrate Existing Data

If you have existing data encrypted with the old Fernet encryption, run the migration script:

```bash
cd backend
source .venv/bin/activate

# Dry run first (no changes)
python scripts/migrate_to_kms_encryption.py --dry-run

# Review the output, then run for real
python scripts/migrate_to_kms_encryption.py
```

The migration script will:
1. Re-encrypt all AWS secret keys in migrations
2. Encrypt connection parameters (first-time encryption)
3. Verify all encryption/decryption operations
4. Update the database with new encrypted values

## Usage in Code

### Encrypting Data

```python
from services.kms_encryption_service import get_kms_encryption_service

# Get service instance
kms_service = get_kms_encryption_service()

# Encrypt with context for audit trail
encryption_context = {
    'migration_id': str(migration_id),
    'field': 'aws_secret_access_key',
    'created_at': datetime.utcnow().isoformat()
}

encrypted_value = kms_service.encrypt(
    plaintext_value,
    encryption_context
)

# Store encrypted_value in database
```

### Decrypting Data

```python
from services.kms_encryption_service import get_kms_encryption_service

# Get service instance
kms_service = get_kms_encryption_service()

# Decrypt with same context used for encryption
encryption_context = {
    'migration_id': str(migration_id),
    'field': 'aws_secret_access_key'
}

plaintext_value = kms_service.decrypt(
    encrypted_value,
    encryption_context
)

# Use plaintext_value
```

## Encryption Context

Encryption context provides:
- **Additional security**: Context must match for decryption to succeed
- **Audit trail**: Context is logged in CloudTrail for compliance
- **Key rotation**: Helps identify what data needs re-encryption

### Recommended Context Fields

- `migration_id`: For migration-related secrets
- `connection_id`: For connection credentials
- `workspace_id`: For workspace-scoped data
- `field`: Name of the field being encrypted
- `created_at` or `updated_at`: Timestamp for tracking

## Key Rotation

To rotate the KMS key:

1. Create a new KMS key (Step 1)
2. Update the secret in Secrets Manager with new key ID (Step 2)
3. Run the rotation script:

```python
from services.kms_encryption_service import get_kms_encryption_service

kms_service = get_kms_encryption_service()

# Re-encrypt data with new key
new_encrypted = kms_service.rotate_key(
    old_encrypted_value,
    encryption_context
)
```

## Monitoring and Logging

### CloudWatch Logs

All KMS operations are logged to CloudWatch:
- Encryption requests
- Decryption requests
- Errors and failures
- Key access patterns

### CloudTrail

AWS CloudTrail logs all KMS API calls:
- Who accessed the key
- When it was accessed
- What encryption context was used
- Success/failure status

### Metrics to Monitor

- KMS API call count
- Encryption/decryption latency
- Error rates
- Secrets Manager access patterns

## Troubleshooting

### Error: "AccessDeniedException"

**Cause**: IAM role doesn't have permission to use KMS key or access Secrets Manager

**Solution**:
1. Verify IAM policies are attached to the role
2. Check KMS key policy allows the role
3. Verify Secrets Manager resource policy

### Error: "NotFoundException: Secrets Manager can't find the specified secret"

**Cause**: Secret name doesn't match or secret doesn't exist

**Solution**:
1. Verify secret name in `.env` matches Secrets Manager
2. Check AWS region is correct
3. Verify secret exists: `aws secretsmanager describe-secret --secret-id datamiq/encryption/kms-key-id`

### Error: "InvalidCiphertextException"

**Cause**: Encrypted data was tampered with or encryption context doesn't match

**Solution**:
1. Verify encryption context matches what was used during encryption
2. Check if data was corrupted in database
3. Re-encrypt the data if necessary

### Error: "KMSInvalidStateException"

**Cause**: KMS key is disabled or pending deletion

**Solution**:
1. Check key status in KMS console
2. Enable the key if disabled
3. Cancel deletion if pending

## Security Best Practices

1. **Use IAM Roles**: Never use access keys in production
2. **Least Privilege**: Grant minimum required permissions
3. **Encryption Context**: Always use encryption context for audit trail
4. **Key Rotation**: Rotate KMS keys annually
5. **Monitor Access**: Set up CloudWatch alarms for unusual KMS activity
6. **Separate Keys**: Use different keys for different environments (dev/staging/prod)
7. **Backup**: Enable automatic key backup in KMS
8. **Audit**: Regularly review CloudTrail logs for KMS access

## Cost Considerations

### KMS Pricing (as of 2024)

- Key storage: $1/month per key
- API requests:
  - First 20,000 requests/month: Free
  - Additional requests: $0.03 per 10,000 requests

### Secrets Manager Pricing

- Secret storage: $0.40/month per secret
- API calls: $0.05 per 10,000 API calls

### Cost Optimization

- Cache decrypted values in memory (with TTL)
- Batch encryption/decryption operations
- Use encryption context to reduce unnecessary decryptions
- Monitor API call patterns

## References

- [AWS KMS Documentation](https://docs.aws.amazon.com/kms/)
- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/)
- [KMS Best Practices](https://docs.aws.amazon.com/kms/latest/developerguide/best-practices.html)
- [Encryption Context](https://docs.aws.amazon.com/kms/latest/developerguide/concepts.html#encrypt_context)
