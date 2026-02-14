# Redshift Load - IAM Role Required

## Current Status

✅ **Export Stage**: COMPLETED
- 2 tables exported from BigQuery to GCS
- Files: customers (729 B), orders (740 B)
- Total: 1.43 KB

✅ **Transfer Stage**: COMPLETED
- 2 files transferred from GCS to S3
- Source: gs://bq_data_transfer_rs/staging
- Destination: s3://sk-manasa/staging
- Success rate: 100%

❌ **Load Stage**: BLOCKED
- Cannot load data from S3 to Redshift
- **Reason**: IAM role ARN is missing

## The Issue

Redshift requires an IAM role to access S3 buckets. The COPY command uses this role to authenticate and read files from S3.

**Current State**:
- Migration 12: `iam_role_arn = None`
- Target Connection 7: No IAM role in connection_params

**Error Message**:
```
ERROR: IAM role ARN not specified
ERROR: IAM role is required for Redshift to access S3
```

## What is an IAM Role ARN?

An IAM role ARN (Amazon Resource Name) looks like:
```
arn:aws:iam::123456789012:role/RedshiftS3AccessRole
```

This role must have:
1. **Trust relationship** with Redshift service
2. **S3 read permissions** for the bucket (sk-manasa)
3. **Attached to the Redshift cluster** (redshift-cluster)

## How to Fix

### Option 1: Create IAM Role in AWS Console

1. **Create IAM Role**:
   - Go to AWS IAM Console
   - Create new role
   - Select "Redshift" as trusted entity
   - Attach policy: `AmazonS3ReadOnlyAccess` or custom policy for bucket `sk-manasa`
   - Name: `RedshiftS3AccessRole`
   - Copy the ARN

2. **Attach Role to Redshift Cluster**:
   - Go to AWS Redshift Console
   - Select cluster: `redshift-cluster`
   - Actions → Manage IAM roles
   - Add the role you created
   - Set as default IAM role

3. **Update Migration Record**:
   ```sql
   UPDATE migrations_bq_redshift 
   SET iam_role_arn = 'arn:aws:iam::YOUR_ACCOUNT:role/RedshiftS3AccessRole'
   WHERE id = 12;
   ```

4. **Re-run Fix Script**:
   ```bash
   cd backend
   python fix_migration_12.py
   ```

### Option 2: Update via UI

1. Edit migration 12 in the UI
2. Add IAM role ARN in the configuration
3. Save and re-run the migration

### Option 3: Use AWS CLI

```bash
# Create IAM role
aws iam create-role \
  --role-name RedshiftS3AccessRole \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "redshift.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

# Attach S3 read policy
aws iam attach-role-policy \
  --role-name RedshiftS3AccessRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess

# Get the role ARN
aws iam get-role --role-name RedshiftS3AccessRole --query 'Role.Arn'

# Attach to Redshift cluster
aws redshift modify-cluster-iam-roles \
  --cluster-identifier redshift-cluster \
  --add-iam-roles arn:aws:iam::YOUR_ACCOUNT:role/RedshiftS3AccessRole \
  --default-iam-role-arn arn:aws:iam::YOUR_ACCOUNT:role/RedshiftS3AccessRole
```

## Example IAM Policy for S3 Access

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
        "arn:aws:s3:::sk-manasa",
        "arn:aws:s3:::sk-manasa/*"
      ]
    }
  ]
}
```

## Testing After Fix

Once the IAM role is configured:

```bash
cd backend
python fix_migration_12.py
```

Expected output:
```
✓ Transfer already completed, skipping
Running LOAD stage...
INITIALIZING REDSHIFT LOADER
✓ Connected to Redshift
✓ IAM role verified
LOADING TABLES TO REDSHIFT
TABLE 1/2: customers
✓ Table customers loaded successfully
  Rows loaded: X
TABLE 2/2: orders
✓ Table orders loaded successfully
  Rows loaded: Y
✓ LOAD STAGE COMPLETED
✓ MIGRATION 12 FIXED SUCCESSFULLY
```

## Verification

After successful load, verify data in Redshift:

```sql
-- Connect to Redshift
psql -h redshift-cluster.XXXXX.us-east-1.redshift.amazonaws.com \
     -U awsuser -d target_db -p 5439

-- Check tables
\dt public.*

-- Check row counts
SELECT 'customers' as table_name, COUNT(*) as row_count FROM public.customers
UNION ALL
SELECT 'orders' as table_name, COUNT(*) as row_count FROM public.orders;

-- Sample data
SELECT * FROM public.customers LIMIT 5;
SELECT * FROM public.orders LIMIT 5;
```

## Summary

The migration is 66% complete (2 out of 3 stages):
- ✅ Export: BigQuery → GCS
- ✅ Transfer: GCS → S3
- ⏸️ Load: S3 → Redshift (waiting for IAM role)

**Next Step**: Configure IAM role ARN and re-run the fix script to complete the migration.

## Files Modified

- `backend/fix_migration_12.py` - Updated to extract credentials from target connection
- `backend/services/bq_redshift_migration/pathway_c.py` - Fixed execute() logic to verify all stages

## Related Documentation

- [AWS Redshift IAM Roles](https://docs.aws.amazon.com/redshift/latest/mgmt/authorizing-redshift-service.html)
- [Redshift COPY Command](https://docs.aws.amazon.com/redshift/latest/dg/r_COPY.html)
- [IAM Roles for Amazon Redshift](https://docs.aws.amazon.com/redshift/latest/mgmt/copy-unload-iam-role.html)
