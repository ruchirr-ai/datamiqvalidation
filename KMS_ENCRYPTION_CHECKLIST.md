# KMS Encryption - Final Deployment Checklist

## ✅ Implementation Complete

All development work is done. This checklist is for deployment only.

## Pre-Deployment Setup (AWS)

### Step 1: Create KMS Key
```bash
# Option A: Using AWS Console
# 1. Go to AWS KMS Console
# 2. Click "Create key"
# 3. Select "Symmetric" and "Encrypt and decrypt"
# 4. Alias: datamiq-encryption-key
# 5. Configure permissions
# 6. Copy the Key ARN

# Option B: Using AWS CLI
aws kms create-key \
  --description "DataMIQ encryption key" \
  --key-usage ENCRYPT_DECRYPT \
  --region us-east-1

# Create alias
aws kms create-alias \
  --alias-name alias/datamiq-encryption-key \
  --target-key-id <KEY_ID> \
  --region us-east-1
```

- [ ] KMS key created
- [ ] Key alias created
- [ ] Key ARN copied

### Step 2: Store Key ID in Secrets Manager
```bash
# Replace with your actual KMS key ARN
aws secretsmanager create-secret \
  --name datamiq/encryption/kms-key-id \
  --description "KMS key ID for DataMIQ encryption" \
  --secret-string '{"kms_key_id":"arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"}' \
  --region us-east-1
```

- [ ] Secret created in Secrets Manager
- [ ] Secret name is `datamiq/encryption/kms-key-id`
- [ ] Secret contains correct KMS key ARN

### Step 3: Configure IAM Permissions
```bash
# Attach this policy to your application's IAM role
# Replace with your actual ARNs
```

Create policy file `kms-encryption-policy.json`:
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

```bash
# Create policy
aws iam create-policy \
  --policy-name DataMIQKMSEncryption \
  --policy-document file://kms-encryption-policy.json

# Attach to role
aws iam attach-role-policy \
  --role-name <YOUR_APP_ROLE> \
  --policy-arn arn:aws:iam::123456789012:policy/DataMIQKMSEncryption
```

- [ ] IAM policy created
- [ ] Policy attached to application role
- [ ] Permissions verified

### Step 4: Test AWS Access
```bash
# Test from application environment
cd backend
source .venv/bin/activate

# Test KMS access
python -c "
import boto3
kms = boto3.client('kms', region_name='us-east-1')
response = kms.describe_key(KeyId='alias/datamiq-encryption-key')
print('✓ KMS access works')
print(f'Key ARN: {response[\"KeyMetadata\"][\"Arn\"]}')
"

# Test Secrets Manager access
python -c "
import boto3
sm = boto3.client('secretsmanager', region_name='us-east-1')
response = sm.get_secret_value(SecretId='datamiq/encryption/kms-key-id')
print('✓ Secrets Manager access works')
"
```

- [ ] KMS access verified
- [ ] Secrets Manager access verified
- [ ] No permission errors

## Application Configuration

### Step 5: Update Environment Variables
```bash
# Edit .env file
cd backend
nano .env  # or vim .env

# Add these lines:
AWS_REGION=us-east-1
ENCRYPTION_SECRET_NAME=datamiq/encryption/kms-key-id
ENCRYPTION_AWS_REGION=us-east-1
```

- [ ] `.env` file updated
- [ ] AWS_REGION set correctly
- [ ] ENCRYPTION_SECRET_NAME set correctly
- [ ] ENCRYPTION_AWS_REGION set correctly

## Testing

### Step 6: Run Test Suite
```bash
cd backend
source .venv/bin/activate

# Run comprehensive test suite
python test_kms_encryption_complete.py
```

**Expected Output**:
```
✓ PASSED: Basic Encryption/Decryption
✓ PASSED: Encryption Context Validation
✓ PASSED: Migration AWS Secret
✓ PASSED: Connection Parameters
✓ PASSED: Error Handling

Total: 5 tests
Passed: 5
Failed: 0

✓ ALL TESTS PASSED
```

- [ ] All 5 tests passed
- [ ] No errors in output
- [ ] Test suite completed successfully

## Database Migration

