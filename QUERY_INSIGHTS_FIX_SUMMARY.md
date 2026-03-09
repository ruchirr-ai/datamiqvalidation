# Query Insights Fix - Summary

## Issue
Query Insights tab was showing no data because query statistics were not being collected during assessment.

## Root Causes Found

### 1. Wrong Project ID ❌
The assessment service was using the connection's `database` field (`"bigquery"`) as the GCP project ID, instead of extracting the actual project ID from the service account credentials (`"assessiq-484512"`).

**Result**: BigQuery API calls failed with "Project bigquery not found"

### 2. Wrong Region Format ❌
The region detection was converting specific regions like `"asia-south1"` to generic regions like `"asia"`, which BigQuery INFORMATION_SCHEMA doesn't support.

**Result**: INFORMATION_SCHEMA queries failed with "Location asia does not support this operation"

## Fixes Applied ✅

### Fix 1: Extract Project ID from Credentials
**File**: `backend/services/bigquery_assessment_service.py`

```python
# Now extracts project_id from service account credentials if not in connection_params
self.project_id = connection_params.get('project_id')
if not self.project_id and credentials_json:
    self.project_id = credentials_json.get('project_id')
```

### Fix 2: Use Exact Region Format
**File**: `backend/services/bigquery_assessment_service.py`

```python
# Now uses exact location (e.g., 'asia-south1') instead of generic 'asia'
if location in ['us', 'eu']:
    region = location  # Multi-region
else:
    region = location  # Specific region (e.g., 'asia-south1')
```

## New Diagnostic Tool 🔧

Created `backend/diagnose_query_insights_production.py` that:
- Reads actual connection from database (like production does)
- Tests BigQuery INFORMATION_SCHEMA access
- Shows detailed error messages with fix instructions
- Verifies query statistics can be collected

**Run it**:
```bash
cd backend
python diagnose_query_insights_production.py
```

## Next Steps for User

### 1. Restart Backend Server
```bash
# Stop current server (Ctrl+C)
./START_BACKEND_HERE.sh
```

### 2. Run Diagnostic (Optional)
```bash
cd backend
python diagnose_query_insights_production.py
```

Should show:
```
✓ Found BigQuery connection: bq_demo
✓ Credentials found for project: assessiq-484512
✓ BigQuery client initialized for project: assessiq-484512
✓ Detected location: asia-south1
✓ Using region for INFORMATION_SCHEMA: asia-south1
✓ Found 3 queries in last 7 days
```

### 3. Create New Assessment
1. Go to http://localhost:3000/assessments
2. Click "Create Assessment"
3. Select BigQuery connection (bq_demo)
4. Select Redshift connection
5. Wait for completion

### 4. Verify Query Insights
- Open the completed assessment
- Go to "Query Insights" tab
- Should now see:
  - Total Queries count
  - Active Users count
  - Bytes Scanned
  - Cache Hit Rate
  - Query details table

## Files Modified

1. `backend/services/bigquery_assessment_service.py` - Fixed project ID extraction and region detection
2. `backend/diagnose_query_insights_production.py` - New diagnostic tool
3. `docs/fixes/QUERY_INSIGHTS_NO_DATA_ROOT_CAUSE_FIX.md` - Complete documentation

## Testing Results

Diagnostic script now successfully:
- ✅ Connects to BigQuery with correct project ID (`assessiq-484512`)
- ✅ Detects correct region (`asia-south1`)
- ✅ Queries INFORMATION_SCHEMA.JOBS_BY_PROJECT
- ✅ Retrieves query statistics (found 3 queries in last 7 days)

## Expected Outcome

After restarting the backend and running a new assessment, Query Insights will display all query statistics including job IDs, execution times, query text, bytes scanned, slot milliseconds, cache hit status, referenced tables, and user emails with timeframe filtering (All Time, Last 24h, Last 7d, Last 30d).
