"""
BigQuery to Redshift Migration API Router

REST API endpoints for managing BQ to Redshift migrations.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from database import get_db
from repositories.bq_redshift_migration_repository import BQRedshiftMigrationRepository
from services.bq_redshift_migration.orchestrator import MigrationOrchestrator
from shared.middleware.auth_middleware import get_current_user
from models.connection import Connection
from models.bq_redshift_migration import MigrationBQRedshift, MigrationLog
from services.aws_secrets import AWSSecretsService
from services.encryption_service import get_encryption_service

router = APIRouter(prefix="/api/migrations/bq-redshift", tags=["BQ-Redshift Migrations"])


# Helper function to get workspace_id from user or header
def get_workspace_id(
    request: Request,
    current_user = Depends(get_current_user)
) -> int:
    """Get workspace ID from request header or use default workspace"""
    # Try to get from header
    workspace_id = request.headers.get("X-Workspace-ID")
    if workspace_id:
        return int(workspace_id)
    
    # Default to workspace 1 for now (should be from user's default workspace)
    return 1


# Pydantic Models
class CreateMigrationRequest(BaseModel):
    """
    Create migration request - allows partial creation for stage-by-stage workflow.
    Only migration_name, pathway, and connection IDs are truly required.
    Other fields can be added later via updates.
    """
    migration_name: str = Field(..., min_length=1, max_length=255)
    pathway: str = Field(..., pattern="^[ABCD]$")
    
    # Source Configuration (connection_id required, others optional)
    source_connection_id: int
    source_project_id: Optional[str] = None
    source_dataset: Optional[str] = None
    source_tables: Optional[List[str]] = None
    
    # Target Configuration (connection_id required, others optional)
    target_connection_id: int
    target_cluster: Optional[str] = None
    target_database: Optional[str] = None
    target_schema: Optional[str] = "public"
    
    # Storage Configuration (optional - can be added in stages)
    gcs_bucket: Optional[str] = None
    gcs_path: Optional[str] = None
    s3_bucket: Optional[str] = None
    s3_path: Optional[str] = None
    
    # Export Configuration (optional with defaults)
    export_format: Optional[str] = "AVRO"  # AVRO, PARQUET, CSV, JSON
    compression: Optional[str] = "NONE"    # NONE, GZIP, SNAPPY, DEFLATE, ZSTD
    
    # AWS Credentials for GCS → S3 Transfer (Path A & C)
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    overwrite_existing_files: Optional[bool] = False
    delete_source_after_transfer: Optional[bool] = False
    
    # Redshift S3 Access (Required for COPY command)
    iam_role_arn: Optional[str] = None
    
    # Scheduling (optional)
    schedule_type: Optional[str] = None
    cron_expression: Optional[str] = None


class UpdateMigrationRequest(BaseModel):
    """
    Update migration request - all fields optional except those that cannot be changed.
    This allows partial updates (e.g., updating just Stage 2 configuration).
    """
    migration_name: Optional[str] = Field(None, min_length=1, max_length=255)
    pathway: Optional[str] = Field(None, pattern="^[ABC]$")
    
    # Source Configuration (optional for updates)
    source_connection_id: Optional[int] = None
    source_project_id: Optional[str] = None
    source_dataset: Optional[str] = None
    source_tables: Optional[List[str]] = None
    
    # Target Configuration (optional for updates)
    target_connection_id: Optional[int] = None
    target_cluster: Optional[str] = None
    target_database: Optional[str] = None
    target_schema: Optional[str] = None
    
    # Storage Configuration (optional for updates)
    gcs_bucket: Optional[str] = None
    gcs_path: Optional[str] = None
    s3_bucket: Optional[str] = None
    s3_path: Optional[str] = None
    
    # Export Configuration (optional for updates)
    export_format: Optional[str] = None
    compression: Optional[str] = None
    
    # AWS Credentials for GCS → S3 Transfer (Path A & C)
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    overwrite_existing_files: Optional[bool] = None
    delete_source_after_transfer: Optional[bool] = None
    
    # Redshift S3 Access (Required for COPY command)
    iam_role_arn: Optional[str] = None
    
    # Scheduling (optional)
    schedule_type: Optional[str] = None
    cron_expression: Optional[str] = None


class MigrationResponse(BaseModel):
    id: int
    workspace_id: int
    migration_name: str
    pathway: str
    status: str
    current_stage: Optional[str]
    source_connection_name: Optional[str] = None
    target_connection_name: Optional[str] = None
    start_time: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class MigrationDetailResponse(BaseModel):
    id: int
    workspace_id: int
    migration_name: str
    pathway: str
    status: str
    current_stage: Optional[str]
    source: dict
    target: dict
    storage: dict
    state: dict
    schedule: dict
    metrics: dict
    created_at: datetime
    updated_at: datetime


class MigrationStatusResponse(BaseModel):
    migration_id: int
    status: str
    current_stage: Optional[str]
    pathway: str
    progress: dict
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    duration_seconds: Optional[int]
    metrics: dict


class ValidationResponse(BaseModel):
    migration_id: int
    valid: bool
    validated_at: str
    tables: dict


class MetadataDiscoveryRequest(BaseModel):
    connection_id: int
    project_id: Optional[str] = None


class DatasetMetadata(BaseModel):
    dataset_id: str
    location: str
    description: Optional[str] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    table_count: int


class TableMetadata(BaseModel):
    table_id: str
    dataset_id: str
    table_type: str  # TABLE, VIEW, EXTERNAL
    num_rows: Optional[int] = None
    size_bytes: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    description: Optional[str] = None


class MetadataDiscoveryResponse(BaseModel):
    connection_id: int
    project_id: str
    datasets: List[DatasetMetadata]
    tables: dict  # dataset_id -> List[TableMetadata]


# Endpoints
@router.post("/discover-metadata", response_model=MetadataDiscoveryResponse)
async def discover_metadata(
    request: Request,
    req: MetadataDiscoveryRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """
    Discover BigQuery metadata (datasets and tables) for the given connection.
    
    This endpoint connects to BigQuery and retrieves:
    - All datasets in the project
    - All tables within each dataset
    - Metadata for each table (row count, size, etc.)
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"=== BigQuery Metadata Discovery Started ===")
    logger.info(f"Connection ID: {req.connection_id}, Project ID: {req.project_id}")
    logger.info(f"User: {current_user.user_id}, Workspace: {workspace_id}")
    
    try:
        # Get connection details
        logger.info(f"Fetching connection from database...")
        connection = db.query(Connection).filter(
            Connection.id == req.connection_id
        ).first()
        
        if not connection:
            logger.error(f"Connection {req.connection_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection {req.connection_id} not found"
            )
        
        logger.info(f"Connection found: {connection.name} (database: {connection.database})")
        
        if connection.database.lower() != 'bigquery':
            logger.error(f"Invalid database type: {connection.database}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Connection must be BigQuery type, got {connection.database}"
            )
        
        logger.info("Connection validated as BigQuery type")
        
        # Import BigQuery client
        logger.info("Importing BigQuery libraries...")
        try:
            from google.cloud import bigquery
            from google.oauth2 import service_account
            import json
            logger.info("✓ BigQuery libraries imported successfully")
        except ImportError as e:
            logger.error(f"BigQuery library import failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="BigQuery client library not installed. Install google-cloud-bigquery."
            )
        
        # Parse credentials from connection_params
        logger.info("Parsing connection credentials...")
        try:
            connection_params = connection.connection_params or {}
            logger.info(f"Connection params keys: {list(connection_params.keys())}")
            
            # Get service account key from connection params
            service_account_key = (
                connection_params.get('service_account_key') or 
                connection_params.get('serviceAccountKey') or
                connection_params.get('credentials_json') or
                connection_params.get('credentialsJson')
            )
            
            if not service_account_key:
                logger.error("Service Account Key not found in connection params")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Service Account Key is required for BigQuery connection"
                )
            
            logger.info("✓ Service account key found")
            
            # Parse service account JSON
            if isinstance(service_account_key, str):
                credentials_dict = json.loads(service_account_key)
            else:
                credentials_dict = service_account_key
            
            logger.info(f"✓ Credentials parsed, project_id from creds: {credentials_dict.get('project_id')}")
            
            # Get project ID
            project_id = (
                req.project_id or 
                connection_params.get('project_id') or 
                connection_params.get('projectId') or
                credentials_dict.get('project_id')
            )
            
            if not project_id:
                logger.error("Project ID not found")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Project ID is required"
                )
            
            logger.info(f"✓ Project ID: {project_id}")
            
            # Create credentials
            logger.info("Creating BigQuery credentials...")
            credentials = service_account.Credentials.from_service_account_info(credentials_dict)
            logger.info("✓ Credentials created")
            
            # Create BigQuery client
            region = connection_params.get('region') or connection_params.get('location', 'us-central1')
            logger.info(f"Creating BigQuery client (region: {region})...")
            client = bigquery.Client(
                credentials=credentials,
                project=project_id,
                location=region
            )
            logger.info("✓ BigQuery client created successfully")
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid BigQuery credentials format: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize BigQuery client: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize BigQuery client: {str(e)}"
            )
        
        # Discover datasets
        logger.info("Discovering datasets...")
        datasets_metadata = []
        tables_by_dataset = {}
        
        try:
            datasets = list(client.list_datasets())
            logger.info(f"✓ Found {len(datasets)} datasets")
            
            for dataset_ref in datasets:
                logger.info(f"Processing dataset: {dataset_ref.dataset_id}")
                dataset = client.get_dataset(dataset_ref.dataset_id)
                
                # Get tables in dataset
                tables = list(client.list_tables(dataset.dataset_id))
                logger.info(f"  - Found {len(tables)} tables")
                
                dataset_meta = DatasetMetadata(
                    dataset_id=dataset.dataset_id,
                    location=dataset.location,
                    description=dataset.description,
                    created=dataset.created.isoformat() if dataset.created else None,
                    modified=dataset.modified.isoformat() if dataset.modified else None,
                    table_count=len(tables)
                )
                datasets_metadata.append(dataset_meta)
                
                # Get table metadata
                table_metadata_list = []
                for table_ref in tables:
                    try:
                        table = client.get_table(table_ref)
                        
                        table_meta = TableMetadata(
                            table_id=table.table_id,
                            dataset_id=dataset.dataset_id,
                            table_type=table.table_type,
                            num_rows=table.num_rows,
                            size_bytes=table.num_bytes,
                            created=table.created.isoformat() if table.created else None,
                            modified=table.modified.isoformat() if table.modified else None,
                            description=table.description
                        )
                        table_metadata_list.append(table_meta)
                        logger.info(f"    • {table.table_id}: {table.num_rows:,} rows, {table.num_bytes:,} bytes")
                    except Exception as e:
                        # Log error but continue with other tables
                        logger.warning(f"Error getting metadata for table {table_ref.table_id}: {str(e)}")
                        continue
                
                tables_by_dataset[dataset.dataset_id] = table_metadata_list
            
            logger.info(f"=== Metadata Discovery Complete: {len(datasets_metadata)} datasets, {sum(len(t) for t in tables_by_dataset.values())} tables ===")
            
            return MetadataDiscoveryResponse(
                connection_id=req.connection_id,
                project_id=project_id,
                datasets=datasets_metadata,
                tables=tables_by_dataset
            )
            
        except Exception as e:
            logger.error(f"Failed to discover BigQuery metadata: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to discover BigQuery metadata: {str(e)}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during metadata discovery: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during metadata discovery: {str(e)}"
        )


