"""
Simple test to check if query statistics can be collected
Run this to diagnose the issue
"""

from google.cloud import bigquery
from google.oauth2 import service_account
import json
import sys

# Get connection from database
from database import db_instance
from repositories.connection_repository import ConnectionRepository

def test_query_stats():
    """Test query statistics collection"""
    
    db = db_instance.SessionLocal()
    try:
        # Get BigQuery connection (adjust ID as needed)
        conn_repo = ConnectionRepository(db)
        connections = conn_repo.list_connections()
        
        bq_connection = None
        for conn in connections:
            if conn.type == 'bigquery':
                bq_connection = conn
                break
        
        if not bq_connection:
            print("No BigQuery connection found in database")
            print(f"Available connections: {[f'{c.name} ({c.type})' for c in connections]}")
            return
        
        print(f"Using connection: {bq_connection.name}")
        print(f"Project ID: {bq_connection.database}")
        
        # Parse credentials
        credentials_json = bq_connection.connection_params.get('credentials_json')
        if isinstance(credentials_json, str):
            credentials_json = json.loads(credentials_json)
        
        project_id = bq_connection.connection_params.get('project_id') or bq_connection.database
        
        # Create BigQuery client
        credentials = service_account.Credentials.from_service_account_info(credentials_json)
        client = bigquery.Client(credentials=credentials, project=project_id)
        
        print(f"\n✓ Connected to BigQuery")
        
        # Detect region
        print("\n" + "="*80)
        print("DETECTING REGION")
        print("="*80)
        
        datasets = list(client.list_datasets())
        if not datasets:
            print("No datasets found!")
            return
        
        first_dataset = client.get_dataset(datasets[0].dataset_id)
        location = first_dataset.location
        
        print(f"First dataset: {datasets[0].dataset_id}")
        print(f"Location: {location}")
        
        # Determine region
        region = 'us'
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
        
        print(f"Detected region: {region}")
        
        # Test query
        print("\n" + "="*80)
        print(f"TESTING QUERY WITH REGION: {region}")
        print("="*80)
        
        query = f"""
        SELECT
            job_id,
            creation_time,
            user_email,
            total_bytes_processed,
            total_slot_ms,
            cache_hit
        FROM `{project_id}.region-{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
        WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
            AND job_type = 'QUERY'
            AND state = 'DONE'
        ORDER BY creation_time DESC
        LIMIT 20
        """
        
        print(f"\nExecuting query...")
        print(f"Table: `{project_id}.region-{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`")
        
        try:
            query_job = client.query(query)
            results = list(query_job.result())
            
            print(f"\n✓ Query successful!")
            print(f"✓ Found {len(results)} queries")
            
            if results:
                # Count unique users
                unique_users = set(row.user_email for row in results if row.user_email)
                print(f"\nUnique users: {len(unique_users)}")
                for user in sorted(unique_users):
                    user_queries = [r for r in results if r.user_email == user]
                    print(f"  - {user}: {len(user_queries)} queries")
                
                print(f"\nSample queries:")
                for i, row in enumerate(results[:5], 1):
                    print(f"\n  Query {i}:")
                    print(f"    User: {row.user_email}")
                    print(f"    Time: {row.creation_time}")
                    print(f"    Bytes: {row.total_bytes_processed or 0:,}")
                    print(f"    Slots: {row.total_slot_ms or 0:,} ms")
                    print(f"    Cache: {'Yes' if row.cache_hit else 'No'}")
            else:
                print("\n⚠ No queries found in the last 7 days")
                print("\nTrying to check if ANY queries exist...")
                
                # Try without time filter
                count_query = f"""
                SELECT COUNT(*) as total
                FROM `{project_id}.region-{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
                WHERE job_type = 'QUERY'
                """
                
                count_job = client.query(count_query)
                count_result = list(count_job.result())[0]
                print(f"Total queries in INFORMATION_SCHEMA: {count_result.total}")
                
        except Exception as e:
            print(f"\n✗ Query failed!")
            print(f"Error: {str(e)}")
            print(f"\nTrying other regions...")
            
            # Try other regions
            for test_region in ['us', 'eu', 'asia']:
                if test_region == region:
                    continue
                
                print(f"\nTrying region: {test_region}")
                test_query = f"""
                SELECT COUNT(*) as count
                FROM `{project_id}.region-{test_region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
                WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
                    AND job_type = 'QUERY'
                """
                
                try:
                    test_job = client.query(test_query)
                    test_result = list(test_job.result())[0]
                    print(f"  ✓ region-{test_region}: {test_result.count} queries found")
                except Exception as e2:
                    print(f"  ✗ region-{test_region}: {str(e2)[:100]}")
        
        print("\n" + "="*80)
        print("TEST COMPLETE")
        print("="*80)
        
    finally:
        db.close()


if __name__ == "__main__":
    test_query_stats()
