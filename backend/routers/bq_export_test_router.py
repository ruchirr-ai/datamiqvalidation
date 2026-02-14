"""
BigQuery to GCS Export Testing Router

Endpoint for testing BigQuery table export to GCS with real production data.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
import logging

from database import get_db
from shared.middleware.auth_middleware import get_current_user
from models.connection import Connection

router = APIRouter(prefix="/api/bq-export-test", tags=["BQ Export Testing"])
logger = logging.getLogger(__name__)


class BQExportTestRequest(BaseModel):
    """Request model for BigQuery export test"""
    connection_id: int = Field(..., description="BigQuery connection ID")
    project_id: str = Field(..., description="GCP Project ID")
    dataset: str = Field(..., description="BigQuery dataset name")
    table: str = Field(..., description="BigQuery table name")
    gcs_bucket: str = Field(..., description="GCS bucket name (without gs:// prefix)")
    gcs_path: str = Field(default="/exports", description="Path within GCS bucket")
    export_format: str = Field(default="AVRO", description="Export format: AVRO, PARQUET, CSV, JSON")
    compression: Optional[str] = Field(default=None, description="Compression: GZIP, SNAPPY, DEFLATE, or None")


class BQExportTestResponse(BaseModel):
    """Response model for BigQuery export test"""
    success: bool
    message: str
    job_id: Optional[str] = None
    destination_uris: Optional[List[str]] = None
    rows_exported: Optional[int] = None
    bytes_exported: Optional[int] = None
    files_created: Optional[int] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None


@router.post("/export", response_model=BQExportTestResponse)
async def test_bigquery_export(
    request: BQExportTestRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Test BigQuery table export to GCS with real production data.
    
    This endpoint:
    1. Connects to BigQuery using the provided connection
    2. Exports the specified table to GCS in the chosen format
    3. Returns detailed results including file locations and statistics
    
    **Export Formats**:
    - AVRO: Recommended for large datasets, preserves schema
    - PARQUET: Columnar format, good compression
    - CSV: Simple text format, widely compatible
    - JSON: Newline-delimited JSON
    
    **Compression Options**:
    - GZIP: Good compression ratio, slower
    - SNAPPY: Fast compression, larger files
    - DEFLATE: Balanced compression
    - None: No compression (faster export)
    """
    import time
    start_time = time.time()
    
    logger.info(f"=== BigQuery Export Test Started ===")
    logger.info(f"User: {current_user.user_id}")
    logger.info(f"Connection: {request.connection_id}")
    logger.info(f"Table: {request.project_id}.{request.dataset}.{request.table}")
    logger.info(f"Destination: gs://{request.gcs_bucket}{request.gcs_path}")
    logger.info(f"Format: {request.export_format}, Compression: {request.compression}")
    
    try:
        # Get BigQuery connection
        connection = db.query(Connection).filter(
            Connection.id == request.connection_id
        ).first()
        
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection {request.connection_id} not found"
            )
        
        if connection.database.lower() != 'bigquery':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Connection must be BigQuery type, got {connection.database}"
            )
        
        logger.info(f"✓ Connection validated: {connection.name}")
        
        # Import BigQuery libraries
        try:
            from google.cloud import bigquery
            from google.oauth2 import service_account
            import json
        except ImportError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="BigQuery client library not installed"
            )
        
        # Parse credentials
        connection_params = connection.connection_params or {}
        service_account_key = (
            connection_params.get('service_account_key') or 
            connection_params.get('serviceAccountKey') or
            connection_params.get('credentials_json') or
            connection_params.get('credentialsJson')
        )
        
        if not service_account_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Service Account Key not found in connection"
            )
        
        # Parse credentials
        if isinstance(service_account_key, str):
            credentials_dict = json.loads(service_account_key)
        else:
            credentials_dict = service_account_key
        
        # Create BigQuery client
        credentials = service_account.Credentials.from_service_account_info(credentials_dict)
        client = bigquery.Client(
            credentials=credentials,
            project=request.project_id
        )
        
        logger.info("✓ BigQuery client created")
        
        # Validate table exists
        table_ref = f"{request.project_id}.{request.dataset}.{request.table}"
        try:
            table = client.get_table(table_ref)
            logger.info(f"✓ Table found: {table.num_rows:,} rows, {table.num_bytes:,} bytes")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Table not found: {table_ref}"
            )
        
        # Prepare destination URI
        destination_uri = f"gs://{request.gcs_bucket}{request.gcs_path}/{request.table}_*.{request.export_format.lower()}"
        if request.compression:
            destination_uri += f".{request.compression.lower()}"
        
        logger.info(f"Destination URI pattern: {destination_uri}")
        
        # Configure export job
        job_config = bigquery.ExtractJobConfig()
        job_config.destination_format = f"NEWLINE_DELIMITED_JSON" if request.export_format == "JSON" else request.export_format
        
        if request.compression:
            job_config.compression = request.compression
        
        # Start export job
        logger.info("Starting BigQuery export job...")
        extract_job = client.extract_table(
            table_ref,
            destination_uri,
            job_config=job_config
        )
        
        # Wait for job to complete
        logger.info(f"Job ID: {extract_job.job_id}")
        logger.info("Waiting for export to complete...")
        
        extract_job.result()  # Wait for completion
        
        duration = time.time() - start_time
        
        logger.info(f"✓ Export completed in {duration:.2f} seconds")
        
        # Get job statistics
        destination_uris = extract_job.destination_uris if hasattr(extract_job, 'destination_uris') else [destination_uri]
        
        # Count files created (estimate based on table size)
        # BigQuery creates multiple files for large tables
        estimated_files = max(1, int(table.num_bytes / (100 * 1024 * 1024)))  # ~100MB per file
        
        logger.info(f"=== Export Complete ===")
        logger.info(f"Job ID: {extract_job.job_id}")
        logger.info(f"Rows: {table.num_rows:,}")
        logger.info(f"Bytes: {table.num_bytes:,}")
        logger.info(f"Files: ~{estimated_files}")
        logger.info(f"Duration: {duration:.2f}s")
        
        return BQExportTestResponse(
            success=True,
            message=f"Successfully exported {table.num_rows:,} rows to GCS",
            job_id=extract_job.job_id,
            destination_uris=destination_uris,
            rows_exported=table.num_rows,
            bytes_exported=table.num_bytes,
            files_created=estimated_files,
            duration_seconds=round(duration, 2)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Export failed after {duration:.2f}s: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        return BQExportTestResponse(
            success=False,
            message="Export failed",
            error=str(e),
            duration_seconds=round(duration, 2)
        )


@router.get("/formats")
async def get_export_formats():
    """Get available export formats and their descriptions"""
    return {
        "formats": [
            {
                "value": "AVRO",
                "label": "AVRO",
                "description": "Binary format, preserves schema, recommended for large datasets",
                "compression": ["SNAPPY", "DEFLATE", "None"]
            },
            {
                "value": "PARQUET",
                "label": "Parquet",
                "description": "Columnar format, excellent compression, good for analytics",
                "compression": ["SNAPPY", "GZIP", "None"]
            },
            {
                "value": "CSV",
                "label": "CSV",
                "description": "Simple text format, widely compatible, human-readable",
                "compression": ["GZIP", "None"]
            },
            {
                "value": "JSON",
                "label": "JSON (Newline-delimited)",
                "description": "JSON format, one record per line, human-readable",
                "compression": ["GZIP", "None"]
            }
        ]
    }
