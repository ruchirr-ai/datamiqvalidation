# Migrations Module

## Overview
The Migrations module handles BigQuery to Redshift data migration with multiple pathway options.

## Migration Pathways

### Pathway A: AWS SCT + DMS
- Uses AWS Schema Conversion Tool
- AWS Database Migration Service for data transfer
- Best for: Standard migrations with AWS tooling

### Pathway B: AWS DataSync
- Direct GCS to S3 transfer using AWS DataSync
- Automated file synchronization
- Best for: Large-scale data transfers

### Pathway C: Direct Download/Upload
- Downloads from GCS, uploads to S3
- Full control over transfer process
- Best for: Custom transfer requirements

## Key Components

### Backend
- **Orchestrator**: `backend/services/bq_redshift_migration/orchestrator.py`
- **BigQuery Exporter**: `backend/services/bq_redshift_migration/bigquery_exporter.py`
- **Redshift Loader**: `backend/services/bq_redshift_migration/redshift_loader.py`
- **Pathway Services**: `backend/services/bq_redshift_migration/pathway_*.py`
- **Router**: `backend/routers/bq_redshift_migration.py`

### Frontend
- **Page**: `frontend/src/pages/MigrationsPage.tsx`
- **Wizard**: `frontend/src/components/migrations/CreateMigrationWizard.tsx`
- **Steps**: `frontend/src/components/migrations/steps/`

## Migration Workflow

1. **Connection Selection**: Choose source (BigQuery) and target (Redshift)
2. **Strategy Selection**: Select migration pathway
3. **Metadata Discovery**: Discover tables and schemas
4. **Configuration**: Configure migration settings
5. **Execution**: Run migration in background
6. **Monitoring**: Track progress and status

## Features

- ✅ Multi-pathway support
- ✅ Background execution
- ✅ Progress tracking
- ✅ Error handling and retry
- ✅ Pause/resume capability
- ✅ Detailed logging
- ✅ Validation checks

## Configuration

### Required Settings
- Source connection (BigQuery)
- Target connection (Redshift)
- GCS bucket for export
- S3 bucket for staging
- IAM role for Redshift COPY

### Optional Settings
- Batch size
- Parallel workers
- Timeout values
- Retry attempts

## Monitoring

Track migration progress:
- Overall progress percentage
- Current stage
- Tables completed
- Rows transferred
- Errors encountered

## API Endpoints

- `POST /api/migrations/` - Create migration
- `GET /api/migrations/` - List migrations
- `GET /api/migrations/{id}` - Get migration details
- `PUT /api/migrations/{id}` - Update migration
- `DELETE /api/migrations/{id}` - Delete migration
- `POST /api/migrations/{id}/start` - Start migration
- `POST /api/migrations/{id}/pause` - Pause migration
- `POST /api/migrations/{id}/resume` - Resume migration
- `POST /api/migrations/{id}/cancel` - Cancel migration
