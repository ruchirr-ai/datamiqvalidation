#!/usr/bin/env python3
"""
Run only the load stage (S3 → Redshift) for a migration where data is already in S3
"""

import sys
sys.path.insert(0, '/Users/manasakallakuri/Manasa/Data accelerator/DataMIQ Backup/backend')

from database import get_db
from models.bq_redshift_migration import MigrationBQRedshift
from models.connection import Connection
from services.bq_redshift_migration.pathway_c import PathwayC
from services.bq_redshift_migration.checkpoint_manager import CheckpointManager
from services.bq_redshift_migration.manifest_handler import ManifestHandler
from services.encryption_service import get_encryption_service
from datetime import datetime

def run_load_stage(migration_id: int):
    """Run only the load stage for a migration"""
    db = next(get_db())
    try:
        migration = db.query(MigrationBQRedshift).filter_by(id=migration_id).first()
        
        if not migration:
            print(f"❌ Migration {migration_id} not found")
            return False
        
        print(f"Migration ID: {migration_id}")
        print(f"Name: {migration.migration_name}")
        print(f"Pathway: {migration.pathway}")
        print(f"Status: {migration.status}")
        
        # Get target connection details
        target_conn = db.query(Connection).filter_by(id=migration.target_connection_id).first()
        if not target_conn:
            print(f"❌ Target connection {migration.target_connection_id} not found")
            return False
        
        conn_params = target_conn.connection_params or {}
        
        # Prepare target config
        target_config = {
            'cluster': conn_params.get('host') or conn_params.get('server_name') or migration.target_cluster,
            'port': int(conn_params.get('port', 5439)),
            'database': conn_params.get('database') or conn_params.get('database_name') or migration.target_database,
            'schema': migration.target_schema or 'public',
            'username': conn_params.get('username'),
            'password_encrypted': conn_params.get('password_encrypted'),
            'iam_role_arn': migration.iam_role_arn
        }
        
        # Prepare storage config
        storage_config = {
            's3_bucket': migration.s3_bucket,
            's3_path': migration.s3_path,
            'export_format': migration.export_format or 'AVRO',
            'compression': migration.compression or 'NONE'
        }
        
        print(f"\nTarget Config:")
        print(f"  Cluster: {target_config['cluster']}")
        print(f"  Database: {target_config['database']}")
        print(f"  Schema: {target_config['schema']}")
        print(f"  IAM Role: {target_config['iam_role_arn']}")
        
        print(f"\nStorage Config:")
        print(f"  S3 Bucket: {storage_config['s3_bucket']}")
        print(f"  S3 Path: {storage_config['s3_path']}")
        print(f"  Format: {storage_config['export_format']}")
        
        # Update migration status
        migration.status = 'running'
        migration.current_stage = 'load'
        migration.updated_at = datetime.utcnow()
        db.commit()
        
        print(f"\n🚀 Starting LOAD stage (S3 → Redshift)...")
        print("="*80)
        
        # Initialize PathwayC
        checkpoint_manager = CheckpointManager(db)
        manifest_handler = ManifestHandler()
        
        def log_callback(migration_id, level, stage, message, **kwargs):
            """Log callback for PathwayC"""
            from models.bq_redshift_migration import MigrationLog
            log = MigrationLog(
                migration_id=migration_id,
                log_level=level,
                stage=stage,
                message=message
            )
            db.add(log)
            db.commit()
        
        pathway_c = PathwayC(checkpoint_manager, manifest_handler, log_callback)
        
        # Run load stage
        success = pathway_c._execute_load_stage(
            migration_id,
            target_config,
            storage_config,
            []  # No shards for Path C
        )
        
        if success:
            print("\n" + "="*80)
            print("✅ LOAD STAGE COMPLETED SUCCESSFULLY")
            print("="*80)
            
            # Update migration status
            migration.status = 'completed'
            migration.end_time = datetime.utcnow()
            migration.updated_at = datetime.utcnow()
            
            # Mark load as complete in checkpoint
            checkpoint_data = migration.checkpoint_data or {}
            checkpoint_data['load_completed_at'] = datetime.utcnow().isoformat()
            migration.checkpoint_data = checkpoint_data
            
            db.commit()
            
            print("\n✅ Migration marked as completed in database")
            return True
        else:
            print("\n" + "="*80)
            print("❌ LOAD STAGE FAILED")
            print("="*80)
            
            migration.status = 'failed'
            migration.updated_at = datetime.utcnow()
            db.commit()
            
            return False
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
        # Update migration status
        migration = db.query(MigrationBQRedshift).filter_by(id=migration_id).first()
        if migration:
            migration.status = 'failed'
            migration.updated_at = datetime.utcnow()
            db.commit()
        
        return False
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 run_load_stage_only.py <migration_id>")
        print("\nExample: python3 run_load_stage_only.py 15")
        print("\nThis script will:")
        print("  1. Skip export and transfer stages (data already in S3)")
        print("  2. Run ONLY the load stage (S3 → Redshift)")
        print("  3. Use the Redshift COPY command with IAM role")
        print("  4. Mark migration as completed if successful")
        sys.exit(1)
    
    migration_id = int(sys.argv[1])
    success = run_load_stage(migration_id)
    sys.exit(0 if success else 1)
