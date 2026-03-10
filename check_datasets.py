import sys
sys.path.insert(0, 'backend')
from database import db_instance
from sqlalchemy import text

with db_instance.engine.connect() as conn:
    r = conn.execute(text("SELECT dataset_name, table_count, round(total_size_mb::numeric, 2) as size_mb FROM assessment_datasets WHERE assessment_id=6 ORDER BY total_size_mb DESC"))
    rows = r.fetchall()
    print(f"\n{'DATASET NAME':<40} {'TABLES':>8} {'SIZE (MB)':>12}")
    print("-" * 62)
    for row in rows:
        print(f"{row[0]:<40} {row[1]:>8} {row[2]:>12}")
    print(f"\nTotal: {len(rows)} datasets")
