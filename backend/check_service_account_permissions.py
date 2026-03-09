"""
Check service account permissions for BigQuery RLS access
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from database import db_instance
from repositories.connection_repository import ConnectionRepository
import json


def check_service_account():
    """Check service account details and provide permission fix commands"""
    db = db_instance.SessionLocal()
    
    try:
        conn_repo = ConnectionRepository(db)
        connection = conn_repo.get_by_id(6)  # bq_demo connection
        
        if not connection:
            print("Connection not found")
            return
        
        print("="*70)
        print("SERVICE ACCOUNT INFORMATION")
        print("="*70)
        
        # Get credentials
        connection_params = connection.connection_params
        credentials_json = connection_params.get('credentials_json')
        if isinstance(credentials_json, str):
            credentials_json = json.loads(credentials_json)
        
        service_account_email = credentials_json.get('client_email')
        project_id = credentials_json.get('project_id')
        
        print(f"\nService Account Email: {service_account_email}")
        print(f"Project ID: {project_id}")
        
        print("\n" + "="*70)
        print("REQUIRED PERMISSIONS FOR RLS POLICIES")
        print("="*70)
        print("""
The service account needs these permissions to read RLS policies:
  ✓ bigquery.rowAccessPolicies.list
  ✓ bigquery.rowAccessPolicies.get
  ✓ bigquery.tables.get
  ✓ bigquery.tables.getData
""")
        
        print("="*70)
        print("FIX: GRANT PERMISSIONS")
        print("="*70)
        
        print("\n📋 Option 1: Grant BigQuery Metadata Viewer Role (Recommended)")
        print("-" * 70)
        print(f"""
gcloud projects add-iam-policy-binding {project_id} \\
  --member="serviceAccount:{service_account_email}" \\
  --role="roles/bigquery.metadataViewer"
""")
        
        print("\n📋 Option 2: Create Custom Role with Minimal Permissions")
        print("-" * 70)
        print(f"""
# Step 1: Create custom role
gcloud iam roles create bigqueryRLSReader \\
  --project={project_id} \\
  --title="BigQuery RLS Reader" \\
  --description="Can read Row-Level Security policies" \\
  --permissions="bigquery.rowAccessPolicies.list,bigquery.rowAccessPolicies.get,bigquery.tables.get,bigquery.tables.getData"

# Step 2: Grant role to service account
gcloud projects add-iam-policy-binding {project_id} \\
  --member="serviceAccount:{service_account_email}" \\
  --role="projects/{project_id}/roles/bigqueryRLSReader"
""")
        
        print("\n📋 Option 3: Test Access (After Granting Permissions)")
        print("-" * 70)
        print(f"""
bq query --use_legacy_sql=false \\
  --impersonate_service_account={service_account_email} \\
  "SELECT COUNT(*) as policy_count FROM `{project_id}.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES`"
""")
        
        print("\n" + "="*70)
        print("AFTER GRANTING PERMISSIONS")
        print("="*70)
        print("""
1. Wait 1-2 minutes for IAM changes to propagate
2. Run the backfill script:
   cd backend
   python scripts/backfill_security_metadata.py
3. Check the assessment report in the UI
""")
        
        print("\n" + "="*70)
        print("ALTERNATIVE: MANUAL EXPORT")
        print("="*70)
        print(f"""
If you cannot grant permissions, export RLS policies manually:

1. Run this query in BigQuery Console (with your user account):

   SELECT
       table_schema,
       table_name,
       policy_name,
       filter_predicate,
       grantee_list,
       ddl
   FROM `{project_id}.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES`
   ORDER BY table_schema, table_name;

2. Export results as JSON
3. See RLS_POLICIES_PERMISSIONS_FIX.md for import instructions
""")
        
    finally:
        db.close()


if __name__ == "__main__":
    check_service_account()
