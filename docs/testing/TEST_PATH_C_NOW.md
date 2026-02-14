# Test Path C Migration Now

## Quick Start Guide

### 1. Install Required Package

```bash
cd backend
source .venv/bin/activate
uv pip install google-cloud-storage-transfer
```

### 2. Set Encryption Key

```bash
# Add to backend/.env
echo "ENCRYPTION_PASSWORD=my-secure-password-2026" >> backend/.env
```

### 3. Restart Backend

```bash
# Kill existing process
lsof -ti:8000 | xargs kill -9

# Start backend
cd backend
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

### 4. Create Migration via UI

1. **Login**: `http://localhost:3000` (admin / AdminPass123!)

2. **Create Connection**:
   - Go to Connections
   - Create BigQuery connection
   - Paste service account JSON
   - Test connection

3. **Create Migration**:
   - Go to Migrations
   - Click "Create Migration"
   - Select "Path C: CLI/Legacy"

4. **Fill Configuration**:

   **Stage 1: BigQuery to GCS**
   ```
   GCS Bucket: your-gcs-bucket
   GCS Path: exports/test
   Export Format: AVRO
   Compression: SNAPPY
   Service Account JSON: {paste your JSON}
   ```

   **Stage 2: GCS to S3**
   ```
   S3 Bucket: your-s3-bucket
   S3 Path: imports/test
   AWS Access Key: AKIAIOSFODNN7EXAMPLE
   AWS Secret Key: wJalrXUtnFEMI/K7MDENG/...
   Overwrite: false
   Delete Source: false
   ```

5. **Submit Migration**

### 5. Start Migration

1. Find migration in list
2. Click menu → "Start Migration"
3. Watch backend logs

### 6. Monitor Progress

**Backend Logs**:
```bash
tail -f backend/server.log
```

**Look for**:
```
================================================================================
MIGRATION X: TRANSFER STAGE
================================================================================
✓ AWS secret key decrypted successfully
✓ Transfer job created: transferJobs/...
✓ Transfer job started
[Check #1] Transfer in progress...
[Check #2] Transfer in progress...
================================================================================
✓ TRANSFER COMPLETED SUCCESSFULLY
================================================================================
Transfer Statistics:
  Objects Copied: 10
  Bytes Copied: 1,234,567
```

### 7. Verify Results

**Check S3**:
```bash
aws s3 ls s3://your-s3-bucket/imports/test/ --recursive
```

**Check Database**:
```sql
SELECT id, migration_name, status, current_stage 
FROM migrations_bq_redshift 
WHERE pathway = 'C' 
ORDER BY created_at DESC 
LIMIT 1;
```

## Expected Output

### Success Scenario

```
✓ Export stage verified
✓ AWS credentials decrypted
✓ Transfer job created
✓ Transfer job started
✓ Transfer completed
✓ 10 objects copied (1.2 MB)
✓ Transfer job cleaned up
```

### Database State

```
status: 'completed'
current_stage: 'load'
checkpoint_data: {
  export_completed_at: '2026-02-09T10:00:00',
  transfer: {
    completed_at: '2026-02-09T10:05:00',
    job_name: 'transferJobs/...',
    stats: {
      objects_copied: 10,
      bytes_copied: 1234567
    }
  }
}
```

## Troubleshooting

### Issue: "google-cloud-storage-transfer not installed"
```bash
cd backend
source .venv/bin/activate
uv pip install google-cloud-storage-transfer
```

### Issue: "Encryption failed"
```bash
# Set encryption password
echo "ENCRYPTION_PASSWORD=my-secure-password" >> backend/.env

# Restart backend
lsof -ti:8000 | xargs kill -9
uvicorn main:app --reload --port 8000
```

### Issue: "Storage Transfer Service API not enabled"
```bash
gcloud services enable storagetransfer.googleapis.com --project=YOUR_PROJECT_ID
```

### Issue: "Permission denied"
```bash
# Grant Storage Transfer Admin role
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_SERVICE_ACCOUNT@YOUR_PROJECT.iam.gserviceaccount.com" \
  --role="roles/storagetransfer.admin"
```

## Test with Sample Data

### 1. Export Sample BigQuery Table

```sql
-- In BigQuery Console
EXPORT DATA OPTIONS(
  uri='gs://your-gcs-bucket/exports/test/sample-*.avro',
  format='AVRO',
  compression='SNAPPY',
  overwrite=true
) AS
SELECT * FROM `your-project.your-dataset.your-table` LIMIT 1000;
```

### 2. Create Migration

Use the exported data path in your migration configuration.

### 3. Verify Transfer

```bash
# Check GCS
gsutil ls gs://your-gcs-bucket/exports/test/

# Check S3 (after migration)
aws s3 ls s3://your-s3-bucket/imports/test/
```

## Success Criteria

✅ Backend starts without errors
✅ Migration created successfully
✅ AWS secret key encrypted in database
✅ Migration starts without errors
✅ Export stage verified
✅ AWS credentials decrypted
✅ Transfer job created
✅ Transfer job runs successfully
✅ Files appear in S3 bucket
✅ Transfer statistics logged
✅ Migration marked as completed

## Next Steps

After successful test:
1. Test with larger datasets
2. Test error scenarios (invalid credentials)
3. Test resume functionality
4. Implement Redshift COPY stage
5. Add UI progress indicators

## Status: Ready to Test!

All components are in place. Follow the steps above to test the complete BigQuery → GCS → S3 migration flow.
