"""
Check migration 18 status and fix transfer checkpoint if needed
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database import get_db
from models.bq_redshift_migration import MigrationBQRedshift
from datetime import datetime
import json

def check_and_fix_migration():
    """Check migration 18 and fix if transfer completed but not marked"""
    
    db = next(get_db())
    try:
        migration = db.query(MigrationBQRedshift).filter_by(id=18).first()
        
        if not migration:
            print("❌ Migration 18 not found")
            return False
        
        print("="*80)
        print(f"MIGRATION 18: {migration.migration_name}")
        print("="*80)
        print(f"Status: {migration.status}")
        print(f"Current Stage: {migration.current_stage}")
        print()
        
        # Check checkpoint data
        checkpoint_data = migration.checkpoint_data or {}
        
        print("CHECKPOINT DATA:")
        print(f"Export completed: {checkpoint_data.get('export_completed_at', 'Not set')}")
        print(f"Transfer completed: {checkpoint_data.get('transfer_completed_at', 'Not set')}")
        print(f"Load completed: {checkpoint_data.get('load_completed_at', 'Not set')}")
        print()
        
        # Check if export results exist
        export_results = checkpoint_data.get('export_results', [])
        print(f"Export results: {len(export_results)} tables")
        if export_results:
            for result in export_results:
                print(f"  - {result.get('table')}: {'✓' if result.get('success') else '✗'}")
        print()
        
        # Check S3 files
        print("STORAGE CONFIGURATION:")
        print(f"GCS Bucket: {migration.gcs_bucket}")
        print(f"GCS Path: {migration.gcs_path}")
        print(f"S3 Bucket: {migration.s3_bucket}")
        print(f"S3 Path: {migration.s3_path}")
        print()
        
        # Ask user if they want to mark transfer as completed
        if not checkpoint_data.get('transfer_completed_at'):
            print("="*80)
            print("TRANSFER STAGE NOT MARKED AS COMPLETED")
            print("="*80)
            print()
            print("Options:")
            print("1. Mark transfer as completed (if files are in S3)")
            print("2. Reset to export stage (to restart transfer)")
            print("3. Cancel (do nothing)")
            print()
            
            choice = input("Enter choice (1/2/3): ").strip()
            
            if choice == "1":
                # Mark transfer as completed
                from datetime import datetime, timezone
                checkpoint_data['transfer_completed_at'] = datetime.now(timezone.utc).isoformat()
                
                # Force SQLAlchemy to detect the change
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(migration, 'checkpoint_data')
                
                migration.current_stage = 'load'
                migration.status = 'running'
                
                db.commit()
                db.refresh(migration)  # Refresh to get updated data
                
                print()
                print("✅ Transfer stage marked as completed")
                print("✅ Current stage set to 'load'")
                print("✅ Status set to 'running'")
                print()
                print("Verifying update...")
                updated_checkpoint = migration.checkpoint_data or {}
                print(f"Transfer completed at: {updated_checkpoint.get('transfer_completed_at', 'NOT SET!')}")
                print()
                print("The migration will now proceed to the load stage with the new fixed code!")
                print()
                print("Monitor progress:")
                print("  tail -f backend.log")
                print()
                return True
                
            elif choice == "2":
                # Reset to export stage
                checkpoint_data['transfer_completed_at'] = None
                checkpoint_data['load_completed_at'] = None
                migration.checkpoint_data = checkpoint_data
                migration.current_stage = 'export'
                migration.status = 'pending'
                
                db.commit()
                
                print()
                print("✅ Migration reset to export stage")
                print("✅ Status set to 'pending'")
                print()
                print("You can now restart the migration from the UI")
                print()
                return True
                
            else:
                print()
                print("❌ No changes made")
                return False
        else:
            print("✅ Transfer already marked as completed")
            print(f"   Completed at: {checkpoint_data.get('transfer_completed_at')}")
            
            if migration.current_stage != 'load':
                print()
                print("⚠️  But current stage is not 'load'")
                print(f"   Current stage: {migration.current_stage}")
                print()
                
                fix = input("Set current stage to 'load'? (y/n): ").strip().lower()
                if fix == 'y':
                    migration.current_stage = 'load'
                    migration.status = 'running'
                    db.commit()
                    
                    print()
                    print("✅ Current stage set to 'load'")
                    print("✅ Status set to 'running'")
                    print()
                    return True
            
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    check_and_fix_migration()
