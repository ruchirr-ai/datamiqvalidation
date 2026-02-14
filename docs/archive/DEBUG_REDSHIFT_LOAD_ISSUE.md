# Debug Redshift Load Issue - Investigation Guide

## Problem Statement
Data is successfully exported from BigQuery to GCS and transferred from GCS to S3, but the S3 to Redshift load stage is not loading data. The migration shows as "completed" but no data appears in Redshift and there are no load-related logs.

## Debug Scripts Created

### 1. `debug_redshift_load.py` - Diagnostic Script
**Purpose**: Investigates the migration state to identify why the load stage didn't execute.

**Usage**:
```bash
cd backend
source .venv/bin/activate
python debug_redshift_load.py <migration_id>
```

**What it checks**:
1. ✅ Migration exists in database
2. ✅ Migration status and current stage
3. ✅ Checkpoint data (export, transfer, load completion)
4. ✅ Export results (tables, schemas, success/failure)
5. ✅ Transfer results (files, bytes, duration)
6. ✅ Load results (presence or absence)
7. ✅ Target configuration (cluster, database, IAM role)
8. ✅ Target connection details
9. ✅ S3 configuration
10. ✅ Migration logs (all stages, errors)

**Output**: Detailed diagnosis with specific issues found and recommended actions.

### 2. `test_redshift_load_from_migration.py` - Load Test Script
**Purpose**: Actually attempts to load data from S3 to Redshift using the migration's configuration.

**Usage**:
```bash
cd backend
source .venv/bin/activate
python test_redshift_load_from_migration.py <migration_id>
```

**What it does**:
1. ✅ Fetches migration configuration from database
2. ✅ Validates all required configuration (Redshift, S3, IAM)
3. ✅ Decrypts credentials (Redshift password, AWS secret key)
4. ✅ Initializes RedshiftLoader
5. ✅ Connects to Redshift cluster
6. ✅ Verifies IAM role permissions
7. ✅ Attempts to load each table from S3
8. ✅ Reports success/failure for each table
9. ✅ Provides detailed error messages

**Output**: Real-time progress and results of load attempts.

## Step-by-Step Investigation Process

### Step 1: Run Diagnostic Script

First, identify your migration ID from the UI or database, then run:

```bash
cd backend
source .venv/bin/activate
python debug_redshift_load.py <migration_id>
```

**Example**:
```bash
python debug_redshift_load.py 123
```

### Step 2: Analyze Diagnostic Output

The script will show you:

#### ✅ If everything is configured correctly:
```
================================================================================
  DIAGNOSIS SUMMARY
================================================================================

✓ No obvious issues found in configuration
  The load stage appears to have executed successfully

  Next steps:
  1. Check Redshift cluster directly for loaded data
  2. Review Redshift STL_LOAD_ERRORS table
  3. Verify IAM role permissions
```

#### ❌ If issues are found:
```
================================================================================
  DIAGNOSIS SUMMARY
================================================================================

❌ ISSUES FOUND:
  1. Load stage was never executed (no results in checkpoint)
  2. No load stage logs found

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

### Step 3: Run Load Test Script

If the diagnostic shows the load stage was never executed, try running it manually:

```bash
python test_redshift_load_from_migration.py <migration_id>
```

This will:
- Validate all configuration
- Attempt to connect to Redshift
- Try to load data from S3
- Show exactly where it fails

### Step 4: Interpret Results

#### Scenario A: Configuration Missing
```
Step 4: Extracting configuration...

Validating configuration:
  Redshift Host: my-cluster.abc123.us-east-1.redshift.amazonaws.com
  Redshift Port: 5439
  Redshift Database: dev
  Redshift User: admin
  Redshift Password: ✓ SET
  IAM Role ARN: ❌ MISSING
  S3 Bucket: my-s3-bucket
  S3 Path: bigquery-data
  AWS Access Key: AKIAIOSFODNN7EXAMPLE
  AWS Secret Key: ✓ SET

❌ Missing required configuration:
  - IAM role ARN

Cannot proceed with load test
```

**Solution**: Add IAM role ARN to the migration or target connection.

#### Scenario B: Connection Failed
```
Step 7: Connecting to Redshift...

Failed to connect to Redshift
Check:
  - Cluster endpoint is correct
  - Cluster is publicly accessible or accessible from your network
  - Security group allows inbound traffic on port 5439
  - Username and password are correct
```

**Solution**: Fix Redshift connection settings or network access.

#### Scenario C: IAM Role Issues
```
Step 8: Verifying IAM role...

IAM role verification failed
Check:
  - IAM role ARN is correct
  - IAM role has trust relationship with Redshift
  - IAM role has S3 read permissions
  - IAM role is attached to Redshift cluster
```

**Solution**: Fix IAM role configuration.

#### Scenario D: Load Failures
```
Table 1/3: customers
  Columns: 8
  S3 Location: s3://my-bucket/bigquery-data/customers
  Format: PARQUET
  Compression: SNAPPY
  ✗ FAILED: No files found in S3 prefix
```

**Solution**: Check S3 bucket and path, verify files were transferred.

#### Scenario E: Success!
```
Table 1/3: customers
  Columns: 8
  S3 Location: s3://my-bucket/bigquery-data/customers
  Format: PARQUET
  Compression: SNAPPY
  ✓ SUCCESS: 1,234,567 rows loaded

================================================================================
LOAD TEST SUMMARY
================================================================================
Tables processed: 3
Successful loads: 3
Failed loads: 0
Total rows loaded: 6,959,146

