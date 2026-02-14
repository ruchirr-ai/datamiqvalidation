"""Check IAM role for migration 12"""
import sys
sys.path.insert(0, '.')

from database import get_db
from models.bq_redshift_migration import MigrationBQRedshift

db = next(get_db())

migration = db.query(MigrationBQRedshift).filter_by(id=12).first()

if migration:
    print(f'Migration ID: {migration.id}')
    print(f'Migration Name: {migration.migration_name}')
    print(f'IAM Role ARN: {migration.iam_role_arn}')
    print(f'Target Connection ID: {migration.target_connection_id}')
    print(f'S3 Bucket: {migration.s3_bucket}')
    print(f'S3 Path: {migration.s3_path}')
else:
    print('Migration 12 not found')

db.close()
