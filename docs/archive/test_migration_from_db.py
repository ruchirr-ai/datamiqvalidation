#!/usr/bin/env python3
"""
Test Migration Using Database Parameters
Fetches migration configuration from database and runs end-to-end test
"""

import os
import sys
import time
import json
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from google.cloud import bigquery, storage as gcs_storage
import boto3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import models
from models.bq_redshift_migration import MigrationBQRedshift
from models.connection import Connection

# Import encryption service
from services.encryption_service import EncryptionService

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://manasakallakuri@localhost/datamiq')

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(80)}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.END}\n")

def print_step(step_num, text):
    print(f"{Colors.CYAN}{Colors.BOLD}[Step {step_num}]{Colors.END} {text}")

def print_success(text):
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}✗ {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")

def format_bytes(bytes_val):
    """Format bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024.0:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.2f} PB"

def get_database_session():
    """Create database session"""
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    return Session()

def list_migrations(session):
    """List all migrations in database"""
    migrations = session.query(MigrationBQRedshift).all()
    
    if not migrations:
        print_warning("No migrations found in database")
        return []
    
    print_info(f"Found {len(migrations)} migration(s):\n")
    
    for i, mig in enumerate(migrations, 1):
        status_color = Colors.GREEN if mig.status == 'completed' else Colors.YELLOW if mig.status == 'pending' else Colors.RED
        print(f"  {i}. {Colors.BOLD}{mig.migration_name}{Colors.END}")
        print(f"     ID: {mig.id}")
        print(f"     Status: {status_color}{mig.status}{Colors.END}")
        print(f"     Pathway: {mig.pathway}")
        print(f"     Dataset: {mig.source_dataset}")
        print(f"     Tables: {', '.join(mig.source_tables[:3])}{' ...' if len(mig.source_tables) > 3 else ''}")
        print(f"     Created: {mig.created_at}")
        print()
    
    return migrations

def get_migration_by_id_or_name(session, identifier):
    """Get migration by ID or name"""
    # Try as ID first
    try:
        migration_id = int(identifier)
        migration = session.query(MigrationBQRedshift).filter(
            MigrationBQRedshift.id == migration_id
        ).first()
        
        if migration:
            return migration
    except ValueError:
        pass
    
    # Try as name
    migration = session.query(MigrationBQRedshift).filter(
        MigrationBQRedshift.migration_name == identifier
    ).first()
    
    if not migration:
        print_error(f"Migration with ID or name '{identifier}' not found")
        return None
    
    return migration

def get_connection_details(session, connection_id):
    """Get connection details"""
    connection = session.query(Connection).filter(
        Connection.id == connection_id
    ).first()
    
    if not connection:
        print_error(f"Connection with ID {connection_id} not found")
        return None
    
    return connection

def display_migration_config(migration, source_conn, target_conn):
    """Display migration configuration"""
    print_header("Migration Configuration")
    
    print(f"{Colors.BOLD}Migration Details:{Colors.END}")
    print(f"  Name: {migration.migration_name}")
    print(f"  ID: {migration.id}")
    print(f"  Pathway: {migration.pathway}")
    print(f"  Status: {migration.status}")
    print()
    
    print(f"{Colors.BOLD}Source (BigQuery):{Colors.END}")
    print(f"  Connection: {source_conn.name if source_conn else 'Unknown'}")
    print(f"  Project: {migration.source_project_id}")
    print(f"  Dataset: {migration.source_dataset}")
    print(f"  Tables: {len(migration.source_tables)} table(s)")
    for table in migration.source_tables[:5]:
        print(f"    - {table}")
    if len(migration.source_tables) > 5:
        print(f"    ... and {len(migration.source_tables) - 5} more")
    print()
    
    print(f"{Colors.BOLD}Storage Configuration:{Colors.END}")
    print(f"  GCS Bucket: {migration.gcs_bucket}")
    print(f"  GCS Path: {migration.gcs_path}")
    print(f"  S3 Bucket: {migration.s3_bucket}")
    print(f"  S3 Path: {migration.s3_path}")
    print(f"  Export Format: {migration.export_format}")
    print(f"  Compression: {migration.compression}")
    print()
    
    print(f"{Colors.BOLD}Target (Redshift):{Colors.END}")
    print(f"  Connection: {target_conn.name if target_conn else 'Unknown'}")
    print(f"  Cluster: {migration.target_cluster}")
    print(f"  Database: {migration.target_database}")
    print(f"  Schema: {migration.target_schema}")
    print()

def test_bigquery_export(migration, source_conn):
    """Test BigQuery export for first table"""
    print_step(1, "Testing BigQuery Export")
    
    try:
        # Get service account credentials from connection
        if not source_conn or not source_conn.connection_params:
            print_error("Source connection or credentials not found")
            return False, [], None, None, None
        
        # Try different possible keys for credentials
        service_account_info = (
            source_conn.connection_params.get('credentials_json') or
            source_conn.connection_params.get('service_account_json') or
            source_conn.connection_params.get('credentials')
        )
        
        if not service_account_info:
            print_error("Service account credentials not found in connection")
            print_info("Connection params keys: " + str(source_conn.connection_params.keys()))
            return False, [], None, None, None
        
        # Parse service account JSON if it's a string
        if isinstance(service_account_info, str):
            import json
            service_account_info = json.loads(service_account_info)
        
        # Create credentials from service account info
        from google.oauth2 import service_account
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=['https://www.googleapis.com/auth/bigquery', 
                   'https://www.googleapis.com/auth/cloud-platform']
        )
        
        # Create BigQuery client with credentials
        client = bigquery.Client(
            project=migration.source_project_id,
            credentials=credentials
        )
        
        # Test with first table
        test_table = migration.source_tables[0]
        table_ref = f"{migration.source_project_id}.{migration.source_dataset}.{test_table}"
        
        print_info(f"Testing with table: {table_ref}")
        
        # Get table metadata
        table = client.get_table(table_ref)
        
        print_success(f"Connected to BigQuery")
        print_info(f"Table: {table_ref}")
        print_info(f"Rows: {table.num_rows:,}")
        print_info(f"Size: {format_bytes(table.num_bytes)}")
        
        # Construct GCS URI
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Clean bucket name (remove gs:// prefix if present)
        gcs_bucket_clean = migration.gcs_bucket.replace('gs://', '')
        gcs_path_clean = migration.gcs_path.lstrip('/')
        
        gcs_uri = f"gs://{gcs_bucket_clean}/{gcs_path_clean}/test_{timestamp}/{test_table}/*.{migration.export_format.lower()}"
        
        print_info(f"Export destination: {gcs_uri}")
        print_info(f"Format: {migration.export_format}")
        print_info(f"Compression: {migration.compression}")
        
        # Configure export job
        job_config = bigquery.ExtractJobConfig()
        job_config.destination_format = f"BIGQUERY_STORAGE_API_AVRO" if migration.export_format == 'AVRO' else f"BIGQUERY_STORAGE_API_{migration.export_format}"
        
        if migration.compression and migration.compression != 'NONE':
            job_config.compression = migration.compression
        
        # Start export job
        print_info("Starting export job...")
        start_time = time.time()
        
        extract_job = client.extract_table(
            table_ref,
            gcs_uri,
            job_config=job_config
        )
        
        # Wait for job to complete
        extract_job.result()
        
        elapsed_time = time.time() - start_time
        
        print_success(f"Export completed in {elapsed_time:.2f} seconds")
        print_info(f"Job ID: {extract_job.job_id}")
        
        # Verify files in GCS
        gcs_client = gcs_storage.Client(
            project=migration.source_project_id,
            credentials=credentials
        )
        bucket = gcs_client.bucket(gcs_bucket_clean)
        prefix = f"{gcs_path_clean}/test_{timestamp}/{test_table}/"
        blobs = list(bucket.list_blobs(prefix=prefix))
        
        total_size = sum(blob.size for blob in blobs)
        
        print_success(f"Found {len(blobs)} file(s) in GCS")
        print_info(f"Total size: {format_bytes(total_size)}")
        
        for blob in blobs[:3]:
            print_info(f"  - {blob.name} ({format_bytes(blob.size)})")
        
        if len(blobs) > 3:
            print_info(f"  ... and {len(blobs) - 3} more files")
        
        return True, blobs, gcs_client, bucket, timestamp
    except Exception as e:
        print_error(f"Failed to export from BigQuery: {e}")
        import traceback
        traceback.print_exc()
        return False, [], None, None, None

def test_gcs_to_s3_transfer(migration, gcs_client, gcs_bucket, blobs, timestamp):
    """Test GCS to S3 transfer"""
    print_step(2, "Testing GCS to S3 Transfer")
    
    try:
        # Clean bucket names
        s3_bucket_clean = migration.s3_bucket.replace('s3://', '')
        s3_path_clean = migration.s3_path.lstrip('/')
        
        # Get AWS credentials from migration
        aws_access_key = migration.aws_access_key_id
        
        if not aws_access_key:
            print_error("AWS access key not found in migration config")
            return False, None, None
        
        # Decrypt AWS secret key
        if migration.aws_secret_access_key_encrypted:
            try:
                encryption_service = EncryptionService()
                aws_secret_key = encryption_service.decrypt(migration.aws_secret_access_key_encrypted)
                print_success("Decrypted AWS secret key from database")
            except Exception as e:
                print_error(f"Failed to decrypt AWS secret key: {e}")
                return False, None, None
        else:
            print_error("AWS secret key not found in migration config")
            return False, None, None
        
        # Create S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name='us-east-1'
        )
        
        # Verify S3 bucket access
        try:
            s3_client.head_bucket(Bucket=s3_bucket_clean)
            print_success(f"Connected to S3 bucket: {s3_bucket_clean}")
        except Exception as e:
            print_error(f"Cannot access S3 bucket: {e}")
            return False
        
        # Transfer files
        print_info(f"Transferring {len(blobs)} file(s) from GCS to S3...")
        
        transferred_count = 0
        total_bytes = 0
        start_time = time.time()
        
        test_table = migration.source_tables[0]
        
        for i, blob in enumerate(blobs, 1):
            # Download from GCS
            print_info(f"[{i}/{len(blobs)}] Downloading {blob.name}...")
            data = blob.download_as_bytes()
            
            # Upload to S3
            s3_key = f"{s3_path_clean}/test_{timestamp}/{test_table}/{blob.name.split('/')[-1]}"
            print_info(f"[{i}/{len(blobs)}] Uploading to s3://{s3_bucket_clean}/{s3_key}...")
            
            s3_client.put_object(
                Bucket=s3_bucket_clean,
                Key=s3_key,
                Body=data
            )
            
            transferred_count += 1
            total_bytes += len(data)
            
            print_success(f"[{i}/{len(blobs)}] Transferred {format_bytes(len(data))}")
        
        elapsed_time = time.time() - start_time
        throughput = total_bytes / elapsed_time if elapsed_time > 0 else 0
        
        print_success(f"Transfer completed!")
        print_info(f"Files transferred: {transferred_count}")
        print_info(f"Total size: {format_bytes(total_bytes)}")
        print_info(f"Time: {elapsed_time:.2f} seconds")
        print_info(f"Throughput: {format_bytes(throughput)}/s")
        
        # Verify files in S3
        print_info("Verifying files in S3...")
        response = s3_client.list_objects_v2(
            Bucket=s3_bucket_clean,
            Prefix=f"{s3_path_clean}/test_{timestamp}/"
        )
        
        if 'Contents' in response:
            s3_files = response['Contents']
            s3_total_size = sum(f['Size'] for f in s3_files)
            
            print_success(f"Found {len(s3_files)} file(s) in S3")
            print_info(f"Total size: {format_bytes(s3_total_size)}")
        else:
            print_warning("No files found in S3")
        
        return True, s3_client, timestamp
    except Exception as e:
        print_error(f"Failed to transfer to S3: {e}")
        import traceback
        traceback.print_exc()
        return False, None, None

def cleanup_test_files(migration, gcs_client, gcs_bucket, s3_client, timestamp):
    """Cleanup test files"""
    print_step(3, "Cleanup Test Files")
    
    cleanup_choice = input(f"\n{Colors.YELLOW}Do you want to clean up test files? (y/n): {Colors.END}").lower()
    
    if cleanup_choice != 'y':
        gcs_bucket_clean = migration.gcs_bucket.replace('gs://', '')
        gcs_path_clean = migration.gcs_path.lstrip('/')
        s3_bucket_clean = migration.s3_bucket.replace('s3://', '')
        s3_path_clean = migration.s3_path.lstrip('/')
        
        print_info("Skipping cleanup")
        print_info(f"GCS files: gs://{gcs_bucket_clean}/{gcs_path_clean}/test_{timestamp}/")
        print_info(f"S3 files: s3://{s3_bucket_clean}/{s3_path_clean}/test_{timestamp}/")
        return
    
    try:
        gcs_bucket_clean = migration.gcs_bucket.replace('gs://', '')
        gcs_path_clean = migration.gcs_path.lstrip('/')
        s3_bucket_clean = migration.s3_bucket.replace('s3://', '')
        s3_path_clean = migration.s3_path.lstrip('/')
        
        # Delete GCS files
        print_info("Deleting GCS files...")
        prefix = f"{gcs_path_clean}/test_{timestamp}/"
        blobs = list(gcs_bucket.list_blobs(prefix=prefix))
        for blob in blobs:
            blob.delete()
        print_success(f"Deleted {len(blobs)} file(s) from GCS")
        
        # Delete S3 files
        if s3_client:
            print_info("Deleting S3 files...")
            response = s3_client.list_objects_v2(
                Bucket=s3_bucket_clean,
                Prefix=f"{s3_path_clean}/test_{timestamp}/"
            )
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    s3_client.delete_object(Bucket=s3_bucket_clean, Key=obj['Key'])
                print_success(f"Deleted {len(response['Contents'])} file(s) from S3")
            else:
                print_info("No S3 files to delete")
        
        print_success("Cleanup completed")
    except Exception as e:
        print_error(f"Cleanup failed: {e}")

def main():
    print_header("Test Migration Using Database Parameters")
    
    # Create database session
    try:
        session = get_database_session()
        print_success("Connected to database")
    except Exception as e:
        print_error(f"Failed to connect to database: {e}")
        return 1
    
    # List migrations
    migrations = list_migrations(session)
    
    if not migrations:
        print_error("No migrations found. Please create a migration first.")
        return 1
    
    # Get migration ID or name from user
    identifier = input(f"\n{Colors.CYAN}Enter migration ID or name to test: {Colors.END}").strip()
    
    if not identifier:
        print_error("No migration ID or name provided")
        return 1
    
    # Get migration details
    migration = get_migration_by_id_or_name(session, identifier)
    if not migration:
        return 1
    
    # Get connection details
    source_conn = get_connection_details(session, migration.source_connection_id)
    target_conn = get_connection_details(session, migration.target_connection_id)
    
    # Display configuration
    display_migration_config(migration, source_conn, target_conn)
    
    # Confirm test
    confirm = input(f"\n{Colors.YELLOW}Run test with this configuration? (y/n): {Colors.END}").lower()
    if confirm != 'y':
        print_info("Test cancelled")
        return 0
    
    # Test BigQuery export
    success, blobs, gcs_client, gcs_bucket, timestamp = test_bigquery_export(migration, source_conn)
    if not success:
        return 1
    
    # Test GCS to S3 transfer
    success, s3_client, timestamp = test_gcs_to_s3_transfer(migration, gcs_client, gcs_bucket, blobs, timestamp)
    if not success:
        return 1
    
    # Cleanup
    cleanup_test_files(migration, gcs_client, gcs_bucket, s3_client, timestamp)
    
    print_header("Test Completed Successfully!")
    
    print_success("All stages completed successfully:")
    print_info("  ✓ BigQuery export to GCS")
    print_info("  ✓ GCS to S3 transfer")
    print_info("  ✓ File verification")
    print()
    print_info("Your migration configuration is working correctly!")
    print_info("You can now run the actual migration from the UI.")
    
    return 0

if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Test interrupted by user{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
