# Query Insights and User Insights Not Showing - Fix Guide

## Problem

### Symptom
The Query Insights and User Insights tabs in the Assessment Report page are not displaying data as expected. The tabs may show:
- Empty state ("No query statistics found")
- Zero users
- No query activity charts
- Missing KPI metrics

### Impact
- Cannot analyze query patterns
- Cannot identify user activity
- Missing performance insights
- Incomplete assessment reports

---

## Root Causes

There are several possible reasons why Query Insights and User Insights might not show data:

### 1. No Query Statistics Collected

**Cause**: The BigQuery assessment didn't collect query statistics from `INFORMATION_SCHEMA.JOBS_BY_PROJECT`.

**Symptoms**:
- `query_stats` array is empty in the API response
- Backend logs show errors accessing INFORMATION_SCHEMA
- Assessment completed but query stats count is 0

**Why This Happens**:
- BigQuery region detection failed
- INFORMATION_SCHEMA.JOBS_BY_PROJECT not accessible
- No queries executed in the last 180 days
- Service account lacks permissions

### 2. Region Detection Issues

**Cause**: The assessment service couldn't detect the correct BigQuery region for querying INFORMATION_SCHEMA.

**Code Location**: `backend/services/bigquery_assessment_service.py` (line ~500)

```python
# Detect the region from the first dataset
region = 'us'  # Default fallback
try:
    datasets = list(self.client.list_datasets())
    if datasets:
        first_dataset = self.client.get_dataset(datasets[0].dataset_id)
        if first_dataset.location:
            location = first_dataset.location.lower()
            if location.startswith('us'):
                region = 'us'
            elif location.startswith('eu'):
                region = 'eu'
            # ...
```

**Issue**: If region detection fails or uses wrong region, the INFORMATION_SCHEMA query will fail.

### 3. Service Account Permissions

**Cause**: The BigQuery service account doesn't have permission to query INFORMATION_SCHEMA.

**Required Permissions**:
- `bigquery.jobs.list`
- `bigquery.jobs.get`
- Access to `INFORMATION_SCHEMA.JOBS_BY_PROJECT`

### 4. Frontend Time Filter Issues

**Cause**: Time filtering logic in frontend might be filtering out all data.

**Code Location**: `frontend/src/pages/AssessmentReportPage.tsx`

---

## Diagnosis Steps

### Step 1: Check if Query Stats Were Collected

Run the diagnostic script:

```bash
cd backend
python debug_query_insights.py <assessment_id>
```

**Expected Output**:
```
================================================================================
Assessment: My Assessment (ID: 1)
Status: completed
Project ID: my-project-123
================================================================================

📊 Query Statistics
================================================================================
Total query_stats records: 1234

✅ Found 1234 query statistics

Unique users: 5
Users: user1@example.com, user2@example.com, ...
```

**If you see "NO QUERY STATS FOUND"**:
- The assessment didn't collect query statistics
- Proceed to Step 2

### Step 2: Check Backend Logs

Look for errors in the assessment logs:

```bash
# Check backend logs
tail -f backend/backend.log | grep -i "query statistics"
```

**Look for**:
- "Querying INFORMATION_SCHEMA with region: ..."
- "✓ Collected X query statistics from region-..."
- "Warning: Could not collect query statistics from region-..."
- Any error messages about INFORMATION_SCHEMA

### Step 3: Verify BigQuery Permissions

Test if the service account can query INFORMATION_SCHEMA:

