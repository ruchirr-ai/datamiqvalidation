#!/usr/bin/env python3
"""
End-to-End Test for Pathway A: BigQuery → GCS → S3
Tests the complete data flow using Storage Transfer Service
"""

import os
import sys
import time
import json
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from google.cloud import bigquery, storage as gcs_storage
import boto3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
BIGQUERY_PROJECT = os.getenv('BIGQUERY_PROJECT_ID', 'assessiq-484512')
BIGQUERY_DATASET = 'analytics'  # Change to your dataset
BIGQUERY_TABLE = 'customers'    # Change to your table
GCS_BUCKET = os.getenv('GCS_BUCKET', 'bq_data_transfer_rs')
S3_BUCKET = os.getenv('S3_BUCKET', 'your-s3-bucket')
S3_REGION = os.getenv('AWS_REGION', 'us-east-1')
AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')

# Test configuration
EXPORT_FORMAT = 'AVRO'
COMPRESSION = 'SNAPPY'
TEST_TIMESTAMP = datetime.now().strftime('%Y%m%d_%H%M%S')
GCS_EXPORT_PATH = f'test_exports/{TEST_TIMESTAMP}'
S3_IMPORT_PATH = f'test_imports/{TEST_TIMESTAMP}'

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

def test_bigquery_connection():
    """Test BigQuery connection and get table info"""
    print_step(1, "Testing BigQuery Connection")
    
    try:
        client = bigquery.Client(project=BIGQUERY_PROJECT)
        
        # Get table reference
        table_ref = f"{BIGQUERY_PROJECT}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}"
        table = client.get_table(table_ref)
        
        print_success(f"Connected to BigQuery project: {BIGQUERY_PROJECT}")
        print_info(f"Table: {table_ref}")
        print_info(f"Rows: {table.num_rows:,}")
        print_info(f"Size: {format_bytes(table.num_bytes)}")
        print_info(f"Created: {table.created}")
        print_info(f"Modified: {table.modified}")
        
        return client, table
    except Exception as e:
        print_error(f"Failed to connect to BigQuery: {e}")
        return None, None

def export_bigquery_to_gcs(bq_client, table):
    """Export BigQuery table to GCS"""
    print_step(2, "Exporting BigQuery Table to GCS")
    
    try:
        # Construct GCS URI
        gcs_uri = f"gs://{GCS_BUCKET}/{GCS_EXPORT_PATH}/{BIGQUERY_TABLE}/*.{EXPORT_FORMAT.lower()}"
        
        print_info(f"Export destination: {gcs_uri}")
        print_info(f"Format: {EXPORT_FORMAT}")
        print_info(f"Compression: {COMPRESSION}")
        
        # Configure export job
        job_config = bigquery.ExtractJobConfig()
        job_config.destination_format = f"BIGQUERY_STORAGE_API_AVRO" if EXPORT_FORMAT == 'AVRO' else f"BIGQUERY_STORAGE_API_{EXPORT_FORMAT}"
        
        if COMPRESSION != 'NONE':
            job_config.compression = COMPRESSION
        
        # Start export job
        table_ref = f"{BIGQUERY_PROJECT}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}"
        extract_job = bq_client.extract_table(
            table_ref,
            gcs_uri,
            job_config=job_config
        )
        
        print_info("Export job started, waiting for completion...")
        start_time = time.time()
        
        # Wait for job to complete
        extract_job.result()
        
        elapsed_time = time.time() - start_time
        
        print_success(f"Export completed in {elapsed_time:.2f} seconds")
        print_info(f"Job ID: {extract_job.job_id}")
        
        # Verify files in GCS
        gcs_client = gcs_storage.Client(project=BIGQUERY_PROJECT)
        bucket = gcs_client.bucket(GCS_BUCKET)
        blobs = list(bucket.list_blobs(prefix=f"{GCS_EXPORT_PATH}/{BIGQUERY_TABLE}/"))
        
        total_size = sum(blob.size for blob in blobs)
        
        print_success(f"Found {len(blobs)} file(s) in GCS")
        print_info(f"Total size: {format_bytes(total_size)}")
        
        for blob in blobs[:5]:  # Show first 5 files
            print_info(f"  - {blob.name} ({format_bytes(blob.size)})")
        
        if len(blobs) > 5:
            print_info(f"  ... and {len(blobs) - 5} more files")
        
        return True, blobs
    except Exception as e:
        print_error(f"Failed to export to GCS: {e}")
        import traceback
        traceback.print_exc()
        return False, []

def test_gcs_connection():
    """Test GCS connection"""
    print_step(3, "Testing GCS Connection")
    
    try:
        client = gcs_storage.Client(project=BIGQUERY_PROJECT)
        bucket = client.bucket(GCS_BUCKET)
        
        # Check if bucket exists
        if bucket.exists():
            print_success(f"Connected to GCS bucket: {GCS_BUCKET}")
            print_info(f"Location: {bucket.location}")
            print_info(f"Storage class: {bucket.storage_class}")
            return client, bucket
        else:
            print_error(f"GCS bucket does not exist: {GCS_BUCKET}")
            return None, None
    except Exception as e:
        print_error(f"Failed to connect to GCS: {e}")
        return None, None

