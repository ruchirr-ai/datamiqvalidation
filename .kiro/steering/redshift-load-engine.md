---
title: Redshift Load Engine
description: Comprehensive guide for loading data from S3 into Redshift with type mapping, IAM verification, and manifest-based loading
inclusion: manual
tags: [redshift, data-loading, s3, migration, bigquery]
---

# Redshift Load Engine

## Overview

The Redshift Load Engine is a production-grade service for loading data from S3 into Amazon Redshift. It handles the final stage of BigQuery to Redshift migrations (Path B and Path C) with comprehensive error handling, type mapping, and manifest-based loading for reliability and resumability.

## Key Features

### 1. BigQuery to Redshift Type Mapping (2026 Standard)

The engine automatically maps BigQuery data types to Redshift-compatible types:

| BigQuery Type | Redshift Type | Notes |
|--------------|---------------|-------|
| STRING, BYTES | VARCHAR(65535) | Maximum Redshift VARCHAR size |
| INT64, INTEGER | BIGINT | 64-bit integer |
| FLOAT64, FLOAT | DOUBLE PRECISION | Double precision floating point |
| NUMERIC, BIGNUMERIC | DECIMAL(38, 9) | High precision decimal |
| BOOL, BOOLEAN | BOOLEAN | Boolean type |
| DATE | DATE | Date without time |
| DATETIME | TIMESTAMP | Timestamp without timezone |
| TIMESTAMP | TIMESTAMPTZ | Timestamp with timezone |
| TIME | TIME | Time without date |
| GEOGRAPHY | GEOMETRY | Spatial data type |
| STRUCT, RECORD | SUPER | Semi-structured data (must be JSON) |
| ARRAY | SUPER | Arrays (must be JSON) |
| JSON | SUPER | JSON data |

**Important**: STRUCT and ARRAY types must be exported as JSON from BigQuery to be loaded into Redshift SUPER columns.

### 2. IAM Role Verification

Before loading data, the engine verifies:
- IAM role exists and is accessible
- Role has required S3 permissions:
  - `s3:GetObject` - Read objects from S3
  - `s3:ListBucket` - List bucket contents
  - `kms:Decrypt` - If S3 bucket is encrypted
  - `kms:GenerateDataKey` - If S3 bucket is encrypted

### 3. Manifest-Based Loading

The engine uses JSON manifest files for reliable, resumable loads:

**Benefits**:
- **Checkpointing**: Manifest defines exact files to load
- **Idempotency**: Re-running with same manifest loads same files
- **Resume capability**: Can regenerate manifest and retry
- **Audit trail**: Manifest provides record of what was loaded

**Manifest Format**:
```json
{
  "entries": [
    {"url": "s3://bucket/path/file1.parquet", "mandatory": true},
    {"url": "s3://bucket/path/file2.parquet", "mandatory": true}
  ]
}
```

### 4. Comprehensive Error Handling

The engine provides detailed error information from Redshift system tables:

**STL_LOAD_ERRORS**: Detailed error information
- Line number where error occurred
- Column name with issue
- Error message and reason
- Raw line content (first 200 chars)
- Error code for categorization

**STL_LOAD_COMMITS**: Load statistics
- Rows loaded successfully
- Bytes loaded
- Load duration
- Commit timestamp

### 5. DDL Generation

Automatically generates Redshift DDL from BigQuery schema:
- Maps all column types
- Handles NULLABLE vs REQUIRED modes
- Supports distribution keys (DISTKEY)
- Supports sort keys (SORTKEY)
- Creates schema if not exists

## Usage

### Basic Usage

```python
from services.bq_redshift_migration.redshift_loader import RedshiftLoader

# Initialize loader
loader = RedshiftLoader(
    redshift_host='my-cluster.redshift.amazonaws.com',
    redshift_port=5439,
    redshift_database='mydb',
    redshift_user='admin',
    redshift_password='password',
    iam_role_arn='arn:aws:iam::123456789012:role/RedshiftS3Role',
    aws_access_key_id='AKIAIOSFODNN7EXAMPLE',
    aws_secret_access_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
    aws_region='us-east-1'
)

# Connect to Redshift
if not loader.connect():
    print("Failed to connect to Redshift")
    exit(1)

# Verify IAM role
if not loader.verify_iam_role():
    print("IAM role verification failed")
    exit(1)

# Load table
result = loader.load_table(
    schema='public',
    table='customers',
    s3_bucket='my-bucket',
    s3_prefix='exports/customers/',
    columns=[
        {'name': 'id', 'type': 'INT64', 'mode': 'REQUIRED'},
        {'name': 'name', 'type': 'STRING', 'mode': 'NULLABLE'},
        {'name': 'email', 'type': 'STRING', 'mode': 'NULLABLE'},
        {'name': 'created_at', 'type': 'TIMESTAMP', 'mode': 'NULLABLE'}
    ],
    file_format='PARQUET',
    distribution_key='id',
    sort_keys=['created_at']
)

# Check result
if result['success']:
    print(f"Loaded {result['rows_loaded']:,} rows")
else:
    print(f"Load failed: {result['error']}")

# Disconnect
loader.disconnect()
```

