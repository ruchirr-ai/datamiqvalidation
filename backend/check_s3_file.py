"""Check S3 file for the problematic migration file."""
import boto3
import sys

s3 = boto3.client('s3', region_name='us-east-1')

bucket = 'sk-manasa'
prefix = 'migrations/BigqueryToRedshift/sales_analytics/assess_tbl_part_clust/'

print(f"Listing files in s3://{bucket}/{prefix}")
print("=" * 80)

resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=50)
contents = resp.get('Contents', [])

if not contents:
    # Try alternate path
    prefix2 = 'migrations/bq-rs/sales_analytics/assess_tbl_part_clust/'
    print(f"No files found. Trying s3://{bucket}/{prefix2}")
    resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix2, MaxKeys=50)
    contents = resp.get('Contents', [])
    prefix = prefix2

print(f"Found {len(contents)} files:")
for obj in contents:
    print(f"  {obj['Size']:>12,}  {obj['Key']}")

# Check the specific problematic file
problem_file = None
for obj in contents:
    if '000000000181' in obj['Key']:
        problem_file = obj['Key']
        break

if problem_file:
    print(f"\nChecking problematic file: {problem_file}")
    # Download first 10 bytes to check gzip magic number
    resp = s3.get_object(Bucket=bucket, Key=problem_file, Range='bytes=0-9')
    header = resp['Body'].read()
    print(f"First 10 bytes (hex): {header.hex()}")
    print(f"First 10 bytes (raw): {header}")
    
    # Gzip magic number is 1f 8b
    if header[:2] == b'\x1f\x8b':
        print("✓ File has valid GZIP magic number")
    else:
        print("✗ File does NOT have valid GZIP magic number!")
        print(f"  Expected: 1f8b, Got: {header[:2].hex()}")
        if header[:4] == b'PK\x03\x04':
            print("  → File appears to be ZIP format, not GZIP!")
        elif header[:5] == b'<?xml':
            print("  → File appears to be XML (possibly an error response)")
        elif header[:1] == b'{':
            print("  → File appears to be JSON")
        elif header[:3] == b'PAR':
            print("  → File appears to be PARQUET format")
else:
    print("\nProblem file (000000000181) not found in listing")
    
    # Check first file instead
    if contents:
        first_file = contents[0]['Key']
        print(f"\nChecking first file instead: {first_file}")
        resp = s3.get_object(Bucket=bucket, Key=first_file, Range='bytes=0-9')
        header = resp['Body'].read()
        print(f"First 10 bytes (hex): {header.hex()}")
        if header[:2] == b'\x1f\x8b':
            print("✓ File has valid GZIP magic number")
        else:
            print(f"✗ NOT GZIP! First 2 bytes: {header[:2].hex()}")