```python
from google.cloud import bigquery
from google.oauth2 import service_account
import json

# Load credentials
with open('path/to/service-account.json') as f:
    creds_json = json.load(f)

credentials = service_account.Credentials.from_service_account_info(creds_json)
client = bigquery.Client(credentials=credentials, project='your-project-id')

# Test query
query = """
SELECT COUNT(*) as job_count
FROM `your-project-id.region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
"""

try:
    results = client.query(query).result()
    for row in results:
        print(f"✅ Found {row.job_count} jobs in last 7 days")
except Exception as e:
    print(f"❌ Error: {e}")
```

### Step 4: Check Frontend Console

Open browser DevTools console and look for:

```javascript
[Query Insights Debug]
Total queryStats received: 0  // ❌ Problem: No data from backend
After time filter: 0
Time filter: all
```

If `Total queryStats received: 0`, the backend isn't returning data.

---

## Solutions

### Solution 1: Re-run Assessment with Correct Region

If region detection failed, manually specify the region:

**File**: `backend/services/bigquery_assessment_service.py`

```python
async def collect_query_statistics_detailed(self) -> List[Dict]:
    """
    Collect detailed query statistics from INFORMATION_SCHEMA.JOBS
    """
    query_stats = []
    
    # OPTION 1: Auto-detect region (current implementation)
    region = 'us'  # Default fallback
    try:
        datasets = list(self.client.list_datasets())
        if datasets:
            first_dataset = self.client.get_dataset(datasets[0].dataset_id)
            if first_dataset.location:
                location = first_dataset.location.lower()
                # ... region detection logic
    except Exception as e:
        print(f"Warning: Could not detect region, using default 'us': {e}")
    
    # OPTION 2: Hardcode region if auto-detection fails
    # region = 'us'  # or 'eu', 'asia-northeast1', etc.
    
    # Query INFORMATION_SCHEMA
    query = f"""
    SELECT
        job_id,
        creation_time as execution_time,
        query as query_text,
        total_bytes_processed as bytes_scanned,
        total_slot_ms as slot_milliseconds,
        cache_hit,
        referenced_tables,
        user_email,
        state,
        error_result
    FROM `{self.project_id}.region-{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
    WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 180 DAY)
        AND job_type = 'QUERY'
        AND state = 'DONE'
    ORDER BY creation_time DESC
    LIMIT 50000
    """
    
    try:
        print(f"Querying INFORMATION_SCHEMA with region: {region}")
        query_job = self.client.query(query)
        results = query_job.result()
        
        for row in results:
            # ... process results
        
        print(f"✓ Collected {len(query_stats)} query statistics from region-{region}")
    except Exception as e:
        print(f"Warning: Could not collect query statistics from region-{region}: {e}")
        print(f"Error details: {str(e)}")
    
    return query_stats
```

**To fix**:
1. Identify your BigQuery region (check in BigQuery console)
2. Update the region detection logic or hardcode the region
3. Re-run the assessment

### Solution 2: Grant Service Account Permissions

Ensure the service account has the required permissions:

**Required IAM Roles**:
- `roles/bigquery.jobUser` - To query INFORMATION_SCHEMA
- `roles/bigquery.dataViewer` - To read job metadata

**Grant permissions**:
```bash
# Grant BigQuery Job User role
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:YOUR_SERVICE_ACCOUNT@YOUR_PROJECT.iam.gserviceaccount.com" \
    --role="roles/bigquery.jobUser"

# Grant BigQuery Data Viewer role
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:YOUR_SERVICE_ACCOUNT@YOUR_PROJECT.iam.gserviceaccount.com" \
    --role="roles/bigquery.dataViewer"
```

### Solution 3: Try Different Region Formats

BigQuery INFORMATION_SCHEMA uses different region formats:

**Common formats**:
- `region-us` - For US multi-region
- `region-eu` - For EU multi-region
- `region-us-central1` - For specific US region
- `region-asia-northeast1` - For specific Asia region

