#!/usr/bin/env python3
"""Check GCS bucket value in database"""

from database import get_db
from models.bq_redshift_migration import MigrationBQRedshift

db = next(get_db())
try:
    # Get the latest migration
    migration = db.query(MigrationBQRedshift).order_by(MigrationBQRedshift.id.desc()).first()
    if migration:
        print(f'Migration ID: {migration.id}')
        print(f'GCS Bucket (raw): |{migration.gcs_bucket}|')
        print(f'GCS Bucket (repr): {repr(migration.gcs_bucket)}')
        print(f'Length: {len(migration.gcs_bucket)}')
        print(f'Starts with gs://: {migration.gcs_bucket.startswith("gs://")}')
        print(f'Starts with gs:://: {migration.gcs_bucket.startswith("gs:://")}')
        
        # Show each character
        print('\nCharacter breakdown:')
        for i, char in enumerate(migration.gcs_bucket[:30]):
            print(f'  [{i}] = {repr(char)} (ord={ord(char)})')
        
        # Test cleaning logic
        print('\n--- Testing Cleaning Logic ---')
        clean_bucket = migration.gcs_bucket
        print(f'Original: {repr(clean_bucket)}')
        
        while clean_bucket.startswith('gs://') or clean_bucket.startswith('gs:://'):
            if clean_bucket.startswith('gs:://'):
                clean_bucket = clean_bucket[6:]
                print(f'After removing gs:://: {repr(clean_bucket)}')
            elif clean_bucket.startswith('gs://'):
                clean_bucket = clean_bucket[5:]
                print(f'After removing gs://: {repr(clean_bucket)}')
        
        if clean_bucket.startswith('gs:'):
            clean_bucket = clean_bucket[3:]
            print(f'After removing gs:: {repr(clean_bucket)}')
        
        clean_bucket = clean_bucket.lstrip('/:').strip()
        print(f'After lstrip and strip: {repr(clean_bucket)}')
        print(f'\nFinal cleaned bucket: {clean_bucket}')
finally:
    db.close()
