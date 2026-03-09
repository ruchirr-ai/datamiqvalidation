# Query Insights Charts Implementation

## Overview
Added two interactive charts to the Query Insights section to provide better visualization of query patterns and distribution.

## Changes Made

### Backend Changes (`backend/routers/assessment_router.py`)

#### 1. Read vs Write Query Classification
- Added regex-based query classification to identify READ and WRITE operations
- Write operations: INSERT, UPDATE, DELETE, MERGE, CREATE, DROP, ALTER, TRUNCATE
- Read operations: SELECT and all other queries
- Added to summary response:
  - `read_queries`: Count of read operations
  - `write_queries`: Count of write operations

#### 2. Concurrent Queries Over Time
- Implemented time-based grouping of queries:
  - **Hourly**: Groups queries by hour (format: `YYYY-MM-DD HH:00`)
  - **Daily**: Groups queries by day (format: `YYYY-MM-DD`)
  - **Weekly**: Groups queries by ISO week (format: `YYYY-WXX`)
- Returns structured data for each interval with time and query count

#### 3. New API Response Structure
```json
{
  "summary": {
    "read_queries": 1200,
    "write_queries": 175,
    ...
  },
  "charts": {
    "read_write_distribution": {
      "read": 1200,
      "write": 175
    },
    "concurrent_queries": {
      "hourly": [{"time": "2026-02-17 10:00", "count": 45}, ...],
      "daily": [{"time": "2026-02-17", "count": 523}, ...],
      "weekly": [{"time": "2026-W07", "count": 1375}, ...]
    }
  },
  "queries": [...]
}
```

### Frontend Changes

