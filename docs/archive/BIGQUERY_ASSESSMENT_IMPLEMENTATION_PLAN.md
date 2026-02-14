# BigQuery Assessment Module - Implementation Plan

## Overview
Create a comprehensive BigQuery assessment module that extracts detailed metadata and generates assessment reports for migration planning.

## Architecture

### Backend Components

#### 1. BigQuery Metadata Extractor Service
**File**: `backend/services/bigquery_assessment_service.py`

**Responsibilities**:
- Connect to BigQuery using service account credentials
- Extract metadata across 11 categories
- Generate comprehensive assessment reports
- Store results in PostgreSQL database

**Key Methods**:
- `extract_datasets()` - Get all datasets with metadata
- `extract_tables()` - Get table metadata including partitioning, clustering
- `extract_columns()` - Get column-level details including security tags
- `extract_views()` - Get views and materialized views
- `extract_routines()` - Get stored procedures and functions
- `extract_query_statistics()` - Get job history and usage patterns
- `extract_ml_models()` - Get ML model metadata
- `extract_spark_jobs()` - Detect Spark-based procedures
- `extract_security_info()` - Get RLS and CLS policies
- `detect_sharded_tables()` - Identify date-sharded tables
- `generate_assessment_report()` - Compile all metadata into report

#### 2. Assessment Database Models
**File**: `backend/models/assessment.py`

**Tables**:
- `assessments` - Main assessment records
- `assessment_datasets` - Dataset metadata
- `assessment_tables` - Table metadata
- `assessment_columns` - Column metadata
- `assessment_views` - View definitions
- `assessment_routines` - Stored procedures/functions
- `assessment_query_stats` - Query statistics
- `assessment_ml_models` - ML model metadata
- `assessment_security` - Security policies
- `assessment_sharded_tables` - Sharded table groups

#### 3. Assessment Repository
**File**: `backend/repositories/assessment_repository.py`

**Methods**:
- `create_assessment()` - Create new assessment
- `get_assessment()` - Retrieve assessment by ID
- `list_assessments()` - List all assessments
- `update_assessment_status()` - Update assessment progress
- `save_assessment_data()` - Save extracted metadata
- `get_assessment_report()` - Get formatted report

#### 4. Assessment Router
**File**: `backend/routers/assessment_router.py`

**Endpoints**:
- `POST /api/assessments/bigquery` - Start BigQuery assessment
- `GET /api/assessments/{assessment_id}` - Get assessment details
- `GET /api/assessments` - List all assessments
- `GET /api/assessments/{assessment_id}/report` - Get assessment report
- `GET /api/assessments/{assessment_id}/datasets` - Get dataset details
- `GET /api/assessments/{assessment_id}/tables` - Get table details
- `GET /api/assessments/{assessment_id}/security` - Get security info
- `DELETE /api/assessments/{assessment_id}` - Delete assessment

### Frontend Components

#### 1. Assessments Page Enhancement
**File**: `frontend/src/pages/assessments/AssessmentReportsPage.tsx`

**Features**:
- List all assessments with status
- Filter by connection, date, status
- Click to view detailed report
- Delete assessments
- Export reports to PDF/CSV

#### 2. Assessment Report Viewer
**File**: `frontend/src/components/assessments/AssessmentReportViewer.tsx`

**Sections**:
- Executive Summary
- Datasets Overview
- Tables Analysis
- Column Details
- Views & Routines
- Query Statistics
- ML Models
- Security Analysis
- Sharded Tables
- Recommendations

#### 3. Connections Page Integration
**File**: `frontend/src/pages/ConnectionsPage.tsx`

**Changes**:
- Add "Perform Assessment" option to BigQuery connection menu
- Show assessment status badge on connections
- Link to latest assessment report

#### 4. Assessment API Service
**File**: `frontend/src/services/assessmentApi.ts`

**Methods**:
- `startAssessment(connectionId)` - Start new assessment
- `getAssessment(assessmentId)` - Get assessment details
- `listAssessments()` - List all assessments
- `getAssessmentReport(assessmentId)` - Get formatted report
- `deleteAssessment(assessmentId)` - Delete assessment

## Database Schema

