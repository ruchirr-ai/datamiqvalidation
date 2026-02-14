"""
Verify BigQuery tables actually have data by querying them directly.
"""

import sys
import os
import json
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
    tables = migration.source_tables
    
    print(f"\n{'='*80}")
    print(f"VERIFYING BIGQUERY DATA")
    print(f"{'='*80}")
    print(f"Project: {project_id}")
    print(f"Dataset: {dataset}")
    print(f"Tables: {', '.join(tables)}")
    print(f"{'='*80}\n")
    
    # Create BigQuery client
    credentials = service_account.Credentials.from_service_account_info(credentials_dict)
    client = bigquery.Client(credentials=credentials, project=project_id)
    
    for table in tables:
        print(f"\n{'='*80}")
        print(f"TABLE: {table}")
        print(f"{'='*80}")
        
        table_ref = f"{project_id}.{dataset}.{table}"
        
        # Get table metadata
        table_obj = client.get_table(table_ref)
        print(f"Metadata:")
        print(f"  Rows: {table_obj.num_rows}")
        print(f"  Bytes: {table_obj.num_bytes}")
        print(f"  Created: {table_obj.created}")
        print(f"  Modified: {table_obj.modified}")
        
        # Query with SELECT *
        print(f"\nQuery 1: SELECT * FROM `{table_ref}` LIMIT 10")
        query1 = f"SELECT * FROM `{table_ref}` LIMIT 10"
        job1 = client.query(query1)
        results1 = list(job1.result())
        print(f"  Returned: {len(results1)} rows")
        
        if results1:
            print(f"\n  Sample row:")
            for key, value in dict(results1[0]).items():
                print(f"    {key}: {value}")
        else:
            print(f"  ⚠️  NO ROWS RETURNED!")
        
        # Query with COUNT(*)
        print(f"\nQuery 2: SELECT COUNT(*) as cnt FROM `{table_ref}`")
        query2 = f"SELECT COUNT(*) as cnt FROM `{table_ref}`"
        job2 = client.query(query2)
        results2 = list(job2.result())
        count = results2[0]['cnt'] if results2 else 0
        print(f"  Count: {count}")
        
        # Try to list first few rows with explicit column names
        print(f"\nQuery 3: SELECT * FROM `{table_ref}` WHERE 1=1 LIMIT 10")
        query3 = f"SELECT * FROM `{table_ref}` WHERE 1=1 LIMIT 10"
        job3 = client.query(query3)
        results3 = list(job3.result())
        print(f"  Returned: {len(results3)} rows")
        
        # Check table schema
        print(f"\nSchema:")
        for field in table_obj.schema:
            print(f"  - {field.name}: {field.field_type} ({field.mode})")
        
        print(f"\n{'='*80}")

if __name__ == "__main__":
    main()
