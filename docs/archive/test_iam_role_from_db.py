#!/usr/bin/env python3
"""
Test script to verify IAM role ARN is correctly fetched from database
and used in S3 to Redshift load operation.

This script:
1. Fetches migration 12 from database
2. Verifies IAM role ARN is stored
3. Simulates the load stage to show IAM role usage
4. Tests Redshift connection with the IAM role
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db
from models.bq_redshift_migration import MigrationBQRedshift
from models.connection import Connection
from services.encryption_service import get_encryption_service
from services.bq_redshift_migration.redshift_loader import RedshiftLoader
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_iam_role_from_database():
    """Test IAM role ARN retrieval and usage from database."""
    
    print("="*80)
    print("TESTING IAM ROLE ARN FROM DATABASE")
    print("="*80)
    
    db = next(get_db())
    
    try:
        # Step 1: Fetch migration from database
        print("\n1. Fetching migration 12 from database...")
        migration = db.query(MigrationBQRedshift).filter_by(id=12).first()
        
        if not migration:
            print("❌ Migration 12 not found in database")
            return False
        
        print(f"✓ Migration found: {migration.migration_name}")
        print(f"  Status: {migration.status}")
        print(f"  Pathway: {migration.pathway}")
        print(f"  Current Stage: {migration.current_stage}")
        
        # Step 2: Check IAM role ARN
        print("\n2. Checking IAM role ARN...")
        iam_role_arn = migration.iam_role_arn
        
        if not iam_role_arn:
            print("❌ IAM role ARN not found in migration record")
            print("   Please update the migration with a valid IAM role ARN")
            return False
        
        print(f"✓ IAM role ARN found: {iam_role_arn}")
        
        # Step 3: Fetch target connection details
        print("\n3. Fetching target connection details...")
        if not migration.target_connection_id:
            print("❌ Target connection ID not set")
            return False
        
        target_conn = db.query(Connection).filter_by(id=migration.target_connection_id).first()
        if not target_conn:
            print(f"❌ Target connection {migration.target_connection_id} not found")
            return False
        
        print(f"✓ Target connection found: {target_conn.name}")
        
        # Extract connection parameters
        conn_params = target_conn.connection_params or {}
        
        cluster = conn_params.get('host') or conn_params.get('server_name')
        port = int(conn_params.get('port', 5439))
        database = conn_params.get('database') or conn_params.get('database_name')
        username = conn_params.get('username')
        password_encrypted = conn_params.get('password_encrypted')
        
        print(f"  Cluster: {cluster}")
        print(f"  Port: {port}")
        print(f"  Database: {database}")
        print(f"  Username: {username}")
        print(f"  Password: {'***encrypted***' if password_encrypted else 'NOT SET'}")
        
        if not all([cluster, database, username, password_encrypted]):
            print("❌ Missing required connection parameters")
            return False
        
        # Step 4: Decrypt password
        print("\n4. Decrypting Redshift password...")
        try:
            encryption_service = get_encryption_service()
            password = encryption_service.decrypt(password_encrypted)
            print("✓ Password decrypted successfully")
        except Exception as e:
            print(f"❌ Failed to decrypt password: {e}")
            return False
        
        # Step 5: Get AWS credentials for S3 access
        print("\n5. Checking AWS credentials...")
        aws_access_key_id = migration.aws_access_key_id
        aws_secret_encrypted = migration.aws_secret_access_key_encrypted
        
        if not aws_access_key_id or not aws_secret_encrypted:
            print("❌ AWS credentials not found in migration")
            print("   AWS credentials are needed for S3 access")
            return False
        
        print(f"✓ AWS Access Key ID: {aws_access_key_id[:10]}...")
        
        try:
            aws_secret_key = encryption_service.decrypt(aws_secret_encrypted)
            print("✓ AWS Secret Key decrypted successfully")
        except Exception as e:
            print(f"❌ Failed to decrypt AWS secret key: {e}")
            return False
        
        # Step 6: Get S3 configuration
        print("\n6. Checking S3 configuration...")
        s3_bucket = migration.s3_bucket
        s3_path = migration.s3_path
        
        if not s3_bucket:
            print("❌ S3 bucket not configured")
            return False
        
        print(f"✓ S3 Bucket: {s3_bucket}")
        print(f"  S3 Path: {s3_path or '/'}")
        
        # Step 7: Initialize RedshiftLoader with IAM role
        print("\n7. Initializing RedshiftLoader with IAM role...")
        print(f"   This will test if the IAM role can be used for S3 access")
        
        loader = RedshiftLoader(
            redshift_host=cluster,
            redshift_port=port,
            redshift_database=database,
            redshift_user=username,
            redshift_password=password,
            iam_role_arn=iam_role_arn,  # ← IAM role from database
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_key,
            aws_region='us-east-1'
        )
        
        print("✓ RedshiftLoader initialized")
        print(f"  IAM Role ARN: {loader.iam_role_arn}")
        
        # Step 8: Test Redshift connection
        print("\n8. Testing Redshift connection...")
        if not loader.connect():
            print("❌ Failed to connect to Redshift")
            print("   Check cluster endpoint, credentials, and network access")
            return False
        
        print("✓ Connected to Redshift successfully")
        
        # Step 9: Verify IAM role
        print("\n9. Verifying IAM role permissions...")
        if not loader.verify_iam_role():
            print("❌ IAM role verification failed")
            print("   The IAM role may not have proper S3 permissions")
            print("   Required permissions:")
            print("   - s3:GetObject")
            print("   - s3:ListBucket")
            loader.disconnect()
            return False
        
        print("✓ IAM role verified successfully")
        print("  The IAM role has proper permissions for S3 access")
        
        # Step 10: Show sample COPY command
        print("\n10. Sample COPY command that would be executed:")
        print("-" * 80)
        
        sample_table = "customers"
        sample_manifest = f"s3://{s3_bucket}/{s3_path}/{sample_table}/manifest.json"
        
        copy_command = f"""
