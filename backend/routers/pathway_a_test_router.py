"""
Pathway A Testing Router
Test endpoints for each step of BigQuery → GCS → S3 → Redshift migration
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from datetime import datetime
import logging

from database import get_db
from shared.middleware.auth_middleware import get_current_user
from models.connection import Connection

router = APIRouter(prefix="/api/migrations/pathway-a/test", tags=["Pathway A Testing"])
logger = logging.getLogger(__name__)


# Request Models
class TestBigQueryExportRequest(BaseModel):
    """Test BigQuery to GCS export"""
    source_connection_id: int
    project_id: str
    dataset: str
    table: str
    gcs_bucket: str
    gcs_path: str


class TestGCSToS3TransferRequest(BaseModel):
    """Test GCS to S3 transfer"""
    gcs_bucket: str
    gcs_path: str
    s3_bucket: str
    s3_path: str
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None


class TestS3ToRedshiftLoadRequest(BaseModel):
    """Test S3 to Redshift load"""
    target_connection_id: int
    s3_bucket: str
    s3_path: str
    table_name: str
    schema: str = "public"
    iam_role: Optional[str] = None


# Response Models
class TestStepResponse(BaseModel):
    """Generic test step response"""
    success: bool
    step: str
    message: str
    details: dict
    duration_seconds: float
    timestamp: str


@router.post("/step1-bigquery-to-gcs", response_model=TestStepResponse)
async def test_bigquery_to_gcs_export(
    req: TestBigQueryExportRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Test Step 1: Export BigQuery table to GCS
    
    This endpoint tests the BigQuery export functionality:
    - Connects to BigQuery using provided credentials
    - Exports specified table to GCS in AVRO format
    - Returns export job details and file locations
    """
    start_time = datetime.utcnow()
    
    try:
        logger.info(f"Testing BigQuery to GCS export for table {req.table}")
        
        # Get source connection
        connection = db.query(Connection).filter(
            Connection.id == req.source_connection_id
        ).first()
        
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection {req.source_connection_id} not found"
            )
        
        if connection.database.lower() != 'bigquery':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Connection must be BigQuery type, got {connection.database}"
            )
        
        # Import BigQuery libraries
        from google.cloud import bigquery
        from google.oauth2 import service_account
        import json
        
        # Parse credentials
        connection_params = connection.connection_params or {}
        service_account_key = (
            connection_params.get('service_account_key') or 
            connection_params.get('serviceAccountKey') or
            connection_params.get('credentials_json')
        )
        
        if not service_account_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Service Account Key is required"
            )
        
        if isinstance(service_account_key, str):
            credentials_dict = json.loads(service_account_key)
        else:
            credentials_dict = service_account_key
        
        # Create BigQuery client
        credentials = service_account.Credentials.from_service_account_info(credentials_dict)
        client = bigquery.Client(
            credentials=credentials,
            project=req.project_id
        )
        
        # Create export job
        table_ref = f"{req.project_id}.{req.dataset}.{req.table}"
        destination_uri = f"gs://{req.gcs_bucket}/{req.gcs_path}/{req.table}/shard-*.avro"
        
        logger.info(f"Exporting {table_ref} to {destination_uri}")
        
        job_config = bigquery.ExtractJobConfig(
            destination_format=bigquery.DestinationFormat.AVRO,
            compression=bigquery.Compression.SNAPPY
        )
        
        extract_job = client.extract_table(
            table_ref,
            destination_uri,
            job_config=job_config
        )
        
        # Wait for job to complete
        extract_job.result()
        
        # Get job statistics
        job_stats = {
            'job_id': extract_job.job_id,
            'state': extract_job.state,
            'created': extract_job.created.isoformat() if extract_job.created else None,
            'started': extract_job.started.isoformat() if extract_job.started else None,
            'ended': extract_job.ended.isoformat() if extract_job.ended else None,
            'destination_uri': destination_uri,
            'destination_uri_file_counts': extract_job.destination_uri_file_counts if hasattr(extract_job, 'destination_uri_file_counts') else None
        }
        
        # Get table info
        table = client.get_table(table_ref)
        table_info = {
            'num_rows': table.num_rows,
            'num_bytes': table.num_bytes,
            'table_type': table.table_type
        }
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info(f"Export completed successfully in {duration:.2f}s")
        
        return TestStepResponse(
            success=True,
            step="bigquery_to_gcs",
            message=f"Successfully exported {req.table} to GCS",
            details={
                'table': req.table,
                'table_info': table_info,
                'job_stats': job_stats,
                'gcs_location': destination_uri
            },
            duration_seconds=duration,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.error(f"BigQuery to GCS export failed: {str(e)}")
        
        return TestStepResponse(
            success=False,
            step="bigquery_to_gcs",
            message=f"Export failed: {str(e)}",
            details={'error': str(e)},
            duration_seconds=duration,
            timestamp=datetime.utcnow().isoformat()
        )


@router.post("/step2-gcs-to-s3", response_model=TestStepResponse)
async def test_gcs_to_s3_transfer(
    req: TestGCSToS3TransferRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Test Step 2: Transfer files from GCS to S3
    
    This endpoint tests the GCS to S3 transfer using Storage Transfer Service:
    - Creates a transfer job from GCS to S3
    - Monitors transfer progress
    - Returns transfer job details and status
    """
    start_time = datetime.utcnow()
    
    try:
        logger.info(f"Testing GCS to S3 transfer: {req.gcs_bucket}/{req.gcs_path} -> {req.s3_bucket}/{req.s3_path}")
        
        # Import Storage Transfer Service
        from google.cloud import storage_transfer_v1
        
        # Create transfer client
        transfer_client = storage_transfer_v1.StorageTransferServiceClient()
        
        # Create transfer job
        transfer_job = {
            'description': f'Test transfer: {req.gcs_path}',
            'status': 'ENABLED',
            'transfer_spec': {
                'gcs_data_source': {
                    'bucket_name': req.gcs_bucket,
                    'path': req.gcs_path
                },
                'aws_s3_data_sink': {
                    'bucket_name': req.s3_bucket,
                    'path': req.s3_path
                },
                'transfer_options': {
                    'overwrite_objects_already_existing_in_sink': False,
                    'delete_objects_from_source_after_transfer': False
                }
            },
            'schedule': {
                'schedule_start_date': {
                    'year': datetime.utcnow().year,
                    'month': datetime.utcnow().month,
                    'day': datetime.utcnow().day
                }
            }
        }
        
        # Add AWS credentials if provided
        if req.aws_access_key_id and req.aws_secret_access_key:
            transfer_job['transfer_spec']['aws_s3_data_sink']['aws_access_key'] = {
                'access_key_id': req.aws_access_key_id,
                'secret_access_key': req.aws_secret_access_key
            }
        
        # Create transfer job
        response = transfer_client.create_transfer_job(transfer_job=transfer_job)
        job_name = response.name
        
        logger.info(f"Created transfer job: {job_name}")
        
        # Get job status
        job = transfer_client.get_transfer_job(job_name=job_name)
        
        job_details = {
            'job_name': job_name,
            'status': job.status.name if hasattr(job.status, 'name') else str(job.status),
            'description': job.description,
            'creation_time': job.creation_time.isoformat() if hasattr(job, 'creation_time') and job.creation_time else None,
            'last_modification_time': job.last_modification_time.isoformat() if hasattr(job, 'last_modification_time') and job.last_modification_time else None
        }
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info(f"Transfer job created successfully in {duration:.2f}s")
        
        return TestStepResponse(
            success=True,
            step="gcs_to_s3",
            message=f"Transfer job created: {job_name}",
            details={
                'job': job_details,
                'source': f"gs://{req.gcs_bucket}/{req.gcs_path}",
                'destination': f"s3://{req.s3_bucket}/{req.s3_path}",
                'note': 'Transfer job is running asynchronously. Check GCP Console for progress.'
            },
            duration_seconds=duration,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.error(f"GCS to S3 transfer failed: {str(e)}")
        
        return TestStepResponse(
            success=False,
            step="gcs_to_s3",
            message=f"Transfer failed: {str(e)}",
            details={'error': str(e)},
            duration_seconds=duration,
            timestamp=datetime.utcnow().isoformat()
        )


@router.post("/step3-s3-to-redshift", response_model=TestStepResponse)
async def test_s3_to_redshift_load(
    req: TestS3ToRedshiftLoadRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Test Step 3: Load data from S3 to Redshift
    
    This endpoint tests the S3 to Redshift load using COPY command:
    - Connects to Redshift using provided credentials
    - Executes COPY command to load data from S3
    - Returns load statistics and row counts
    """
    start_time = datetime.utcnow()
    
    try:
        logger.info(f"Testing S3 to Redshift load for table {req.table_name}")
        
        # Get target connection
        connection = db.query(Connection).filter(
            Connection.id == req.target_connection_id
        ).first()
        
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection {req.target_connection_id} not found"
            )
        
        if connection.database.lower() != 'redshift':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Connection must be Redshift type, got {connection.database}"
            )
        
        # Import Redshift libraries
        import psycopg2
        
        # Parse credentials
        connection_params = connection.connection_params or {}
        host = connection_params.get('host') or connection_params.get('cluster')
        port = connection_params.get('port', 5439)
        database = connection_params.get('database')
        username = connection_params.get('username') or connection_params.get('user')
        password = connection_params.get('password')
        
        if not all([host, database, username, password]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required Redshift connection parameters"
            )
        
        # Connect to Redshift
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=username,
            password=password,
            sslmode='require'
        )
        cursor = conn.cursor()
        
        # Build S3 path
        s3_uri = f"s3://{req.s3_bucket}/{req.s3_path}/{req.table_name}/"
        
        # Execute COPY command
        copy_sql = f"""
            COPY {req.schema}.{req.table_name}
            FROM '{s3_uri}'
            FORMAT AS AVRO 'auto'
            COMPUPDATE OFF
            STATUPDATE OFF
        """
        
        # Add IAM role if provided
        if req.iam_role:
            copy_sql = copy_sql.replace(
                "FORMAT AS AVRO",
                f"IAM_ROLE '{req.iam_role}'\n    FORMAT AS AVRO"
            )
        else:
            # Use access credentials from connection
            aws_access_key_id = connection_params.get('aws_access_key_id')
            aws_secret_access_key = connection_params.get('aws_secret_access_key')
            
            if aws_access_key_id and aws_secret_access_key:
                copy_sql = copy_sql.replace(
                    "FORMAT AS AVRO",
                    f"ACCESS_KEY_ID '{aws_access_key_id}'\n    SECRET_ACCESS_KEY '{aws_secret_access_key}'\n    FORMAT AS AVRO"
                )
        
        logger.info(f"Executing COPY command for {req.table_name}")
        
        cursor.execute(copy_sql)
        conn.commit()
        
        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {req.schema}.{req.table_name}")
        row_count = cursor.fetchone()[0]
        
        # Get table info
        cursor.execute(f"""
            SELECT 
                COUNT(*) as row_count,
                pg_size_pretty(pg_total_relation_size('{req.schema}.{req.table_name}')) as table_size
            FROM {req.schema}.{req.table_name}
        """)
        table_stats = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info(f"Load completed successfully in {duration:.2f}s")
        
        return TestStepResponse(
            success=True,
            step="s3_to_redshift",
            message=f"Successfully loaded {row_count} rows into {req.table_name}",
            details={
                'table': req.table_name,
                'schema': req.schema,
                'row_count': row_count,
                'table_size': table_stats[1] if table_stats else None,
                's3_source': s3_uri
            },
            duration_seconds=duration,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.error(f"S3 to Redshift load failed: {str(e)}")
        
        return TestStepResponse(
            success=False,
            step="s3_to_redshift",
            message=f"Load failed: {str(e)}",
            details={'error': str(e)},
            duration_seconds=duration,
            timestamp=datetime.utcnow().isoformat()
        )


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "pathway-a-testing",
        "steps": [
            "step1-bigquery-to-gcs",
            "step2-gcs-to-s3",
            "step3-s3-to-redshift"
        ]
    }
