# Test IAM Role ARN from Database

## Overview
This test verifies that the IAM role ARN is correctly stored in the database and used for S3 to Redshift data load operations.

## What This Test Does

The test script (`backend/test_iam_role_from_db.py`) performs the following checks:

1. **Fetch Migration**: Retrieves migration 12 from the database
2. **Verify IAM Role**: Checks that `iam_role_arn` field is populated
3. **Fetch Connection**: Gets target Redshift connection details
4. **Decrypt Credentials**: Decrypts Redshift password and AWS secret key
5. **Initialize Loader**: Creates RedshiftLoader with IAM role from database
6. **Test Connection**: Connects to Redshift cluster
7. **Verify IAM Role**: Validates IAM role has proper S3 permissions
8. **Show COPY Command**: Displays sample COPY command with IAM role

## Prerequisites

### 1. Migration Must Have IAM Role ARN
The migration record must have `iam_role_arn` field populated. You can set this via:

**Option A: Update via UI**
1. Go to Migrations page
2. Click "Edit" on migration 12
3. Navigate to Step 4: Configuration Setup
4. Expand "Stage 3: S3 to Redshift Load"
5. Enter IAM Role ARN (e.g., `arn:aws:iam::123456789012:role/RedshiftS3Role`)
6. Click "Save & Continue"

**Option B: Update via SQL**
```sql
UPDATE migrations_bq_redshift
SET iam_role_arn = 'arn:aws:iam::123456789012:role/RedshiftS3Role'
WHERE id = 12;
```

### 2. IAM Role Must Exist in AWS
The IAM role must be created in your AWS account with the following:

**Trust Policy** (allows Redshift to assume the role):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "redshift.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

