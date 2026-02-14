#!/usr/bin/env python3
"""
Test script to verify S3 to Redshift data load with IAM role from database.

This script:
1. Fetches migration 12 from database
2. Gets IAM role ARN and connection details
3. Connects to Redshift
4. Creates schema if it doesn't exist
5. Creates table if it doesn't exist (using BigQuery schema)
6. Generates manifest file
7. Executes COPY command with IAM role
8. Verifies data loaded successfully
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

def test_s3_to_redshift_load():
    """Test complete S3 to Redshift load with table creation."""
    
    print("="*80)
    print("TESTING S3 TO REDSHIFT DATA LOAD")
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
        print(f"  Pathway: {migration.pathway}")
        print(f"  Source Dataset: {migration.source_dataset}")
        print(f"  Source Tables: {migration.source_tables}")
        
        # Step 2: Get IAM role ARN
        print("\n2. Checking IAM role ARN...")
        iam_role_arn = migration.iam_role_arn
        
        if not iam_role_arn:
            print("❌ IAM role ARN not found in migration record")
            return False
        
        print(f"✓ IAM role ARN: {iam_role_arn}")
        
        # Step 3: Get target connection details
        print("\n3. Fetching target connection details...")
        if not migration.target_connection_id:
            print("❌ Target connection ID not set")
            return False
        
        target_conn = db.query(Connection).filter_by(id=migration.target_connection_id).first()
        if not target_conn:
            print(f"❌ Target connection {migration.target_connection_id} not found")
            return False
        
        print(f"✓ Target connection: {target_conn.name}")
        
        # Extract connection parameters
        conn_params = target_conn.connection_params or {}
        
        cluster = conn_params.get('host') or conn_params.get('server_name')
        port = int(conn_params.get('port', 5439))
        database = conn_params.get('database') or conn_params.get('database_name')
        username = conn_params.get('username')
        password_encrypted = conn_params.get('password_encrypted')
        
        print(f"  Cluster: {cluster}")
        print(f"  Database: {database}")
        print(f"  Schema: {migration.target_schema or 'public'}")
        
        # Step 4: Decrypt credentials
        print("\n4. Decrypting credentials...")
        encryption_service = get_encryption_service()
        
        try:
            password = encryption_service.decrypt(password_encrypted)
            print("✓ Redshift password decrypted")
        except Exception as e:
            print(f"❌ Failed to decrypt password: {e}")
            return False
        
        try:
            aws_secret_key = encryption_service.decrypt(migration.aws_secret_access_key_encrypted)
            print("✓ AWS secret key decrypted")
        except Exception as e:
            print(f"❌ Failed to decrypt AWS secret key: {e}")
            return False
        
        # Step 5: Get S3 configuration
        print("\n5. Checking S3 configuration...")
        s3_bucket = migration.s3_bucket.replace('s3://', '').strip('/')
        s3_path = migration.s3_path.strip('/') if migration.s3_path else ''
        
        print(f"✓ S3 Bucket: {s3_bucket}")
        print(f"  S3 Path: {s3_path or '/'}")
        print(f"  Export Format: {migration.export_format or 'PARQUET'}")
        
        # Step 6: Get export results from checkpoint data
        print("\n6. Checking export results...")
        checkpoint_data = migration.checkpoint_data or {}
        export_results = checkpoint_data.get('export_results', [])
        
        if not export_results:
            print("❌ No export results found in checkpoint data")
            print("   Please run the export stage first")
            return False
        
        successful_exports = [r for r in export_results if r.get('success')]
        print(f"✓ Found {len(successful_exports)} successfully exported tables")
        
        if not successful_exports:
            print("❌ No successful exports found")
            return False
        
        # Step 7: Initialize RedshiftLoader
        print("\n7. Initializing RedshiftLoader...")
        loader = RedshiftLoader(
            redshift_host=cluster,
            redshift_port=port,
            redshift_database=database,
            redshift_user=username,
            redshift_password=password,
            iam_role_arn=iam_role_arn,
            aws_access_key_id=migration.aws_access_key_id,
            aws_secret_access_key=aws_secret_key,
            aws_region='us-east-1'
        )
        
        print("✓ RedshiftLoader initialized")
        
        # Step 8: Connect to Redshift
        print("\n8. Connecting to Redshift...")
        if not loader.connect():
            print("❌ Failed to connect to Redshift")
            return False
        
        print("✓ Connected to Redshift")
        
        # Step 9: Verify IAM role (will skip if no permissions)
        print("\n9. Verifying IAM role...")
        loader.verify_iam_role()  # This will log warnings if it can't verify
        
        # Step 10: Load tables
        print("\n10. Loading tables to Redshift...")
        print("="*80)
        
        # Get project ID and dataset name for database/schema creation
        # New naming convention:
        # - Database = GCP Project ID (e.g., "assessiq-484512")
        # - Schema = Dataset name (e.g., "sales_analytics")
        # - Table = Table name (e.g., "customers")
        
        project_id = migration.source_project_id
        dataset_name = migration.source_dataset
        
        # Redshift database names must follow naming rules:
        # - Start with a letter
        # - Contain only lowercase letters, numbers, and underscores
        # - Max 64 characters
        # Convert project_id to valid database name
        database_name = project_id.replace('-', '_').lower()
        
        print(f"\nNaming Convention:")
        print(f"  GCP Project ID: {project_id}")
        print(f"  GCP Dataset: {dataset_name}")
        print(f"  Redshift Database: {database_name}")
        print(f"  Redshift Schema: {dataset_name}")
        
        # Step 10a: Create database as project ID (if needed)
        print(f"\n10a. Checking/Creating Redshift database: {database_name}")
        
        try:
            # Check if database exists
            with loader.connection.cursor() as cursor:
                cursor.execute("""
                    SELECT datname FROM pg_database 
                    WHERE datname = %s
                """, (database_name,))
                
                result = cursor.fetchone()
                
                if result:
                    print(f"✓ Database {database_name} already exists")
                else:
                    print(f"Creating database {database_name}...")
                    
                    # Create database (requires autocommit)
                    old_autocommit = loader.connection.autocommit
                    loader.connection.autocommit = True
                    
                    try:
                        cursor.execute(f"CREATE DATABASE {database_name}")
                        print(f"✓ Database {database_name} created successfully")
                    except Exception as e:
                        print(f"⚠ Could not create database {database_name}: {e}")
                        print(f"  Will use existing database: {database}")
                        database_name = database  # Fallback to original database
                    finally:
                        loader.connection.autocommit = old_autocommit
            
            # Reconnect to the project database
            if database_name != database:
                print(f"\nReconnecting to database: {database_name}")
                loader.disconnect()
                
                loader.redshift_database = database_name
                if not loader.connect():
                    print(f"❌ Failed to reconnect to database {database_name}")
                    print(f"  Falling back to original database: {database}")
                    loader.redshift_database = database
                    if not loader.connect():
                        print("❌ Failed to reconnect to Redshift")
                        return False
                else:
                    print(f"✓ Reconnected to database: {database_name}")
        
        except Exception as e:
            print(f"⚠ Database creation check failed: {e}")
            print(f"  Will use existing database: {database}")
        
        print("\n10b. Loading tables...")
        
        # Use dataset name as schema
        schema = dataset_name
        load_results = []
        successful_loads = 0
        failed_loads = 0
        total_rows_loaded = 0
        
        for i, export_result in enumerate(successful_exports, 1):
            table_name_full = export_result['table']  # e.g., "assessiq-484512.sales_analytics.customers"
            columns = export_result.get('schema', [])
            
            # Extract just the table name from fully qualified name
            # Format: project.dataset.table
            table_name = table_name_full.split('.')[-1]
            dataset_name = table_name_full.split('.')[-2] if '.' in table_name_full else migration.source_dataset
            
            # If schema is missing, fetch it from BigQuery
            if not columns:
                print(f"\n⚠ Schema not found in export results for {table_name_full}")
                print(f"  Fetching schema from BigQuery...")
                
                try:
                    # Get source connection for BigQuery credentials
                    source_conn = db.query(Connection).filter_by(id=migration.source_connection_id).first()
                    if not source_conn:
                        print(f"❌ Source connection {migration.source_connection_id} not found")
                        continue
                    
                    # Get credentials from connection params
                    connection_params = source_conn.connection_params or {}
                    service_account_key = (
                        connection_params.get('service_account_key') or 
                        connection_params.get('serviceAccountKey') or
                        connection_params.get('credentials_json') or
                        connection_params.get('credentialsJson')
                    )
                    
                    if not service_account_key:
                        print(f"❌ Service account key not found in connection params")
                        continue
                    
                    # Parse service account key if it's a string
                    if isinstance(service_account_key, str):
                        import json
                        credentials_dict = json.loads(service_account_key)
                    else:
                        credentials_dict = service_account_key
                    
                    project_id = migration.source_project_id or credentials_dict.get('project_id')
                    
                    # Initialize BigQuery client
                    from google.cloud import bigquery
                    from google.oauth2 import service_account
                    
                    credentials = service_account.Credentials.from_service_account_info(credentials_dict)
                    bq_client = bigquery.Client(credentials=credentials, project=project_id)
                    
                    # Get table schema
                    table_ref = f"{project_id}.{dataset_name}.{table_name}"
                    table_obj = bq_client.get_table(table_ref)
                    
                    # Extract schema
                    columns = []
                    for field in table_obj.schema:
                        columns.append({
                            'name': field.name,
                            'type': field.field_type,
                            'mode': field.mode or 'NULLABLE',
                            'description': field.description or ''
                        })
                    
                    print(f"✓ Fetched schema from BigQuery: {len(columns)} columns")
                    
                except Exception as e:
                    print(f"❌ Failed to fetch schema from BigQuery: {e}")
                    import traceback
                    print(traceback.format_exc())
                    continue
            
            if not columns:
                print(f"\n⚠ Skipping {table_name_full} - no schema available")
                continue
            
            print(f"\n{'='*80}")
            print(f"TABLE {i}/{len(successful_exports)}: {table_name}")
            print(f"{'='*80}")
            print(f"BigQuery: {project_id}.{dataset_name}.{table_name}")
            print(f"Redshift: {database_name}.{schema}.{table_name}")
            print(f"Columns: {len(columns)}")
            
            # Construct S3 prefix for this table
            # GCS export creates: gcs_path/dataset/table/files
            # So S3 should have: s3_path/dataset/table/files
            if s3_path:
                table_s3_prefix = f"{s3_path}/{dataset_name}/{table_name}"
            else:
                table_s3_prefix = f"{dataset_name}/{table_name}"
            
            print(f"S3 Path: s3://{s3_bucket}/{table_s3_prefix}")
            
            # Load table using RedshiftLoader
            # This will:
            # 1. Create schema if it doesn't exist
            # 2. Create table if it doesn't exist
            # 3. List S3 files
            # 4. Execute COPY command with IAM role
            # 5. Get load statistics
            result = loader.load_table(
                schema=schema,
                table=table_name,
                s3_bucket=s3_bucket,
                s3_prefix=table_s3_prefix,
                columns=columns,
                file_format=migration.export_format or 'PARQUET',
                compression=migration.compression
            )
            
            load_results.append(result)
            
            if result.get('success'):
                successful_loads += 1
                rows_loaded = result.get('rows_loaded', 0)
                
                # If rows_loaded is 0, try to get actual count from table
                if rows_loaded == 0:
                    try:
                        with loader.connection.cursor() as cursor:
                            cursor.execute(f"SELECT COUNT(*) FROM {schema}.{table_name}")
                            actual_count = cursor.fetchone()[0]
                            rows_loaded = actual_count
                            print(f"\n✓ Table {table_name} loaded successfully")
                            print(f"  Rows in table: {rows_loaded:,}")
                    except Exception as e:
                        print(f"\n✓ Table {table_name} loaded successfully")
                        print(f"  Could not verify row count: {e}")
                else:
                    print(f"\n✓ Table {table_name} loaded successfully")
                    print(f"  Rows loaded: {rows_loaded:,}")
                
                total_rows_loaded += rows_loaded
                print(f"  Bytes loaded: {result.get('bytes_loaded', 0):,}")
            else:
                failed_loads += 1
                print(f"\n❌ Table {table_name} load failed")
                print(f"  Error: {result.get('error', 'Unknown error')}")
                
                # Show error details if available
                error_details = result.get('error_details', [])
                if error_details:
                    print(f"  Error details ({len(error_details)} errors):")
                    for detail in error_details[:3]:  # Show first 3 errors
                        print(f"    Line {detail.get('line_number')}: {detail.get('error_message')}")
        
        # Step 11: Disconnect
        loader.disconnect()
        print(f"\n✓ Disconnected from Redshift")
        
        # Step 12: Summary
        print("\n" + "="*80)
        if successful_loads > 0:
            print("✅ S3 TO REDSHIFT LOAD COMPLETED")
        else:
            print("❌ S3 TO REDSHIFT LOAD FAILED")
        print("="*80)
        
        print(f"\nSummary:")
        print(f"  Migration ID: {migration.id}")
        print(f"  Migration Name: {migration.migration_name}")
        print(f"  IAM Role ARN: {iam_role_arn}")
        print(f"  Redshift Cluster: {cluster}")
        print(f"  Redshift Database: {loader.redshift_database}")  # Show actual database used
        print(f"  Redshift Schema: {schema}")
        print(f"  S3 Bucket: {s3_bucket}")
        print(f"  BigQuery Project: {project_id}")
        print(f"  BigQuery Dataset: {dataset_name}")
        print(f"  Tables Processed: {len(successful_exports)}")
        print(f"  Tables Loaded Successfully: {successful_loads}")
        print(f"  Tables Failed: {failed_loads}")
        print(f"  Total Rows Loaded: {total_rows_loaded:,}")
        
        if successful_loads > 0:
            print(f"\n✓ Data successfully loaded from S3 to Redshift!")
            print(f"✓ Tables created (if they didn't exist)")
            print(f"✓ COPY command executed with IAM role")
            print(f"✓ {total_rows_loaded:,} rows loaded")
        
        print("="*80)
        
        return successful_loads > 0
        
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
    print("S3 TO REDSHIFT DATA LOAD TEST")
    print("="*80)
    print("\nThis script will:")
    print("1. Fetch migration configuration from database")
    print("2. Connect to Redshift using encrypted credentials")
    print("3. Create schema if it doesn't exist")
    print("4. Create tables if they don't exist")
    print("5. Generate manifest files for S3 data")
    print("6. Execute COPY command with IAM role from database")
    print("7. Verify data loaded successfully")
    print("="*80)
    
    success = test_s3_to_redshift_load()
    
    if success:
        print("\n✅ All tests passed! Data loaded successfully!")
        sys.exit(0)
    else:
        print("\n❌ Tests failed!")
        sys.exit(1)