✓ Some tables loaded successfully!
```

**Next**: Verify data in Redshift.

## Common Issues and Solutions

### Issue 1: Load Stage Never Executed

**Symptoms**:
- Migration shows "completed"
- No load results in checkpoint_data
- No load stage logs

**Root Causes**:
1. **Orchestrator not calling load stage**: Check `orchestrator.py` `_execute_migration()` method
2. **Pathway C skipping load stage**: Check `pathway_c.py` `execute()` method
3. **Silent exception**: Check for try/catch blocks swallowing errors

**Solution**:
```python
# In pathway_c.py execute() method, ensure this logic exists:
if transfer_completed and not load_completed:
    logger.info(f"Starting LOAD stage")
    success = self._execute_load_stage(
        migration_id,
        target_config,
        storage_config,
        []
    )
```

### Issue 2: Missing IAM Role ARN

**Symptoms**:
- Diagnostic shows "IAM role ARN not configured"
- Load test fails at IAM verification

**Solution**:
Add IAM role to migration:
```sql
UPDATE migrations_bq_redshift 
SET iam_role_arn = 'arn:aws:iam::123456789012:role/RedshiftS3Role'
WHERE id = <migration_id>;
```

Or add to target connection:
```sql
UPDATE connections 
SET connection_params = jsonb_set(
    connection_params, 
    '{iam_role_arn}', 
    '"arn:aws:iam::123456789012:role/RedshiftS3Role"'
)
WHERE id = <target_connection_id>;
```

### Issue 3: Redshift Connection Failed

**Symptoms**:
- Cannot connect to Redshift cluster
- Connection timeout or authentication error

**Solutions**:
1. **Check cluster endpoint**: Verify it's correct in connection params
2. **Check network access**: Ensure cluster is publicly accessible or accessible from your network
3. **Check security group**: Allow inbound traffic on port 5439 from your IP
4. **Check credentials**: Verify username and password are correct

### Issue 4: No Files in S3

**Symptoms**:
- Load fails with "No files found in S3 prefix"
- Transfer completed but files not in expected location

**Solutions**:
1. **Check S3 path**: Verify `s3_path` in migration matches where files were transferred
2. **Check transfer results**: Look at `transfer_stats` in checkpoint_data
3. **Manually check S3**: Use AWS CLI or console to verify files exist

```bash
aws s3 ls s3://your-bucket/your-path/ --recursive
```

### Issue 5: Type Mapping Errors

**Symptoms**:
- Load fails with data type errors
- Redshift rejects certain column types

**Solutions**:
1. **Check RedshiftLoader type mapping**: Review `_map_bigquery_type_to_redshift()` method
2. **Check Redshift STL_LOAD_ERRORS**: See specific error messages
3. **Adjust schema**: May need to modify column types

```sql
SELECT * FROM stl_load_errors 
WHERE query = pg_last_copy_id() 
ORDER BY starttime DESC;
```

## Verification Queries

After successful load, verify data in Redshift:

### Check Tables Created
```sql
SELECT schemaname, tablename, 
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY tablename;
```

### Check Row Counts
```sql
SELECT 'customers' as table_name, COUNT(*) as row_count FROM public.customers
UNION ALL
SELECT 'orders', COUNT(*) FROM public.orders
UNION ALL
SELECT 'products', COUNT(*) FROM public.products;
```

### Check Sample Data
```sql
SELECT * FROM public.customers LIMIT 10;
```

### Check Load Errors
```sql
SELECT * FROM stl_load_errors 
WHERE starttime >= CURRENT_DATE 
ORDER BY starttime DESC;
```

## Next Steps After Debugging

### If Load Stage Never Executed:

1. **Review Code**:
   - Check `backend/services/bq_redshift_migration/pathway_c.py`
   - Check `backend/services/bq_redshift_migration/orchestrator.py`
   - Look for conditions that might skip load stage

2. **Add Logging**:
   - Add more debug logs to track execution flow
   - Log when each stage starts and completes

3. **Test Manually**:
   - Use `test_redshift_load_from_migration.py` to load data
   - This bypasses orchestrator and tests load directly

### If Configuration Missing:

1. **Update Migration**:
   - Add missing fields (IAM role, cluster, database)
   - Update via SQL or create new migration with correct config

2. **Update Connection**:
   - Add missing fields to target connection
   - Ensure all required parameters are present

### If Load Fails:

1. **Check Redshift**:
   - Verify cluster is running and accessible
   - Check IAM role permissions
   - Review security group rules

2. **Check S3**:
   - Verify files exist in expected location
   - Check file format and compression
   - Verify IAM role can read from S3

3. **Check Logs**:
   - Review Redshift STL_LOAD_ERRORS table
   - Check CloudWatch logs
   - Review application logs

## Files to Review

If you need to fix the code:

1. **`backend/services/bq_redshift_migration/pathway_c.py`**
   - `execute()` method - stage transition logic
   - `_execute_load_stage()` method - load implementation

2. **`backend/services/bq_redshift_migration/orchestrator.py`**
   - `_execute_migration()` method - calls pathway execute
   - Check if pathway.execute() is being called

3. **`backend/services/bq_redshift_migration/redshift_loader.py`**
   - `load_table()` method - actual load logic
   - Type mapping and error handling

## Summary

Use these scripts to:
1. ✅ **Diagnose** why load stage didn't execute (`debug_redshift_load.py`)
2. ✅ **Test** load stage manually (`test_redshift_load_from_migration.py`)
3. ✅ **Identify** specific configuration issues
4. ✅ **Verify** Redshift connectivity and permissions
5. ✅ **Troubleshoot** load failures with detailed errors

The scripts provide comprehensive diagnostics and will pinpoint exactly where the issue is occurring.