### Step 7: Run Database Migration
```bash
cd backend
source .venv/bin/activate

# Check current migration version
alembic current

# Run migration
alembic upgrade head

# Verify migration
alembic current
```

**Expected Output**:
```
INFO  [alembic.runtime.migration] Running upgrade 016 -> 017, add encrypted connection params
✓ Added connection_params_encrypted column to connections table
✓ Added index on connection_params_encrypted
```

- [ ] Migration ran successfully
- [ ] Current version is 017
- [ ] No errors in output

### Step 8: Verify Database Schema
```bash
cd backend
source .venv/bin/activate

# Verify column exists
python -c "
from database import get_db
from models.connection import Connection
db = next(get_db())
conn = db.query(Connection).first()
if hasattr(conn, 'connection_params_encrypted'):
    print('✓ connection_params_encrypted column exists')
else:
    print('✗ Column missing - migration failed')
"
```

- [ ] Column exists in database
- [ ] No errors

## Data Migration

### Step 9: Run Data Migration (Dry Run)
```bash
cd backend
source .venv/bin/activate

# Dry run first (no changes)
python scripts/migrate_to_kms_encryption.py --dry-run
```

**Review Output**:
- Check number of migrations to migrate
- Check number of connections to encrypt
- Verify no errors
- Review test results

- [ ] Dry run completed successfully
- [ ] No errors in output
- [ ] Numbers look correct

### Step 10: Run Data Migration (Live)
```bash
cd backend
source .venv/bin/activate

# Run for real
python scripts/migrate_to_kms_encryption.py
```

**Expected Output**:
```
✓ KMS encryption service working correctly
Migration AWS Secrets: X succeeded, 0 failed
Connection Parameters: Y succeeded, 0 failed
Total: Z succeeded, 0 failed

✓ MIGRATION COMPLETED
```

- [ ] Migration completed successfully
- [ ] 0 failures
- [ ] All records migrated

### Step 11: Verify Data Migration
```bash
cd backend
source .venv/bin/activate

# Verify migrations
python -c "
from database import get_db
from models.bq_redshift_migration import MigrationBQRedshift
from services.kms_encryption_service import get_kms_encryption_service

db = next(get_db())
kms_service = get_kms_encryption_service()

migrations = db.query(MigrationBQRedshift).filter(
    MigrationBQRedshift.aws_secret_access_key_encrypted.isnot(None)
).all()

print(f'Found {len(migrations)} migrations with encrypted AWS secrets')

if migrations:
    m = migrations[0]
    context = {'migration_id': str(m.id), 'field': 'aws_secret_access_key'}
    decrypted = kms_service.decrypt(m.aws_secret_access_key_encrypted, context)
    print(f'✓ Successfully decrypted AWS secret for migration {m.id}')
"

# Verify connections
python -c "
from database import get_db
from models.connection import Connection
from services.kms_encryption_service import get_kms_encryption_service
import json

db = next(get_db())
kms_service = get_kms_encryption_service()

connections = db.query(Connection).filter(
    Connection.connection_params_encrypted.isnot(None)
).all()

print(f'Found {len(connections)} connections with encrypted params')

if connections:
    c = connections[0]
    context = {'connection_id': str(c.id), 'field': 'connection_params'}
    decrypted_json = kms_service.decrypt(c.connection_params_encrypted, context)
    params = json.loads(decrypted_json)
    print(f'✓ Successfully decrypted params for connection {c.id}')
"
```

- [ ] Migrations verified
- [ ] Connections verified
- [ ] Decryption works correctly

## Application Deployment

### Step 12: Deploy Application
```bash
# Stop application
sudo systemctl stop datamiq-backend

# Pull latest code (if using git)
git pull origin main

# Restart application
sudo systemctl start datamiq-backend

# Check status
sudo systemctl status datamiq-backend
```

- [ ] Application stopped
- [ ] Code updated
- [ ] Application started
- [ ] No errors in status

### Step 13: Check Application Logs
```bash
# Check logs for errors
sudo journalctl -u datamiq-backend -n 100 --no-pager

# Or check log file
tail -f backend/backend.log
```

