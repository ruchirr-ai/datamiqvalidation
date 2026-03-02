# KMS Encryption Setup Guide

Complete guide to setting up AWS KMS encryption for all DataMIQ credentials.

## Overview

DataMIQ uses AWS KMS (Key Management Service) to encrypt all sensitive credentials:
- AWS Access Keys & Secret Keys
- GCP Service Account JSON
- GCP HMAC Access & Secret Keys
- Database passwords
- Connection credentials

**Architecture:**
1. KMS Key ARN is stored in AWS Secrets Manager under secret name `datamiq`
2. The secret contains JSON: `{"kms_arn": "arn:aws:kms:REGION:ACCOUNT:key/KEY_ID"}`
3. All encryption/decryption uses this KMS key
4. Graceful fallback for development environments without AWS

---

## Prerequisites

- AWS Account with appropriate permissions
- AWS CLI installed and configured
- Python environment with boto3

---

## Step 1: Create KMS Key

### Option A: AWS Console

1. Go to [AWS KMS Console](https://console.aws.amazon.com/kms)
2. Click **Create key**
3. Configure key:
   - Key type: **Symmetric**
   - Key usage: **Encrypt and decrypt**
   - Advanced options: Leave defaults
4. Click **Next**
5. Add alias: `datamiq-encryption-key`
6. Add description: "DataMIQ credential encryption key"
7. Click **Next**
8. Define key administrators:
   - Select IAM users/roles that can manage the key
   - Enable key deletion (optional, for non-production)
9. Click **Next**
10. Define key usage permissions:
    - Select IAM roles that DataMIQ uses (EC2 role, ECS task role, etc.)
    - Check: **Encrypt**, **Decrypt**, **DescribeKey**
11. Click **Next**, review, and **Finish**
12. Copy the **Key ARN** (format: `arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012`)

### Option B: AWS CLI

```bash
# Create KMS key
aws kms create-key \
  --description "DataMIQ credential encryption key" \
  --key-usage ENCRYPT_DECRYPT \
  --origin AWS_KMS

# Output will contain KeyId - save this
# Example output:
# {
#   "KeyMetadata": {
#     "KeyId": "12345678-1234-1234-1234-123456789012",
#     "Arn": "arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"
#   }
# }

# Create alias for easier reference
aws kms create-alias \
  --alias-name alias/datamiq-encryption-key \
  --target-key-id 12345678-1234-1234-1234-123456789012

# Get the full ARN
aws kms describe-key --key-id alias/datamiq-encryption-key --query 'KeyMetadata.Arn' --output text
```

---

## Step 2: Store KMS ARN in Secrets Manager

### Option A: AWS Console

1. Go to [AWS Secrets Manager Console](https://console.aws.amazon.com/secretsmanager)
2. Click **Store a new secret**
3. Select **Other type of secret**
4. In **Key/value pairs**, click **Plaintext** tab
5. Paste this JSON (replace with your KMS ARN):
   ```json
   {
     "kms_arn": "arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"
   }
   ```
6. Click **Next**
7. Secret name: `datamiq`
8. Description: "DataMIQ KMS key ARN for credential encryption"
9. Click **Next**
10. Disable automatic rotation (not needed for this secret)
11. Click **Next**, review, and **Store**

### Option B: AWS CLI

```bash
# Store KMS ARN in Secrets Manager
aws secretsmanager create-secret \
  --name datamiq \
  --description "DataMIQ KMS key ARN for credential encryption" \
  --secret-string '{"kms_arn":"arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"}'

# Verify
aws secretsmanager get-secret-value --secret-id datamiq --query 'SecretString' --output text
```

---

## Step 3: Configure IAM Permissions

DataMIQ needs the following IAM permissions:

### Required IAM Policy

Create an IAM policy named `DataMIQ-Encryption-Policy`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "KMSEncryptDecrypt",
      "Effect": "Allow",
      "Action": [
        "kms:Encrypt",
        "kms:Decrypt",
        "kms:DescribeKey",
        "kms:GenerateDataKey"
      ],
      "Resource": "arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"
    },
    {
      "Sid": "SecretsManagerRead",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:123456789012:secret:datamiq-*"
    }
  ]
}
```

### Create Policy via AWS CLI

```bash
# Save the policy to a file
cat > datamiq-encryption-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "KMSEncryptDecrypt",
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
      "Sid": "SecretsManagerRead",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:123456789012:secret:datamiq-*"
    }
  ]
}
EOF

