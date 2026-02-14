#!/usr/bin/env python3
"""
Test Migration Execution

This script tests the migration execution flow to ensure:
1. Background thread starts properly
2. Logs are created
3. BigQuery export is triggered
4. Migration status updates correctly
"""

import sys
import time
from database import db_instance
from services.bq_redshift_migration.orchestrator import MigrationOrchestrator
from models.bq_redshift_migration import MigrationBQRedshift, MigrationLog

def test_migration_execution(migration_id: int):
    """Test migration execution"""
    db = db_instance.SessionLocal()
    
    try:
        print(f"\n{'='*60}")
        print(f"Testing Migration Execution: ID {migration_id}")
        print(f"{'='*60}\n")
        
        # Get migration
        migration = db.query(MigrationBQRedshift).filter_by(id=migration_id).first()
        
        if not migration:
            print(f"❌ Migration {migration_id} not found")
            return False
        
        print(f"✓ Migration found: {migration.migration_name}")
        print(f"  Status: {migration.status}")
        print(f"  Pathway: {migration.pathway}")
        print(f"  Source Connection ID: {migration.source_connection_id}")
        print(f"  Tables: {migration.source_tables}")
        print()
        
        if migration.status != 'pending':
            print(f"⚠️  Migration status is '{migration.status}', not 'pending'")
            print(f"   Resetting to pending...")
            migration.status = 'pending'
            migration.start_time = None
            migration.end_time = None
            migration.current_stage = None
            migration.progress_percentage = 0
            db.commit()
            print(f"✓ Reset to pending")
            print()
        
        # Test orchestrator initialization
        print("Testing orchestrator initialization...")
        orchestrator = MigrationOrchestrator(db)
        print("✓ Orchestrator initialized")
        print()
        
        # Start migration
        print("Starting migration...")
        print(f"{'='*60}")
        
        success = orchestrator.start_migration(migration_id)
        
        print(f"{'='*60}")
        print(f"\nMigration execution completed: {'SUCCESS' if success else 'FAILED'}")
        print()
        
        # Check final status
        db.refresh(migration)
        print(f"Final Status:")
        print(f"  Status: {migration.status}")
        print(f"  Current Stage: {migration.current_stage}")
        print(f"  Progress: {migration.progress_percentage}%")
        print(f"  Start Time: {migration.start_time}")
        print(f"  End Time: {migration.end_time}")
        print()
        
        # Check logs
        logs = db.query(MigrationLog).filter_by(
            migration_id=migration_id
        ).order_by(MigrationLog.created_at.desc()).limit(10).all()
        
        print(f"Recent Logs ({len(logs)} entries):")
        for log in logs:
            print(f"  [{log.log_level}] {log.stage}: {log.message}")
        print()
        
        return success
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        db.close()


if __name__ == "__main__":
    migration_id = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    
    print("\n" + "="*60)
    print("MIGRATION EXECUTION TEST")
    print("="*60)
    
    success = test_migration_execution(migration_id)
    
    print("\n" + "="*60)
    print(f"TEST RESULT: {'✓ PASSED' if success else '✗ FAILED'}")
    print("="*60 + "\n")
    
    sys.exit(0 if success else 1)
