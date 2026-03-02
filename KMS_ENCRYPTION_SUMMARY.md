# KMS Encryption Implementation Summary

## What Was Built

A comprehensive KMS-based encryption system for all DataMIQ credentials with:

1. **Unified KMS Service** (`services/unified_kms_service.py`)
   - Centralized encryption/decryption for all credential types
   - Reads KMS ARN from AWS Secrets Manager secret "datamiq"
   - Graceful fallback for development without AWS
   - Audit logging with encryption context

2. **Migration Script** (`scripts/encrypt_existing_credentials.py`)
   - Encrypts all existing plaintext credentials
   - Supports dry-run mode
   - Comprehensive error handling and reporting

3. **Test Script** (`test_kms_setup.py`)
   - Verifies KMS setup is working
   - Tests all credential types
   - Validates encryption/decryption

4. **Documentation**
   - Complete setup guide (`KMS_ENCRYPTION_SETUP_GUIDE.md`)
   - IAM policy template (`iam-policies/datamiq-encryption-policy.json`)

---

## Credentials Encrypted

The system encrypts these credential types:

### In `migrations_bq_redshift` table:
- `aws_secret_access_key_encrypted` - AWS Secret Access Key
- `gcs_secret_key_encrypted` - GCP HMAC Secret Key
- `service_account_json_encrypted` - GCP Service Account JSON

### In `connections` table:
- `password` - Database/connection password
- `password_encrypted` - Encrypted password field
- `service_account_json` - GCP Service Account JSON

### NOT encrypted (stored as-is):
- `aws_access_key_id` - AWS Access Key ID (not secret)
- `gcs_access_key` - GCP HMAC Access Key (not secret)
- `iam_role_arn` - IAM Role ARN (not secret)
- `datasync_s3_role_arn` - DataSync IAM Role ARN (not secret)

---

## Configuration

The secret name is configured via environment variable, not per-migration:

```bash
# Default secret name (no need to set if using 'datamiq')
export ENCRYPTION_SECRET_NAME=datamiq

# AWS region
export AWS_REGION=us-east-1
```

This is infrastructure-level config — all migrations in your deployment use the same KMS setup. Users don't enter this during migration creation.

### 1. Create KMS Key

```bash
aws kms create-key --description "DataMIQ credential encryption"
# Save the KeyId from output
```

### 2. Store KMS ARN in Secrets Manager

```bash
aws secretsmanager create-secret \
  --name datamiq \
  --secret-string '{"kms_arn":"arn:aws:kms:REGION:ACCOUNT:key/KEY_ID"}'
```

### 3. Attach IAM Policy

```bash
aws iam attach-role-policy \
  --role-name YOUR-ROLE-NAME \
  --policy-arn arn:aws:iam::ACCOUNT:policy/DataMIQ-Encryption-Policy
```

### 4. Test Setup

```bash
cd datamiq/backend
python test_kms_setup.py
```

### 5. Encrypt Existing Credentials

```bash
# Dry run first
python scripts/encrypt_existing_credentials.py --dry-run

# Then encrypt
python scripts/encrypt_existing_credentials.py
```

---

## Required IAM Permissions

Your IAM role needs these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "kms:Encrypt",
        "kms:Decrypt",
        "kms:DescribeKey"
      ],
      "Resource": "arn:aws:kms:*:*:key/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:*:*:secret:datamiq-*"
    }
  ]
}
```

Full policy available in: `iam-policies/datamiq-encryption-policy.json`

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      DataMIQ Application                     │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         Unified KMS Service                            │ │
│  │  (services/unified_kms_service.py)                     │ │
│  │                                                         │ │
│  │  • encrypt_credential()                                │ │
│  │  • decrypt_credential()                                │ │
│  │  • Audit logging with context                          │ │
│  └────────────────────────────────────────────────────────┘ │
│                          │                                   │
└──────────────────────────┼───────────────────────────────────┘
                           │
                           ▼
         ┌─────────────────────────────────────┐
         │    AWS Secrets Manager              │
         │                                     │
         │  Secret: "datamiq"                  │
         │  {                                  │
         │    "kms_arn": "arn:aws:kms:..."    │
         │  }                                  │
         └─────────────────────────────────────┘
                           │
                           ▼
         ┌─────────────────────────────────────┐
         │         AWS KMS                     │
         │                                     │
         │  Key: datamiq-encryption-key        │
         │  • Encrypt                          │
         │  • Decrypt                          │
         │  • Automatic rotation (optional)    │
         └─────────────────────────────────────┘
```

