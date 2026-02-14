# BigQuery to Redshift Migration - Implementation Guide

## Overview
Production-grade implementation of BigQuery to Redshift migration workflow with 4-step wizard, metadata discovery, and 3-stage migration process.

## Architecture Summary

### Migration Flow
```
Step 1: Connection & Staging Configuration
  ↓
Step 2: Source Metadata Discovery (Object Picker)
  ↓
Step 3: Migration Strategy Selection
  ↓
Step 4: Scheduling & Monitoring
  ↓
Execution: BQ → GCS → S3 → Redshift
```

### 3-Stage Migration Process
1. **Export**: BigQuery → GCS (Google Cloud Storage)
2. **Transfer**: GCS → S3 (AWS S3)
3. **Load**: S3 → Redshift

## Implementation Components

### 1. Frontend Components

#### Create Migration Wizard (`CreateMigrationWizard.tsx`)
- Multi-step form with 4 steps
- Progress indicator
- Validation at each step
- Back/Next navigation
- Submit and save draft functionality

#### Step 1: Connection & Staging Configuration
**Inputs**:
- Source Connection (BigQuery) - dropdown
- Target Connection (Redshift) - dropdown
- GCS Staging Bucket - text input
- GCS Region - dropdown
- S3 Staging Bucket - text input
- S3 Region - dropdown
- IAM Role/Service Account - JSON upload

**Validation**:
- Both connections must be selected
- Staging buckets are mandatory when BQ→Redshift
- Valid JSON for service account

#### Step 2: Source Metadata Discovery
**UI Component**: Hierarchical Tree View
- Root: BigQuery Project
- Level 1: Datasets (expandable)
- Level 2: Tables (selectable with checkboxes)

**Features**:
- Lazy loading (fetch tables when dataset expanded)
- Select All toggle
- Select entire dataset
- Search/filter functionality
- Display table metadata (row count, size)

**Backend API**:
```
GET /api/migrations/bq-redshift/discover-metadata
  ?connection_id={id}
  &project_id={project}
  &dataset={dataset}
```

#### Step 3: Migration Strategy Selection
**Options** (Radio buttons with descriptions):
1. **GCP Storage Transfer Service** (Path A)
   - Tag: "Recommended for 100TB+ / Large Scale"
   - Description: Native GCP tooling, managed transfer
   
2. **AWS SCT** (Path B)
   - Tag: "Recommended for Schema-heavy migrations"
   - Description: AWS-managed end-to-end
   
3. **AWS DataSync** (Path C)
   - Tag: "Recommended for Continuous Sync"
   - Description: Hybrid cloud optimization
   
4. **CLI Orchestration** (Path D)
   - Tag: "Legacy / Small scale"
   - Description: Full control, scriptable

**Summary Sidebar**:
- Total tables selected: X
- Estimated data volume: Y GB
- Estimated duration: Z hours
- Recommended pathway: Based on volume

#### Step 4: Scheduling & Monitoring
**Inputs**:
- Schedule Type: Radio (Run Now / Scheduled)
- CRON Expression: Text input (if scheduled)
- Next Run Time: Display calculated time
- Email Notifications: Checkbox
- Slack Webhook: Optional text input

**Monitoring Configuration**:
- Log Level: Dropdown (DEBUG, INFO, WARNING, ERROR)
- Enable Checkpointing: Checkbox (default: true)
- Retry Failed Shards: Checkbox (default: true)
- Max Retries: Number input (default: 3)

### 2. Backend API Endpoints

#### Create Migration
```python
POST /api/migrations/bq-redshift/create
Request Body:
{
  "migration_name": "string",
  "source_connection_id": int,
  "target_connection_id": int,
  "source_project_id": "string",
  "source_dataset": "string",
  "source_tables": ["table1", "table2"],
  "gcs_bucket": "string",
  "gcs_region": "string",
  "s3_bucket": "string",
  "s3_region": "string",
  "pathway": "A|B|C|D",
  "schedule_type": "one-time|recurring",
  "cron_expression": "string (optional)",
  "service_account_json": "string"
}

Response:
{
  "success": true,
  "migration_id": int,
  "message": "Migration created successfully"
}
```