# Create the policy
aws iam create-policy \
  --policy-name DataMIQ-Encryption-Policy \
  --policy-document file://datamiq-encryption-policy.json \
  --description "Permissions for DataMIQ to encrypt/decrypt credentials using KMS"

# Attach to your IAM role (replace with your role name)
aws iam attach-role-policy \
  --role-name DataMIQ-EC2-Role \
  --policy-arn arn:aws:iam::123456789012:policy/DataMIQ-Encryption-Policy
```

### For EC2 Instances

If DataMIQ runs on EC2, attach the policy to the EC2 instance role:

```bash
# List instance roles
aws iam list-roles --query 'Roles[?contains(RoleName, `EC2`)].RoleName'

# Attach policy to role
aws iam attach-role-policy \
  --role-name YOUR-EC2-ROLE-NAME \
  --policy-arn arn:aws:iam::123456789012:policy/DataMIQ-Encryption-Policy
```

### For ECS/Fargate

If DataMIQ runs on ECS, attach the policy to the ECS task execution role:

```bash
# Attach policy to ECS task role
aws iam attach-role-policy \
  --role-name YOUR-ECS-TASK-ROLE-NAME \
  --policy-arn arn:aws:iam::123456789012:policy/DataMIQ-Encryption-Policy
```

### For Local Development

For local development, configure AWS credentials:

```bash
# Option 1: AWS CLI configure
aws configure

# Option 2: Environment variables
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1
```

---

## Step 4: Configure DataMIQ

### Environment Variables

Set these environment variables in your DataMIQ deployment:

```bash
# AWS Region (where KMS key and secret are located)
export AWS_REGION=us-east-1

# Secret name in AWS Secrets Manager (default: 'datamiq')
# Only change this if you want to use a different secret name
export ENCRYPTION_SECRET_NAME=datamiq

# Optional: For local development with AWS credentials
# export AWS_ACCESS_KEY_ID=your-access-key
# export AWS_SECRET_ACCESS_KEY=your-secret-key
```

**Note:** The `ENCRYPTION_SECRET_NAME` defaults to `datamiq`. You only need to set it if you want to use a different secret name.

### For Docker/Docker Compose

Add to `docker-compose.yml`:

```yaml
services:
  backend:
    environment:
      - AWS_REGION=us-east-1
      # For local dev with AWS credentials
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
```

### For Kubernetes

Create a ConfigMap:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: datamiq-config
data:
  AWS_REGION: "us-east-1"
```

---

## Step 5: Encrypt Existing Credentials

Run the migration script to encrypt existing plaintext credentials:

### Dry Run (Preview)

```bash
cd datamiq/backend
python scripts/encrypt_existing_credentials.py --dry-run
```

### Actual Encryption

```bash
# With confirmation prompt
python scripts/encrypt_existing_credentials.py

# Skip confirmation
python scripts/encrypt_existing_credentials.py --force
```

### Expected Output

```
================================================================================
CREDENTIAL ENCRYPTION SCRIPT
================================================================================
Mode: LIVE
================================================================================

Testing AWS KMS connectivity...
✓ AWS KMS connectivity verified

================================================================================
ENCRYPTING MIGRATION CREDENTIALS
================================================================================
Found 5 migrations to process

Processing Migration 1: BQ to Redshift Migration
  - Encrypting AWS Secret Access Key
  - Encrypting GCP HMAC Secret Key
  - Encrypting GCP Service Account JSON

...

✓ Migration credentials encrypted and committed to database

================================================================================
ENCRYPTING CONNECTION CREDENTIALS
================================================================================
Found 3 connections to process

Processing Connection 1: BigQuery Production
  - Encrypting service account JSON

...

✓ Connection credentials encrypted and committed to database

================================================================================
ENCRYPTION SUMMARY
================================================================================
Migrations processed: 5
Migrations encrypted: 5
Connections processed: 3
Connections encrypted: 3
Total fields encrypted: 15
Errors: 0
================================================================================

✓ All credentials encrypted successfully!
```

---

## Step 6: Verify Encryption

### Test Encryption/Decryption

