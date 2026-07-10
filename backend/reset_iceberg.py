import sys
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv("../.env")
from database import db_instance
from sqlalchemy import text

with db_instance.get_session() as db:
    db.execute(text(
        "UPDATE migrations_bq_iceberg "
        "SET status='pending', current_stage=NULL, progress_percentage=0, "
        "start_time=NULL, updated_at=NOW() WHERE id=1"
    ))
    db.commit()
    r = db.execute(text("SELECT id, status, current_stage FROM migrations_bq_iceberg WHERE id=1")).fetchone()
    print(f"Reset done: id={r[0]}, status={r[1]}, stage={r[2]}")
