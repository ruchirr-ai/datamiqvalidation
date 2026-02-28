"""
Verify if BigQuery project has RLS policies
This script checks multiple ways to detect RLS policies
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from database import db_instance
from repositories.connection_repository import ConnectionRepository
from google.cloud import bigquery
from google.oauth2 import service_account
import json


def verify_rls_policies(connection_id: int = 6):
    """Comprehensive check for RLS policies"""
    db = db_instance.SessionLocal()
    
    try:
        conn_repo = ConnectionRepository(db)
        connection = conn_repo.get_by_id(connection_id)
        
        if not connection:
            print(f"❌ Connection {connection_id} not found")
            return
        
        print("="*70)
        print("RLS POLICIES VERIFICATION")
        print("="*70)
        
        # Get credentials
        connection_params = connection.connection_params
        credentials_json = connection_params.get('credentials_json')
        if isinstance(credentials_json, str):
            credentials_json = json.loads(credentials_json)
        
        project_id = connection_params.get('project_id') or credentials_json.get('project_id')
        service_account_email = credentials_json.get('client_email')
        
        print(f"\n📋 Project: {project_id}")
        print(f"📧 Service Account: {service_account_email}")
        
        # Create BigQuery client
        credentials = service_account.Credentials.from_service_account_info(credentials_json)
        client = bigquery.Client(credentials=credentials, project=project_id)
        
        # Method 1: Try project-level INFORMATION_SCHEMA
        print("\n" + "="*70)
        print("METHOD 1: Project-level INFORMATION_SCHEMA.ROW_ACCESS_POLICIES")
        print("="*70)
        
        try:
            query = f"""
            SELECT COUNT(*) as policy_count
            FROM `{project_id}.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES`
            """
            result = list(client.query(query).result())
            count = result[0].policy_count if result else 0
            
            if count > 0:
                print(f"✅ Found {count} RLS policies!")
                
                # Get details
                detail_query = f"""
                SELECT 
                    table_schema,
                    table_name,
                    policy_name,
                    filter_predicate,
                    grantee_list
                FROM `{project_id}.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES`
                LIMIT 10
                """
                policies = list(client.query(detail_query).result())
                
                print("\nRLS Policies Found:")
                for p in policies:
                    print(f"\n  📌 Policy: {p.policy_name}")
                    print(f"     Table: {p.table_schema}.{p.table_name}")
                    print(f"     Filter: {p.filter_predicate}")
                    print(f"     Grantees: {p.grantee_list}")
                
                return True
            else:
                print("⚠️  No RLS policies found (count = 0)")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            if "was not found" in str(e):
                print("\n💡 This means:")
                print("   - The INFORMATION_SCHEMA.ROW_ACCESS_POLICIES view doesn't exist")
                print("   - This happens when NO RLS policies have ever been created")
                print("   - The view only appears after creating at least one RLS policy")
        
        # Method 2: Check each dataset
        print("\n" + "="*70)
        print("METHOD 2: Per-dataset INFORMATION_SCHEMA check")
        print("="*70)
        
        datasets = list(client.list_datasets())
        print(f"\nFound {len(datasets)} datasets")
        
        total_policies = 0
        for dataset in datasets:
            dataset_id = dataset.dataset_id
            print(f"\n  Checking dataset: {dataset_id}")
            
            try:
                query = f"""
                SELECT COUNT(*) as policy_count
                FROM `{project_id}.{dataset_id}.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES`
                """
                result = list(client.query(query).result())
                count = result[0].policy_count if result else 0
                
                if count > 0:
                    print(f"    ✅ Found {count} policies")
                    total_policies += count
                    
                    # Get details
                    detail_query = f"""
                    SELECT policy_name, table_name, filter_predicate
                    FROM `{project_id}.{dataset_id}.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES`
                    """
                    policies = list(client.query(detail_query).result())
                    for p in policies:
                        print(f"      - {p.policy_name} on {p.table_name}")
                else:
                    print(f"    ⚠️  No policies")
                    
            except Exception as e:
                if "was not found" in str(e):
                    print(f"    ⚠️  No RLS policies in this dataset")
                else:
                    print(f"    ❌ Error: {e}")
        
        if total_policies > 0:
            print(f"\n✅ Total RLS policies found: {total_policies}")
            return True
        
        # Method 3: Check tables directly
        print("\n" + "="*70)
        print("METHOD 3: Direct table inspection")
        print("="*70)
        
        print("\nChecking tables for RLS policy indicators...")
        tables_checked = 0
        tables_with_rls = 0
        
        for dataset in datasets[:3]:  # Check first 3 datasets only
            dataset_id = dataset.dataset_id
            print(f"\n  Dataset: {dataset_id}")
            
            try:
                tables = list(client.list_tables(dataset_id, max_results=10))
                for table_item in tables:
                    tables_checked += 1
                    table = client.get_table(f"{project_id}.{dataset_id}.{table_item.table_id}")
                    
                    # Check if table has row_access_policies property
                    if hasattr(table, '_properties'):
                        if 'rowAccessPolicies' in table._properties:
                            tables_with_rls += 1
                            print(f"    ✅ {table_item.table_id} has RLS policies")
                        
            except Exception as e:
                print(f"    ❌ Error checking tables: {e}")
        
        print(f"\nTables checked: {tables_checked}")
        print(f"Tables with RLS: {tables_with_rls}")
        
        if tables_with_rls > 0:
            return True
        
        # Final verdict
        print("\n" + "="*70)
        print("FINAL VERDICT")
        print("="*70)
        print("\n❌ NO RLS POLICIES FOUND")
        print("\nThis means your BigQuery project does NOT have any Row-Level Security")
        print("policies configured. This is completely normal if you haven't set them up.")
        print("\n📝 To create a test RLS policy, run this in BigQuery Console:")
        print(f"""
-- 1. Create a test table
CREATE TABLE `{project_id}.{datasets[0].dataset_id if datasets else 'your_dataset'}.test_rls_table` (
  id INT64,
  user_email STRING,
  data STRING
);

-- 2. Create an RLS policy
CREATE ROW ACCESS POLICY test_policy
ON `{project_id}.{datasets[0].dataset_id if datasets else 'your_dataset'}.test_rls_table`
GRANT TO ("allAuthenticatedUsers")
FILTER USING (user_email = SESSION_USER());

-- 3. Verify policy was created
SELECT * FROM `{project_id}.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES`;
""")
        
        return False
        
    finally:
        db.close()


if __name__ == "__main__":
    print("BigQuery RLS Policies Verification")
    print("="*70)
    
    has_rls = verify_rls_policies(6)
    
    if has_rls:
        print("\n✅ Your project HAS RLS policies")
        print("   Run the backfill script to collect them:")
        print("   python scripts/backfill_security_metadata.py")
    else:
        print("\n⚠️  Your project does NOT have RLS policies")
        print("   This is why they don't appear in the assessment report")
