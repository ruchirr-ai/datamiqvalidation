# KMS Encryption Deployment Checklist

## Pre-Deployment Checklist

### AWS Setup
- [ ] Create KMS key in AWS Console or CLI
- [ ] Create alias for KMS key: `alias/datamiq-encryption-key`
- [ ] Store KMS key ID in AWS Secrets Manager
  - Secret name: `datamiq/encryption/kms-key-id`
  - Secret value: `{"kms_key_id": "arn:aws:kms:region:account:key/key-id"}`
- [ ] Configure IAM permissions for application role
  - KMS: Encrypt, Decrypt, DescribeKey, GenerateDataKey
  - Secrets Manager: GetSecretValue, DescribeSecret
- [ ] Test IAM permissions from application environment

### Application Configuration
- [ ] Update `.env` file with KMS configuration:
  ```bash
  AWS_REGION=us-east-1
  ENCRYPTION_SECRET_NAME=datamiq/encryption/kms-key-id
  ENCRYPTION_AWS_REGION=us-east-1
  ```
- [ ] Verify AWS credentials are configured (IAM role or environment variables)
- [ ] Test AWS connectivity from application environment

### Code Deployment
- [ ] Pull latest code with KMS encryption implementation
- [ ] Review all changes in:
  - `backend/services/kms_encryption_service.py`
  - `backend/routers/bq_redshift_migration.py`
  - `backend/routers/connections_router.py`
  - `backend/services/bq_redshift_migration/orchestrator.py`
  - `backend/services/bq_redshift_migration/pathway_c.py`
  - `backend/models/connection.py`
- [ ] Install any new dependencies (boto3 should already be installed)

## Deployment Steps

### Step 1: Test KMS Encryption Service

```bash
cd backend
source .venv/bin/activate

# Run comprehensive test suite
python test_kms_encryption_complete.py
```

**Expected Output**: All 5 tests should pass
- ✓ Basic Encryption/Decryption
- ✓ Encryption Context Validation
- ✓ Migration AWS Secret
- ✓ Connection Parameters
- ✓ Error Handling

**If tests fail**: Check AWS credentials, KMS key permissions, and Secrets Manager configuration

### Step 2: Run Database Migration

```bash
cd backend
source .venv/bin/activate

# Run Alembic migration to add connection_params_encrypted column
alembic upgrade head
```

**Expected Output**:
```
INFO  [alembic.runtime.migration] Running upgrade 016 -> 017, add encrypted connection params
✓ Added connection_params_encrypted column to connections table
✓ Added index on connection_params_encrypted
```

**Verify Migration**:
```bash
# Check that column was added
python -c "
from database import get_db
from models.connection import Connection
db = next(get_db())
conn = db.query(Connection).first()
print('✓ connection_params_encrypted column exists' if hasattr(conn, 'connection_params_encrypted') else '✗ Column missing')
"
```

### Step 3: Migrate Existing Data (Dry Run)

```bash
cd backend
source .venv/bin/activate

# Run migration script in dry-run mode first
python scripts/migrate_to_kms_encryption.py --dry-run
```

**Review Output**:
- Check number of migrations with AWS secrets
- Check number of connections to encrypt
- Verify no errors in dry run
- Review encryption/decryption test results

### Step 4: Migrate Existing Data (Live)

```bash
cd backend
source .venv/bin/activate

# Run migration script for real
python scripts/migrate_to_kms_encryption.py
```

**Expected Output**:
```
✓ KMS encryption service working correctly
✓ Migration AWS Secrets: X succeeded, 0 failed
✓ Connection Parameters: Y succeeded, 0 failed
✓ MIGRATION COMPLETED
```

**If migration fails**:
- Check error logs
- Verify AWS permissions
- Check database connectivity
- Review failed records in output

### Step 5: Verify Data Migration

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

# Check migrations with AWS secrets
migrations = db.query(MigrationBQRedshift).filter(
    MigrationBQRedshift.aws_secret_access_key_encrypted.isnot(None)
).all()

