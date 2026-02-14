"""
Check migration status and logs
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database import get_db
from models.bq_redshift_migration import MigrationBQRedshift, MigrationLog
from sqlalchemy import desc

def check_migration_status(migration_name: str = "bigquery_redshift_transfer"):
    """Check status of a migration by name"""
    db = next(get_db())
    try:
        # Find migration by name
        migration = db.query(MigrationBQRedshift).filter(
            MigrationBQRedshift.migration_name == migration_name
        ).first()
        
        if not migration:
            print(f"❌ Migration '{migration_name}' not found")
            return
        
        print("="*80)
        print(f"MIGRATION: {migration.migration_name}")
        print("="*80)
        print(f"ID: {migration.id}")
        print(f"Status: {migration.status}")
        print(f"Pathway: {migration.pathway}")
        print(f"Current Stage: {migration.current_stage}")
        print(f"Created: {migration.created_at}")
        print(f"Started: {migration.start_time}")
        print(f"Updated: {migration.updated_at}")
        print()
        
        # Check checkpoint data
        checkpoint_data = migration.checkpoint_data or {}
        print("="*80)
        print("CHECKPOINT DATA")
        print("="*80)
        print(f"Export completed: {checkpoint_data.get('export_completed_at', 'NOT COMPLETED')}")
        print(f"Transfer completed: {checkpoint_data.get('transfer_completed_at', 'NOT COMPLETED')}")
        print(f"Load completed: {checkpoint_data.get('load_completed_at', 'NOT COMPLETED')}")
        print()
        
        # Show export results if available
        export_results = checkpoint_data.get('export_results', [])
        if export_results:
            print(f"Export Results: {len(export_results)} tables")
            for result in export_results:
                status = "✓" if result.get('success') else "✗"
                print(f"  {status} {result.get('table', 'unknown')}")
            print()
        
        # Get recent logs
        print("="*80)
        print("RECENT LOGS (Last 50)")
        print("="*80)
        logs = db.query(MigrationLog).filter(
            MigrationLog.migration_id == migration.id
        ).order_by(desc(MigrationLog.created_at)).limit(50).all()
        
        if not logs:
            print("No logs found")
        else:
            for log in reversed(logs):  # Show oldest first
                level_icon = {
                    'INFO': 'ℹ️',
                    'WARNING': '⚠️',
                    'ERROR': '❌',
                    'DEBUG': '🔍'
                }.get(log.log_level, '•')
                print(f"{level_icon} [{log.stage}] {log.message}")
        
        print()
        print("="*80)
        
    finally:
        db.close()

if __name__ == "__main__":
    migration_name = sys.argv[1] if len(sys.argv) > 1 else "bigquery_redshift_transfer"
    check_migration_status(migration_name)