### assessments table
```sql
CREATE TABLE assessments (
    id SERIAL PRIMARY KEY,
    connection_id INTEGER NOT NULL REFERENCES connections(id),
    project_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    total_datasets INTEGER DEFAULT 0,
    total_tables INTEGER DEFAULT 0,
    total_views INTEGER DEFAULT 0,
    total_routines INTEGER DEFAULT 0,
    total_ml_models INTEGER DEFAULT 0,
    total_size_mb BIGINT DEFAULT 0,
    assessment_data JSONB,
    created_by VARCHAR(255),
    workspace_id INTEGER NOT NULL,
    CONSTRAINT fk_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
);

CREATE INDEX idx_assessments_connection ON assessments(connection_id);
CREATE INDEX idx_assessments_workspace ON assessments(workspace_id);
CREATE INDEX idx_assessments_status ON assessments(status);
```

### assessment_datasets table
```sql
CREATE TABLE assessment_datasets (
    id SERIAL PRIMARY KEY,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    dataset_name VARCHAR(255) NOT NULL,
    creation_time TIMESTAMP,
    location VARCHAR(100),
    table_count INTEGER DEFAULT 0,
    total_size_mb BIGINT DEFAULT 0,
    metadata JSONB
);

CREATE INDEX idx_assessment_datasets_assessment ON assessment_datasets(assessment_id);
```

### assessment_tables table
```sql
CREATE TABLE assessment_tables (
    id SERIAL PRIMARY KEY,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    project_id VARCHAR(255) NOT NULL,
    dataset_name VARCHAR(255) NOT NULL,
    table_name VARCHAR(255) NOT NULL,
    table_type VARCHAR(50),
    creation_time TIMESTAMP,
    row_count BIGINT,
    size_mb BIGINT,
    partitioning_columns TEXT[],
    clustering_columns TEXT[],
    has_column_security BOOLEAN DEFAULT FALSE,
    has_row_security BOOLEAN DEFAULT FALSE,
    is_sharded BOOLEAN DEFAULT FALSE,
    shard_group VARCHAR(255),
    update_frequency VARCHAR(50),
    metadata JSONB
);

CREATE INDEX idx_assessment_tables_assessment ON assessment_tables(assessment_id);
CREATE INDEX idx_assessment_tables_dataset ON assessment_tables(dataset_name);
CREATE INDEX idx_assessment_tables_sharded ON assessment_tables(is_sharded);
```

### assessment_columns table
```sql
CREATE TABLE assessment_columns (
    id SERIAL PRIMARY KEY,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    table_id INTEGER NOT NULL REFERENCES assessment_tables(id) ON DELETE CASCADE,
    column_name VARCHAR(255) NOT NULL,
    data_type VARCHAR(100) NOT NULL,
    is_nullable BOOLEAN DEFAULT TRUE,
    ordinal_position INTEGER,
    is_partitioning_column BOOLEAN DEFAULT FALSE,
    clustering_ordinal_position INTEGER,
    policy_tags TEXT[],
    max_length INTEGER,
    metadata JSONB
);

CREATE INDEX idx_assessment_columns_assessment ON assessment_columns(assessment_id);
CREATE INDEX idx_assessment_columns_table ON assessment_columns(table_id);
```

### assessment_views table
```sql
CREATE TABLE assessment_views (
    id SERIAL PRIMARY KEY,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    view_name VARCHAR(255) NOT NULL,
    view_type VARCHAR(50),
    view_definition TEXT,
    creation_time TIMESTAMP,
    dependencies TEXT[],
    metadata JSONB
);

CREATE INDEX idx_assessment_views_assessment ON assessment_views(assessment_id);
```

### assessment_routines table
```sql
CREATE TABLE assessment_routines (
    id SERIAL PRIMARY KEY,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    routine_name VARCHAR(255) NOT NULL,
    routine_type VARCHAR(50),
    return_type VARCHAR(100),
    definition TEXT,
    external_language VARCHAR(50),
    creation_time TIMESTAMP,
    call_frequency INTEGER DEFAULT 0,
    metadata JSONB
);

CREATE INDEX idx_assessment_routines_assessment ON assessment_routines(assessment_id);
```

### assessment_query_stats table
```sql
CREATE TABLE assessment_query_stats (
    id SERIAL PRIMARY KEY,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    job_id VARCHAR(255),
    execution_time TIMESTAMP,
    query_text TEXT,
    bytes_scanned BIGINT,
    slot_milliseconds BIGINT,
    cache_hit BOOLEAN,
    referenced_tables TEXT[],
    user_email VARCHAR(255),
    metadata JSONB
);

CREATE INDEX idx_assessment_query_stats_assessment ON assessment_query_stats(assessment_id);
```

