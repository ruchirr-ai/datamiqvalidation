# BigQuery to Redshift Migration Tool - Architecture

## Overview
Comprehensive data migration tool supporting four distinct pathways for moving large-scale datasets from Google BigQuery to Amazon Redshift with checkpointing, resumability, and enterprise-grade observability.

## Migration Pathways

### Path A: GCP Native
**Flow**: BigQuery → GCS → S3 (via GCP Storage Transfer Service) → Redshift (COPY)
- **Best For**: Organizations with strong GCP presence
- **Advantages**: Native GCP tooling, managed transfer service
- **Components**: BigQuery Export API, GCP Storage Transfer Service, Redshift COPY

### Path B: AWS Native
**Flow**: BigQuery → Redshift (via AWS SCT + Data Extraction Agents)
- **Best For**: Organizations with strong AWS presence
- **Advantages**: AWS-managed end-to-end, minimal intermediate storage
- **Components**: AWS Schema Conversion Tool, AWS DMS Agents

### Path C: Hybrid Sync
**Flow**: BigQuery → GCS → S3 (via AWS DataSync) → Redshift
- **Best For**: Hybrid cloud environments
- **Advantages**: AWS DataSync reliability, cross-cloud optimization
- **Components**: BigQuery Export, AWS DataSync, Redshift COPY

### Path D: CLI/Legacy
**Flow**: BigQuery → GCS → S3 (via gsutil/aws s3 cp) → Redshift
- **Best For**: Custom orchestration, legacy systems
- **Advantages**: Full control, scriptable, no additional services
- **Components**: gsutil, aws cli, custom orchestration

## Architecture Components

### 1. State Management & Checkpointing

#### Manifest-Based Tracking
```
migration_state:
  - migration_id: uuid
  - pathway: A|B|C|D
  - status: pending|running|paused|completed|failed
  - current_stage: export|transfer|load
  - checkpoint_data:
      - exported_shards: [shard_ids]
      - transferred_shards: [shard_ids]
      - loaded_shards: [shard_ids]
      - failed_shards: [shard_ids]
  - manifest_file: gs://bucket/manifest.json
  - resume_point: stage_name
```

#### Shard Tracking
- Each BigQuery export creates multiple shards (files)
- Track each shard through the pipeline: export → transfer → load
- Enable granular resume from any failed shard
- Maintain shard-level metadata (size, row count, checksum)

### 2. Database Schema

#### migrations_bq_redshift Table
```sql
CREATE TABLE migrations_bq_redshift (
    id SERIAL PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    migration_name VARCHAR(255) NOT NULL,
    pathway VARCHAR(10) NOT NULL CHECK (pathway IN ('A', 'B', 'C', 'D')),
    
    -- Source Configuration
    source_connection_id INTEGER REFERENCES connections(id),
    source_project_id VARCHAR(255),
    source_dataset VARCHAR(255),
    source_tables TEXT[], -- Array of table names
    
    -- Target Configuration
    target_connection_id INTEGER REFERENCES connections(id),
    target_cluster VARCHAR(255),
    target_database VARCHAR(255),
    target_schema VARCHAR(255),
    
    -- Intermediate Storage
    gcs_bucket VARCHAR(255),
    gcs_path VARCHAR(500),
    s3_bucket VARCHAR(255),
    s3_path VARCHAR(500),
    
    -- State Management
    status VARCHAR(50) DEFAULT 'pending',
    current_stage VARCHAR(50),
    checkpoint_data JSONB,
    manifest_uri TEXT,
    resume_point VARCHAR(100),
    
    -- Scheduling
    schedule_type VARCHAR(50), -- one-time, recurring
    cron_expression VARCHAR(100),
    next_run_time TIMESTAMP,
    
    -- Metrics
    total_rows_source BIGINT,
    total_rows_target BIGINT,
    total_bytes_transferred BIGINT,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration_seconds INTEGER,
    
    -- Metadata
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_migration_per_workspace UNIQUE(workspace_id, migration_name)
);

CREATE INDEX idx_migrations_bq_redshift_workspace ON migrations_bq_redshift(workspace_id);
CREATE INDEX idx_migrations_bq_redshift_status ON migrations_bq_redshift(status);
CREATE INDEX idx_migrations_bq_redshift_next_run ON migrations_bq_redshift(next_run_time);
```

