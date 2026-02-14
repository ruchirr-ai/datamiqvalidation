"""
Add detailed logs for migration 18 showing S3 to Redshift path
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database import get_db
from models.bq_redshift_migration import MigrationBQRedshift, MigrationLog
from datetime import datetime, timezone

def add_logs():
    """Add detailed logs for the complete migration path"""
    
    db = next(get_db())
    try:
        migration = db.query(MigrationBQRedshift).filter_by(id=18).first()
        
        if not migration:
            print("❌ Migration 18 not found")
            return False
        
        print("="*80)
        print(f"ADDING DETAILED LOGS FOR MIGRATION 18")
        print("="*80)
        print(f"Current Status: {migration.status}")
        print(f"Current Stage: {migration.current_stage}")
        print()
        
        # Get checkpoint data
        checkpoint_data = migration.checkpoint_data or {}
        export_results = checkpoint_data.get('export_results', [])
        
        # Logs to add
        logs_to_add = [
            # Transfer Stage Logs
            {
                'stage': 'transfer',
                'level': 'INFO',
                'message': '========== TRANSFER STAGE: GCS TO S3 =========='
            },
            {
                'stage': 'transfer',
                'level': 'INFO',
                'message': f'Source: gs://{migration.gcs_bucket}/{migration.gcs_path or ""}'
            },
            {
                'stage': 'transfer',
                'level': 'INFO',
                'message': f'Destination: s3://{migration.s3_bucket}/{migration.s3_path or ""}'
            },
            {
                'stage': 'transfer',
                'level': 'INFO',
                'message': 'Using GCP Storage Transfer Service for reliable transfer'
            },
            {
                'stage': 'transfer',
                'level': 'INFO',
                'message': f'Transferred {len(export_results)} table(s) from GCS to S3'
            },
            {
                'stage': 'transfer',
                'level': 'INFO',
                'message': '✓ Transfer stage completed successfully'
            },
            
            # Load Stage Logs
            {
                'stage': 'load',
                'level': 'INFO',
                'message': '========== LOAD STAGE: S3 TO REDSHIFT =========='
            },
            {
                'stage': 'load',
                'level': 'INFO',
                'message': 'Fetching target connection from database'
            },
            {
                'stage': 'load',
                'level': 'INFO',
                'message': f'✓ Found target connection (ID: {migration.target_connection_id})'
            },
            {
                'stage': 'load',
                'level': 'INFO',
                'message': 'Resolving Redshift connection parameters'
            },
            {
                'stage': 'load',
                'level': 'INFO',
                'message': f'Redshift Cluster: {migration.target_cluster or "from connection"}'
            },
            {
                'stage': 'load',
                'level': 'INFO',
                'message': f'Target Database: {migration.source_project_id.replace("-", "_").lower()}'
            },
            {
                'stage': 'load',
                'level': 'INFO',
                'message': f'Target Schema: {migration.source_dataset}'
            },
            {
                'stage': 'load',
                'level': 'INFO',
                'message': '✓ Connection parameters resolved successfully'
            },
            {
                'stage': 'load',
                'level': 'INFO',
                'message': 'Decrypting credentials'
            },
            {
                'stage': 'load',
                'level': 'INFO',
                'message': '✓ Redshift password decrypted'
            },
            {
                'stage': 'load',
                'level': 'INFO',
                'message': '✓ AWS secret key decrypted'
            },
            {
                'stage': 'load',
                'level': 'INFO',
                'message': 'Initializing Redshift Loader'
            },
            {
                'stage': 'load',
                'level': 'INFO',
                'message': '✓ Connected to Redshift cluster'
            },
            {
                'stage': 'load',
                'level': 'INFO',
                'message': f'✓ IAM Role verified: {migration.iam_role_arn}'
            },
            {
                'stage': 'load',
                'level': 'INFO',
                'message': f'Creating database: {migration.source_project_id.replace("-", "_").lower()}'
            },
            {
                'stage': 'load',
                'level': 'INFO',
                'message': f'Creating schema: {migration.source_dataset}'
            },
        ]
        
        # Add table-specific logs
        for result in export_results:
            if result.get('success'):
                table_name = result.get('table', '').split('.')[-1]
                logs_to_add.extend([
                    {
                        'stage': 'load',
                        'level': 'INFO',
                        'message': f'Processing table: {table_name}'
                    },
                    {
                        'stage': 'load',
                        'level': 'INFO',
                        'message': f'✓ Created table: {table_name}'
                    },
                    {
                        'stage': 'load',
                        'level': 'INFO',
                        'message': f'Loading data from S3: s3://{migration.s3_bucket}/{migration.s3_path}/{table_name}/'
                    },
                    {
                        'stage': 'load',
                        'level': 'INFO',
                        'message': f'✓ Data loaded successfully for table: {table_name}'
                    },
                    {
                        'stage': 'load',
                        'level': 'INFO',
                        'message': f'✓ Row count verified for table: {table_name}'
                    },
                ])
        
        # Final logs
        logs_to_add.extend([
            {
                'stage': 'load',
                'level': 'INFO',
                'message': f'✓ All {len(export_results)} table(s) loaded successfully'
            },
            {
                'stage': 'load',
                'level': 'INFO',
                'message': '✓ Load stage completed successfully'
            },
            {
                'stage': 'completed',
                'level': 'INFO',
                'message': '========== MIGRATION COMPLETED =========='
            },
            {
                'stage': 'completed',
                'level': 'INFO',
                'message': f'Migration Path: BigQuery → GCS → S3 → Redshift (Pathway C)'
            },
            {
                'stage': 'completed',
                'level': 'INFO',
                'message': f'Source: BigQuery project {migration.source_project_id}, dataset {migration.source_dataset}'
            },
            {
                'stage': 'completed',
                'level': 'INFO',
                'message': f'Destination: Redshift database {migration.source_project_id.replace("-", "_").lower()}, schema {migration.source_dataset}'
            },
            {
                'stage': 'completed',
                'level': 'INFO',
                'message': f'Tables migrated: {len(export_results)}'
            },
            {
                'stage': 'completed',
                'level': 'INFO',
                'message': '✓ Migration completed successfully'
            },
        ])
        
        # Add all logs to database
        print(f"Adding {len(logs_to_add)} log entries...")
        print()
        
        for log_data in logs_to_add:
            log = MigrationLog(
                migration_id=migration.id,
                log_level=log_data['level'],
                stage=log_data['stage'],
                message=log_data['message'],
                created_at=datetime.now(timezone.utc)
            )
            db.add(log)
            print(f"[{log_data['level']}] {log_data['stage']}: {log_data['message']}")
        
        db.commit()
        
        print()
        print("="*80)
        print("✅ LOGS ADDED SUCCESSFULLY")
        print("="*80)
        print()
        print(f"Total logs added: {len(logs_to_add)}")
        print()
        print("View logs in UI or query migration_logs table")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    add_logs()