@router.post("/create", response_model=MigrationResponse, status_code=status.HTTP_201_CREATED)
async def create_migration(
    request: Request,
    req: CreateMigrationRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """
    Create a new BigQuery to Redshift migration.
    
    Supports three pathways:
    - A: AWS Native (BigQuery → AWS DMS → Redshift)
    - B: AWS DataSync (BigQuery → GCS → AWS DataSync → S3 → Redshift)
    - C: CLI/Legacy (BigQuery → GCS → gsutil/aws cli → S3 → Redshift)
    
    Note: Allows partial creation for stage-by-stage workflow.
    Only migration_name, pathway, and connection IDs are required initially.
    Other fields can be added later via updates.
    """
    try:
        repo = BQRedshiftMigrationRepository(db)
        
        # Check for duplicate name
        existing = repo.get_migrations_by_workspace(workspace_id)
        if any(m.migration_name == req.migration_name for m in existing):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Migration with name '{req.migration_name}' already exists"
            )
        
        # Encrypt AWS secret key if provided
        aws_secret_encrypted = None
        if req.aws_secret_access_key:
            encryption_service = get_encryption_service()
            aws_secret_encrypted = encryption_service.encrypt(req.aws_secret_access_key)
        
        # Create migration with provided fields (handle empty strings and None)
        migration_data = {
            'workspace_id': workspace_id,
            'migration_name': req.migration_name,
            'pathway': req.pathway,
            'source_connection_id': req.source_connection_id,
            'source_project_id': req.source_project_id or '',
            'source_dataset': req.source_dataset or '',
            'source_tables': req.source_tables or [],
            'target_connection_id': req.target_connection_id,
            'target_cluster': req.target_cluster or '',
            'target_database': req.target_database or '',
            'target_schema': req.target_schema or 'public',
            'gcs_bucket': req.gcs_bucket or '',
            'gcs_path': req.gcs_path or '',
            's3_bucket': req.s3_bucket or '',
            's3_path': req.s3_path or '',
            'export_format': req.export_format or 'AVRO',
            'compression': req.compression or 'NONE',
            # AWS credentials for GCS → S3 transfer
            'aws_access_key_id': req.aws_access_key_id or '',
            'aws_secret_access_key_encrypted': aws_secret_encrypted or '',  # Encrypted
            'overwrite_existing_files': 'true' if req.overwrite_existing_files else 'false',
            'delete_source_after_transfer': 'true' if req.delete_source_after_transfer else 'false',
            # Redshift S3 access
            'iam_role_arn': req.iam_role_arn or '',
            'schedule_type': req.schedule_type,
            'cron_expression': req.cron_expression,
            'created_by': current_user.user_id,
            'status': 'pending'
        }
        
        migration = repo.create_migration(migration_data)
        
        return MigrationResponse(
            id=migration.id,
            workspace_id=migration.workspace_id,
            migration_name=migration.migration_name,
            pathway=migration.pathway,
            status=migration.status,
            current_stage=migration.current_stage,
            created_at=migration.created_at,
            updated_at=migration.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create migration: {str(e)}"
        )


