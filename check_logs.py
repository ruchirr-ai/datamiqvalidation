import psycopg2
conn = psycopg2.connect(
    host='datamiq.cluster-ch4gq2icq60n.us-east-1.rds.amazonaws.com',
    dbname='datamiq', user='postgres', password='Shellkode123', sslmode='require'
)
cur = conn.cursor()
cur.execute("""
    SELECT stage, log_level, message, created_at 
    FROM assessment_logs 
    WHERE assessment_id = 9
    ORDER BY created_at DESC LIMIT 30
""")
for row in cur.fetchall():
    print(f'[{row[3]}] [{row[0]}] [{row[1]}] {row[2][:500]}')
cur.close()
conn.close()
