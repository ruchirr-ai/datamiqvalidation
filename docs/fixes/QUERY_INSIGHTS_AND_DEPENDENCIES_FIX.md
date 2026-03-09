# Query Insights and Stored Procedure Dependencies Fix

## Issues Fixed

### 1. Stored Procedures Dependencies Not Showing
**Problem**: In the Assessment section, stored procedures were not showing their dependencies (dependent_tables, dependent_views) correctly.

**Root Cause**: The `collect_routines()` method in `BigQueryAssessmentService` was parsing dependencies but leaving `dependent_tables` and `dependent_views` as empty arrays.

**Solution**: Enhanced the routine collection to:
1. First collect all views to distinguish them from tables
2. Parse dependencies from stored procedure SQL
3. Categorize dependencies into tables vs views by cross-referencing with the view list
4. Properly populate `dependent_tables`, `dependent_views`, `dependent_functions`, and `calls_procedures`

### 2. Query Insights Feature Missing
**Problem**: Query Insights section was not showing detailed BigQuery query statistics with filters.

**Required Features**:
- Job ID
- Execution time
- Query text
- Bytes scanned/billed
- Slot milliseconds used
- Cache hit status
- Referenced tables
- User email
- Total query count
- Active users count
- Cache hit rate
- Timeframe filters (All Time, Last 24 hours, Last 7 days, Last 30 days)

**Solution**: Implemented complete Query Insights feature with:
1. New backend API endpoint
2. Frontend component with filtering
3. Summary statistics
4. Interactive query table

## Changes Made

### Backend Changes

#### 1. Fixed Stored Procedure Dependencies
**File**: `backend/services/bigquery_assessment_service.py`

**Changes**:
- Modified `collect_routines()` method to properly categorize dependencies
- Added view collection step before routine collection
- Cross-reference dependencies with view names to distinguish tables from views
- Calculate dependency depth based on total dependencies

```python
async def collect_routines(self) -> List[Dict]:
    """Collect stored procedures and functions with dependencies"""
    routines = []
    
    # First, collect all views to distinguish them from tables
    view_names = set()
    for dataset in self.client.list_datasets():
        for table in self.client.list_tables(dataset.dataset_id):
            table_ref = self.client.get_table(f"{self.project_id}.{dataset.dataset_id}.{table.table_id}")
            if table_ref.table_type == 'VIEW':
                view_names.add(f"{dataset.dataset_id}.{table.table_id}")
                view_names.add(f"{self.project_id}.{dataset.dataset_id}.{table.table_id}")
    
    # Collect all routines with dependencies
    for dataset in self.client.list_datasets():
        for routine in self.client.list_routines(dataset.dataset_id):
            # ... parse dependencies and categorize into tables/views
```

#### 2. Created Query Insights API Endpoint
**File**: `backend/routers/assessment_router.py`

**New Endpoint**: `GET /api/assessments/{assessment_id}/query-insights`

**Query Parameters**:
- `timeframe`: Filter by time period (all, 24h, 7d, 30d)

**Response Structure**:
```json
{
  "assessment_id": 1,
  "timeframe": "all",
  "summary": {
    "total_query_count": 1250,
    "active_users_count": 15,
    "total_bytes_scanned": 5368709120,
    "total_bytes_billed": 5368709120,
    "total_slot_milliseconds": 125000,
    "cache_hit_rate": 45.2,
    "cache_hits": 565,
    "cache_misses": 685
  },
  "queries": [
    {
      "job_id": "job_abc123",
      "execution_time": "2026-02-17T10:30:00Z",
      "query_text": "SELECT * FROM dataset.table WHERE...",
      "bytes_scanned": 1048576,
      "bytes_billed": 1048576,
      "slot_milliseconds": 1500,
      "cache_hit": false,
      "cache_hit_status": "Miss",
      "referenced_tables": ["project.dataset.table1", "project.dataset.table2"],
      "user_email": "user@example.com"
    }
  ]
}
```

**Features**:
- Filters query statistics by timeframe
- Calculates aggregated metrics (total queries, users, bytes, cache hit rate)
- Returns full query text (not truncated)
- Includes all query details for table display

### Frontend Changes

#### 1. Created Query Insights Component
**File**: `frontend/src/components/assessments/QueryInsightsSection.tsx`