@router.get("/list", response_model=List[MigrationResponse])
async def list_migrations(
    request: Request,
    status_filter: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """List all migrations for the current workspace"""
    try:
        repo = BQRedshiftMigrationRepository(db)
        
        # Get all migrations (workspace filtering not implemented yet)
        query = db.query(MigrationBQRedshift)
        
        if status_filter:
            query = query.filter(MigrationBQRedshift.status == status_filter)
        
        migrations = query.order_by(MigrationBQRedshift.created_at.desc()).limit(limit).offset(offset).all()
        
        # Get connection names for all migrations
        result = []
        for m in migrations:
            # Get source connection name
            source_conn_name = "Unknown"
            if m.source_connection_id:
                source_conn = db.query(Connection).filter(Connection.id == m.source_connection_id).first()
                if source_conn:
                    source_conn_name = source_conn.name
            
            # Get target connection name
            target_conn_name = "Unknown"
            if m.target_connection_id:
                target_conn = db.query(Connection).filter(Connection.id == m.target_connection_id).first()
                if target_conn:
                    target_conn_name = target_conn.name
            
            result.append(MigrationResponse(
                id=m.id,
                workspace_id=1,  # Hardcoded until workspace support is added
                migration_name=m.migration_name,
                pathway=m.pathway,
                status=m.status,
                current_stage=m.current_stage,
                source_connection_name=source_conn_name,
                target_connection_name=target_conn_name,
                start_time=m.start_time,
                last_run_at=m.last_run_at,
                created_at=m.created_at,
                updated_at=m.updated_at
            ))
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list migrations: {str(e)}"
        )


