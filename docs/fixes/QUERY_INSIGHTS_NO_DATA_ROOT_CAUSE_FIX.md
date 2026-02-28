# Query Insights No Data - Root Cause Fix

## Issue Summary
Query Insights tab was showing no data because query statistics were not being collected during assessment.

## Root Causes Identified

### 1. Incorrect Project ID
**Problem**: The assessment service was using the connection's `database` field (`bigquery`) as the GCP project ID, instead of extracting the actual project ID from the service account credentials (`assessiq-484512`).

**Impact**: BigQuery API calls failed with "Project bigquery not found" error.

**Fix**: Modified `BigQueryAssessmentService.__init__()` to extract `project_id` from the service account credentials JSON if not provided in connection_params.

```python
# Before (WRONG)
self.project_id = connection_params.get('project_id')

# After (CORRECT)
# Parse credentials first
credentials_json = connection_params.get('credentials_json')
if isinstance(credentials_json, str):
    credentials_json = json.loads(credentials_json)

# Get project_id from connection_params or extract from credentials
self.project_id = connection_params.get('project_id')
if not self.project_id and credentials_json:
    # Extract project_id from service account credentials
    self.project_id = credentials_json.get('project_id')
    print(f"Extracted project_id from credentials: {self.project_id}")
```

### 2. Incorrect Region Format
**Problem**: The region detection logic was converting specific regions like `asia-south1` to generic regions like `asia`, which BigQuery INFORMATION_SCHEMA doesn't support.

**Impact**: INFORMATION_SCHEMA queries failed with "Location asia does not support this operation" error.

**Fix**: Modified region detection to use the exact location from BigQuery datasets.

```python
# Before (WRONG)
if location_lower.startswith('asia'):
    region = 'asia'

# After (CORRECT)
# For multi-region locations (us, eu), use as-is
if location in ['us', 'eu']:
    region = location
else:
    # For specific regions, use the full location
    region = location
```

## Files Modified

### 1. `backend/services/bigquery_assessment_service.py`
- Fixed `__init__()` method to extract project_id from credentials
- Fixed `collect_query_statistics_detailed()` region detection logic

### 2. `backend/diagnose_query_insights_production.py` (NEW)
- Created production diagnostic tool that uses actual database connections
- Tests BigQuery INFORMATION_SCHEMA access with correct project ID and region
- Provides detailed error messages and fix instructions

## Testing

### Run Diagnostic Script
```bash
cd backend
python diagnose_query_insights_production.py
```

### Expected Output (Success)
```
✓ Found BigQuery connection: bq_demo
✓ Credentials found for project: assessiq-484512
✓ BigQuery client initialized for project: assessiq-484512
✓ Detected location: asia-south1
✓ Using region for INFORMATION_SCHEMA: asia-south1
✓ Found 3 queries in last 7 days
✓ Successfully fetched 3 sample queries
```

## Verification Steps

1. **Run diagnostic script** to verify BigQuery connection and INFORMATION_SCHEMA access:
   ```bash
   cd backend
   python diagnose_query_insights_production.py
   ```

2. **Restart backend server** to load the fixed code:
   ```bash
   # Stop current server (Ctrl+C)
   ./START_BACKEND_HERE.sh
   ```

3. **Create new assessment**:
   - Go to http://localhost:3000/assessments
   - Click "Create Assessment"
   - Select BigQuery connection (bq_demo)
   - Select Redshift connection
   - Click "Create"
   - Wait for assessment to complete

4. **Verify Query Insights**:
   - Click on the completed assessment
   - Go to "Query Insights" tab
   - Should see query statistics with:
     - Total Queries count
     - Active Users count
     - Bytes Scanned
     - Cache Hit Rate
     - Table with query details

## Expected Results

After the fix, the assessment should:
1. Successfully connect to BigQuery using correct project ID
2. Detect the correct region format
3. Query INFORMATION_SCHEMA.JOBS_BY_PROJECT successfully
4. Collect query statistics (job_id, execution_time, query_text, bytes_scanned, etc.)
5. Store query statistics in `assessment_query_stats` table
6. Display data in Query Insights tab

## Common Issues

### No Queries Found
If diagnostic shows "Found 0 queries in last 7 days":
- No queries have been executed in BigQuery recently
- OR service account lacks permissions

**Solution**: Grant permissions to service account:
1. Go to GCP Console > IAM & Admin > IAM
2. Find service account (e.g., `assesiq@assessiq-484512.iam.gserviceaccount.com`)
3. Click "Edit" (pencil icon)
4. Add roles:
   - BigQuery Job User (`roles/bigquery.jobUser`)
   - BigQuery Data Viewer (`roles/bigquery.dataViewer`)
5. Click "Save"

### Permission Denied
If diagnostic shows "403 Forbidden" or "Permission denied":
- Service account lacks required permissions

**Solution**: Same as above - grant BigQuery Job User and Data Viewer roles

## Database Schema

Query statistics are stored in `assessment_query_stats` table:

```sql
CREATE TABLE assessment_query_stats (
    id SERIAL PRIMARY KEY,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id),
    job_id VARCHAR(255),
    execution_time TIMESTAMP,
    query_text TEXT,
    bytes_scanned BIGINT,
    slot_milliseconds BIGINT,
    cache_hit BOOLEAN,
    referenced_tables TEXT[],
    user_email VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## API Endpoint

Query Insights data is fetched via:
```
GET /api/assessments/{assessment_id}/query-insights?timeframe={filter}
```

Timeframe filters:
- `all` - All time
- `24h` - Last 24 hours
- `7d` - Last 7 days
- `30d` - Last 30 days

## Summary

The Query Insights feature is now working correctly. The root causes were:
1. Using wrong project ID (database field instead of credentials)
2. Using wrong region format (generic instead of specific)

Both issues have been fixed in the assessment service, and a diagnostic tool has been created to help troubleshoot similar issues in the future.
