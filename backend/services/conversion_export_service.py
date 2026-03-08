"""
Conversion Export Service

Service for exporting conversion results to SQL files or ZIP archives.
"""

import logging
import os
import io
import zipfile
from typing import Optional, Dict, Any
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class ExportResult:
    """Result of export operation"""
    
    def __init__(
        self,
        success: bool,
        file_path: Optional[str] = None,
        s3_url: Optional[str] = None,
        file_content: Optional[bytes] = None,
        error_message: Optional[str] = None
    ):
        self.success = success
        self.file_path = file_path
        self.s3_url = s3_url
        self.file_content = file_content
        self.error_message = error_message


class ConversionExportService:
    """
    Service for exporting conversion results to SQL files or ZIP archives.
    Supports local file generation and S3 upload.
    """
    
    def __init__(self):
        """Initialize export service"""
        self.logger = logger
        self.s3_enabled = os.getenv('AWS_S3_EXPORT_ENABLED', 'false').lower() == 'true'
        self.s3_bucket = os.getenv('AWS_S3_EXPORT_BUCKET')
        
        if self.s3_enabled and self.s3_bucket:
            self.s3_client = boto3.client('s3')
        else:
            self.s3_client = None
    
    async def export_single_job(
        self,
        job: Any,
        workspace_id: int
    ) -> ExportResult:
        """
        Export single conversion job to SQL file.
        
        Args:
            job: Conversion job to export
            workspace_id: Workspace identifier
            
        Returns:
            ExportResult with file content or S3 URL
        """
        try:
            if not job.target_code:
                return ExportResult(
                    success=False,
                    error_message="No target code available for export"
                )
            
            # Generate filename
            filename = self._generate_filename(job)
            
            # Create file content
            file_content = job.target_code.encode('utf-8')
            
            # Upload to S3 if enabled
            if self.s3_enabled and self.s3_client:
                s3_url = await self.upload_to_s3(
                    file_content, workspace_id, filename
                )
                return ExportResult(
                    success=True,
                    s3_url=s3_url,
                    file_content=file_content
                )
            
            # Return file content for download
            return ExportResult(
                success=True,
                file_path=filename,
                file_content=file_content
            )
            
        except Exception as e:
            self.logger.error(f"Export failed: {str(e)}")
            return ExportResult(
                success=False,
                error_message=str(e)
            )
    
    async def export_batch(
        self,
        batch: Any,
        jobs: list,
        workspace_id: int
    ) -> ExportResult:
        """
        Export batch conversion to ZIP archive.
        
        Args:
            batch: Conversion batch
            jobs: List of conversion jobs
            workspace_id: Workspace identifier
            
        Returns:
            ExportResult with ZIP file content or S3 URL
        """
        try:
            # Create ZIP archive in memory
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Organize by asset type
                for job in jobs:
                    if job.target_code and job.status == 'completed':
                        # Create subdirectory by asset type
                        filename = self._generate_filename(job)
                        zip_path = f"{job.asset_type}/{filename}"
                        
                        zip_file.writestr(zip_path, job.target_code)
            
            zip_buffer.seek(0)
            file_content = zip_buffer.read()
            
            # Generate ZIP filename
            zip_filename = f"batch_{batch.id}_conversions.zip"
            
            # Upload to S3 if enabled
            if self.s3_enabled and self.s3_client:
                s3_url = await self.upload_to_s3(
                    file_content, workspace_id, zip_filename
                )
                return ExportResult(
                    success=True,
                    s3_url=s3_url,
                    file_content=file_content
                )
            
            # Return ZIP content for download
            return ExportResult(
                success=True,
                file_path=zip_filename,
                file_content=file_content
            )
            
        except Exception as e:
            self.logger.error(f"Batch export failed: {str(e)}")
            return ExportResult(
                success=False,
                error_message=str(e)
            )
    
    async def upload_to_s3(
        self,
        file_content: bytes,
        workspace_id: int,
        file_name: str
    ) -> str:
        """
        Upload file to S3 with workspace-scoped prefix.
        
        Args:
            file_content: File content bytes
            workspace_id: Workspace identifier
            file_name: Destination file name
            
        Returns:
            S3 URL
        """
        try:
            # Workspace-scoped prefix
            s3_key = f"workspace_{workspace_id}/conversions/{file_name}"
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=s3_key,
                Body=file_content,
                ContentType='application/octet-stream'
            )
            
            # Generate S3 URL
            s3_url = f"s3://{self.s3_bucket}/{s3_key}"
            
            self.logger.info(f"Uploaded to S3: {s3_url}")
            
            return s3_url
            
        except ClientError as e:
            self.logger.error(f"S3 upload failed: {str(e)}")
            raise
    
    def _generate_filename(self, job: Any) -> str:
        """Generate filename for conversion job"""
        # Use asset name if available
        if job.asset_name:
            base_name = job.asset_name
        else:
            base_name = f"conversion_{job.id}"
        
        # Add appropriate extension
        extension = self._get_file_extension(job.target_dialect)
        
        return f"{base_name}.{extension}"
    
    def _get_file_extension(self, dialect: str) -> str:
        """Get file extension for dialect"""
        extensions = {
            'postgres': 'sql',
            'mysql': 'sql',
            'redshift': 'sql',
            'bigquery': 'sql',
            'snowflake': 'sql',
            'oracle': 'sql',
            'mssql': 'sql'
        }
        return extensions.get(dialect.lower(), 'sql')

    def _generate_filename(self, job: Any) -> str:
        """Generate filename for conversion job"""
        # Use asset name if available
        if job.asset_name:
            base_name = job.asset_name.replace(' ', '_').replace('/', '_')
        else:
            base_name = f"conversion_{job.id}"
        
        # Add dialect suffix
        base_name = f"{base_name}_{job.target_dialect}"
        
        # Add appropriate extension
        extension = self._get_file_extension(job.target_dialect)
        
        return f"{base_name}.{extension}"
    
    def _get_file_extension(self, dialect: str) -> str:
        """Get file extension for dialect"""
        return 'sql'
