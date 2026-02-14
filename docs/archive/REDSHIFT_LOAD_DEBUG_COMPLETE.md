# Redshift Load Debug Scripts - Complete

## Problem Addressed
Data is successfully exported from BigQuery to GCS and transferred from GCS to S3, but the S3 to Redshift load stage is not loading data to Redshift. The migration shows as "completed" but no data appears in Redshift and there are no load-related logs.

## Solution: Comprehensive Debug Scripts

Created two powerful debug scripts to investigate and resolve the issue:

### 1. **Diagnostic Script** (`debug_redshift_load.py`)
**Purpose**: Comprehensive investigation of migration state to identify why load stage didn't execute.

**Features**:
- ✅ Fetches migration details from database
- ✅ Analyzes checkpoint data for all stages
- ✅ Checks export results (tables, schemas, success/failure)
- ✅ Validates transfer results (files, bytes, duration)
- ✅ Identifies missing load results
- ✅ Validates target configuration (cluster, database, IAM role)
- ✅ Checks target connection details and credentials
- ✅ Validates S3 configuration
- ✅ Analyzes migration logs for all stages
- ✅ Provides specific diagnosis with recommended actions

**Usage**:
```bash
cd backend
source .venv/bin/activate
python debug_redshift_load.py <migration_id>
```

**Output**: Detailed diagnosis report showing:
- What stages completed
- What configuration is missing
- What errors occurred
- Specific recommendations to fix

### 2. **Load Test Script** (`test_redshift_load_from_migration.py`)
**Purpose**: Actually attempts to load data from S3 to Redshift using the migration's configuration.

**Features**:
- ✅ Loads migration configuration from database
- ✅ Validates all required configuration
- ✅ Decrypts credentials (Redshift password, AWS secret key)
- ✅ Initializes RedshiftLoader
- ✅ Connects to Redshift cluster
- ✅ Verifies IAM role permissions
- ✅ Attempts to load each table from S3
- ✅ Reports success/failure for each table
- ✅ Provides detailed error messages
- ✅ Shows row counts loaded

**Usage**:
```bash
cd backend
source .venv/bin/activate
python test_redshift_load_from_migration.py <migration_id>
```

**Output**: Real-time progress showing:
- Configuration validation
- Connection status
- IAM role verification
- Per-table load results
- Total rows loaded
- Specific errors if any

## Investigation Process

### Step 1: Run Diagnostic Script
```bash
python debug_redshift_load.py 123
```

This will identify:
- ❌ Load stage was never executed
- ❌ Missing configuration (IAM role, cluster, etc.)
- ❌ Connection issues
- ❌ Missing export/transfer results

### Step 2: Run Load Test Script
```bash
python test_redshift_load_from_migration.py 123
```

This will:
- ✅ Validate configuration
- ✅ Test Redshift connection
- ✅ Verify IAM role
- ✅ Attempt actual load
- ✅ Show exactly where it fails

### Step 3: Fix Issues
Based on diagnostic output:
- Add missing configuration
- Fix connection settings
- Configure IAM role
- Verify S3 files exist

### Step 4: Verify Data
```sql
SELECT * FROM pg_tables WHERE schemaname = 'public';
SELECT COUNT(*) FROM public.customers;
```

## Common Issues Detected

### Issue 1: Load Stage Never Executed
**Symptoms**: No load results in checkpoint_data, no load logs

**Diagnosis Output**:
```
❌ ISSUE FOUND: No load results in checkpoint data
   This indicates the load stage was never executed or failed silently
   
   ⚠️  Export and transfer completed, but load did not run!
   This is the root cause of the issue.
```

**Recommended Actions**:
1. Check orchestrator logic in `pathway_c.py`
2. Verify stage transition conditions
3. Look for silent exceptions

### Issue 2: Missing IAM Role ARN
**Symptoms**: IAM role not configured

**Diagnosis Output**:
```
IAM Role ARN: ❌ NOT SET

❌ Missing required configuration:
  - IAM role ARN
```

**Solution**:
```sql
UPDATE migrations_bq_redshift 
SET iam_role_arn = 'arn:aws:iam::123456789012:role/RedshiftS3Role'
WHERE id = 123;
```

### Issue 3: Redshift Connection Failed
**Symptoms**: Cannot connect to cluster

**Test Output**:
```
Step 7: Connecting to Redshift...

Failed to connect to Redshift
Check:
  - Cluster endpoint is correct
  - Cluster is publicly accessible
  - Security group allows port 5439
  - Username and password are correct
```

