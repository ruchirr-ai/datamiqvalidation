"""
Deep search for RLS policies in BigQuery
This script will exhaustively search for RLS policies
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from database import db_instance
from repositories.connection_repository import ConnectionRepository
from google.cloud import bigquery
from google.oauth2 import service_account
import json


def deep_search_rls(connection_id: int = 6):
    """Exhaustive search for RLS policies"""
    db = db_instance.SessionLocal()
    
    try:
        conn_repo = ConnectionRepository(db)
        connection = conn_repo.get_by_id(connection_id)
        
        if not connection:
            print(f"❌ Connection {connection_id} not found")
            return
        
        print("="*80)
        print("DEEP SEARCH FOR RLS POLICIES")
        print("="*80)
        
        # Get credentials
        connection_params = connection.connection_params
        credentials_json = connection_params.get('credentials_json')
        if isinstance(credentials_json, str):
            credentials_json = json.loads(credentials_json)
        
        project_id = connection_params.get('project_id') or credentials_json.get('project_id')
        service_account_email = credentials_json.get('client_email')
        
        print(f"\n📋 Connection: {connection.name}")
        print(f"📋 Project ID: {project_id}")
        print(f"📧 Service Account: {service_account_email}")
        
        # Create BigQuery client
        credentials = service_account.Credentials.from_service_account_info(credentials_json)
        client = bigquery.Client(credentials=credentials, project=project_id)
        
        # List all datasets
        print("\n" + "="*80)
        print("STEP 1: List all datasets and their locations")
        print("="*80)
        
        datasets = list(client.list_datasets())
        print(f"\nFound {len(datasets)} dataset(s):")
        
        for dataset in datasets:
            dataset_ref = client.get_dataset(dataset.dataset_id)
            print(f"\n  📁 Dataset: {dataset.dataset_id}")
            print(f"     Location: {dataset_ref.location}")
            print(f"     Created: {dataset_ref.created}")
            
            # List tables in dataset
            tables = list(client.list_tables(dataset.dataset_id))
            print(f"     Tables: {len(tables)}")
            
            if tables:
                for table in tables[:5]:  # Show first 5 tables
                    print(f"       - {table.table_id}")
                if len(tables) > 5:
                    print(f"       ... and {len(tables) - 5} more")
        
        # Try different query approaches
        print("\n" + "="*80)
        print("STEP 2: Try different INFORMATION_SCHEMA queries")
        print("="*80)
        
        # Approach 1: Project-level with region
        for region in ['US', 'EU', 'us-central1', 'us-east1', 'europe-west1']:
            print(f"\n  Trying region: {region}")
            try:
                query = f"""
                SELECT COUNT(*) as count
                FROM `{project_id}.region-{region}.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES`
                """
                result = list(client.query(query).result())
                count = result[0].count if result else 0
                if count > 0:
                    print(f"    ✅ Found {count} policies in region {region}!")
                else:
                    print(f"    ⚠️  No policies in region {region}")
            except Exception as e:
                if "was not found" not in str(e):
                    print(f"    ❌ Error: {str(e)[:100]}")
        
        # Approach 2: Per-dataset queries with details
        print("\n" + "="*80)
        print("STEP 3: Check each dataset individually")
        print("="*80)
        
        total_policies = 0
        for dataset in datasets:
            dataset_id = dataset.dataset_id
            print(f"\n  📁 Checking dataset: {dataset_id}")
            
            # Try to query ROW_ACCESS_POLICIES
            try:
                query = f"""
                SELECT 
                    table_catalog,
                    table_schema,
                    table_name,
                    policy_name,
                    filter_predicate,
                    grantee_list
                FROM `{project_id}.{dataset_id}.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES`
                """
                
                results = list(client.query(query).result())
                
                if results:
                    print(f"    ✅ Found {len(results)} RLS policies!")
                    total_policies += len(results)
                    
                    for row in results:
                        print(f"\n      Policy: {row.policy_name}")
                        print(f"      Table: {row.table_name}")
                        print(f"      Filter: {row.filter_predicate}")
                        print(f"      Grantees: {row.grantee_list}")
                else:
                    print(f"    ⚠️  Query succeeded but returned 0 policies")
                    
            except Exception as e:
                error_msg = str(e)
                if "was not found" in error_msg:
                    print(f"    ⚠️  INFORMATION_SCHEMA.ROW_ACCESS_POLICIES not found")
                else:
                    print(f"    ❌ Error: {error_msg[:150]}")
        
        # Approach 3: Check individual tables
        print("\n" + "="*80)
        print("STEP 4: Check individual tables for RLS indicators")
        print("="*80)
        
        tables_with_rls_indicator = []
        
        for dataset in datasets:
            dataset_id = dataset.dataset_id
            print(f"\n  📁 Dataset: {dataset_id}")
            
            tables = list(client.list_tables(dataset_id))
            
            for table_item in tables:
                try:
                    table_full_id = f"{project_id}.{dataset_id}.{table_item.table_id}"
                    table = client.get_table(table_full_id)
                    
                    # Check table properties
                    if hasattr(table, '_properties'):
                        props = table._properties
                        
                        # Look for any RLS-related properties
                        if 'rowAccessPolicies' in props:
                            print(f"    ✅ {table_item.table_id} has rowAccessPolicies property!")
                            print(f"       Value: {props['rowAccessPolicies']}")
                            tables_with_rls_indicator.append(table_full_id)
                        
                        # Check for other security-related properties
                        security_keys = [k for k in props.keys() if 'security' in k.lower() or 'policy' in k.lower() or 'access' in k.lower()]
                        if security_keys:
                            print(f"    🔍 {table_item.table_id} has security-related properties: {security_keys}")
                            
                except Exception as e:
                    pass  # Skip tables we can't access
        
        # Approach 4: Try querying with your user account (if different)
        print("\n" + "="*80)
        print("STEP 5: Verification with direct SQL")
        print("="*80)
        
        print("\n📝 Please run this query in BigQuery Console with YOUR user account:")
        print(f"""
SELECT 
    table_catalog,
    table_schema,
    table_name,
    policy_name,
    filter_predicate,
    grantee_list
FROM `{project_id}.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES`
ORDER BY table_schema, table_name;
""")
        
        print("\nIf this query returns results in the Console but not here,")
        print("it means the service account lacks permissions.")
        
        # Summary
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        
        if total_policies > 0:
            print(f"\n✅ FOUND {total_policies} RLS POLICIES!")
            print("\nRun the backfill script to collect them:")
            print("  python scripts/backfill_security_metadata.py")
        elif tables_with_rls_indicator:
            print(f"\n⚠️  Found {len(tables_with_rls_indicator)} tables with RLS indicators")
            print("but couldn't query the policies directly.")
            print("\nThis suggests a permissions or API access issue.")
        else:
            print("\n❌ NO RLS POLICIES FOUND")
            print("\nPossible reasons:")
            print("1. RLS policies don't exist in this project")
            print("2. RLS policies are in a different project")
            print("3. Service account lacks permissions")
            print("4. RLS policies are in a different region")
            
            print("\n📝 To verify, please:")
            print("1. Run the SQL query above in BigQuery Console")
            print("2. Check if you're looking at the correct project")
            print("3. Verify the dataset name matches")
        
    finally:
        db.close()


if __name__ == "__main__":
    print("Deep Search for RLS Policies")
    print("="*80)
    print("\nThis script will exhaustively search for RLS policies")
    print("in your BigQuery project using multiple methods.\n")
    
    deep_search_rls(6)
