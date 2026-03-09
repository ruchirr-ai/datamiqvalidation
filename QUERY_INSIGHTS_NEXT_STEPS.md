# Query Insights - Next Steps

## Current Status ✅

The fix is **WORKING** and loaded in the running backend server:
- ✅ Project ID is correctly extracted from credentials (`assessiq-484512`)
- ✅ Region detection is fixed (`asia-south1`)
- ✅ Backend server is running with the fixed code

## Why You're Not Seeing Data

Assessment ID 10 (`bq_rs_assess`) was created on **Feb 14** BEFORE the fix was applied.
- Query Stats Count: **0** (because the fix wasn't applied yet)
- The old assessment cannot be "fixed" - you need to create a new one

## Data Collection Period

The assessment service collects **180 days** of query history (not 7 days):

```python
# From backend/services/bigquery_assessment_service.py
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 180 DAY)
```

**Note**: The diagnostic script uses 7 days for quick testing, but the actual assessment uses 180 days.

## Action Required: Create New Assessment

### Step 1: Go to Assessments Page
```
http://localhost:3000/assessments
```

### Step 2: Create New Assessment
1. Click "Create Assessment" button
2. Fill in the form:
   - **Name**: `bq_assessment_with_query_insights` (or any name)
   - **Source Connection**: Select `bq_demo` (BigQuery)
   - **Target Connection**: Select `redshift_demo` (Redshift)
3. Click "Create"

### Step 3: Wait for Completion
The assessment will:
1. Collect datasets (few seconds)
2. Collect tables (few seconds)
3. Collect columns (few seconds)
4. Collect views (few seconds)
5. Collect routines/stored procedures (few seconds)
6. **Collect query statistics - 180 days** (may take 10-30 seconds)
7. Collect ML models (few seconds)
8. Collect security policies (few seconds)

Total time: ~1-2 minutes

### Step 4: Verify Query Insights
1. Click on the completed assessment
2. Go to "Query Insights" tab
3. You should see:
   - **Total Queries**: Count of all queries in last 180 days
   - **Active Users**: Count of unique users
   - **Bytes Scanned**: Total bytes processed
   - **Cache Hit Rate**: Percentage of cached queries
   - **Query Table**: Detailed list with:
     - Job ID
     - Execution Time
     - User Email
     - Bytes Scanned
     - Slot Milliseconds
     - Cache Hit Status
     - Query Text (expandable)

### Step 5: Test Timeframe Filters
The Query Insights tab has filters:
- **All Time**: Shows all 180 days of data
- **Last 24 hours**: Filters to last 24 hours
- **Last 7 days**: Filters to last 7 days
- **Last 30 days**: Filters to last 30 days

## Expected Results

Based on the diagnostic script, you should see:
- At least **3 queries** in the last 7 days
- Queries from users:
  - `assesiq@assessiq-484512.iam.gserviceaccount.com`
  - `manasa.k@shellkode.com`

If there are more queries in the 180-day window, you'll see all of them.

## If You Still See No Data

### Check 1: Verify Assessment Completed Successfully
```bash
cd backend
python check_query_stats.py <assessment_id>
```

### Check 2: Check Backend Logs
Look for errors during query statistics collection:
```bash
cd backend
tail -100 backend.log | grep -i "query statistics"
```

### Check 3: Run Diagnostic Again
```bash
cd backend
python diagnose_query_insights_production.py
```

Should show:
```
✓ Found 3 queries in last 7 days
✓ Successfully fetched 3 sample queries
```

## Troubleshooting

### "No queries found in last 180 days"
This means:
1. No queries have been executed in BigQuery in the last 180 days
2. OR service account lacks permissions

**Solution**: Execute some queries in BigQuery Console, then run a new assessment.

### "Permission denied" errors
Service account needs:
- `BigQuery Job User` role
- `BigQuery Data Viewer` role

**Solution**: Grant roles in GCP Console > IAM & Admin > IAM

## Summary

1. ✅ Fix is working and loaded
2. ❌ Old assessment (ID 10) has no data (created before fix)
3. ✅ New assessment will collect 180 days of query history
4. 🎯 **Action**: Create a new assessment now

The Query Insights feature will work correctly for any new assessments created after the fix.