#### Discover BigQuery Metadata
```python
GET /api/migrations/bq-redshift/discover-metadata
Query Params:
  - connection_id: int (required)
  - project_id: string (optional, from connection if not provided)
  - dataset: string (optional, if provided returns tables in dataset)

Response:
{
  "project_id": "string",
  "datasets": [
    {
      "dataset_id": "string",
      "location": "string",
      "created": "timestamp",
      "modified": "timestamp",
      "table_count": int
    }
  ],
  "tables": [  // Only if dataset param provided
    {
      "table_id": "string",
      "type": "TABLE|VIEW",
      "num_rows": int,
      "num_bytes": int,
      "created": "timestamp",
      "modified": "timestamp"
    }
  ]
}
```

#### Start Migration
```python
POST /api/migrations/bq-redshift/{migration_id}/start
Response:
{
  "success": true,
  "job_id": "string",
  "message": "Migration started"
}
```

#### Get Migration Status
```python
GET /api/migrations/bq-redshift/{migration_id}/status
Response:
{
  "migration_id": int,
  "status": "pending|running|paused|completed|failed",
  "current_stage": "export|transfer|load",
  "progress": {
    "total_shards": int,
    "completed_shards": int,
    "failed_shards": int,
    "percentage": float
  },
  "metrics": {
    "rows_exported": int,
    "rows_transferred": int,
    "rows_loaded": int,
    "bytes_transferred": int,
    "duration_seconds": int
  },
  "shards": [
    {
      "shard_id": int,
      "table_name": "string",
      "export_status": "string",
      "transfer_status": "string",
      "load_status": "string"
    }
  ]
}
```

#### Pause/Resume/Cancel Migration
```python
POST /api/migrations/bq-redshift/{migration_id}/pause
POST /api/migrations/bq-redshift/{migration_id}/resume
POST /api/migrations/bq-redshift/{migration_id}/cancel
```

#### Get Migration Logs
```python
GET /api/migrations/bq-redshift/{migration_id}/logs
Query Params:
  - level: string (optional filter)
  - stage: string (optional filter)
  - limit: int (default: 100)
  - offset: int (default: 0)

Response:
{
  "logs": [
    {
      "id": int,
      "timestamp": "string",
      "level": "string",
      "stage": "string",
      "message": "string",
      "shard_id": int (optional)
    }
  ],
  "total": int
}
```

### 3. Backend Services Implementation

#### Metadata Discovery Service
**File**: `backend/services/bq_redshift_migration/metadata_discovery.py`

```python
class BigQueryMetadataDiscovery:
    def __init__(self, connection_params):
        """Initialize with BigQuery connection"""
        self.project_id = connection_params['project_id']
        self.credentials = self._get_credentials(connection_params)
        self.client = bigquery.Client(
            credentials=self.credentials,
            project=self.project_id
        )
    
    def list_datasets(self):
        """List all datasets in project"""
        datasets = list(self.client.list_datasets())
        return [
            {
                'dataset_id': ds.dataset_id,
                'location': ds.location,
                'created': ds.created.isoformat(),
                'modified': ds.modified.isoformat()
            }
            for ds in datasets
        ]
    
    def list_tables(self, dataset_id):
        """List all tables in a dataset"""
        dataset_ref = self.client.dataset(dataset_id)
        tables = list(self.client.list_tables(dataset_ref))
        
        table_details = []
        for table in tables:
            table_ref = dataset_ref.table(table.table_id)
            table_obj = self.client.get_table(table_ref)
            
            table_details.append({
                'table_id': table.table_id,
                'type': table.table_type,
                'num_rows': table_obj.num_rows,
                'num_bytes': table_obj.num_bytes,
                'created': table_obj.created.isoformat(),
                'modified': table_obj.modified.isoformat()
            })
        
        return table_details
    
    def get_table_schema(self, dataset_id, table_id):
        """Get detailed schema for a table"""
        table_ref = self.client.dataset(dataset_id).table(table_id)
        table = self.client.get_table(table_ref)
        
        return {
            'fields': [
                {
                    'name': field.name,
                    'type': field.field_type,
                    'mode': field.mode,
                    'description': field.description
                }
                for field in table.schema
            ]
        }
```

