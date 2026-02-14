"""
Test Path C: BigQuery → GCS → S3 Transfer from Database
Reads migration configuration from database and executes complete transfer.

Uses:
- BigQueryExporter service for BQ → GCS (same as migration job)
- Download and upload approach for GCS → S3
"""

import logging
import sys
import os
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import json

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.bq_redshift_migration import MigrationBQRedshift
from models.connection import Connection
from services.bq_redshift_migration.bigquery_exporter import BigQueryExporter
from services.bq_redshift_migration.gcs_to_s3_transfer import GCSToS3Transfer
from services.encryption_service import EncryptionService
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_db_session():
    """Create database session"""
    # Try DATABASE_URL first
    database_url = os.getenv("DATABASE_URL")
    
    # If not set, construct from individual variables
    if not database_url:
        db_host = os.getenv("APP_DB_HOST", "localhost")
        db_port = os.getenv("APP_DB_PORT", "5432")
        db_name = os.getenv("APP_DB_NAME")
        db_user = os.getenv("APP_DB_USER")
        db_password = os.getenv("APP_DB_PASSWORD", "")
        
        if not db_name or not db_user:
            raise ValueError("Database configuration not found. Set DATABASE_URL or APP_DB_* variables")
        
        database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


async def test_path_c_from_database(migration_id: int):
    """
    Test Path C migration from database configuration.
    
    Args:
        migration_id: ID of the migration to test
    """
    db = None
    
    try:
        logger.info("="*80)
        logger.info("PATH C TEST: BIGQUERY → GCS → S3 (FROM DATABASE)")
        logger.info("="*80)
        
        # Get database session
        db = get_db_session()
        
        # Fetch migration
        logger.info(f"Fetching migration ID: {migration_id}")
        migration = db.query(MigrationBQRedshift).filter(
            MigrationBQRedshift.id == migration_id
        ).first()
        
        if not migration:
            raise ValueError(f"Migration {migration_id} not found")
        
        logger.info(f"✓ Found migration: {migration.migration_name}")
        logger.info(f"  Pathway: {migration.pathway}")
        logger.info(f"  Status: {migration.status}")
        
        if migration.pathway != 'C':
            raise ValueError(f"Migration is not Path C (found: {migration.pathway})")
        
        # Fetch source connection
        logger.info(f"Fetching source connection ID: {migration.source_connection_id}")
        source_conn = db.query(Connection).filter(
            Connection.id == migration.source_connection_id
        ).first()
        
        if not source_conn:
            raise ValueError(f"Source connection {migration.source_connection_id} not found")
        
        logger.info(f"✓ Source connection: {source_conn.name} ({source_conn.type})")
        
        # Parse GCP credentials from connection_params
        # Try different possible keys for credentials
        connection_params = source_conn.connection_params
        gcp_credentials_json = (
            connection_params.get('service_account_key') or 
            connection_params.get('serviceAccountKey') or
            connection_params.get('credentials_json') or
            connection_params.get('credentialsJson') or
            connection_params.get('credentials')
        )
        
        if not gcp_credentials_json:
            raise ValueError("GCP credentials not found in connection_params")
        
        # Parse JSON if it's a string
        if isinstance(gcp_credentials_json, str):
            gcp_credentials = json.loads(gcp_credentials_json)
        else:
            gcp_credentials = gcp_credentials_json
        
        # Decrypt AWS secret key
        encryption_service = EncryptionService()
        aws_secret_key = encryption_service.decrypt(migration.aws_secret_access_key_encrypted)
        
        logger.info("="*80)
        logger.info("MIGRATION CONFIGURATION")
        logger.info("="*80)
        logger.info(f"Source Project: {migration.source_project_id}")
        logger.info(f"Source Dataset: {migration.source_dataset}")
        logger.info(f"Source Tables: {migration.source_tables}")
        
        # Clean up GCS bucket name (remove gs:// prefix if present)
        gcs_bucket_clean = migration.gcs_bucket.replace('gs://', '').strip('/')
        gcs_path_clean = migration.gcs_path.strip('/') if migration.gcs_path else ''
        
        logger.info(f"GCS Bucket: {gcs_bucket_clean}")
        logger.info(f"GCS Path: {gcs_path_clean}")
        logger.info(f"S3 Bucket: {migration.s3_bucket}")
        logger.info(f"S3 Path: {migration.s3_path}")
        logger.info(f"Export Format: {migration.export_format}")
        logger.info(f"Compression: {migration.compression}")
        logger.info(f"Delete After Transfer: {migration.delete_source_after_transfer}")
        logger.info("="*80)
        
        # ========================================================================
        # STAGE 1: EXPORT FROM BIGQUERY TO GCS
        # ========================================================================
        logger.info("")
        logger.info("="*80)
        logger.info("STAGE 1: EXPORT FROM BIGQUERY TO GCS")
        logger.info("="*80)
        
        # Initialize BigQuery exporter (same as migration job uses)
        exporter = BigQueryExporter(
            credentials_dict=gcp_credentials,
            project_id=migration.source_project_id
        )
        
        # Parse tables
        tables = json.loads(migration.source_tables) if isinstance(migration.source_tables, str) else migration.source_tables
        table_names = [t if isinstance(t, str) else t.get('name') for t in tables]
        
        logger.info(f"Exporting {len(table_names)} tables...")
        
        # Export all tables using the exporter service
        export_results = exporter.export_tables(
            dataset=migration.source_dataset,
            tables=table_names,
            gcs_bucket=gcs_bucket_clean,
            gcs_path=gcs_path_clean,
            export_format=migration.export_format,
            compression=migration.compression
        )
        
        # Calculate totals
        total_rows_exported = sum(r.get('num_rows', 0) for r in export_results if r.get('success'))
        total_bytes_exported = sum(r.get('num_bytes', 0) for r in export_results if r.get('success'))
        successful_exports = sum(1 for r in export_results if r.get('success'))
        
        logger.info("")
        logger.info("="*80)
        logger.info("STAGE 1 COMPLETE: BIGQUERY EXPORT")
        logger.info("="*80)
        logger.info(f"Tables Exported: {successful_exports}/{len(table_names)}")
        logger.info(f"Total Rows: {total_rows_exported:,}")
        logger.info(f"Total Bytes: {total_bytes_exported:,}")
        logger.info("="*80)
        
        if successful_exports == 0:
            raise Exception("No tables exported successfully")
        
        # ========================================================================
        # STAGE 2: TRANSFER FROM GCS TO S3
        # ========================================================================
        logger.info("")
        logger.info("="*80)
        logger.info("STAGE 2: TRANSFER FROM GCS TO S3")
        logger.info("="*80)
        
        # Initialize GCS to S3 transfer
        transfer_service = GCSToS3Transfer(gcp_credentials_dict=gcp_credentials)
        
        # Perform transfer using download and upload approach
        transfer_result = transfer_service.transfer_files(
            gcs_bucket=gcs_bucket_clean,
            gcs_path=gcs_path_clean,
            s3_bucket=migration.s3_bucket,
            s3_path=migration.s3_path,
            aws_access_key_id=migration.aws_access_key_id,
            aws_secret_access_key=aws_secret_key,
            delete_source=migration.delete_source_after_transfer
        )
        
        logger.info("")
        logger.info("="*80)
        logger.info("STAGE 2 COMPLETE: GCS TO S3 TRANSFER")
        logger.info("="*80)
        logger.info(f"Status: {transfer_result.get('status', 'UNKNOWN')}")
        logger.info(f"Files Found: {transfer_result.get('files_found', 0)}")
        logger.info(f"Files Transferred: {transfer_result.get('files_transferred', 0)}")
        logger.info(f"Bytes Transferred: {transfer_result.get('bytes_transferred', 0):,}")
        logger.info(f"Files Failed: {transfer_result.get('files_failed', 0)}")
        if transfer_result.get('error'):
            logger.error(f"Error: {transfer_result['error']}")
        logger.info("="*80)
        
        if transfer_result['status'] == 'FAILED':
            raise Exception(f"Transfer failed: {transfer_result.get('error')}")
        
        # ========================================================================
        # VERIFICATION
        # ========================================================================
        logger.info("")
        logger.info("="*80)
        logger.info("VERIFICATION")
        logger.info("="*80)
        
        # Verify S3 files
        import boto3
        s3_client = boto3.client(
            's3',
            aws_access_key_id=migration.aws_access_key_id,
            aws_secret_access_key=aws_secret_key
        )
        
        logger.info(f"Checking S3 bucket: s3://{migration.s3_bucket}/{migration.s3_path}")
        
        try:
            s3_path_prefix = migration.s3_path.strip('/') if migration.s3_path else ''
            response = s3_client.list_objects_v2(
                Bucket=migration.s3_bucket,
                Prefix=s3_path_prefix
            )
            
            if 'Contents' in response:
                s3_files = response['Contents']
                logger.info(f"✓ Found {len(s3_files)} files in S3:")
                for obj in s3_files[:10]:  # Show first 10
                    logger.info(f"  - {obj['Key']} ({obj['Size']:,} bytes)")
                if len(s3_files) > 10:
                    logger.info(f"  ... and {len(s3_files) - 10} more files")
            else:
                logger.warning("✗ No files found in S3!")
        except Exception as e:
            logger.error(f"✗ Failed to list S3 files: {e}")
        
        logger.info("="*80)
        
        # ========================================================================
        # FINAL SUMMARY
        # ========================================================================
        logger.info("")
        logger.info("="*80)
        logger.info("✓ PATH C TEST COMPLETED SUCCESSFULLY")
        logger.info("="*80)
        logger.info(f"Migration ID: {migration_id}")
        logger.info(f"Migration Name: {migration.migration_name}")
        logger.info(f"Tables Exported: {successful_exports}/{len(table_names)}")
        logger.info(f"Total Rows: {total_rows_exported:,}")
        logger.info(f"Total Bytes: {total_bytes_exported:,}")
        logger.info(f"Files Transferred: {transfer_result.get('files_transferred', 0)}")
        logger.info(f"Bytes Transferred: {transfer_result.get('bytes_transferred', 0):,}")
        logger.info(f"Status: {transfer_result.get('status', 'UNKNOWN')}")
        logger.info("="*80)
        
        return {
            'success': True,
            'migration_id': migration_id,
            'export_results': export_results,
            'transfer_result': transfer_result
        }
        
    except Exception as e:
        logger.error("="*80)
        logger.error(f"✗ PATH C TEST FAILED: {str(e)}")
        logger.error("="*80)
        logger.exception(e)
        return {
            'success': False,
            'error': str(e)
        }
    
    finally:
        if db:
            db.close()