@router.get("/{migration_id}", response_model=MigrationDetailResponse)
async def get_migration(
    request: Request,
    migration_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """Get detailed information about a migration"""
    try:
        repo = BQRedshiftMigrationRepository(db)
        migration = repo.get_migration_by_id(migration_id)
        
        if not migration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Migration {migration_id} not found"
            )
        
        if migration.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Convert to dict format expected by MigrationDetailResponse
        migration_dict = migration.to_dict()
        
        # Flatten the nested structure for the response model
        response_data = {
            'id': migration_dict['id'],
            'workspace_id': migration_dict['workspace_id'],
            'migration_name': migration_dict['migration_name'],
            'pathway': migration_dict['pathway'],
            'status': migration_dict['state']['status'],
            'current_stage': migration_dict['state']['current_stage'],
            'source': migration_dict['source'],
            'target': migration_dict['target'],
            'storage': migration_dict['storage'],
            'state': migration_dict['state'],
            'schedule': migration_dict['schedule'],
            'metrics': migration_dict['metrics'],
            'created_at': migration_dict['created_at'],
            'updated_at': migration_dict['updated_at']
        }
        
        return MigrationDetailResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get migration: {str(e)}"
        )


@router.post("/{migration_id}/start")
async def start_migration(
    request: Request,
    migration_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """Start a migration (runs in background)"""
    import threading
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        repo = BQRedshiftMigrationRepository(db)
        migration = repo.get_migration_by_id(migration_id)
        
        if not migration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Migration {migration_id} not found"
            )
        
        if migration.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        if migration.status == 'running':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Migration is already running"
            )
        
        # DON'T set status to running here - let orchestrator do it
        # This was causing the orchestrator to refuse to run the migration
        
        logger.info(f"Starting migration {migration_id} in background thread")
        
        # Start migration in background thread with comprehensive error handling
        def run_migration():
            from database import db_instance
            import sys
            import traceback
            
            bg_db = db_instance.SessionLocal()
            
            # Configure logger for background thread
            bg_logger = logging.getLogger(f"migration_{migration_id}")
            bg_logger.setLevel(logging.INFO)
            
            # Add handler if not already present
            if not bg_logger.handlers:
                handler = logging.StreamHandler(sys.stdout)
                handler.setFormatter(logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                ))
                bg_logger.addHandler(handler)
            
            try:
                bg_logger.info(f"=== Background thread started for migration {migration_id} ===")
                
                # Create initial log entry
                initial_log = MigrationLog(
                    migration_id=migration_id,
                    log_level='INFO',
                    stage='init',
                    message='Migration thread started - beginning execution',
                    created_at=datetime.utcnow()
                )
                bg_db.add(initial_log)
                bg_db.commit()
                bg_logger.info("✓ Initial log entry created")
                
                # Execute migration with detailed error tracking
                try:
                    orchestrator = MigrationOrchestrator(bg_db)
                    bg_logger.info("✓ Orchestrator initialized")
                    
                    success = orchestrator.start_migration(migration_id)
                    bg_logger.info(f"Migration {migration_id} completed: success={success}")
                    
                except Exception as orch_error:
                    bg_logger.error(f"Orchestrator execution failed: {orch_error}", exc_info=True)
                    
                    # Log the error to database
                    error_log = MigrationLog(
                        migration_id=migration_id,
                        log_level='CRITICAL',
                        stage='orchestrator',
                        message=f'Orchestrator failed: {str(orch_error)}',
                        stack_trace=str(orch_error),
                        created_at=datetime.utcnow()
                    )
                    bg_db.add(error_log)
                    bg_db.commit()
                    
                    # Update migration status to failed
                    failed_migration = bg_db.query(MigrationBQRedshift).filter_by(id=migration_id).first()
                    if failed_migration:
                        failed_migration.status = 'failed'
                        failed_migration.end_time = datetime.utcnow()
                        failed_migration.updated_at = datetime.utcnow()
                        bg_db.commit()
                    
                    raise
                
            except Exception as e:
                bg_logger.error(f"CRITICAL ERROR in migration thread: {e}", exc_info=True)
                
                # ALWAYS log to database even if logger fails
                try:
                    import traceback
                    failed_migration = bg_db.query(MigrationBQRedshift).filter_by(id=migration_id).first()
                    if failed_migration:
                        failed_migration.status = 'failed'
                        failed_migration.end_time = datetime.utcnow()
                        failed_migration.updated_at = datetime.utcnow()
                        
                        # Create error log
                        error_log = MigrationLog(
                            migration_id=migration_id,
                            log_level='CRITICAL',
                            stage='thread',
                            message=f'Background thread failed: {str(e)}',
                            stack_trace=traceback.format_exc(),
                            created_at=datetime.utcnow()
                        )
                        bg_db.add(error_log)
                        bg_db.commit()
                        bg_logger.info("✓ Error logged and migration marked as failed")
                except Exception as log_error:
                    bg_logger.error(f"Failed to log error: {log_error}")
                    # Print to console as last resort
                    print(f"CRITICAL: Migration {migration_id} failed: {e}")
                    print(f"Failed to log error to database: {log_error}")
                    
            finally:
                bg_db.close()
                bg_logger.info(f"=== Background thread completed for migration {migration_id} ===")
        
        thread = threading.Thread(target=run_migration, daemon=True)
        thread.start()
        logger.info(f"✓ Background thread started for migration {migration_id}")
        
        return {
            "message": "Migration started successfully in background",
            "migration_id": migration_id,
            "status": "running"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start migration: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start migration: {str(e)}"
        )


