# Quick Test: Path C GCS to S3 Transfer

## Prerequisites
- Backend running on port 8000
- Frontend running on port 3000
- PostgreSQL database running
- Admin credentials: username=`admin`, password=`AdminPass123!`

## Step 1: Run Database Migration

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

**Expected Output**:
```
INFO  [alembic.runtime.migration] Running upgrade 007 -> 008, add aws_region to migrations
```

## Step 2: Restart Backend

```bash
# Kill existing backend process
lsof -ti:8000 | xargs kill -9

# Start backend
cd backend
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

**Expected Output**:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

## Step 3: Test Frontend Form

1. **Open Browser**: Navigate to `http://localhost:3000`

2. **Login**: Use admin credentials

3. **Navigate to Migrations**:
   - Click "Migrations" in sidebar
   - Click "Create Migration" button

4. **Select Path C**:
   - In Strategy Selection step
   - Choose "Path C: CLI/Legacy"
   - Click "Next"

5. **Fill Configuration Form**:

   **Stage 1: BigQuery to GCS Export**
   - GCS Staging Bucket: `gs://your-gcs-bucket`
   - GCS Region: Select any region
   - Export Format: `Parquet`
   - Compression: `SNAPPY`
   - GCP Service Account JSON: Paste your service account JSON
   - Click "Save & Continue"

   **Stage 2: GCS to S3 Transfer (Path C)**
   - S3 Bucket Name: `your-s3-bucket` (without s3:// prefix)
   - S3 Path: `migrations/test`
   - AWS Access Key ID: `AKIAIOSFODNN7EXAMPLE`
   - AWS Secret Access Key: `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`
   - AWS Region: Select `us-east-1`
   - Transfer Method: Select `Direct Transfer (Recommended)`
   - Click "Save & Continue"

   **Stage 3: S3 to Redshift Load**
   - Fill placeholder fields
   - Click "Save & Continue"

6. **Complete Wizard**:
   - Fill remaining steps
   - Submit migration

## Step 4: Verify Database Storage

```bash
# Connect to PostgreSQL
psql -U manasakallakuri -d datamiq

# Query migration
SELECT 
    id,
    migration_name,
    pathway,
    aws_access_key_id,
    LENGTH(aws_secret_access_key_encrypted) as encrypted_length,
    aws_region,
    status
FROM migrations_bq_redshift
WHERE pathway = 'C'
ORDER BY created_at DESC
LIMIT 1;
```

**Expected Output**:
```
 id | migration_name | pathway | aws_access_key_id      | encrypted_length | aws_region | status
----+----------------+---------+------------------------+------------------+------------+---------
  1 | Test Migration | C       | AKIAIOSFODNN7EXAMPLE   | 156              | us-east-1  | pending
```

**Verify**:
- ✅ `aws_access_key_id` is stored in plain text
- ✅ `aws_secret_access_key_encrypted` has length > 0 (encrypted)
- ✅ `aws_region` is set correctly
- ✅ `status` is 'pending'

## Step 5: Test Decryption (Optional)

Create a test script to verify encryption/decryption:

```python
# backend/test_encryption.py
from services.encryption_service import get_encryption_service

# Test encryption/decryption
encryption_service = get_encryption_service()

# Original secret
original_secret = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

# Encrypt
encrypted = encryption_service.encrypt(original_secret)
print(f"Encrypted: {encrypted[:50]}...")
print(f"Length: {len(encrypted)}")

# Decrypt
decrypted = encryption_service.decrypt(encrypted)
print(f"Decrypted: {decrypted}")

# Verify
assert decrypted == original_secret
print("✅ Encryption/Decryption working correctly!")
```

Run test:
```bash
cd backend
source .venv/bin/activate
python test_encryption.py
```

**Expected Output**:
```
Encrypted: gAAAAABl8xYZ...
Length: 156
Decrypted: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
✅ Encryption/Decryption working correctly!
```

## Step 6: Monitor Migration Execution

Start the migration and monitor logs:

```bash
# Watch backend logs
tail -f backend/server.log
```

**Look for these log entries**:

1. **Migration Started**:
```
INFO: Starting migration 1 in background thread
INFO: === Background thread started for migration 1 ===
```

2. **AWS Credentials Decryption**:
```
INFO: Migration 1: Starting TRANSFER stage (X shards)
INFO: Transfer method: direct
INFO: ✓ AWS secret key decrypted successfully
```

3. **S3 Client Initialization**:
```
INFO: Direct transfer: gs://bucket/path -> s3://bucket/path
INFO: ✓ Credentials created
```

4. **Transfer Progress**:
```
INFO: Downloading from GCS: gs://...
INFO: Downloaded 1,234,567 bytes
INFO: Uploading to S3: s3://...
INFO: Direct transfer successful for shard 1
```

## Step 7: Verify S3 Upload (If Real Credentials)

If you used real AWS credentials, verify the upload:

```bash
# List S3 bucket contents
aws s3 ls s3://your-s3-bucket/migrations/test/ --recursive

# Or use AWS Console
# Navigate to S3 → your-s3-bucket → migrations/test/
```

## Troubleshooting

### Issue: Database migration fails
**Solution**: Check if migration 007 exists
```bash
alembic current
alembic history
```

### Issue: Encryption fails
**Solution**: Set encryption key in .env
```bash
# backend/.env
ENCRYPTION_PASSWORD=your-strong-password-here
```

### Issue: S3 upload fails with authentication error
**Solution**: Verify AWS credentials are correct
- Check access key ID format
- Verify secret key is complete
- Ensure IAM user has S3 write permissions

### Issue: "AWS secret key decrypted successfully" not in logs
**Solution**: Check if encrypted value exists in database
```sql
SELECT aws_secret_access_key_encrypted 
FROM migrations_bq_redshift 
WHERE id = 1;
```

### Issue: Frontend form doesn't show AWS fields
**Solution**: 
- Clear browser cache
- Restart frontend: `npm run dev`
- Check browser console for errors

## Success Criteria

✅ Database migration runs successfully
✅ Backend starts without errors
✅ Frontend form shows all AWS credential fields
✅ Secret key field is masked (password type)
✅ Form submission succeeds
✅ Database stores encrypted secret key
✅ Migration logs show "✓ AWS secret key decrypted successfully"
✅ S3 client initialization succeeds
✅ Transfer completes (if real credentials provided)

## Next Steps

After successful testing:
1. Test with real GCS and S3 credentials
2. Verify actual file transfer
3. Test error handling (invalid credentials)
4. Test with different AWS regions
5. Test CLI transfer method
6. Implement S3 to Redshift load stage

## Status: Ready for Testing

All components are in place and ready for end-to-end testing!