### Integration with Migration Pathways

The Redshift Loader is integrated into Path B and Path C load stages:

**Path B**: BigQuery → GCS → S3 (DataSync) → Redshift
**Path C**: BigQuery → GCS → S3 (Direct Transfer) → Redshift

Both pathways use the same load stage implementation:

```python
def _execute_load_stage(
    self,
    migration_id: int,
    target_config: Dict,
    storage_config: Dict,
    pending_shards: List
) -> bool:
    """Load data from S3 to Redshift using RedshiftLoader"""
    
    # Initialize loader
    loader = RedshiftLoader(
        redshift_host=target_config['cluster'],
        redshift_port=target_config.get('port', 5439),
        redshift_database=target_config['database'],
        redshift_user=target_config['username'],
        redshift_password=target_config['password'],
        iam_role_arn=target_config['iam_role_arn'],
        aws_access_key_id=storage_config['aws_access_key_id'],
        aws_secret_access_key=storage_config['aws_secret_access_key'],
        aws_region=storage_config.get('aws_region', 'us-east-1')
    )
    
    # Connect and verify
    if not loader.connect():
        return False
    
    if not loader.verify_iam_role():
        loader.disconnect()
        return False
    
    # Load each table
    for table_info in tables_to_load:
        result = loader.load_table(
            schema=target_config.get('schema', 'public'),
            table=table_info['table_name'],
            s3_bucket=storage_config['s3_bucket'],
            s3_prefix=f"{storage_config['s3_path']}/{table_info['table_name']}",
            columns=table_info['columns'],
            file_format=storage_config.get('export_format', 'PARQUET'),
            distribution_key=table_info.get('distribution_key'),
            sort_keys=table_info.get('sort_keys')
        )
        
        if not result['success']:
            logger.error(f"Failed to load {table_info['table_name']}")
            loader.disconnect()
            return False
    
    loader.disconnect()
    return True
```

## Configuration Requirements

### Target Connection Configuration

The target Redshift connection must include:

```python
target_config = {
    'cluster': 'my-cluster.redshift.amazonaws.com',  # Redshift endpoint
    'port': 5439,                                     # Redshift port
    'database': 'mydb',                               # Database name
    'username': 'admin',                              # Database user
    'password': 'encrypted_password',                 # Encrypted password
    'schema': 'public',                               # Target schema
    'iam_role_arn': 'arn:aws:iam::123456789012:role/RedshiftS3Role'
}
```

### Storage Configuration

The storage configuration must include:

```python
storage_config = {
    's3_bucket': 'my-migration-bucket',
    's3_path': 'migrations/migration-123',
    'export_format': 'PARQUET',  # or CSV, JSON
    'compression': 'SNAPPY',     # or GZIP, NONE
    'aws_access_key_id': 'AKIAIOSFODNN7EXAMPLE',
    'aws_secret_access_key': 'decrypted_secret_key',
    'aws_region': 'us-east-1'
}
```

## Error Handling

### Connection Errors

If Redshift connection fails:
- Check host, port, database name
- Verify credentials
- Check security groups and network access
- Verify VPC configuration

### IAM Role Errors

If IAM role verification fails:
- Verify role ARN is correct
- Check role exists in AWS account
- Verify role has S3 read permissions
- Check role trust policy allows Redshift

### COPY Command Errors

If COPY command fails, the engine automatically queries `STL_LOAD_ERRORS` and logs:
- Line number with error
- Column name with issue
- Error message and reason
- Raw line content (truncated)

Common COPY errors:
- **Type mismatch**: Data doesn't match column type
- **Missing columns**: File has fewer columns than table
- **Extra columns**: File has more columns than table
- **Invalid format**: File format doesn't match specified format
- **Encoding issues**: Character encoding problems
- **Delimiter issues**: Wrong delimiter for CSV files

### Resume Capability

If a load fails, you can resume by:
1. Regenerating the manifest file
2. Re-running the COPY command with the same manifest
3. Redshift will skip already-loaded files if using transactions

## Performance Optimization

### Distribution Keys

Choose distribution keys based on:
- **Join columns**: Columns used in JOIN operations
- **High cardinality**: Columns with many unique values
- **Even distribution**: Columns that distribute data evenly

```python
result = loader.load_table(
    schema='public',
    table='orders',
    s3_bucket='my-bucket',
    s3_prefix='exports/orders/',
    columns=columns,
    distribution_key='customer_id',  # Distribute by customer
    sort_keys=['order_date', 'order_id']
)
```

### Sort Keys

Choose sort keys based on:
- **Filter columns**: Columns used in WHERE clauses
- **Range queries**: Columns used in range filters
- **Time series**: Date/timestamp columns for time-based queries

### File Format

**PARQUET** (Recommended):
- Columnar format
- Efficient compression
- Fast query performance
- Best for analytical workloads

**CSV**:
- Simple format
- Human-readable
- Slower than Parquet
- Good for small datasets

**JSON**:
- Semi-structured data
- Flexible schema
- Slower than Parquet
- Good for nested data

