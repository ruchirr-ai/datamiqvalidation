# Quick Test Guide - GCS to S3 Transfer with Encryption

## ✅ Everything is Ready!

All implementations have been verified:
- ✅ Encryption service configured
- ✅ GCS to S3 transfer service implemented
- ✅ Router encrypts AWS credentials
- ✅ Orchestrator decrypts credentials
- ✅ Pathway A uses transfer service
- ✅ Frontend UI complete

## Start Testing Now

### Step 1: Start Backend (Terminal 1)

```bash
# From project root
./START_BACKEND_HERE.sh
```

**Expected Output**:
```
✓ Virtual environment found
✓ Starting uvicorn on port 8000...
Backend API: http://localhost:8000
```

### Step 2: Start Frontend (Terminal 2)

```bash
# From project root
./START_FRONTEND_HERE.sh
```

**Expected Output**:
```
✓ Frontend running on http://localhost:3000
```

### Step 3: Login

1. Open browser: http://localhost:3000/login
2. Username: `admin`
3. Password: `admin123`

### Step 4: Create Migration

1. Navigate to: http://localhost:3000/migrations/create
2. Fill in the wizard:

**Step 1 - Migration Type**:
- Migration Name: `Test GCS to S3 Transfer`
- Select Pathway A (GCP Native)

**Step 2 - Connections**:
- Source: Select your BigQuery connection
- Target: Select your Redshift connection

**Step 3 - Metadata Discovery**:
- Select dataset (e.g., `bigquery-public-data.samples`)
- Select tables (e.g., `shakespeare`, `natality`)

**Step 4 - Configuration**:

*Stage 1: BigQuery → GCS*
- GCS Bucket: `bq_data_transfer_rs` (or your bucket)
- GCS Path: `exports/test-migration`
- Export Format: AVRO
- Compression: SNAPPY

*Stage 2: GCS → S3* (NEW!)
- S3 Bucket: Your S3 bucket name (e.g., `my-redshift-data`)
- S3 Path: `imports/test-migration`
- AWS Access Key ID: Your AWS access key
- AWS Secret Access Key: Your AWS secret (will be encrypted!)
- ☑️ Overwrite Existing Files (optional)
- ☐ Delete Source After Transfer (optional)

**Step 5 - Scheduling**:
- Schedule Type: One-time (or configure schedule)

3. Click **Create Migration**

### Step 5: Verify Encryption

Open a new terminal and check the database:

```bash
psql -U manasakallakuri -d datamiq -c "
SELECT 
  id, 
  migration_name,
  aws_access_key_id,
  LEFT(aws_secret_access_key_encrypted, 50) || '...' as encrypted_key
FROM migrations_bq_redshift
ORDER BY id DESC
LIMIT 1;
"
```

**Expected Output**:
```
 id | migration_name              | aws_access_key_id | encrypted_key
----+-----------------------------+-------------------+------------------
  1 | Test GCS to S3 Transfer     | AKIAIOSFODNN7...  | gAAAAABmXYZ123...
```

✅ The secret key should be an encrypted blob starting with `gAAAAA`

### Step 6: Run Migration

1. Go to migrations list: http://localhost:3000/migrations
2. Find your migration
3. Click menu (⋮) → **Run Migration**
4. Watch the status change to "running"

### Step 7: Monitor Progress

**In the UI**:
- Status should show "running"
- Current Stage should update (export → transfer → load)
- Last Run At should show current time

**In the backend logs** (Terminal 1):
```
INFO - Starting migration 1 (Pathway A)
INFO - Step 1: Exporting data from BigQuery to GCS
INFO - ✓ BigQuery export completed successfully
INFO - Step 2: Executing Pathway A logic
INFO - Source: gs://bq_data_transfer_rs/exports/test-migration
INFO - Destination: s3://my-redshift-data/imports/test-migration
INFO - Created transfer job: transferJobs/...
INFO - Transfer in progress... (30s elapsed)
INFO - ✓ Transfer job completed successfully
INFO - ✓ Pathway A execution completed successfully
```

### Step 8: Verify Results

**Check GCS Bucket**:
```bash
gsutil ls gs://bq_data_transfer_rs/exports/test-migration/
```

**Check S3 Bucket**:
```bash
aws s3 ls s3://my-redshift-data/imports/test-migration/
```

