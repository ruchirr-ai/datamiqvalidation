"""Update migration #1 to use product-dev account resources."""
import sys; sys.path.insert(0, ".")
from dotenv import load_dotenv; load_dotenv("../.env")
from database import db_instance
from sqlalchemy import text

with db_instance.get_session() as db:
    db.execute(text("""
        UPDATE migrations_bq_iceberg
        SET glue_database_name = 'datamiq_iceberg',
            s3_bucket = 'datamiq-data',
            s3_path_prefix = 'iceberg/',
            aws_region = 'us-east-1',
            status = 'pending',
            current_stage = NULL,
            progress_percentage = 0,
            start_time = NULL,
            structure_report = NULL,
            cost_analysis_report = NULL,
            structure_approved_at = NULL,
            checkpoint_data = '{}',
            updated_at = NOW()
        WHERE id = 1
    """))
    db.commit()
    r = db.execute(text(
        "SELECT id, migration_name, status, glue_database_name, s3_bucket FROM migrations_bq_iceberg WHERE id=1"
    )).fetchone()
    print(f"Updated: id={r[0]}, name={r[1]}, status={r[2]}")
    print(f"  Glue DB: {r[3]}")
    print(f"  S3 bucket: {r[4]}")
