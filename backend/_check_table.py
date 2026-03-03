import psycopg2
conn = psycopg2.connect(host='localhost', port=5432, database='datamiq', user='postgres', password='12345678')
cur = conn.cursor()
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'datasync_agents' ORDER BY ordinal_position")
for row in cur.fetchall():
    print(row)
conn.close()
