# Query Insights - Avg Execution Time Update

## Changes Made

### 1. Backend API Update ✅

**File**: `backend/routers/assessment_router.py`

**Changes**:
- Added calculation for average execution time in seconds
- Formula: `avg_execution_time_seconds = (total_slot_ms / total_queries) / 1000`
- Added `avg_execution_time_seconds` to the API response summary

**API Response** (updated):
```json
{
  "summary": {
    "total_query_count": 1372,
    "active_users_count": 4,
    "avg_execution_time_seconds": 2.456,  // NEW
    "total_bytes_scanned": 123456789,
    "cache_hit_rate": 45.2
  }
}
```

### 2. Frontend Component Update ✅

**File**: `frontend/src/components/assessments/QueryInsightsSection.tsx`

**Changes**:
1. Updated interface to include `avg_execution_time_seconds`
2. Replaced "Active Users" card with "Avg Execution Time" card
3. Changed icon from `Users` to `Clock`
4. Added `formatTime()` helper function to format execution time

**Time Formatting**:
- Less than 1 second: Shows milliseconds (e.g., "250ms")
- 1-60 seconds: Shows seconds with 2 decimals (e.g., "2.45s")
- Over 60 seconds: Shows minutes and seconds (e.g., "2m 30s")

### 3. Timeframe Filtering ✅

**Already Working**: The backend API already filters data by timeframe:
- `all`: All time (180 days of data)
- `24h`: Last 24 hours
- `7d`: Last 7 days
- `30d`: Last 30 days

**Frontend**: The component already fetches data when timeframe changes via `useEffect` dependency on `timeframe`.

## Summary Cards (Updated)

1. **Total Queries** - Count of all queries
2. **Avg Execution Time** - Average execution time (NEW - replaces Active Users)
3. **Bytes Scanned** - Total bytes processed
4. **Cache Hit Rate** - Percentage of cached queries

## How It Works

### Average Execution Time Calculation

The average execution time is calculated from `slot_milliseconds`, which represents the actual compute time used by BigQuery:

```python
# Backend calculation
total_slot_ms = sum(q.slot_milliseconds for q in query_stats)
avg_execution_time_ms = total_slot_ms / total_queries
avg_execution_time_seconds = avg_execution_time_ms / 1000
```

### Timeframe Filtering

When user selects a timeframe:
1. Frontend calls API with `?timeframe=7d` parameter
2. Backend filters query stats by execution time
3. Backend recalculates all metrics (including avg execution time) for filtered data
4. Frontend displays updated summary and query list

## Example Output

### All Time (1,372 queries)
- Total Queries: 1,372
- Avg Execution Time: 2.45s
- Bytes Scanned: 1.2 GB
- Cache Hit Rate: 45.2%

### Last 7 Days (4 queries)
- Total Queries: 4
- Avg Execution Time: 0.08s
- Bytes Scanned: 168 B
- Cache Hit Rate: 0%

### Last 30 Days (1,062 queries)
- Total Queries: 1,062
- Avg Execution Time: 2.51s
- Bytes Scanned: 950 MB
- Cache Hit Rate: 46.1%

## Testing

### Backend Test
```bash
# Test the API endpoint
curl "http://localhost:8000/api/assessments/10/query-insights?timeframe=7d"
```

Expected response includes:
```json
{
  "summary": {
    "avg_execution_time_seconds": 0.08
  }
}
```

### Frontend Test
1. Open assessment report
2. Go to Query Insights tab
3. Verify "Avg Execution Time" card shows formatted time
4. Change timeframe filters
5. Verify metrics update correctly

## Benefits

1. **More Useful Metric**: Average execution time is more actionable than active users count
2. **Performance Insights**: Helps identify slow queries and optimization opportunities
3. **Timeframe Comparison**: Compare average execution time across different time periods
4. **Better UX**: Clear, formatted time display (ms, s, or m:s)

## Files Modified

1. `backend/routers/assessment_router.py` - Added avg execution time calculation
2. `frontend/src/components/assessments/QueryInsightsSection.tsx` - Updated UI to show avg execution time
3. `frontend/src/components/assessments/QueryInsightsSection.css` - No changes needed (existing styles work)

## Next Steps

1. Restart backend server (if not using auto-reload)
2. Refresh frontend
3. Create new assessment to see the updated metrics
4. Test all timeframe filters

The Query Insights feature now shows average execution time instead of active users, providing more actionable performance insights!