**Solution**: Fix network access and credentials

### Issue 4: No Files in S3
**Symptoms**: Load fails with "No files found"

**Test Output**:
```
Table 1/3: customers
  S3 Location: s3://my-bucket/bigquery-data/customers
  ✗ FAILED: No files found in S3 prefix
```

**Solution**: Verify S3 path and transfer completion

### Issue 5: IAM Role Verification Failed
**Symptoms**: IAM role cannot access S3

**Test Output**:
```
Step 8: Verifying IAM role...

IAM role verification failed
Check:
  - IAM role ARN is correct
  - IAM role has S3 read permissions
  - IAM role is attached to Redshift cluster
```

**Solution**: Fix IAM role configuration

## Files Created

### Debug Scripts
1. **`backend/debug_redshift_load.py`** (350+ lines)
   - Comprehensive diagnostic script
   - Analyzes migration state
   - Identifies root causes
   - Provides recommendations

2. **`backend/test_redshift_load_from_migration.py`** (400+ lines)
   - Load test script
   - Tests actual load from S3 to Redshift
   - Shows real-time progress
   - Reports detailed results

### Documentation
3. **`DEBUG_REDSHIFT_LOAD_ISSUE.md`** (Comprehensive guide)
   - Detailed investigation process
   - Common issues and solutions
   - Verification queries
   - Code review guidance

4. **`RUN_DEBUG_SCRIPTS.md`** (Quick reference)
   - Quick start guide
   - Expected output examples
   - Common issues
   - Verification steps

5. **`REDSHIFT_LOAD_DEBUG_COMPLETE.md`** (This file)
   - Summary of solution
   - Overview of scripts
   - Key features

## Usage Examples

### Example 1: Diagnose Issue
```bash
cd backend
source .venv/bin/activate

# Find migration ID
python -c "
from database import get_db
from models.bq_redshift_migration import MigrationBQRedshift
db = next(get_db())
m = db.query(MigrationBQRedshift).order_by(MigrationBQRedshift.id.desc()).first()
print(f'Latest migration: ID={m.id}, Name={m.migration_name}')
db.close()
"

# Run diagnostic
python debug_redshift_load.py 123
```

### Example 2: Test Load
```bash
cd backend
source .venv/bin/activate

# Test load stage
python test_redshift_load_from_migration.py 123
```

### Example 3: Verify Results
```bash
# Connect to Redshift
psql -h my-cluster.abc123.us-east-1.redshift.amazonaws.com \
     -U admin -d dev -p 5439

# Check tables
SELECT schemaname, tablename FROM pg_tables WHERE schemaname = 'public';

# Check row counts
SELECT 'customers' as table, COUNT(*) FROM public.customers
UNION ALL
SELECT 'orders', COUNT(*) FROM public.orders;
```

## Benefits

### For Debugging
1. ✅ **Pinpoint exact issue**: Know exactly what's wrong
2. ✅ **Comprehensive analysis**: Check all aspects of migration
3. ✅ **Actionable recommendations**: Get specific steps to fix
4. ✅ **Real-time testing**: Test load without running full migration

### For Development
1. ✅ **Identify code issues**: Find where orchestrator/pathway fails
2. ✅ **Validate configuration**: Ensure all required fields present
3. ✅ **Test connectivity**: Verify Redshift and S3 access
4. ✅ **Debug permissions**: Check IAM role configuration

### For Operations
1. ✅ **Quick diagnosis**: Identify issues in minutes
2. ✅ **Manual recovery**: Load data even if migration failed
3. ✅ **Verification**: Confirm data loaded correctly
4. ✅ **Troubleshooting**: Detailed error messages

## Next Steps

### 1. Run Diagnostic
```bash
python debug_redshift_load.py <migration_id>
```

### 2. Review Output
- Check what stages completed
- Identify missing configuration
- Note any errors

### 3. Run Load Test
```bash
python test_redshift_load_from_migration.py <migration_id>
```

### 4. Fix Issues
- Add missing configuration
- Fix connection settings
- Configure IAM role

### 5. Verify Data
- Connect to Redshift
- Check tables exist
- Verify row counts

## Conclusion

These debug scripts provide comprehensive investigation and testing capabilities to:
- ✅ Identify why load stage didn't execute
- ✅ Test load stage independently
- ✅ Validate all configuration
- ✅ Provide specific error messages
- ✅ Enable manual data loading

The scripts will pinpoint exactly where the S3 to Redshift load is failing and provide actionable steps to resolve the issue.

**Ready to debug!** 🚀
