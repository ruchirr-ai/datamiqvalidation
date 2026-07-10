import sys
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv("../.env")
from database import db_instance
from sqlalchemy import text

with db_instance.get_session() as db:
    m = db.execute(text(
        "SELECT id, source_project_id, source_dataset, source_tables, "
        "service_account_json_encrypted IS NOT NULL as has_sa, "
        "source_connection_id FROM migrations_bq_iceberg WHERE id=1"
    )).fetchone()
    print(f"project={m[1]}, dataset={m[2]}, tables={m[3]}, has_sa={m[4]}, conn_id={m[5]}")

    if m[5]:
        conn = db.execute(text(
            "SELECT id, name, type FROM connections WHERE id=:cid"
        ), {"cid": m[5]}).fetchone()
        if conn:
            print(f"connection: id={conn[0]}, name={conn[1]}, type={conn[2]}")

    # Also check if SA JSON field has data
    raw = db.execute(text(
        "SELECT service_account_json_encrypted FROM migrations_bq_iceberg WHERE id=1"
    )).fetchone()
    val = raw[0]
    if val:
        print(f"SA JSON stored, first 50 chars: {str(val)[:50]}")
    else:
        print("SA JSON is NULL - not stored in migration record")
