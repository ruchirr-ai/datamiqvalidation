# Debug Migration Issue - Files Not in S3

## Issue
Migration shows as successful but files are not appearing in S3 bucket.

## Debugging Steps

### 1. Check Backend Logs

```bash
# Check recent logs
tail -100 backend/server.log | grep -A 10 "TRANSFER"

# Or check full logs
cat backend/server.log | grep -A 20 "MIGRATION.*TRANSFER"
```

**Look for**:
- "✓ AWS secret key decrypted successfully"
- "✓ Transfer job created: transferJobs/..."
- "✓ Transfer job started"
- "✓ TRANSFER COMPLETED SUCCESSFULLY"
- Transfer statistics (objects copied, bytes copied)

### 2. Check Database

```sql
-- Connect to database
psql -U manasakallakuri -d datamiq

-- Check migration details
SELECT 
    id,
    migration_name,
    pathway,
    status,
    current_stage,
    checkpoint_data
FROM migrations_bq_redshift
WHERE pathway = 'C'
ORDER BY created_at DESC
LIMIT 1;

-- Check if checkpoint_data has transfer info
SELECT 
    id,
    migration_name,
    checkpoint_data->'transfer' as transfer_info
FROM migrations_bq_redshift
WHERE pathway = 'C'
ORDER BY created_at DESC
LIMIT 1;
```

### 3. Check GCS Bucket

```bash
# List files in GCS bucket
gsutil ls -r gs://YOUR_GCS_BUCKET/YOUR_GCS_PATH/

# Check if files exist
gsutil ls gs://YOUR_GCS_BUCKET/YOUR_GCS_PATH/**/*.avro
```

### 4. Check S3 Bucket

```bash
# List files in S3 bucket
aws s3 ls s3://YOUR_S3_BUCKET/YOUR_S3_PATH/ --recursive

# Check specific path
aws s3 ls s3://YOUR_S3_BUCKET/YOUR_S3_PATH/ --recursive --human-readable
```

### 5. Check GCP Storage Transfer Service

```bash
# List transfer jobs
gcloud transfer jobs list --project=YOUR_PROJECT_ID

# Check specific job status
gcloud transfer jobs describe JOB_NAME --project=YOUR_PROJECT_ID

# List operations
gcloud transfer operations list --job-names=JOB_NAME --project=YOUR_PROJECT_ID
```

## Common Issues

### Issue 1: Transfer Stage Skipped
**Symptom**: Migration marked as successful but transfer didn't run
**Cause**: Export stage failed or was skipped
**Solution**: Check export_completed_at in checkpoint_data

```sql
SELECT checkpoint_data->'export_completed_at' 
FROM migrations_bq_redshift 
WHERE id = YOUR_MIGRATION_ID;
```

### Issue 2: Transfer Job Created But Not Run
**Symptom**: Transfer job created but never started
**Cause**: run_transfer_job() failed
**Solution**: Check logs for "Running transfer job" message

### Issue 3: Transfer Job Failed Silently
**Symptom**: Transfer job ran but failed without proper error
**Cause**: AWS credentials invalid or S3 bucket doesn't exist
**Solution**: Check transfer job status in GCP Console

### Issue 4: Wrong S3 Path
**Symptom**: Files transferred to wrong location
**Cause**: S3 path configuration mismatch
**Solution**: Check actual S3 path used in logs

### Issue 5: No Files in GCS
**Symptom**: Transfer succeeded but nothing to transfer
**Cause**: BigQuery export failed or exported to wrong location
**Solution**: Check GCS bucket for exported files

## Quick Diagnostic Script

```bash
#!/bin/bash

echo "=== Migration Diagnostic ==="
echo ""

# 1. Check backend logs
echo "1. Checking backend logs for TRANSFER stage..."
tail -50 backend/server.log | grep -A 5 "TRANSFER"
echo ""

# 2. Check database
echo "2. Checking database..."
psql -U manasakallakuri -d datamiq -c "
SELECT 
    id,
    migration_name,
    status,
    current_stage,
    checkpoint_data->'transfer'->'completed_at' as transfer_completed,
    checkpoint_data->'transfer'->'stats' as transfer_stats
FROM migrations_bq_redshift
WHERE pathway = 'C'
ORDER BY created_at DESC
LIMIT 1;
"
echo ""

# 3. Get migration details
echo "3. Getting migration configuration..."
psql -U manasakallakuri -d datamiq -c "
SELECT 
    gcs_bucket,
    gcs_path,
    s3_bucket,
    s3_path
FROM migrations_bq_redshift
WHERE pathway = 'C'
ORDER BY created_at DESC
LIMIT 1;
"
echo ""

echo "=== End Diagnostic ==="
```

## What to Share

Please provide:

1. **Backend Logs** (last 100 lines with TRANSFER):
```bash
tail -100 backend/server.log | grep -B 5 -A 10 "TRANSFER"
```

2. **Database Checkpoint Data**:
```sql
SELECT checkpoint_data FROM migrations_bq_redshift WHERE id = YOUR_ID;
```

3. **Migration Configuration**:
```sql
SELECT 
    gcs_bucket, gcs_path, s3_bucket, s3_path,
    aws_access_key_id
FROM migrations_bq_redshift 
WHERE id = YOUR_ID;
```

4. **GCS Files**:
```bash
gsutil ls gs://YOUR_GCS_BUCKET/YOUR_GCS_PATH/
```

5. **S3 Files**:
```bash
aws s3 ls s3://YOUR_S3_BUCKET/YOUR_S3_PATH/ --recursive
```

## Expected Behavior

If transfer was successful, you should see:

1. **In Logs**:
```
================================================================================
MIGRATION X: TRANSFER STAGE
================================================================================
✓ AWS secret key decrypted successfully
✓ Transfer job created: transferJobs/12345...
✓ Transfer job started
[Check #1] Transfer in progress...
[Check #2] Transfer in progress...
================================================================================
✓ TRANSFER COMPLETED SUCCESSFULLY
================================================================================
Transfer Statistics:
  Objects Found: 10
  Bytes Found: 1,234,567
  Objects Copied: 10
  Bytes Copied: 1,234,567
  Objects Failed: 0
```

2. **In Database**:
```json
{
  "transfer": {
    "completed_at": "2026-02-09T10:30:00",
    "job_name": "transferJobs/...",
    "stats": {
      "objects_copied": 10,
      "bytes_copied": 1234567
    }
  }
}
```

3. **In S3**:
```
s3://your-bucket/your-path/table1/shard-00000.avro
s3://your-bucket/your-path/table1/shard-00001.avro
```

## Next Steps

Based on the diagnostic information, we can:
1. Identify where the transfer failed
2. Fix the configuration
3. Re-run the migration
4. Verify files appear in S3