**Test different formats**:
```python
# Try these region formats
regions_to_try = [
    'us',
    'us-central1',
    'us-east1',
    'us-west1',
    'eu',
    'europe-west1',
    'asia-northeast1'
]

for region in regions_to_try:
    try:
        query = f"""
        SELECT COUNT(*) as cnt
        FROM `{project_id}.region-{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
        LIMIT 1
        """
        result = client.query(query).result()
        print(f"✅ Region '{region}' works!")
        break
    except Exception as e:
        print(f"❌ Region '{region}' failed: {e}")
```

### Solution 4: Check for Empty Query History

If BigQuery has no query history, there's nothing to collect:

**Verify query history exists**:
```sql
-- Run this in BigQuery console
SELECT COUNT(*) as query_count
FROM `your-project-id.region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  AND job_type = 'QUERY'
  AND state = 'DONE';
```

**If count is 0**:
- No queries were executed in the last 7 days
- Query Insights will be empty (this is expected)
- Run some queries in BigQuery, then re-run assessment

### Solution 5: Increase Query Limit

If you have many queries but only seeing a few:

**File**: `backend/services/bigquery_assessment_service.py` (line ~550)

```python
# Current limit
LIMIT 50000

# Increase if needed
LIMIT 100000
```

**Note**: Be careful with very large limits as it may impact performance.

---

## Verification

### Test Query Insights

1. Navigate to Assessment Report
2. Click "Query Insights" tab
3. Verify:
   - ✅ KPI tiles show metrics (Total Queries, Avg Execution Time, Cache Hit Rate, Total Bytes Scanned)
   - ✅ Pie chart shows Read vs Write distribution
   - ✅ Bar chart shows hourly/daily activity
   - ✅ Query list shows recent queries with user, execution time, data scanned, cache status

### Test User Insights

1. Click "User Insights" tab
2. Verify:
   - ✅ Shows count of unique users
   - ✅ Table lists all users with metrics
   - ✅ Metrics include: Queries Executed, Total Data Scanned, Slots Utilized, Cache Hit Ratio
   - ✅ Time filter works (All Time, Last 24 Hours, Last 7 Days, Last 30 Days)

### Test Time Filters

1. In Query Insights, change time filter to "Last 24 Hours"
   - ✅ Data updates to show only recent queries
   - ✅ KPIs recalculate
   - ✅ Charts update

2. In User Insights, change time filter to "Last 7 Days"
   - ✅ User list updates
   - ✅ Metrics recalculate for time period

---

## Prevention

### Best Practices

1. **Always check assessment logs** after completion
   - Look for "✓ Collected X query statistics"
   - If X is 0, investigate immediately

2. **Test INFORMATION_SCHEMA access** before running assessments
   - Run a simple test query
   - Verify service account permissions

3. **Document BigQuery region** in connection metadata
   - Store region with connection
   - Use stored region instead of auto-detection

4. **Add region parameter** to assessment creation
   - Allow users to specify region
   - Fall back to auto-detection if not provided

5. **Improve error messages**
   - Show specific error if INFORMATION_SCHEMA fails
   - Provide troubleshooting steps in UI

### Code Improvements

**Add region parameter to assessment**:

```python
# In assessment creation
async def create_assessment(
    connection_id: int,
    name: str,
    bigquery_region: Optional[str] = None,  # NEW: Allow region override
    db: Session = Depends(get_db)
):
    # ... existing code
    
    # Pass region to service
    service = BigQueryAssessmentService({
        'project_id': connection.project_id,
        'credentials_json': decrypted_creds,
        'region': bigquery_region  # NEW: Use provided region
    })
```

**Better error handling**:

```python
try:
    query_stats_data = await self.collect_query_statistics_detailed()
    if query_stats_data:
        repo.bulk_create_query_stats(assessment_id, query_stats_data)
    print(f"✓ Collected {len(query_stats_data)} query statistics")
except Exception as e:
    # Don't fail assessment, but log warning
    error_msg = f"Warning: Could not collect query statistics: {str(e)}"
    print(error_msg)
    repo.add_log(assessment_id, 'warning', error_msg)
    # Continue with assessment
```

---

## Related Files

### Backend Files
- `backend/services/bigquery_assessment_service.py` - Query statistics collection
- `backend/routers/assessment_router.py` - API endpoint returning query_stats
- `backend/repositories/assessment_repository.py` - Database queries
- `backend/models/assessment.py` - AssessmentQueryStat model
- `backend/debug_query_insights.py` - Diagnostic script (NEW)

### Frontend Files
- `frontend/src/pages/AssessmentReportPage.tsx` - Query Insights and User Insights components
- `frontend/src/services/assessmentsApi.ts` - API client

---

## Common Error Messages

### "No query statistics found for selected time period"

**Cause**: Time filter is excluding all data

**Fix**: 
1. Change time filter to "All Time"
2. Check if query_stats has data with execution_time in the past

### "Warning: Could not collect query statistics from region-X"

**Cause**: Wrong region or permissions issue

**Fix**:
1. Verify BigQuery region
2. Check service account permissions
3. Try different region format

### "INFORMATION_SCHEMA.JOBS_BY_PROJECT not found"

**Cause**: Region format is incorrect

**Fix**:
1. Use correct region format: `region-us`, `region-eu`, etc.
2. Check BigQuery documentation for your region

---

## Status

📋 **DIAGNOSTIC TOOL CREATED** - February 15, 2026

### Tools Added
- [x] `backend/debug_query_insights.py` - Diagnostic script to check query stats data
- [x] `docs/fixes/QUERY_USER_INSIGHTS_FIX.md` - Comprehensive fix guide

### Next Steps
1. Run diagnostic script on affected assessments
2. Identify root cause (no data vs. frontend issue)
3. Apply appropriate solution
4. Re-run assessment if needed
5. Verify Query Insights and User Insights display correctly

---

**Created By**: DataMIQ Development Team  
**Date**: February 15, 2026  
**Type**: Diagnostic Guide & Troubleshooting
