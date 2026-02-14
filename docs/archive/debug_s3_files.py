#!/usr/bin/env python3
"""
Debug script to check S3 files and understand why data isn't loading to Redshift.
"""

import sys
import os
import boto3

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db
from models.bq_redshift_migration import MigrationBQRedshift
from services.encryption_service import get_encryption_service

def debug_s3_files():
    """Check S3 files to understand data loading issue."""
    
    print("="*80)
    print("DEBUGGING S3 FILES AND DATA LOADING")
    print("="*80)
    
    db = next(get_db())
    
    try:
        # Get migration
        migration = db.query(MigrationBQRedshift).filter_by(id=12).first()
        
        if not migration:
            print("❌ Migration 12 not found")
            return
        
        print(f"\nMigration: {migration.migration_name}")
        print(f"S3 Bucket: {migration.s3_bucket}")
        print(f"S3 Path: {migration.s3_path}")
        
        # Decrypt AWS credentials
        encryption_service = get_encryption_service()
        aws_secret_key = encryption_service.decrypt(migration.aws_secret_access_key_encrypted)
        
        # Initialize S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=migration.aws_access_key_id,
            aws_secret_access_key=aws_secret_key,
            region_name='us-east-1'
        )
        
        # Get export results
        checkpoint_data = migration.checkpoint_data or {}
        export_results = checkpoint_data.get('export_results', [])
        
        print(f"\n{'='*80}")
        print("CHECKING S3 FILES")
        print("="*80)
        
        for export_result in export_results:
            if not export_result.get('success'):
                continue
            
            table_name_full = export_result['table']
            table_name = table_name_full.split('.')[-1]
            dataset_name = table_name_full.split('.')[-2]
            
            print(f"\n{'='*80}")
            print(f"TABLE: {table_name}")
            print("="*80)
            
            # Expected S3 path
            s3_path = migration.s3_path.strip('/')
            s3_prefix = f"{s3_path}/{dataset_name}/{table_name}/"
            
            print(f"S3 Prefix: s3://{migration.s3_bucket}/{s3_prefix}")
            
            # List files in S3
            try:
                response = s3_client.list_objects_v2(
                    Bucket=migration.s3_bucket,
                    Prefix=s3_prefix
                )
                
                if 'Contents' not in response:
                    print("❌ No files found in S3!")
                    print(f"   Expected path: s3://{migration.s3_bucket}/{s3_prefix}")
                    
                    # Try listing parent directory
                    print(f"\n   Checking parent directory...")
                    parent_prefix = f"{s3_path}/{dataset_name}/"
                    parent_response = s3_client.list_objects_v2(
                        Bucket=migration.s3_bucket,
                        Prefix=parent_prefix,
                        MaxKeys=10
                    )
                    
                    if 'Contents' in parent_response:
                        print(f"   Files found in parent directory:")
                        for obj in parent_response['Contents'][:10]:
                            print(f"     - {obj['Key']} ({obj['Size']} bytes)")
                    else:
                        print(f"   No files in parent directory either")
                    
                    continue
                
                files = response['Contents']
                print(f"✓ Found {len(files)} file(s) in S3")
                
                total_size = 0
                for obj in files:
                    size = obj['Size']
                    total_size += size
                    print(f"  - {obj['Key']}")
                    print(f"    Size: {size:,} bytes")
                    print(f"    Last Modified: {obj['LastModified']}")
                    
                    # Check if file is empty
                    if size == 0:
                        print(f"    ⚠️  WARNING: File is empty!")
                
                print(f"\nTotal size: {total_size:,} bytes")
                
                # Compare with BigQuery export info
                bq_rows = export_result.get('num_rows', 0)
                bq_bytes = export_result.get('num_bytes', 0)
                
                print(f"\nBigQuery Export Info:")
                print(f"  Rows: {bq_rows:,}")
                print(f"  Bytes: {bq_bytes:,}")
                
                if total_size == 0:
                    print(f"\n❌ ISSUE: S3 files are empty!")
                    print(f"   BigQuery had {bq_rows} rows, but S3 files have 0 bytes")
                    print(f"   This suggests the GCS to S3 transfer failed or transferred empty files")
                elif total_size < bq_bytes * 0.5:  # Less than 50% of expected size
                    print(f"\n⚠️  WARNING: S3 files are smaller than expected")
                    print(f"   Expected ~{bq_bytes:,} bytes, got {total_size:,} bytes")
                else:
                    print(f"\n✓ File sizes look reasonable")
                
                # Try to download and inspect first file
                if len(files) > 0 and files[0]['Size'] > 0:
                    first_file = files[0]
                    print(f"\n{'='*80}")
                    print(f"INSPECTING FIRST FILE: {first_file['Key']}")
                    print("="*80)
                    
                    try:
                        # Download file
                        local_file = f"/tmp/{table_name}_sample.parquet"
                        s3_client.download_file(
                            migration.s3_bucket,
                            first_file['Key'],
                            local_file
                        )
                        print(f"✓ Downloaded to {local_file}")
                        
                        # Try to read with pyarrow
                        try:
                            import pyarrow.parquet as pq
                            
                            parquet_file = pq.ParquetFile(local_file)
                            print(f"\n✓ Valid PARQUET file")
                            print(f"  Rows: {parquet_file.metadata.num_rows:,}")
                            print(f"  Columns: {parquet_file.metadata.num_columns}")
                            print(f"  Schema:")
                            for field in parquet_file.schema:
                                print(f"    - {field.name}: {field.type}")
                            
                            # Read first few rows
                            table = parquet_file.read()
                            print(f"\n  First 3 rows:")
                            print(table.to_pandas().head(3).to_string())
                            
                        except Exception as e:
                            print(f"❌ Failed to read PARQUET file: {e}")
                            print(f"   This might be why Redshift can't load the data")
                        
                        # Clean up
                        os.remove(local_file)
                        
                    except Exception as e:
                        print(f"❌ Failed to download/inspect file: {e}")
                
            except Exception as e:
                print(f"❌ Error listing S3 files: {e}")
        
        print(f"\n{'='*80}")
        print("DIAGNOSIS COMPLETE")
        print("="*80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()

if __name__ == "__main__":
    debug_s3_files()
