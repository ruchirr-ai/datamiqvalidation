"""
GCS to S3 Transfer using Download and Upload Approach

Simple, reliable implementation:
- Downloads files from GCS
- Uploads files to S3
- Proper error handling
- Progress tracking
- Detailed logging with transfer speed and ETA
"""

import logging
import os
import tempfile
import time
from typing import Dict, Optional
from datetime import datetime, timedelta
from google.cloud import storage as gcs_storage
from google.oauth2 import service_account
import boto3

logger = logging.getLogger(__name__)


class GCSToS3Transfer:
    """Handles GCS to S3 transfers using download and upload approach"""
    
    def __init__(self, gcp_credentials_dict: Optional[Dict] = None):
        """
        Initialize GCS to S3 Transfer service.
        
        Args:
            gcp_credentials_dict: GCP service account credentials dictionary
        """
        self.gcs_client = None
        self.s3_client = None
        self.gcp_credentials_dict = gcp_credentials_dict
    
    def _get_gcs_client(self):
        """Lazy initialization of GCS client"""
        if not self.gcs_client:
            if self.gcp_credentials_dict:
                credentials = service_account.Credentials.from_service_account_info(
                    self.gcp_credentials_dict
                )
                self.gcs_client = gcs_storage.Client(credentials=credentials)
                logger.info("✓ GCS client initialized with service account credentials")
            else:
                self.gcs_client = gcs_storage.Client()
                logger.info("✓ GCS client initialized with default credentials")
        return self.gcs_client
    
    def _get_s3_client(self, aws_access_key_id: str, aws_secret_access_key: str):
        """Initialize S3 client with provided credentials"""
        if not self.s3_client:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key
            )
            logger.info("✓ S3 client initialized with provided credentials")
        return self.s3_client
    
    def _format_bytes(self, bytes_val: int) -> str:
        """Format bytes to human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.2f} {unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.2f} PB"
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration to human-readable format"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"
    
    def transfer_files(
        self,
        gcs_bucket: str,
        gcs_path: str,
        s3_bucket: str,
        s3_path: str,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        delete_source: bool = False
    ) -> Dict:
        """
        Transfer files from GCS to S3 using download and upload approach.
        
        Args:
            gcs_bucket: Source GCS bucket name (without gs://)
            gcs_path: Path within GCS bucket
            s3_bucket: Target S3 bucket name (without s3://)
            s3_path: Path within S3 bucket
            aws_access_key_id: AWS access key
            aws_secret_access_key: AWS secret key
            delete_source: Whether to delete source files after transfer
            
        Returns:
            Dictionary with transfer statistics
        """
        transfer_start_time = time.time()
        
        try:
            logger.info("="*80)
            logger.info("STARTING GCS TO S3 TRANSFER")
            logger.info("="*80)
            
            # Clean bucket names - remove any gs:// or gs::// prefixes
            original_gcs_bucket = gcs_bucket
            while gcs_bucket.startswith('gs://') or gcs_bucket.startswith('gs:://'):
                if gcs_bucket.startswith('gs:://'):
                    gcs_bucket = gcs_bucket[6:]  # Remove 'gs::/'
                elif gcs_bucket.startswith('gs://'):
                    gcs_bucket = gcs_bucket[5:]  # Remove 'gs://'
            # Also handle any remaining gs: prefix
            if gcs_bucket.startswith('gs:'):
                gcs_bucket = gcs_bucket[3:]
            # Remove any leading slashes or colons
            gcs_bucket = gcs_bucket.lstrip('/:').strip()
            
            if original_gcs_bucket != gcs_bucket:
                logger.info(f"Cleaned GCS bucket: '{original_gcs_bucket}' → '{gcs_bucket}'")
            
            # Clean S3 bucket name - remove s3:// prefix if present
            original_s3_bucket = s3_bucket
            while s3_bucket.startswith('s3://'):
                s3_bucket = s3_bucket[5:]
            s3_bucket = s3_bucket.strip().strip('/')
            
            if original_s3_bucket != s3_bucket:
                logger.info(f"Cleaned S3 bucket: '{original_s3_bucket}' → '{s3_bucket}'")
            
            # Initialize clients
            gcs_client = self._get_gcs_client()
            s3_client = self._get_s3_client(aws_access_key_id, aws_secret_access_key)
            
            logger.info(f"Source: gs://{gcs_bucket}/{gcs_path}")
            logger.info(f"Destination: s3://{s3_bucket}/{s3_path}")
            logger.info(f"Delete source after transfer: {delete_source}")
            logger.info("="*80)
            
            # Get GCS bucket
            bucket = gcs_client.bucket(gcs_bucket)
            
            # List all blobs in the path
            logger.info(f"📋 Listing files in gs://{gcs_bucket}/{gcs_path}...")
            list_start = time.time()
            blobs = list(bucket.list_blobs(prefix=gcs_path))
            list_duration = time.time() - list_start
            
            # Filter out directories
            file_blobs = [b for b in blobs if not b.name.endswith('/')]
            
            if not file_blobs:
                logger.warning(f"⚠️  No files found in gs://{gcs_bucket}/{gcs_path}")
                return {
                    'status': 'SUCCESS',
                    'files_found': 0,
                    'files_transferred': 0,
                    'bytes_transferred': 0,
                    'files_failed': 0,
                    'duration_seconds': time.time() - transfer_start_time,
                    'completed_at': datetime.utcnow().isoformat()
                }
            
            # Calculate total size
            total_size = sum(blob.size for blob in file_blobs)
            
            logger.info(f"✓ Found {len(file_blobs)} files to transfer")
            logger.info(f"✓ Total size: {self._format_bytes(total_size)}")
            logger.info(f"✓ Listing completed in {list_duration:.2f}s")
            logger.info("="*80)
            
            # Transfer statistics
            files_transferred = 0
            bytes_transferred = 0
            files_failed = 0
            failed_files = []
            
            # Create temp directory for downloads
            with tempfile.TemporaryDirectory() as temp_dir:
                logger.info(f"📁 Using temporary directory: {temp_dir}")
                logger.info("="*80)
                
                for i, blob in enumerate(file_blobs, 1):
                    file_start_time = time.time()
                    
                    try:
                        # Calculate progress
                        progress_pct = (i / len(file_blobs)) * 100
                        
                        logger.info(f"")
                        logger.info(f"📦 FILE {i}/{len(file_blobs)} ({progress_pct:.1f}% complete)")
                        logger.info(f"   Name: {blob.name}")
                        logger.info(f"   Size: {self._format_bytes(blob.size)}")
                        
                        # Download from GCS
                        local_file = os.path.join(temp_dir, os.path.basename(blob.name))
                        download_start = time.time()
                        logger.info(f"   ⬇️  Downloading from GCS...")
                        blob.download_to_filename(local_file)
                        download_duration = time.time() - download_start
                        file_size = os.path.getsize(local_file)
                        download_speed = file_size / download_duration if download_duration > 0 else 0
                        
                        logger.info(f"   ✓ Downloaded {self._format_bytes(file_size)} in {download_duration:.2f}s")
                        logger.info(f"   ✓ Download speed: {self._format_bytes(download_speed)}/s")
                        
                        # Upload to S3
                        # Construct S3 key maintaining the directory structure
                        relative_path = blob.name[len(gcs_path):].lstrip('/')
                        s3_key = f"{s3_path}/{relative_path}".strip('/')
                        
                        upload_start = time.time()
                        logger.info(f"   ⬆️  Uploading to S3: s3://{s3_bucket}/{s3_key}")
                        s3_client.upload_file(local_file, s3_bucket, s3_key)
                        upload_duration = time.time() - upload_start
                        upload_speed = file_size / upload_duration if upload_duration > 0 else 0
                        
                        logger.info(f"   ✓ Uploaded {self._format_bytes(file_size)} in {upload_duration:.2f}s")
                        logger.info(f"   ✓ Upload speed: {self._format_bytes(upload_speed)}/s")
                        
                        # Delete source if requested
                        if delete_source:
                            logger.info(f"   🗑️  Deleting source file from GCS...")
                            blob.delete()
                            logger.info(f"   ✓ Source file deleted")
                        
                        # Update statistics
                        files_transferred += 1
                        bytes_transferred += file_size
                        
                        # Calculate overall progress
                        file_duration = time.time() - file_start_time
                        elapsed_time = time.time() - transfer_start_time
                        avg_time_per_file = elapsed_time / i
                        remaining_files = len(file_blobs) - i
                        eta_seconds = avg_time_per_file * remaining_files
                        
                        overall_speed = bytes_transferred / elapsed_time if elapsed_time > 0 else 0
                        
                        logger.info(f"   ✓ File transfer completed in {file_duration:.2f}s")
                        logger.info(f"")
                        logger.info(f"📊 PROGRESS SUMMARY:")
                        logger.info(f"   Files: {files_transferred}/{len(file_blobs)} ({progress_pct:.1f}%)")
                        logger.info(f"   Data: {self._format_bytes(bytes_transferred)}/{self._format_bytes(total_size)}")
                        logger.info(f"   Speed: {self._format_bytes(overall_speed)}/s")
                        logger.info(f"   Elapsed: {self._format_duration(elapsed_time)}")
                        if remaining_files > 0:
                            logger.info(f"   ETA: {self._format_duration(eta_seconds)} ({remaining_files} files remaining)")
                        logger.info(f"-" * 80)
                        
                    except Exception as e:
                        files_failed += 1
                        failed_files.append({
                            'file': blob.name,
                            'error': str(e)
                        })
                        logger.error(f"   ✗ Failed to transfer {blob.name}: {e}")
                        logger.error(f"-" * 80)
                        continue
            
            # Calculate final statistics
            total_duration = time.time() - transfer_start_time
            avg_speed = bytes_transferred / total_duration if total_duration > 0 else 0
            success_rate = (files_transferred / len(file_blobs) * 100) if file_blobs else 0
            
            logger.info("")
            logger.info("="*80)
            logger.info("✓ TRANSFER COMPLETE")
            logger.info("="*80)
            logger.info(f"📊 FINAL STATISTICS:")
            logger.info(f"   Files found: {len(file_blobs)}")
            logger.info(f"   Files transferred: {files_transferred}")
            logger.info(f"   Files failed: {files_failed}")
            logger.info(f"   Success rate: {success_rate:.1f}%")
            logger.info(f"   Data transferred: {self._format_bytes(bytes_transferred)}")
            logger.info(f"   Total duration: {self._format_duration(total_duration)}")
            logger.info(f"   Average speed: {self._format_bytes(avg_speed)}/s")
            
            if files_failed > 0:
                logger.warning(f"")
                logger.warning(f"⚠️  FAILED FILES ({files_failed}):")
                for failed in failed_files[:5]:  # Show first 5 failures
                    logger.warning(f"   - {failed['file']}: {failed['error']}")
                if len(failed_files) > 5:
                    logger.warning(f"   ... and {len(failed_files) - 5} more")
            
            logger.info("="*80)
            
            return {
                'status': 'SUCCESS' if files_failed == 0 else 'PARTIAL_SUCCESS',
                'files_found': len(file_blobs),
                'files_transferred': files_transferred,
                'bytes_transferred': bytes_transferred,
                'files_failed': files_failed,
                'failed_files': failed_files,
                'duration_seconds': total_duration,
                'average_speed_bytes_per_sec': avg_speed,
                'success_rate_percent': success_rate,
                'completed_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            total_duration = time.time() - transfer_start_time
            logger.error("="*80)
            logger.error("✗ TRANSFER FAILED")
            logger.error("="*80)
            logger.error(f"Error: {e}")
            logger.error(f"Duration before failure: {self._format_duration(total_duration)}")
            logger.error("="*80)
            
            import traceback
            logger.error(traceback.format_exc())
            
            return {
                'status': 'FAILED',
                'error': str(e),
                'duration_seconds': total_duration,
                'completed_at': datetime.utcnow().isoformat()
            }
