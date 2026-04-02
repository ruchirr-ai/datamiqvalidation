"""
One-time script: Extract salesforce tables from vs_bq_assessment.
Outputs a CSV text file with table_name, rows, data_size_mb.
"""
import os
import sys
from sqlalchemy import create_engine, text

# Build DB URL from .env defaults
DB_HOST = os.getenv("APP_DB_HOST", "localhost")
DB_PORT = os.getenv("APP_DB_PORT", "5432")
DB_NAME = os.getenv("APP_DB_NAME", "datamiq")
DB_USER = os.getenv("APP_DB_USER", "postgres")
DB_PASS = os.getenv("APP_DB_PASSWORD", "12345678")
DB_SSL = os.getenv("APP_DB_SSL_MODE", "disable")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode={DB_SSL}"

engine = create_engine(DATABASE_URL)

query = text("""
    SELECT 
        t.table_name,
        t.row_count,
        t.size_mb
    FROM assessment_tables t
    JOIN assessments a ON a.id = t.assessment_id
    WHERE a.name = :assessment_name
      AND t.dataset_name = :dataset_name
    ORDER BY t.table_name
""")

with engine.connect() as conn:
    rows = conn.execute(query, {"assessment_name": "vs_bq_assessment", "dataset_name": "salesforce"}).fetchall()

if not rows:
    print("No tables found for assessment 'vs_bq_assessment' with dataset_name 'salesforce'.")
    print("Checking available assessments and datasets...")
    with engine.connect() as conn:
        assessments = conn.execute(text("SELECT id, name FROM assessments ORDER BY id")).fetchall()
        print(f"\nAvailable assessments: {[(r[0], r[1]) for r in assessments]}")
        if assessments:
            for a in assessments:
                datasets = conn.execute(
                    text("SELECT DISTINCT dataset_name FROM assessment_tables WHERE assessment_id = :aid"),
                    {"aid": a[0]}
                ).fetchall()
                print(f"  Assessment '{a[1]}' (id={a[0]}): datasets = {[d[0] for d in datasets]}")
    sys.exit(1)

# Write CSV
output_path = os.path.join(os.path.dirname(__file__), "..", "salesforce_tables.txt")
with open(output_path, "w") as f:
    f.write("table_name,rows,data_size_mb\n")
    for row in rows:
        f.write(f"{row[0]},{row[1]},{row[2]}\n")

print(f"Done! {len(rows)} tables written to {os.path.abspath(output_path)}")
