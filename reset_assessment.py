"""Reset assessment 6 status"""
from sqlalchemy import create_engine, text

db_url = "postgresql://postgres:Shellkode123@datamiq.cluster-ch4gq2icq60n.us-east-1.rds.amazonaws.com:5432/datamiq?sslmode=require"
engine = create_engine(db_url)

with engine.connect() as conn:
    result = conn.execute(text("UPDATE assessments SET status = 'failed', error_message = 'Stopped by user' WHERE id = 6 AND status = 'running'"))
    conn.commit()
    print(f"Updated {result.rowcount} row(s)")
    
    rows = conn.execute(text("SELECT id, name, status FROM assessments ORDER BY id DESC LIMIT 5")).fetchall()
    for r in rows:
        print(f"  Assessment {r[0]}: {r[1]} -> {r[2]}")
