#!/usr/bin/env python3
"""Fix GCS bucket value in database by removing gs:// prefix"""

import sys
sys.path.insert(0, '/Users/manasakallakuri/Manasa/Data accelerator/DataMIQ Backup/backend')

from database import get_db
from models.bq_redshift_migration import MigrationBQRedshift

def clean_gcs_bucket(bucket: str) -> str:
    """Clean GCS bucket name by removing all gs:// and gs::// prefixes"""
    clean_bucket = bucket
    
    # Remove all occurrences of gs:// or gs::// prefix
    while clean_bucket.startswith('gs://') or clean_bucket.startswith('gs:://'):
        if clean_bucket.startswith('gs:://'):
            clean_bucket = clean_bucket[6:]  # Remove 'gs::/'
        elif clean_bucket.startswith('gs://'):
            clean_bucket = clean_bucket[5:]  # Remove 'gs://'
    
    # Also handle any remaining gs: prefix
    if clean_bucket.startswith('gs:'):
        clean_bucket = clean_bucket[3:]
    
    # Remove any leading slashes or colons
    clean_bucket = clean_bucket.lstrip('/:').strip()
    
    return clean_bucket

db = next(get_db())
try:
    # Get all migrations with GCS bucket
    migrations = db.query(MigrationBQRedshift).filter(
        MigrationBQRedshift.gcs_bucket.isnot(None)
    ).all()
    
    print(f'Found {len(migrations)} migrations with GCS bucket')
    print('='*80)
    
    for migration in migrations:
        original = migration.gcs_bucket
        cleaned = clean_gcs_bucket(original)
        
        if original != cleaned:
            print(f'\nMigration ID: {migration.id}')
            print(f'  Original: {repr(original)}')
            print(f'  Cleaned:  {repr(cleaned)}')
            print(f'  Will update: YES')
            
            # Update the database
            migration.gcs_bucket = cleaned
            db.commit()
            print(f'  ✓ Updated in database')
        else:
            print(f'\nMigration ID: {migration.id}')
            print(f'  Bucket: {repr(original)}')
            print(f'  Will update: NO (already clean)')
    
    print('\n' + '='*80)
    print('✓ All GCS buckets cleaned')
    
finally:
    db.close()