- [ ] No errors in logs
- [ ] Application started successfully
- [ ] No KMS-related errors

## Smoke Tests

### Step 14: Test Create Migration
```bash
# Use API or UI to create a new migration with AWS credentials
# POST /api/migrations/bq-redshift/create
# Include aws_access_key_id and aws_secret_access_key
```

- [ ] Migration created successfully
- [ ] No errors
- [ ] AWS secret encrypted in database

### Step 15: Test Create Connection
```bash
# Use API or UI to create a new connection
# POST /api/connections
# Include connection_params with password
```

- [ ] Connection created successfully
- [ ] No errors
- [ ] Connection params encrypted in database

### Step 16: Test Execute Migration
```bash
# Execute an existing migration
# POST /api/migrations/bq-redshift/{id}/start
```

- [ ] Migration started successfully
- [ ] AWS secrets decrypted correctly
- [ ] No decryption errors
- [ ] Migration executes normally

### Step 17: Test Update Connection
```bash
# Update an existing connection
# PUT /api/connections/{id}
# Modify connection_params
```

- [ ] Connection updated successfully
- [ ] New params encrypted
- [ ] Connection still works

## Monitoring

### Step 18: Check CloudWatch Logs
```bash
# View recent logs
aws logs tail /aws/datamiq/backend --follow --filter-pattern "KMS"
```

- [ ] Logs show encryption operations
- [ ] Logs show decryption operations
- [ ] No error messages

### Step 19: Check CloudTrail
```bash
# View KMS API calls
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=ResourceType,AttributeValue=AWS::KMS::Key \
  --max-results 20
```

- [ ] Encrypt calls logged
- [ ] Decrypt calls logged
- [ ] Encryption context recorded
- [ ] No access denied errors

### Step 20: Monitor for 24 Hours
- [ ] Check logs every few hours
- [ ] Monitor error rates
- [ ] Check performance metrics
- [ ] Verify all operations work

## Post-Deployment

### Step 21: Set Up CloudWatch Alarms
```bash
# Create alarm for high KMS error rate
aws cloudwatch put-metric-alarm \
  --alarm-name datamiq-kms-high-error-rate \
  --alarm-description "KMS error rate > 1%" \
  --metric-name Errors \
  --namespace AWS/KMS \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold
```

- [ ] Error rate alarm created
- [ ] Latency alarm created
- [ ] Alarms tested

### Step 22: Document Deployment
- [ ] Update deployment log
- [ ] Document any issues encountered
- [ ] Update team wiki
- [ ] Notify team of completion

### Step 23: Schedule Follow-Up
- [ ] Schedule 1-week review
- [ ] Schedule 1-month review
- [ ] Plan key rotation schedule
- [ ] Plan security audit

## Success Criteria

All items must be checked:

- [ ] All AWS resources created
- [ ] All IAM permissions configured
- [ ] All tests passed
- [ ] Database migration successful
- [ ] Data migration successful (0 failures)
- [ ] Application deployed successfully
- [ ] All smoke tests passed
- [ ] CloudWatch logs show no errors
- [ ] CloudTrail shows KMS operations
- [ ] Monitoring set up
- [ ] Documentation updated

## If Something Goes Wrong

### Rollback Procedure

1. **Check logs first**:
   ```bash
   tail -f backend/backend.log
   aws logs tail /aws/datamiq/backend --follow
   ```

2. **Verify AWS access**:
   ```bash
   aws sts get-caller-identity
   aws kms describe-key --key-id alias/datamiq-encryption-key
   aws secretsmanager get-secret-value --secret-id datamiq/encryption/kms-key-id
   ```

3. **If needed, rollback database**:
   ```bash
   cd backend
   alembic downgrade -1
   ```

4. **Contact support**:
   - Check documentation in `docs/`
   - Review troubleshooting guide
   - Contact DevOps team

## Completion

Date: _______________
Deployed by: _______________
Verified by: _______________

**Status**: ☐ Complete ☐ Issues (describe below)

Issues encountered:
_______________________________________
_______________________________________
_______________________________________

Resolution:
_______________________________________
_______________________________________
_______________________________________

---

**Congratulations! KMS Encryption is now deployed!** 🎉
