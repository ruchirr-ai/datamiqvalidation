# Quick Fix: Enable RLS Policies Display

## 🎯 Problem
Your BigQuery has RLS policies, but they're not showing in the assessment report due to missing service account permissions.

## 🔑 Service Account Details
- **Email**: `assesiq@assessiq-484512.iam.gserviceaccount.com`
- **Project**: `assessiq-484512`

## ⚡ Quick Fix (Choose One)

### Option 1: Grant Metadata Viewer Role (Recommended - 30 seconds)

Run this command in your terminal:

```bash
gcloud projects add-iam-policy-binding assessiq-484512 \
  --member="serviceAccount:assesiq@assessiq-484512.iam.gserviceaccount.com" \
  --role="roles/bigquery.metadataViewer"
```

### Option 2: Manual Export (If you can't grant permissions - 5 minutes)

1. Open BigQuery Console
2. Run this query with YOUR user account:

```sql
SELECT
    table_schema,
    table_name,
    policy_name,
    filter_predicate,
    grantee_list,
    ddl
FROM `assessiq-484512.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES`
ORDER BY table_schema, table_name;
```

3. Export results and contact me to import them

## ✅ After Granting Permissions

### Step 1: Wait 1-2 minutes for IAM changes to propagate

### Step 2: Run backfill script

```bash
cd backend
source .venv/bin/activate
python scripts/backfill_security_metadata.py
```

### Step 3: Verify

1. Open assessment report in browser
2. Go to "Security Policies" tab
3. RLS policies should now be visible!

## 🧪 Test Permissions (Optional)

After granting permissions, test if it worked:

```bash
bq query --use_legacy_sql=false \
  --impersonate_service_account=assesiq@assessiq-484512.iam.gserviceaccount.com \
  "SELECT COUNT(*) as policy_count FROM \`assessiq-484512.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES\`"
```

If this returns a count, permissions are working!

## 📚 Detailed Documentation

- Full guide: [RLS_POLICIES_PERMISSIONS_FIX.md](./RLS_POLICIES_PERMISSIONS_FIX.md)
- Technical details: [SECURITY_POLICIES_FIX.md](./SECURITY_POLICIES_FIX.md)

## ❓ Why This Happened

The service account needs specific permissions to read RLS policies:
- `bigquery.rowAccessPolicies.list`
- `bigquery.rowAccessPolicies.get`
- `bigquery.tables.get`
- `bigquery.tables.getData`

The `BigQuery Metadata Viewer` role includes all of these.
