#!/usr/bin/env python3
"""
Check BigQuery region and available query history.
"""

from google.cloud import bigquery
from google.oauth2 import service_account
import json

# You'll need to provide your BigQuery credentials
PROJECT_ID = "your-project-id"  # Replace with your project ID
CREDENTIALS_FILE = "path/to/credentials.json"  # Replace with your credentials path

def check_regions():
    """Check which regions have query history."""
    
    print("=" * 80)
    print("BIGQUERY REGION AND QUERY HISTORY CHECK")
    print("=" * 80)
    print()
    
    # Load credentials
    credentials = service_account.Credentials.from_service_account_file(CREDENTIALS_FILE)
    client = bigquery.Client(credentials=credentials, project=PROJECT_ID)
    
    # Common BigQuery regions
    regions = [
        'region-us',
        'region-eu',
        'region-asia-northeast1',
        'region-asia-southeast1',
        'us',
        'eu',
    ]
    
    print(f"Project: {PROJECT_ID}")
    print()
    print("Checking regions for query history...")
    print()
    
    for region in regions:
        try:
            query = f"""
            SELECT 
                COUNT(*) as query_count,
                COUNT(DISTINCT user_email) as unique_users
            FROM `{PROJECT_ID}.{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
            WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
                AND job_type = 'QUERY'
                AND state = 'DONE'
            """
            
            query_job = client.query(query)
            results = query_job.result()
            
            for row in results:
                if row.query_count > 0:
                    print(f"✅ {region}: {row.query_count} queries from {row.unique_users} users")
                    
                    # Get user list
                    user_query = f"""
                    SELECT DISTINCT user_email
                    FROM `{PROJECT_ID}.{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
                    WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
                        AND job_type = 'QUERY'
                        AND state = 'DONE'
                    ORDER BY user_email
                    """
                    
                    user_job = client.query(user_query)
                    user_results = user_job.result()
                    
                    print(f"   Users:")
                    for user_row in user_results:
                        print(f"     • {user_row.user_email}")
                    print()
                else:
                    print(f"⚪ {region}: No queries found")
                    
        except Exception as e:
            print(f"❌ {region}: {str(e)[:100]}")
    
    print()
    print("=" * 80)
    print("RECOMMENDATION:")
    print("Update backend/services/bigquery_assessment_service.py")
    print("Change the region in collect_query_statistics_detailed() method")
    print("From: region-us")
    print("To: <the region that showed queries above>")
    print("=" * 80)

if __name__ == "__main__":
    print()
    print("NOTE: Update PROJECT_ID and CREDENTIALS_FILE in this script first!")
    print()
    # check_regions()  # Uncomment after updating credentials