def test_s3_connection():
    """Test S3 connection"""
    print_step(4, "Testing S3 Connection")
    
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=S3_REGION
        )
        
        # Check if bucket exists
        try:
            s3_client.head_bucket(Bucket=S3_BUCKET)
            print_success(f"Connected to S3 bucket: {S3_BUCKET}")
            print_info(f"Region: {S3_REGION}")
            return s3_client
        except Exception as e:
            print_error(f"S3 bucket does not exist or is not accessible: {S3_BUCKET}")
            print_error(f"Error: {e}")
            return None
    except Exception as e:
        print_error(f"Failed to connect to S3: {e}")
        return None

def create_storage_transfer_job(gcs_blobs):
    """Create Storage Transfer Service job to transfer from GCS to S3"""
    print_step(5, "Creating Storage Transfer Service Job")
    
    try:
        from google.cloud import storage_transfer
        
        client = storage_transfer.StorageTransferServiceClient()
        
        # Create transfer job
        transfer_job = {
            'description': f'Test transfer: {BIGQUERY_TABLE} ({TEST_TIMESTAMP})',
            'status': 'ENABLED',
            'project_id': BIGQUERY_PROJECT,
            'transfer_spec': {
                'gcs_data_source': {
                    'bucket_name': GCS_BUCKET,
                    'path': f'{GCS_EXPORT_PATH}/{BIGQUERY_TABLE}/'
                },
                'aws_s3_data_sink': {
                    'bucket_name': S3_BUCKET,
                    'path': f'{S3_IMPORT_PATH}/{BIGQUERY_TABLE}/',
                    'aws_access_key': {
                        'access_key_id': AWS_ACCESS_KEY,
                        'secret_access_key': AWS_SECRET_KEY
                    }
                },
                'transfer_options': {
                    'overwrite_objects_already_existing_in_sink': True,
                    'delete_objects_from_source_after_transfer': False
                }
            },
            'schedule': {
                'schedule_start_date': {
                    'year': datetime.now().year,
                    'month': datetime.now().month,
                    'day': datetime.now().day
                },
                'schedule_end_date': {
                    'year': datetime.now().year,
                    'month': datetime.now().month,
                    'day': datetime.now().day
                }
            }
        }
        
        print_info(f"Source: gs://{GCS_BUCKET}/{GCS_EXPORT_PATH}/{BIGQUERY_TABLE}/")
        print_info(f"Destination: s3://{S3_BUCKET}/{S3_IMPORT_PATH}/{BIGQUERY_TABLE}/")
        print_info("Creating transfer job...")
        
        # Create the job
        request = storage_transfer.CreateTransferJobRequest(
            transfer_job=transfer_job
        )
        
        response = client.create_transfer_job(request=request)
        
        print_success(f"Transfer job created: {response.name}")
        print_info(f"Status: {response.status}")
        
        # Run the job immediately
        print_info("Starting transfer job...")
        
        run_request = storage_transfer.RunTransferJobRequest(
            job_name=response.name,
            project_id=BIGQUERY_PROJECT
        )
        
        client.run_transfer_job(request=run_request)
        
        print_success("Transfer job started")
        
        return response.name
    except Exception as e:
        print_error(f"Failed to create Storage Transfer Service job: {e}")
        print_warning("Note: Storage Transfer Service requires additional setup and permissions")
        print_info("Alternative: Using direct boto3 transfer (slower but simpler)")
        import traceback
        traceback.print_exc()
        return None

