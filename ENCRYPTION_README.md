# DataMIQ Credential Encryption

All sensitive credentials in DataMIQ are automatically encrypted using AWS KMS before being stored in the database.

## What Gets Encrypted

✅ **Automatically encrypted:**
- AWS Secret Access Keys
- GCP Service Account JSON
- GCP HMAC Secret Keys  
- Database/Connection passwords

❌ **Not encrypted (not sensitive):**
- AWS Access Key IDs (like usernames)
- GCP HMAC Access Keys (like usernames)
- IAM Role ARNs (public identifiers)

## Setup (One-Time)

### 1. Create KMS Key

```bash
aws kms create-key --description "DataMIQ credential encryption"
```

### 2. Store KMS ARN in Secrets Manager

```bash
aws secretsmanager create-secret \
  --name datamiq \
  --secret-string '{"kms_arn":"arn:aws:kms:REGION:ACCOUNT:key/YOUR_KEY_ID"}'
```

### 3. Set Environment Variables

```bash
export AWS_REGION=us-east-1
export ENCRYPTION_SECRET_NAME=datamiq  # Optional, defaults to 'datamiq'
```

### 4. Grant IAM Permissions

Your IAM user/role needs:
- `kms:Encrypt`, `kms:Decrypt` on the KMS key
- `secretsmanager:GetSecretValue` on the "datamiq" secret

See `iam-policies/datamiq-encryption-policy.json` for the full policy.

### 5. Encrypt Existing Data

```bash
cd datamiq/backend

# Preview what will be encrypted
python scripts/encrypt_existing_credentials.py --dry-run

# Encrypt existing plaintext credentials
python scripts/encrypt_existing_credentials.py
```

## How It Works

### When Creating/Updating Migrations

1. User enters credentials in the UI (AWS keys, GCP service account, etc.)
2. Frontend sends credentials to backend API
3. **Backend automatically encrypts** sensitive fields using KMS
4. Encrypted data is stored in database
5. User never sees the encrypted values

### When Running Migrations

1. Backend reads encrypted credentials from database
2. **Backend automatically decrypts** using KMS
3. Decrypted credentials are used for AWS/GCP operations
4. Credentials are never logged or exposed

### Development Mode (No AWS)

If AWS credentials aren't configured:
- Credentials are stored as plaintext (with warning logs)
- Application continues to work normally
- This is for local development only

## Configuration

### Secret Name

The AWS Secrets Manager secret name is configured via environment variable:

```bash
export ENCRYPTION_SECRET_NAME=datamiq
```

**Default:** `datamiq`

You only need to set this if you want to use a different secret name. This is infrastructure-level config — all migrations use the same KMS setup.

### AWS Region

```bash
export AWS_REGION=us-east-1
```

Must match the region where your KMS key and secret are located.

## Testing

Verify your setup:

```bash
cd datamiq/backend
python test_kms_setup.py
```

This will:
- Test AWS connectivity
- Encrypt/decrypt test data
- Verify all credential types work
- Confirm graceful fallback

## Security Features

1. **Encryption at Rest**: All sensitive data encrypted in database
2. **Encryption in Transit**: HTTPS for API calls
3. **Audit Logging**: All encrypt/decrypt operations logged with context
4. **Graceful Fallback**: Handles legacy plaintext data
5. **No Plaintext Logs**: Credentials never appear in logs

## Cost

~$1.50/month:
- KMS key: $1.00/month
- Secrets Manager secret: $0.40/month  
- API calls: $0.03/month (estimated)

## Troubleshooting

### "Secret 'datamiq' not found"

Create the secret:
```bash
aws secretsmanager create-secret --name datamiq \
  --secret-string '{"kms_arn":"YOUR_KMS_ARN"}'
```

### "Access denied to KMS key"

Attach the IAM policy:
```bash
aws iam attach-role-policy \
  --role-name YOUR_ROLE \
  --policy-arn arn:aws:iam::ACCOUNT:policy/DataMIQ-Encryption-Policy
```

### "AWS credentials not configured"

For local development:
```bash
aws configure
# OR
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
```

## Documentation

- **Complete Setup Guide**: `KMS_ENCRYPTION_SETUP_GUIDE.md`
- **Quick Reference**: `KMS_ENCRYPTION_SUMMARY.md`
- **IAM Policy**: `iam-policies/datamiq-encryption-policy.json`

## Support

For detailed instructions and troubleshooting, see `KMS_ENCRYPTION_SETUP_GUIDE.md`.