---

## Usage Examples

### Encrypt a Credential

```python
from services.unified_kms_service import get_unified_kms_service

kms = get_unified_kms_service()

# Encrypt AWS secret key
encrypted = kms.encrypt_credential(
    plaintext="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    credential_type="aws_secret_key",
    resource_type="migration",
    resource_id=123
)

# Store in database
migration.aws_secret_access_key_encrypted = encrypted
```

### Decrypt a Credential

```python
# Retrieve from database
encrypted = migration.aws_secret_access_key_encrypted

# Decrypt
plaintext = kms.decrypt_credential(
    ciphertext=encrypted,
    credential_type="aws_secret_key",
    resource_type="migration",
    resource_id=123
)

# Use the plaintext credential
boto3.client('s3', aws_secret_access_key=plaintext)
```

### Check if Encrypted

```python
if kms.is_encrypted(migration.aws_secret_access_key_encrypted):
    print("Credential is encrypted")
else:
    print("Credential is plaintext (needs encryption)")
```

---

## Development Mode

For local development without AWS:

1. The service gracefully falls back to storing credentials unencrypted
2. Logs warnings about missing AWS configuration
3. Returns plaintext values as-is

To enable encryption in development:
```bash
export AWS_REGION=us-east-1
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
```

---

## Security Features

1. **Encryption Context**: Every encrypt/decrypt includes audit context
   - Service name
   - Credential type
   - Resource type and ID
   - Operation type

2. **Graceful Fallback**: Handles legacy plaintext data
   - Attempts decryption first
   - Falls back to plaintext if decryption fails
   - Logs warnings for audit trail

3. **Error Handling**: Comprehensive error messages
   - Missing AWS credentials
   - Missing KMS key
   - Permission denied
   - Invalid ciphertext

4. **Audit Logging**: All operations logged
   - Encryption events
   - Decryption events
   - Errors and warnings
   - Resource context

---

## Cost

Estimated monthly cost:
- KMS key: $1.00/month
- Secrets Manager secret: $0.40/month
- API calls (~10K/month): $0.03
- **Total: ~$1.50/month**

---

## Troubleshooting

### "Secret 'datamiq' not found"
```bash
aws secretsmanager create-secret --name datamiq \
  --secret-string '{"kms_arn":"YOUR-KMS-ARN"}'
```

### "Access denied to KMS key"
```bash
aws iam attach-role-policy \
  --role-name YOUR-ROLE \
  --policy-arn arn:aws:iam::ACCOUNT:policy/DataMIQ-Encryption-Policy
```

### "AWS credentials not configured"
```bash
# Verify credentials
aws sts get-caller-identity

# Configure if needed
aws configure
```

---

## Files Created

1. `services/unified_kms_service.py` - Main encryption service
2. `scripts/encrypt_existing_credentials.py` - Migration script
3. `test_kms_setup.py` - Setup verification
4. `KMS_ENCRYPTION_SETUP_GUIDE.md` - Complete setup guide
5. `iam-policies/datamiq-encryption-policy.json` - IAM policy template
6. `KMS_ENCRYPTION_SUMMARY.md` - This file

---

## Next Steps

1. ✅ Review the setup guide: `KMS_ENCRYPTION_SETUP_GUIDE.md`
2. ✅ Create KMS key in AWS
3. ✅ Store KMS ARN in Secrets Manager
4. ✅ Attach IAM policy to your role
5. ✅ Test setup: `python test_kms_setup.py`
6. ✅ Encrypt existing credentials: `python scripts/encrypt_existing_credentials.py`
7. ✅ Verify application works with encrypted credentials
8. ✅ Enable KMS key rotation
9. ✅ Set up CloudTrail logging

---

## Support

For detailed instructions, see: `KMS_ENCRYPTION_SETUP_GUIDE.md`

For IAM policy, see: `iam-policies/datamiq-encryption-policy.json`
