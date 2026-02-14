# Quick Start: Debug Redshift Load Issue

## Problem
Data exported to S3 but not loading to Redshift. Migration shows "completed" but no data in Redshift.

## Quick Debug Steps

### 1. Find Your Migration ID

From the UI:
- Go to http://localhost:3000/migrations
- Find your migration in the list
- Note the ID (e.g., 123)

Or from database:
```bash
cd backend
source .venv/bin/activate
python -c "
from database import get_db
from models.bq_redshift_migration import MigrationBQRedshift

db = next(get_db())
migrations = db.query(MigrationBQRedshift).order_by(MigrationBQRedshift.id.desc()).limit(10).all()
for m in migrations:
    print(f'ID: {m.id}, Name: {m.migration_name}, Status: {m.status}')
db.close()
"
```

### 2. Run Diagnostic Script

```bash
cd backend
source .venv/bin/activate
python debug_redshift_load.py <migration_id>
```

**Example**:
```bash
python debug_redshift_load.py 123
```

This will show you:
- ✅ What stages completed (export, transfer, load)
- ✅ What configuration is missing
- ✅ What errors occurred
- ✅ Specific recommendations

### 3. Run Load Test Script

If diagnostic shows load stage never ran, test it manually:

```bash
cd backend
source .venv/bin/activate
python test_redshift_load_from_migration.py <migration_id>
```

**Example**:
```bash
python test_redshift_load_from_migration.py 123
```

This will:
- ✅ Actually attempt to load data from S3 to Redshift
- ✅ Show exactly where it fails
- ✅ Provide detailed error messages

## Expected Output

### Diagnostic Script Output

```
================================================================================
  DEBUGGING MIGRATION 123
================================================================================

--------------------------------------------------------------------------------
  Step 1: Fetching Migration Details
--------------------------------------------------------------------------------
✓ Migration found: My BigQuery Migration
  Status: completed
  Current Stage: transfer
  Pathway: C
  Created: 2026-02-09 10:00:00
  Updated: 2026-02-09 10:30:00

--------------------------------------------------------------------------------
  Step 2: Analyzing Checkpoint Data
--------------------------------------------------------------------------------
Checkpoint keys: ['export_completed_at', 'export_results', 'transfer_completed_at', 'transfer_stats']

Stage Completion Status:
  Export:   ✓ Completed
            at 2026-02-09T10:15:00Z
  Transfer: ✓ Completed
            at 2026-02-09T10:25:00Z
  Load:     ✗ Not completed

--------------------------------------------------------------------------------
  Step 5: Checking Load Results
--------------------------------------------------------------------------------
❌ ISSUE FOUND: No load results in checkpoint data
   This indicates the load stage was never executed or failed silently

   Possible reasons:
   1. Load stage was skipped due to missing configuration
   2. Load stage failed before creating results
   3. Load stage was never called by the orchestrator

   ⚠️  Export and transfer completed, but load did not run!
   This is the root cause of the issue.

================================================================================
  DIAGNOSIS SUMMARY
================================================================================

❌ ISSUES FOUND:
  1. Load stage not completed
  2. Load stage was never executed (no results in checkpoint)
  3. No load stage logs found

📋 RECOMMENDED ACTIONS:

  1. Check orchestrator logic:
     - Verify pathway_c.py _execute_load_stage() is being called
     - Check if there are any conditions preventing load stage execution
     - Review orchestrator.py _execute_migration() flow

  2. Check target configuration:
     - Ensure target_cluster, target_database are set
     - Verify IAM role ARN is configured
     - Check target connection has valid credentials
```

### Load Test Script Output