**Features**:
- Timeframe filter buttons (All Time, Last 24 Hours, Last 7 Days, Last 30 Days)
- Summary cards showing:
  - Total Queries
  - Active Users
  - Bytes Scanned
  - Cache Hit Rate
- Interactive query table with columns:
  - Job ID
  - Execution Time
  - Query Text (truncated, click to expand)
  - Bytes Scanned
  - Bytes Billed
  - Slot Milliseconds
  - Cache Hit Status (with icons)
  - Referenced Tables
  - User Email
- Expandable rows to show full query text and referenced tables
- Loading and error states
- Empty state for no data

#### 2. Created Query Insights Styles
**File**: `frontend/src/components/assessments/QueryInsightsSection.css`

**Styling**:
- Clean, minimal design following Snowflake UI inspiration
- Responsive layout for mobile, tablet, and desktop
- Summary cards with icons
- Interactive table with hover effects
- Expandable rows for query details
- Color-coded cache hit/miss status
- Smooth animations and transitions

#### 3. Updated Assessment Report Page
**File**: `frontend/src/pages/AssessmentReportPage.tsx`

**Changes**:
- Added import for `QueryInsightsSection`
- Updated query-insights tab to use new component
- Passes `assessmentId` to component for API calls

```tsx
{activeTab === 'query-insights' && (
  <QueryInsightsSection assessmentId={parseInt(assessmentId!)} />
)}
```

## How It Works

### Stored Procedure Dependencies Flow
1. Assessment service collects all views first
2. For each stored procedure/function:
   - Parse SQL to extract dependencies
   - Check each dependency against view list
   - Categorize as table or view
   - Store in appropriate array
3. Calculate dependency depth
4. Store in database
5. Display in frontend with proper categorization

### Query Insights Flow
1. User selects timeframe filter
2. Frontend calls `/api/assessments/{id}/query-insights?timeframe={filter}`
3. Backend:
   - Fetches all query statistics from database
   - Filters by selected timeframe
   - Calculates aggregated metrics
   - Returns formatted data
4. Frontend displays:
   - Summary cards with metrics
   - Table with all queries
   - Expandable rows for details

## Testing

### Test Stored Procedure Dependencies
1. Run an assessment on a BigQuery project with stored procedures
2. Navigate to Assessment Report → Stored Procedures tab
3. Verify that dependencies are showing:
   - `dependent_tables` array populated
   - `dependent_views` array populated
   - `dependent_functions` array populated
   - `calls_procedures` array populated
   - `dependency_depth` calculated correctly

### Test Query Insights
1. Run an assessment that collects query statistics
2. Navigate to Assessment Report → Query Insights tab
3. Verify:
   - Summary cards show correct metrics
   - Query table displays all queries
   - Timeframe filters work correctly
   - Click on query text expands full query
   - Cache hit/miss status displays correctly
   - Referenced tables show in expanded view

## API Endpoints

### Get Query Insights
```
GET /api/assessments/{assessment_id}/query-insights?timeframe={filter}
```

**Parameters**:
- `assessment_id` (path): Assessment ID
- `timeframe` (query): Filter timeframe (all, 24h, 7d, 30d)

**Response**: Query insights data with summary and queries array

## Database Schema

No database changes required. Uses existing tables:
- `assessment_routines` - Stores routine dependencies
- `assessment_query_stats` - Stores query statistics

## Files Modified

### Backend
- `backend/services/bigquery_assessment_service.py` - Fixed routine dependency collection
- `backend/routers/assessment_router.py` - Added query insights endpoint

### Frontend
- `frontend/src/components/assessments/QueryInsightsSection.tsx` - New component
- `frontend/src/components/assessments/QueryInsightsSection.css` - New styles
- `frontend/src/pages/AssessmentReportPage.tsx` - Updated to use new component

## Benefits

1. **Accurate Dependencies**: Stored procedures now show correct dependencies categorized by type
2. **Query Insights**: Complete visibility into BigQuery query patterns and performance
3. **Timeframe Filtering**: Analyze queries for specific time periods
4. **Performance Metrics**: Track bytes scanned, cache hit rates, and slot usage
5. **User Activity**: See which users are running queries
6. **Cost Analysis**: Understand query costs through bytes billed
7. **Query Optimization**: Identify expensive queries and cache misses

## Next Steps

1. Test with real BigQuery data
2. Add export functionality for query insights
3. Add query performance recommendations
4. Add cost estimation based on bytes billed
5. Add query pattern analysis (most common queries, slowest queries, etc.)