#### 1. Pie Chart - Query Type Distribution (`QueryInsightsSection.tsx`)
- **Purpose**: Shows segregation of READ vs WRITE queries
- **Implementation**: SVG-based pie chart with two segments
- **Features**:
  - Blue segment (#0070E0) for READ queries
  - Gold segment (#FFD140) for WRITE queries
  - Legend showing counts and percentages
  - Responsive design
- **Location**: Left side of charts section

#### 2. Line Chart - Concurrent Queries Over Time (`QueryInsightsSection.tsx`)
- **Purpose**: Visualizes query volume over time
- **Implementation**: SVG-based line chart with area fill
- **Features**:
  - Dynamic interval switching (Hourly, Daily, Weekly)
  - Grid lines for better readability
  - Gradient area fill under the line
  - Interactive data points with tooltips
  - Responsive X-axis labels
  - Auto-scaling Y-axis based on max value
- **Location**: Right side of charts section (2x width of pie chart)

#### 3. Component Updates
- Added new TypeScript interfaces:
  - `ConcurrentQueryData`: Time-series data point
  - `QueryInsightsCharts`: Chart data structure
- Added state management:
  - `concurrentInterval`: Controls hourly/daily/weekly view
- Added rendering functions:
  - `renderPieChart()`: Renders pie chart
  - `renderLineChart()`: Renders line chart with interval controls

#### 4. CSS Styling (`QueryInsightsSection.css`)
- **Charts Section**: 2-column grid layout (1fr for pie, 2fr for line)
- **Chart Cards**: White background, border, rounded corners, padding
- **Pie Chart**: 200x200px SVG with centered legend
- **Line Chart**: Full-width responsive SVG with controls
- **Interval Buttons**: Styled filter buttons matching timeframe filters
- **Responsive Design**:
  - Desktop (>1200px): Side-by-side charts
  - Tablet (768-1200px): Stacked charts
  - Mobile (<768px): Stacked charts with full-width controls

## Visual Design

### Color Scheme
- **Read Queries**: Blue (#0070E0) - matches primary brand color
- **Write Queries**: Gold (#FFD140) - matches accent color
- **Line Chart**: Blue (#0070E0) with gradient fill
- **Grid Lines**: Light grey (#e0e0e0)

### Layout
```
┌─────────────────────────────────────────────────────────┐
│  Summary Cards (4 cards in grid)                        │
├─────────────────────┬───────────────────────────────────┤
│  Pie Chart          │  Line Chart                       │
│  (Query Types)      │  (Concurrent Queries)             │
│                     │  [Hourly] [Daily] [Weekly]        │
│  ● Read: 1200 (87%) │                                   │
│  ● Write: 175 (13%) │  [Line graph with area fill]      │
└─────────────────────┴───────────────────────────────────┘
│  Query Table                                            │
└─────────────────────────────────────────────────────────┘
```

## Features

### Pie Chart
- ✅ Visual representation of query type distribution
- ✅ Percentage and count display
- ✅ Color-coded legend
- ✅ Responsive sizing

### Line Chart
- ✅ Time-series visualization of query volume
- ✅ Three interval options (hourly, daily, weekly)
- ✅ Interactive data points with tooltips
- ✅ Grid lines for reference
- ✅ Gradient area fill
- ✅ Auto-scaling axes
- ✅ Smart label positioning (shows subset to avoid crowding)

### Integration
- ✅ Works with existing timeframe filters (All Time, 24h, 7d, 30d)
- ✅ Charts update when timeframe changes
- ✅ Data fetched from backend API
- ✅ Responsive design for all screen sizes

## Technical Details

### Query Classification Logic
```python
# Backend classification
if re.match(r'^\s*(INSERT|UPDATE|DELETE|MERGE|CREATE|DROP|ALTER|TRUNCATE)', query_upper):
    write_count += 1
else:
    read_count += 1
```

### Time Grouping Logic
```python
# Hourly: YYYY-MM-DD HH:00
hour_key = q.execution_time.strftime('%Y-%m-%d %H:00')

# Daily: YYYY-MM-DD
day_key = q.execution_time.strftime('%Y-%m-%d')

# Weekly: YYYY-WXX
week_key = q.execution_time.strftime('%Y-W%W')
```

### SVG Chart Rendering
- **Pie Chart**: Uses SVG circles with stroke-dasharray for segments
- **Line Chart**: Uses SVG path elements for line and area
- **Scaling**: Automatic based on data range
- **Tooltips**: Native SVG title elements

## Testing

### Test Scenarios
1. ✅ Empty data (no queries) - charts should not render
2. ✅ Single query type (all read or all write) - pie chart shows 100%
3. ✅ Mixed query types - pie chart shows correct distribution
4. ✅ Timeframe filtering - charts update correctly
5. ✅ Interval switching - line chart updates smoothly
6. ✅ Responsive behavior - charts stack on mobile

### Sample Data
- Assessment ID 10: 1,375 queries over 32 days
- Assessment ID 11: 1,376 queries over 32 days
- Mix of read and write operations
- Multiple users and time periods

## Performance Considerations

### Backend
- Query classification done in-memory (no additional DB queries)
- Time grouping uses Python datetime formatting (efficient)
- Data sorted once before returning

### Frontend
- SVG rendering (lightweight, no external libraries)
- Charts only render when data is available
- Responsive design uses CSS grid (no JavaScript calculations)
- State updates trigger re-renders only for affected components

## Future Enhancements

### Potential Improvements
1. Add zoom/pan functionality to line chart
2. Add export chart as image functionality
3. Add more query type classifications (DDL, DML, DQL)
4. Add query complexity metrics to charts
5. Add user-specific filtering for charts
6. Add comparison view (compare two time periods)
7. Add anomaly detection highlighting

### Additional Charts
1. Query execution time distribution (histogram)
2. Top users by query count (bar chart)
3. Cache hit rate over time (line chart)
4. Bytes scanned over time (area chart)
5. Query types by user (stacked bar chart)

## Files Modified

### Backend
- `backend/routers/assessment_router.py` - Added chart data generation

### Frontend
- `frontend/src/components/assessments/QueryInsightsSection.tsx` - Added chart components
- `frontend/src/components/assessments/QueryInsightsSection.css` - Added chart styles

## Documentation
- This file: `QUERY_INSIGHTS_CHARTS_IMPLEMENTATION.md`

## Deployment Notes

### Backend
- No new dependencies required
- Uses standard Python `re` module for regex
- Uses standard `datetime` module for time formatting

### Frontend
- No new dependencies required
- Uses native SVG rendering
- Uses existing React hooks and state management

### Testing
```bash
# Backend - restart server to apply changes
cd backend
source .venv/bin/activate
uvicorn main:app --reload

# Frontend - no restart needed (hot reload)
cd frontend
npm start
```

## Conclusion

Successfully implemented two interactive charts in the Query Insights section:
1. **Pie Chart**: Shows read vs write query distribution with percentages
2. **Line Chart**: Shows concurrent queries over time with hourly/daily/weekly intervals

Both charts are fully responsive, integrate seamlessly with existing filters, and provide valuable insights into query patterns without requiring any external charting libraries.