**Permissions Policy** (allows S3 access):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-bucket-name/*",
        "arn:aws:s3:::your-bucket-name"
      ]
    }
  ]
}
```

### 3. Redshift Cluster Must Trust the IAM Role
The IAM role must be attached to your Redshift cluster:

```bash
aws redshift modify-cluster-iam-roles \
  --cluster-identifier your-cluster-name \
  --add-iam-roles arn:aws:iam::123456789012:role/RedshiftS3Role
```

Or via AWS Console:
1. Go to Amazon Redshift console
2. Select your cluster
3. Click "Actions" → "Manage IAM roles"
4. Add the IAM role ARN
5. Click "Save"

## Running the Test

### Step 1: Activate Virtual Environment
```bash
cd backend
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows
```

### Step 2: Run the Test Script
```bash
python test_iam_role_from_db.py
```

## Expected Output

### Success Case
```
================================================================================
IAM ROLE ARN DATABASE TEST
================================================================================

This script verifies that:
1. IAM role ARN is stored in the database
2. IAM role ARN is correctly retrieved
3. IAM role ARN is used in RedshiftLoader
4. IAM role has proper S3 permissions
================================================================================

================================================================================
TESTING IAM ROLE ARN FROM DATABASE
================================================================================

1. Fetching migration 12 from database...
✓ Migration found: bq_rs_mig
  Status: completed
  Pathway: C
  Current Stage: load

2. Checking IAM role ARN...
✓ IAM role ARN found: arn:aws:iam::123456789012:role/RedshiftS3Role

3. Fetching target connection details...
✓ Target connection found: redshift_demo
  Cluster: redshift-cluster-1.abc123.us-east-1.redshift.amazonaws.com
  Port: 5439
  Database: dev
  Username: admin
  Password: ***encrypted***

4. Decrypting Redshift password...
✓ Password decrypted successfully

5. Checking AWS credentials...
✓ AWS Access Key ID: AKIAIOSFOD...
✓ AWS Secret Key decrypted successfully

6. Checking S3 configuration...
✓ S3 Bucket: my-migration-bucket
  S3 Path: /migrations/bq-to-redshift

7. Initializing RedshiftLoader with IAM role...
   This will test if the IAM role can be used for S3 access
✓ RedshiftLoader initialized
  IAM Role ARN: arn:aws:iam::123456789012:role/RedshiftS3Role

8. Testing Redshift connection...
✓ Connected to Redshift successfully

9. Verifying IAM role permissions...
✓ IAM role verified successfully
  The IAM role has proper permissions for S3 access

10. Sample COPY command that would be executed:
--------------------------------------------------------------------------------

COPY public.customers
FROM 's3://my-migration-bucket/migrations/bq-to-redshift/customers/manifest.json'
IAM_ROLE 'arn:aws:iam::123456789012:role/RedshiftS3Role'
FORMAT AS PARQUET
MANIFEST
STATUPDATE ON
COMPUPDATE ON;

--------------------------------------------------------------------------------

✓ Disconnected from Redshift

================================================================================
✅ IAM ROLE TEST COMPLETED SUCCESSFULLY
================================================================================

Summary:
  ✓ Migration ID: 12
  ✓ Migration Name: bq_rs_mig
  ✓ IAM Role ARN: arn:aws:iam::123456789012:role/RedshiftS3Role
  ✓ Redshift Cluster: redshift-cluster-1.abc123.us-east-1.redshift.amazonaws.com
  ✓ Redshift Database: dev
  ✓ S3 Bucket: my-migration-bucket
  ✓ Connection: Successful
  ✓ IAM Role: Verified

The IAM role is correctly configured and ready for S3 to Redshift load!
================================================================================

✅ All tests passed!
```

### Failure Cases

#### Case 1: IAM Role ARN Not Set
```
2. Checking IAM role ARN...
❌ IAM role ARN not found in migration record
   Please update the migration with a valid IAM role ARN
```

**Solution**: Update the migration with IAM role ARN (see Prerequisites)

#### Case 2: IAM Role Verification Failed
```
9. Verifying IAM role permissions...
❌ IAM role verification failed
   The IAM role may not have proper S3 permissions
   Required permissions:
   - s3:GetObject
   - s3:ListBucket
```

**Solution**: 
1. Check IAM role exists in AWS
2. Verify trust policy allows Redshift to assume role
3. Verify permissions policy grants S3 access
4. Attach role to Redshift cluster

#### Case 3: Connection Failed
```
8. Testing Redshift connection...
❌ Failed to connect to Redshift
   Check cluster endpoint, credentials, and network access
```

**Solution**:
1. Verify Redshift cluster is running
2. Check security group allows inbound connections
3. Verify credentials are correct
4. Check network connectivity

## What Happens During Actual Migration

When you run a migration with Pathway C, the system:

1. **Orchestrator** fetches migration from database including `iam_role_arn`
2. **Orchestrator** passes `iam_role_arn` in `target_config` to Pathway C
3. **Pathway C** receives `iam_role_arn` and passes to RedshiftLoader
4. **RedshiftLoader** uses `iam_role_arn` in COPY command:
   ```sql
   COPY schema.table
   FROM 's3://bucket/path/manifest.json'
   IAM_ROLE 'arn:aws:iam::123456789012:role/RedshiftS3Role'
   FORMAT AS PARQUET
   MANIFEST;
   ```
5. **Redshift** assumes the IAM role and accesses S3 to load data

## Verification Steps

After running the test successfully:

1. **Check Database**:
   ```sql
   SELECT id, migration_name, iam_role_arn, status
   FROM migrations_bq_redshift
   WHERE id = 12;
   ```

2. **Check Redshift Cluster IAM Roles**:
   ```bash
   aws redshift describe-clusters \
     --cluster-identifier your-cluster-name \
     --query 'Clusters[0].IamRoles'
   ```

3. **Test COPY Command Manually** (optional):
   ```sql
   -- Connect to Redshift
   COPY test_table
   FROM 's3://your-bucket/test-file.parquet'
   IAM_ROLE 'arn:aws:iam::123456789012:role/RedshiftS3Role'
   FORMAT AS PARQUET;
   ```

## Troubleshooting

### Issue: "IAM role ARN not found"
- Update migration via UI or SQL
- Ensure "Save & Continue" was clicked in UI

### Issue: "IAM role verification failed"
- Check IAM role exists: `aws iam get-role --role-name RedshiftS3Role`
- Check trust policy allows Redshift
- Check permissions policy grants S3 access
- Attach role to cluster

### Issue: "Connection failed"
- Check cluster status: `aws redshift describe-clusters`
- Check security group rules
- Verify VPC and subnet configuration
- Test network connectivity: `telnet cluster-endpoint 5439`

### Issue: "Access Denied" during COPY
- Verify S3 bucket permissions
- Check IAM role has s3:GetObject and s3:ListBucket
- Verify bucket policy allows access from IAM role
- Check S3 bucket encryption settings

## Next Steps

After successful test:

1. **Run Full Migration**: Start or resume migration 12
2. **Monitor Progress**: Check migration logs for COPY command execution
3. **Verify Data**: Query Redshift tables to confirm data loaded
4. **Check Metrics**: Review row counts and load statistics

## Related Files

- **Test Script**: `backend/test_iam_role_from_db.py`
- **Orchestrator**: `backend/services/bq_redshift_migration/orchestrator.py`
- **Pathway C**: `backend/services/bq_redshift_migration/pathway_c.py`
- **Redshift Loader**: `backend/services/bq_redshift_migration/redshift_loader.py`
- **Migration Model**: `backend/models/bq_redshift_migration.py`

## Summary

This test confirms that:
- ✅ IAM role ARN is stored in database
- ✅ IAM role ARN is retrieved correctly
- ✅ IAM role ARN is passed through the entire pipeline
- ✅ IAM role ARN is used in COPY command
- ✅ IAM role has proper S3 permissions
- ✅ Redshift can assume the IAM role
- ✅ End-to-end S3 to Redshift load will work

The IAM role integration is complete and ready for production use!