### Compression

**SNAPPY** (Recommended for Parquet):
- Fast compression/decompression
- Good compression ratio
- Low CPU overhead

**GZIP**:
- Better compression ratio
- Higher CPU overhead
- Good for network transfer

**NONE**:
- No compression
- Fastest load time
- Largest file size

## Monitoring

### Load Statistics

After each load, check:
- Rows loaded: `result['rows_loaded']`
- Bytes loaded: `result['bytes_loaded']`
- Duration: `result['end_time'] - result['start_time']`
- Files processed: `result['files_found']`

### System Tables

Query Redshift system tables for monitoring:

**Recent loads**:
```sql
SELECT 
    schema_name,
    table_name,
    SUM(rows_loaded) as total_rows,
    SUM(bytes_loaded) as total_bytes,
    MAX(load_time) as last_load_time
FROM stl_load_commits
WHERE load_time >= DATEADD(hour, -1, GETDATE())
GROUP BY schema_name, table_name
ORDER BY last_load_time DESC;
```

**Load errors**:
```sql
SELECT 
    schema_name,
    table_name,
    line_number,
    colname,
    err_reason,
    starttime
FROM stl_load_errors
WHERE starttime >= DATEADD(hour, -1, GETDATE())
ORDER BY starttime DESC
LIMIT 100;
```

## Best Practices

### 1. Always Use Manifest Files
- Provides audit trail
- Enables resume capability
- Prevents duplicate loads

### 2. Verify IAM Role Before Loading
- Catches permission issues early
- Prevents failed loads
- Saves time and resources

### 3. Use Appropriate File Format
- Parquet for large datasets
- CSV for small, simple data
- JSON for semi-structured data

### 4. Choose Distribution and Sort Keys Wisely
- Analyze query patterns
- Test different configurations
- Monitor query performance

### 5. Monitor Load Performance
- Track load times
- Monitor error rates
- Optimize based on metrics

### 6. Handle Errors Gracefully
- Log detailed error information
- Implement retry logic
- Alert on persistent failures

### 7. Use Compression
- Reduces storage costs
- Speeds up network transfer
- Minimal CPU overhead with Snappy

### 8. Test with Small Datasets First
- Validate schema mapping
- Test error handling
- Verify performance

## Troubleshooting

### Problem: COPY command fails with "permission denied"

**Solution**: Verify IAM role has S3 read permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::my-bucket",
        "arn:aws:s3:::my-bucket/*"
      ]
    }
  ]
}
```

### Problem: Type mismatch errors during load

**Solution**: Check BigQuery to Redshift type mapping. Ensure:
- STRUCT/ARRAY types are exported as JSON
- Numeric precision matches
- Date/timestamp formats are compatible

### Problem: Load is very slow

**Solution**: Optimize:
- Use Parquet format instead of CSV
- Enable compression (Snappy for Parquet)
- Increase Redshift cluster size
- Use multiple files for parallel loading

### Problem: Manifest file not found

**Solution**: Verify:
- Manifest was uploaded to S3
- S3 path is correct
- IAM role can read manifest location

### Problem: Connection timeout

**Solution**: Check:
- Redshift cluster is running
- Security groups allow inbound traffic
- VPC configuration is correct
- Network connectivity from application

## Migration Model Updates

To use the Redshift Loader, ensure your migration model includes:

```python
# In MigrationBQRedshift model
target_cluster = Column(String(255))      # Redshift endpoint
target_database = Column(String(255))     # Database name
target_schema = Column(String(255))       # Schema name
target_username = Column(String(255))     # Database user
target_password_encrypted = Column(Text)  # Encrypted password
iam_role_arn = Column(String(255))        # IAM role for S3 access
```

## Testing

### Unit Tests

Test individual methods:
```python
def test_type_mapping():
    loader = RedshiftLoader(...)
    assert loader.map_bigquery_type_to_redshift('STRING') == 'VARCHAR(65535)'
    assert loader.map_bigquery_type_to_redshift('INT64') == 'BIGINT'
    assert loader.map_bigquery_type_to_redshift('ARRAY') == 'SUPER'
```

### Integration Tests

Test complete load process:
```python
def test_load_table():
    loader = RedshiftLoader(...)
    loader.connect()
    
    result = loader.load_table(
        schema='test',
        table='test_table',
        s3_bucket='test-bucket',
        s3_prefix='test/',
        columns=[...],
        file_format='PARQUET'
    )
    
    assert result['success'] == True
    assert result['rows_loaded'] > 0
    
    loader.disconnect()
```

## References

- [Redshift COPY Command Documentation](https://docs.aws.amazon.com/redshift/latest/dg/r_COPY.html)
- [Redshift Data Types](https://docs.aws.amazon.com/redshift/latest/dg/c_Supported_data_types.html)
- [Redshift System Tables](https://docs.aws.amazon.com/redshift/latest/dg/c_intro_system_tables.html)
- [IAM Roles for Redshift](https://docs.aws.amazon.com/redshift/latest/mgmt/authorizing-redshift-service.html)
