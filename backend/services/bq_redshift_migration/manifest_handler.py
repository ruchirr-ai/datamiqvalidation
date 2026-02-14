"""
Manifest Handler for BigQuery to Redshift Migrations

Handles manifest file creation, parsing, and shard tracking.
Manifest files are the key to granular resume functionality.
"""

import json
import logging
from typing import Dict, List
from datetime import datetime
from google.cloud import storage as gcs_storage
import boto3

logger = logging.getLogger(__name__)


class ManifestHandler:
    """
    Manages manifest files for tracking BigQuery export shards.
    
    Manifest files contain metadata about all exported shards, enabling:
    - Precise tracking of which shards have been processed
    - Validation of data integrity via checksums
    - Resume from any point in the pipeline
    """
    
    def __init__(self):
        self.gcs_client = None
        self.s3_client = None
    
    def _get_gcs_client(self):
        """Lazy initialization of GCS client"""
        if not self.gcs_client:
            self.gcs_client = gcs_storage.Client()
        return self.gcs_client
    
    def _get_s3_client(self):
        """Lazy initialization of S3 client"""
        if not self.s3_client:
            self.s3_client = boto3.client('s3')
        return self.s3_client
    
    def create_manifest(
        self,
        migration_id: int,
        source_config: Dict,
        shards: List[Dict]
    ) -> Dict:
        """
        Create a manifest file for a migration.
        
        Args:
            migration_id: Migration ID
            source_config: Source configuration (project, dataset, tables)
            shards: List of shard metadata dictionaries
            
        Returns:
            Manifest dictionary
        """
        manifest = {
            'version': '1.0',
            'migration_id': migration_id,
            'created_at': datetime.utcnow().isoformat(),
            'source': source_config,
            'shards': shards,
            'metadata': {
                'total_shards': len(shards),
                'total_size_bytes': sum(s.get('size_bytes', 0) for s in shards),
                'total_rows': sum(s.get('row_count', 0) for s in shards)
            }
        }
        
        logger.info(
            f"Created manifest for migration {migration_id} with {len(shards)} shards",
            extra={
                'migration_id': migration_id,
                'total_shards': len(shards),
                'total_size_bytes': manifest['metadata']['total_size_bytes']
            }
        )
        
        return manifest
    
    def save_manifest_to_gcs(
        self,
        manifest: Dict,
        bucket: str,
        path: str
    ) -> str:
        """
        Save manifest file to Google Cloud Storage.
        
        Args:
            manifest: Manifest dictionary
            bucket: GCS bucket name
            path: Path within bucket
            
        Returns:
            GCS URI of saved manifest
        """
        try:
            client = self._get_gcs_client()
            bucket_obj = client.bucket(bucket)
            
            manifest_path = f"{path}/manifest.json"
            blob = bucket_obj.blob(manifest_path)
            
            manifest_json = json.dumps(manifest, indent=2)
            blob.upload_from_string(
                manifest_json,
                content_type='application/json'
            )
            
            uri = f"gs://{bucket}/{manifest_path}"
            
            logger.info(
                f"Saved manifest to GCS: {uri}",
                extra={'uri': uri, 'size_bytes': len(manifest_json)}
            )
            
            return uri
            
        except Exception as e:
            logger.error(f"Failed to save manifest to GCS: {e}")
            raise
    
    def save_manifest_to_s3(
        self,
        manifest: Dict,
        bucket: str,
        path: str
    ) -> str:
        """
        Save manifest file to AWS S3.
        
        Args:
            manifest: Manifest dictionary
            bucket: S3 bucket name
            path: Path within bucket
            
        Returns:
            S3 URI of saved manifest
        """
        try:
            client = self._get_s3_client()
            
            manifest_path = f"{path}/manifest.json"
            manifest_json = json.dumps(manifest, indent=2)
            
            client.put_object(
                Bucket=bucket,
                Key=manifest_path,
                Body=manifest_json.encode('utf-8'),
                ContentType='application/json'
            )
            
            uri = f"s3://{bucket}/{manifest_path}"
            
            logger.info(
                f"Saved manifest to S3: {uri}",
                extra={'uri': uri, 'size_bytes': len(manifest_json)}
            )
            
            return uri
            
        except Exception as e:
            logger.error(f"Failed to save manifest to S3: {e}")
            raise
    
    def load_manifest_from_gcs(self, uri: str) -> Dict:
        """
        Load manifest file from Google Cloud Storage.
        
        Args:
            uri: GCS URI (gs://bucket/path/manifest.json)
            
        Returns:
            Manifest dictionary
        """
        try:
            # Parse URI
            if not uri.startswith('gs://'):
                raise ValueError(f"Invalid GCS URI: {uri}")
            
            parts = uri[5:].split('/', 1)
            bucket = parts[0]
            path = parts[1] if len(parts) > 1 else ''
            
            client = self._get_gcs_client()
            bucket_obj = client.bucket(bucket)
            blob = bucket_obj.blob(path)
            
            manifest_json = blob.download_as_text()
            manifest = json.loads(manifest_json)
            
            logger.info(
                f"Loaded manifest from GCS: {uri}",
                extra={'uri': uri, 'total_shards': len(manifest.get('shards', []))}
            )
            
            return manifest
            
        except Exception as e:
            logger.error(f"Failed to load manifest from GCS: {e}")
            raise
    
    def load_manifest_from_s3(self, uri: str) -> Dict:
        """
        Load manifest file from AWS S3.
        
        Args:
            uri: S3 URI (s3://bucket/path/manifest.json)
            
        Returns:
            Manifest dictionary
        """
        try:
            # Parse URI
            if not uri.startswith('s3://'):
                raise ValueError(f"Invalid S3 URI: {uri}")
            
            parts = uri[5:].split('/', 1)
            bucket = parts[0]
            key = parts[1] if len(parts) > 1 else ''
            
            client = self._get_s3_client()
            
            response = client.get_object(Bucket=bucket, Key=key)
            manifest_json = response['Body'].read().decode('utf-8')
            manifest = json.loads(manifest_json)
            
            logger.info(
                f"Loaded manifest from S3: {uri}",
                extra={'uri': uri, 'total_shards': len(manifest.get('shards', []))}
            )
            
            return manifest
            
        except Exception as e:
            logger.error(f"Failed to load manifest from S3: {e}")
            raise
    
    def parse_bigquery_export_manifest(self, gcs_uri: str) -> List[Dict]:
        """
        Parse BigQuery export manifest to extract shard information.
        
        BigQuery creates a manifest file when exporting with wildcards.
        This function parses that manifest to get all shard URIs.
        
        Args:
            gcs_uri: GCS URI of BigQuery export manifest
            
        Returns:
            List of shard metadata dictionaries
        """
        try:
            manifest = self.load_manifest_from_gcs(gcs_uri)
            
            shards = []
            for idx, entry in enumerate(manifest.get('entries', [])):
                shard = {
                    'shard_index': idx,
                    'gcs_uri': entry.get('url', ''),
                    'size_bytes': entry.get('sizeBytes', 0),
                    'md5': entry.get('md5', '')
                }
                shards.append(shard)
            
            logger.info(
                f"Parsed BigQuery export manifest: {len(shards)} shards",
                extra={'gcs_uri': gcs_uri, 'total_shards': len(shards)}
            )
            
            return shards
            
        except Exception as e:
            logger.error(f"Failed to parse BigQuery export manifest: {e}")
            raise
    
    def create_redshift_manifest(
        self,
        s3_uris: List[str],
        mandatory: bool = True
    ) -> Dict:
        """
        Create a Redshift COPY manifest file.
        
        Redshift COPY command can use manifest files to specify which files to load.
        This is more reliable than using wildcards.
        
        Args:
            s3_uris: List of S3 URIs to include in manifest
            mandatory: If True, COPY will fail if any file is missing
            
        Returns:
            Redshift manifest dictionary
        """
        manifest = {
            'entries': [
                {
                    'url': uri,
                    'mandatory': mandatory
                }
                for uri in s3_uris
            ]
        }
        
        logger.info(
            f"Created Redshift manifest with {len(s3_uris)} entries",
            extra={'total_entries': len(s3_uris), 'mandatory': mandatory}
        )
        
        return manifest
    
    def update_manifest_shard_status(
        self,
        manifest: Dict,
        shard_index: int,
        status_field: str,
        status: bool
    ) -> Dict:
        """
        Update shard status in manifest.
        
        Args:
            manifest: Manifest dictionary
            shard_index: Index of shard to update
            status_field: Status field to update (exported, transferred, loaded)
            status: New status value
            
        Returns:
            Updated manifest dictionary
        """
        try:
            if 'shards' not in manifest:
                raise ValueError("Manifest does not contain shards")
            
            if shard_index >= len(manifest['shards']):
                raise ValueError(f"Shard index {shard_index} out of range")
            
            shard = manifest['shards'][shard_index]
            if 'status' not in shard:
                shard['status'] = {}
            
            shard['status'][status_field] = status
            shard['status']['updated_at'] = datetime.utcnow().isoformat()
            
            manifest['metadata']['updated_at'] = datetime.utcnow().isoformat()
            
            return manifest
            
        except Exception as e:
            logger.error(f"Failed to update manifest shard status: {e}")
            raise
    
    def get_incomplete_shards(self, manifest: Dict, stage: str) -> List[int]:
        """
        Get list of shard indices that are incomplete for a given stage.
        
        Args:
            manifest: Manifest dictionary
            stage: Stage to check (exported, transferred, loaded)
            
        Returns:
            List of shard indices that are incomplete
        """
        incomplete = []
        
        for idx, shard in enumerate(manifest.get('shards', [])):
            status = shard.get('status', {})
            if not status.get(stage, False):
                incomplete.append(idx)
        
        logger.info(
            f"Found {len(incomplete)} incomplete shards for stage '{stage}'",
            extra={'stage': stage, 'incomplete_count': len(incomplete)}
        )
        
        return incomplete
    
    def validate_manifest(self, manifest: Dict) -> bool:
        """
        Validate manifest structure and required fields.
        
        Args:
            manifest: Manifest dictionary
            
        Returns:
            True if valid, False otherwise
        """
        required_fields = ['version', 'migration_id', 'source', 'shards']
        
        for field in required_fields:
            if field not in manifest:
                logger.error(f"Manifest missing required field: {field}")
                return False
        
        if not isinstance(manifest['shards'], list):
            logger.error("Manifest 'shards' field must be a list")
            return False
        
        logger.info("Manifest validation passed")
        return True