**Check Migration Status**:
```bash
psql -U manasakallakuri -d datamiq -c "
SELECT 
  id,
  migration_name,
  status,
  current_stage,
  start_time,
  last_run_at
FROM migrations_bq_redshift
WHERE id = 1;
"
```

**Expected**:
- Status: `completed`
- Current Stage: `load`
- Last Run At: Recent timestamp

## What to Look For

### ✅ Success Indicators

1. **Encryption Working**:
   - AWS secret key in database is encrypted blob
   - Backend logs show "Decrypting AWS secret key"
   - No plain text secrets in logs

2. **Transfer Working**:
   - Transfer job created successfully
   - Progress monitored every 30 seconds
   - Transfer completes without errors
   - Files appear in S3 bucket

3. **Status Updates**:
   - Status changes from pending → running → completed
   - Last Run At shows correct timestamp
   - Current Stage updates through export → transfer → load

### ⚠️ Common Issues

**Issue**: "Decryption failed"
- **Cause**: Encryption key changed or not set
- **Fix**: Check `ENCRYPTION_PASSWORD` in `backend/.env`

**Issue**: "Transfer job failed"
- **Cause**: Invalid AWS credentials or permissions
- **Fix**: Test credentials with `aws sts get-caller-identity`

**Issue**: "Service account key not found"
- **Cause**: BigQuery connection missing credentials
- **Fix**: Re-enter service account JSON in connection

**Issue**: "Bucket not found"
- **Cause**: GCS or S3 bucket doesn't exist
- **Fix**: Create bucket or check bucket name

## Quick Verification Commands

### Check Backend is Running
```bash
curl http://localhost:8000/health
```

### Check Frontend is Running
```bash
curl http://localhost:3000
```

### Check Database Connection
```bash
psql -U manasakallakuri -d datamiq -c "SELECT COUNT(*) FROM migrations_bq_redshift;"
```

### Check Encryption Service
```bash
cd backend
source .venv/bin/activate
python -c "
from services.encryption_service import get_encryption_service
service = get_encryption_service()
encrypted = service.encrypt('test-secret')
decrypted = service.decrypt(encrypted)
print('✓ Encryption working!' if decrypted == 'test-secret' else '✗ Encryption failed!')
"
```

### Check GCS Access
```bash
gsutil ls gs://bq_data_transfer_rs/
```

### Check S3 Access
```bash
aws s3 ls s3://my-redshift-data/
```

## Test Scenarios

### Scenario 1: Basic Migration
- Create migration with minimal configuration
- Run migration
- Verify completion

### Scenario 2: With Overwrite
- Create migration with "Overwrite Existing Files" enabled
- Run migration twice
- Verify files are overwritten

### Scenario 3: With Delete Source
- Create migration with "Delete Source After Transfer" enabled
- Run migration
- Verify GCS files are deleted after transfer

### Scenario 4: Large Dataset
- Select multiple large tables
- Monitor transfer progress
- Verify all files transferred

### Scenario 5: Error Handling
- Use invalid AWS credentials
- Verify migration fails gracefully
- Check error messages in logs

## Next Steps After Testing

### If Everything Works ✅
1. Test with production data (small subset)
2. Implement Stage 3 (S3 → Redshift load)
3. Add transfer progress percentage in UI
4. Implement retry logic

### If Issues Found ⚠️
1. Check logs in Terminal 1 (backend)
2. Check browser console (F12)
3. Check database for error logs:
   ```sql
   SELECT * FROM migration_logs 
   WHERE migration_id = 1 
   ORDER BY created_at DESC;
   ```
4. Review troubleshooting section above

## Production Readiness Checklist

Before deploying to production:

- [ ] Migrate to AWS KMS for encryption
- [ ] Store encryption key in AWS Secrets Manager
- [ ] Use IAM roles instead of access keys
- [ ] Implement audit logging
- [ ] Add transfer cost estimation
- [ ] Implement automatic key rotation
- [ ] Add comprehensive monitoring
- [ ] Set up CloudWatch alarms
- [ ] Test disaster recovery procedures
- [ ] Document runbooks

## Support

If you encounter issues:

1. **Check Logs**: Backend terminal shows detailed logs
2. **Check Database**: Migration logs table has error details
3. **Check Documentation**: 
   - `GCS_TO_S3_TRANSFER_COMPLETE.md`
   - `AWS_SECRET_KEY_ENCRYPTION_COMPLETE.md`
   - `IMPLEMENTATION_VERIFIED_READY.md`

---

**Ready to test!** Start with Step 1 above. 🚀
