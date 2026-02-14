# Assessments Module

## Overview
The Assessments module provides comprehensive BigQuery metadata collection and analysis for migration planning.

## Features
- ✅ Dataset and table metadata collection
- ✅ Column-level analysis with data types
- ✅ Views and materialized views
- ✅ Stored procedures and functions
- ✅ ML models detection
- ✅ Query statistics (180-day history)
- ✅ User insights and query patterns
- ✅ Security policies (RLS/CLS)
- ✅ Dependency analysis
- ✅ Sharded table detection

## Key Components

### Backend
- **Service**: `backend/services/bigquery_assessment_service.py`
- **Router**: `backend/routers/assessment_router.py`
- **Repository**: `backend/repositories/assessment_repository.py`
- **Models**: `backend/models/assessment.py`

### Frontend
- **Page**: `frontend/src/pages/AssessmentReportPage.tsx`
- **Components**: `frontend/src/components/assessments/`
- **API**: `frontend/src/services/assessmentsApi.ts`

## Usage

### Creating an Assessment
1. Navigate to Assessments page
2. Click "Create Assessment"
3. Select BigQuery source connection
4. Select Redshift target connection
5. Assessment runs in background

### Viewing Results
Assessment report includes tabs for:
- **Summary**: Overview with metrics
- **Datasets**: Dataset information
- **Tables**: Table metadata with columns
- **Views**: View definitions and dependencies
- **Stored Procedures**: Procedure code and dependencies
- **Functions**: Function definitions
- **ML & Spark Models**: ML model inventory
- **Query Insights**: Query patterns and performance
- **User Insights**: User activity analysis
- **Security**: RLS and CLS policies

## Important Notes

### Region Detection
The service automatically detects the BigQuery region from dataset location. This is critical for query statistics collection.

### Assessment Data
- Assessment data is **static** (captured at runtime)
- To see updated data, run a new assessment
- Query statistics collect 180 days of history

### Permissions Required
Service account needs:
- `bigquery.datasets.get`
- `bigquery.tables.get`
- `bigquery.tables.list`
- `bigquery.routines.get`
- `bigquery.routines.list`
- `bigquery.jobs.list` (for query statistics)

## Troubleshooting

### No Query Statistics
If Query Insights or User Insights are empty:
1. Check backend logs for region detection
2. Verify service account has `bigquery.jobs.list` permission
3. Ensure queries exist in the last 180 days
4. Run a new assessment after fixes

### Missing Users
If not all users appear:
1. Verify correct BigQuery region is detected
2. Check that assessment was run with latest code
3. Run new assessment to capture fresh data

## API Endpoints

- `POST /api/assessments/` - Create assessment
- `GET /api/assessments/` - List assessments
- `GET /api/assessments/{id}` - Get assessment details
- `GET /api/assessments/{id}/report` - Get full report
- `GET /api/assessments/{id}/logs` - Get execution logs
- `PUT /api/assessments/{id}` - Update assessment
- `DELETE /api/assessments/{id}` - Delete assessment
- `POST /api/assessments/{id}/run` - Re-run assessment