COPY public.{sample_table}
FROM '{sample_manifest}'
IAM_ROLE '{iam_role_arn}'
FORMAT AS PARQUET
MANIFEST
STATUPDATE ON
COMPUPDATE ON;
"""
        print(copy_command)
        print("-" * 80)
        
        # Disconnect
        loader.disconnect()
        print("\n✓ Disconnected from Redshift")
        
        # Summary
        print("\n" + "="*80)
        print("✅ IAM ROLE TEST COMPLETED SUCCESSFULLY")
        print("="*80)
        print("\nSummary:")
        print(f"  ✓ Migration ID: {migration.id}")
        print(f"  ✓ Migration Name: {migration.migration_name}")
        print(f"  ✓ IAM Role ARN: {iam_role_arn}")
        print(f"  ✓ Redshift Cluster: {cluster}")
        print(f"  ✓ Redshift Database: {database}")
        print(f"  ✓ S3 Bucket: {s3_bucket}")
        print(f"  ✓ Connection: Successful")
        print(f"  ✓ IAM Role: Verified")
        print("\nThe IAM role is correctly configured and ready for S3 to Redshift load!")
        print("="*80)
        
        return True
        
    except Exception as e:
        print("\n" + "="*80)
        print("❌ TEST FAILED")
        print("="*80)
        print(f"Error: {e}")
        
        import traceback
        print("\nFull traceback:")
        print(traceback.format_exc())
        print("="*80)
        
        return False
        
    finally:
        db.close()

if __name__ == "__main__":
    print("\n" + "="*80)
    print("IAM ROLE ARN DATABASE TEST")
    print("="*80)
    print("\nThis script verifies that:")
    print("1. IAM role ARN is stored in the database")
    print("2. IAM role ARN is correctly retrieved")
    print("3. IAM role ARN is used in RedshiftLoader")
    print("4. IAM role has proper S3 permissions")
    print("="*80)
    
    success = test_iam_role_from_database()
    
    if success:
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Tests failed!")
        sys.exit(1)
