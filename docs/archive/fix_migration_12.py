"""
Fix Migration 12 - Run Transfer and Load Stages

This script will manually execute the transfer and load stages for migration 12
since they were skipped due to a bug in the pathway execute logic.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import logging
from database import get_db
from models.bq_redshift_migration import MigrationBQRedshift
from services.bq_redshift_migration.pathway_c import PathwayC
from services.bq_redshift_migration.checkpoint_manager import CheckpointManager
from services.bq_redshift_migration.manifest_handler import ManifestHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_migration_12():
    """Fix migration 12 by running transfer and load stages"""
    
    migration_id = 12
    
    db = next(get_db())
    try:
        migration = db.query(MigrationBQRedshift).filter_by(id=migration_id).first()
        if not migration:
            logger.error(f"Migration {migration_id} not found")
            return False
        
        logger.info("="*80)
        logger.info(f"FIXING MIGRATION {migration_id}")
        logger.info("="*80)
        
        # Initialize pathway
        checkpoint_manager = CheckpointManager(db)
        manifest_handler = ManifestHandler()
        pathway = PathwayC(checkpoint_manager, manifest_handler)
        
        # Prepare storage config
        storage_config = {
            'gcs_bucket': migration.gcs_bucket,
            'gcs_path': migration.gcs_path,
            's3_bucket': migration.s3_bucket,
            's3_path': migration.s3_path,
            'project_id': migration.source_project_id,
            'source_connection_id': migration.source_connection_id,
            'aws_access_key_id': migration.aws_access_key_id,
            'aws_secret_access_key_encrypted': migration.aws_secret_access_key_encrypted,
            'overwrite_existing': migration.overwrite_existing_files == 'true',
            'delete_source': migration.delete_source_after_transfer == 'true',
            'export_format': migration.export_format or 'PARQUET',
            'compression': migration.compression or 'NONE'
        }
        
        # Get target connection for credentials
        from models.connection import Connection
        from services.encryption_service import get_encryption_service
        
        target_conn = db.query(Connection).filter_by(id=migration.target_connection_id).first()
        if not target_conn:
            logger.error(f"Target connection {migration.target_connection_id} not found")
            return False
        
        # Extract credentials from connection_params
        connection_params = target_conn.connection_params or {}
        
        # Get username
        username = (
            connection_params.get('username') or 
            connection_params.get('user') or
            'redshift_user'
        )
        
        # Get encrypted password
        password_encrypted = (
            connection_params.get('password_encrypted') or
            connection_params.get('passwordEncrypted') or
            connection_params.get('password')
        )
        
        if not password_encrypted:
            logger.error("Target connection password not found in connection_params")
            logger.error(f"Available keys: {list(connection_params.keys())}")
            return False
        
        logger.info(f"✓ Target credentials extracted from connection {migration.target_connection_id}")
        logger.info(f"  Username: {username}")
        logger.info(f"  Password: {'*' * 10} (encrypted)")
        
        # Check IAM role
        if not migration.iam_role_arn:
            logger.warning("⚠ IAM role ARN is not set in migration")
            logger.warning("  This is required for Redshift to access S3")
            logger.warning("  Load stage may fail without proper IAM role")
        else:
            logger.info(f"  IAM Role: {migration.iam_role_arn}")
        
        # Prepare target config
        target_config = {
            'cluster': migration.target_cluster,
            'database': migration.target_database,
            'schema': migration.target_schema or 'public',
            'username': username,
            'password_encrypted': password_encrypted,
            'iam_role_arn': migration.iam_role_arn,
            'port': connection_params.get('port', 5439)
        }
        
        # Check current state
        checkpoint_data = migration.checkpoint_data or {}
        export_completed = checkpoint_data.get('export_completed_at') is not None
        transfer_completed = checkpoint_data.get('transfer_completed_at') is not None
        load_completed = checkpoint_data.get('load_completed_at') is not None
        
        logger.info(f"Current state:")
        logger.info(f"  Export: {'✓' if export_completed else '✗'}")
        logger.info(f"  Transfer: {'✓' if transfer_completed else '✗'}")
        logger.info(f"  Load: {'✓' if load_completed else '✗'}")
        logger.info("="*80)
        
        # Run transfer stage if not completed
        if not transfer_completed:
            logger.info("Running TRANSFER stage...")
            success = pathway._execute_transfer_stage(migration_id, storage_config)
            if not success:
                logger.error("Transfer stage failed")
                return False
            logger.info("✓ Transfer stage completed")
            
            # Refresh migration
            db.refresh(migration)
            checkpoint_data = migration.checkpoint_data or {}
            transfer_completed = checkpoint_data.get('transfer_completed_at') is not None
        else:
            logger.info("✓ Transfer already completed, skipping")
        
        # Run load stage if not completed
        if not load_completed:
            logger.info("Running LOAD stage...")
            success = pathway._execute_load_stage(
                migration_id,
                target_config,
                storage_config,
                []
            )
            if not success:
                logger.error("Load stage failed")
                return False
            logger.info("✓ Load stage completed")
        else:
            logger.info("✓ Load already completed, skipping")
        
        # Update migration status
        migration.status = 'completed'
        migration.current_stage = 'load'
        db.commit()
        
        logger.info("="*80)
        logger.info("✓ MIGRATION 12 FIXED SUCCESSFULLY")
        logger.info("="*80)
        return True
        
    except Exception as e:
        logger.error(f"Failed to fix migration: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == '__main__':
    success = fix_migration_12()
    sys.exit(0 if success else 1)
