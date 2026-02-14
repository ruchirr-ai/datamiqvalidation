"""
Diagnostic script to troubleshoot query statistics collection
"""

import asyncio
import json
from google.cloud import bigquery
from google.oauth2 import service_account

# Your BigQuery project ID
PROJECT_ID = "assessiq-484512"  # Update this with your actual project ID

# Path to your service account JSON file
SERVICE_ACCOUNT_FILE = "path/to/your/service-account.json"  # Update this path


async def diagnose_query_stats():
    """Diagnose query statistics collection issues"""
    
    print("=" * 80)
    print("BIGQUERY QUERY STATISTICS DIAGNOSTIC")
    print("=" * 80)
    
    # Load credentials
    try:
        with open(SERVICE_ACCOUNT_FILE, 'r') as f:
            credentials_json = json.load(f)
        
        credentials = service_account.Credentials.from_service_account_info(credentials_json)
        client = bigquery.Client(credentials=credentials, project=PROJECT_ID)
        print(f"✓ Connected to BigQuery project: {PROJECT_ID}\n")
    except Exception as e:
        print(f"✗ Failed to connect to BigQuery: {e}")
        return
    
    # Step 1: Detect region from first dataset
    print("STEP 1: Detecting BigQuery Region")
    print("-" * 80)
    try:
        datasets = list(client.list_datasets())
        if not datasets:
            print("✗ No datasets found in project")
            return
        
        first_dataset = client.get_dataset(datasets[0].dataset_id)
        location = first_dataset.location
        print(f"Dataset: {datasets[0].dataset_id}")
        print(f"Location: {location}")
        
        # Determine region
        region = 'us'  # Default
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
        
        print(f"Detected Region: {region}")
        print(f"✓ Region detection successful\n")
    except Exception as e:
        print(f"✗ Failed to detect region: {e}\n")
        return
    
    # Step 2: Test INFORMATION_SCHEMA access with different regions
    print("STEP 2: Testing INFORMATION_SCHEMA Access")
    print("-" * 80)
    
    regions_to_test = ['us', 'eu', 'asia', location.lower() if location else 'us']
    regions_to_test = list(set(regions_to_test))  # Remove duplicates
    
    for test_region in regions_to_test:
        print(f"\nTesting region: {test_region}")
        query = f"""
        SELECT COUNT(*) as query_count
        FROM `{PROJECT_ID}.region-{test_region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
        WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
            AND job_type = 'QUERY'
            AND state = 'DONE'
        """
        
        try:
            query_job = client.query(query)
            results = query_job.result()
            for row in results:
                count = row.query_count
                print(f"  ✓ Found {count} queries in region-{test_region}")
                if count > 0:
                    print(f"  → This is the correct region!")
        except Exception as e:
            print(f"  ✗ Error querying region-{test_region}: {str(e)[:100]}")
    
    # Step 3: Get detailed query statistics from correct region
    print(f"\n\nSTEP 3: Collecting Query Statistics from region-{region}")
    print("-" * 80)
    
    query = f"""
    SELECT
        job_id,
        creation_time,
        user_email,
        total_bytes_processed,
        total_slot_ms,
        cache_hit,
        state
    FROM `{PROJECT_ID}.region-{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
    WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
        AND job_type = 'QUERY'
        AND state = 'DONE'
    ORDER BY creation_time DESC
    LIMIT 10
    """
    
    try:
        print(f"Querying: region-{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT")
        query_job = client.query(query)
        results = query_job.result()
        
        queries = list(results)
        print(f"\n✓ Found {len(queries)} recent queries")
        
        if queries:
            print("\nSample queries:")
            for i, row in enumerate(queries[:5], 1):
                print(f"\n  Query {i}:")
                print(f"    User: {row.user_email}")
                print(f"    Time: {row.creation_time}")
                print(f"    Bytes: {row.total_bytes_processed or 0}")
                print(f"    Slots: {row.total_slot_ms or 0}")
                print(f"    Cache: {row.cache_hit}")
            
            # Count unique users
            unique_users = set(row.user_email for row in queries if row.user_email)
            print(f"\n  Unique users in sample: {len(unique_users)}")
            for user in unique_users:
                print(f"    - {user}")
        else:
            print("\n✗ No queries found in the last 7 days")
            print("\nPossible reasons:")
            print("  1. No queries have been run in the last 7 days")
            print("  2. Service account doesn't have permission to view INFORMATION_SCHEMA")
            print("  3. Wrong region is being queried")
    except Exception as e:
        print(f"\n✗ Error collecting query statistics: {e}")
        print(f"\nFull error: {str(e)}")
    
    # Step 4: Check permissions
    print("\n\nSTEP 4: Checking Permissions")
    print("-" * 80)
    
    try:
        # Try to list datasets (basic permission check)
        datasets = list(client.list_datasets())
        print(f"✓ Can list datasets: {len(datasets)} datasets found")
        
        # Try to query a dataset
        if datasets:
            test_dataset = datasets[0].dataset_id
            tables = list(client.list_tables(test_dataset))
            print(f"✓ Can list tables in {test_dataset}: {len(tables)} tables found")
        
        print("\n✓ Basic permissions look good")
        print("\nRequired permissions for INFORMATION_SCHEMA.JOBS:")
        print("  - bigquery.jobs.list")
        print("  - bigquery.jobs.get")
        print("\nIf queries are still not showing, verify the service account has these permissions.")
    except Exception as e:
        print(f"✗ Permission check failed: {e}")
    
    print("\n" + "=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(diagnose_query_stats())