```python
from services.unified_kms_service import get_unified_kms_service

kms = get_unified_kms_service()

# Encrypt
encrypted = kms.encrypt_credential(
    plaintext="my-secret-value",
    credential_type="aws_secret_key",
    resource_type="migration",
    resource_id=123
)
print(f"Encrypted: {encrypted[:50]}...")

# Decrypt
decrypted = kms.decrypt_credential(
    ciphertext=encrypted,
    credential_type="aws_secret_key",
    resource_type="migration",
    resource_id=123
)
print(f"Decrypted: {decrypted}")
```

### Check Database

```sql
-- Check if credentials are encrypted (base64-encoded, > 100 chars)
SELECT 
    id,
    migration_name,
    LENGTH(aws_secret_access_key_encrypted) as aws_key_length,
    LENGTH(service_account_json_encrypted) as sa_json_length
FROM migrations_bq_redshift
WHERE aws_secret_access_key_encrypted IS NOT NULL
   OR service_account_json_encrypted IS NOT NULL;
```

---

## Troubleshooting

### Error: "Secret 'datamiq' not found"

**Solution:** Create the secret in AWS Secrets Manager (see Step 2)

```bash
aws secretsmanager create-secret \
  --name datamiq \
  --secret-string '{"kms_arn":"YOUR-KMS-ARN"}'
```

### Error: "Access denied to KMS key"

**Solution:** Attach the IAM policy to your role (see Step 3)

```bash
aws iam attach-role-policy \
  --role-name YOUR-ROLE-NAME \
  --policy-arn arn:aws:iam::ACCOUNT:policy/DataMIQ-Encryption-Policy
```

### Error: "AWS credentials not configured"

**Solution:** 
- For EC2: Attach IAM role to instance
- For local dev: Run `aws configure` or set environment variables
- Verify: `aws sts get-caller-identity`

### Error: "KMS key is disabled"

**Solution:** Enable the KMS key

```bash
aws kms enable-key --key-id YOUR-KEY-ID
```

### Development Mode (No AWS)

DataMIQ gracefully falls back to storing credentials unencrypted if AWS is not configured. This is for local development only.

To force encryption in development:
1. Configure AWS credentials locally
2. Create KMS key and secret in your AWS account
3. Set `AWS_REGION` environment variable

---

## Security Best Practices

1. **Key Rotation**: Enable automatic key rotation for KMS key
   ```bash
   aws kms enable-key-rotation --key-id YOUR-KEY-ID
   ```

2. **Least Privilege**: Only grant KMS permissions to roles that need them

3. **Audit Logging**: Enable CloudTrail to log all KMS operations
   ```bash
   aws cloudtrail create-trail \
     --name datamiq-kms-audit \
     --s3-bucket-name your-audit-bucket
   ```

4. **Key Policies**: Use KMS key policies to restrict access
   ```bash
   aws kms put-key-policy \
     --key-id YOUR-KEY-ID \
     --policy-name default \
     --policy file://key-policy.json
   ```

5. **Backup**: Regularly backup your database (encrypted credentials can't be recovered if KMS key is deleted)

6. **Monitoring**: Set up CloudWatch alarms for KMS usage anomalies

---

## Cost Estimation

AWS KMS pricing (as of 2024):
- KMS key: $1/month per key
- API requests: $0.03 per 10,000 requests
- Secrets Manager: $0.40/month per secret + $0.05 per 10,000 API calls

**Estimated monthly cost for DataMIQ:**
- 1 KMS key: $1.00
- 1 Secret: $0.40
- ~10,000 encrypt/decrypt operations: $0.03
- **Total: ~$1.50/month**

---

## Migration Checklist

- [ ] Create KMS key in AWS
- [ ] Store KMS ARN in Secrets Manager secret "datamiq"
- [ ] Create and attach IAM policy
- [ ] Set AWS_REGION environment variable
- [ ] Test KMS connectivity
- [ ] Run encryption script with --dry-run
- [ ] Backup database
- [ ] Run encryption script (live)
- [ ] Verify encryption in database
- [ ] Test application functionality
- [ ] Enable KMS key rotation
- [ ] Set up CloudTrail logging
- [ ] Document KMS key ARN for team

---

## Support

For issues or questions:
1. Check CloudWatch Logs for error details
2. Verify IAM permissions with AWS Policy Simulator
3. Test KMS key access: `aws kms describe-key --key-id YOUR-KEY-ID`
4. Check Secrets Manager: `aws secretsmanager get-secret-value --secret-id datamiq`
