"""
Direct load from S3 to Redshift - bypassing migration framework

This script:
1. Fetches migration configuration from database
2. Gets export results with table schemas
3. Connects to Redshift
4. Creates database, schema, and tables
5. Loads data from S3 using COPY command
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database import get_db
from models.bq_redshift_migration import MigrationBQRedshift
from models.connection import Connection
from services.bq_redshift_migration.redshift_loader import RedshiftLoader
from services.encryption_service import get_encryption_service
import json

def load_to_redshift(migration_id: int = None, migration_name: str = None):
    """Load data to Redshift from existing S3 data"""
    
    db = next(get_db())
    try:
        # Find migration
        if migration_id:
            migration = db.query(MigrationBQRedshift).filter_by(id=migration_id).first()
        elif migration_name:
            migration = db.query(MigrationBQRedshift).filter_by(migration_name=migration_name).first()
        else:
            print("❌ Please provide migration_id or migration_name")
            return False
        
        if not migration:
            print(f"❌ Migration not found")
            return False
        
        print("="*80)
        print(f"LOADING DATA TO REDSHIFT")
        print("="*80)
        print(f"Migration: {migration.migration_name} (ID: {migration.id})")
        print(f"Pathway: {migration.pathway}")
        print()
        
        # Get checkpoint data
        checkpoint_data = migration.checkpoint_data or {}
        export_results = checkpoint_data.get('export_results', [])
        
        if not export_results:
            print("❌ No export results found - run export stage first")
            return False
        
        successful_exports = [r for r in export_results if r.get('success')]
        if not successful_exports:
            print("❌ No successful exports found")
            return False
        
        print(f"✓ Found {len(successful_exports)} exported tables")
        for result in successful_exports:
            print(f"  - {result.get('table')}")
        print()
        
        # Get target connection
        target_conn = db.query(Connection).filter_by(id=migration.target_connection_id).first()
        if not target_conn:
            print(f"❌ Target connection {migration.target_connection_id} not found")
            return False
        
        # Get connection params
        conn_params = target_conn.connection_params or {}
        
        # Decrypt credentials
        print("Decrypting credentials...")
        encryption_service = get_encryption_service()
        
        try:
            target_password = encryption_service.decrypt(conn_params.get('password_encrypted', ''))
            print("✓ Target password decrypted")
        except Exception as e:
            print(f"✗ Failed to decrypt target password: {e}")
            return False
        
        try:
            aws_secret_access_key = encryption_service.decrypt(
                migration.aws_secret_access_key_encrypted
            )
            print("✓ AWS secret key decrypted")
        except Exception as e:
            print(f"✗ Failed to decrypt AWS secret key: {e}")
            return False
        
        # Get configuration
        project_id = migration.source_project_id
        dataset_name = migration.source_dataset
        database_name = project_id.replace('-', '_').lower()
        schema_name = dataset_name
        
        # Get Redshift host - handle different field names
        redshift_host = (
            conn_params.get('host') or 
            conn_params.get('server_name') or 
            conn_params.get('cluster') or
            conn_params.get('endpoint')
        )
        
        if not redshift_host:
            print("❌ Redshift host not found in connection params")
            print(f"Available params: {list(conn_params.keys())}")
            return False
        
        print()
        print("="*80)
        print("CONFIGURATION")
        print("="*80)
        print(f"GCP Project: {project_id}")
        print(f"GCP Dataset: {dataset_name}")
        print(f"Redshift Database: {database_name}")
        print(f"Redshift Schema: {schema_name}")
        print(f"Redshift Cluster: {redshift_host}")
        print(f"IAM Role: {migration.iam_role_arn}")
        print(f"S3 Bucket: s3://{migration.s3_bucket}/{migration.s3_path or ''}")
        print("="*80)
        print()
        
        # Initialize Redshift Loader
        print("Initializing Redshift Loader...")
        loader = RedshiftLoader(
            redshift_host=redshift_host,
            redshift_port=conn_params.get('port', 5439),
            redshift_database=conn_params.get('database', conn_params.get('database_name', 'dev')),
            redshift_user=conn_params.get('username'),
            redshift_password=target_password,
            iam_role_arn=migration.iam_role_arn,
            aws_access_key_id=migration.aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_region='us-east-1'
        )
        
        # Connect to Redshift
        print("Connecting to Redshift...")
        if not loader.connect():
            print("❌ Failed to connect to Redshift")
            return False
        
        print("✓ Connected to Redshift")
        print()
        
        # Verify IAM role
        loader.verify_iam_role()
        print()
        
        # Step 1: Create database
        print("="*80)
        print(f"STEP 1: CREATE DATABASE '{database_name}'")
        print("="*80)
        
        try:
            with loader.connection.cursor() as cursor:
                cursor.execute("""
                    SELECT datname FROM pg_database 
                    WHERE datname = %s
                """, (database_name,))
                
                if cursor.fetchone():
                    print(f"✓ Database '{database_name}' already exists")
                else:
                    print(f"Creating database '{database_name}'...")
                    cursor.execute(f'CREATE DATABASE "{database_name}"')
                    loader.connection.commit()
                    print(f"✓ Database '{database_name}' created")
        except Exception as e:
            print(f"✗ Failed to create database: {e}")
            loader.disconnect()
            return False
        
        print()
        
        # Step 2: Reconnect to new database
        print("="*80)
        print(f"STEP 2: CONNECT TO DATABASE '{database_name}'")
        print("="*80)
        
        loader.disconnect()
        loader.redshift_database = database_name
        
        if not loader.connect():
            print(f"❌ Failed to connect to database '{database_name}'")
            return False
        
        print(f"✓ Connected to database '{database_name}'")
        print()
        
        # Step 3: Create schema
        print("="*80)
        print(f"STEP 3: CREATE SCHEMA '{schema_name}'")
        print("="*80)
        
        try:
            with loader.connection.cursor() as cursor:
                cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"')
                loader.connection.commit()
                print(f"✓ Schema '{schema_name}' ready")
        except Exception as e:
            print(f"✗ Failed to create schema: {e}")
            loader.disconnect()
            return False
        
        print()
        
        # Step 4: Load tables
        print("="*80)
        print("STEP 4: LOAD TABLES")
        print("="*80)
        print()
        
        s3_bucket = migration.s3_bucket.replace('s3://', '').strip('/')
        s3_path = migration.s3_path.strip('/') if migration.s3_path else ''
        
        load_results = []
        successful_loads = 0
        failed_loads = 0
        total_rows_loaded = 0
        
        for i, export_result in enumerate(successful_exports, 1):
            table_ref = export_result.get('table', '')
            table_name = table_ref.split('.')[-1] if '.' in table_ref else table_ref
            columns = export_result.get('schema', [])
            
            if not columns:
                print(f"⚠️  Skipping {table_name} - no schema found")
                continue
            
            print(f"[{i}/{len(successful_exports)}] Loading table: {table_name}")
            print(f"  Source: {project_id}.{dataset_name}.{table_name}")
            print(f"  Target: {database_name}.{schema_name}.{table_name}")
            print(f"  Columns: {len(columns)}")
            
            # Construct S3 prefix
            if s3_path:
                table_s3_prefix = f"{s3_path}/{dataset_name}/{table_name}"
            else:
                table_s3_prefix = f"{dataset_name}/{table_name}"
            
            print(f"  S3 Location: s3://{s3_bucket}/{table_s3_prefix}")
            
            # Load table
            result = loader.load_table(
                schema=schema_name,
                table=table_name,
                s3_bucket=s3_bucket,
                s3_prefix=table_s3_prefix,
                columns=columns,
                file_format=migration.export_format or 'PARQUET',
                compression=migration.compression
            )
            
            load_results.append({
                'table': table_name,
                **result
            })
            
            if result.get('success'):
                successful_loads += 1
                rows_loaded = result.get('rows_loaded', 0)
                total_rows_loaded += rows_loaded
                print(f"  ✓ Success - {rows_loaded:,} rows loaded")
            else:
                failed_loads += 1
                print(f"  ✗ Failed - {result.get('error', 'Unknown error')}")
            
            print()
        
        # Disconnect
        loader.disconnect()
        
        # Summary
        print("="*80)
        print("LOAD SUMMARY")
        print("="*80)
        print(f"Database: {database_name}")
        print(f"Schema: {schema_name}")
        print(f"Tables loaded successfully: {successful_loads}/{len(successful_exports)}")
        print(f"Tables failed: {failed_loads}")
        print(f"Total rows loaded: {total_rows_loaded:,}")
        print("="*80)
        
        if successful_loads == 0:
            print()
            print("❌ NO TABLES LOADED SUCCESSFULLY")
            return False
        
        print()
        print("✅ DATA LOADED TO REDSHIFT SUCCESSFULLY!")
        return True
        
    finally:
        db.close()

if __name__ == "__main__":
    # Get migration ID or name from command line
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg.isdigit():
            success = load_to_redshift(migration_id=int(arg))
        else:
            success = load_to_redshift(migration_name=arg)
    else:
        # Default to latest migration
        print("Usage: python load_to_redshift_direct.py <migration_id_or_name>")
        print("Example: python load_to_redshift_direct.py 18")
        print("Example: python load_to_redshift_direct.py bq_rs_data_migration")
        sys.exit(1)
    
    sys.exit(0 if success else 1)
