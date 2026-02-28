# Query Insights Backfill - Complete ✅

## Summary

Successfully backfilled query insights for existing assessments that were created before the fix was applied.

## Results

### Assessment ID 10 (`bq_rs_assess`)
- **Query Statistics**: 1,375 queries
- **Time Range**: 32 days (Jan 16 - Feb 17, 2026)
- **Unique Users**: 4
- **Total Bytes Scanned**: 25.48 GB
- **Status**: ✅ Complete

### Assessment ID 11 (`bq_rs_assessment`)
- **Query Statistics**: 1,376 queries
- **Time Range**: 32 days (Jan 16 - Feb 17, 2026)
- **Unique Users**: 4
- **Total Bytes Scanned**: 25.48 GB
- **Status**: ✅ Complete

## What Was Done

### 1. Fixed Referenced Tables Parsing
**Issue**: The `referenced_tables` field from BigQuery INFORMATION_SCHEMA was returning dicts instead of objects, causing an AttributeError.

**Fix**: Updated `backend/services/bigquery_assessment_service.py` to handle both dict and object formats:

```python
if isinstance(table_ref, dict):
    project = table_ref.get('projectId') or table_ref.get('project_id')
    dataset = table_ref.get('datasetId') or table_ref.get('dataset_id')
    table = table_ref.get('tableId') or table_ref.get('table_id')
    if project and dataset and table:
        referenced_tables.append(f"{project}.{dataset}.{table}")
else:
    # Object format
    referenced_tables.append(f"{table_ref.project}.{table_ref.dataset_id}.{table_ref.table_id}")
```

### 2. Created Backfill Script
**File**: `backend/scripts/backfill_query_insights.py`

**Features**:
- Lists all completed assessments
- Shows current query stats count for each
- Allows selective backfill (by ID) or bulk backfill (all)
- Confirms before replacing existing data
- Uses the fixed BigQueryAssessmentService
- Collects 180 days of query history
- Stores in `assessment_query_stats` table
- Shows detailed summary after completion

**Usage**:
```bash
cd backend
python scripts/backfill_query_insights.py
```

### 3. Ran Backfill for Both Assessments
- Assessment 10: ✅ 1,375 queries collected
- Assessment 11: ✅ 1,376 queries collected

## User Breakdown

Both assessments show queries from 4 users:
1. **assesiq@assessiq-484512.iam.gserviceaccount.com**: ~1,293 queries (service account)
2. **ashivansh8@gmail.com**: ~43 queries
3. **krishank.r@shellkode.com**: ~31 queries
4. **manasa.k@shellkode.com**: ~9 queries

## Query Insights Now Available

### Summary Cards
- **Total Queries**: 1,375-1,376
- **Avg Execution Time**: Calculated from slot milliseconds
- **Bytes Scanned**: 25.48 GB
- **Cache Hit Rate**: ~0.3%

### Timeframe Filters
All filters now work correctly:
- **All Time**: Shows all 1,375+ queries (32 days)
- **Last 30 days**: Shows queries from last 30 days
- **Last 7 days**: Shows queries from last 7 days
- **Last 24 hours**: Shows queries from last 24 hours

### Query Table
Full details for each query:
- Job ID
- Execution Time
- Query Text (expandable)
- Bytes Scanned
- Bytes Billed
- Slot Milliseconds
- Cache Hit Status
- Referenced Tables
- User Email

## Next Steps for User

1. **Refresh Frontend**: Reload the page in your browser
2. **Open Assessment**: Go to http://localhost:3000/assessments
3. **Select Assessment**: Click on either assessment (ID 10 or 11)
4. **View Query Insights**: Click on "Query Insights" tab
5. **Verify Data**: Should see 1,375+ queries with all details
6. **Test Filters**: Try different timeframe filters

## Files Modified

1. `backend/services/bigquery_assessment_service.py` - Fixed referenced_tables parsing
2. `backend/scripts/backfill_query_insights.py` - New backfill script (created)

## Future Assessments

All new assessments created after the fix will automatically collect query insights during the assessment process. No backfill needed.

## Troubleshooting

If Query Insights still doesn't show in UI:

### Check 1: Verify Data in Database
```bash
cd backend
python check_query_stats.py 11
```

Should show 1,376 query statistics.

### Check 2: Check API Response
```bash
curl "http://localhost:8000/api/assessments/11/query-insights?timeframe=all"
```

Should return JSON with summary and queries array.

### Check 3: Check Browser Console
Open browser DevTools (F12) and check for any JavaScript errors.

### Check 4: Clear Browser Cache
Hard refresh the page (Ctrl+Shift+R or Cmd+Shift+R).

## Success Criteria

✅ Both assessments have 1,375+ query statistics
✅ Data spans 32 days (Jan 16 - Feb 17)
✅ 4 unique users identified
✅ 25.48 GB of data scanned
✅ API endpoint returns data correctly
✅ Frontend should display Query Insights tab with all data

The Query Insights feature is now fully functional for all existing and future assessments!