async def list_path_c_migrations():
    """List all Path C migrations in the database"""
    db = None
    
    try:
        db = get_db_session()
        
        migrations = db.query(MigrationBQRedshift).filter(
            MigrationBQRedshift.pathway == 'C'
        ).all()
        
        if not migrations:
            logger.info("No Path C migrations found in database")
            return
        
        logger.info("="*80)
        logger.info("PATH C MIGRATIONS IN DATABASE")
        logger.info("="*80)
        
        for m in migrations:
            logger.info(f"\nID: {m.id}")
            logger.info(f"Name: {m.migration_name}")
            logger.info(f"Status: {m.status}")
            logger.info(f"Source: {m.source_project_id}.{m.source_dataset}")
            logger.info(f"GCS: gs://{m.gcs_bucket}/{m.gcs_path}")
            logger.info(f"S3: s3://{m.s3_bucket}/{m.s3_path}")
            logger.info(f"Created: {m.created_at}")
        
        logger.info("="*80)
        
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    import argparse
    import asyncio
    
    parser = argparse.ArgumentParser(description='Test Path C migration from database')
    parser.add_argument('--list', action='store_true', help='List all Path C migrations')
    parser.add_argument('--migration-id', type=int, help='Migration ID to test')
    
    args = parser.parse_args()
    
    if args.list:
        asyncio.run(list_path_c_migrations())
    elif args.migration_id:
        asyncio.run(test_path_c_from_database(args.migration_id))
    else:
        print("Usage:")
        print("  List migrations: python test_path_c_from_db.py --list")
        print("  Test migration:  python test_path_c_from_db.py --migration-id <ID>")
