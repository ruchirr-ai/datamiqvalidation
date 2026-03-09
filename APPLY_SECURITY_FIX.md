# Apply Security Policies Fix to Existing Reports

## Overview
This guide will help you update existing assessment reports to display Row-Level Security (RLS) policies properly.

## What Was Fixed
- Backend API now includes `security_metadata` field (containing DDL statements)
- Created backfill script to re-collect security policies for existing assessments

## Steps to Apply the Fix

### Step 1: Restart Backend Server

The API changes require a backend restart to take effect.

**Option A: If running in terminal**
```bash
# Press Ctrl+C to stop the server
# Then restart:
cd backend
source .venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Option B: If using the start script**
```bash
# Stop the current server (Ctrl+C)
# Then run:
./START_BACKEND_HERE.sh
```

**Option C: If using PM2**
```bash
pm2 restart backend
```

### Step 2: Run Backfill Script

This script will re-collect security policies for all existing completed assessments.

```bash
cd backend
source .venv/bin/activate
python scripts/backfill_security_metadata.py
```

**What the script does:**
1. Finds all completed assessments
2. For each assessment:
   - Connects to BigQuery using the source connection
   - Re-collects all security policies (RLS and CLS)
   - Updates the database with complete metadata including DDL
3. Shows progress and summary

**Expected output:**
```
Security Metadata Backfill Script
============================================================
Found 3 completed assessments

============================================================
Processing Assessment ID: 1
============================================================
Assessment: My BigQuery Assessment
Status: completed
Source Connection: BigQuery Production

Initializing BigQuery service...
Collecting security policies from BigQuery...
✓ Found 5 security policies

  Policy: customer_access_policy
  Table: customers
  Type: ROW_ACCESS_POLICY
  Has DDL: Yes

  Policy: employee_data_policy
  Table: employees
  Type: ROW_ACCESS_POLICY
  Has DDL: Yes

Saving security policies to database...
✓ Successfully backfilled 5 security policies

============================================================
SUMMARY
============================================================
Total assessments processed: 3
Successful: 3
Failed: 0
```

### Step 3: Verify in UI

1. Open your application in the browser
2. Navigate to Assessments page
3. Click "View Report" on any assessment
4. Go to the "Security Policies" tab
5. You should now see:
   - Row-Level Security (RLS) policies with full details
   - Policy DDL/creation statements
   - Column-Level Security (CLS) policy tags

## Troubleshooting

### No Security Policies Found

If the script reports "No security policies found", it could mean:

1. **Your BigQuery dataset doesn't have RLS policies**
   - This is normal if you haven't configured any security policies
   - You can test by creating a sample policy:
   ```sql
   CREATE ROW ACCESS POLICY test_policy
   ON `project.dataset.table`
   GRANT TO ("user:test@example.com")
   FILTER USING (status = 'active');
   ```

2. **Service account lacks permissions**
   - The service account needs `bigquery.rowAccessPolicies.list` permission
   - Grant the "BigQuery Metadata Viewer" role to the service account

3. **Policies exist but in different datasets**
   - The script only collects policies from datasets that were assessed
   - Make sure the assessment included the datasets with policies

### Script Fails with Connection Error

If you see connection errors:

```bash
# Check if the connection credentials are valid
cd backend
source .venv/bin/activate
python -c "
from database import db_instance
from repositories.connection_repository import ConnectionRepository

db = db_instance.SessionLocal()
conn_repo = ConnectionRepository(db)
connections = conn_repo.list_connections()
for conn in connections:
    print(f'Connection: {conn.name}, Type: {conn.connection_type}, Status: {conn.status}')
db.close()
"
```

### Backend Server Not Restarting

If the backend server won't restart:

```bash
# Check if port 8000 is already in use
lsof -i :8000

# Kill any process using port 8000
kill -9 <PID>

# Then restart the server
cd backend
source .venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## What Gets Displayed After Fix

### Row-Level Security (RLS)
- ✓ Policy name
- ✓ Table name  
- ✓ Filter predicate (the WHERE clause)
- ✓ Grantees (users/groups with access)
- ✓ DDL (complete policy creation statement)

### Column-Level Security (CLS)
- ✓ Tables with policy tags
- ✓ Columns with policy tags
- ✓ Policy tag names

## Running the Script Multiple Times

The backfill script is **safe to run multiple times**:
- It will replace existing security policy data with fresh data from BigQuery
- No duplicate entries will be created
- Only completed assessments are processed
- Failed assessments are skipped

## Next Steps

After applying the fix:

1. **Test with a new assessment** - Create a new assessment to verify security policies are collected automatically
2. **Review existing reports** - Check that all existing reports now show security policies
3. **Document your RLS policies** - Use the assessment reports to document your security policies

## Files Modified

- `backend/routers/assessment_router.py` - Added security_metadata to API response
- `backend/scripts/backfill_security_metadata.py` - New backfill script for existing data

## Related Documentation

- [BigQuery Row-Level Security](https://cloud.google.com/bigquery/docs/row-level-security-intro)
- [BigQuery Column-Level Security](https://cloud.google.com/bigquery/docs/column-level-security)
- Assessment Security Model: `backend/models/assessment.py`
- Security Collection Service: `backend/services/bigquery_assessment_service.py`

## Support

If you encounter any issues:
1. Check the backend logs for error messages
2. Verify BigQuery service account permissions
3. Ensure the assessment completed successfully
4. Check that security policies exist in BigQuery
