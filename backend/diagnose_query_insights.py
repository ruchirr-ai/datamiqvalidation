"""
Diagnostic script to troubleshoot Query Insights data collection

This script helps identify why query statistics are not being collected.
"""

import os
import sys
from google.cloud import bigquery
from google.oauth2 import service_account
import json

def diagnose_query_insights():
    """Diagnose query insights collection issues"""
    
    print("=" * 80)
    print("Query Insights Diagnostic Tool")
    print("=" * 80)
    print()
    
    # Step 1: Check environment variables
    print("Step 1: Checking environment variables...")
    gcp_creds = os.getenv('GCP_SERVICE_ACCOUNT_KEY')
    if not gcp_creds:
        print("❌ GCP_SERVICE_ACCOUNT_KEY not found in environment")
        return
    print("✓ GCP_SERVICE_ACCOUNT_KEY found")
    print()
    
    # Step 2: Initialize BigQuery client
    print("Step 2: Initializing BigQuery client...")
    try:
        credentials_info = json.loads(gcp_creds)
        credentials = service_account.Credentials.from_service_account_info(credentials_info)
        client = bigquery.Client(credentials=credentials, project=credentials_info['project_id'])
        project_id = credentials_info['project_id']
        print(f"✓ BigQuery client initialized for project: {project_id}")
    except Exception as e:
        print(f"❌ Failed to initialize BigQuery client: {e}")
        return
    print()
    
    # Step 3: Detect region
    print("Step 3: Detecting BigQuery region...")
    try:
        datasets = list(client.list_datasets())
        if not datasets:
            print("❌ No datasets found in project")
            return
        
        first_dataset = client.get_dataset(datasets[0].dataset_id)
        location = first_dataset.location
        print(f"✓ Detected location: {location}")
        
        # Convert to region format
        region = 'us'  # default
        if location:
            location_lower = location.lower()
            if location_lower.startswith('us'):
                region = 'us'
            elif location_lower.startswith('eu'):
                region = 'eu'
            elif location_lower.startswith('asia'):
                region = 'asia'
            else:
                region = location_lower
        print(f"✓ Using region: {region}")
    except Exception as e:
        print(f"❌ Failed to detect region: {e}")
        return
    print()
    
    # Step 4: Check INFORMATION_SCHEMA access
    print("Step 4: Testing INFORMATION_SCHEMA.JOBS_BY_PROJECT access...")
    test_query = f"""
    SELECT COUNT(*) as job_count
    FROM `{project_id}.region-{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
    WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
        AND job_type = 'QUERY'
        AND state = 'DONE'
    """
    
    try:
        print(f"Query: {test_query}")
        query_job = client.query(test_query)
        results = query_job.result()
        for row in results:
            print(f"✓ Found {row.job_count} queries in last 7 days")
    except Exception as e:
        print(f"❌ Failed to query INFORMATION_SCHEMA: {e}")
        print()
        print("Common causes:")
        print("1. Service account lacks 'bigquery.jobs.list' permission")
        print("2. Incorrect region format")
        print("3. INFORMATION_SCHEMA not enabled")
        print()
        print("Solutions:")
        print("1. Grant 'BigQuery Job User' role to service account")
        print("2. Grant 'BigQuery Data Viewer' role to service account")
        print("3. Try different region formats: 'us', 'eu', 'asia-northeast1', etc.")
        return
    print()
    
    # Step 5: Fetch sample query data
    print("Step 5: Fetching sample query statistics...")
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
    FROM `{project_id}.region-{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
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
            print(f"  Bytes: {row.bytes_scanned:,}")
            print(f"  Cache Hit: {row.cache_hit}")
            print(f"  Query: {row.query_text[:100] if row.query_text else 'N/A'}...")
        
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
    print("If all steps passed, query insights should work.")
    print("If any step failed, follow the solutions provided above.")
    print()


if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    diagnose_query_insights()
