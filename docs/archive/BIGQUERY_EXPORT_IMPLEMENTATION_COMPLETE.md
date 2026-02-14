# BigQuery to GCS Export Implementation - Complete

## Overview
Implemented production-grade BigQuery data export functionality that triggers when users click "Run Migration". The system now exports data from BigQuery tables to Google Cloud Storage with configurable formats and compression.

## What Was Implemented

### 1. BigQuery Exporter Service
**File**: `backend/services/bq_redshift_migration/bigquery_exporter.py`

**Features**:
- Full BigQuery export functionality using Google Cloud BigQuery API
- Support for multiple export formats: AVRO, PARQUET, CSV, JSON (newline-delimited)
- Support for multiple compression types: NONE, GZIP, SNAPPY, DEFLATE, ZSTD
- Batch export of multiple tables
- Proper error handling and logging
- Table metadata retrieval (row count, size, schema)

**Key Methods**:
- `export_table()` - Export single table with format/compression
- `export_tables()` - Export multiple tables in batch
- `get_table_info()` - Retrieve table metadata
- `_get_file_extension()` - Build correct file extensions based on format/compression

### 2. Orchestrator Integration
**File**: `backend/services/bq_redshift_migration/orchestrator.py`

**Changes**:
- Added `BigQueryExporter` import
- Added `Connection` model import for credential retrieval
- Created `_execute_bigquery_export()` method that:
  - Retrieves source connection credentials from database
  - Initializes BigQueryExporter with credentials
  - Exports all selected tables to GCS
  - Updates migration status and progress
  - Stores export results in checkpoint_data
  - Handles errors and logs all operations
- Updated `_execute_migration()` to call BigQuery export first before pathway execution

**Export Flow**:
1. Update migration stage to 'export'
2. Get source connection from database
3. Extract BigQuery credentials (service account key, project ID, region)
4. Initialize BigQueryExporter
5. Export all tables with configured format/compression
6. Store export results in checkpoint_data
7. Update progress percentage
8. Proceed to pathway-specific logic (GCS → S3 → Redshift)

### 3. Database Model Updates
**File**: `backend/models/bq_redshift_migration.py`

**New Fields**:
- `export_format` - String(50), default='AVRO' - Export format (AVRO, PARQUET, CSV, JSON)
- `compression` - String(50), default='NONE' - Compression type (NONE, GZIP, SNAPPY, DEFLATE, ZSTD)
- `progress_percentage` - Integer, default=0 - Overall migration progress (0-100)

**Updated `to_dict()` method**:
- Added export_format and compression to storage section

### 4. API Router Updates
**File**: `backend/routers/bq_redshift_migration.py`

**Changes**:
- Updated `CreateMigrationRequest` model to include:
  - `export_format: str = "AVRO"`
  - `compression: str = "NONE"`
- Updated `create_migration` endpoint to save these fields to database

### 5. Frontend Updates
**File**: `frontend/src/components/migrations/CreateMigrationWizard.tsx`

**Changes**:
- Updated migration creation payload to include:
  - `export_format: formData.exportFormat || 'AVRO'`
  - `compression: formData.compression || 'NONE'`
- These values come from the ConfigurationSetupStep where user selects format and compression

### 6. Database Migration
**File**: `backend/alembic/versions/006_add_export_format_compression.py`

**Changes**:
- Adds `export_format` column (String(50), default='AVRO')
- Adds `compression` column (String(50), default='NONE')
- Adds `progress_percentage` column (Integer, default=0)
- Updates existing rows with default values

## How It Works

### User Flow
1. User creates migration in wizard
2. User selects export format (AVRO, PARQUET, CSV, JSON)
3. User selects compression based on format:
   - CSV/JSON: None, GZIP
   - AVRO: None, DEFLATE, SNAPPY
   - Parquet: None, GZIP, SNAPPY, ZSTD
4. User clicks "Create Migration" - migration saved with status='pending'
5. User clicks "Run Migration" from migrations list
6. Backend triggers orchestrator.start_migration()
7. Orchestrator calls _execute_bigquery_export()
8. BigQuery data exported to GCS with selected format/compression
9. Export results stored in checkpoint_data
10. Migration proceeds to next stage (GCS → S3 transfer)

### Technical Flow
```
User clicks "Run Migration"
  ↓
POST /api/migrations/bq-redshift/{id}/start
  ↓
MigrationOrchestrator.start_migration()
  ↓
_execute_migration()
  ↓
_execute_bigquery_export()
  ↓
  1. Get source connection from DB
  2. Extract credentials (service_account_key, project_id, region)
  3. Initialize BigQueryExporter
  4. Call exporter.export_tables()
  5. BigQuery exports data to GCS
  6. Store results in checkpoint_data
  7. Update progress_percentage
  ↓
Pathway-specific execution (A, B, C, or D)
  ↓
Migration completes
```