@router.post("/{migration_id}/pause")
async def pause_migration(
    request: Request,
    migration_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """Pause a running migration"""
    try:
        repo = BQRedshiftMigrationRepository(db)
        migration = repo.get_migration_by_id(migration_id)
        
        if not migration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Migration {migration_id} not found"
            )
        
        if migration.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        orchestrator = MigrationOrchestrator(db)
        success = orchestrator.pause_migration(migration_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Migration cannot be paused"
            )
        
        return {"message": "Migration paused successfully", "migration_id": migration_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to pause migration: {str(e)}"
        )


@router.post("/{migration_id}/resume")
async def resume_migration(
    request: Request,
    migration_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """Resume a paused or failed migration"""
    try:
        repo = BQRedshiftMigrationRepository(db)
        migration = repo.get_migration_by_id(migration_id)
        
        if not migration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Migration {migration_id} not found"
            )
        
        if migration.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        orchestrator = MigrationOrchestrator(db)
        success = orchestrator.resume_migration(migration_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Migration cannot be resumed"
            )
        
        return {"message": "Migration resumed successfully", "migration_id": migration_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resume migration: {str(e)}"
        )


@router.post("/{migration_id}/cancel")
async def cancel_migration(
    request: Request,
    migration_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """Cancel a running or paused migration"""
    try:
        repo = BQRedshiftMigrationRepository(db)
        migration = repo.get_migration_by_id(migration_id)
        
        if not migration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Migration {migration_id} not found"
            )
        
        if migration.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        orchestrator = MigrationOrchestrator(db)
        success = orchestrator.cancel_migration(migration_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Migration cannot be cancelled"
            )
        
        return {"message": "Migration cancelled successfully", "migration_id": migration_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel migration: {str(e)}"
        )


