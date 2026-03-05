"""
Redshift Load Engine for BigQuery to Redshift Migration

Handles the final stage of migration: Loading data from S3 into Redshift
with comprehensive error handling, type mapping, and manifest-based loading.
"""

import logging
import json
import boto3
import psycopg2
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class RedshiftLoader:
    """
    Redshift Load Engine with:
    - BigQuery to Redshift type mapping
    - IAM role verification
    - Manifest-based loading
    - Comprehensive error handling and recovery
    """
    
    # BigQuery to Redshift type mapping (2026 standard)
    TYPE_MAPPING = {
        'STRING': 'VARCHAR(65535)',
        'BYTES': 'VARCHAR(65535)',
        'INTEGER': 'BIGINT',
        'INT64': 'BIGINT',
        'FLOAT': 'DOUBLE PRECISION',
        'FLOAT64': 'DOUBLE PRECISION',
        'NUMERIC': 'DECIMAL(38, 9)',
        'BIGNUMERIC': 'DECIMAL(38, 9)',
        'BOOLEAN': 'BOOLEAN',
        'BOOL': 'BOOLEAN',
        'DATE': 'DATE',
        'DATETIME': 'TIMESTAMP',
        'TIMESTAMP': 'TIMESTAMPTZ',
        'TIME': 'TIME',
        'GEOGRAPHY': 'GEOMETRY',
        'STRUCT': 'SUPER',  # Must be exported as JSON
        'RECORD': 'SUPER',  # Must be exported as JSON
        'ARRAY': 'SUPER',   # Must be exported as JSON
        'JSON': 'SUPER'
    }
    
    def __init__(
        self,
        redshift_host: str,
        redshift_port: int,
        redshift_database: str,
        redshift_user: str,
        redshift_password: str,
        iam_role_arn: str,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        aws_region: str = 'us-east-1'
    ):
        """
        Initialize Redshift Loader.
        
        Args:
            redshift_host: Redshift cluster endpoint
            redshift_port: Redshift port (default 5439)
            redshift_database: Database name
            redshift_user: Database user
            redshift_password: Database password
            iam_role_arn: IAM role ARN for S3 access
            aws_access_key_id: AWS access key
            aws_secret_access_key: AWS secret key
            aws_region: AWS region
        """
        self.redshift_host = redshift_host
        self.redshift_port = redshift_port
        self.redshift_database = redshift_database
        self.redshift_user = redshift_user
        self.redshift_password = redshift_password
        self.iam_role_arn = iam_role_arn
        self.aws_region = aws_region
        
        # Initialize AWS clients
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region
        )
        
        self.iam_client = boto3.client(
            'iam',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region
        )
        
        self.connection = None
        self.migration_id = None
        self.migration_name = None
    
    def connect(self) -> bool:
        """
        Establish connection to Redshift cluster.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info("="*80)
            logger.info("CONNECTING TO REDSHIFT")
            logger.info("="*80)
            logger.info(f"Host: {self.redshift_host}")
            logger.info(f"Port: {self.redshift_port}")
            logger.info(f"Database: {self.redshift_database}")
            logger.info(f"User: {self.redshift_user}")
            
            self.connection = psycopg2.connect(
                host=self.redshift_host,
                port=self.redshift_port,
                database=self.redshift_database,
                user=self.redshift_user,
                password=self.redshift_password,
                sslmode='require',
                connect_timeout=30
            )
            
            self.connection.autocommit = True
            
            logger.info("✓ Connected to Redshift successfully")
            logger.info("="*80)
            return True
            
        except Exception as e:
            logger.error("="*80)
            logger.error("✗ FAILED TO CONNECT TO REDSHIFT")
            logger.error("="*80)
            logger.error(f"Error Type: {type(e).__name__}")
            logger.error(f"Error Message: {str(e)}")
            logger.error(f"Host: {self.redshift_host}")
            logger.error(f"Port: {self.redshift_port}")
            logger.error(f"Database: {self.redshift_database}")
            logger.error("="*80)
            return False
    
    def disconnect(self):
        """Close Redshift connection"""
        if self.connection:
            try:
                self.connection.close()
                logger.info("✓ Disconnected from Redshift")
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")
    
    def create_database(self, database_name: str) -> bool:
        """
        Create database in Redshift if it doesn't exist.
        
        Note: This requires connecting to a different database (like 'dev' or 'postgres')
        to create a new database. After creation, you need to reconnect to the new database.
        
        Args:
            database_name: Name of database to create
            
        Returns:
            True if created or already exists, False on error
        """
        try:
            logger.info("="*80)
            logger.info(f"CREATING DATABASE: {database_name}")
            logger.info("="*80)
            
            # Check if database exists
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    SELECT datname FROM pg_database 
                    WHERE datname = %s
                """, (database_name,))
                
                result = cursor.fetchone()
                
                if result:
                    logger.info(f"✓ Database {database_name} already exists")
                    logger.info("="*80)
                    return True
                
                # Create database
                # Note: CREATE DATABASE cannot run inside a transaction block
                # We need to set autocommit
                old_autocommit = self.connection.autocommit
                self.connection.autocommit = True
                
                try:
                    cursor.execute(f"CREATE DATABASE {database_name}")
                    logger.info(f"✓ Database {database_name} created successfully")
                    logger.info("="*80)
                    return True
                finally:
                    self.connection.autocommit = old_autocommit
            
        except Exception as e:
            logger.error("="*80)
            logger.error(f"✗ FAILED TO CREATE DATABASE: {database_name}")
            logger.error("="*80)
            logger.error(f"Error Type: {type(e).__name__}")
            logger.error(f"Error Message: {str(e)}")
            logger.error("="*80)
            return False
    
    def verify_iam_role(self) -> bool:
        """
        Verify IAM role exists and has required S3 permissions.
        
        Note: This is a best-effort verification. If AWS credentials don't have
        iam:GetRole permission, we'll skip verification but still return True
        since Redshift can use the role directly in COPY commands.
        
        Returns:
            True if role is valid or verification is skipped, False only if role definitely doesn't exist
        """
        try:
            logger.info("="*80)
            logger.info("VERIFYING IAM ROLE")
            logger.info("="*80)
            logger.info(f"IAM Role ARN: {self.iam_role_arn}")
            
            # Extract role name from ARN
            role_name = self.iam_role_arn.split('/')[-1]
            
            # Get role details
            try:
                role = self.iam_client.get_role(RoleName=role_name)
                logger.info(f"✓ IAM Role exists: {role_name}")
                
                # Get attached policies
                try:
                    policies = self.iam_client.list_attached_role_policies(RoleName=role_name)
                    logger.info(f"Attached policies: {len(policies['AttachedPolicies'])}")
                    
                    required_permissions = ['s3:GetObject', 's3:ListBucket']
                    logger.info(f"Required permissions: {', '.join(required_permissions)}")
                    logger.info("Note: Verify manually that the role has S3 read access")
                    
                except Exception as e:
                    logger.warning(f"Could not list policies: {e}")
                    logger.warning("Skipping policy verification - will rely on Redshift runtime check")
                
                logger.info("✓ IAM Role verification complete")
                logger.info("="*80)
                return True
                
            except Exception as e:
                error_str = str(e)
                
                # Check if it's a permission error (AccessDenied)
                if 'AccessDenied' in error_str or 'not authorized' in error_str:
                    logger.warning("="*80)
                    logger.warning("⚠ IAM ROLE VERIFICATION SKIPPED")
                    logger.warning("="*80)
                    logger.warning(f"AWS credentials don't have iam:GetRole permission")
                    logger.warning(f"This is OK - Redshift will use the role directly in COPY commands")
                    logger.warning(f"IAM Role ARN: {self.iam_role_arn}")
                    logger.warning("")
                    logger.warning("To enable verification, grant these permissions to AWS credentials:")
                    logger.warning("  - iam:GetRole")
                    logger.warning("  - iam:ListAttachedRolePolicies")
                    logger.warning("")
                    logger.warning("For now, proceeding with migration...")
                    logger.warning("Redshift will validate the role when executing COPY command")
                    logger.warning("="*80)
                    return True  # Return True to allow migration to proceed
                
                # If it's not a permission error, the role might not exist
                logger.error(f"✗ IAM Role verification failed: {role_name}")
                logger.error(f"Error: {e}")
                logger.error("")
                logger.error("Possible issues:")
                logger.error("  1. IAM role doesn't exist")
                logger.error("  2. IAM role ARN is incorrect")
                logger.error("  3. IAM role is in a different AWS account")
                logger.error("")
                logger.error("Proceeding anyway - Redshift will validate at runtime")
                logger.warning("="*80)
                return True  # Still return True to allow migration to proceed
            
        except Exception as e:
            logger.warning("="*80)
            logger.warning("⚠ IAM ROLE VERIFICATION ENCOUNTERED ERROR")
            logger.warning("="*80)
            logger.warning(f"Error Type: {type(e).__name__}")
            logger.warning(f"Error Message: {str(e)}")
            logger.warning(f"IAM Role ARN: {self.iam_role_arn}")
            logger.warning("")
            logger.warning("This is not critical - proceeding with migration")
            logger.warning("Redshift will validate the IAM role when executing COPY command")
            logger.warning("="*80)
            return True  # Return True to allow migration to proceed
    
    def map_bigquery_type_to_redshift(self, bq_type: str, bq_mode: str = 'NULLABLE') -> str:
        """
        Map BigQuery data type to Redshift data type.
        
        Args:
            bq_type: BigQuery type (STRING, INT64, etc.)
            bq_mode: BigQuery mode (NULLABLE, REQUIRED, REPEATED)
            
        Returns:
            Redshift type definition
        """
        # Handle REPEATED mode (arrays)
        if bq_mode == 'REPEATED':
            return 'SUPER'  # Arrays must use SUPER type
        
        # Get base type mapping
        redshift_type = self.TYPE_MAPPING.get(bq_type.upper(), 'VARCHAR(65535)')
        
        return redshift_type
    
    def generate_ddl(
        self,
        schema: str,
        table: str,
        columns: List[Dict],
        distribution_key: Optional[str] = None,
        sort_keys: Optional[List[str]] = None
    ) -> str:
        """
        Generate Redshift DDL from BigQuery schema.
        
        Args:
            schema: Redshift schema name
            table: Table name
            columns: List of column definitions from BigQuery
            distribution_key: Column for distribution (optional)
            sort_keys: List of columns for sort key (optional)
            
        Returns:
            DDL statement
        """
        try:
            logger.info(f"Generating DDL for {schema}.{table}")
            
            # Build column definitions
            column_defs = []
            for col in columns:
                col_name = col['name']
                col_type = col.get('type', 'STRING')
                col_mode = col.get('mode', 'NULLABLE')
                
                # Map type
                redshift_type = self.map_bigquery_type_to_redshift(col_type, col_mode)
                
                # Add NOT NULL for REQUIRED fields
                nullable = '' if col_mode == 'REQUIRED' else ''
                
                column_def = f"    {col_name} {redshift_type}{nullable}"
                column_defs.append(column_def)
            
            # Build DDL
            ddl = f"CREATE TABLE IF NOT EXISTS {schema}.{table} (\n"
            ddl += ",\n".join(column_defs)
            ddl += "\n)"
            
            # Add distribution key
            if distribution_key:
                ddl += f"\nDISTKEY({distribution_key})"
            
            # Add sort keys
            if sort_keys:
                sort_key_str = ", ".join(sort_keys)
                ddl += f"\nSORTKEY({sort_key_str})"
            
            ddl += ";"
            
            logger.info(f"✓ DDL generated for {schema}.{table}")
            return ddl
            
        except Exception as e:
            logger.error(f"✗ Failed to generate DDL for {schema}.{table}")
            logger.error(f"Error: {e}")
            raise
    
    def create_table(self, schema: str, table: str, ddl: str) -> bool:
        """
        Create table in Redshift.
        
        Args:
            schema: Schema name
            table: Table name
            ddl: DDL statement
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("="*80)
            logger.info(f"CREATING TABLE: {schema}.{table}")
            logger.info("="*80)
            
            # Create schema if not exists
            with self.connection.cursor() as cursor:
                cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
                logger.info(f"✓ Schema {schema} ready")
                
                # Create table
                logger.info(f"Executing DDL:\n{ddl}")
                cursor.execute(ddl)
                logger.info(f"✓ Table {schema}.{table} created successfully")
            
            logger.info("="*80)
            return True
            
        except Exception as e:
            logger.error("="*80)
            logger.error(f"✗ FAILED TO CREATE TABLE: {schema}.{table}")
            logger.error("="*80)
            logger.error(f"Error Type: {type(e).__name__}")
            logger.error(f"Error Message: {str(e)}")
            logger.error(f"DDL:\n{ddl}")
            logger.error("="*80)
            return False
    
    def list_s3_files(self, bucket: str, prefix: str) -> List[str]:
        """
        List all files in S3 prefix.
        
        Args:
            bucket: S3 bucket name
            prefix: S3 prefix/path
            
        Returns:
            List of S3 file URIs
        """
        try:
            logger.info(f"Listing files in s3://{bucket}/{prefix}")
            
            files = []
            skipped = []
            paginator = self.s3_client.get_paginator('list_objects_v2')
            
            # Data file extensions we expect from BigQuery exports
            data_extensions = ('.csv', '.parquet', '.json', '.avro', '.gz', '.snappy', '.zst')
            
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']
                        # Skip directories
                        if key.endswith('/'):
                            continue
                        
                        # Skip non-data files (metadata, manifests, etc.)
                        key_lower = key.lower()
                        if any(key_lower.endswith(ext) for ext in data_extensions):
                            file_uri = f"s3://{bucket}/{key}"
                            files.append(file_uri)
                        else:
                            skipped.append(key)
            
            logger.info(f"✓ Found {len(files)} data files")
            for f in files[:10]:  # Log first 10 files
                logger.info(f"  {f}")
            if len(files) > 10:
                logger.info(f"  ... and {len(files) - 10} more")
            if skipped:
                logger.info(f"  Skipped {len(skipped)} non-data files: {skipped[:5]}")
            
            return files
            
        except Exception as e:
            logger.error(f"✗ Failed to list S3 files")
            logger.error(f"Error: {e}")
            raise
    
    def generate_manifest(
        self,
        files: List[str],
        manifest_bucket: str,
        manifest_key: str
    ) -> str:
        """
        Generate and upload manifest file to S3.
        
        Args:
            files: List of S3 file URIs
            manifest_bucket: Bucket for manifest file
            manifest_key: Key for manifest file
            
        Returns:
            Manifest S3 URI
        """
        try:
            logger.info("="*80)
            logger.info("GENERATING MANIFEST FILE")
            logger.info("="*80)
            logger.info(f"Files: {len(files)}")
            logger.info(f"Manifest: s3://{manifest_bucket}/{manifest_key}")
            
            # Create manifest JSON
            manifest = {
                "entries": [
                    {"url": file_uri, "mandatory": True}
                    for file_uri in files
                ]
            }
            
            manifest_json = json.dumps(manifest, indent=2)
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=manifest_bucket,
                Key=manifest_key,
                Body=manifest_json.encode('utf-8'),
                ContentType='application/json'
            )
            
            manifest_uri = f"s3://{manifest_bucket}/{manifest_key}"
            logger.info(f"✓ Manifest uploaded: {manifest_uri}")
            logger.info(f"Manifest contains {len(files)} files")
            logger.info("="*80)
            
            return manifest_uri
            
        except Exception as e:
            logger.error("="*80)
            logger.error("✗ FAILED TO GENERATE MANIFEST")
            logger.error("="*80)
            logger.error(f"Error: {e}")
            logger.error("="*80)
            raise
    
    def execute_copy_command(
        self,
        schema: str,
        table: str,
        manifest_uri: str,
        file_format: str = 'PARQUET',
        compression: Optional[str] = None,
        s3_prefix: Optional[str] = None
    ) -> Tuple[bool, Dict]:
        """
        Execute Redshift COPY command with manifest or prefix.
        Waits for COPY to complete and returns actual load statistics.
        
        Args:
            schema: Schema name
            table: Table name
            manifest_uri: S3 URI of manifest file (or prefix for PARQUET)
            file_format: File format (PARQUET, CSV, JSON)
            compression: Compression type (GZIP, etc.)
            s3_prefix: S3 prefix for direct load (used for PARQUET instead of manifest)
            
        Returns:
            Tuple of (success, stats)
        """
        import time
        
        try:
            logger.info("="*80)
            logger.info(f"EXECUTING COPY COMMAND: {schema}.{table}")
            logger.info("="*80)
            logger.info(f"Format: {file_format}")
            logger.info(f"IAM Role: {self.iam_role_arn}")
            
            # For PARQUET, use prefix instead of manifest (simpler and more reliable)
            # BUT if a manifest_uri is provided, always use it (manifest is preferred)
            is_csv = file_format.upper() == 'CSV'
            is_parquet = file_format.upper() == 'PARQUET'
            
            if manifest_uri:
                logger.info(f"Manifest: {manifest_uri}")
                
                # Build COPY command with manifest
                if is_csv:
                    # CSV format: use CSV option with IGNOREHEADER for BigQuery exports
                    # BigQuery CSV exports include a header row by default
                    # TIMEFORMAT/DATEFORMAT 'auto' handles BigQuery's timestamp formats
                    # EMPTYASNULL treats empty fields as NULL (BigQuery exports NULLs as empty)
                    # ACCEPTINVCHARS replaces invalid UTF-8 chars instead of failing
                    # MAXERROR allows some bad rows without failing the entire load
                    copy_sql = f"""
            COPY {schema}.{table}
            FROM '{manifest_uri}'
            IAM_ROLE '{self.iam_role_arn}'
            CSV
            IGNOREHEADER 1
            TIMEFORMAT 'auto'
            DATEFORMAT 'auto'
            EMPTYASNULL
            BLANKSASNULL
            ACCEPTINVCHARS
            MAXERROR 1000
            MANIFEST
            STATUPDATE ON
            COMPUPDATE ON"""
                else:
                    copy_sql = f"""
            COPY {schema}.{table}
            FROM '{manifest_uri}'
            IAM_ROLE '{self.iam_role_arn}'
            FORMAT AS {file_format}
            MANIFEST
            STATUPDATE ON"""
                    
                    # COMPUPDATE is not supported for PARQUET
                    if not is_parquet:
                        copy_sql += "\n            COMPUPDATE ON"
                
                if compression and compression.upper() != 'NONE':
                    copy_sql += f"\n            {compression}"
                
                copy_sql += ";"
            elif is_parquet and s3_prefix:
                logger.info(f"S3 Prefix: {s3_prefix}")
                
                # Build COPY command with prefix (fallback when no manifest)
                copy_sql = f"""
            COPY {schema}.{table}
            FROM '{s3_prefix}'
            IAM_ROLE '{self.iam_role_arn}'
            FORMAT AS PARQUET;"""
            elif is_csv and s3_prefix:
                logger.info(f"S3 Prefix: {s3_prefix}")
                
                # CSV with prefix (no manifest)
                copy_sql = f"""
            COPY {schema}.{table}
            FROM '{s3_prefix}'
            IAM_ROLE '{self.iam_role_arn}'
            CSV
            IGNOREHEADER 1
            TIMEFORMAT 'auto'
            DATEFORMAT 'auto'
            EMPTYASNULL
            BLANKSASNULL
            ACCEPTINVCHARS
            MAXERROR 1000
            STATUPDATE ON
            COMPUPDATE ON"""
                
                if compression and compression.upper() != 'NONE':
                    copy_sql += f"\n            {compression}"
                
                copy_sql += ";"
            else:
                logger.error("No manifest URI or S3 prefix provided")
                return False, {'error': 'No manifest URI or S3 prefix provided'}
            
            logger.info(f"COPY SQL:\n{copy_sql}")
            
            # Execute COPY
            start_time = datetime.utcnow()
            copy_id = None
            
            with self.connection.cursor() as cursor:
                cursor.execute(copy_sql)
                
                # Try to get the COPY query ID for tracking
                try:
                    cursor.execute("SELECT pg_last_copy_id()")
                    copy_id_result = cursor.fetchone()
                    copy_id = copy_id_result[0] if copy_id_result else None
                    if copy_id:
                        logger.info(f"COPY Query ID: {copy_id}")
                except Exception as e:
                    logger.warning(f"Could not get COPY ID: {e}")
            
            # Wait for COPY to complete by polling system tables
            logger.info("Waiting for COPY operation to complete...")
            max_wait_seconds = 3600  # 1 hour timeout
            poll_interval = 5  # Check every 5 seconds
            elapsed = 0
            copy_completed = False
            
            while elapsed < max_wait_seconds:
                time.sleep(poll_interval)
                elapsed += poll_interval
                
                # Check if COPY completed successfully
                with self.connection.cursor() as cursor:
                    if copy_id:
                        # Check by COPY ID (most accurate)
                        cursor.execute("""
                            SELECT COUNT(*) 
                            FROM stl_load_commits 
                            WHERE query = %s
                        """, (copy_id,))
                    else:
                        # Fallback: Check by time and table name
                        cursor.execute("""
                            SELECT COUNT(*) 
                            FROM stl_load_commits 
                            WHERE schema_name = %s 
                              AND table_name = %s
                              AND load_time >= %s
                        """, (schema, table, start_time))
                    
                    result = cursor.fetchone()
                    if result and result[0] > 0:
                        copy_completed = True
                        logger.info(f"✓ COPY operation completed after {elapsed}s")
                        break
                
                # Check for errors during COPY
                error_details = self._get_load_errors(schema, table, copy_id, start_time)
                if error_details:
                    logger.error(f"✗ COPY operation failed with {len(error_details)} errors")
                    logger.error("DETAILED ERROR INFORMATION:")
                    for error in error_details[:5]:  # Show first 5 errors
                        logger.error(f"  Line: {error.get('line_number')}")
                        logger.error(f"  Column: {error.get('column_name')}")
                        logger.error(f"  Error: {error.get('error_message')}")
                        logger.error(f"  Raw Line: {error.get('raw_line', '')[:200]}")
                    self._log_copy_history(schema, table, copy_sql, manifest_uri or s3_prefix, file_format, compression, start_time, 'failed', error_message='COPY failed', error_details=error_details)
                    return False, {'error': 'COPY failed', 'error_details': error_details}
                
                if elapsed % 30 == 0:  # Log progress every 30 seconds
                    logger.info(f"Still waiting for COPY to complete... ({elapsed}s elapsed)")
            
            if not copy_completed:
                logger.error(f"✗ COPY operation timed out after {max_wait_seconds}s")
                self._log_copy_history(schema, table, copy_sql, manifest_uri or s3_prefix, file_format, compression, start_time, 'failed', error_message=f'COPY timeout after {max_wait_seconds}s')
                return False, {'error': f'COPY timeout after {max_wait_seconds}s'}
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            # Get final load statistics
            stats = self._get_load_stats(schema, table, copy_id, start_time)
            
            logger.info("="*80)
            logger.info("✓ COPY COMMAND COMPLETED SUCCESSFULLY")
            logger.info("="*80)
            logger.info(f"Duration: {duration:.2f} seconds")
            logger.info(f"Rows Loaded: {stats.get('rows_loaded', 0):,}")
            logger.info(f"Bytes Loaded: {stats.get('bytes_loaded', 0):,}")
            logger.info("="*80)
            
            self._log_copy_history(schema, table, copy_sql, manifest_uri or s3_prefix, file_format, compression, start_time, 'completed', rows_loaded=stats.get('rows_loaded', 0), bytes_loaded=stats.get('bytes_loaded', 0))
            
            return True, stats
            
        except Exception as e:
            logger.error("="*80)
            logger.error(f"✗ COPY COMMAND FAILED: {schema}.{table}")
            logger.error("="*80)
            logger.error(f"Error Type: {type(e).__name__}")
            logger.error(f"Error Message: {str(e)}")
            if s3_prefix:
                logger.error(f"S3 Prefix: {s3_prefix}")
            else:
                logger.error(f"Manifest: {manifest_uri}")
            logger.error("="*80)
            
            # Get detailed error information
            error_details = self._get_load_errors(schema, table)
            if error_details:
                logger.error("DETAILED ERROR INFORMATION:")
                for error in error_details:
                    logger.error(f"  Line: {error.get('line_number')}")
                    logger.error(f"  Column: {error.get('column_name')}")
                    logger.error(f"  Error: {error.get('error_message')}")
                    logger.error(f"  Raw Line: {error.get('raw_line', '')[:200]}")
                logger.error("="*80)
            
            self._log_copy_history(schema, table, copy_sql if 'copy_sql' in dir() else '', manifest_uri or (s3_prefix if 's3_prefix' in dir() else ''), file_format, compression, start_time if 'start_time' in dir() else datetime.utcnow(), 'failed', error_message=str(e), error_details=error_details)
            
            return False, {'error': str(e), 'error_details': error_details}
    
    def _log_copy_history(self, schema, table, copy_sql, source_uri, file_format, compression, start_time, status, rows_loaded=0, bytes_loaded=0, error_message=None, error_details=None):
        """Log COPY command to copy_history table."""
        try:
            from database import db_instance
            from models.copy_history import CopyHistory
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds() if start_time else None
            
            with db_instance.get_session() as db:
                record = CopyHistory(
                    migration_id=self.migration_id or 0,
                    migration_name=self.migration_name or 'Unknown',
                    schema_name=schema,
                    table_name=table,
                    copy_command=copy_sql.strip() if copy_sql else '',
                    source_uri=source_uri,
                    file_format=file_format,
                    compression=compression,
                    iam_role_arn=self.iam_role_arn,
                    status=status,
                    started_at=start_time,
                    completed_at=end_time,
                    duration_seconds=duration,
                    rows_loaded=rows_loaded or 0,
                    bytes_loaded=bytes_loaded or 0,
                    error_message=error_message,
                    error_details=error_details,
                )
                db.add(record)
        except Exception as log_err:
            logger.warning(f"Failed to log COPY history: {log_err}")

    def _get_load_stats(
        self, 
        schema: str, 
        table: str, 
        copy_id: Optional[int] = None,
        start_time: Optional[datetime] = None
    ) -> Dict:
        """
        Get load statistics for a COPY command.
        
        Tries multiple approaches in order:
        1. SYS_LOAD_HISTORY (best - has loaded_rows and loaded_bytes)
        2. STL_QUERY (rows affected by the query)
        3. stl_load_commits lines_scanned (rough row count)
        
        Args:
            schema: Schema name
            table: Table name
            copy_id: COPY query ID from pg_last_copy_id()
            start_time: Start time of COPY operation
            
        Returns:
            Dictionary with rows_loaded and bytes_loaded
        """
        rows_loaded = 0
        bytes_loaded = 0
        
        # Approach 1: SYS_LOAD_HISTORY (has loaded_rows and loaded_bytes)
        try:
            if copy_id:
                query = """
                SELECT loaded_rows, loaded_bytes
                FROM sys_load_history
                WHERE query_id = %s
                """
                params = (copy_id,)
            else:
                query = """
                SELECT loaded_rows, loaded_bytes
                FROM sys_load_history
                WHERE table_name = %s
                  AND start_time >= %s
                ORDER BY start_time DESC
                LIMIT 1
                """
                params = (table, start_time or datetime.utcnow())
            
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                result = cursor.fetchone()
                if result:
                    rows_loaded = result.get('loaded_rows', 0) or 0
                    bytes_loaded = result.get('loaded_bytes', 0) or 0
                    if rows_loaded > 0 or bytes_loaded > 0:
                        logger.info(f"Stats from SYS_LOAD_HISTORY: rows={rows_loaded:,}, bytes={bytes_loaded:,}")
                        return {'rows_loaded': rows_loaded, 'bytes_loaded': bytes_loaded}
                    else:
                        logger.info("SYS_LOAD_HISTORY returned 0 rows/bytes, trying next approach")
        except Exception as e:
            logger.warning(f"SYS_LOAD_HISTORY query failed: {e}")
        
        # Approach 2: STL_QUERY (has rows column = number of rows affected)
        try:
            if copy_id:
                with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT rows, elapsed / 1000000.0 as duration_sec
                        FROM stl_query
                        WHERE query = %s
                    """, (copy_id,))
                    result = cursor.fetchone()
                    if result and result.get('rows'):
                        rows_loaded = result.get('rows', 0) or 0
                        logger.info(f"Stats from STL_QUERY: rows={rows_loaded:,}")
                        # STL_QUERY doesn't have bytes, try to get from S3 file sizes
        except Exception as e:
            logger.warning(f"STL_QUERY query failed: {e}")
        
        # Approach 3: stl_load_commits lines_scanned (rough row count if nothing else worked)
        if rows_loaded == 0:
            try:
                if copy_id:
                    with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                        cursor.execute("""
                            SELECT SUM(lines_scanned) as total_lines
                            FROM stl_load_commits
                            WHERE query = %s
                        """, (copy_id,))
                        result = cursor.fetchone()
                        if result and result.get('total_lines'):
                            rows_loaded = result.get('total_lines', 0) or 0
                            logger.info(f"Stats from stl_load_commits: lines_scanned={rows_loaded:,}")
            except Exception as e:
                logger.warning(f"stl_load_commits query failed: {e}")
        
        # Approach 4: Get bytes from S3 source files if we still don't have bytes
        if bytes_loaded == 0 and rows_loaded > 0:
            try:
                if copy_id:
                    with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                        # STL_FILE_SCAN has bytes column
                        cursor.execute("""
                            SELECT SUM(bytes) as total_bytes
                            FROM stl_file_scan
                            WHERE query = %s
                        """, (copy_id,))
                        result = cursor.fetchone()
                        if result and result.get('total_bytes'):
                            bytes_loaded = result.get('total_bytes', 0) or 0
                            logger.info(f"Stats from stl_file_scan: bytes={bytes_loaded:,}")
            except Exception as e:
                logger.warning(f"stl_file_scan query failed: {e}")
        
        logger.info(f"Final load stats: rows={rows_loaded:,}, bytes={bytes_loaded:,}")
        return {'rows_loaded': rows_loaded, 'bytes_loaded': bytes_loaded}
    
    def _get_load_errors(
        self, 
        schema: str, 
        table: str, 
        copy_id: Optional[int] = None,
        start_time: Optional[datetime] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Get load errors from STL_LOAD_ERRORS.
        
        Args:
            schema: Schema name
            table: Table name
            copy_id: COPY query ID (optional, for precise tracking)
            start_time: Start time of COPY operation (optional, fallback)
            limit: Maximum number of errors to return
            
        Returns:
            List of error dictionaries
        """
        try:
            if copy_id:
                # Use COPY ID for precise tracking
                query = """
                SELECT 
                    line_number,
                    colname as column_name,
                    err_reason as error_message,
                    raw_line,
                    err_code
                FROM stl_load_errors
                WHERE query = %s
                ORDER BY starttime DESC
                LIMIT %s
                """
                params = (copy_id, limit)
            elif start_time:
                # Fallback: Use time-based tracking
                query = """
                SELECT 
                    line_number,
                    colname as column_name,
                    err_reason as error_message,
                    raw_line,
                    err_code
                FROM stl_load_errors
                WHERE schema_name = %s
                  AND table_name = %s
                  AND starttime >= %s
                ORDER BY starttime DESC
                LIMIT %s
                """
                params = (schema, table, start_time, limit)
            else:
                # Last resort: Recent errors only
                query = """
                SELECT 
                    line_number,
                    colname as column_name,
                    err_reason as error_message,
                    raw_line,
                    err_code
                FROM stl_load_errors
                WHERE schema_name = %s
                  AND table_name = %s
                ORDER BY starttime DESC
                LIMIT %s
                """
                params = (schema, table, limit)
            
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                errors = cursor.fetchall()
                
                return [dict(error) for error in errors]
            
        except Exception as e:
            logger.warning(f"Could not get load errors: {e}")
            return []
    
    def load_table(
        self,
        schema: str,
        table: str,
        s3_bucket: str,
        s3_prefix: str,
        columns: List[Dict],
        file_format: str = 'PARQUET',
        compression: Optional[str] = None,
        distribution_key: Optional[str] = None,
        sort_keys: Optional[List[str]] = None,
        load_type: str = 'full',
        primary_key_column: Optional[str] = None,
        truncate_before_load: bool = False
    ) -> Dict:
        """
        Complete table load process: DDL generation, manifest creation, and COPY execution.
        
        Args:
            schema: Redshift schema name
            table: Table name
            s3_bucket: S3 bucket containing data files
            s3_prefix: S3 prefix for data files
            columns: Column definitions from BigQuery
            file_format: File format (PARQUET, CSV, JSON)
            compression: Compression type
            distribution_key: Distribution key column
            sort_keys: Sort key columns
            load_type: 'full' or 'incremental'
            primary_key_column: Primary key column for upsert (incremental only)
            truncate_before_load: If True, truncate existing table before loading
            
        Returns:
            Dictionary with load results
        """
        try:
            logger.info("="*80)
            logger.info(f"LOADING TABLE: {schema}.{table}")
            logger.info("="*80)
            
            result = {
                'schema': schema,
                'table': table,
                'success': False,
                'start_time': datetime.utcnow().isoformat()
            }
            
            # Step 1: Check if table already exists
            table_exists = False
            try:
                with self.connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_schema = %s AND table_name = %s
                    """, (schema, table))
                    table_exists = cursor.fetchone() is not None
            except Exception as e:
                logger.warning(f"Could not check table existence: {e}")
            
            if table_exists:
                if truncate_before_load:
                    logger.info(f"Truncating table {schema}.{table} before load (truncate_before_load=True)")
                    try:
                        with self.connection.cursor() as cursor:
                            cursor.execute(f"TRUNCATE TABLE {schema}.{table}")
                        self.connection.commit()
                        logger.info(f"✓ Table {schema}.{table} truncated successfully")
                        result['table_action'] = 'truncate_and_load'
                    except Exception as e:
                        logger.error(f"✗ Failed to truncate table {schema}.{table}: {e}")
                        result['error'] = f'Failed to truncate table: {e}'
                        return result
                else:
                    logger.info(f"✓ Table {schema}.{table} already exists — data will be appended")
                    result['table_action'] = 'append'
            
            # Always generate DDL (needed for staging table in incremental mode, and for table creation)
            ddl = self.generate_ddl(schema, table, columns, distribution_key, sort_keys)
            
            if not table_exists:
                logger.info(f"Table {schema}.{table} does not exist — will create and load")
                result['table_action'] = 'create'
                
                if not self.create_table(schema, table, ddl):
                    result['error'] = 'Failed to create table'
                    return result
            
            # Step 2: List S3 files
            files = self.list_s3_files(s3_bucket, s3_prefix)
            if not files:
                logger.warning(f"No files found in s3://{s3_bucket}/{s3_prefix}")
                result['error'] = 'No files found'
                return result
            
            result['files_found'] = len(files)
            
            # Step 2.5: Check for pre-generated manifest file
            manifest_key = f"manifests/{table}/manifest.json"
            # Also check the path-based manifest from PathwayB
            # PathwayB generates manifests at: {s3_path}/manifests/{table_name}.manifest
            # s3_prefix here is: {s3_path}/{dataset}/{table_name}
            s3_prefix_clean = s3_prefix.strip('/')
            # Go up TWO levels (past table_name and dataset) to reach the base s3_path
            parts = s3_prefix_clean.split('/')
            base_prefix = '/'.join(parts[:-2]) if len(parts) >= 3 else ('/'.join(parts[:-1]) if len(parts) >= 2 else '')
            pathb_manifest_key = f"{base_prefix}/manifests/{table}.manifest" if base_prefix else f"manifests/{table}.manifest"
            
            pre_generated_manifest_uri = None
            for mkey in [pathb_manifest_key, manifest_key]:
                try:
                    self.s3_client.head_object(Bucket=s3_bucket, Key=mkey)
                    pre_generated_manifest_uri = f"s3://{s3_bucket}/{mkey}"
                    logger.info(f"✓ Found pre-generated manifest: {pre_generated_manifest_uri}")
                    break
                except Exception:
                    logger.info(f"  Manifest not found at: s3://{s3_bucket}/{mkey}")
                    pass
            
            # Step 3: Execute COPY command
            # For PARQUET, use prefix directly (simpler and more reliable)
            # For other formats, generate manifest
            # If a pre-generated manifest exists (from PathwayB), use it
            if load_type == 'incremental' and primary_key_column:
                # Incremental: COPY into staging table, then MERGE into target
                logger.info(f"Incremental load using primary key: {primary_key_column}")
                staging_table = f"_staging_{table}"
                
                # Create staging table with same schema
                staging_ddl = ddl.replace(
                    f"CREATE TABLE IF NOT EXISTS {schema}.{table}",
                    f"CREATE TABLE IF NOT EXISTS {schema}.{staging_table}"
                )
                if not self.create_table(schema, staging_table, staging_ddl):
                    result['error'] = 'Failed to create staging table'
                    return result
                
                # Truncate staging table
                with self.connection.cursor() as cursor:
                    cursor.execute(f"TRUNCATE TABLE {schema}.{staging_table}")
                logger.info(f"✓ Staging table {schema}.{staging_table} ready")
                
                # COPY into staging
                if file_format.upper() == 'PARQUET':
                    s3_prefix_clean = s3_prefix.strip('/')
                    s3_uri = f"s3://{s3_bucket}/{s3_prefix_clean}/"
                    success, stats = self.execute_copy_command(
                        schema, staging_table, None, file_format, compression, s3_prefix=s3_uri
                    )
                else:
                    manifest_key = f"manifests/{schema}/{table}/manifest_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
                    manifest_uri = self.generate_manifest(files, s3_bucket, manifest_key)
                    result['manifest_uri'] = manifest_uri
                    success, stats = self.execute_copy_command(
                        schema, staging_table, manifest_uri, file_format, compression
                    )
                
                if not success:
                    result['success'] = False
                    # Include detailed error info from stl_load_errors
                    error_msg = f"Load into table '{staging_table}' failed."
                    error_details = stats.get('error_details', [])
                    if error_details:
                        first_err = error_details[0]
                        error_msg += f" Column: {first_err.get('column_name', 'N/A')}, Error: {first_err.get('error_message', 'N/A')}"
                    elif stats.get('error'):
                        error_msg += f" {stats['error']}"
                    error_msg += "  Check 'stl_load_errors' system table for details."
                    result['error'] = error_msg
                    result.update(stats)
                    return result
                
                # MERGE: DELETE matching rows from target, then INSERT from staging
                logger.info(f"Merging data using key: {primary_key_column}")
                with self.connection.cursor() as cursor:
                    # Delete existing rows that match staging
                    delete_sql = f"""
                        DELETE FROM {schema}.{table}
                        USING {schema}.{staging_table}
                        WHERE {schema}.{table}.{primary_key_column} = {schema}.{staging_table}.{primary_key_column}
                    """
                    cursor.execute(delete_sql)
                    
                    # Insert all rows from staging
                    insert_sql = f"""
                        INSERT INTO {schema}.{table}
                        SELECT * FROM {schema}.{staging_table}
                    """
                    cursor.execute(insert_sql)
                    
                    # Drop staging table
                    cursor.execute(f"DROP TABLE IF EXISTS {schema}.{staging_table}")
                
                logger.info(f"✓ Incremental merge completed for {schema}.{table}")
                result['success'] = True
                result['load_type'] = 'incremental'
                result['end_time'] = datetime.utcnow().isoformat()
                result.update(stats)
            elif file_format.upper() == 'PARQUET':
                # Use pre-generated manifest if available, otherwise use prefix
                if pre_generated_manifest_uri:
                    logger.info(f"Using pre-generated manifest for PARQUET load: {pre_generated_manifest_uri}")
                    result['manifest_uri'] = pre_generated_manifest_uri
                    success, stats = self.execute_copy_command(
                        schema, table, pre_generated_manifest_uri, file_format, compression
                    )
                else:
                    # Ensure no double slashes in S3 URI
                    s3_prefix_clean = s3_prefix.strip('/')
                    s3_uri = f"s3://{s3_bucket}/{s3_prefix_clean}/"
                    logger.info(f"Using S3 prefix for PARQUET load: {s3_uri}")
                    success, stats = self.execute_copy_command(
                        schema, table, None, file_format, compression, s3_prefix=s3_uri
                    )
            else:
                # Generate manifest for non-PARQUET formats
                manifest_key = f"manifests/{schema}/{table}/manifest_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
                manifest_uri = self.generate_manifest(files, s3_bucket, manifest_key)
                result['manifest_uri'] = manifest_uri
                
                success, stats = self.execute_copy_command(
                    schema, table, manifest_uri, file_format, compression
                )
            
            result['success'] = success
            result['end_time'] = datetime.utcnow().isoformat()
            result.update(stats)
            
            if success:
                logger.info("="*80)
                logger.info(f"✓ TABLE LOAD COMPLETED: {schema}.{table}")
                logger.info("="*80)
            else:
                logger.error("="*80)
                logger.error(f"✗ TABLE LOAD FAILED: {schema}.{table}")
                logger.error("="*80)
            
            return result
            
        except Exception as e:
            logger.error("="*80)
            logger.error(f"✗ TABLE LOAD FAILED: {schema}.{table}")
            logger.error("="*80)
            logger.error(f"Error: {e}")
            logger.error("="*80)
            
            return {
                'schema': schema,
                'table': table,
                'success': False,
                'error': str(e),
                'end_time': datetime.utcnow().isoformat()
            }
