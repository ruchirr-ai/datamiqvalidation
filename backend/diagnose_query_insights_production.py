"""
Production Query Insights Diagnostic Tool

This script diagnoses why query statistics are not being collected
by using the actual connection from the database (like the assessment does).
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import json
from google.cloud import bigquery
from google.oauth2 import service_account

# Load environment variables
load_dotenv()

# Get database configuration
db_host = os.getenv('APP_DB_HOST', 'localhost')
db_port = os.getenv('APP_DB_PORT', '5432')
db_name = os.getenv('APP_DB_NAME')
db_user = os.getenv('APP_DB_USER')
db_password = os.getenv('APP_DB_PASSWORD', '')

if not db_name or not db_user:
    print("❌ Missing database configuration")
    sys.exit(1)

# Create database URL
if db_password:
    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
else:
    database_url = f"postgresql://{db_user}@{db_host}:{db_port}/{db_name}"

engine = create_engine(database_url)


def get_bigquery_connection():
    """Get a BigQuery connection from the database"""
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
            print("❌ No BigQuery connection found in database")
            print()
            print("Please create a BigQuery connection first:")
            print("1. Go to http://localhost:3000/connections")
            print("2. Click 'Add Connection'")
            print("3. Select 'BigQuery' as type")
            print("4. Fill in the connection details")
            return None
        
        return {
            'id': row[0],
            'name': row[1],
            'project_id': row[2],
            'connection_params': row[3]
        }


def diagnose_query_insights():
    """Diagnose query insights collection issues using production connection"""
    
    print("=" * 80)
    print("Production Query Insights Diagnostic Tool")
    print("=" * 80)
    print()
    
    # Step 1: Get BigQuery connection from database
    print("Step 1: Retrieving BigQuery connection from database...")
    bq_conn = get_bigquery_connection()
    if not bq_conn:
        return
    
    print(f"✓ Found BigQuery connection: {bq_conn['name']}")
    print(f"  Project ID: {bq_conn['project_id']}")
    print()
    
    # Step 2: Parse connection parameters
    print("Step 2: Parsing connection parameters...")
    try:
        connection_params = bq_conn['connection_params']
        
        # Check if credentials_json exists
        if 'credentials_json' not in connection_params:
            print("❌ No credentials_json found in connection_params")
            print()
            print("Connection params keys:", list(connection_params.keys()))
            return
        
        credentials_json = connection_params['credentials_json']
        
        # Parse if string
        if isinstance(credentials_json, str):
            credentials_json = json.loads(credentials_json)
        
        # Extract project_id from credentials (same logic as fixed assessment service)
        actual_project_id = connection_params.get('project_id') or credentials_json.get('project_id')
        
        print(f"✓ Credentials found for project: {credentials_json.get('project_id', 'unknown')}")
        print(f"  Connection database field: {bq_conn['project_id']}")
        print(f"  Actual GCP project ID: {actual_project_id}")
        
        if bq_conn['project_id'] != actual_project_id:
            print(f"  ⚠️  Mismatch detected! Using actual project ID: {actual_project_id}")
    except Exception as e:
        print(f"❌ Failed to parse connection parameters: {e}")
        return
    print()
    
    # Step 3: Initialize BigQuery client
    print("Step 3: Initializing BigQuery client...")
    try:
        credentials = service_account.Credentials.from_service_account_info(credentials_json)
        # Use the actual project ID from credentials, not the database field
        client = bigquery.Client(credentials=credentials, project=actual_project_id)
        print(f"✓ BigQuery client initialized for project: {actual_project_id}")
    except Exception as e:
        print(f"❌ Failed to initialize BigQuery client: {e}")
        return
    print()
    
    # Step 4: Detect region
    print("Step 4: Detecting BigQuery region...")
    try:
        datasets = list(client.list_datasets())
        if not datasets:
            print("❌ No datasets found in project")
            print()
            print("This project has no datasets. Query statistics require datasets to exist.")
            return
        
        first_dataset = client.get_dataset(datasets[0].dataset_id)
        location = first_dataset.location
        print(f"✓ Detected location: {location}")
        
        # Convert to region format for INFORMATION_SCHEMA
        # BigQuery INFORMATION_SCHEMA uses specific region formats
        region = 'us'  # default
        if location:
            location_lower = location.lower()
            # For multi-region locations (us, eu, asia), use as-is
            if location_lower in ['us', 'eu']:
                region = location_lower
            # For specific regions, use the full location
            else:
                region = location_lower
        print(f"✓ Using region for INFORMATION_SCHEMA: {region}")
    except Exception as e:
        print(f"❌ Failed to detect region: {e}")
        return
    print()
    
    # Step 5: Test INFORMATION_SCHEMA access
    print("Step 5: Testing INFORMATION_SCHEMA.JOBS_BY_PROJECT access...")
    test_query = f"""
    SELECT COUNT(*) as job_count
    FROM `{actual_project_id}.region-{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
    WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
        AND job_type = 'QUERY'
        AND state = 'DONE'
    """
    
    print(f"Query: {test_query}")
    print()
    
    try:
        query_job = client.query(test_query)
        results = query_job.result()
        for row in results:
            print(f"✓ Found {row.job_count} queries in last 7 days")
            
            if row.job_count == 0:
                print()
                print("⚠️  No queries found in last 7 days")
                print()
                print("This means:")
                print("1. No queries have been executed in BigQuery in the last 7 days")
                print("2. OR the service account doesn't have permission to see job history")
                print()
                print("To verify permissions:")
                print("- Service account needs 'BigQuery Job User' role")
                print("- Service account needs 'BigQuery Data Viewer' role")
                return
    except Exception as e:
        print(f"❌ Failed to query INFORMATION_SCHEMA: {e}")
        print()
        print("Common causes:")
        print("1. Service account lacks 'bigquery.jobs.list' permission")
        print("   → Grant 'BigQuery Job User' role to service account")
        print()
        print("2. Service account lacks 'bigquery.jobs.get' permission")
        print("   → Grant 'BigQuery Data Viewer' role to service account")
        print()
        print("3. Incorrect region format")
        print(f"   → Tried region: {region}")
        print("   → Try different formats: 'us', 'eu', 'asia-northeast1', etc.")
        print()
        print("4. INFORMATION_SCHEMA not enabled (rare)")
        print()
        print("To fix permissions in GCP Console:")
        print("1. Go to IAM & Admin > IAM")
        print(f"2. Find service account: {credentials_json.get('client_email', 'unknown')}")
        print("3. Click 'Edit' (pencil icon)")
        print("4. Click 'Add Another Role'")
        print("5. Add 'BigQuery Job User' role")
        print("6. Add 'BigQuery Data Viewer' role")
        print("7. Click 'Save'")
        return
    print()
    
    # Step 6: Fetch sample query data
    print("Step 6: Fetching sample query statistics...")
    sample_query = f"""
    SELECT
        job_id,
        creation_time as execution_time,
        query as query_text,
        total_bytes_processed as bytes_scanned,
        total_slot_ms as slot_milliseconds,
        cache_hit,
        referenced_tables,
        user_email
    FROM `{actual_project_id}.region-{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
    WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
        AND job_type = 'QUERY'
        AND state = 'DONE'
    ORDER BY creation_time DESC
    LIMIT 5
    """
    
    try:
        query_job = client.query(sample_query)
        results = query_job.result()
        
        count = 0
        for row in results:
            count += 1
            print(f"\nQuery {count}:")
            print(f"  Job ID: {row.job_id}")
            print(f"  Time: {row.execution_time}")
            print(f"  User: {row.user_email}")
            print(f"  Bytes: {row.bytes_scanned:,} bytes" if row.bytes_scanned else "  Bytes: 0")
            print(f"  Slot ms: {row.slot_milliseconds:,} ms" if row.slot_milliseconds else "  Slot ms: 0")
            print(f"  Cache Hit: {row.cache_hit}")
            if row.query_text:
                print(f"  Query: {row.query_text[:100]}...")
        
        if count == 0:
            print("⚠️  No queries found in last 7 days")
        else:
            print(f"\n✓ Successfully fetched {count} sample queries")
    except Exception as e:
        print(f"❌ Failed to fetch sample data: {e}")
        return
    print()
    
    print("=" * 80)
    print("Diagnosis Complete!")
    print("=" * 80)
    print()
    print("✅ If all steps passed, query insights should work after re-running assessment.")
    print()
    print("Next steps:")
    print("1. If permissions were missing, grant them in GCP Console")
    print("2. Go to http://localhost:3000/assessments")
    print("3. Delete the old assessment (if needed)")
    print("4. Create a new assessment")
    print("5. Wait for assessment to complete")
    print("6. Check Query Insights tab")
    print()


if __name__ == "__main__":
    diagnose_query_insights()