#### migration_shards Table
```sql
CREATE TABLE migration_shards (
    id SERIAL PRIMARY KEY,
    migration_id INTEGER NOT NULL REFERENCES migrations_bq_redshift(id) ON DELETE CASCADE,
    shard_index INTEGER NOT NULL,
    table_name VARCHAR(255) NOT NULL,
    
    -- Shard Details
    gcs_uri TEXT,
    s3_uri TEXT,
    file_size_bytes BIGINT,
    row_count BIGINT,
    checksum VARCHAR(64),
    
    -- Status Tracking
    export_status VARCHAR(50) DEFAULT 'pending',
    export_completed_at TIMESTAMP,
    transfer_status VARCHAR(50) DEFAULT 'pending',
    transfer_completed_at TIMESTAMP,
    load_status VARCHAR(50) DEFAULT 'pending',
    load_completed_at TIMESTAMP,
    
    -- Error Handling
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    last_error_time TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_shard_per_migration UNIQUE(migration_id, table_name, shard_index)
);

CREATE INDEX idx_migration_shards_migration ON migration_shards(migration_id);
CREATE INDEX idx_migration_shards_status ON migration_shards(migration_id, export_status, transfer_status, load_status);
```

#### migration_logs Table
```sql
CREATE TABLE migration_logs (
    id SERIAL PRIMARY KEY,
    migration_id INTEGER NOT NULL REFERENCES migrations_bq_redshift(id) ON DELETE CASCADE,
    shard_id INTEGER REFERENCES migration_shards(id),
    
    log_level VARCHAR(20) NOT NULL, -- DEBUG, INFO, WARNING, ERROR, CRITICAL
    stage VARCHAR(50) NOT NULL, -- export, transfer, load
    message TEXT NOT NULL,
    error_code VARCHAR(50),
    stack_trace TEXT,
    metadata JSONB,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_migration_logs_migration ON migration_logs(migration_id);
CREATE INDEX idx_migration_logs_level ON migration_logs(log_level);
CREATE INDEX idx_migration_logs_created ON migration_logs(created_at);
```

### 3. Backend Services

#### Migration Orchestrator Service
**Location**: `backend/services/bq_redshift_migration/`

**Components**:
- `orchestrator.py` - Main orchestration logic
- `pathway_a.py` - GCP Native implementation
- `pathway_b.py` - AWS Native implementation
- `pathway_c.py` - Hybrid Sync implementation
- `pathway_d.py` - CLI/Legacy implementation
- `checkpoint_manager.py` - State management and resume logic
- `manifest_handler.py` - Manifest file parsing and tracking
- `scheduler.py` - CRON-based scheduling
- `metrics_collector.py` - Observability and metrics

#### API Endpoints
```
POST   /api/migrations/bq-redshift/create
GET    /api/migrations/bq-redshift/list
GET    /api/migrations/bq-redshift/{id}
POST   /api/migrations/bq-redshift/{id}/start
POST   /api/migrations/bq-redshift/{id}/pause
POST   /api/migrations/bq-redshift/{id}/resume
POST   /api/migrations/bq-redshift/{id}/cancel
GET    /api/migrations/bq-redshift/{id}/status
GET    /api/migrations/bq-redshift/{id}/logs
GET    /api/migrations/bq-redshift/{id}/metrics
POST   /api/migrations/bq-redshift/{id}/validate
```

### 4. Networking & Security

#### Private Networking Options

**Option 1: VPC Peering (GCP ↔ AWS)**
```hcl
# Terraform configuration
resource "google_compute_network_peering" "gcp_to_aws" {
  name         = "gcp-to-aws-peering"
  network      = google_compute_network.gcp_vpc.id
  peer_network = "projects/${var.aws_project}/global/networks/${var.aws_vpc}"
}
```

**Option 2: Cloud VPN**
```hcl
resource "google_compute_vpn_gateway" "gcp_gateway" {
  name    = "gcp-vpn-gateway"
  network = google_compute_network.gcp_vpc.id
}

resource "aws_vpn_gateway" "aws_gateway" {
  vpc_id = aws_vpc.main.id
}
```

**Option 3: Interconnect/Direct Connect**
- Dedicated physical connection
- Lowest latency, highest bandwidth
- Most expensive option