print(f'Found {len(migrations)} migrations with encrypted AWS secrets')

# Test decryption on first migration
if migrations:
    m = migrations[0]
    context = {'migration_id': str(m.id), 'field': 'aws_secret_access_key'}
    try:
        decrypted = kms_service.decrypt(m.aws_secret_access_key_encrypted, context)
        print(f'✓ Successfully decrypted AWS secret for migration {m.id}')
    except Exception as e:
        print(f'✗ Failed to decrypt: {e}')
"

# Verify connections
python -c "
from database import get_db
from models.connection import Connection
from services.kms_encryption_service import get_kms_encryption_service
import json

db = next(get_db())
kms_service = get_kms_encryption_service()

# Check connections with encrypted params
connections = db.query(Connection).filter(
    Connection.connection_params_encrypted.isnot(None)
).all()

print(f'Found {len(connections)} connections with encrypted params')

# Test decryption on first connection
if connections:
    c = connections[0]
    context = {'connection_id': str(c.id), 'field': 'connection_params'}
    try:
        decrypted_json = kms_service.decrypt(c.connection_params_encrypted, context)
        params = json.loads(decrypted_json)
        print(f'✓ Successfully decrypted params for connection {c.id}')
        print(f'  Keys: {list(params.keys())}')
    except Exception as e:
        print(f'✗ Failed to decrypt: {e}')
"
```

### Step 6: Deploy Application

```bash
# Stop application
sudo systemctl stop datamiq-backend  # or your service name

# Pull latest code
git pull origin main

# Restart application
sudo systemctl start datamiq-backend

# Check logs
sudo journalctl -u datamiq-backend -f
```

### Step 7: Smoke Tests

#### Test 1: Create New Migration with AWS Secrets

```bash
# Use API or UI to create a new migration with AWS credentials
# Verify:
# - Migration is created successfully
# - AWS secret is encrypted in database
# - Migration can be executed
```

#### Test 2: Create New Connection

```bash
# Use API or UI to create a new connection
# Verify:
# - Connection is created successfully
# - Connection params are encrypted in database
# - Connection can be tested
# - Connection can be used in migrations
```

#### Test 3: Execute Existing Migration

```bash
# Execute a migration that uses encrypted AWS secrets
# Verify:
# - Migration starts successfully
# - AWS secrets are decrypted correctly
# - Migration completes without errors
```

#### Test 4: Update Connection

```bash
# Update an existing connection
# Verify:
# - Connection is updated successfully
# - New params are encrypted
# - Connection still works
```

## Post-Deployment Verification

### Check CloudWatch Logs

```bash
# View KMS encryption logs
aws logs tail /aws/datamiq/backend --follow --filter-pattern "KMS"

# Look for:
# - Successful encryption operations
# - Successful decryption operations
# - No error messages
```

### Check CloudTrail

```bash
# View KMS API calls
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=ResourceType,AttributeValue=AWS::KMS::Key \
  --max-results 50

# Verify:
# - Encrypt and Decrypt calls are logged
# - Encryption context is recorded
# - No access denied errors
```

### Monitor Application Logs

```bash
# Check for encryption-related errors
grep -i "encrypt\|decrypt\|kms" backend/backend.log

# Look for:
# - Successful encryption operations
# - Successful decryption operations
# - No error messages
```

### Performance Check

```bash
# Monitor KMS API latency
aws cloudwatch get-metric-statistics \
  --namespace AWS/KMS \
  --metric-name Duration \
  --dimensions Name=Operation,Value=Decrypt \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum

# Typical latency: 50-200ms
# Alert if > 1000ms
```

## Rollback Procedure

If issues arise after deployment:

### Step 1: Identify Issue

- Check application logs
- Check CloudWatch logs
- Check CloudTrail for KMS errors
- Identify which operations are failing

### Step 2: Quick Fix Options

**Option A: Revert to Old Encryption (Not Recommended)**

```bash
# Revert code changes
git revert <commit-hash>

