"""
Populate BigQuery tables with sample data.

This script inserts actual data into the BigQuery tables so they can be exported.
"""

import sys
import os
import json
from datetime import datetime, date
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db
from models.bq_redshift_migration import MigrationBQRedshift
from models.connection import Connection
from google.cloud import bigquery
from google.oauth2 import service_account

def main():
    db = next(get_db())
    
    # Get migration 12
    migration = db.query(MigrationBQRedshift).filter_by(id=12).first()
    source_conn = db.query(Connection).filter_by(id=migration.source_connection_id).first()
    
    # Get credentials
    conn_params = source_conn.connection_params or {}
    service_account_key = (
        conn_params.get('service_account_key') or 
        conn_params.get('serviceAccountKey') or
        conn_params.get('credentials_json')
    )
    
    if isinstance(service_account_key, str):
        credentials_dict = json.loads(service_account_key)
    else:
        credentials_dict = service_account_key
    
    project_id = credentials_dict.get('project_id')
    dataset = migration.source_dataset
    
    print(f"\n{'='*80}")
    print(f"POPULATING BIGQUERY TABLES WITH SAMPLE DATA")
    print(f"{'='*80}")
    print(f"Project: {project_id}")
    print(f"Dataset: {dataset}")
    print(f"{'='*80}\n")
    
    # Create BigQuery client
    credentials = service_account.Credentials.from_service_account_info(credentials_dict)
    client = bigquery.Client(credentials=credentials, project=project_id)
    
    # Sample data for customers table
    customers_data = [
        {
            'customer_id': 1,
            'customer_name': 'John Doe',
            'email': 'john.doe@example.com',
            'city': 'New York',
            'created_at': datetime(2024, 1, 15, 10, 30, 0)
        },
        {
            'customer_id': 2,
            'customer_name': 'Jane Smith',
            'email': 'jane.smith@example.com',
            'city': 'Los Angeles',
            'created_at': datetime(2024, 2, 20, 14, 45, 0)
        },
        {
            'customer_id': 3,
            'customer_name': 'Bob Johnson',
            'email': 'bob.johnson@example.com',
            'city': 'Chicago',
            'created_at': datetime(2024, 3, 10, 9, 15, 0)
        }
    ]
    
    # Sample data for orders table
    orders_data = [
        {
            'order_id': 101,
            'customer_id': 1,
            'order_amount': 250.50,
            'order_status': 'completed',
            'order_date': date(2024, 1, 20)
        },
        {
            'order_id': 102,
            'customer_id': 1,
            'order_amount': 175.25,
            'order_status': 'completed',
            'order_date': date(2024, 2, 15)
        },
        {
            'order_id': 103,
            'customer_id': 2,
            'order_amount': 450.00,
            'order_status': 'pending',
            'order_date': date(2024, 3, 5)
        },
        {
            'order_id': 104,
            'customer_id': 3,
            'order_amount': 325.75,
            'order_status': 'completed',
            'order_date': date(2024, 3, 12)
        }
    ]
    
    # Insert customers
    print(f"\n{'='*80}")
    print(f"INSERTING CUSTOMERS DATA")
    print(f"{'='*80}")
    
    customers_table = f"{project_id}.{dataset}.customers"
    
    # First, delete existing data
    print(f"Deleting existing data from {customers_table}...")
    delete_query = f"DELETE FROM `{customers_table}` WHERE 1=1"
    delete_job = client.query(delete_query)
    delete_job.result()
    print(f"✓ Existing data deleted")
    
    # Insert new data
    print(f"\nInserting {len(customers_data)} customers...")
    errors = client.insert_rows_json(customers_table, customers_data)
    
    if errors:
        print(f"✗ Errors occurred while inserting customers:")
        for error in errors:
            print(f"  {error}")
    else:
        print(f"✓ Successfully inserted {len(customers_data)} customers")
        
        # Verify
        verify_query = f"SELECT COUNT(*) as cnt FROM `{customers_table}`"
        verify_job = client.query(verify_query)
        result = list(verify_job.result())
        count = result[0]['cnt'] if result else 0
        print(f"✓ Verified: {count} rows in customers table")
        
        # Show sample
        sample_query = f"SELECT * FROM `{customers_table}` LIMIT 3"
        sample_job = client.query(sample_query)
        sample_results = list(sample_job.result())
        print(f"\nSample data:")
        for row in sample_results:
            print(f"  {dict(row)}")
    
    # Insert orders
    print(f"\n{'='*80}")
    print(f"INSERTING ORDERS DATA")
    print(f"{'='*80}")
    
    orders_table = f"{project_id}.{dataset}.orders"
    
    # First, delete existing data
    print(f"Deleting existing data from {orders_table}...")
    delete_query = f"DELETE FROM `{orders_table}` WHERE 1=1"
    delete_job = client.query(delete_query)
    delete_job.result()
    print(f"✓ Existing data deleted")
    
    # Insert new data
    print(f"\nInserting {len(orders_data)} orders...")
    errors = client.insert_rows_json(orders_table, orders_data)
    
    if errors:
        print(f"✗ Errors occurred while inserting orders:")
        for error in errors:
            print(f"  {error}")
    else:
        print(f"✓ Successfully inserted {len(orders_data)} orders")
        
        # Verify
        verify_query = f"SELECT COUNT(*) as cnt FROM `{orders_table}`"
        verify_job = client.query(verify_query)
        result = list(verify_job.result())
        count = result[0]['cnt'] if result else 0
        print(f"✓ Verified: {count} rows in orders table")
        
        # Show sample
        sample_query = f"SELECT * FROM `{orders_table}` LIMIT 4"
        sample_job = client.query(sample_query)
        sample_results = list(sample_job.result())
        print(f"\nSample data:")
        for row in sample_results:
            print(f"  {dict(row)}")
    
    print(f"\n{'='*80}")
    print(f"✓ DATA POPULATION COMPLETE")
    print(f"{'='*80}")
    print(f"\nYou can now run the export and migration again.")
    print(f"The tables now have actual data that will be exported.")

if __name__ == "__main__":
    main()