### assessment_ml_models table
```sql
CREATE TABLE assessment_ml_models (
    id SERIAL PRIMARY KEY,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    model_name VARCHAR(255) NOT NULL,
    model_type VARCHAR(100),
    dataset_name VARCHAR(255),
    creation_time TIMESTAMP,
    last_modified_time TIMESTAMP,
    metadata JSONB
);

CREATE INDEX idx_assessment_ml_models_assessment ON assessment_ml_models(assessment_id);
```

### assessment_security table
```sql
CREATE TABLE assessment_security (
    id SERIAL PRIMARY KEY,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    security_type VARCHAR(50),
    table_name VARCHAR(255),
    policy_name VARCHAR(255),
    filter_predicate TEXT,
    grantees TEXT[],
    creation_time TIMESTAMP,
    metadata JSONB
);

CREATE INDEX idx_assessment_security_assessment ON assessment_security(assessment_id);
CREATE INDEX idx_assessment_security_type ON assessment_security(security_type);
```

### assessment_sharded_tables table
```sql
CREATE TABLE assessment_sharded_tables (
    id SERIAL PRIMARY KEY,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    shard_group VARCHAR(255) NOT NULL,
    table_prefix VARCHAR(255) NOT NULL,
    shard_count INTEGER DEFAULT 0,
    total_size_mb BIGINT DEFAULT 0,
    date_range_start DATE,
    date_range_end DATE,
    shard_tables TEXT[],
    metadata JSONB
);

CREATE INDEX idx_assessment_sharded_assessment ON assessment_sharded_tables(assessment_id);
```

## BigQuery Metadata Queries

### 1. Datasets Query
```sql
SELECT
  schema_name as dataset_name,
  creation_time,
  location,
  (SELECT COUNT(*) FROM `{project_id}.{dataset}.INFORMATION_SCHEMA.TABLES`) as table_count
FROM `{project_id}.INFORMATION_SCHEMA.SCHEMATA`
ORDER BY schema_name;
```

### 2. Tables Query
```sql
SELECT
  table_catalog as project_id,
  table_schema as dataset_name,
  table_name,
  table_type,
  creation_time,
  IFNULL(row_count, 0) as row_count,
  ROUND(size_bytes / 1024 / 1024, 2) as size_mb
FROM `{project_id}.{dataset}.INFORMATION_SCHEMA.TABLES`
WHERE table_type IN ('BASE TABLE', 'VIEW', 'MATERIALIZED VIEW', 'EXTERNAL')
ORDER BY table_schema, table_name;
```

### 3. Columns Query
```sql
SELECT
  table_schema as dataset_name,
  table_name,
  column_name,
  data_type,
  is_nullable,
  ordinal_position,
  is_partitioning_column,
  clustering_ordinal_position
FROM `{project_id}.{dataset}.INFORMATION_SCHEMA.COLUMNS`
ORDER BY table_schema, table_name, ordinal_position;
```

### 4. Partitioning & Clustering Query
```sql
SELECT
  table_schema as dataset_name,
  table_name,
  partition_columns,
  clustering_columns
FROM `{project_id}.{dataset}.INFORMATION_SCHEMA.PARTITIONS`
WHERE partition_columns IS NOT NULL OR clustering_columns IS NOT NULL
GROUP BY table_schema, table_name, partition_columns, clustering_columns;
```

### 5. Views Query
```sql
SELECT
  table_schema as dataset_name,
  table_name as view_name,
  table_type as view_type,
  view_definition,
  creation_time
FROM `{project_id}.{dataset}.INFORMATION_SCHEMA.VIEWS`
ORDER BY table_schema, table_name;
```

### 6. Routines Query
```sql
SELECT
  routine_schema as dataset_name,
  routine_name,
  routine_type,
  data_type as return_type,
  routine_definition as definition,
  external_language,
  created as creation_time
FROM `{project_id}.{dataset}.INFORMATION_SCHEMA.ROUTINES`
ORDER BY routine_schema, routine_name;
```

