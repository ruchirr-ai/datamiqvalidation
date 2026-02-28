"""
Migration Script: Fernet to AWS KMS Encryption

This script migrates existing encrypted data from Fernet encryption to AWS KMS encryption.
It re-encrypts all encrypted fields in the database using the new KMS encryption service.

Usage:
    python scripts/migrate_to_kms_encryption.py [--dry-run]

Requirements:
    - AWS credentials configured (IAM role or environment variables)
    - KMS key ID stored in AWS Secrets Manager
    - Database connection configured in .env
"""

import sys
import logging
from datetime import datetime
from typing import List, Tuple

from database import get_db
from models.bq_redshift_migration import MigrationBQRedshift
from models.connection import Connection
from services.encryption_service import get_encryption_service as get_old_encryption_service
from services.kms_encryption_service import get_kms_encryption_service

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def migrate_migration_aws_secrets(db, dry_run: bool = False) -> Tuple[int, int]:
    """
    Migrate AWS secret keys in migrations from Fernet to KMS encryption.
    
    Returns:
        Tuple of (success_count, error_count)
    """
    logger.info("="*80)
    logger.info("MIGRATING MIGRATION AWS SECRET KEYS")
    logger.info("="*80)
    
    old_service = get_old_encryption_service()
    new_service = get_kms_encryption_service()
    
    migrations = db.query(MigrationBQRedshift).filter(
        MigrationBQRedshift.aws_secret_access_key_encrypted.isnot(None),
        MigrationBQRedshift.aws_secret_access_key_encrypted != ''
    ).all()
    
    logger.info(f"Found {len(migrations)} migrations with encrypted AWS secrets")
    
    success_count = 0
    error_count = 0
    
    for migration in migrations:
        try:
            logger.info(f"\nProcessing migration {migration.id}: {migration.migration_name}")
            
            # Decrypt with old service
            logger.info("  Decrypting with Fernet...")
            decrypted_secret = old_service.decrypt(migration.aws_secret_access_key_encrypted)
            logger.info(f"  ✓ Decrypted successfully (length: {len(decrypted_secret)})")
            
            # Encrypt with new service
            logger.info("  Encrypting with KMS...")
            encryption_context = {
                'migration_id': str(migration.id),
                'field': 'aws_secret_access_key',
                'migrated_at': datetime.utcnow().isoformat()
            }
            new_encrypted = new_service.encrypt(decrypted_secret, encryption_context)
            logger.info(f"  ✓ Encrypted successfully with KMS")
            
            # Verify by decrypting
            logger.info("  Verifying encryption...")
            verified = new_service.decrypt(new_encrypted, encryption_context)
            if verified != decrypted_secret:
                raise ValueError("Verification failed: decrypted value doesn't match original")
            logger.info("  ✓ Verification successful")
            
            if not dry_run:
                # Update database
                migration.aws_secret_access_key_encrypted = new_encrypted
                migration.updated_at = datetime.utcnow()
                db.commit()
                logger.info("  ✓ Database updated")
            else:
                logger.info("  [DRY RUN] Would update database")
            
            success_count += 1
            logger.info(f"  ✓ Migration {migration.id} completed successfully")
            
        except Exception as e:
            error_count += 1
            logger.error(f"  ✗ Failed to migrate migration {migration.id}: {e}")
            if not dry_run:
                db.rollback()
    
    logger.info("\n" + "="*80)
    logger.info(f"MIGRATION AWS SECRETS: {success_count} succeeded, {error_count} failed")
    logger.info("="*80)
    
    return success_count, error_count