```
================================================================================
TESTING REDSHIFT LOAD FOR MIGRATION 123
================================================================================

Step 1: Fetching migration details...
✓ Migration found: My BigQuery Migration
  Status: completed
  Pathway: C

Step 2: Validating checkpoint data...
✓ Found 3 export results
✓ 3 tables exported successfully

Step 3: Getting target connection...
✓ Target connection: My Redshift Cluster

Step 4: Extracting configuration...

Validating configuration:
  Redshift Host: my-cluster.abc123.us-east-1.redshift.amazonaws.com
  Redshift Port: 5439
  Redshift Database: dev
  Redshift User: admin
  Redshift Password: ✓ SET
  IAM Role ARN: arn:aws:iam::123456789012:role/RedshiftS3Role
  S3 Bucket: my-s3-bucket
  S3 Path: bigquery-data
  AWS Access Key: AKIAIOSFODNN7EXAMPLE
  AWS Secret Key: ✓ SET

✓ All required configuration present

Step 5: Decrypting credentials...
✓ Redshift password decrypted
✓ AWS secret key decrypted

Step 6: Initializing RedshiftLoader...
✓ RedshiftLoader initialized

Step 7: Connecting to Redshift...
✓ Connected to Redshift

Step 8: Verifying IAM role...
✓ IAM role verified

Step 9: Loading tables to Redshift...
================================================================================

Table 1/3: customers
  Columns: 8
  S3 Location: s3://my-s3-bucket/bigquery-data/customers
  Format: PARQUET
  Compression: SNAPPY
  ✓ SUCCESS: 1,234,567 rows loaded

Table 2/3: orders
  Columns: 12
  S3 Location: s3://my-s3-bucket/bigquery-data/orders
  Format: PARQUET
  Compression: SNAPPY
  ✓ SUCCESS: 5,678,901 rows loaded

Table 3/3: products
  Columns: 6
  S3 Location: s3://my-s3-bucket/bigquery-data/products
  Format: PARQUET
  Compression: SNAPPY
  ✓ SUCCESS: 45,678 rows loaded

✓ Disconnected from Redshift

================================================================================
LOAD TEST SUMMARY
================================================================================
Tables processed: 3
Successful loads: 3
Failed loads: 0
Total rows loaded: 6,959,146

✓ Some tables loaded successfully!

To verify data in Redshift:
  1. Connect to Redshift cluster
  2. Run: SELECT * FROM pg_tables WHERE schemaname = 'public';
  3. Check row counts for each table
================================================================================
```

## Common Issues

### Issue: "Migration not found"
**Solution**: Check migration ID is correct

### Issue: "No export results found"
**Solution**: Export stage didn't complete. Run migration again.

### Issue: "IAM role ARN not configured"
**Solution**: Add IAM role to migration or connection:
```sql
UPDATE migrations_bq_redshift 
SET iam_role_arn = 'arn:aws:iam::123456789012:role/RedshiftS3Role'
WHERE id = 123;
```

### Issue: "Failed to connect to Redshift"
**Solution**: 
- Check cluster endpoint
- Check security group (allow port 5439)
- Check credentials

### Issue: "IAM role verification failed"
**Solution**:
- Check IAM role ARN is correct
- Check role has S3 read permissions
- Check role is attached to Redshift cluster

### Issue: "No files found in S3"
**Solution**:
- Check S3 bucket and path
- Verify transfer completed successfully
- Check files exist: `aws s3 ls s3://bucket/path/`

## Verify Data in Redshift

After successful load:

```sql
-- Connect to Redshift
psql -h my-cluster.abc123.us-east-1.redshift.amazonaws.com \
     -U admin -d dev -p 5439

-- Check tables
SELECT schemaname, tablename 
FROM pg_tables 
WHERE schemaname = 'public';

-- Check row counts
SELECT 'customers' as table_name, COUNT(*) FROM public.customers
UNION ALL
SELECT 'orders', COUNT(*) FROM public.orders;

-- Sample data
SELECT * FROM public.customers LIMIT 10;
```

## Need More Help?

See detailed guide: `DEBUG_REDSHIFT_LOAD_ISSUE.md`

## Summary

1. ✅ Run `debug_redshift_load.py` to diagnose
2. ✅ Run `test_redshift_load_from_migration.py` to test load
3. ✅ Fix any configuration issues found
4. ✅ Verify data in Redshift

These scripts will pinpoint exactly where the issue is!
