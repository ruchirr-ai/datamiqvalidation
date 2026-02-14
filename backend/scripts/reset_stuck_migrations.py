#!/usr/bin/env python3
"""
Reset Stuck Migrations Script

This script resets migrations that are stuck in 'running' status.
Useful when migrations fail to complete due to server crashes or other issues.
"""

import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models.bq_redshift_migration import MigrationBQRedshift


def reset_stuck_migrations(hours_threshold: int = 1):
    """
    Reset migrations stuck in 'running' status for more than X hours.
    
    Args:
        hours_threshold: Number of hours after which a running migration is considered stuck
    """
    db = SessionLocal()
    
    try:
        # Find stuck migrations
        threshold_time = datetime.utcnow() - timedelta(hours=hours_threshold)
        
        stuck_migrations = db.query(MigrationBQRedshift).filter(
            MigrationBQRedshift.status == 'running',
            MigrationBQRedshift.updated_at < threshold_time
        ).all()
        
        if not stuck_migrations:
            print(f"✓ No stuck migrations found (threshold: {hours_threshold} hours)")
            return
        
        print(f"Found {len(stuck_migrations)} stuck migration(s):")
        print()
        
        for migration in stuck_migrations:
            print(f"  ID: {migration.id}")
            print(f"  Name: {migration.migration_name}")
            print(f"  Status: {migration.status}")
            print(f"  Stage: {migration.current_stage}")
            print(f"  Started: {migration.start_time}")
            print(f"  Last Updated: {migration.updated_at}")
            print()
        
        # Ask for confirmation
        response = input("Reset these migrations to 'failed' status? (yes/no): ")
        
        if response.lower() not in ['yes', 'y']:
            print("Cancelled.")
            return
        
        # Reset migrations
        for migration in stuck_migrations:
            migration.status = 'failed'
            migration.end_time = datetime.utcnow()
            migration.updated_at = datetime.utcnow()
            
            print(f"✓ Reset migration {migration.id} ({migration.migration_name}) to 'failed'")
        
        db.commit()
        print()
        print(f"✓ Successfully reset {len(stuck_migrations)} migration(s)")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        db.rollback()
    finally:
        db.close()


def reset_specific_migration(migration_id: int):
    """
    Reset a specific migration by ID.
    
    Args:
        migration_id: ID of the migration to reset
    """
    db = SessionLocal()
    
    try:
        migration = db.query(MigrationBQRedshift).filter_by(id=migration_id).first()
        
        if not migration:
            print(f"✗ Migration {migration_id} not found")
            return
        
        print(f"Migration Details:")
        print(f"  ID: {migration.id}")
        print(f"  Name: {migration.migration_name}")
        print(f"  Status: {migration.status}")
        print(f"  Stage: {migration.current_stage}")
        print(f"  Started: {migration.start_time}")
        print(f"  Last Updated: {migration.updated_at}")
        print()
        
        if migration.status not in ['running', 'paused']:
            print(f"✗ Migration is not in 'running' or 'paused' status (current: {migration.status})")
            return
        
        response = input(f"Reset migration {migration_id} to 'failed' status? (yes/no): ")
        
        if response.lower() not in ['yes', 'y']:
            print("Cancelled.")
            return
        
        migration.status = 'failed'
        migration.end_time = datetime.utcnow()
        migration.updated_at = datetime.utcnow()
        
        db.commit()
        print(f"✓ Successfully reset migration {migration_id} to 'failed'")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Reset stuck migrations")
    parser.add_argument(
        '--id',
        type=int,
        help='Reset specific migration by ID'
    )
    parser.add_argument(
        '--hours',
        type=int,
        default=1,
        help='Hours threshold for considering a migration stuck (default: 1)'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Reset Stuck Migrations")
    print("=" * 60)
    print()
    
    if args.id:
        reset_specific_migration(args.id)
    else:
        reset_stuck_migrations(args.hours)