#### Path A Implementation (GCP Native)
**File**: `backend/services/bq_redshift_migration/pathway_a.py`

```python
class PathwayA:
    """
    GCP Native Pathway
    Flow: BigQuery → GCS → S3 (via GCP Storage Transfer) → Redshift
    """
    
    def __init__(self, migration_config, checkpoint_manager):
        self.config = migration_config
        self.checkpoint_mgr = checkpoint_manager
        self.bq_client = self._init_bigquery_client()
        self.gcs_client = self._init_gcs_client()
        self.s3_client = self._init_s3_client()
        self.redshift_client = self._init_redshift_client()
    
    async def execute(self):
        """Execute full migration pipeline"""
        try:
            # Stage 1: Export BigQuery to GCS
            await self.stage_1_export_to_gcs()
            
            # Stage 2: Transfer GCS to S3
            await self.stage_2_transfer_to_s3()
            
            # Stage 3: Load S3 to Redshift
            await self.stage_3_load_to_redshift()
            
            return {'success': True, 'message': 'Migration completed'}
        
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            await self.checkpoint_mgr.save_checkpoint(
                migration_id=self.config['migration_id'],
                stage=self.current_stage,
                error=str(e)
            )
            raise
    
    async def stage_1_export_to_gcs(self):
        """Stage 1: Export BigQuery tables to GCS"""
        logger.info("Stage 1: Exporting BigQuery to GCS")
        
        for table in self.config['source_tables']:
            # Check if already exported (resume logic)
            if self.checkpoint_mgr.is_stage_complete(
                migration_id=self.config['migration_id'],
                table=table,
                stage='export'
            ):
                logger.info(f"Table {table} already exported, skipping")
                continue
            
            # Export table to GCS
            destination_uri = f"gs://{self.config['gcs_bucket']}/{self.config['gcs_path']}/{table}/*.avro"
            
            job_config = bigquery.ExtractJobConfig()
            job_config.destination_format = bigquery.DestinationFormat.AVRO
            job_config.compression = bigquery.Compression.SNAPPY
            
            table_ref = f"{self.config['source_project_id']}.{self.config['source_dataset']}.{table}"
            
            extract_job = self.bq_client.extract_table(
                table_ref,
                destination_uri,
                job_config=job_config
            )
            
            # Wait for job to complete
            extract_job.result()
            
            # Get list of exported shards
            shards = self._list_gcs_shards(table)
            
            # Save shard metadata
            for idx, shard in enumerate(shards):
                await self._save_shard_metadata(
                    table=table,
                    shard_index=idx,
                    gcs_uri=shard['uri'],
                    file_size=shard['size'],
                    stage='export'
                )
            
            # Mark export complete
            await self.checkpoint_mgr.mark_stage_complete(
                migration_id=self.config['migration_id'],
                table=table,
                stage='export'
            )
            
            logger.info(f"Exported {table} to GCS ({len(shards)} shards)")
    
    async def stage_2_transfer_to_s3(self):
        """Stage 2: Transfer GCS to S3 using GCP Storage Transfer Service"""
        logger.info("Stage 2: Transferring GCS to S3")
        
        # Create Storage Transfer Service job
        transfer_job = self._create_storage_transfer_job()
        
        # Monitor transfer progress
        while not self._is_transfer_complete(transfer_job):
            await asyncio.sleep(30)  # Check every 30 seconds
            progress = self._get_transfer_progress(transfer_job)
            logger.info(f"Transfer progress: {progress}%")
        
        # Update shard metadata with S3 URIs
        for table in self.config['source_tables']:
            shards = await self._get_table_shards(table)
            for shard in shards:
                s3_uri = self._convert_gcs_to_s3_uri(shard['gcs_uri'])
                await self._update_shard_s3_uri(shard['id'], s3_uri)
                
                await self.checkpoint_mgr.mark_stage_complete(
                    migration_id=self.config['migration_id'],
                    shard_id=shard['id'],
                    stage='transfer'
                )
        
        logger.info("Transfer to S3 completed")
    
    async def stage_3_load_to_redshift(self):
        """Stage 3: Load S3 data to Redshift using COPY command"""
        logger.info("Stage 3: Loading S3 to Redshift")
        
        for table in self.config['source_tables']:
            # Check if already loaded
            if self.checkpoint_mgr.is_stage_complete(
                migration_id=self.config['migration_id'],
                table=table,
                stage='load'
            ):
                logger.info(f"Table {table} already loaded, skipping")
                continue
            
            # Create table in Redshift if not exists
            await self._create_redshift_table(table)
            
            # Generate manifest file for COPY command
            manifest_uri = await self._generate_manifest_file(table)
            
            # Execute COPY command
            copy_command = f"""
            COPY {self.config['target_schema']}.{table}
            FROM '{manifest_uri}'
            IAM_ROLE '{self.config['iam_role']}'
            FORMAT AS AVRO 'auto'
            MANIFEST
            COMPUPDATE ON
            STATUPDATE ON;
            """
            
            await self._execute_redshift_query(copy_command)
            
            # Verify row count
            source_count = await self._get_bigquery_row_count(table)
            target_count = await self._get_redshift_row_count(table)
            
            if source_count != target_count:
                logger.warning(
                    f"Row count mismatch for {table}: "
                    f"Source={source_count}, Target={target_count}"
                )
            
            # Mark load complete
            await self.checkpoint_mgr.mark_stage_complete(
                migration_id=self.config['migration_id'],
                table=table,
                stage='load'
            )
            
            logger.info(f"Loaded {table} to Redshift ({target_count} rows)")
    
    def _create_storage_transfer_job(self):
        """Create GCP Storage Transfer Service job"""
        # Implementation for creating transfer job
        pass
    
    def _generate_manifest_file(self, table):
        """Generate Redshift manifest file"""
        # Implementation for generating manifest
        pass
```

