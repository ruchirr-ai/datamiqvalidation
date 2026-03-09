"""
Check how much query history is actually available in BigQuery
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import json
from google.cloud import bigquery
from google.oauth2 import service_account
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# Get database configuration
db_host = os.getenv('APP_DB_HOST', 'localhost')
db_port = os.getenv('APP_DB_PORT', '5432')
db_name = os.getenv('APP_DB_NAME')
db_user = os.getenv('APP_DB_USER')
db_password = os.getenv('APP_DB_PASSWORD', '')

if db_password:
    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
else:
    database_url = f"postgresql://{db_user}@{db_host}:{db_port}/{db_name}"

engine = create_engine(database_url)

print("=" * 80)
print("BigQuery Query History Analysis")
print("=" * 80)
print()

# Get BigQuery connection
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT id, name, database, connection_params
        FROM connections
        WHERE database = 'bigquery'
        AND is_active = true
        ORDER BY created_at DESC
        LIMIT 1
    """))
    
    row = result.fetchone()
    if not row:
        print("❌ No BigQuery connection found")
        sys.exit(1)
    
    connection_params = row[3]
    print(f"✓ Using connection: {row[1]}")

# Initialize BigQuery client
credentials_json = connection_params['credentials_json']
if isinstance(credentials_json, str):
    credentials_json = json.loads(credentials_json)

project_id = connection_params.get('project_id') or credentials_json.get('project_id')
credentials = service_account.Credentials.from_service_account_info(credentials_json)
client = bigquery.Client(credentials=credentials, project=project_id)

# Detect region
datasets = list(client.list_datasets())
if not datasets:
    print("❌ No datasets found")
    sys.exit(1)

first_dataset = client.get_dataset(datasets[0].dataset_id)
location = first_dataset.location.lower()
region = location if location in ['us', 'eu'] else location

print(f"✓ Project ID: {project_id}")
print(f"✓ Region: {region}")
print()

# Check query history for different time periods
time_periods = [
    ("Last 7 days", 7),
    ("Last 30 days", 30),
    ("Last 90 days", 90),
    ("Last 180 days", 180),
]

print("Query History Analysis:")
print("-" * 80)

for period_name, days in time_periods:
    query = f"""
    SELECT 
        COUNT(*) as query_count,
        COUNT(DISTINCT user_email) as unique_users,
        MIN(creation_time) as oldest_query,
        MAX(creation_time) as newest_query
    FROM `{project_id}.region-{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
    WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
        AND job_type = 'QUERY'
        AND state = 'DONE'
    """
    
    try:
        query_job = client.query(query)
        results = query_job.result()
        
        for row in results:
            print(f"\n{period_name}:")
            print(f"  Total Queries: {row.query_count}")
            print(f"  Unique Users: {row.unique_users}")
            if row.oldest_query:
                print(f"  Oldest Query: {row.oldest_query}")
                print(f"  Newest Query: {row.newest_query}")
                actual_days = (row.newest_query - row.oldest_query).days
                print(f"  Actual Range: {actual_days} days")
            else:
                print(f"  No queries found")
    except Exception as e:
        print(f"\n{period_name}: ❌ Error - {e}")

print()
print("=" * 80)
print("Analysis Complete")
print("=" * 80)
print()

# Provide interpretation
print("Interpretation:")
print()
print("If you see queries only in 'Last 7 days' but not in longer periods,")
print("it means BigQuery only has 7 days of query history available.")
print()
print("Possible reasons:")
print("1. The BigQuery project is new (less than 7 days old)")
print("2. No queries were executed before 7 days ago")
print("3. Service account only has access to recent queries")
print("4. Query history was cleared/reset")
print()
print("The assessment service will collect ALL available history (up to 180 days).")
print("If BigQuery only has 7 days, the assessment will show 7 days.")
