# Query Insights Fixes Complete

## Changes Made

### 1. ✅ Removed "Query ID" Column from Recent Queries Table

**File**: `frontend/src/pages/AssessmentReportPage.tsx`

**Changes**:
- Removed `<th>Query ID</th>` from table header
- Removed `<td className="query-id-cell">` with job_id display from table body
- Removed "Query End Time" column (was using incorrect field names)

**New Table Structure**:
- Query User
- Execution Time
- Data Scanned
- Cache Status
- Query Slots Utilised
- Query Start Time

**Fixed Data Mapping**:
- Changed `query.creation_time` to `query.execution_time` for start time
- Changed `formatDuration(query.execution_time)` to `formatDuration(query.slot_milliseconds)` for execution time display
- Removed end_time column (not available in data)

### 2. ✅ Added Debug Logging to Investigate Data Limitation

**File**: `frontend/src/pages/AssessmentReportPage.tsx`

**Added Debug Logging**:
```typescript
React.useEffect(() => {
  console.log('[Query Insights Debug]');
  console.log('Total queryStats received:', queryStats?.length || 0);
  console.log('After time filter:', filteredQueries.length);
  console.log('Time filter:', timeFilter);
  console.log('Unique users:', new Set(queryStats?.map((q: any) => q.user_email)).size);
  console.log('Sample query data:', queryStats?.[0]);
  if (filteredQueries.length > 0) {
    console.log('Filtered sample:', filteredQueries[0]);
  }
}, [queryStats, timeFilter, filteredQueries.length]);
```

This will help diagnose:
- How many queries are being received from the backend
- How many queries remain after time filtering
- How many unique users exist in the data
- Sample query structure

## Understanding the Data Limitation Issue

### Why You're Seeing Only One Query/User

Based on the previous context, your current assessment (ID: 7 or 8) was captured with OLD data. The issue is:

1. **Assessment Data is Static**: When an assessment runs, it captures a snapshot of BigQuery at that moment
2. **Old Assessment**: Your assessment was run with code that only collected 7 days of query history
3. **Limited Capture**: If only 1 user ran queries in that 7-day window, only 1 user is captured

### The Solution: Run a NEW Assessment

As explained in the previous documentation:

1. **Go to Assessments Page**: http://localhost:3000/assessments
2. **Create New Assessment**: Click "Create Assessment"
3. **Fill Details**:
   - Name: "BigQuery Full Assessment - 180 Days"
   - Source: Your BigQuery connection
   - Target: Your Redshift connection
4. **Run Assessment**: Wait for completion
5. **View New Report**: The new assessment will have:
   - 180 days of query history
   - All users (assessiq, demo, service accounts, etc.)
   - Up to 50,000 queries

### Backend Already Fixed ✅

The backend code has already been updated to:
- Collect 180 days of query history (not 7 days)
- Collect up to 50,000 queries (not 10,000)
- Return ALL query stats without limit

**File**: `backend/services/bigquery_assessment_service.py` (lines 448-500)

```python
async def collect_query_statistics_detailed(self) -> List[Dict]:
    """
    Collect detailed query statistics from INFORMATION_SCHEMA.JOBS
    Collects up to 180 days of query history
    """
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
    FROM `{self.project_id}.region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
    WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 180 DAY)
        AND job_type = 'QUERY'
        AND state = 'DONE'
    ORDER BY creation_time DESC
    LIMIT 50000
    """
```

## Verification Steps

### 1. Check Debug Console

After the changes, open browser console (F12) and navigate to Query Insights tab. You should see:

```
[Query Insights Debug]
Total queryStats received: 1
After time filter: 0 or 1
Time filter: all
Unique users: 1
Sample query data: { job_id: "...", user_email: "manasa.k@shellkode.com", ... }
```

This confirms the data limitation is in the captured assessment data, not the frontend code.

### 2. Run New Assessment

After running a new assessment, you should see:

```
[Query Insights Debug]
Total queryStats received: 5000+ (or whatever was captured)
After time filter: varies by filter
Time filter: all
Unique users: 5+ (assessiq, demo, service accounts, etc.)
Sample query data: { job_id: "...", user_email: "...", ... }
```

### 3. Verify Table Display

The Recent Queries table should now show:
- ✅ No "Query ID" column
- ✅ No "Query End Time" column
- ✅ Proper execution time display (using slot_milliseconds)
- ✅ Proper start time display (using execution_time)
- ✅ All queries from the assessment (up to 50 displayed)

## Summary

### What Was Fixed ✅
- ✅ Removed "Query ID" column from Recent Queries table
- ✅ Removed "Query End Time" column (incorrect data mapping)
- ✅ Fixed execution time display to use slot_milliseconds
- ✅ Fixed start time display to use execution_time
- ✅ Added debug logging to diagnose data issues

### What You Need to Do 🎯
- 🎯 Run a NEW assessment to capture fresh data with 180-day history
- 🎯 Check browser console for debug output
- 🎯 Verify the new assessment shows multiple users and queries

### Root Cause of Limited Data 📊
- Assessment data is STATIC (captured at runtime)
- Old assessment has OLD data (7 days, limited queries)
- New assessment will have NEW data (180 days, up to 50,000 queries)
- Code fixes only apply to NEW assessments

## Files Modified

1. **Frontend Query Insights Table**
   - `frontend/src/pages/AssessmentReportPage.tsx`
   - Removed Query ID column
   - Removed Query End Time column
   - Fixed data field mappings
   - Added debug logging

2. **Backend Query Collection** (Already Fixed Previously)
   - `backend/services/bigquery_assessment_service.py`
   - Collects 180 days of history
   - Collects up to 50,000 queries

3. **Backend API Response** (Already Fixed Previously)
   - `backend/routers/assessment_router.py`
   - Returns ALL query stats without limit

## Next Steps

1. **Check Console**: Open browser console and view debug output
2. **Run New Assessment**: Create and run a new assessment
3. **Verify Results**: Check that new assessment shows multiple users and queries
4. **Remove Debug Logging**: Once verified, the debug logging can be removed if desired

The Query Insights table is now cleaner and the debug logging will help confirm the data limitation issue! 🚀