#### Checkpoint Manager
**File**: `backend/services/bq_redshift_migration/checkpoint_manager.py`

```python
class CheckpointManager:
    """Manages migration checkpoints for resumability"""
    
    def __init__(self, db_session):
        self.db = db_session
    
    async def save_checkpoint(self, migration_id, stage, data):
        """Save checkpoint to database"""
        migration = self.db.query(MigrationBQRedshift).filter_by(
            id=migration_id
        ).first()
        
        if not migration:
            raise ValueError(f"Migration {migration_id} not found")
        
        checkpoint_data = migration.checkpoint_data or {}
        checkpoint_data[stage] = {
            'timestamp': datetime.utcnow().isoformat(),
            'data': data
        }
        
        migration.checkpoint_data = checkpoint_data
        migration.current_stage = stage
        migration.updated_at = datetime.utcnow()
        
        self.db.commit()
    
    async def load_checkpoint(self, migration_id):
        """Load last checkpoint"""
        migration = self.db.query(MigrationBQRedshift).filter_by(
            id=migration_id
        ).first()
        
        return migration.checkpoint_data if migration else None
    
    async def get_resume_point(self, migration_id):
        """Determine where to resume from"""
        shards = self.db.query(MigrationShard).filter_by(
            migration_id=migration_id
        ).all()
        
        # Find incomplete shards
        pending_export = [s for s in shards if s.export_status != 'completed']
        pending_transfer = [s for s in shards if s.transfer_status != 'completed']
        pending_load = [s for s in shards if s.load_status != 'completed']
        
        if pending_export:
            return 'export', pending_export
        elif pending_transfer:
            return 'transfer', pending_transfer
        elif pending_load:
            return 'load', pending_load
        else:
            return 'completed', []
    
    def is_stage_complete(self, migration_id, table, stage):
        """Check if a stage is complete for a table"""
        shards = self.db.query(MigrationShard).filter_by(
            migration_id=migration_id,
            table_name=table
        ).all()
        
        if not shards:
            return False
        
        status_field = f"{stage}_status"
        return all(getattr(s, status_field) == 'completed' for s in shards)
    
    async def mark_stage_complete(self, migration_id, table=None, shard_id=None, stage='export'):
        """Mark a stage as complete"""
        if shard_id:
            shard = self.db.query(MigrationShard).filter_by(id=shard_id).first()
            if shard:
                setattr(shard, f"{stage}_status", 'completed')
                setattr(shard, f"{stage}_completed_at", datetime.utcnow())
                self.db.commit()
        elif table:
            shards = self.db.query(MigrationShard).filter_by(
                migration_id=migration_id,
                table_name=table
            ).all()
            for shard in shards:
                setattr(shard, f"{stage}_status", 'completed')
                setattr(shard, f"{stage}_completed_at", datetime.utcnow())
            self.db.commit()
```

