"""
Test AWS credentials for DataSync agent activation.

This script helps diagnose AWS credential issues by:
1. Loading credentials from the migration
2. Testing them with AWS STS
3. Checking IAM permissions
"""

import sys
from database import get_db
from models.bq_redshift_migration import MigrationBQRedshift
from services.kms_encryption_service import get_kms_encryption_service
import boto3
from botocore.exceptions import ClientError

def test_credentials(migration_id: int):
    """Test AWS credentials for a migration."""
    db = next(get_db())
    
    try:
        # Get migration
        migration = db.query(MigrationBQRedshift).filter_by(id=migration_id).first()
        if not migration:
            print(f"❌ Migration {migration_id} not found")
            return False
        
        print(f"✓ Found migration: {migration.migration_name}")
        print(f"  Pathway: {migration.pathway}")
        print(f"  AWS Region: {migration.aws_region or 'us-east-1'}")
        print()
        
        # Get AWS credentials
        aws_access_key = migration.aws_access_key_id or ''
        aws_secret_key = ''
        
        if migration.aws_secret_access_key_encrypted:
            try:
                encryption_service = get_kms_encryption_service()
                encryption_context = {
                    'migration_id': str(migration.id),
                    'field': 'aws_secret_access_key'
                }
                aws_secret_key = encryption_service.decrypt(
                    migration.aws_secret_access_key_encrypted,
                    encryption_context
                )
                print("✓ AWS secret key decrypted successfully")
            except Exception as e:
                print(f"⚠ KMS decryption failed, using value as-is: {e}")
                aws_secret_key = migration.aws_secret_access_key_encrypted
        
        # Check if credentials exist
        if not aws_access_key:
            print("❌ AWS Access Key ID is empty")
            return False
        if not aws_secret_key:
            print("❌ AWS Secret Access Key is empty")
            return False
        
        # Strip whitespace
        aws_access_key = aws_access_key.strip()
        aws_secret_key = aws_secret_key.strip()
        
        print(f"✓ AWS Access Key ID: {aws_access_key[:4]}...{aws_access_key[-4:]} (length: {len(aws_access_key)})")
        print(f"✓ AWS Secret Key: ****** (length: {len(aws_secret_key)})")
        print()
        
        # Test 1: Verify credentials with STS
        print("Test 1: Verifying credentials with AWS STS...")
        try:
            sts = boto3.client(
                'sts',
                region_name=migration.aws_region or 'us-east-1',
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key
            )
            identity = sts.get_caller_identity()
            print(f"✓ Credentials are valid!")
            print(f"  Account: {identity['Account']}")
            print(f"  User ARN: {identity['Arn']}")
            print(f"  User ID: {identity['UserId']}")
            print()
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = e.response['Error']['Message']
            print(f"❌ Credential verification failed!")
            print(f"  Error Code: {error_code}")
            print(f"  Error Message: {error_msg}")
            print()
            
            if error_code == 'InvalidClientTokenId':
                print("💡 This means the Access Key ID is invalid or doesn't exist.")
                print("   - Check if the Access Key ID is correct")
                print("   - Verify the IAM user exists")
                print("   - Make sure the key hasn't been deleted")
            elif error_code == 'SignatureDoesNotMatch':
                print("💡 This means the Secret Access Key is incorrect.")
                print("   - Check if the Secret Access Key is correct")
                print("   - Make sure there are no extra spaces or characters")
            elif error_code == 'UnrecognizedClientException':
                print("💡 This means the security token is invalid.")
                print("   - The credentials might be corrupted")
                print("   - Try re-entering the credentials in the UI")
            
            return False
        
        # Test 2: Check DataSync permissions
        print("Test 2: Checking DataSync permissions...")
        try:
            datasync = boto3.client(
                'datasync',
                region_name=migration.aws_region or 'us-east-1',
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key
            )
            # Try to list agents (this requires datasync:ListAgents permission)
            datasync.list_agents(MaxResults=1)
            print("✓ DataSync permissions OK (can list agents)")
            print()
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDeniedException':
                print("⚠ No DataSync permissions (but credentials are valid)")
                print("  The IAM user needs these permissions:")
                print("  - datasync:CreateAgent")
                print("  - datasync:ListAgents")
                print("  - datasync:CreateLocationObjectStorage")
                print("  - datasync:CreateLocationS3")
                print("  - datasync:CreateTask")
                print("  - datasync:StartTaskExecution")
                print()
            else:
                print(f"⚠ DataSync check failed: {error_code}")
                print()
        
        # Test 3: Check S3 permissions
        print("Test 3: Checking S3 permissions...")
        try:
            s3 = boto3.client(
                's3',
                region_name=migration.aws_region or 'us-east-1',
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key
            )
            # Try to list buckets
            s3.list_buckets()
            print("✓ S3 permissions OK (can list buckets)")
            print()
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDenied':
                print("⚠ No S3 permissions (but credentials are valid)")
                print("  The IAM user needs S3 read/write permissions")
                print()
            else:
                print(f"⚠ S3 check failed: {error_code}")
                print()
        
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print("✓ Credentials are valid and can be used with AWS services")
        print()
        print("Next steps:")
        print("1. Make sure the IAM user has AWSDataSyncFullAccess policy")
        print("2. Make sure the IAM user has AmazonS3FullAccess policy")
        print("3. Try running the migration again")
        print()
        
        return True
        
    finally:
        db.close()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python test_aws_credentials.py <migration_id>")
        print("Example: python test_aws_credentials.py 18")
        sys.exit(1)
    
    migration_id = int(sys.argv[1])
    success = test_credentials(migration_id)
    sys.exit(0 if success else 1)
