#!/usr/bin/env python3
"""
Fix migration status and checkpoint to allow resuming
"""

import sys
sys.path.insert(0, '/Users/manasakallakuri/Manasa/Data accelerator/DataMIQ Backup/backend')

from database import get_db
from models.bq_redshift_migration import MigrationBQRedshift
from datetime import datetime

def fix_and_prepare_resume(migration_id: int):
    """Fix migration status and checkpoint to allow resuming"""
    db = next(get_db())
    try:
        migration = db.query(MigrationBQRedshift).filter_by(id=migration_id).first()
        
        if not migration:
            print(f"❌ Migration {migration_id} not found")
            return False
        
        print(f"Migration ID: {migration_id}")
        print(f"Name: {migration.migration_name}")
        print(f"Current Status: {migration.status}")
        print(f"Current Stage: {migration.current_stage}")
        
        checkpoint_data = migration.checkpoint_data or {}
        
        print("\nCurrent Checkpoint Status:")
        print(f"  Export completed: {checkpoint_data.get('export_completed_at')}")
        print(f"  Transfer completed: {checkpoint_data.get('transfer_completed_at')}")
        print(f"  Load completed: {checkpoint_data.get('load_completed_at')}")
        
        # Fix 1: Mark transfer as complete if not already
        if not checkpoint_data.get('transfer_completed_at'):
            print("\n📝 Marking transfer stage as complete...")
            checkpoint_data['transfer_completed_at'] = datetime.utcnow().isoformat()
            checkpoint_data['transfer_stats'] = {
                'status': 'SUCCESS',
                'manually_marked': True,
                'marked_at': datetime.utcnow().isoformat()
            }
        
        # Fix 2: Change status from 'failed' to 'paused' to allow resume
        if migration.status == 'failed':
            print("📝 Changing status from 'failed' to 'paused' to allow resume...")
            migration.status = 'paused'
        
        # Fix 3: Set resume point to 'load' stage
        migration.resume_point = 'load'
        migration.current_stage = 'transfer'
        
        # Save changes
        migration.checkpoint_data = checkpoint_data
        migration.updated_at = datetime.utcnow()
        
        db.commit()
        
        print("\n✅ Migration fixed successfully!")
        print(f"   Status: {migration.status}")
        print(f"   Resume point: {migration.resume_point}")
        print(f"   Transfer checkpoint: {checkpoint_data.get('transfer_completed_at')}")
        print("\n🚀 You can now resume the migration from the UI")
        print("   It will proceed directly to the LOAD stage (S3 → Redshift)")
        
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
        print("Usage: python3 fix_and_resume_migration.py <migration_id>")
        print("\nExample: python3 fix_and_resume_migration.py 15")
        print("\nThis script will:")
        print("  1. Mark transfer stage as complete")
        print("  2. Change status from 'failed' to 'paused'")
        print("  3. Set resume point to 'load' stage")
        print("  4. Allow you to resume the migration from UI")
        sys.exit(1)
    
    migration_id = int(sys.argv[1])
    fix_and_prepare_resume(migration_id)