### 7. Query Statistics (Last 7 days)
```sql
SELECT
  job_id,
  creation_time as execution_time,
  query as query_text,
  total_bytes_processed as bytes_scanned,
  total_slot_ms as slot_milliseconds,
  cache_hit,
  referenced_tables,
  user_email
FROM `{project_id}.region-{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  AND job_type = 'QUERY'
  AND state = 'DONE'
ORDER BY creation_time DESC
LIMIT 1000;
```

### 8. ML Models Query
```sql
SELECT
  model_catalog as project_id,
  model_schema as dataset_name,
  model_name,
  model_type,
  creation_time,
  last_modified_time
FROM `{project_id}.{dataset}.INFORMATION_SCHEMA.ML_MODELS`
ORDER BY model_schema, model_name;
```

### 9. Row-Level Security Query
```sql
SELECT
  table_catalog as project_id,
  table_schema as dataset_name,
  table_name,
  policy_name,
  filter_predicate,
  grantee_list
FROM `{project_id}.{dataset}.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES`
ORDER BY table_schema, table_name;
```

### 10. Column-Level Security Query
```sql
SELECT
  table_schema as dataset_name,
  table_name,
  column_name,
  policy_tags
FROM `{project_id}.{dataset}.INFORMATION_SCHEMA.COLUMN_FIELD_PATHS`
WHERE policy_tags IS NOT NULL
ORDER BY table_schema, table_name, column_name;
```

## Implementation Phases

### Phase 1: Backend Foundation (Day 1-2)
1. Create database models and migrations
2. Create BigQuery metadata extractor service
3. Create assessment repository
4. Create assessment router with basic endpoints
5. Write unit tests for metadata extraction

### Phase 2: Metadata Extraction (Day 3-4)
1. Implement all 11 metadata extraction methods
2. Add sharded table detection logic
3. Add large STRING column detection
4. Add update frequency calculation
5. Test with real BigQuery projects

### Phase 3: Frontend UI (Day 5-6)
1. Update ConnectionsPage with "Perform Assessment" button
2. Create AssessmentReportViewer component
3. Update AssessmentReportsPage with list view
4. Create assessment API service
5. Add loading states and error handling

### Phase 4: Report Generation (Day 7)
1. Create comprehensive report formatter
2. Add executive summary generation
3. Add recommendations engine
4. Add export to PDF/CSV functionality
5. Add report sharing capabilities

### Phase 5: Testing & Polish (Day 8)
1. End-to-end testing
2. Performance optimization
3. UI/UX refinements
4. Documentation
5. Deployment

## API Endpoints

### Start Assessment
```
POST /api/assessments/bigquery
Body: {
  "connection_id": 1,
  "project_id": "my-gcp-project",
  "datasets": ["dataset1", "dataset2"] // optional, all if not specified
}
Response: {
  "assessment_id": 123,
  "status": "pending",
  "started_at": "2026-02-09T10:00:00Z"
}
```

### Get Assessment Status
```
GET /api/assessments/123
Response: {
  "id": 123,
  "connection_id": 1,
  "project_id": "my-gcp-project",
  "status": "completed",
  "started_at": "2026-02-09T10:00:00Z",
  "completed_at": "2026-02-09T10:15:00Z",
  "total_datasets": 5,
  "total_tables": 150,
  "total_views": 25,
  "total_routines": 10,
  "total_ml_models": 3,
  "total_size_mb": 50000
}
```

### Get Assessment Report
```
GET /api/assessments/123/report
Response: {
  "assessment_id": 123,
  "executive_summary": {...},
  "datasets": [...],
  "tables": [...],
  "columns": [...],
  "views": [...],
  "routines": [...],
  "query_stats": {...},
  "ml_models": [...],
  "security": {...},
  "sharded_tables": [...],
  "recommendations": [...]
}
```

## UI Flow

### 1. From Connections Page
1. User clicks three-dot menu on BigQuery connection
2. Sees "Perform Assessment" option
3. Clicks "Perform Assessment"
4. Modal appears: "Start BigQuery Assessment?"
5. User confirms
6. Assessment starts (shows progress toast)
7. User redirected to Assessments page

### 2. Assessments Page
1. Shows list of all assessments
2. Each row shows: Connection Name, Project ID, Status, Date, Actions
3. Status badge: Pending (yellow), Running (blue), Completed (green), Failed (red)
4. Click on row to view detailed report
5. Actions menu: View Report, Delete

### 3. Assessment Report Viewer
1. Executive Summary section (collapsible)
2. Datasets section with table
3. Tables section with filters and search
4. Columns section with data type breakdown
5. Views & Routines section
6. Query Statistics with charts
7. ML Models section
8. Security Analysis section
9. Sharded Tables section
10. Recommendations section
11. Export button (PDF/CSV)

## Success Metrics

1. **Completeness**: Extract all 11 metadata categories
2. **Performance**: Complete assessment in < 5 minutes for 100 tables
3. **Accuracy**: 100% accurate metadata extraction
4. **Usability**: Users can start assessment in < 3 clicks
5. **Insights**: Generate actionable recommendations

## Next Steps

1. Review and approve this plan
2. Create database migration for assessment tables
3. Start Phase 1 implementation
4. Set up testing environment with sample BigQuery project
5. Iterate based on feedback