# Restart application
sudo systemctl restart datamiq-backend

# Note: Old encryption service still exists, but data is now KMS-encrypted
# This will cause decryption failures
```

**Option B: Fix Configuration**

```bash
# Check AWS credentials
aws sts get-caller-identity

# Check KMS key access
aws kms describe-key --key-id <key-id>

# Check Secrets Manager access
aws secretsmanager get-secret-value --secret-id datamiq/encryption/kms-key-id

# Fix IAM permissions if needed
# Restart application
```

**Option C: Rollback Database Migration**

```bash
cd backend
source .venv/bin/activate

# Rollback to previous migration
alembic downgrade -1

# Note: This removes connection_params_encrypted column
# Encrypted data will be lost
```

### Step 3: Re-Deploy After Fix

- Fix the root cause
- Test in staging environment
- Re-deploy to production
- Verify all operations work

## Monitoring Setup

### CloudWatch Alarms

Create alarms for:

```bash
# High KMS error rate
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

# High KMS latency
aws cloudwatch put-metric-alarm \
  --alarm-name datamiq-kms-high-latency \
  --alarm-description "KMS latency > 1s" \
  --metric-name Duration \
  --namespace AWS/KMS \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 1000 \
  --comparison-operator GreaterThanThreshold
```

### Application Metrics

Monitor:
- Encryption operation count
- Decryption operation count
- Encryption errors
- Decryption errors
- Average encryption time
- Average decryption time

## Troubleshooting

### Issue: "AccessDeniedException"

**Cause**: IAM role doesn't have KMS or Secrets Manager permissions

**Solution**:
```bash
# Check IAM role
aws sts get-caller-identity

# Attach required policies
aws iam attach-role-policy \
  --role-name <role-name> \
  --policy-arn arn:aws:iam::aws:policy/SecretsManagerReadWrite

# Create custom KMS policy and attach
```

### Issue: "NotFoundException: Secrets Manager can't find secret"

**Cause**: Secret doesn't exist or wrong name

**Solution**:
```bash
# List secrets
aws secretsmanager list-secrets

# Create secret if missing
aws secretsmanager create-secret \
  --name datamiq/encryption/kms-key-id \
  --secret-string '{"kms_key_id":"arn:aws:kms:region:account:key/key-id"}'
```

### Issue: "InvalidCiphertextException"

**Cause**: Encryption context doesn't match or data corrupted

**Solution**:
- Check encryption context in code
- Verify data wasn't modified in database
- Re-encrypt the data if necessary

### Issue: Migration script fails

**Cause**: Various (permissions, connectivity, data issues)

**Solution**:
```bash
# Run with verbose logging
python scripts/migrate_to_kms_encryption.py --dry-run 2>&1 | tee migration.log

# Review errors in migration.log
# Fix issues and re-run
```

## Success Criteria

Deployment is successful when:

- [ ] All tests pass
- [ ] Database migration completes successfully
- [ ] Data migration completes with 0 failures
- [ ] New migrations can be created with encrypted AWS secrets
- [ ] New connections can be created with encrypted params
- [ ] Existing migrations can be executed
- [ ] Existing connections can be used
- [ ] No errors in application logs
- [ ] No errors in CloudWatch logs
- [ ] CloudTrail shows successful KMS operations
- [ ] Performance is acceptable (< 500ms for encrypt/decrypt)

## Support Contacts

- AWS Support: For KMS/Secrets Manager issues
- DevOps Team: For deployment issues
- Development Team: For application issues

## Additional Resources

- Setup Guide: `docs/KMS_ENCRYPTION_SETUP.md`
- Quick Start: `docs/KMS_ENCRYPTION_QUICK_START.md`
- Implementation Details: `docs/fixes/KMS_ENCRYPTION_IMPLEMENTATION.md`
- AWS KMS Documentation: https://docs.aws.amazon.com/kms/
- AWS Secrets Manager Documentation: https://docs.aws.amazon.com/secretsmanager/