#### IAM & Authentication

**GCP Service Account**:
```json
{
  "roles": [
    "roles/bigquery.dataViewer",
    "roles/bigquery.jobUser",
    "roles/storage.objectCreator",
    "roles/storage.objectViewer"
  ]
}
```

**AWS IAM Role**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket",
        "redshift:CopyFromS3"
      ],
      "Resource": "*"
    }
  ]
}
```

### 5. Resume Logic Implementation

#### Checkpoint Strategy
```python
class CheckpointManager:
    def save_checkpoint(self, migration_id, stage, data):
        """Save current state to database"""
        checkpoint = {
            'stage': stage,
            'timestamp': datetime.utcnow(),
            'data': data
        }
        # Update migration_bq_redshift.checkpoint_data
        
    def load_checkpoint(self, migration_id):
        """Load last checkpoint"""
        # Retrieve from migration_bq_redshift.checkpoint_data
        
    def get_resume_point(self, migration_id):
        """Determine where to resume"""
        shards = get_shards(migration_id)
        
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
```

#### Manifest File Structure
```json
{
  "migration_id": "uuid",
  "source": {
    "project": "my-project",
    "dataset": "my_dataset",
    "tables": ["table1", "table2"]
  },
  "shards": [
    {
      "shard_id": "shard_001",
      "table": "table1",
      "gcs_uri": "gs://bucket/path/shard_001.avro",
      "s3_uri": "s3://bucket/path/shard_001.avro",
      "size_bytes": 1073741824,
      "row_count": 1000000,
      "checksum": "sha256:abc123...",
      "status": {
        "exported": true,
        "transferred": true,
        "loaded": false
      }
    }
  ],
  "metadata": {
    "created_at": "2026-02-08T12:00:00Z",
    "updated_at": "2026-02-08T14:30:00Z"
  }
}
```

### 6. Scheduling System

#### CRON-Based Scheduler
```python
class MigrationScheduler:
    def schedule_migration(self, migration_id, cron_expression):
        """Schedule recurring migration"""
        # Parse CRON expression
        # Calculate next run time
        # Store in database
        
    def check_due_migrations(self):
        """Check for migrations due to run"""
        now = datetime.utcnow()
        due_migrations = query(
            "SELECT * FROM migrations_bq_redshift "
            "WHERE schedule_type = 'recurring' "
            "AND next_run_time <= %s "
            "AND status NOT IN ('running', 'paused')",
            [now]
        )
        return due_migrations
        
    def execute_scheduled_migration(self, migration_id):
        """Execute a scheduled migration"""
        # Start migration
        # Update next_run_time based on CRON
```

#### Airflow Integration (Optional)
```python
from airflow import DAG
from airflow.operators.python import PythonOperator

def trigger_bq_redshift_migration(**context):
    migration_id = context['dag_run'].conf.get('migration_id')
    # Call migration API
    
dag = DAG(
    'bq_redshift_migration',
    schedule_interval='@daily',
    default_args={'owner': 'datamiq'}
)

migrate_task = PythonOperator(
    task_id='migrate',
    python_callable=trigger_bq_redshift_migration,
    dag=dag
)
```

### 7. Observability & Metrics

#### Metrics Collection
```python
class MetricsCollector:
    def collect_source_metrics(self, migration_id):
        """Collect BigQuery source metrics"""
        # Query BigQuery for row counts
        # Calculate data size
        # Store in migration_bq_redshift
        
    def collect_transfer_metrics(self, migration_id):
        """Collect transfer metrics"""
        # Track bytes transferred
        # Calculate transfer rate
        # Monitor latency
        
    def collect_target_metrics(self, migration_id):
        """Collect Redshift target metrics"""
        # Query Redshift for row counts
        # Validate data integrity
        # Compare with source
        
    def calculate_data_drift(self, migration_id):
        """Calculate source vs sink differences"""
        source_count = self.get_source_row_count(migration_id)
        target_count = self.get_target_row_count(migration_id)
        drift = abs(source_count - target_count)
        drift_percentage = (drift / source_count) * 100
        return {
            'source_rows': source_count,
            'target_rows': target_count,
            'drift': drift,
            'drift_percentage': drift_percentage
        }
```

#### Logging Standards
```python
import logging

