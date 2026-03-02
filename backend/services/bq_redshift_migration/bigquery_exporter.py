"""
BigQuery to GCS Exporter

Handles exporting BigQuery tables to Google Cloud Storage with various formats and compression options.
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime
from google.cloud import bigquery
from google.oauth2 import service_account
import json

logger = logging.getLogger(__name__)


class BigQueryExporter:
    """Exports BigQuery tables to GCS"""
    
    def __init__(self, credentials_dict: dict, project_id: str):
        """
        Initialize BigQuery exporter
        
        Args:
            credentials_dict: Service account credentials as dictionary
            project_id: GCP project ID
        """
        self.project_id = project_id
        self.credentials = service_account.Credentials.from_service_account_info(credentials_dict)
        self.client = bigquery.Client(
            credentials=self.credentials,
            project=project_id
        )
        logger.info(f"BigQuery exporter initialized for project: {project_id}")
    
    def export_table(
        self,
        dataset: str,
        table: str,
        gcs_bucket: str,
        gcs_path: str,
        export_format: str = 'AVRO',
        compression: Optional[str] = None,
        load_type: str = 'full',
        timestamp_column: Optional[str] = None,
        last_extracted_value: Optional[str] = None
    ) -> Dict:
        """
        Export a single BigQuery table to GCS
        
        Args:
            dataset: BigQuery dataset name
            table: BigQuery table name
            gcs_bucket: GCS bucket name (without gs:// prefix)
            gcs_path: Path within GCS bucket
            export_format: Export format (AVRO, PARQUET, CSV, JSON)
            compression: Compression type (GZIP, SNAPPY, DEFLATE, ZSTD, or None)
            load_type: 'full' or 'incremental'
            timestamp_column: Column name for incremental filtering
            last_extracted_value: Last extracted timestamp value for incremental
        
        Returns:
            Dictionary with export results
        """
        try:
            logger.info(f"=== Starting BigQuery Export ===")
            logger.info(f"Table: {self.project_id}.{dataset}.{table}")
            logger.info(f"Destination: gs://{gcs_bucket}{gcs_path}")
            logger.info(f"Format: {export_format}, Compression: {compression}")
            
            # Get table reference
            table_ref = f"{self.project_id}.{dataset}.{table}"
            
            try:
                table_obj = self.client.get_table(table_ref)
                logger.info(f"Table info: {table_obj.num_rows:,} rows, {table_obj.num_bytes:,} bytes")
            except Exception as e:
                error_msg = f"Failed to access table '{table}' in dataset '{dataset}': {str(e)}"
                logger.error(error_msg)
                
                # Provide helpful error context
                if 'Not found' in str(e) or '404' in str(e):
                    error_msg += f"\n  → Table '{table}' does not exist in dataset '{dataset}' (project: {self.project_id})"
                elif 'Permission denied' in str(e) or '403' in str(e):
                    error_msg += f"\n  → Service account lacks permission to read table '{table}'"
                    error_msg += "\n  → Required permission: bigquery.tables.get"
                
                raise Exception(error_msg)
            
            # Build destination URI with organized structure: bucket/dataset/table/filename
            # If gcs_path is provided, use it as base, otherwise go directly to dataset/table
            
            # Clean up gcs_bucket - remove ALL gs:// and gs::// prefixes (handle malformed prefixes)
            clean_bucket = gcs_bucket
            # Remove all occurrences of gs:// or gs::// prefix
            while clean_bucket.startswith('gs://') or clean_bucket.startswith('gs:://'):
                if clean_bucket.startswith('gs:://'):
                    clean_bucket = clean_bucket[6:]  # Remove 'gs::/'
                elif clean_bucket.startswith('gs://'):
                    clean_bucket = clean_bucket[5:]  # Remove 'gs://'
            # Also handle any remaining gs: prefix
            if clean_bucket.startswith('gs:'):
                clean_bucket = clean_bucket[3:]
            # Remove any leading slashes or colons
            clean_bucket = clean_bucket.lstrip('/:').strip()
            
            logger.info(f"Original bucket: '{gcs_bucket}' → Cleaned bucket: '{clean_bucket}'")
            
            # Clean up gcs_path
            if gcs_path:
                # Remove leading/trailing slashes
                gcs_path = gcs_path.strip('/')
                # Build path with base prefix
                organized_path = f"/{gcs_path}/{dataset}/{table}" if gcs_path else f"/{dataset}/{table}"
            else:
                # No base path, go directly to dataset/table
                organized_path = f"/{dataset}/{table}"
            
            file_extension = self._get_file_extension(export_format, compression)
            destination_uri = f"gs://{clean_bucket}{organized_path}/{table}_*.{file_extension}"
            
            logger.info(f"Destination URI pattern: {destination_uri}")
            
            # Configure export job
            job_config = bigquery.ExtractJobConfig()
            
            # Set format
            if export_format == 'JSON':
                job_config.destination_format = bigquery.DestinationFormat.NEWLINE_DELIMITED_JSON
            elif export_format == 'CSV':
                job_config.destination_format = bigquery.DestinationFormat.CSV
            elif export_format == 'AVRO':
                job_config.destination_format = bigquery.DestinationFormat.AVRO
            elif export_format == 'PARQUET':
                job_config.destination_format = bigquery.DestinationFormat.PARQUET
            else:
                raise ValueError(f"Unsupported export format: {export_format}")
            
            # Set compression
            if compression and compression.upper() != 'NONE':
                compression_upper = compression.upper()
                if compression_upper == 'GZIP':
                    job_config.compression = bigquery.Compression.GZIP
                elif compression_upper == 'SNAPPY':
                    job_config.compression = bigquery.Compression.SNAPPY
                elif compression_upper == 'DEFLATE':
                    job_config.compression = bigquery.Compression.DEFLATE
                elif compression_upper == 'ZSTD':
                    job_config.compression = bigquery.Compression.ZSTD
                else:
                    logger.warning(f"Unknown compression type: {compression}, using no compression")
            
            # Start export job
            logger.info("Starting BigQuery extract job...")
            
            # For incremental loads, create a filtered temp table and export that
            actual_table_ref = table_ref
            temp_table_created = False
            if load_type == 'incremental' and timestamp_column and last_extracted_value:
                logger.info(f"Incremental mode: filtering WHERE {timestamp_column} > '{last_extracted_value}'")
                temp_dataset = dataset
                temp_table_name = f"_tmp_export_{table}_{int(datetime.now().timestamp())}"
                temp_table_ref = f"{self.project_id}.{temp_dataset}.{temp_table_name}"
                
                from datetime import datetime as dt
                
                query = f"""
                    CREATE OR REPLACE TABLE `{temp_table_ref}` AS
                    SELECT * FROM `{table_ref}`
                    WHERE `{timestamp_column}` > TIMESTAMP('{last_extracted_value}')
                """
                logger.info(f"Creating temp table with incremental filter: {temp_table_ref}")
                query_job = self.client.query(query)
                query_job.result()  # Wait for completion
                
                # Get row count of filtered data
                temp_table_obj = self.client.get_table(temp_table_ref)
                logger.info(f"Incremental export: {temp_table_obj.num_rows:,} rows after filtering")
                
                if temp_table_obj.num_rows == 0:
                    logger.info("No new rows to export for incremental load")
                    # Clean up temp table
                    self.client.delete_table(temp_table_ref, not_found_ok=True)
                    return {
                        'success': True,
                        'job_id': None,
                        'table': table_ref,
                        'destination_uris': [],
                        'num_files': 0,
                        'num_rows': 0,
                        'num_bytes': 0,
                        'format': export_format,
                        'compression': compression or 'NONE',
                        'schema': [{
                            'name': f.name,
                            'type': f.field_type,
                            'mode': f.mode or 'NULLABLE',
                            'description': f.description or ''
                        } for f in table_obj.schema],
                        'incremental': True,
                        'no_new_data': True
                    }
                
                actual_table_ref = temp_table_ref
                temp_table_created = True
            try:
                extract_job = self.client.extract_table(
                    actual_table_ref,
                    destination_uri,
                    job_config=job_config
                )
                
                job_id = extract_job.job_id
                logger.info(f"Job ID: {job_id}")
                logger.info("Waiting for export to complete...")
                
                # Wait for job to complete
                extract_job.result()
                
                logger.info(f"✓ Export completed successfully")
                
                # Clean up temp table if created for incremental
                if temp_table_created:
                    try:
                        self.client.delete_table(actual_table_ref, not_found_ok=True)
                        logger.info(f"✓ Cleaned up temp table: {actual_table_ref}")
                    except Exception as cleanup_err:
                        logger.warning(f"Failed to clean up temp table: {cleanup_err}")
                
            except Exception as e:
                error_msg = f"BigQuery export job failed for table '{table}': {str(e)}"
                logger.error(error_msg)
                
                # Provide helpful error context based on error type
                if 'Permission denied' in str(e) or '403' in str(e):
                    error_msg += f"\n  → Service account lacks permission to write to GCS bucket '{clean_bucket}'"
                    error_msg += "\n  → Required permissions: storage.objects.create, storage.objects.delete"
                    error_msg += f"\n  → Check bucket '{clean_bucket}' exists and service account has Storage Object Creator role"
                elif 'Not found' in str(e) or '404' in str(e):
                    if 'bucket' in str(e).lower():
                        error_msg += f"\n  → GCS bucket '{clean_bucket}' does not exist"
                        error_msg += "\n  → Create the bucket or verify the bucket name is correct"
                    else:
                        error_msg += f"\n  → Resource not found during export"
                elif 'Quota exceeded' in str(e) or 'quota' in str(e).lower():
                    error_msg += "\n  → BigQuery export quota exceeded"
                    error_msg += "\n  → Wait a few minutes and try again, or request quota increase"
                elif 'Invalid' in str(e):
                    error_msg += f"\n  → Invalid export configuration"
                    error_msg += f"\n  → Format: {export_format}, Compression: {compression}"
                
                raise Exception(error_msg)
            
            # Get destination URIs
            destination_uris = []
            if hasattr(extract_job, 'destination_uris'):
                destination_uris = extract_job.destination_uris
            else:
                # Estimate based on table size (BigQuery creates ~100MB files)
                num_files = max(1, int(table_obj.num_bytes / (100 * 1024 * 1024)))
                for i in range(num_files):
                    uri = f"gs://{clean_bucket}{organized_path}/{table}_{i:012d}.{file_extension}"
                    destination_uris.append(uri)
            
            # Extract schema information for Redshift table creation
            schema = []
            for field in table_obj.schema:
                schema.append({
                    'name': field.name,
                    'type': field.field_type,
                    'mode': field.mode or 'NULLABLE',
                    'description': field.description or ''
                })
            
            logger.info(f"✓ Extracted schema: {len(schema)} columns")
            
            result = {
                'success': True,
                'job_id': job_id,
                'table': table_ref,
                'destination_uris': destination_uris,
                'num_files': len(destination_uris),
                'num_rows': table_obj.num_rows,
                'num_bytes': table_obj.num_bytes,
                'format': export_format,
                'compression': compression or 'NONE',
                'schema': schema  # Add schema for Redshift table creation
            }
            
            logger.info(f"Export result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to export table {table}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    def export_tables(
        self,
        dataset: str,
        tables: List[str],
        gcs_bucket: str,
        gcs_path: str,
        export_format: str = 'AVRO',
        compression: Optional[str] = None,
        load_type: str = 'full',
        timestamp_column: Optional[str] = None,
        last_extracted_value: Optional[str] = None,
        table_load_configs: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Export multiple BigQuery tables to GCS
        
        Args:
            dataset: BigQuery dataset name
            tables: List of BigQuery table names
            gcs_bucket: GCS bucket name (without gs:// prefix)
            gcs_path: Path within GCS bucket
            export_format: Export format (AVRO, PARQUET, CSV, JSON)
            compression: Compression type (GZIP, SNAPPY, DEFLATE, ZSTD, or None)
            load_type: Default load type ('full' or 'incremental') — used when table has no per-table config
            timestamp_column: Default timestamp column — used when table has no per-table config
            last_extracted_value: Last extracted timestamp value for incremental
            table_load_configs: Per-table config dict: { "table_name": { "load_type": "incremental", "primary_key_column": "id", "timestamp_column": "updated_at" } }
        
        Returns:
            List of dictionaries with export results for each table
        """
        results = []
        
        logger.info(f"=== Exporting {len(tables)} tables (default mode: {load_type}) ===")
        if table_load_configs:
            logger.info(f"Per-table configs: {list(table_load_configs.keys())}")
        
        for idx, table in enumerate(tables, 1):
            try:
                # Resolve per-table config (fall back to global defaults)
                table_config = (table_load_configs or {}).get(table, {})
                effective_load_type = table_config.get('load_type', load_type)
                effective_timestamp_col = table_config.get('timestamp_column', timestamp_column)
                
                logger.info(f"[{idx}/{len(tables)}] Exporting table: {table} (load_type={effective_load_type})")
                result = self.export_table(
                    dataset=dataset,
                    table=table,
                    gcs_bucket=gcs_bucket,
                    gcs_path=gcs_path,
                    export_format=export_format,
                    compression=compression,
                    load_type=effective_load_type,
                    timestamp_column=effective_timestamp_col,
                    last_extracted_value=last_extracted_value
                )
                results.append(result)
                logger.info(f"✓ [{idx}/{len(tables)}] Table {table} exported successfully")
            except Exception as e:
                error_msg = str(e)
                logger.error(f"✗ [{idx}/{len(tables)}] Failed to export table {table}: {error_msg}")
                results.append({
                    'success': False,
                    'table': table,
                    'table_id': table,  # Add table_id for backward compatibility
                    'error': error_msg,
                    'error_type': type(e).__name__
                })
        
        successful = sum(1 for r in results if r.get('success'))
        logger.info(f"=== Export complete: {successful}/{len(tables)} tables successful ===")
        
        return results
    
    def _get_file_extension(self, export_format: str, compression: Optional[str]) -> str:
        """Get file extension based on format and compression"""
        format_lower = export_format.lower()
        
        # Base extension
        if format_lower == 'json':
            ext = 'json'
        elif format_lower == 'csv':
            ext = 'csv'
        elif format_lower == 'avro':
            ext = 'avro'
        elif format_lower == 'parquet':
            ext = 'parquet'
        else:
            ext = format_lower
        
        # Add compression extension
        if compression and compression.upper() != 'NONE':
            comp_lower = compression.lower()
            if comp_lower == 'gzip':
                ext += '.gz'
            elif comp_lower == 'snappy':
                ext += '.snappy'
            elif comp_lower == 'deflate':
                ext += '.deflate'
            elif comp_lower == 'zstd':
                ext += '.zst'
        
        return ext
    
    def get_table_info(self, dataset: str, table: str) -> Dict:
        """
        Get information about a BigQuery table
        
        Args:
            dataset: BigQuery dataset name
            table: BigQuery table name
        
        Returns:
            Dictionary with table information
        """
        try:
            table_ref = f"{self.project_id}.{dataset}.{table}"
            table_obj = self.client.get_table(table_ref)
            
            return {
                'table_id': table_obj.table_id,
                'dataset_id': table_obj.dataset_id,
                'project_id': table_obj.project,
                'num_rows': table_obj.num_rows,
                'num_bytes': table_obj.num_bytes,
                'created': table_obj.created.isoformat() if table_obj.created else None,
                'modified': table_obj.modified.isoformat() if table_obj.modified else None,
                'table_type': table_obj.table_type,
                'description': table_obj.description
            }
        except Exception as e:
            logger.error(f"Failed to get table info for {table}: {str(e)}")
            raise
