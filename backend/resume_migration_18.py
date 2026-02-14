"""
Resume migration 18 from load stage
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database import get_db
from models.bq_redshift_migration import MigrationBQRedshift
from services.bq_redshift_migration.orchestrator import MigrationOrchestrator

def resume_migration():
    """Resume migration 18"""
    
    db = next(get_db())
    try:
        migration = db.query(MigrationBQRedshift).filter_by(id=18).first()
        
        if not migration:
            print("❌ Migration 18 not found")
            return False
        
        print("="*80)
        print(f"RESUMING MIGRATION 18: {migration.migration_name}")
        print("="*80)
        print(f"Status: {migration.status}")
        print(f"Current Stage: {migration.current_stage}")
        print()
        
        # Create orchestrator
        orchestrator = MigrationOrchestrator(db)
        
        print("Starting migration execution...")
        print("This will use the NEW FIXED code for load stage!")
        print()
        
        # Resume migration (it will continue from current stage)
        success = orchestrator.resume_migration(migration.id)
        
        if success:
            print()
            print("="*80)
            print("✅ MIGRATION COMPLETED SUCCESSFULLY")
            print("="*80)
            print()
            print("Check Redshift for data:")
            print(f"  Database: {migration.source_project_id.replace('-', '_').lower()}")
            print(f"  Schema: {migration.source_dataset}")
            print()
        else:
            print()
            print("="*80)
            print("❌ MIGRATION FAILED")
            print("="*80)
            print()
            print("Check logs for details:")
            print("  tail -100 backend.log")
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
    resume_migration()