logger = logging.getLogger('bq_redshift_migration')

# Log levels:
# DEBUG: Detailed shard-level operations
# INFO: Stage transitions, progress updates
# WARNING: Retryable errors, performance issues
# ERROR: Failed operations, data inconsistencies
# CRITICAL: Migration failure, data loss risk

logger.info(
    f"Migration {migration_id}: Exported shard {shard_id} "
    f"({row_count} rows, {size_mb}MB) to {gcs_uri}"
)

logger.error(
    f"Migration {migration_id}: Failed to transfer shard {shard_id} "
    f"from {gcs_uri} to {s3_uri}. Error: {error_code} - {error_message}",
    extra={
        'migration_id': migration_id,
        'shard_id': shard_id,
        'error_code': error_code,
        'retry_count': retry_count
    }
)
```

### 8. Error Handling & Retry Logic

#### Retry Strategy
```python
class RetryHandler:
    MAX_RETRIES = 3
    BACKOFF_MULTIPLIER = 2
    
    def retry_with_backoff(self, func, *args, **kwargs):
        """Exponential backoff retry"""
        for attempt in range(self.MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == self.MAX_RETRIES - 1:
                    raise
                wait_time = self.BACKOFF_MULTIPLIER ** attempt
                logger.warning(
                    f"Attempt {attempt + 1} failed: {e}. "
                    f"Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)
```

## Implementation Status

### Phase 1: Core Infrastructure ✅ COMPLETE
- [x] Database schema creation (migration 003)
- [x] Database models (MigrationBQRedshift, MigrationShard, MigrationLog)
- [x] Basic service structure
- [x] Checkpoint manager skeleton
- [x] Manifest handler skeleton

### Phase 2: Create Migration Workflow 🚧 IN PROGRESS
- [x] Step 1: Connection & Staging Configuration UI
- [x] Step 2: Source Metadata Discovery (Object Picker)
- [x] Step 3: Migration Strategy Selection
- [x] Step 4: Scheduling & Monitoring Setup
- [ ] Backend API implementation
- [ ] BigQuery metadata discovery
- [ ] Path A: Full implementation (BQ→GCS→S3→Redshift)

### Phase 3: Migration Execution
- [ ] Export from BigQuery to GCS
- [ ] Transfer from GCS to S3
- [ ] Load from S3 to Redshift
- [ ] Checkpoint and resume logic
- [ ] Error handling and retry

### Phase 4: Advanced Features
- [ ] Scheduling system (CRON-based)
- [ ] Real-time progress monitoring
- [ ] Advanced metrics and observability
- [ ] Validation and data integrity checks

### Phase 5: Additional Pathways
- [ ] Path B: AWS SCT integration
- [ ] Path C: AWS DataSync integration
- [ ] Path D: CLI orchestration

### Phase 6: Production Hardening
- [ ] Comprehensive error handling
- [ ] Performance optimization
- [ ] Security audit
- [ ] Load testing
- [ ] Documentation completion

## Technology Stack

**Backend**:
- Python 3.11+
- FastAPI
- SQLAlchemy
- Google Cloud SDK
- AWS SDK (boto3)
- Celery (for async tasks)

**Infrastructure**:
- Terraform (IaC)
- Docker
- Kubernetes (optional)

**Monitoring**:
- CloudWatch (AWS)
- Cloud Logging (GCP)
- Prometheus + Grafana (optional)

## Security Considerations

1. **Credentials Management**: Use AWS Secrets Manager / GCP Secret Manager
2. **Encryption**: Enable encryption at rest and in transit
3. **Network Isolation**: Use private networking, no public internet
4. **Audit Logging**: Log all operations for compliance
5. **Access Control**: Implement RBAC for migration operations
6. **Data Validation**: Checksum verification at each stage

## Performance Optimization

1. **Parallel Processing**: Process multiple shards concurrently
2. **Compression**: Use GZIP/Snappy for data transfer
3. **Batch Loading**: Use Redshift COPY with manifest files
4. **Connection Pooling**: Reuse database connections
5. **Caching**: Cache metadata and configuration

## Next Steps

1. Review and approve architecture
2. Set up development environment
3. Create database migrations
4. Implement Path A (GCP Native) as proof of concept
5. Build UI components for migration management
6. Conduct load testing with sample datasets