### 4. Database Operations

#### Run Migrations
```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

### 5. Environment Configuration

Add to `backend/.env`:
```bash
# BigQuery Configuration
GCP_PROJECT_ID=your-project-id
GCP_SERVICE_ACCOUNT_KEY_PATH=/path/to/key.json

# GCS Configuration
GCS_STAGING_BUCKET=your-gcs-bucket
GCS_STAGING_REGION=us-central1

# AWS Configuration
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1

# S3 Configuration
S3_STAGING_BUCKET=your-s3-bucket
S3_STAGING_REGION=us-east-1

# Redshift Configuration
REDSHIFT_CLUSTER=your-cluster
REDSHIFT_DATABASE=your-database
REDSHIFT_USER=your-user
REDSHIFT_PASSWORD=your-password
REDSHIFT_PORT=5439

# IAM Role for Redshift COPY
REDSHIFT_IAM_ROLE=arn:aws:iam::account:role/RedshiftCopyRole
```

### 6. Testing Strategy

#### Unit Tests
- Test metadata discovery
- Test checkpoint manager
- Test each migration stage independently
- Test error handling and retry logic

#### Integration Tests
- Test full migration flow with sample data
- Test resume functionality
- Test concurrent migrations
- Test failure scenarios

#### Load Tests
- Test with large datasets (100GB+)
- Test with many tables (1000+)
- Test concurrent migrations
- Monitor resource usage

### 7. Monitoring & Observability

#### Metrics to Track
- Migration duration
- Data transfer rate (GB/hour)
- Row count accuracy
- Error rate
- Retry count
- Resource utilization (CPU, memory, network)

#### Logging
- Log all stage transitions
- Log shard-level operations
- Log errors with full context
- Log performance metrics

#### Alerts
- Migration failure
- Data count mismatch
- Transfer rate below threshold
- High error rate
- Resource exhaustion

## Next Steps

1. ✅ Update architecture documentation
2. 🚧 Implement Create Migration Wizard UI
3. 🚧 Implement metadata discovery API
4. 🚧 Implement Path A migration logic
5. ⏳ Add comprehensive error handling
6. ⏳ Add monitoring and metrics
7. ⏳ Write tests
8. ⏳ Performance optimization
9. ⏳ Security hardening
10. ⏳ Documentation completion

## Timeline

- **Week 1**: UI components + metadata discovery
- **Week 2**: Path A implementation (export + transfer)
- **Week 3**: Path A completion (load) + testing
- **Week 4**: Error handling + monitoring + optimization
- **Week 5**: Additional pathways (B, C, D)
- **Week 6**: Production hardening + documentation
