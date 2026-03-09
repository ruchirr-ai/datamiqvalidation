# RLS Policies - Permissions Fix

## Issue
Your BigQuery project has RLS policies, but the service account cannot access them due to missing permissions.

## Root Cause
The service account needs specific IAM permissions to read Row-Level Security policies:
- `bigquery.rowAccessPolicies.list`
- `bigquery.rowAccessPolicies.get`
- `bigquery.tables.get`
- `bigquery.tables.getData`

## Solution: Grant Required Permissions

### Option 1: Use Predefined Role (Recommended)

Grant the **BigQuery Metadata Viewer** role to your service account:

```bash
# Replace with your service account email
SERVICE_ACCOUNT="your-service-account@project-id.iam.gserviceaccount.com"
PROJECT_ID="assessiq-484512"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/bigquery.metadataViewer"
```

### Option 2: Create Custom Role with Minimal Permissions

If you want more granular control:

```bash
# 1. Create custom role
gcloud iam roles create bigqueryRLSReader \
  --project=$PROJECT_ID \
  --title="BigQuery RLS Reader" \
  --description="Can read Row-Level Security policies" \
  --permissions="bigquery.rowAccessPolicies.list,bigquery.rowAccessPolicies.get,bigquery.tables.get,bigquery.tables.getData" \
  --stage=GA

# 2. Grant custom role to service account
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="projects/$PROJECT_ID/roles/bigqueryRLSReader"
```

### Option 3: Grant at Dataset Level

If you only want to grant access to specific datasets:

```bash
# For each dataset with RLS policies
DATASET_ID="sales_analytics"

bq show --format=prettyjson $PROJECT_ID:$DATASET_ID > dataset_policy.json

# Edit dataset_policy.json to add:
# {
#   "access": [
#     {
#       "role": "READER",
#       "userByEmail": "your-service-account@project-id.iam.gserviceaccount.com"
#     }
#   ]
# }

bq update --source dataset_policy.json $PROJECT_ID:$DATASET_ID
```

## After Granting Permissions

### Step 1: Verify Permissions

```bash
# Check if service account can list RLS policies
bq query --use_legacy_sql=false \
  --impersonate_service_account=$SERVICE_ACCOUNT \
  "SELECT * FROM \`$PROJECT_ID.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES\` LIMIT 1"
```

### Step 2: Run Backfill Script

```bash
cd backend
source .venv/bin/activate
python scripts/backfill_security_metadata.py
```

### Step 3: Verify in UI

1. Open assessment report in browser
2. Go to Security Policies tab
3. RLS policies should now be visible

## Manual Workaround (If You Can't Grant Permissions)

If you cannot grant the required permissions, you can manually add RLS policy information:

### Step 1: Export RLS Policies from BigQuery Console

```sql
-- Run this query in BigQuery Console with your user account
SELECT
    table_schema,
    table_name,
    policy_name,
    filter_predicate,
    grantee_list,
    ddl
FROM `assessiq-484512.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES`
ORDER BY table_schema, table_name, policy_name;
```

### Step 2: Save Results as JSON

Export the query results and save as `rls_policies.json`:

```json
[
  {
    "table_schema": "sales_analytics",
    "table_name": "customers",
    "policy_name": "regional_access",
    "filter_predicate": "region = 'US'",
    "grantee_list": "user:analyst@example.com",
    "ddl": "CREATE ROW ACCESS POLICY regional_access ON `project.dataset.table` GRANT TO ('user:analyst@example.com') FILTER USING (region = 'US')"
  }
]
```

### Step 3: Import Manually

Create a script to import the policies:

```bash
cd backend
python -c "
import json
import sys
sys.path.insert(0, '.')

from database import db_instance
from repositories.assessment_repository import AssessmentRepository

# Load your exported policies
with open('rls_policies.json', 'r') as f:
    policies = json.load(f)

# Convert to expected format
security_data = []
for policy in policies:
    security_data.append({
        'security_type': 'RLS',
        'table_name': f\"{policy['table_schema']}.{policy['table_name']}\",
        'policy_name': policy['policy_name'],
        'filter_predicate': policy['filter_predicate'],
        'grantees': policy['grantee_list'].split(',') if policy['grantee_list'] else [],
        'creation_time': None,
        'security_metadata': {
            'ddl': policy.get('ddl')
        }
    })

# Save to database
db = db_instance.SessionLocal()
try:
    repo = AssessmentRepository(db)
    assessment_id = 10  # Your assessment ID
    
    # Delete existing policies
    db.execute('DELETE FROM assessment_security WHERE assessment_id = :id', {'id': assessment_id})
    
    # Insert new policies
    repo.bulk_create_security_policies(assessment_id, security_data)
    db.commit()
    
    print(f'✓ Imported {len(security_data)} RLS policies')
finally:
    db.close()
"
```

## Troubleshooting

### Check Current Service Account Permissions

```bash
# Get service account email from connection
cd backend
python -c "
import sys
sys.path.insert(0, '.')
import json
from database import db_instance
from repositories.connection_repository import ConnectionRepository

db = db_instance.SessionLocal()
try:
    repo = ConnectionRepository(db)
    conn = repo.get_by_id(6)
    creds = conn.connection_params.get('credentials_json')
    if isinstance(creds, str):
        creds = json.loads(creds)
    print(f\"Service Account: {creds.get('client_email')}\")
finally:
    db.close()
"

# Then check permissions
gcloud projects get-iam-policy $PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:YOUR_SERVICE_ACCOUNT_EMAIL"
```

### Test BigQuery Access

```bash
# Test if service account can query INFORMATION_SCHEMA
bq query --use_legacy_sql=false \
  --impersonate_service_account=$SERVICE_ACCOUNT \
  "SELECT COUNT(*) as policy_count FROM \`$PROJECT_ID.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES\`"
```

## Required IAM Roles Summary

| Role | Permissions | Use Case |
|------|-------------|----------|
| `roles/bigquery.metadataViewer` | Full metadata read access | Recommended for assessments |
| `roles/bigquery.dataViewer` | Data + metadata read | If you also need to read data |
| Custom role | Minimal RLS permissions | Most restrictive option |

## Next Steps

1. **Grant permissions** using one of the options above
2. **Verify access** using the test queries
3. **Run backfill script** to collect RLS policies
4. **Check UI** to confirm policies are displayed

## Support

If you continue to have issues:
1. Verify the service account email is correct
2. Check that IAM policy changes have propagated (can take a few minutes)
3. Ensure you're using the correct project ID
4. Try the manual workaround if permissions cannot be granted
