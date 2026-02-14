# Migration Execution Implementation Plan

## Overview

Implement full migration execution flow with proper connection name display, Run/Resume actions, and BigQuery to GCS export with compression options.

## Tasks

### 1. Fix Connection Names Display ✅

**Problem**: Source and Destination showing as "undefined"

**Solution**: 
- Backend: Include connection names in migration list response
- Frontend: Display connection names instead of project/cluster

**Files to Modify**:
- `backend/routers/bq_redshift_migration.py` - Add connection name lookup
- `frontend/src/pages/MigrationsPage.tsx` - Display connection names
- `frontend/src/services/bqRedshiftApi.ts` - Update interface

### 2. Add Run/Resume Migration Actions ✅

**Problem**: Menu only has Test/Update/Delete

**Solution**:
- Add "Run Migration" menu item
- Add "Resume Migration" menu item (conditional on status)
- Call `/start` or `/resume` endpoints

**Files to Modify**:
- `frontend/src/pages/MigrationsPage.tsx` - Add menu items and handlers

### 3. Implement BigQuery to GCS Export ✅

**Problem**: Start migration doesn't actually export data

**Solution**:
- Create orchestrator service to handle migration execution
- Implement BigQuery export with proper compression
- Update migration status during execution

**Files to Create/Modify**:
- `backend/services/bq_redshift_migration/orchestrator.py` - Migration orchestration
- `backend/services/bq_redshift_migration/bigquery_exporter.py` - BQ export logic
- `backend/routers/bq_redshift_migration.py` - Wire up start endpoint

### 4. Add Compression Options ✅

**Problem**: No compression selection in wizard

**Solution**:
- Add compression dropdown in ConfigurationSetupStep
- Format-specific compression options:
  - CSV: None, GZIP
  - JSON: None, GZIP
  - AVRO: None, SNAPPY, DEFLATE
  - Parquet: None, GZIP, SNAPPY, ZSTD

**Files to Modify**:
- `frontend/src/components/migrations/steps/ConfigurationSetupStep.tsx`
- `frontend/src/components/migrations/CreateMigrationWizard.tsx`

### 5. Make Schedule Form Placeholder ✅

**Problem**: Schedule form is functional but stages aren't ready

**Solution**:
- Add "Coming Soon" warning to SchedulingMonitoringStep
- Keep form visible but mark as placeholder

**Files to Modify**:
- `frontend/src/components/migrations/steps/SchedulingMonitoringStep.tsx`

### 6. Add Required Packages ✅

**Packages Needed**:
- `google-cloud-bigquery` - Already installed
- `google-cloud-storage` - For GCS operations
- `boto3` - For S3 operations (future)

**Files to Modify**:
- `backend/requirements.txt`

## Implementation Order

1. ✅ Fix connection names display (quick win)
2. ✅ Add Run/Resume actions (quick win)
3. ✅ Add compression options to wizard (quick win)
4. ✅ Make schedule form placeholder (quick win)
5. ✅ Implement BigQuery to GCS export (main work)
6. ✅ Add required packages

## API Endpoints

### Existing (to be enhanced)
- `POST /api/migrations/bq-redshift/{id}/start` - Start migration
- `POST /api/migrations/bq-redshift/{id}/resume` - Resume migration
- `GET /api/migrations/bq-redshift/{id}/status` - Get status

### New (if needed)
- None - use existing endpoints

## Database Schema

No changes needed - existing schema supports all features.

## Testing Plan

### Unit Tests
- Test BigQuery export with different formats
- Test compression options
- Test error handling

### Integration Tests
- Test full export flow
- Test status updates
- Test resume functionality

### Manual Testing
1. Create migration with compression options
2. Click "Run Migration"
3. Verify export starts
4. Monitor status updates
5. Verify files in GCS
6. Test pause/resume

## Success Criteria

✅ Connection names display correctly  
✅ Run/Resume actions work  
✅ BigQuery export executes  
✅ Compression options available  
✅ Status updates in real-time  
✅ Files appear in GCS  
✅ Schedule form marked as placeholder  

## Timeline

- Connection names: 30 minutes
- Run/Resume actions: 30 minutes
- Compression options: 30 minutes
- Schedule placeholder: 15 minutes
- BigQuery export: 2-3 hours
- Testing: 1 hour

**Total**: ~5 hours

## Next Steps After This

1. Implement GCS to S3 transfer
2. Implement S3 to Redshift load
3. Implement full orchestration
4. Implement scheduler for recurring migrations
5. Add progress tracking UI