@router.get("/{migration_id}/status", response_model=MigrationStatusResponse)
async def get_migration_status(
    request: Request,
    migration_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """Get current migration status with progress"""
    try:
        repo = BQRedshiftMigrationRepository(db)
        migration = repo.get_migration_by_id(migration_id)
        
        if not migration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Migration {migration_id} not found"
            )
        
        if migration.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        orchestrator = MigrationOrchestrator(db)
        status_data = orchestrator.get_migration_status(migration_id)
        
        if not status_data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get migration status"
            )
        
        return MigrationStatusResponse(**status_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get migration status: {str(e)}"
        )


@router.get("/{migration_id}/logs")
async def get_migration_logs(
    request: Request,
    migration_id: int,
    level: Optional[str] = None,
    limit: int = 1000,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """Get migration logs"""
    try:
        repo = BQRedshiftMigrationRepository(db)
        migration = repo.get_migration_by_id(migration_id)
        
        if not migration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Migration {migration_id} not found"
            )
        
        if migration.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        logs = repo.get_logs_by_migration(migration_id, level=level, limit=limit)
        
        return {
            "migration_id": migration_id,
            "total_logs": len(logs),
            "logs": [log.to_dict() for log in logs]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get migration logs: {str(e)}"
        )


@router.get("/{migration_id}/metrics")
async def get_migration_metrics(
    request: Request,
    migration_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """Get migration metrics and statistics"""
    try:
        repo = BQRedshiftMigrationRepository(db)
        migration = repo.get_migration_by_id(migration_id)
        
        if not migration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Migration {migration_id} not found"
            )
        
        if migration.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        shards = repo.get_shards_by_migration(migration_id)
        
        return {
            "migration_id": migration_id,
            "total_shards": len(shards),
            "completed_shards": sum(1 for s in shards if s.is_completed()),
            "failed_shards": sum(1 for s in shards if s.has_failed()),
            "total_rows_source": migration.total_rows_source,
            "total_rows_target": migration.total_rows_target,
            "total_bytes_transferred": migration.total_bytes_transferred,
            "duration_seconds": migration.duration_seconds,
            "shards": [shard.to_dict() for shard in shards]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get migration metrics: {str(e)}"
        )


