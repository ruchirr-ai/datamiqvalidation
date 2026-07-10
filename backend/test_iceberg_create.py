"""Test creating an Iceberg table directly with PyIceberg."""
import os, sys
sys.path.insert(0, 'C:/temp_pkgs')  # s3fs
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv("../.env")

os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = os.getenv("AWS_ACCESS_KEY_ID", "")
os.environ["AWS_SECRET_ACCESS_KEY"] = os.getenv("AWS_SECRET_ACCESS_KEY", "")

from pyiceberg.catalog.glue import GlueCatalog
from pyiceberg.schema import Schema
from pyiceberg.types import NestedField, StringType, LongType

print("Creating GlueCatalog...")
# PyIceberg GlueCatalog needs s3.region and the warehouse
catalog = GlueCatalog("glue", **{
    "warehouse": "s3://sk-manasa/iceberg",
    "region_name": "us-east-1",
    "s3.region": "us-east-1",
    "s3.access-key-id": os.getenv("AWS_ACCESS_KEY_ID"),
    "s3.secret-access-key": os.getenv("AWS_SECRET_ACCESS_KEY"),
})

schema = Schema(
    NestedField(1, "order_id", LongType(), required=False),
    NestedField(2, "name", StringType(), required=False),
)

print("Attempting to create table iceberg_demo.datamiq_test_v2...")
try:
    tbl = catalog.create_table(
        "iceberg_demo.datamiq_test_v2",
        schema=schema,
        location="s3://sk-manasa/iceberg/iceberg_demo/datamiq_test_v2",
    )
    print(f"SUCCESS! Table created: {tbl}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
