"""
Test Redshift Load from Existing Migration

This script tests the S3 to Redshift load stage using data from an existing migration.
It will attempt to load the data that was already exported and transferred.

Usage:
    python test_redshift_load_from_migration.py <migration_id>
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import logging
from sqlalchemy.orm import Session
from database import get_db
from models.bq_redshift_migration import MigrationBQRedshift
from models.connection import Connection
from services.bq_redshift_migration.redshift_loader import RedshiftLoader
from services.encryption_service import get_encryption_service
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_load_stage(migration_id: int):
    """
    Test the load stage for a migration.
    
    Args:
        migration_id: Migration ID to test
    """
    db: Session = next(get_db())
    
    try:
        logger.info("="*80)
        logger.info(f"TESTING REDSHIFT LOAD FOR MIGRATION {migration_id}")
        logger.info("="*80)
        
        # Step 1: Get migration
        logger.info("\nStep 1: Fetching migration details...")
        migration = db.query(MigrationBQRedshift).filter_by(id=migration_id).first()
        
        if not migration:
            logger.error(f"Migration {migration_id} not found")
            return False
        
        logger.info(f"✓ Migration found: {migration.migration_name}")
        logger.info(f"  Status: {migration.status}")
        logger.info(f"  Pathway: {migration.pathway}")
        
        # Step 2: Validate checkpoint data
        logger.info("\nStep 2: Validating checkpoint data...")
        checkpoint_data = migration.checkpoint_data or {}
        
        export_results = checkpoint_data.get('export_results', [])
        if not export_results:
            logger.error("No export results found - cannot proceed with load test")
            return False
        
        logger.info(f"✓ Found {len(export_results)} export results")
        
        successful_exports = [r for r in export_results if r.get('success')]
        if not successful_exports:
            logger.error("No successful exports found - cannot proceed with load test")
            return False
        
        logger.info(f"✓ {len(successful_exports)} tables exported successfully")
        
        # Step 3: Get target connection
        logger.info("\nStep 3: Getting target connection...")
        
        if not migration.target_connection_id:
            logger.error("Target connection ID not set")
            return False
        
        target_conn = db.query(Connection).filter_by(id=migration.target_connection_id).first()
        if not target_conn:
            logger.error(f"Target connection {migration.target_connection_id} not found")
            return False
        
        logger.info(f"✓ Target connection: {target_conn.name}")
        
        # Step 4: Extract configuration
        logger.info("\nStep 4: Extracting configuration...")
        
        conn_params = target_conn.connection_params or {}
        
        # Get Redshift credentials
        redshift_host = conn_params.get('host') or conn_params.get('server_name') or migration.target_cluster
        redshift_port = int(conn_params.get('port', 5439))
        redshift_database = conn_params.get('database') or conn_params.get('database_name') or migration.target_database
        redshift_user = conn_params.get('username')
        redshift_password_encrypted = conn_params.get('password_encrypted')
        
        # Get IAM role
        iam_role_arn = conn_params.get('iam_role_arn') or migration.iam_role_arn
        
        # Get S3 configuration
        s3_bucket = migration.s3_bucket
        s3_path = migration.s3_path or ''
        
        # Get AWS credentials
        aws_access_key_id = migration.aws_access_key_id
        aws_secret_encrypted = migration.aws_secret_access_key_encrypted
        
        # Validate required fields
        logger.info("\nValidating configuration:")
        logger.info(f"  Redshift Host: {redshift_host or '❌ MISSING'}")
        logger.info(f"  Redshift Port: {redshift_port}")
        logger.info(f"  Redshift Database: {redshift_database or '❌ MISSING'}")
        logger.info(f"  Redshift User: {redshift_user or '❌ MISSING'}")
        logger.info(f"  Redshift Password: {'✓ SET' if redshift_password_encrypted else '❌ MISSING'}")
        logger.info(f"  IAM Role ARN: {iam_role_arn or '❌ MISSING'}")
        logger.info(f"  S3 Bucket: {s3_bucket or '❌ MISSING'}")
        logger.info(f"  S3 Path: {s3_path or '(root)'}")
        logger.info(f"  AWS Access Key: {aws_access_key_id or '❌ MISSING'}")
        logger.info(f"  AWS Secret Key: {'✓ SET' if aws_secret_encrypted else '❌ MISSING'}")
        
        # Check for missing required fields
        missing_fields = []
        if not redshift_host:
            missing_fields.append("Redshift host")
        if not redshift_database:
            missing_fields.append("Redshift database")
        if not redshift_user:
            missing_fields.append("Redshift username")
        if not redshift_password_encrypted:
            missing_fields.append("Redshift password")
        if not iam_role_arn:
            missing_fields.append("IAM role ARN")
        if not s3_bucket:
            missing_fields.append("S3 bucket")
        
        if missing_fields:
            logger.error("\n❌ Missing required configuration:")
            for field in missing_fields:
                logger.error(f"  - {field}")
            logger.error("\nCannot proceed with load test")
            return False
        
        logger.info("\n✓ All required configuration present")
        
        # Step 5: Decrypt credentials
        logger.info("\nStep 5: Decrypting credentials...")
        
        encryption_service = get_encryption_service()
        
        try:
            redshift_password = encryption_service.decrypt(redshift_password_encrypted)
            logger.info("✓ Redshift password decrypted")
        except Exception as e:
            logger.error(f"Failed to decrypt Redshift password: {e}")
            return False
        
        try:
            aws_secret_access_key = encryption_service.decrypt(aws_secret_encrypted)
            logger.info("✓ AWS secret key decrypted")
        except Exception as e:
            logger.error(f"Failed to decrypt AWS secret key: {e}")
            return False
        
        # Step 6: Initialize RedshiftLoader
        logger.info("\nStep 6: Initializing RedshiftLoader...")
        
        loader = RedshiftLoader(
            redshift_host=redshift_host,
            redshift_port=redshift_port,
            redshift_database=redshift_database,
            redshift_user=redshift_user,
            redshift_password=redshift_password,
            iam_role_arn=iam_role_arn,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_region='us-east-1'  # TODO: Get from config
        )
        
        logger.info("✓ RedshiftLoader initialized")
        
        # Step 7: Connect to Redshift
        logger.info("\nStep 7: Connecting to Redshift...")
        
        if not loader.connect():
            logger.error("Failed to connect to Redshift")
            logger.error("Check:")
            logger.error("  - Cluster endpoint is correct")
            logger.error("  - Cluster is publicly accessible or accessible from your network")
            logger.error("  - Security group allows inbound traffic on port 5439")
            logger.error("  - Username and password are correct")
            return False
        
        logger.info("✓ Connected to Redshift")
        
        # Step 8: Verify IAM role
        logger.info("\nStep 8: Verifying IAM role...")
        
        # Check if IAM role looks like a test/dummy role
        is_test_role = '123456789012' in iam_role_arn or 'test' in iam_role_arn.lower()
        
        if is_test_role:
            logger.warning("⚠️  Test/dummy IAM role detected - skipping verification")
            logger.warning(f"   Role: {iam_role_arn}")
            logger.warning("   For production, use a real IAM role with S3 read permissions")
        else:
            if not loader.verify_iam_role():
                logger.error("IAM role verification failed")
                logger.error("Check:")
                logger.error("  - IAM role ARN is correct")
                logger.error("  - IAM role has trust relationship with Redshift")
                logger.error("  - IAM role has S3 read permissions")
                logger.error("  - IAM role is attached to Redshift cluster")
                loader.disconnect()
                return False
            
            logger.info("✓ IAM role verified")
        
        # Step 9: Load tables
        logger.info("\nStep 9: Loading tables to Redshift...")
        logger.info("="*80)
        
        schema = migration.target_schema or 'public'
        export_format = migration.export_format or 'PARQUET'
        compression = migration.compression
        
        load_results = []
        successful_loads = 0
        failed_loads = 0
        total_rows_loaded = 0
        
        for i, export_result in enumerate(successful_exports, 1):
            table_name = export_result.get('table', export_result.get('table_id', 'unknown'))
            columns = export_result.get('schema', [])
            
            if not columns:
                logger.warning(f"Skipping {table_name} - no schema found")
                continue
            
            logger.info(f"\nTable {i}/{len(successful_exports)}: {table_name}")
            logger.info(f"  Columns: {len(columns)}")
            
            # Construct S3 prefix for this table
            table_s3_prefix = f"{s3_path}/{table_name}".strip('/') if s3_path else table_name
            
            logger.info(f"  S3 Location: s3://{s3_bucket}/{table_s3_prefix}")
            logger.info(f"  Format: {export_format}")
            logger.info(f"  Compression: {compression or 'NONE'}")
            
            # Load table
            result = loader.load_table(
                schema=schema,
                table=table_name,
                s3_bucket=s3_bucket,
                s3_prefix=table_s3_prefix,
                columns=columns,
                file_format=export_format,
                compression=compression
            )
            
            load_results.append(result)
            
            if result.get('success'):
                successful_loads += 1
                rows_loaded = result.get('rows_loaded', 0)
                total_rows_loaded += rows_loaded
                logger.info(f"  ✓ SUCCESS: {rows_loaded:,} rows loaded")
            else:
                failed_loads += 1
                error = result.get('error', 'Unknown error')
                logger.error(f"  ✗ FAILED: {error}")
                
                # Show error details if available
                error_details = result.get('error_details', [])
                if error_details:
                    logger.error(f"  Error details ({len(error_details)} errors):")
                    for detail in error_details[:3]:  # Show first 3
                        logger.error(f"    Line {detail.get('line_number')}: {detail.get('error_message')}")
        
        # Disconnect
        loader.disconnect()
        logger.info("\n✓ Disconnected from Redshift")
        
        # Step 10: Summary
        logger.info("\n" + "="*80)
        logger.info("LOAD TEST SUMMARY")
        logger.info("="*80)
        logger.info(f"Tables processed: {len(successful_exports)}")
        logger.info(f"Successful loads: {successful_loads}")
        logger.info(f"Failed loads: {failed_loads}")
        logger.info(f"Total rows loaded: {total_rows_loaded:,}")
        
        if failed_loads > 0:
            logger.warning(f"\n⚠️  {failed_loads} table(s) failed to load")
            logger.info("\nTo investigate failures:")
            logger.info("  1. Check Redshift STL_LOAD_ERRORS table:")
            logger.info("     SELECT * FROM stl_load_errors WHERE query = pg_last_copy_id();")
            logger.info("  2. Verify S3 files exist and are accessible")
            logger.info("  3. Check IAM role permissions")
            logger.info("  4. Verify file format and compression settings")
        
        if successful_loads > 0:
            logger.info("\n✓ Some tables loaded successfully!")
            logger.info("\nTo verify data in Redshift:")
            logger.info("  1. Connect to Redshift cluster")
            logger.info("  2. Run: SELECT * FROM pg_tables WHERE schemaname = 'public';")
            logger.info("  3. Check row counts for each table")
        
        logger.info("="*80)
        
        return successful_loads > 0
    
    except Exception as e:
        logger.error("="*80)
        logger.error("ERROR DURING LOAD TEST")
        logger.error("="*80)
        logger.error(f"Exception: {e}")
        
        import traceback
        logger.error("\nFull traceback:")
        logger.error(traceback.format_exc())
        
        return False
    
    finally:
        db.close()


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python test_redshift_load_from_migration.py <migration_id>")
        print("\nExample:")
        print("  python test_redshift_load_from_migration.py 123")
        print("\nThis script will:")
        print("  1. Load migration configuration from database")
        print("  2. Extract export results and S3 locations")
        print("  3. Connect to Redshift cluster")
        print("  4. Attempt to load data from S3 to Redshift")
        print("  5. Report success/failure for each table")
        sys.exit(1)
    
    try:
        migration_id = int(sys.argv[1])
    except ValueError:
        print(f"Error: Invalid migration ID '{sys.argv[1]}'. Must be an integer.")
        sys.exit(1)
    
    success = test_load_stage(migration_id)
    
    if success:
        print("\n✓ Load test completed with some successes")
        sys.exit(0)
    else:
        print("\n❌ Load test failed - see details above")
        sys.exit(1)


if __name__ == '__main__':
    main()
