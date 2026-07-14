"""Verify product-dev AWS account access via SSO profile."""
import os, sys
sys.path.insert(0, ".")
os.environ["AWS_PROFILE"] = "SK-Product-dev"
from dotenv import load_dotenv; load_dotenv("../.env")
import boto3

print("=== Testing product-dev account (072160582527) ===")

# S3
try:
    s3 = boto3.client("s3", region_name="us-east-1")
    buckets = [b["Name"] for b in s3.list_buckets()["Buckets"] if "datamiq" in b["Name"]]
    print(f"S3 datamiq buckets: {buckets}")
except Exception as e:
    print(f"S3 ERROR: {e}")

# Glue
try:
    glue = boto3.client("glue", region_name="us-east-1")
    db = glue.get_database(Name="datamiq_iceberg")
    name = db["Database"]["Name"]
    loc = db["Database"]["LocationUri"]
    print(f"Glue DB: {name} -> {loc}")
except Exception as e:
    print(f"Glue ERROR: {e}")

# Bedrock
try:
    b = boto3.client("bedrock", region_name="us-east-1")
    models = b.list_foundation_models()["modelSummaries"]
    claude4 = [m["modelId"] for m in models if "claude" in m["modelId"] and "sonnet-4" in m["modelId"]]
    print(f"Bedrock Claude 4: {claude4[:2]}")
except Exception as e:
    print(f"Bedrock ERROR: {e}")

# Iceberg PyIceberg test
try:
    import os as _os
    _os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    from pyiceberg.catalog.glue import GlueCatalog
    cat = GlueCatalog(name="glue", warehouse="s3://datamiq-data/iceberg", region_name="us-east-1")
    ns = cat.list_namespaces()
    print(f"PyIceberg namespaces in datamiq_iceberg: {ns[:3]}")
except Exception as e:
    print(f"PyIceberg ERROR: {e}")