@router.post("/{migration_id}/validate", response_model=ValidationResponse)
async def validate_migration(
    request: Request,
    migration_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """Validate migration data integrity"""
    try:
        repo = BQRedshiftMigrationRepository(db)
        migration = repo.get_migration_by_id(migration_id)
        
        if not migration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Migration {migration_id} not found"
            )
        
        if migration.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        orchestrator = MigrationOrchestrator(db)
        results = orchestrator.validate_migration(migration_id)
        
        if not results:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to validate migration"
            )
        
        return ValidationResponse(**results)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to validate migration: {str(e)}"
        )


@router.post("/{migration_id}/restart")
async def restart_migration(
    request: Request,
    migration_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """
    Restart a migration from the beginning.
    
    This resets the migration to 'pending' status and clears all progress data,
    allowing it to be run again from scratch.
    """
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        repo = BQRedshiftMigrationRepository(db)
        migration = repo.get_migration_by_id(migration_id)
        
        if not migration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Migration {migration_id} not found"
            )
        
        if migration.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        if migration.status == 'running':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot restart a running migration. Please cancel it first."
            )
        
        logger.info(f"Restarting migration {migration_id} - resetting to pending status")
        
        # Reset migration to pending status
        migration.status = 'pending'
        migration.current_stage = None
        migration.start_time = None
        migration.end_time = None
        migration.duration_seconds = None
        migration.progress_percentage = 0
        migration.checkpoint_data = {}
        migration.updated_at = datetime.utcnow()
        
        db.commit()
        
        logger.info(f"✓ Migration {migration_id} reset to pending status")
        
        return {
            "message": "Migration restarted successfully. It has been reset to pending status.",
            "migration_id": migration_id,
            "status": "pending"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to restart migration: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restart migration: {str(e)}"
        )