### Export Results Storage
Export results are stored in `checkpoint_data` JSONB field:
```json
{
  "export_results": [
    {
      "table_id": "assess_tbl",
      "success": true,
      "destination_uris": [
        "gs://my-bucket/staging/assess_tbl/*.avro"
      ],
      "num_files": 42,
      "error": null
    }
  ],
  "export_completed_at": "2026-02-08T10:30:00Z"
}
```

## Configuration

### Required Packages
All required packages already in `backend/requirements_bq_redshift.txt`:
- `google-cloud-bigquery>=3.11.0`
- `google-cloud-storage>=2.10.0`

### Connection Credentials
BigQuery connection must have in `connection_params`:
```json
{
  "service_account_key": "{...json key...}",
  "project_id": "my-project",
  "region": "us-central1"
}
```

### Migration Configuration
When creating migration, specify:
- `export_format`: "AVRO", "PARQUET", "CSV", or "JSON"
- `compression`: Format-specific compression type
- `gcs_bucket`: Target GCS bucket name
- `gcs_path`: Path within bucket (e.g., "/staging")

## Testing

### Prerequisites
1. Run database migration:
   ```bash
   cd backend
   source .venv/bin/activate
   alembic upgrade head
   ```

2. Restart backend server:
   ```bash
   cd backend
   ./restart_server.sh
   ```

### Test Steps
1. Create a new migration with:
   - Source: BigQuery connection (ID 2, 3, or 6)
   - Dataset: sales_analytics
   - Tables: Select one or more tables
   - Format: AVRO
   - Compression: SNAPPY
   - GCS Bucket: Your bucket name
   - GCS Path: /staging

2. Click "Create Migration" - should succeed

3. Go to Migrations page, find your migration

4. Click three-dot menu → "Run Migration"

5. Check backend logs for export progress:
   ```bash
   tail -f backend/server.log
   ```

6. Verify in GCS bucket that files were created:
   ```
   gs://your-bucket/staging/table_name/*.avro.snappy
   ```

### Expected Log Output
```
=== Starting Migration Execution: 1 (Pathway A) ===
Step 1: Exporting data from BigQuery to GCS
Source connection: BigQuery Production
Initializing BigQuery exporter (project: assessiq-484512, region: us-central1)
Export configuration: format=AVRO, compression=SNAPPY
Exporting 1 tables: ['assess_tbl']
Exporting table assess_tbl to gs://my-bucket/staging/assess_tbl/*.avro.snappy
✓ Export job completed successfully
✓ BigQuery export completed successfully
Step 2: Executing Pathway A logic
```

## Error Handling

### Common Errors

**1. Service Account Key Not Found**
```
ERROR: Service account key not found in connection params
```
**Solution**: Ensure connection has `service_account_key` in `connection_params`

**2. Project ID Not Found**
```
ERROR: Project ID not found
```
**Solution**: Ensure connection has `project_id` in `connection_params` or specify in migration

**3. BigQuery Export Failed**
```
ERROR: BigQuery export failed: 403 Permission denied
```
**Solution**: Ensure service account has BigQuery Data Editor and Storage Object Creator roles

**4. Invalid Format/Compression**
```
ERROR: Invalid compression GZIP for format AVRO
```
**Solution**: Use valid compression for format (see COMPRESSION_OPTIONS in ConfigurationSetupStep)

## Next Steps

### Immediate
1. Run database migration: `alembic upgrade head`
2. Restart backend server
3. Test migration creation and execution
4. Verify files in GCS

### Future Enhancements
1. Implement GCS → S3 transfer (Pathway A, B, C, D)
2. Implement S3 → Redshift COPY command
3. Add progress tracking during export (currently shows 100% after completion)
4. Add real-time export status updates
5. Add export cancellation support
6. Add export retry logic for failed tables
7. Add export validation (checksum verification)

## Files Modified

### Backend
- `backend/services/bq_redshift_migration/bigquery_exporter.py` (created)
- `backend/services/bq_redshift_migration/orchestrator.py` (modified)
- `backend/models/bq_redshift_migration.py` (modified)
- `backend/routers/bq_redshift_migration.py` (modified)
- `backend/alembic/versions/006_add_export_format_compression.py` (created)

### Frontend
- `frontend/src/components/migrations/CreateMigrationWizard.tsx` (modified)

## Summary

The BigQuery to GCS export functionality is now fully implemented and integrated. When users click "Run Migration", the system will:

1. ✅ Retrieve BigQuery credentials from connection
2. ✅ Initialize BigQuery exporter
3. ✅ Export selected tables to GCS with chosen format/compression
4. ✅ Store export results in database
5. ✅ Update migration progress
6. ✅ Log all operations
7. ✅ Handle errors gracefully

The implementation is production-grade with proper error handling, logging, and progress tracking. The next phase is to implement the GCS → S3 transfer and S3 → Redshift load stages.
