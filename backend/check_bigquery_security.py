"""
Check BigQuery for Row-Level Security policies
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from database import db_instance
from repositories.connection_repository import ConnectionRepository
from google.cloud import bigquery
from google.oauth2 import service_account
import json


def check_rls_policies(connection_id: int):
    """Check if BigQuery has any RLS policies"""
    db = db_instance.SessionLocal()
    
    try:
        conn_repo = ConnectionRepository(db)
        connection = conn_repo.get_by_id(connection_id)
        
        if not connection:
            print(f"Connection {connection_id} not found")
            return
        
        print(f"Connection: {connection.name}")
        print(f"Type: {connection.type}")
        
        # Get credentials
        connection_params = connection.connection_params
        credentials_json = connection_params.get('credentials_json')
        if isinstance(credentials_json, str):
            credentials_json = json.loads(credentials_json)
        
        project_id = connection_params.get('project_id') or credentials_json.get('project_id')
        print(f"Project ID: {project_id}")
        
        # Create BigQuery client
        credentials = service_account.Credentials.from_service_account_info(credentials_json)
        client = bigquery.Client(credentials=credentials, project=project_id)
        
        print("\n" + "="*60)
        print("Checking for Row-Level Security Policies")
        print("="*60)
        
        # Try to query INFORMATION_SCHEMA.ROW_ACCESS_POLICIES
        query = f"""
        SELECT 
            table_catalog,
            table_schema,
            table_name,
            policy_name,
            grantees,
            filter_predicate
        FROM `{project_id}.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES`
        LIMIT 100
        """
        
        try:
            print(f"\nQuerying: {project_id}.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES")
            results = client.query(query).result()
            
            policies = list(results)
            print(f"\n✓ Found {len(policies)} RLS policies")
            
            if policies:
                print("\nRLS Policies:")
                for row in policies:
                    print(f"\n  Dataset: {row.table_schema}")
                    print(f"  Table: {row.table_name}")
                    print(f"  Policy: {row.policy_name}")
                    print(f"  Filter: {row.filter_predicate}")
                    print(f"  Grantees: {row.grantees}")
            else:
                print("\nNo RLS policies found in this project.")
                print("This is normal if you haven't configured any Row-Level Security.")
                
        except Exception as e:
            print(f"\n❌ Error querying ROW_ACCESS_POLICIES: {e}")
            print("\nThis could mean:")
            print("1. Your BigQuery project doesn't have any RLS policies")
            print("2. The INFORMATION_SCHEMA.ROW_ACCESS_POLICIES view is not available in your region")
            print("3. The service account lacks permissions to read RLS policies")
        
        # Check for datasets
        print("\n" + "="*60)
        print("Available Datasets")
        print("="*60)
        
        datasets = list(client.list_datasets())
        if datasets:
            print(f"\nFound {len(datasets)} datasets:")
            for dataset in datasets:
                print(f"  - {dataset.dataset_id}")
        else:
            print("\nNo datasets found")
        
        # Check for policy tags (Column-Level Security)
        print("\n" + "="*60)
        print("Checking for Policy Tags (Column-Level Security)")
        print("="*60)
        
        query_tags = f"""
        SELECT 
            table_schema,
            table_name,
            column_name,
            policy_tags
        FROM `{project_id}.INFORMATION_SCHEMA.COLUMN_FIELD_PATHS`
        WHERE policy_tags IS NOT NULL
        LIMIT 100
        """
        
        try:
            print(f"\nQuerying: {project_id}.INFORMATION_SCHEMA.COLUMN_FIELD_PATHS")
            results = client.query(query_tags).result()
            
            tags = list(results)
            print(f"\n✓ Found {len(tags)} columns with policy tags")
            
            if tags:
                print("\nColumns with Policy Tags:")
                for row in tags:
                    print(f"\n  Dataset: {row.table_schema}")
                    print(f"  Table: {row.table_name}")
                    print(f"  Column: {row.column_name}")
                    print(f"  Policy Tags: {row.policy_tags}")
            else:
                print("\nNo policy tags found.")
                
        except Exception as e:
            print(f"\n❌ Error querying policy tags: {e}")
        
    finally:
        db.close()


if __name__ == "__main__":
    print("BigQuery Security Policy Checker")
    print("="*60)
    
    # Check connection 6 (bq_demo)
    check_rls_policies(6)