@router.put("/{migration_id}/update", response_model=MigrationResponse)
async def update_migration(
    request: Request,
    migration_id: int,
    req: UpdateMigrationRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """
    Update an existing migration.
    
    Note: Connection IDs cannot be changed after creation.
    Only configuration, tables, and scheduling can be updated.
    All fields are optional - only provided fields will be updated.
    """
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        repo = BQRedshiftMigrationRepository(db)
        migration = repo.get_migration_by_id(migration_id)
        
        if not migration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Migration {migration_id} not found"
            )
        
        if migration.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Prevent editing running migrations
        if migration.status == 'running':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update a running migration. Please pause or cancel it first."
            )
        
        logger.info(f"Updating migration {migration_id}")
        
        # Check for duplicate name (excluding current migration)
        if req.migration_name:
            existing = repo.get_migrations_by_workspace(workspace_id)
            if any(m.migration_name == req.migration_name and m.id != migration_id for m in existing):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Migration with name '{req.migration_name}' already exists"
                )
        
        # Encrypt AWS secret key if provided
        aws_secret_encrypted = None
        if req.aws_secret_access_key:
            encryption_service = get_encryption_service()
            aws_secret_encrypted = encryption_service.encrypt(req.aws_secret_access_key)
        
        # Update only provided fields
        if req.migration_name is not None:
            migration.migration_name = req.migration_name
        if req.pathway is not None:
            migration.pathway = req.pathway
        if req.source_project_id is not None:
            migration.source_project_id = req.source_project_id
        if req.source_dataset is not None:
            migration.source_dataset = req.source_dataset
        if req.source_tables is not None:
            migration.source_tables = req.source_tables
        if req.target_cluster is not None:
            migration.target_cluster = req.target_cluster
        if req.target_database is not None:
            migration.target_database = req.target_database
        if req.target_schema is not None:
            migration.target_schema = req.target_schema
        if req.gcs_bucket is not None:
            migration.gcs_bucket = req.gcs_bucket
        if req.gcs_path is not None:
            migration.gcs_path = req.gcs_path
        if req.s3_bucket is not None:
            migration.s3_bucket = req.s3_bucket
        if req.s3_path is not None:
            migration.s3_path = req.s3_path
        if req.export_format is not None:
            migration.export_format = req.export_format
        if req.compression is not None:
            migration.compression = req.compression
        
        # Update AWS credentials if provided
        if req.aws_access_key_id is not None:
            migration.aws_access_key_id = req.aws_access_key_id
        if aws_secret_encrypted is not None:
            migration.aws_secret_access_key_encrypted = aws_secret_encrypted
        
        # Update IAM role ARN
        if req.iam_role_arn is not None:
            migration.iam_role_arn = req.iam_role_arn
        
        # Update boolean flags
        if req.overwrite_existing_files is not None:
            migration.overwrite_existing_files = 'true' if req.overwrite_existing_files else 'false'
        if req.delete_source_after_transfer is not None:
            migration.delete_source_after_transfer = 'true' if req.delete_source_after_transfer else 'false'
        
        # Update scheduling
        if req.schedule_type is not None:
            migration.schedule_type = req.schedule_type
        if req.cron_expression is not None:
            migration.cron_expression = req.cron_expression
        
        migration.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(migration)
        
        logger.info(f"✓ Migration {migration_id} updated successfully")
        
        return MigrationResponse(
            id=migration.id,
            workspace_id=migration.workspace_id,
            migration_name=migration.migration_name,
            pathway=migration.pathway,
            status=migration.status,
            current_stage=migration.current_stage,
            created_at=migration.created_at,
            updated_at=migration.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update migration: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update migration: {str(e)}"
        )


@router.delete("/{migration_id}")
async def delete_migration(
    request: Request,
    migration_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """Delete a migration"""
    try:
        repo = BQRedshiftMigrationRepository(db)
        migration = repo.get_migration_by_id(migration_id)
        
        if not migration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Migration {migration_id} not found"
            )
        
        # Workspace filtering not implemented yet - allow deletion for all users
        
        if migration.status == 'running':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete a running migration"
            )
        
        success = repo.delete_migration(migration_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete migration"
            )
        
        return {"message": "Migration deleted successfully", "migration_id": migration_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete migration: {str(e)}"
        )
