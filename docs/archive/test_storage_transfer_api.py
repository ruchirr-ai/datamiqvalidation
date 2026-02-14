#!/usr/bin/env python3
"""
Test Storage Transfer Service API

Tests GCS to S3 transfer using Google Cloud Storage Transfer Service API
with migration configuration from database.
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime, date

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from google.cloud import storage_transfer_v1
from google.cloud.storage_transfer_v1 import types
from google.oauth2 import service_account
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from models.bq_redshift_migration import MigrationBQRedshift
from models.connection import Connection
from services.encryption_service import get_encryption_service

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

def print_success(text):
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}✗ {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")

def get_database_session():
    """Create database session"""
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    return Session()

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
    
    return migration

def test_storage_transfer_api(migration_id_or_name: str):
    """Test Storage Transfer Service API"""
    print_header("Storage Transfer Service API Test")
    
    # Get database session
    session = get_database_session()
    print_success("Connected to database")
    
    # Get migration
    migration = get_migration_by_id_or_name(session, migration_id_or_name)
    if not migration:
        print_error(f"Migration '{migration_id_or_name}' not found")
        return False
    
    print_info(f"Migration: {migration.migration_name} (ID: {migration.id})")
    print_info(f"Pathway: {migration.pathway}")
    
    # Get source connection for GCS credentials
    source_conn = session.query(Connection).filter_by(id=migration.source_connection_id).first()
    if not source_conn:
        print_error("Source connection not found")
        return False
    
    print_success(f"Source connection: {source_conn.name}")
    
    # Get service account credentials
    connection_params = source_conn.connection_params or {}
    service_account_key = (
        connection_params.get('service_account_key') or 
        connection_params.get('serviceAccountKey') or
        connection_params.get('credentials_json') or
        connection_params.get('credentialsJson')
    )
    
    if not service_account_key:
        print_error("Service account key not found")
        return False
    
    # Parse credentials
    if isinstance(service_account_key, str):
        import json
        credentials_dict = json.loads(service_account_key)
    else:
        credentials_dict = service_account_key
    
    print_success("Service account credentials loaded")
    
    # Get AWS credentials
    aws_access_key = migration.aws_access_key_id
    if not aws_access_key:
        print_error("AWS access key not found in migration")
        return False
    
    # Decrypt AWS secret key
    if not migration.aws_secret_access_key_encrypted:
        print_error("AWS secret key not found in migration")
        return False
    
    try:
        encryption_service = get_encryption_service()
        aws_secret_key = encryption_service.decrypt(migration.aws_secret_access_key_encrypted)
        print_success("AWS secret key decrypted")
    except Exception as e:
        print_error(f"Failed to decrypt AWS secret key: {e}")
        return False
    
    # Clean bucket names
    gcs_bucket = migration.gcs_bucket.replace('gs://', '').strip('/')
    s3_bucket = migration.s3_bucket.replace('s3://', '').strip('/')
    gcs_path = migration.gcs_path.strip('/')
    s3_path = migration.s3_path.strip('/')
    
    print_info(f"Source: gs://{gcs_bucket}/{gcs_path}")
    print_info(f"Destination: s3://{s3_bucket}/{s3_path}")
    print_info(f"Project ID: {migration.source_project_id}")
    
    # Create Storage Transfer Service client
    print_header("Creating Storage Transfer Job")
    
    try:
        # Create credentials
        credentials = service_account.Credentials.from_service_account_info(credentials_dict)
        
        # Create client
        client = storage_transfer_v1.StorageTransferServiceClient(credentials=credentials)
        print_success("Storage Transfer Service client created")
        
        # Get today's date for schedule
        today = date.today()
        
        # Build transfer job
        transfer_job = types.TransferJob(
            description=f"Test Migration {migration.id} - GCS to S3",
            status=types.TransferJob.Status.ENABLED,
            project_id=migration.source_project_id,
            transfer_spec=types.TransferSpec(
                gcs_data_source=types.GcsData(
                    bucket_name=gcs_bucket,
                    path=gcs_path
                ),
                aws_s3_data_sink=types.AwsS3Data(
                    bucket_name=s3_bucket,
                    path=s3_path,
                    aws_access_key=types.AwsAccessKey(
                        access_key_id=aws_access_key,
                        secret_access_key=aws_secret_key
                    )
                ),
                transfer_options=types.TransferOptions(
                    overwrite_objects_already_existing_in_sink=False,
                    delete_objects_from_source_after_transfer=False
                )
            ),
            schedule=types.Schedule(
                schedule_start_date=types.Date(
                    year=today.year,
                    month=today.month,
                    day=today.day
                ),
                schedule_end_date=types.Date(
                    year=today.year,
                    month=today.month,
                    day=today.day
                )
            )
        )
        
        print_info("Transfer job configuration created")
        
        # Create job
        request = types.CreateTransferJobRequest(transfer_job=transfer_job)
        response = client.create_transfer_job(request=request)
        job_name = response.name
        
        print_success(f"Transfer job created: {job_name}")
        
        # Run the job
        print_header("Running Transfer Job")
        
        run_request = types.RunTransferJobRequest(
            job_name=job_name,
            project_id=migration.source_project_id
        )
        
        client.run_transfer_job(request=run_request)
        print_success("Transfer job started")
        
        # Monitor the job
        print_header("Monitoring Transfer Job")
        
        start_time = time.time()
        poll_interval = 10  # Check every 10 seconds
        timeout = 600  # 10 minute timeout
        
        iteration = 0
        while True:
            iteration += 1
            elapsed = time.time() - start_time
            
            if elapsed > timeout:
                print_error(f"Timeout after {timeout}s")
                return False
            
            print_info(f"[Check #{iteration}] Elapsed: {int(elapsed)}s")
            
            # List operations
            filter_str = f'{{"project_id": "{migration.source_project_id}", "job_names": ["{job_name}"]}}'
            
            list_request = types.ListTransferOperationsRequest(
                filter=filter_str,
                page_size=1
            )
            
            operations = list(client.list_transfer_operations(request=list_request))
            
            if not operations:
                print_info(f"[Check #{iteration}] No operations yet, waiting {poll_interval}s...")
                time.sleep(poll_interval)
                continue
            
            operation = operations[0]
            print_info(f"[Check #{iteration}] Operation found, done={operation.done}")
            
            if operation.done:
                if operation.error and operation.error.message:
                    print_error(f"Transfer failed: {operation.error.message}")
                    return False
                else:
                    print_success("Transfer completed!")
                    
                    # Get statistics
                    if hasattr(operation, 'metadata') and operation.metadata:
                        counters = operation.metadata.counters
                        print_header("Transfer Statistics")
                        print_info(f"Objects found: {counters.objects_found_from_source}")
                        print_info(f"Bytes found: {counters.bytes_found_from_source:,}")
                        print_info(f"Objects copied: {counters.objects_copied_to_sink}")
                        print_info(f"Bytes copied: {counters.bytes_copied_to_sink:,}")
                    
                    return True
            else:
                print_info(f"[Check #{iteration}] Still running, waiting {poll_interval}s...")
                time.sleep(poll_interval)
        
    except Exception as e:
        print_error(f"Error: {type(e).__name__}: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return False
    finally:
        session.close()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python test_storage_transfer_api.py <migration_id_or_name>")
        print("Example: python test_storage_transfer_api.py test")
        print("Example: python test_storage_transfer_api.py 9")
        sys.exit(1)
    
    migration_id_or_name = sys.argv[1]
    success = test_storage_transfer_api(migration_id_or_name)
    
    if success:
        print_header("Test Completed Successfully!")
        sys.exit(0)
    else:
        print_header("Test Failed")
        sys.exit(1)