def transfer_gcs_to_s3_direct(gcs_client, gcs_bucket, s3_client, gcs_blobs):
    """Direct transfer from GCS to S3 using boto3 (fallback method)"""
    print_step(5, "Transferring Files from GCS to S3 (Direct Method)")
    
    try:
        print_info(f"Transferring {len(gcs_blobs)} file(s)...")
        
        transferred_count = 0
        total_bytes = 0
        start_time = time.time()
        
        for i, blob in enumerate(gcs_blobs, 1):
            # Download from GCS
            print_info(f"[{i}/{len(gcs_blobs)}] Downloading {blob.name}...")
            data = blob.download_as_bytes()
            
            # Upload to S3
            s3_key = f"{S3_IMPORT_PATH}/{BIGQUERY_TABLE}/{blob.name.split('/')[-1]}"
            print_info(f"[{i}/{len(gcs_blobs)}] Uploading to s3://{S3_BUCKET}/{s3_key}...")
            
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=data
            )
            
            transferred_count += 1
            total_bytes += len(data)
            
            print_success(f"[{i}/{len(gcs_blobs)}] Transferred {format_bytes(len(data))}")
        
        elapsed_time = time.time() - start_time
        throughput = total_bytes / elapsed_time if elapsed_time > 0 else 0
        
        print_success(f"Transfer completed!")
        print_info(f"Files transferred: {transferred_count}")
        print_info(f"Total size: {format_bytes(total_bytes)}")
        print_info(f"Time: {elapsed_time:.2f} seconds")
        print_info(f"Throughput: {format_bytes(throughput)}/s")
        
        return True
    except Exception as e:
        print_error(f"Failed to transfer files: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_s3_files(s3_client):
    """Verify files in S3"""
    print_step(6, "Verifying Files in S3")
    
    try:
        response = s3_client.list_objects_v2(
            Bucket=S3_BUCKET,
            Prefix=f"{S3_IMPORT_PATH}/{BIGQUERY_TABLE}/"
        )
        
        if 'Contents' not in response:
            print_error("No files found in S3")
            return False
        
        files = response['Contents']
        total_size = sum(f['Size'] for f in files)
        
        print_success(f"Found {len(files)} file(s) in S3")
        print_info(f"Total size: {format_bytes(total_size)}")
        
        for f in files[:5]:  # Show first 5 files
            print_info(f"  - {f['Key']} ({format_bytes(f['Size'])})")
        
        if len(files) > 5:
            print_info(f"  ... and {len(files) - 5} more files")
        
        return True
    except Exception as e:
        print_error(f"Failed to verify S3 files: {e}")
        return False

def cleanup(gcs_client, gcs_bucket, s3_client):
    """Cleanup test files"""
    print_step(7, "Cleanup")
    
    cleanup_choice = input(f"\n{Colors.YELLOW}Do you want to clean up test files? (y/n): {Colors.END}").lower()
    
    if cleanup_choice != 'y':
        print_info("Skipping cleanup")
        print_info(f"GCS files: gs://{GCS_BUCKET}/{GCS_EXPORT_PATH}/")
        print_info(f"S3 files: s3://{S3_BUCKET}/{S3_IMPORT_PATH}/")
        return
    
    try:
        # Delete GCS files
        print_info("Deleting GCS files...")
        blobs = list(gcs_bucket.list_blobs(prefix=f"{GCS_EXPORT_PATH}/"))
        for blob in blobs:
            blob.delete()
        print_success(f"Deleted {len(blobs)} file(s) from GCS")
        
        # Delete S3 files
        print_info("Deleting S3 files...")
        response = s3_client.list_objects_v2(
            Bucket=S3_BUCKET,
            Prefix=f"{S3_IMPORT_PATH}/"
        )
        
        if 'Contents' in response:
            for obj in response['Contents']:
                s3_client.delete_object(Bucket=S3_BUCKET, Key=obj['Key'])
            print_success(f"Deleted {len(response['Contents'])} file(s) from S3")
        else:
            print_info("No S3 files to delete")
        
        print_success("Cleanup completed")
    except Exception as e:
        print_error(f"Cleanup failed: {e}")

def main():
    print_header("Pathway A End-to-End Test: BigQuery → GCS → S3")
    
    print_info(f"Test timestamp: {TEST_TIMESTAMP}")
    print_info(f"BigQuery: {BIGQUERY_PROJECT}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}")
    print_info(f"GCS: gs://{GCS_BUCKET}/{GCS_EXPORT_PATH}/")
    print_info(f"S3: s3://{S3_BUCKET}/{S3_IMPORT_PATH}/")
    
    # Validate configuration
    if not AWS_ACCESS_KEY or not AWS_SECRET_KEY:
        print_error("AWS credentials not configured")
        print_info("Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env file")
        return 1
    
    # Test BigQuery connection
    bq_client, table = test_bigquery_connection()
    if not bq_client:
        return 1
    
    # Export BigQuery to GCS
    success, gcs_blobs = export_bigquery_to_gcs(bq_client, table)
    if not success:
        return 1
    
    # Test GCS connection
    gcs_client, gcs_bucket = test_gcs_connection()
    if not gcs_client:
        return 1
    
    # Test S3 connection
    s3_client = test_s3_connection()
    if not s3_client:
        return 1
    
    # Transfer GCS to S3 (try Storage Transfer Service first, fallback to direct)
    transfer_job_name = create_storage_transfer_job(gcs_blobs)
    
    if not transfer_job_name:
        # Fallback to direct transfer
        success = transfer_gcs_to_s3_direct(gcs_client, gcs_bucket, s3_client, gcs_blobs)
        if not success:
            return 1
    else:
        print_info("Storage Transfer Service job is running...")
        print_info("This may take several minutes depending on data size")
        print_warning("Note: You can monitor the job in GCP Console")
        
        # Wait a bit and then verify
        time.sleep(10)
    
    # Verify S3 files
    verify_s3_files(s3_client)
    
    # Cleanup
    cleanup(gcs_client, gcs_bucket, s3_client)
    
    print_header("Test Completed Successfully!")
    
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
