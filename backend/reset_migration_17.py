"""
Reset migration 17 to allow it to run again with fixed code
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database import get_db
from models.bq_redshift_migration import MigrationBQRedshift
from datetime import datetime

def reset_migration():
    """Reset migration 17 to pending status"""
    db = next(get_db())
    try:
        migration = db.query(MigrationBQRedshift).filter_by(id=17).first()
        
        if not migration:
            print("❌ Migration 17 not found")
            return
        
        print("="*80)
        print(f"RESETTING MIGRATION: {migration.migration_name}")
        print("="*80)
        print(f"Current Status: {migration.status}")
        print(f"Current Stage: {migration.current_stage}")
        print()
        
        # Reset status
        migration.status = 'pending'
        migration.current_stage = None
        migration.start_time = None
        migration.end_time = None
        migration.duration_seconds = None
        migration.progress_percentage = 0
        migration.updated_at = datetime.utcnow()
        
        # Clear checkpoint data to start fresh
        migration.checkpoint_data = {}
        
        db.commit()
        
        print("✅ Migration reset successfully!")
        print()
        print("New Status: pending")
        print("Checkpoint Data: cleared")
        print()
        print("You can now run the migration again with the fixed code.")
        print("="*80)
        
    finally:
        db.close()

if __name__ == "__main__":
    reset_migration()
