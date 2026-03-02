"""
Encrypt Existing Plaintext Credentials

This script encrypts all plaintext credentials in the database using AWS KMS.
It handles:
- AWS Access Keys & Secret Keys in migrations
- GCP Service Account JSON in migrations
- GCP HMAC keys in migrations
- Connection passwords
- Any other sensitive fields

Usage:
    python scripts/encrypt_existing_credentials.py [--dry-run] [--force]
    
Options:
    --dry-run: Show what would be encrypted without making changes
    --force: Skip confirmation prompt
    
Prerequisites:
    1. AWS credentials configured (IAM role or environment variables)
    2. Secret "datamiq" exists in AWS Secrets Manager with "kms_arn" key
    3. KMS key exists and IAM role has encrypt/decrypt permissions
"""

import sys
import os
import argparse
import logging
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import db_instance
from models.bq_redshift_migration import MigrationBQRedshift
from models.connection import Connection
from services.unified_kms_service import get_unified_kms_service
from sqlalchemy.orm.attributes import flag_modified

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CredentialEncryptor:
    """Encrypts plaintext credentials in the database"""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.kms = get_unified_kms_service()
        self.db = db_instance.SessionLocal()
        
        # Statistics
        self.stats = {
            'migrations_processed': 0,
            'migrations_encrypted': 0,
            'connections_processed': 0,
            'connections_encrypted': 0,
            'fields_encrypted': 0,
            'errors': 0
        }
    
    def encrypt_migration_credentials(self):
        """Encrypt credentials in migrations_bq_redshift table"""
        logger.info("=" * 80)
        logger.info("ENCRYPTING MIGRATION CREDENTIALS")
        logger.info("=" * 80)
        
        migrations = self.db.query(MigrationBQRedshift).all()
        logger.info(f"Found {len(migrations)} migrations to process")
        
        for migration in migrations:
            self.stats['migrations_processed'] += 1
            encrypted_any = False
            
            logger.info(f"\nProcessing Migration {migration.id}: {migration.migration_name}")
            
            # AWS Secret Access Key
            if migration.aws_secret_access_key_encrypted:
                if not self.kms.is_encrypted(migration.aws_secret_access_key_encrypted):
                    logger.info(f"  - Encrypting AWS Secret Access Key")
                    if not self.dry_run:
                        try:
                            migration.aws_secret_access_key_encrypted = self.kms.encrypt_credential(
                                plaintext=migration.aws_secret_access_key_encrypted,
                                credential_type='aws_secret_key',
                                resource_type='migration',
                                resource_id=migration.id
                            )
                            self.stats['fields_encrypted'] += 1
                            encrypted_any = True
                        except Exception as e:
                            logger.error(f"    ERROR: {e}")
                            self.stats['errors'] += 1
                else:
                    logger.info(f"  - AWS Secret Access Key already encrypted")
            
            # GCP Secret Key (HMAC)
            if migration.gcs_secret_key_encrypted:
                if not self.kms.is_encrypted(migration.gcs_secret_key_encrypted):
                    logger.info(f"  - Encrypting GCP HMAC Secret Key")
                    if not self.dry_run:
                        try:
                            migration.gcs_secret_key_encrypted = self.kms.encrypt_credential(
                                plaintext=migration.gcs_secret_key_encrypted,
                                credential_type='gcp_hmac_secret',
                                resource_type='migration',
                                resource_id=migration.id
                            )
                            self.stats['fields_encrypted'] += 1
                            encrypted_any = True
                        except Exception as e:
                            logger.error(f"    ERROR: {e}")
                            self.stats['errors'] += 1
                else:
                    logger.info(f"  - GCP HMAC Secret Key already encrypted")
            
            # GCP Service Account JSON
            if migration.service_account_json_encrypted:
                if not self.kms.is_encrypted(migration.service_account_json_encrypted):
                    logger.info(f"  - Encrypting GCP Service Account JSON")
                    if not self.dry_run:
                        try:
                            migration.service_account_json_encrypted = self.kms.encrypt_credential(
                                plaintext=migration.service_account_json_encrypted,
                                credential_type='gcp_service_account',
                                resource_type='migration',
                                resource_id=migration.id
                            )
                            self.stats['fields_encrypted'] += 1
                            encrypted_any = True
                        except Exception as e:
                            logger.error(f"    ERROR: {e}")
                            self.stats['errors'] += 1
                else:
                    logger.info(f"  - GCP Service Account JSON already encrypted")
            
            if encrypted_any:
                self.stats['migrations_encrypted'] += 1
                if not self.dry_run:
                    migration.updated_at = datetime.utcnow()
        
        if not self.dry_run:
            self.db.commit()
            logger.info("\n✓ Migration credentials encrypted and committed to database")
        else:
            logger.info("\n[DRY RUN] No changes made to database")
    
    def encrypt_connection_credentials(self):
        """Encrypt credentials in connections table"""
        logger.info("\n" + "=" * 80)
        logger.info("ENCRYPTING CONNECTION CREDENTIALS")
        logger.info("=" * 80)
        
        connections = self.db.query(Connection).all()
        logger.info(f"Found {len(connections)} connections to process")
        
        for connection in connections:
            self.stats['connections_processed'] += 1
            encrypted_any = False
            
            logger.info(f"\nProcessing Connection {connection.id}: {connection.connection_name}")
            
            # Password (if exists and not encrypted)
            if hasattr(connection, 'password') and connection.password:
                if not self.kms.is_encrypted(connection.password):
                    logger.info(f"  - Encrypting password")
                    if not self.dry_run:
                        try:
                            connection.password = self.kms.encrypt_credential(
                                plaintext=connection.password,
                                credential_type='connection_password',
                                resource_type='connection',
                                resource_id=connection.id
                            )
                            self.stats['fields_encrypted'] += 1
                            encrypted_any = True
                        except Exception as e:
                            logger.error(f"    ERROR: {e}")
                            self.stats['errors'] += 1
                else:
                    logger.info(f"  - Password already encrypted")
            
            # Password Encrypted field (if exists)
            if hasattr(connection, 'password_encrypted') and connection.password_encrypted:
                if not self.kms.is_encrypted(connection.password_encrypted):
                    logger.info(f"  - Encrypting password_encrypted field")
                    if not self.dry_run:
                        try:
                            connection.password_encrypted = self.kms.encrypt_credential(
                                plaintext=connection.password_encrypted,
                                credential_type='connection_password',
                                resource_type='connection',
                                resource_id=connection.id
                            )
                            self.stats['fields_encrypted'] += 1
                            encrypted_any = True
                        except Exception as e:
                            logger.error(f"    ERROR: {e}")
                            self.stats['errors'] += 1
                else:
                    logger.info(f"  - Password_encrypted already encrypted")
            
            # Service Account JSON (for BigQuery connections)
            if hasattr(connection, 'service_account_json') and connection.service_account_json:
                if not self.kms.is_encrypted(connection.service_account_json):
                    logger.info(f"  - Encrypting service account JSON")
                    if not self.dry_run:
                        try:
                            connection.service_account_json = self.kms.encrypt_credential(
                                plaintext=connection.service_account_json,
                                credential_type='gcp_service_account',
                                resource_type='connection',
                                resource_id=connection.id
                            )
                            self.stats['fields_encrypted'] += 1
                            encrypted_any = True
                        except Exception as e:
                            logger.error(f"    ERROR: {e}")
                            self.stats['errors'] += 1
                else:
                    logger.info(f"  - Service account JSON already encrypted")
            
            if encrypted_any:
                self.stats['connections_encrypted'] += 1
                if not self.dry_run:
                    connection.updated_at = datetime.utcnow()
        
        if not self.dry_run:
            self.db.commit()
            logger.info("\n✓ Connection credentials encrypted and committed to database")
        else:
            logger.info("\n[DRY RUN] No changes made to database")
    
    def print_summary(self):
        """Print encryption summary"""
        logger.info("\n" + "=" * 80)
        logger.info("ENCRYPTION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Migrations processed: {self.stats['migrations_processed']}")
        logger.info(f"Migrations encrypted: {self.stats['migrations_encrypted']}")
        logger.info(f"Connections processed: {self.stats['connections_processed']}")
        logger.info(f"Connections encrypted: {self.stats['connections_encrypted']}")
        logger.info(f"Total fields encrypted: {self.stats['fields_encrypted']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info("=" * 80)
        
        if self.dry_run:
            logger.info("\n[DRY RUN] No changes were made to the database")
            logger.info("Run without --dry-run to apply changes")
    
    def close(self):
        """Close database connection"""
        self.db.close()


def main():
    parser = argparse.ArgumentParser(
        description='Encrypt existing plaintext credentials in database using AWS KMS'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be encrypted without making changes'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Skip confirmation prompt'
    )
    
    args = parser.parse_args()
    
    # Print header
    print("\n" + "=" * 80)
    print("CREDENTIAL ENCRYPTION SCRIPT")
    print("=" * 80)
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print("=" * 80)
    
    # Confirmation prompt
    if not args.force and not args.dry_run:
        print("\nWARNING: This will encrypt all plaintext credentials in the database.")
        print("Make sure you have:")
        print("  1. AWS credentials configured")
        print("  2. Secret 'datamiq' with 'kms_arn' key in AWS Secrets Manager")
        print("  3. KMS key with proper permissions")
        print("  4. Database backup (recommended)")
        
        response = input("\nContinue? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return
    
    # Run encryption
    encryptor = CredentialEncryptor(dry_run=args.dry_run)
    
    try:
        # Test KMS connectivity
        logger.info("\nTesting AWS KMS connectivity...")
        test_encrypted = encryptor.kms.encrypt_credential(
            plaintext="test",
            credential_type="generic"
        )
        test_decrypted = encryptor.kms.decrypt_credential(
            ciphertext=test_encrypted,
            credential_type="generic"
        )
        if test_decrypted != "test":
            raise ValueError("KMS encryption/decryption test failed")
        logger.info("✓ AWS KMS connectivity verified")
        
        # Encrypt credentials
        encryptor.encrypt_migration_credentials()
        encryptor.encrypt_connection_credentials()
        
        # Print summary
        encryptor.print_summary()
        
        if not args.dry_run:
            logger.info("\n✓ All credentials encrypted successfully!")
        
    except Exception as e:
        logger.error(f"\n✗ Encryption failed: {e}")
        if not args.dry_run:
            logger.error("Rolling back changes...")
            encryptor.db.rollback()
        sys.exit(1)
    
    finally:
        encryptor.close()


if __name__ == '__main__':
    main()
