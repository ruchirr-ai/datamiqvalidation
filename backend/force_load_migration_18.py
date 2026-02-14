"""
Force load stage execution for migration 18 using the new fixed code
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database import get_db
from models.bq_redshift_migration import MigrationBQRedshift
from services.bq_redshift_migration.pathway_c import PathwayC
from services.bq_redshift_migration.checkpoint_manager import CheckpointManager
from services.bq_redshift_migration.manifest_handler import ManifestHandler

def force_load():
    """Force execute load stage for migration 18"""
    
    db = next(get_db())
    try:
        migration = db.query(MigrationBQRedshift).filter_by(id=18).first()
        
        if not migration:
            print("❌ Migration 18 not found")
            return False
        
        print("="*80)
        print(f"FORCE LOADING MIGRATION 18: {migration.migration_name}")
        print("="*80)
        print(f"Status: {migration.status}")
        print(f"Current Stage: {migration.current_stage}")
        print()
        
        # Get checkpoint data
        checkpoint_data = migration.checkpoint_data or {}
        
        print("CHECKPOINT STATUS:")
        print(f"Export completed: {checkpoint_data.get('export_completed_at', 'Not set')}")
        print(f"Transfer completed: {checkpoint_data.get('transfer_completed_at', 'Not set')}")
        print(f"Load completed: {checkpoint_data.get('load_completed_at', 'Not set')}")
        print()
        
        if not checkpoint_data.get('export_completed_at'):
            print("❌ Export stage not completed - cannot proceed to load")
            return False
        
        if not checkpoint_data.get('transfer_completed_at'):
            print("❌ Transfer stage not completed - cannot proceed to load")
            return False
        
        print("✅ Export and Transfer stages completed")
        print()
        print("="*80)
        print("EXECUTING LOAD STAGE WITH NEW FIXED CODE")
        print("="*80)
        print()
        
        # Create PathwayC instance
        checkpoint_manager = CheckpointManager(db)
        manifest_handler = ManifestHandler()
        
        def log_callback(migration_id, level, stage, message):
            print(f"[{level}] {message}")
        
        pathway_c = PathwayC(checkpoint_manager, manifest_handler, log_callback)
        
        # Prepare configurations (empty - will be fetched from database in load stage)
        target_config = {}
        storage_config = {
            's3_bucket': migration.s3_bucket,
            's3_path': migration.s3_path,
            'aws_region': 'us-east-1',
            'export_format': migration.export_format or 'PARQUET',
            'compression': migration.compression or 'NONE'
        }
        
        # Execute load stage
        print("Calling _execute_load_stage with new fixed code...")
        print()
        
        success = pathway_c._execute_load_stage(
            migration_id=migration.id,
            target_config=target_config,
            storage_config=storage_config,
            pending_shards=[],
            db=db
        )
        
        if success:
            print()
            print("="*80)
            print("✅ LOAD STAGE COMPLETED SUCCESSFULLY")
            print("="*80)
            print()
            
            # Update migration status
            migration.status = 'completed'
            migration.current_stage = 'completed'
            db.commit()
            
            print("✅ Migration status updated to 'completed'")
            print()
            print("Check Redshift for data:")
            print(f"  Database: {migration.source_project_id.replace('-', '_').lower()}")
            print(f"  Schema: {migration.source_dataset}")
            print()
            
            # Show tables
            export_results = checkpoint_data.get('export_results', [])
            if export_results:
                print("Tables loaded:")
                for result in export_results:
                    if result.get('success'):
                        print(f"  - {result.get('table')}")
            print()
        else:
            print()
            print("="*80)
            print("❌ LOAD STAGE FAILED")
            print("="*80)
            print()
            print("Check the output above for detailed error messages")
            print()
        
        return success
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    force_load()
