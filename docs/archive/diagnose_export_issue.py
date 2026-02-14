"""
Comprehensive diagnostic script to identify why exported files have 0 rows.

This script will:
1. Query BigQuery tables directly to verify they have data
2. Check GCS files to see if they have data
3. Check S3 files to see if they have data
4. Re-export from BigQuery with validation
5. Identify where data is being lost
"""

import os
import sys
import json
import logging
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from google.cloud import bigquery, storage as gcs_storage
from google.oauth2 import service_account
import boto3
import pyarrow.parquet as pq
import io

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_bigquery_data(credentials_dict, project_id, dataset, table):
    """Check if BigQuery table has data"""
    logger.info(f"\n{'='*80}")
    logger.info(f"STEP 1: Checking BigQuery Table Data")
    logger.info(f"{'='*80}")
    
    try:
        credentials = service_account.Credentials.from_service_account_info(credentials_dict)
        client = bigquery.Client(credentials=credentials, project=project_id)
        
        table_ref = f"{project_id}.{dataset}.{table}"
        logger.info(f"Table: {table_ref}")
        
        # Get table metadata
        table_obj = client.get_table(table_ref)
        logger.info(f"✓ Table exists")
        logger.info(f"  Rows: {table_obj.num_rows:,}")
        logger.info(f"  Bytes: {table_obj.num_bytes:,}")
        logger.info(f"  Columns: {len(table_obj.schema)}")
        
        # Query actual data
        query = f"SELECT * FROM `{table_ref}` LIMIT 10"
        logger.info(f"\nQuerying data: {query}")
        
        query_job = client.query(query)
        results = list(query_job.result())
        
        logger.info(f"✓ Query returned {len(results)} rows")
        
        if results:
            logger.info(f"\nSample data (first row):")
            for key, value in dict(results[0]).items():
                logger.info(f"  {key}: {value}")
        
        return {
            'has_data': table_obj.num_rows > 0,
            'row_count': table_obj.num_rows,
            'sample_rows': len(results)
        }
        
    except Exception as e:
        logger.error(f"✗ Failed to check BigQuery data: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {'has_data': False, 'error': str(e)}


def check_gcs_files(credentials_dict, bucket_name, path_prefix):
    """Check if GCS files have data"""
    logger.info(f"\n{'='*80}")
    logger.info(f"STEP 2: Checking GCS Files")
    logger.info(f"{'='*80}")
    
    try:
        credentials = service_account.Credentials.from_service_account_info(credentials_dict)
        client = gcs_storage.Client(credentials=credentials)
        
        bucket = client.bucket(bucket_name)
        logger.info(f"Bucket: gs://{bucket_name}")
        logger.info(f"Path: {path_prefix}")
        
        # List files
        blobs = list(bucket.list_blobs(prefix=path_prefix))
        file_blobs = [b for b in blobs if not b.name.endswith('/')]
        
        logger.info(f"✓ Found {len(file_blobs)} files")
        
        results = []
        for blob in file_blobs[:5]:  # Check first 5 files
            logger.info(f"\nFile: {blob.name}")
            logger.info(f"  Size: {blob.size:,} bytes")
            
            # Download and check content
            if blob.name.endswith('.parquet'):
                try:
                    content = blob.download_as_bytes()
                    parquet_file = pq.read_table(io.BytesIO(content))
                    row_count = len(parquet_file)
                    
                    logger.info(f"  Format: PARQUET")
                    logger.info(f"  Rows: {row_count}")
                    logger.info(f"  Columns: {len(parquet_file.schema)}")
                    
                    if row_count > 0:
                        logger.info(f"  ✓ File has data!")
                        # Show sample
                        df = parquet_file.to_pandas()
                        logger.info(f"\n  Sample data (first row):")
                        for col in df.columns:
                            logger.info(f"    {col}: {df[col].iloc[0]}")
                    else:
                        logger.warning(f"  ⚠️  File has 0 rows!")
                    
                    results.append({
                        'file': blob.name,
                        'size': blob.size,
                        'rows': row_count,
                        'has_data': row_count > 0
                    })
                    
                except Exception as e:
                    logger.error(f"  ✗ Failed to read PARQUET: {e}")
                    results.append({
                        'file': blob.name,
                        'size': blob.size,
                        'error': str(e)
                    })
        
        return results
        
    except Exception as e:
        logger.error(f"✗ Failed to check GCS files: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []


def check_s3_files(bucket_name, path_prefix, aws_access_key, aws_secret_key):
    """Check if S3 files have data"""
    logger.info(f"\n{'='*80}")
    logger.info(f"STEP 3: Checking S3 Files")
    logger.info(f"{'='*80}")
    
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key
        )
        
        logger.info(f"Bucket: s3://{bucket_name}")
        logger.info(f"Path: {path_prefix}")
        
        # List files
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=path_prefix
        )
        
        if 'Contents' not in response:
            logger.warning(f"⚠️  No files found in S3")
            return []
        
        files = [obj for obj in response['Contents'] if not obj['Key'].endswith('/')]
        logger.info(f"✓ Found {len(files)} files")
        
        results = []
        for obj in files[:5]:  # Check first 5 files
            logger.info(f"\nFile: {obj['Key']}")
            logger.info(f"  Size: {obj['Size']:,} bytes")
            
            # Download and check content
            if obj['Key'].endswith('.parquet'):
                try:
                    response = s3_client.get_object(Bucket=bucket_name, Key=obj['Key'])
                    content = response['Body'].read()
                    
                    parquet_file = pq.read_table(io.BytesIO(content))
                    row_count = len(parquet_file)
                    
                    logger.info(f"  Format: PARQUET")
                    logger.info(f"  Rows: {row_count}")
                    logger.info(f"  Columns: {len(parquet_file.schema)}")
                    
                    if row_count > 0:
                        logger.info(f"  ✓ File has data!")
                        # Show sample
                        df = parquet_file.to_pandas()
                        logger.info(f"\n  Sample data (first row):")
                        for col in df.columns:
                            logger.info(f"    {col}: {df[col].iloc[0]}")
                    else:
                        logger.warning(f"  ⚠️  File has 0 rows!")
                    
                    results.append({
                        'file': obj['Key'],
                        'size': obj['Size'],
                        'rows': row_count,
                        'has_data': row_count > 0
                    })
                    
                except Exception as e:
                    logger.error(f"  ✗ Failed to read PARQUET: {e}")
                    results.append({
                        'file': obj['Key'],
                        'size': obj['Size'],
                        'error': str(e)
                    })
        
        return results
        
    except Exception as e:
        logger.error(f"✗ Failed to check S3 files: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []


def export_with_validation(credentials_dict, project_id, dataset, table, gcs_bucket, gcs_path):
    """Export from BigQuery with validation"""
    logger.info(f"\n{'='*80}")
    logger.info(f"STEP 4: Fresh Export with Validation")
    logger.info(f"{'='*80}")
    
    try:
        credentials = service_account.Credentials.from_service_account_info(credentials_dict)
        bq_client = bigquery.Client(credentials=credentials, project=project_id)
        gcs_client = gcs_storage.Client(credentials=credentials)
        
        table_ref = f"{project_id}.{dataset}.{table}"
        table_obj = bq_client.get_table(table_ref)
        
        logger.info(f"Source table: {table_ref}")
        logger.info(f"  Rows: {table_obj.num_rows:,}")
        logger.info(f"  Bytes: {table_obj.num_bytes:,}")
        
        # Create export path with timestamp
        import time
        timestamp = int(time.time())
        export_path = f"{gcs_path}/test_export_{timestamp}"
        destination_uri = f"gs://{gcs_bucket}{export_path}/{table}_*.parquet"
        
        logger.info(f"\nExporting to: {destination_uri}")
        
        # Configure export
        job_config = bigquery.ExtractJobConfig()
        job_config.destination_format = bigquery.DestinationFormat.PARQUET
        
        # Start export
        extract_job = bq_client.extract_table(
            table_ref,
            destination_uri,
            job_config=job_config
        )
        
        logger.info(f"Job ID: {extract_job.job_id}")
        logger.info("Waiting for export...")
        
        extract_job.result()
        
        logger.info(f"✓ Export completed")
        
        # Validate exported files
        logger.info(f"\nValidating exported files...")
        bucket = gcs_client.bucket(gcs_bucket)
        blobs = list(bucket.list_blobs(prefix=export_path.lstrip('/')))
        file_blobs = [b for b in blobs if not b.name.endswith('/')]
        
        logger.info(f"✓ Found {len(file_blobs)} exported files")
        
        total_rows = 0
        for blob in file_blobs:
            logger.info(f"\nValidating: {blob.name}")
            logger.info(f"  Size: {blob.size:,} bytes")
            
            content = blob.download_as_bytes()
            parquet_file = pq.read_table(io.BytesIO(content))
            row_count = len(parquet_file)
            
            logger.info(f"  Rows: {row_count}")
            total_rows += row_count
        
        logger.info(f"\n{'='*40}")
        logger.info(f"VALIDATION RESULT:")
        logger.info(f"  Source rows: {table_obj.num_rows:,}")
        logger.info(f"  Exported rows: {total_rows:,}")
        logger.info(f"  Match: {'✓ YES' if total_rows == table_obj.num_rows else '✗ NO'}")
        logger.info(f"{'='*40}")
        
        return {
            'success': True,
            'source_rows': table_obj.num_rows,
            'exported_rows': total_rows,
            'match': total_rows == table_obj.num_rows,
            'export_path': export_path
        }
        
    except Exception as e:
        logger.error(f"✗ Export failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {'success': False, 'error': str(e)}


def main():
    """Run comprehensive diagnostics"""
    logger.info(f"\n{'#'*80}")
    logger.info(f"COMPREHENSIVE EXPORT DIAGNOSTICS")
    logger.info(f"{'#'*80}")
    
    # Import database dependencies
    from database import get_db
    from models.bq_redshift_migration import MigrationBQRedshift
    from models.connection import Connection
    from services.encryption_service import get_encryption_service
    
    db = next(get_db())
    encryption_service = get_encryption_service()
    
    # Load migration 12 from database
    logger.info("\nLoading migration 12 from database...")
    migration = db.query(MigrationBQRedshift).filter_by(id=12).first()
    
    if not migration:
        logger.error("Migration 12 not found in database")
        return
    
    logger.info(f"✓ Migration: {migration.migration_name}")
    
    # Get source connection for GCP credentials
    source_conn = db.query(Connection).filter_by(id=migration.source_connection_id).first()
    if not source_conn:
        logger.error("Source connection not found")
        return
    
    # Extract GCP credentials
    conn_params = source_conn.connection_params or {}
    service_account_key = (
        conn_params.get('service_account_key') or 
        conn_params.get('serviceAccountKey') or
        conn_params.get('credentials_json') or
        conn_params.get('service_account_key_encrypted')
    )
    
    if not service_account_key:
        logger.error("GCP credentials not found in connection")
        return
    
    # Parse credentials
    if isinstance(service_account_key, str):
        gcp_credentials = json.loads(service_account_key)
    else:
        gcp_credentials = service_account_key
    project_id = gcp_credentials.get('project_id')
    
    logger.info(f"✓ GCP Project: {project_id}")
    
    # Get AWS credentials
    aws_access_key = migration.aws_access_key_id
    aws_secret_key_encrypted = migration.aws_secret_access_key_encrypted
    aws_secret_key = encryption_service.decrypt(aws_secret_key_encrypted)
    
    # Configuration from migration
    dataset = migration.source_dataset
    tables = migration.source_tables if isinstance(migration.source_tables, list) else []
    gcs_bucket = migration.gcs_bucket.replace('gs://', '').strip('/')
    gcs_base_path = migration.gcs_path.strip('/') if migration.gcs_path else ''
    
    s3_bucket = migration.s3_bucket.replace('s3://', '').strip('/')
    s3_base_path = migration.s3_path.strip('/') if migration.s3_path else ''
    
    logger.info(f"✓ Dataset: {dataset}")
    logger.info(f"✓ Tables: {', '.join(tables)}")
    logger.info(f"✓ GCS: gs://{gcs_bucket}/{gcs_base_path}")
    logger.info(f"✓ S3: s3://{s3_bucket}/{s3_base_path}")
    
    # Run diagnostics for each table
    for table in tables:
        logger.info(f"\n\n{'#'*80}")
        logger.info(f"DIAGNOSING TABLE: {table}")
        logger.info(f"{'#'*80}")
        
        # Step 1: Check BigQuery
        bq_result = check_bigquery_data(gcp_credentials, project_id, dataset, table)
        
        if not bq_result.get('has_data'):
            logger.error(f"✗ BigQuery table has no data! Skipping further checks.")
            continue
        
        # Step 2: Check GCS files
        gcs_path = f"{gcs_base_path}/{table}"
        gcs_results = check_gcs_files(gcp_credentials, gcs_bucket, gcs_path.lstrip('/'))
        
        # Step 3: Check S3 files
        s3_path = f"{s3_base_path}/{table}"
        s3_results = check_s3_files(s3_bucket, s3_path, aws_access_key, aws_secret_key)
        
        # Step 4: Fresh export with validation
        export_result = export_with_validation(
            gcp_credentials, project_id, dataset, table,
            gcs_bucket, gcs_base_path
        )
        
        # Summary
        logger.info(f"\n{'='*80}")
        logger.info(f"SUMMARY FOR {table}")
        logger.info(f"{'='*80}")
        logger.info(f"BigQuery: {bq_result.get('row_count', 0)} rows")
        
        if gcs_results:
            gcs_rows = sum(r.get('rows', 0) for r in gcs_results if 'rows' in r)
            logger.info(f"GCS Files: {gcs_rows} rows (checked {len(gcs_results)} files)")
        else:
            logger.info(f"GCS Files: No files or failed to check")
        
        if s3_results:
            s3_rows = sum(r.get('rows', 0) for r in s3_results if 'rows' in r)
            logger.info(f"S3 Files: {s3_rows} rows (checked {len(s3_results)} files)")
        else:
            logger.info(f"S3 Files: No files or failed to check")
        
        if export_result.get('success'):
            logger.info(f"Fresh Export: {export_result.get('exported_rows', 0)} rows")
            logger.info(f"  Match: {'✓' if export_result.get('match') else '✗'}")
        
        logger.info(f"{'='*80}")
    
    logger.info(f"\n{'#'*80}")
    logger.info(f"DIAGNOSTICS COMPLETE")
    logger.info(f"{'#'*80}")


if __name__ == "__main__":
    main()
