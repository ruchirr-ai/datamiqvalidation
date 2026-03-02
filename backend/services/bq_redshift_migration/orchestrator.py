"""
Migration Orchestrator

Main orchestration service for BigQuery to Redshift migrations.
Manages pathway selection, execution, error handling, and state transitions.
"""

import logging
from typing import Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from models.bq_redshift_migration import MigrationBQRedshift, MigrationLog
from models.connection import Connection
from .checkpoint_manager import CheckpointManager
from .manifest_handler import ManifestHandler
from .bigquery_exporter import BigQueryExporter
from .pathway_a import PathwayA
from .pathway_b import PathwayB
from .pathway_c import PathwayC
from services.unified_kms_service import get_unified_kms_service

logger = logging.getLogger(__name__)


class MigrationOrchestrator:
    """
    Orchestrates BigQuery to Redshift migrations across all pathways.
    
    Responsibilities:
    - Pathway selection and execution
    - State management
    - Error handling and recovery
    - Progress tracking
    - Logging
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.checkpoint_manager = CheckpointManager(db)
        self.manifest_handler = ManifestHandler()
        
        # Initialize pathway implementations
        self.pathways = {
            'A': PathwayA(self.checkpoint_manager, self.manifest_handler, self._log),
            'B': PathwayB(self.checkpoint_manager, self.manifest_handler, self._log),
            'C': PathwayC(self.checkpoint_manager, self.manifest_handler, self._log),
        }
    
    def start_migration(self, migration_id: int, _skip_status_check: bool = False) -> bool:
        """
        Start a migration.
        
        Args:
            migration_id: Migration ID
            _skip_status_check: If True, skip the 'already running' check.
                Used by the restart endpoint which pre-sets status to 'running'.
            
        Returns:
            True if started successfully, False otherwise
        """
        try:
            migration = self.db.query(MigrationBQRedshift).filter_by(
                id=migration_id
            ).first()
            
            if not migration:
                logger.error(f"Migration {migration_id} not found")
                return False
            
            if migration.status == 'running' and not _skip_status_check:
                logger.warning(f"Migration {migration_id} is already running")
                return False
            
            # Update status
            migration.status = 'running'
            migration.start_time = datetime.utcnow()
            migration.updated_at = datetime.utcnow()
            self.db.commit()
            
            self._log(migration_id, 'INFO', 'export', f"Starting migration (Pathway {migration.pathway})")
            
            logger.info(f"Started migration {migration_id} (Pathway {migration.pathway})")
            
            # Execute migration
            success = self._execute_migration(migration)
            
            # Update final status
            if success:
                migration.status = 'completed'
                migration.end_time = datetime.utcnow()
                migration.last_run_at = datetime.utcnow()  # Fix: Add last_run_at
                migration.duration_seconds = int(
                    (migration.end_time - migration.start_time).total_seconds()
                )
                self._log(migration_id, 'INFO', 'load', 'Migration completed successfully')
            else:
                migration.status = 'failed'
                migration.end_time = datetime.utcnow()
                migration.last_run_at = datetime.utcnow()  # Fix: Add last_run_at even for failures
                self._log(migration_id, 'ERROR', migration.current_stage or 'unknown', 'Migration failed')
            
            migration.updated_at = datetime.utcnow()
            self.db.commit()
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to start migration {migration_id}: {e}", exc_info=True)
            self._log(migration_id, 'CRITICAL', 'unknown', f"Migration failed: {str(e)}")
            
            # Update status to failed
            migration = self.db.query(MigrationBQRedshift).filter_by(id=migration_id).first()
            if migration:
                migration.status = 'failed'
                migration.end_time = datetime.utcnow()
                migration.updated_at = datetime.utcnow()
                self.db.commit()
            
            return False
    
    def pause_migration(self, migration_id: int) -> bool:
        """
        Pause a running migration.
        
        Args:
            migration_id: Migration ID
            
        Returns:
            True if paused successfully, False otherwise
        """
        try:
            migration = self.db.query(MigrationBQRedshift).filter_by(
                id=migration_id
            ).first()
            
            if not migration:
                logger.error(f"Migration {migration_id} not found")
                return False
            
            if migration.status != 'running':
                logger.warning(f"Migration {migration_id} is not running")
                return False
            
            migration.status = 'paused'
            migration.updated_at = datetime.utcnow()
            self.db.commit()
            
            self._log(migration_id, 'INFO', migration.current_stage or 'unknown', 'Migration paused')
            
            logger.info(f"Paused migration {migration_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to pause migration {migration_id}: {e}")
            return False
    
    def resume_migration(self, migration_id: int) -> bool:
        """
        Resume a paused or failed migration.
        
        For Path B (and pathways using checkpoint_data), resume is determined
        by checkpoint_data keys (export_completed_at, transfer_completed_at, etc.)
        rather than MigrationShard records. This method delegates to _execute_migration
        which already handles checkpoint-based resume for all pathways.
        
        Args:
            migration_id: Migration ID
            
        Returns:
            True if resumed successfully, False otherwise
        """
        try:
            migration = self.db.query(MigrationBQRedshift).filter_by(
                id=migration_id
            ).first()
            
            if not migration:
                logger.error(f"Migration {migration_id} not found")
                return False
            
            if migration.status not in ('paused', 'failed'):
                logger.warning(f"Migration {migration_id} cannot be resumed (status: {migration.status})")
                return False
            
            # Determine resume stage from checkpoint_data (works for all pathways)
            checkpoint_data = migration.checkpoint_data or {}
            export_done = checkpoint_data.get('export_completed_at') is not None
            transfer_done = checkpoint_data.get('transfer_completed_at') is not None
            load_done = checkpoint_data.get('load_completed_at') is not None
            
            if load_done:
                resume_stage = 'completed'
            elif transfer_done:
                resume_stage = 'load'
            elif export_done:
                resume_stage = 'transfer'
            else:
                resume_stage = 'export'
            
            self._log(
                migration_id,
                'INFO',
                resume_stage,
                f"Resuming migration from {resume_stage} stage (Pathway {migration.pathway})"
            )
            
            # Update status and resume
            migration.status = 'running'
            migration.resume_point = resume_stage
            migration.updated_at = datetime.utcnow()
            if not migration.start_time:
                migration.start_time = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"Resuming migration {migration_id} from {resume_stage} stage (Pathway {migration.pathway})")
            
            # Execute migration — _execute_migration already handles checkpoint-based resume
            success = self._execute_migration(migration)
            
            # Update final status
            if success:
                migration.status = 'completed'
                migration.end_time = datetime.utcnow()
                migration.last_run_at = datetime.utcnow()
                if migration.start_time:
                    migration.duration_seconds = int(
                        (migration.end_time - migration.start_time).total_seconds()
                    )
                self._log(migration_id, 'INFO', 'load', 'Migration completed successfully')
            else:
                migration.status = 'failed'
                migration.end_time = datetime.utcnow()
                migration.last_run_at = datetime.utcnow()
                self._log(migration_id, 'ERROR', migration.current_stage or 'unknown', 'Migration failed')
            
            migration.updated_at = datetime.utcnow()
            self.db.commit()
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to resume migration {migration_id}: {e}", exc_info=True)
            
            # Mark as failed so it can be retried
            migration = self.db.query(MigrationBQRedshift).filter_by(id=migration_id).first()
            if migration and migration.status == 'running':
                migration.status = 'failed'
                migration.end_time = datetime.utcnow()
                migration.updated_at = datetime.utcnow()
                self.db.commit()
            
            return False
    
    def cancel_migration(self, migration_id: int) -> bool:
        """
        Cancel a running or paused migration.
        
        Args:
            migration_id: Migration ID
            
        Returns:
            True if cancelled successfully, False otherwise
        """
        try:
            migration = self.db.query(MigrationBQRedshift).filter_by(
                id=migration_id
            ).first()
            
            if not migration:
                logger.error(f"Migration {migration_id} not found")
                return False
            
            if migration.status not in ('running', 'paused'):
                logger.warning(f"Migration {migration_id} cannot be cancelled (status: {migration.status})")
                return False
            
            migration.status = 'cancelled'
            migration.end_time = datetime.utcnow()
            migration.updated_at = datetime.utcnow()
            self.db.commit()
            
            self._log(migration_id, 'WARNING', migration.current_stage or 'unknown', 'Migration cancelled by user')
            
            logger.info(f"Cancelled migration {migration_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel migration {migration_id}: {e}")
            return False
    
    def get_migration_status(self, migration_id: int) -> Optional[Dict]:
        """
        Get current migration status with progress.
        
        Args:
            migration_id: Migration ID
            
        Returns:
            Status dictionary or None if not found
        """
        try:
            migration = self.db.query(MigrationBQRedshift).filter_by(
                id=migration_id
            ).first()
            
            if not migration:
                return None
            
            # Get progress
            progress = self.checkpoint_manager.get_migration_progress(migration_id)
            
            return {
                'migration_id': migration_id,
                'status': migration.status,
                'current_stage': migration.current_stage,
                'pathway': migration.pathway,
                'progress': progress,
                'start_time': migration.start_time.isoformat() if migration.start_time else None,
                'end_time': migration.end_time.isoformat() if migration.end_time else None,
                'duration_seconds': migration.duration_seconds,
                'metrics': {
                    'total_rows_source': migration.total_rows_source,
                    'total_rows_target': migration.total_rows_target,
                    'total_bytes_transferred': migration.total_bytes_transferred
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get migration status: {e}")
            return None
    
    def validate_migration(self, migration_id: int) -> Optional[Dict]:
        """
        Validate migration data integrity.
        
        Args:
            migration_id: Migration ID
            
        Returns:
            Validation results or None if failed
        """
        try:
            migration = self.db.query(MigrationBQRedshift).filter_by(
                id=migration_id
            ).first()
            
            if not migration:
                logger.error(f"Migration {migration_id} not found")
                return None
            
            if migration.status != 'completed':
                logger.warning(f"Migration {migration_id} is not completed")
                return None
            
            # Get pathway implementation
            pathway = self.pathways.get(migration.pathway)
            if not pathway:
                logger.error(f"Pathway {migration.pathway} not implemented")
                return None
            
            # Prepare configurations
            source_config = {
                'project_id': migration.source_project_id,
                'dataset': migration.source_dataset,
                'tables': migration.source_tables
            }
            
            target_config = {
                'cluster': migration.target_cluster,
                'database': migration.target_database,
                'schema': migration.target_schema,
                'username': 'redshift_user',  # Should come from connection
                'password': 'redshift_pass'   # Should come from connection
            }
            
            # Validate
            results = pathway.validate_migration(
                migration_id,
                source_config,
                target_config
            )
            
            # Update migration metrics
            if results.get('valid'):
                total_source = sum(t['source_count'] for t in results['tables'].values())
                total_target = sum(t['target_count'] for t in results['tables'].values())
                
                migration.total_rows_source = total_source
                migration.total_rows_target = total_target
                migration.updated_at = datetime.utcnow()
                self.db.commit()
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to validate migration {migration_id}: {e}", exc_info=True)
            return None
    
    def _execute_migration(self, migration: MigrationBQRedshift) -> bool:
        """
        Execute migration using the appropriate pathway.
        
        Args:
            migration: Migration model instance
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"=== Starting Migration Execution: {migration.id} (Pathway {migration.pathway}) ===")
            self._log(
                migration.id,
                'INFO',
                'migration',
                f"Starting migration execution using Pathway {migration.pathway}",
                log_metadata={
                    'pathway': migration.pathway,
                    'source_dataset': migration.source_dataset,
                    'target_database': migration.target_database
                }
            )
            
            # Check if export is already completed
            checkpoint_data = migration.checkpoint_data or {}
            export_completed = checkpoint_data.get('export_completed_at') is not None
            
            if export_completed:
                logger.info("✓ Export stage already completed, skipping to transfer stage")
                self._log(
                    migration.id,
                    'INFO',
                    'export',
                    "Export stage already completed, resuming from transfer stage"
                )
            else:
                # Step 1: Export from BigQuery to GCS
                logger.info("Step 1: Exporting data from BigQuery to GCS")
                self._log(
                    migration.id,
                    'INFO',
                    'export',
                    f"Starting BigQuery export: {len(migration.source_tables or [])} tables from {migration.source_dataset}"
                )
                
                export_success = self._execute_bigquery_export(migration)
                
                if not export_success:
                    logger.error("BigQuery export failed")
                    self._log(
                        migration.id,
                        'ERROR',
                        'export',
                        "BigQuery export failed - migration cannot continue"
                    )
                    return False
                
                logger.info("✓ BigQuery export completed successfully")
                self._log(
                    migration.id,
                    'INFO',
                    'export',
                    "BigQuery export completed successfully - proceeding to transfer stage"
                )
            
            # Step 2: Execute pathway-specific logic (GCS → S3 → Redshift)
            logger.info(f"Step 2: Executing Pathway {migration.pathway} transfer and load stages")
            self._log(
                migration.id,
                'INFO',
                'transfer',
                f"Starting Pathway {migration.pathway} transfer and load stages",
                log_metadata={
                    'gcs_bucket': migration.gcs_bucket,
                    's3_bucket': migration.s3_bucket,
                    'target_cluster': migration.target_cluster
                }
            )
            
            # Get pathway implementation
            pathway = self.pathways.get(migration.pathway)
            if not pathway:
                logger.error(f"Pathway {migration.pathway} not implemented")
                self._log(
                    migration.id,
                    'ERROR',
                    'transfer',
                    f"Pathway {migration.pathway} is not implemented"
                )
                return False
            
            # Prepare configurations
            source_config = {
                'project_id': migration.source_project_id,
                'dataset': migration.source_dataset,
                'tables': migration.source_tables
            }
            
            # Get target connection details from database
            target_config = {}
            if migration.target_connection_id:
                from models.connection import Connection
                target_conn = self.db.query(Connection).filter_by(id=migration.target_connection_id).first()
                if target_conn:
                    conn_params = target_conn.connection_params or {}
                    target_config = {
                        'cluster': conn_params.get('host') or conn_params.get('server_name') or migration.target_cluster,
                        'port': int(conn_params.get('port', 5439)),
                        'database': conn_params.get('database') or conn_params.get('database_name') or migration.target_database,
                        'schema': migration.target_schema or 'public',
                        'username': conn_params.get('username'),
                        'password_encrypted': conn_params.get('password_encrypted'),
                        'iam_role_arn': migration.iam_role_arn
                    }
                    logger.info(f"✓ Loaded target connection details from connection ID {migration.target_connection_id}")
                else:
                    logger.warning(f"Target connection {migration.target_connection_id} not found, using migration fields")
                    target_config = {
                        'cluster': migration.target_cluster,
                        'database': migration.target_database,
                        'schema': migration.target_schema or 'public',
                        'iam_role_arn': migration.iam_role_arn
                    }
            else:
                logger.warning("No target connection ID set, using migration fields")
                target_config = {
                    'cluster': migration.target_cluster,
                    'database': migration.target_database,
                    'schema': migration.target_schema or 'public',
                    'iam_role_arn': migration.iam_role_arn
                }
            
            # Decrypt AWS secret key if present
            aws_secret_key = ''
            if migration.aws_secret_access_key_encrypted:
                try:
                    self._log(
                        migration.id,
                        'INFO',
                        'transfer',
                        "Decrypting AWS credentials for S3 access"
                    )
                    kms = get_unified_kms_service()
                    aws_secret_key = kms.decrypt_credential(
                        ciphertext=migration.aws_secret_access_key_encrypted,
                        credential_type='aws_secret_key',
                        resource_type='migration',
                        resource_id=migration.id,
                        allow_plaintext_fallback=True
                    )
                    logger.info("✓ AWS credentials decrypted successfully")
                except Exception as e:
                    logger.warning(f"KMS decryption failed, treating as unencrypted (DEV ONLY): {e}")
                    # Fallback: treat the value as already decrypted (for local dev without KMS)
                    aws_secret_key = migration.aws_secret_access_key_encrypted
                    logger.info("✓ Using AWS credentials (unencrypted fallback)")
                    self._log(
                        migration.id,
                        'WARNING',
                        'transfer',
                        "Using unencrypted AWS credentials (development mode)"
                    )
            
            storage_config = {
                'gcs_bucket': migration.gcs_bucket,
                'gcs_path': migration.gcs_path,
                'gcs_region': migration.gcs_region,
                's3_bucket': migration.s3_bucket,
                's3_path': migration.s3_path,
                'project_id': migration.source_project_id,
                'source_connection_id': migration.source_connection_id,
                'aws_access_key_id': migration.aws_access_key_id or '',
                'aws_secret_access_key_encrypted': migration.aws_secret_access_key_encrypted,
                'overwrite_existing': migration.overwrite_existing_files == 'true',
                'delete_source': migration.delete_source_after_transfer == 'true',
                'export_format': migration.export_format or 'AVRO',
                'compression': migration.compression or 'NONE',
                # Path B: AWS DataSync Agent on GCP VM
                'datasync_agent_mode': getattr(migration, 'datasync_agent_mode', 'existing_vm') or 'existing_vm',
                'datasync_gcp_zone': getattr(migration, 'datasync_gcp_zone', '') or '',
                'datasync_gcp_machine_type': getattr(migration, 'datasync_gcp_machine_type', 'n1-standard-4') or 'n1-standard-4',
                'datasync_gcp_network': getattr(migration, 'datasync_gcp_network', '') or '',
                'datasync_gcp_subnet': getattr(migration, 'datasync_gcp_subnet', '') or '',
                'datasync_existing_vm_ip': getattr(migration, 'datasync_existing_vm_ip', '') or '',
                'datasync_s3_role_arn': getattr(migration, 'datasync_s3_role_arn', '') or '',
                'aws_region': getattr(migration, 'aws_region', 'us-east-1') or 'us-east-1',
                'gcs_access_key': migration.gcs_access_key or '',
                'gcs_secret_key_encrypted': migration.gcs_secret_key_encrypted or '',
                # Service account JSON (encrypted)
                'service_account_json_encrypted': migration.service_account_json_encrypted or '',
                # Load type configuration
                'load_type': migration.load_type or 'full',
                'primary_key_column': migration.primary_key_column or '',
                'timestamp_column': migration.timestamp_column or '',
                'truncate_before_load': getattr(migration, 'truncate_before_load', 'false') == 'true',
                'table_load_configs': migration.table_load_configs or {},
            }
            
            # Execute pathway
            self._log(
                migration.id,
                'INFO',
                'transfer',
                f"Executing Pathway {migration.pathway} - this may take several minutes"
            )
            
            success = pathway.execute(
                migration.id,
                source_config,
                target_config,
                storage_config
            )
            
            if success:
                logger.info(f"✓ Pathway {migration.pathway} execution completed successfully")
                self._log(
                    migration.id,
                    'INFO',
                    'load',
                    f"Pathway {migration.pathway} execution completed successfully - migration finished"
                )
            else:
                logger.error(f"✗ Pathway {migration.pathway} execution failed")
                self._log(
                    migration.id,
                    'ERROR',
                    'load',
                    f"Pathway {migration.pathway} execution failed - check logs for details"
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Migration execution failed: {e}", exc_info=True)
            self._log(
                migration.id,
                'CRITICAL',
                'migration',
                f"Migration execution failed with exception: {str(e)}",
                log_metadata={'exception_type': type(e).__name__}
            )
            return False
    
    def _execute_bigquery_export(self, migration: MigrationBQRedshift) -> bool:
        """
        Execute BigQuery to GCS export.
        
        Args:
            migration: Migration model instance
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Update migration stage
            migration.current_stage = 'export'
            migration.updated_at = datetime.utcnow()
            self.db.commit()
            
            self._log(migration.id, 'INFO', 'export', 'Starting BigQuery export to GCS')
            
            # Get source connection
            source_connection = self.db.query(Connection).filter_by(
                id=migration.source_connection_id
            ).first()
            
            if not source_connection:
                error_msg = f"Source connection {migration.source_connection_id} not found in database"
                logger.error(error_msg)
                self._log(
                    migration.id,
                    'ERROR',
                    'export',
                    error_msg,
                    error_code='CONNECTION_NOT_FOUND',
                    log_metadata={'connection_id': migration.source_connection_id}
                )
                return False
            
            logger.info(f"Source connection: {source_connection.name}")
            self._log(
                migration.id,
                'INFO',
                'export',
                f"Using source connection: {source_connection.name} (ID: {source_connection.id})"
            )
            
            # Get credentials from connection params
            connection_params = source_connection.connection_params or {}
            
            # First try: use service account JSON stored directly on the migration (from Stage 1 config)
            service_account_key = None
            if migration.service_account_json_encrypted:
                try:
                    kms = get_unified_kms_service()
                    decrypted_sa_json = kms.decrypt_credential(
                        ciphertext=migration.service_account_json_encrypted,
                        credential_type='gcp_service_account',
                        resource_type='migration',
                        resource_id=migration.id,
                        allow_plaintext_fallback=True
                    )
                    if decrypted_sa_json:
                        service_account_key = decrypted_sa_json
                        logger.info("✓ Using service account JSON from migration configuration (Stage 1)")
                        self._log(migration.id, 'INFO', 'export', 'Using service account credentials from migration Stage 1 configuration')
                except Exception as e:
                    logger.warning(f"KMS decryption failed, treating as unencrypted (DEV ONLY): {e}")
                    # Fallback: treat the value as already decrypted (for local dev without KMS)
                    service_account_key = migration.service_account_json_encrypted
                    logger.info("✓ Using service account JSON from migration configuration (unencrypted fallback)")
                    self._log(migration.id, 'INFO', 'export', 'Using service account credentials from migration (unencrypted)')
            
            # Second try: fall back to connection params
            if not service_account_key:
                service_account_key = (
                    connection_params.get('service_account_key') or 
                    connection_params.get('serviceAccountKey') or
                    connection_params.get('credentials_json') or
                    connection_params.get('credentialsJson')
                )
            
            if not service_account_key:
                error_msg = "Service account key not found in connection parameters. Please ensure the BigQuery connection has valid credentials."
                logger.error(error_msg)
                self._log(
                    migration.id,
                    'ERROR',
                    'export',
                    error_msg,
                    error_code='MISSING_CREDENTIALS',
                    log_metadata={
                        'connection_id': source_connection.id,
                        'available_params': list(connection_params.keys())
                    }
                )
                return False
            
            # Parse service account key if it's a string
            if isinstance(service_account_key, str):
                try:
                    import json
                    credentials_dict = json.loads(service_account_key)
                    logger.info("✓ Service account key parsed from JSON string")
                    self._log(migration.id, 'INFO', 'export', 'Service account credentials parsed successfully')
                except json.JSONDecodeError as e:
                    error_msg = f"Invalid service account key JSON format: {str(e)}"
                    logger.error(error_msg)
                    self._log(
                        migration.id,
                        'ERROR',
                        'export',
                        error_msg,
                        error_code='INVALID_CREDENTIALS_FORMAT',
                        log_metadata={'parse_error': str(e)}
                    )
                    return False
            else:
                credentials_dict = service_account_key
                logger.info("✓ Service account key already in dict format")
            
            project_id = (
                migration.source_project_id or
                connection_params.get('project_id') or 
                connection_params.get('projectId') or
                credentials_dict.get('project_id')
            )
            
            if not project_id:
                error_msg = "Project ID not found. Please specify project_id in migration configuration or connection parameters."
                logger.error(error_msg)
                self._log(
                    migration.id,
                    'ERROR',
                    'export',
                    error_msg,
                    error_code='MISSING_PROJECT_ID'
                )
                return False
            
            logger.info(f"Initializing BigQuery exporter (project: {project_id})")
            self._log(
                migration.id,
                'INFO',
                'export',
                f"Initializing BigQuery client for project: {project_id}"
            )
            
            # Initialize BigQuery exporter
            try:
                exporter = BigQueryExporter(
                    credentials_dict=credentials_dict,
                    project_id=project_id
                )
                self._log(migration.id, 'INFO', 'export', 'BigQuery client initialized successfully')
            except Exception as e:
                error_msg = f"Failed to initialize BigQuery client: {str(e)}"
                logger.error(error_msg, exc_info=True)
                self._log(
                    migration.id,
                    'ERROR',
                    'export',
                    error_msg,
                    error_code='CLIENT_INIT_FAILED',
                    log_metadata={
                        'project_id': project_id,
                        'error_type': type(e).__name__,
                        'error_details': str(e)
                    }
                )
                return False
            
            # Get export configuration from migration
            export_format = migration.export_format or 'AVRO'
            compression = migration.compression or 'NONE'
            
            logger.info(f"Export configuration: format={export_format}, compression={compression}")
            
            # Build destination URI
            gcs_bucket = migration.gcs_bucket
            gcs_path = migration.gcs_path.strip('/') if migration.gcs_path else ''
            dataset = migration.source_dataset
            
            # Validate GCS bucket
            if not gcs_bucket:
                error_msg = "GCS bucket not specified. Please configure the destination GCS bucket."
                logger.error(error_msg)
                self._log(
                    migration.id,
                    'ERROR',
                    'export',
                    error_msg,
                    error_code='MISSING_GCS_BUCKET'
                )
                return False
            
            # Clean GCS bucket name - remove gs:// or gs::// prefix if present (handle malformed prefixes)
            original_bucket = gcs_bucket
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
            
            if original_bucket != gcs_bucket:
                logger.info(f"Cleaned GCS bucket: '{original_bucket}' → '{gcs_bucket}'")
                self._log(
                    migration.id,
                    'INFO',
                    'export',
                    f"Cleaned GCS bucket name: '{original_bucket}' → '{gcs_bucket}'"
                )
            
            # Export all tables
            tables_to_export = migration.source_tables or []
            
            if not tables_to_export:
                error_msg = "No tables specified for export. Please select at least one table to migrate."
                logger.warning(error_msg)
                self._log(
                    migration.id,
                    'WARNING',
                    'export',
                    error_msg,
                    error_code='NO_TABLES_SELECTED'
                )
                return False
            
            logger.info(f"Exporting {len(tables_to_export)} tables: {tables_to_export}")
            self._log(
                migration.id,
                'INFO',
                'export',
                f"Starting export of {len(tables_to_export)} tables from dataset '{dataset}'",
                log_metadata={
                    'dataset': dataset,
                    'tables': tables_to_export,
                    'gcs_bucket': gcs_bucket,
                    'gcs_path': gcs_path,
                    'format': export_format,
                    'compression': compression
                }
            )
            
            # Export tables
            table_load_configs = migration.table_load_configs or {}
            export_results = exporter.export_tables(
                dataset=dataset,
                tables=tables_to_export,
                gcs_bucket=gcs_bucket,
                gcs_path=gcs_path,
                export_format=export_format,
                compression=compression,
                load_type=migration.load_type or 'full',
                timestamp_column=migration.timestamp_column or None,
                last_extracted_value=migration.last_extracted_value or None,
                table_load_configs=table_load_configs
            )
            
            # Check results and log detailed information
            successful_exports = [r for r in export_results if r.get('success')]
            failed_exports = [r for r in export_results if not r.get('success')]
            
            logger.info(f"Export results: {len(successful_exports)} succeeded, {len(failed_exports)} failed")
            
            # Log successful exports
            if successful_exports:
                for result in successful_exports:
                    table_name = result.get('table', 'unknown')
                    num_rows = result.get('num_rows', 0)
                    num_bytes = result.get('num_bytes', 0)
                    num_files = result.get('num_files', 0)
                    
                    self._log(
                        migration.id,
                        'INFO',
                        'export',
                        f"✓ Table '{table_name}' exported successfully: {num_rows:,} rows, {num_bytes:,} bytes, {num_files} files",
                        log_metadata={
                            'table': table_name,
                            'rows': num_rows,
                            'bytes': num_bytes,
                            'files': num_files,
                            'job_id': result.get('job_id')
                        }
                    )
            
            # Log failed exports with detailed error information
            if failed_exports:
                logger.error(f"Failed exports: {failed_exports}")
                
                for result in failed_exports:
                    table_name = result.get('table', 'unknown')
                    error_msg = result.get('error', 'Unknown error')
                    
                    # Provide more context based on error type
                    detailed_msg = f"✗ Table '{table_name}' export failed: {error_msg}"
                    
                    # Add helpful hints based on common errors
                    if 'permission' in error_msg.lower() or 'access' in error_msg.lower():
                        detailed_msg += "\n  → Check: Service account has BigQuery Data Viewer and Storage Object Creator permissions"
                    elif 'not found' in error_msg.lower():
                        detailed_msg += f"\n  → Check: Table exists in dataset '{dataset}' and project '{project_id}'"
                    elif 'quota' in error_msg.lower():
                        detailed_msg += "\n  → Check: BigQuery export quota limits and try again later"
                    elif 'bucket' in error_msg.lower():
                        detailed_msg += f"\n  → Check: GCS bucket '{gcs_bucket}' exists and service account has write access"
                    
                    self._log(
                        migration.id,
                        'ERROR',
                        'export',
                        detailed_msg,
                        error_code='TABLE_EXPORT_FAILED',
                        log_metadata={
                            'table': table_name,
                            'dataset': dataset,
                            'project_id': project_id,
                            'gcs_bucket': gcs_bucket,
                            'error': error_msg
                        }
                    )
                
                # Summary error log
                self._log(
                    migration.id,
                    'ERROR',
                    'export',
                    f"Export failed: {len(failed_exports)} out of {len(tables_to_export)} tables could not be exported",
                    error_code='PARTIAL_EXPORT_FAILURE',
                    log_metadata={
                        'total_tables': len(tables_to_export),
                        'successful': len(successful_exports),
                        'failed': len(failed_exports),
                        'failed_tables': [r.get('table', 'unknown') for r in failed_exports]
                    }
                )
            
            # Store export results in checkpoint data
            checkpoint_data = migration.checkpoint_data or {}
            checkpoint_data['export_results'] = export_results
            checkpoint_data['export_completed_at'] = datetime.utcnow().isoformat()
            migration.checkpoint_data = checkpoint_data
            
            # Update last_extracted_value for incremental loads
            if migration.load_type == 'incremental' and migration.timestamp_column:
                migration.last_extracted_value = datetime.utcnow().isoformat()
                logger.info(f"Updated last_extracted_value to {migration.last_extracted_value}")
            
            # Update migration progress
            total_tables = len(tables_to_export)
            exported_tables = len(successful_exports)
            migration.progress_percentage = int((exported_tables / total_tables) * 100) if total_tables > 0 else 0
            
            migration.updated_at = datetime.utcnow()
            self.db.commit()
            
            self._log(
                migration.id,
                'INFO',
                'export',
                f"Export completed: {exported_tables}/{total_tables} tables exported successfully ({migration.progress_percentage}% complete)"
            )
            
            # Return success only if all exports succeeded
            return len(failed_exports) == 0
            
        except Exception as e:
            error_msg = f"BigQuery export failed with exception: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # Log detailed error with stack trace
            import traceback
            stack_trace = traceback.format_exc()
            
            self._log(
                migration.id,
                'CRITICAL',
                'export',
                error_msg,
                error_code='EXPORT_EXCEPTION',
                log_metadata={
                    'exception_type': type(e).__name__,
                    'exception_message': str(e),
                    'stack_trace': stack_trace
                }
            )
            return False
    
    def _log(
        self,
        migration_id: int,
        level: str,
        stage: str,
        message: str,
        error_code: Optional[str] = None,
        log_metadata: Optional[Dict] = None
    ) -> None:
        """
        Create a migration log entry.
        
        Args:
            migration_id: Migration ID
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            stage: Migration stage
            message: Log message
            error_code: Optional error code
            log_metadata: Optional metadata dictionary
        """
        try:
            log = MigrationLog(
                migration_id=migration_id,
                log_level=level,
                stage=stage,
                message=message,
                error_code=error_code,
                log_metadata=log_metadata
            )
            self.db.add(log)
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to create log entry: {e}")
            self.db.rollback()
