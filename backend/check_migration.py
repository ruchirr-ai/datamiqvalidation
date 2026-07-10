import sys
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv("../.env")
from database import db_instance
from sqlalchemy import text
import json

with db_instance.get_session() as db:
    m = db.execute(text(
        "SELECT id, status, current_stage, structure_report, "
        "checkpoint_data, total_rows_source, total_rows_target "
        "FROM migrations_bq_iceberg WHERE id=1"
    )).fetchone()

    print(f"status={m[1]}, stage={m[2]}, rows_source={m[5]}, rows_target={m[6]}")

    sr = m[3] if isinstance(m[3], dict) else (json.loads(m[3]) if m[3] else {})
    tables = sr.get("tables", [])
    print(f"structure_report tables count: {len(tables)}")

    cp = m[4] if isinstance(m[4], dict) else (json.loads(m[4]) if m[4] else {})
    plan = cp.get("iceberg_structure_plan", {})
    plan_tables = plan.get("tables", [])
    print(f"approved plan tables count: {len(plan_tables)}")
    print(f"checkpoint keys: {list(cp.keys())}")

    # Check BG thread logs
    logs = db.execute(text(
        "SELECT level, message, created_at FROM migration_logs "
        "WHERE migration_id=1 ORDER BY created_at DESC LIMIT 20"
    )).fetchall()
    print(f"\nRecent logs ({len(logs)}):")
    for l in logs:
        print(f"  [{l[0]}] {l[2]} - {l[1][:150]}")
