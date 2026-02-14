#!/usr/bin/env python3
"""
Fix transfer checkpoint for migrations where transfer completed but checkpoint wasn't saved
"""

import sys
sys.path.insert(0, '/Users/manasakallakuri/Manasa/Data accelerator/DataMIQ Backup/backend')

from database import get_db
from models.bq_redshift_migration import MigrationBQRedshift
from datetime import datetime

def fix_transfer_checkpoint(migration_id: int):
    """Mark transfer stage as complete for a migration"""
    db = next(get_db())
    try:
        migration = db.query(MigrationBQRedshift).filter_by(id=migration_id).first()
        
        if not migration:
            print(f"❌ Migration {migration_id} not found")
            return False
        
        print(f"Migration ID: {migration_id}")
        print(f"Name: {migration.migration_name}")
        print(f"Status: {migration.status}")
        print(f"Current Stage: {migration.current_stage}")
        
        checkpoint_data = migration.checkpoint_data or {}
        
        print("\nCurrent Checkpoint Status:")
        print(f"  Export completed: {checkpoint_data.get('export_completed_at')}")
        print(f"  Transfer completed: {checkpoint_data.get('transfer_completed_at')}")
        print(f"  Load completed: {checkpoint_data.get('load_completed_at')}")
        
        # Check if transfer already marked complete
        if checkpoint_data.get('transfer_completed_at'):
            print("\n✓ Transfer already marked as complete")
            return True
        
        # Mark transfer as complete
        checkpoint_data['transfer_completed_at'] = datetime.utcnow().isoformat()
        checkpoint_data['transfer_stats'] = {
            'status': 'SUCCESS',
            'manually_marked': True,
            'marked_at': datetime.utcnow().isoformat()
        }
        
        migration.checkpoint_data = checkpoint_data
        migration.current_stage = 'transfer'
        migration.updated_at = datetime.utcnow()
        
        db.commit()
        
        print("\n✅ Transfer checkpoint saved successfully")
        print(f"   transfer_completed_at: {checkpoint_data['transfer_completed_at']}")
        print("\nYou can now resume the migration - it will proceed to the load stage")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 fix_transfer_checkpoint.py <migration_id>")
        print("\nExample: python3 fix_transfer_checkpoint.py 15")
        sys.exit(1)
    
    migration_id = int(sys.argv[1])
    fix_transfer_checkpoint(migration_id)