def migrate_connection_passwords(db, dry_run: bool = False) -> Tuple[int, int]:
    """
    Migrate connection passwords from Fernet to KMS encryption.
    
    Note: Currently connection_params are stored as JSON and NOT encrypted.
    This function will encrypt them for the first time using KMS.
    
    Returns:
        Tuple of (success_count, error_count)
    """
    logger.info("\n" + "="*80)
    logger.info("MIGRATING CONNECTION PARAMETERS")
    logger.info("="*80)
    
    new_service = get_kms_encryption_service()
    
    connections = db.query(Connection).filter(
        Connection.is_active == True,
        Connection.connection_params.isnot(None)
    ).all()
    
    logger.info(f"Found {len(connections)} active connections with parameters")
    
    success_count = 0
    error_count = 0
    
    for conn in connections:
        try:
            logger.info(f"\nProcessing connection {conn.id}: {conn.name} ({conn.database})")
            
            # Connection params are currently NOT encrypted - this is first-time encryption
            import json
            
            # Get current params
            params = conn.connection_params
            logger.info(f"  Current params keys: {list(params.keys())}")
            
            # Encrypt the entire params JSON
            logger.info("  Encrypting connection parameters with KMS...")
            encryption_context = {
                'connection_id': str(conn.id),
                'field': 'connection_params',
                'migrated_at': datetime.utcnow().isoformat()
            }
            params_json = json.dumps(params)
            encrypted_params = new_service.encrypt(params_json, encryption_context)
            logger.info(f"  ✓ Encrypted successfully with KMS")
            
            # Verify by decrypting
            logger.info("  Verifying encryption...")
            verified = new_service.decrypt(encrypted_params, encryption_context)
            if verified != params_json:
                raise ValueError("Verification failed: decrypted value doesn't match original")
            logger.info("  ✓ Verification successful")
            
            if not dry_run:
                # Add new encrypted column (will be added via migration)
                # For now, just log what would happen
                logger.info("  [INFO] Would store encrypted params in connection_params_encrypted column")
                logger.info("  [INFO] Schema migration needed to add connection_params_encrypted column")
            else:
                logger.info("  [DRY RUN] Would encrypt and store connection parameters")
            
            success_count += 1
            logger.info(f"  ✓ Connection {conn.id} completed successfully")
            
        except Exception as e:
            error_count += 1
            logger.error(f"  ✗ Failed to migrate connection {conn.id}: {e}")
            if not dry_run:
                db.rollback()
    
    logger.info("\n" + "="*80)
    logger.info(f"CONNECTION PARAMETERS: {success_count} succeeded, {error_count} failed")
    logger.info("="*80)
    logger.info("\nNOTE: Schema migration required to add connection_params_encrypted column")
    logger.info("Run: alembic revision --autogenerate -m 'add_encrypted_connection_params'")
    
    return success_count, error_count


def main():
    """Main migration function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate encryption from Fernet to AWS KMS')
    parser.add_argument('--dry-run', action='store_true', help='Run without making changes')
    args = parser.parse_args()
    
    logger.info("="*80)
    logger.info("ENCRYPTION MIGRATION: FERNET → AWS KMS")
    logger.info("="*80)
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    logger.info("="*80)
    
    if args.dry_run:
        logger.warning("\n⚠️  DRY RUN MODE - No changes will be made to the database")
    else:
        logger.warning("\n⚠️  LIVE MODE - Database will be modified")
        response = input("\nContinue? (yes/no): ")
        if response.lower() != 'yes':
            logger.info("Migration cancelled")
            return
    
    db = next(get_db())
    
    try:
        # Test KMS encryption service
        logger.info("\n" + "="*80)
        logger.info("TESTING KMS ENCRYPTION SERVICE")
        logger.info("="*80)
        
        kms_service = get_kms_encryption_service()
        test_data = "test-secret-123"
        test_context = {'test': 'true'}
        
        logger.info("Encrypting test data...")
        encrypted = kms_service.encrypt(test_data, test_context)
        logger.info("✓ Encryption successful")
        
        logger.info("Decrypting test data...")
        decrypted = kms_service.decrypt(encrypted, test_context)
        logger.info("✓ Decryption successful")
        
        if decrypted != test_data:
            raise ValueError("Test failed: decrypted data doesn't match original")
        logger.info("✓ KMS encryption service working correctly")
        
        # Migrate migration AWS secrets
        mig_success, mig_error = migrate_migration_aws_secrets(db, args.dry_run)
        
        # Migrate connection passwords (first-time encryption)
        conn_success, conn_error = migrate_connection_passwords(db, args.dry_run)
        
        # Summary
        logger.info("\n" + "="*80)
        logger.info("MIGRATION SUMMARY")
        logger.info("="*80)
        logger.info(f"Migration AWS Secrets: {mig_success} succeeded, {mig_error} failed")
        logger.info(f"Connection Parameters: {conn_success} succeeded, {conn_error} failed")
        logger.info(f"Total: {mig_success + conn_success} succeeded, {mig_error + conn_error} failed")
        logger.info("="*80)
        
        if args.dry_run:
            logger.info("\n✓ DRY RUN COMPLETED - No changes made")
        else:
            logger.info("\n✓ MIGRATION COMPLETED")
            logger.info("\nNEXT STEPS:")
            logger.info("1. Create database migration for connection_params_encrypted column")
            logger.info("2. Update code to use get_kms_encryption_service() instead of get_encryption_service()")
            logger.info("3. Test all encryption/decryption operations")
            logger.info("4. Deploy updated code")
        
    except Exception as e:
        logger.error(f"\n✗ MIGRATION FAILED: {e}")
        import traceback
        logger.error(traceback.format_exc())
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == '__main__':
    main()
