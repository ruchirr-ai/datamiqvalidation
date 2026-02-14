"""
List all migrations
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database import get_db
from models.bq_redshift_migration import MigrationBQRedshift
from sqlalchemy import desc

def list_migrations():
    """List all migrations"""
    db = next(get_db())
    try:
        migrations = db.query(MigrationBQRedshift).order_by(desc(MigrationBQRedshift.id)).all()
        
        print("="*80)
        print(f"ALL MIGRATIONS ({len(migrations)} total)")
        print("="*80)
        print()
        
        for m in migrations:
            print(f"ID: {m.id}")
            print(f"Name: {m.migration_name}")
            print(f"Status: {m.status}")
            print(f"Pathway: {m.pathway}")
            print(f"Current Stage: {m.current_stage}")
            print(f"Created: {m.created_at}")
            print(f"Started: {m.start_time}")
            
            checkpoint = m.checkpoint_data or {}
            export_done = "✓" if checkpoint.get('export_completed_at') else "✗"
            transfer_done = "✓" if checkpoint.get('transfer_completed_at') else "✗"
            load_done = "✓" if checkpoint.get('load_completed_at') else "✗"
            print(f"Checkpoints: Export {export_done} | Transfer {transfer_done} | Load {load_done}")
            print("-" * 80)
        
    finally:
        db.close()

if __name__ == "__main__":
    list_migrations()
