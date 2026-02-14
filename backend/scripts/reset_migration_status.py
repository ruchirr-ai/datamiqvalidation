#!/usr/bin/env python3
"""
Reset Migration Status

Resets a migration to 'pending' status so it can be restarted.
Useful when a migration gets stuck in 'running' status.
"""

import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from models.bq_redshift_migration import MigrationBQRedshift

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://manasakallakuri@localhost/datamiq')

def reset_migration_status(migration_id: int):
    """Reset migration to pending status"""
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        migration = session.query(MigrationBQRedshift).filter_by(id=migration_id).first()
        
        if not migration:
            print(f"❌ Migration {migration_id} not found")
            return False
        
        print(f"Migration: {migration.migration_name}")
        print(f"Current Status: {migration.status}")
        print(f"Current Stage: {migration.current_stage}")
        
        # Reset to pending
        migration.status = 'pending'
        migration.current_stage = None
        migration.start_time = None
        migration.end_time = None
        migration.duration_seconds = None
        migration.progress_percentage = 0
        migration.checkpoint_data = {}
        migration.updated_at = datetime.utcnow()
        
        session.commit()
        
        print(f"✅ Migration {migration_id} reset to 'pending' status")
        print(f"You can now restart the migration from the UI")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        session.rollback()
        return False
    finally:
        session.close()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python reset_migration_status.py <migration_id>")
        print("Example: python reset_migration_status.py 9")
        sys.exit(1)
    
    migration_id = int(sys.argv[1])
    reset_migration_status(migration_id)
