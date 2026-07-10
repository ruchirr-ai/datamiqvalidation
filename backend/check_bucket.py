import os, boto3
from dotenv import load_dotenv; load_dotenv("../.env")
s3 = boto3.client("s3", region_name="us-east-1",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"))
try:
    r = s3.head_bucket(Bucket="sk-manasa")
    print("Bucket sk-manasa: accessible")
    loc = s3.get_bucket_location(Bucket="sk-manasa")
    region = loc["LocationConstraint"] or "us-east-1"
    print(f"Region: {region}")
    r2 = s3.list_objects_v2(Bucket="sk-manasa", Prefix="iceberg/", MaxKeys=5)
    keys = [o["Key"] for o in r2.get("Contents", [])]
    print(f"Objects under iceberg/: {keys}")
except Exception as e:
    print(f"Error: {e}")
