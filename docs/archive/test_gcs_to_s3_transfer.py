#!/usr/bin/env python3
"""
Test Script for GCS to S3 Transfer

This script tests the GCS to S3 transfer functionality using the
GCP Storage Transfer Service API.

Usage:
    python test_gcs_to_s3_transfer.py
"""

import os
import sys
import json
import logging
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.bq_redshift_migration.gcs_to_s3_transfer import GCSToS3Transfer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_gcs_to_s3_transfer():
    """
    Test GCS to S3 transfer with user-provided credentials.
    """
    print("=" * 80)
    print("GCS to S3 Transfer Test")
    print("=" * 80)
    print()
    
    # Collect configuration from user
    print("Please provide the following information:")
    print()
    
    # GCP Configuration
    print("--- GCP Configuration ---")
    project_id = input("GCP Project ID: ").strip()
    gcs_bucket = input("GCS Bucket (without gs://): ").strip()
    gcs_path = input("GCS Path (e.g., exports/test): ").strip()
    
    print()
    print("--- AWS Configuration ---")
    s3_bucket = input("S3 Bucket (without s3://): ").strip()
    s3_path = input("S3 Path (e.g., imports/test): ").strip()
    aws_access_key_id = input("AWS Access Key ID: ").strip()
    aws_secret_access_key = input("AWS Secret Access Key: ").strip()
    
    print()
    print("--- Transfer Options ---")
    overwrite_input = input("Overwrite existing files? (y/n) [n]: ").strip().lower()
    overwrite_existing = overwrite_input == 'y'
    
    delete_input = input("Delete source after transfer? (y/n) [n]: ").strip().lower()
    delete_source = delete_input == 'y'
    
    print()
    print("=" * 80)
    print("Configuration Summary")
    print("=" * 80)
    print(f"Source: gs://{gcs_bucket}/{gcs_path}")
    print(f"Destination: s3://{s3_bucket}/{s3_path}")
    print(f"Overwrite Existing: {overwrite_existing}")
    print(f"Delete Source: {delete_source}")
    print("=" * 80)
    print()
    
    confirm = input("Proceed with transfer? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Transfer cancelled.")
        return
    
    print()
    print("Starting transfer test...")
    print()
    
    try:
        # Initialize transfer service
        logger.info("Initializing GCS to S3 Transfer Service")
        transfer_service = GCSToS3Transfer()
        
        # Create transfer job
        logger.info("Creating transfer job...")
        job_name = transfer_service.create_transfer_job(
            project_id=project_id,
            gcs_bucket=gcs_bucket,
            gcs_path=gcs_path,
            s3_bucket=s3_bucket,
            s3_path=s3_path,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            description=f"Test Transfer - {datetime.utcnow().isoformat()}",
            overwrite_existing=overwrite_existing,
            delete_source=delete_source
        )
        
        print(f"✓ Transfer job created: {job_name}")
        print()
        
        # Run transfer job
        logger.info("Running transfer job...")
        transfer_service.run_transfer_job(
            project_id=project_id,
            job_name=job_name
        )
        
        print("✓ Transfer job started")
        print()
        print("Monitoring transfer progress...")
        print("(This may take several minutes depending on data size)")
        print()
        
        # Monitor transfer
        result = transfer_service.monitor_transfer_job(
            job_name=job_name,
            project_id=project_id,
            poll_interval=30,
            timeout=3600  # 1 hour
        )
        
        print()
        print("=" * 80)
        print("Transfer Results")
        print("=" * 80)
        
        if result['status'] == 'SUCCESS':
            print("✓ Transfer completed successfully!")
            print()
            
            # Display statistics
            stats = result.get('stats')
            if stats:
                print("Transfer Statistics:")
                print(f"  Objects Found: {stats.get('objects_found', 0):,}")
                print(f"  Bytes Found: {stats.get('bytes_found', 0):,}")
                print(f"  Objects Copied: {stats.get('objects_copied', 0):,}")
                print(f"  Bytes Copied: {stats.get('bytes_copied', 0):,}")
                if stats.get('objects_failed', 0) > 0:
                    print(f"  Objects Failed: {stats.get('objects_failed', 0):,}")
            
            print()
            print(f"Completed At: {result.get('completed_at', 'N/A')}")
            print()
            
            # Cleanup option
            cleanup = input("Delete transfer job? (y/n) [y]: ").strip().lower()
            if cleanup != 'n':
                logger.info("Deleting transfer job...")
                success = transfer_service.delete_transfer_job(
                    project_id=project_id,
                    job_name=job_name
                )
                if success:
                    print("✓ Transfer job deleted")
                else:
                    print("⚠ Failed to delete transfer job")
            
        else:
            print("✗ Transfer failed!")
            print(f"Error: {result.get('error', 'Unknown error')}")
            return False
        
        print("=" * 80)
        return True
        
    except KeyboardInterrupt:
        print()
        print("Transfer interrupted by user")
        return False
        
    except Exception as e:
        logger.error(f"Transfer test failed: {e}", exc_info=True)
        print()
        print("=" * 80)
        print("Transfer Failed")
        print("=" * 80)
        print(f"Error: {str(e)}")
        print()
        print("Please check:")
        print("  1. GCP credentials are configured (GOOGLE_APPLICATION_CREDENTIALS)")
        print("  2. GCS bucket exists and is accessible")
        print("  3. S3 bucket exists and AWS credentials are valid")
        print("  4. AWS credentials have write permissions to S3 bucket")
        print("  5. GCP service account has Storage Transfer permissions")
        print("=" * 80)
        return False


def verify_prerequisites():
    """Verify that required dependencies are installed."""
    print("Checking prerequisites...")
    print()
    
    try:
        from google.cloud import storage_transfer_v1
        print("✓ google-cloud-storage-transfer installed")
    except ImportError:
        print("✗ google-cloud-storage-transfer not installed")
        print("  Install with: uv pip install google-cloud-storage-transfer")
        return False
    
    try:
        from google.oauth2 import service_account
        print("✓ google-auth installed")
    except ImportError:
        print("✗ google-auth not installed")
        print("  Install with: uv pip install google-auth")
        return False
    
    # Check for GCP credentials
    gcp_creds = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if gcp_creds:
        print(f"✓ GOOGLE_APPLICATION_CREDENTIALS set: {gcp_creds}")
    else:
        print("⚠ GOOGLE_APPLICATION_CREDENTIALS not set")
        print("  You'll need to provide service account credentials")
    
    print()
    return True


if __name__ == '__main__':
    print()
    
    # Verify prerequisites
    if not verify_prerequisites():
        print()
        print("Please install missing dependencies and try again.")
        sys.exit(1)
    
    print()
    
    # Run test
    success = test_gcs_to_s3_transfer()
    
    print()
    if success:
        print("✓ Test completed successfully!")
        sys.exit(0)
    else:
        print("✗ Test failed")
        sys.exit(1)
