"""
List all datasets in BigQuery project to see what's available
"""

import json
from google.cloud import bigquery
from google.oauth2 import service_account

# Service account credentials
credentials_json = """{
  "type": "service_account",
  "project_id": "assessiq-484512",
  "private_key_id": "91c710ed87399b87a5b8eae02614e96828cdd0f1",
  "private_key": "-----BEGIN PRIVATE KEY-----\\nMIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQC0MRBegk/Oc/Qk\\ngNJHP2mIPOKcKijJTGeJV5Dse0hK1hJ2XlQ3rgAr1vilDiRlQ8YFwtJoDENRT/Pl\\n9ZBiNcNFFTkIHvA4a+NeYhtdQ6+TFYY+BOjlWudOOITnvnhti/QsImaNW97QQtVR\\nE/trX/zH/8ZozaLsIhfYTtQiOq8f1QdR8DAX6Qe72/bfmQU/HD7wimHyvvnXtQkY\\n/GNdaRT9AVcfZB77Djv4yFtsVktbV5ebIp7GT+8/ovJDD698HcIXIQuecn/Fphwa\\n+Aqrue6OJ6ld4GqTTtao5Suv/22hmfcoh+/eoSsuH1G5a5FujC8pcw04dDixXqzY\\ndvaFBE2pAgMBAAECggEACAMOeUVOCx34ww6/Ss+0/4vFf7AYNCsjh2XPWdR5eGpg\\nU8cJ85fXBhv+3kfsslv7GBJ7jIjPDXSCobzzeIpvbkjtSkEl6TxS1cWC9fime+G/\\nIE7TlC8gjcfRkQRVEnngl33IFYz6MURne71ptnKEKNhkmBBcqCcz7DhFEmiNlNqu\\n3fecadPWhrr5uZX0171VRUADcHIVPfnSSfZf4A4+VmiE3YaISo5OoMqFNWsFVQ2T\\nedC9nxzouwSWlBYv4BqCdvXsnT5/Rq8pFIpSUCP/OEUQYxYJkpO0PMe2bofMXwRo\\nKBWgC8JDQj4EwVQ89s7Q9eYKfpiZpXTYT2mi+aeTCQKBgQDlxqsPTaTMGK0ozUOO\\nzIJCqnSNwYqWTzy7mfJAFLY8aOg/UOj7Ip0CvDrWObnvaJbR1hyVsXi6TbXeluAA\\nyJUlhZOaaznuCchcnoR5Pk0x4CzbwlIlirpWFN1GstUmJu60tCEkHvflI+enhi5L\\nQzPZdlegK1sE5CHgoD3rF5CPcwKBgQDIwbI03qBFQE43RMnqnUgxz+ZUEGPbLpeN\\n/5ilyzxjJrw1rBiWIgJtJfY9VyMOztRnpWC/eXjeJ2ZZBCV+tW67tvF0b5C6Crf+\\nEBhNkLbDry9H4lOz2TQlK33cW6xlc+yEptj94NeR5kL/eUH+CfsOehdZqvWwXto/\\nolo38VtvcwKBgQCgiPkirACjh+oTQ7Ybos6vfSAJmlsVQS8RczFJjC72beU1t3XP\\nYBOKwa/p1FMP7WbSHGHEREYxA/I5HfhLE9kAah8CGEBVCwitjSLJAro0SoeM0mtK\\nR26Ajfs7Vd6N1U2ZevBcqDZSJY/H/3uAoecr2/7ErQXemPUCV3JrOf+J+QKBgQCT\\npJAw/cGU7JQZZYex+fYMXD+id2NY4M0o618SH4PLz8L/Hg/+6ggqyY5s0lbAHzBr\\nAV9DskxH5WYJ9Vi19Sz49LRi02H20Mc8HA4jjVg8VexJy5OPYyBMbc3kb6879aNu\\nc16GaANiE5wWUtFLyX9PyE6/7VE/YqLTxczf86sxLQKBgQDUnRtjr10oWvblhMlt\\njY91/dcjpzRZpPXQknl0caUW3uJ4WN4UilqZ1H+NEkh90yRx/ikIFx0+QYTnJIrh\\njEFGSJEVzLvve+UVc+SGWiyG4xz2gk8vkCY5pEwsCtnJJWP4wgHNtoqb7+QKUUVh\\np+DiKy+u2KjaiKZRYsJb1bT4gA==\\n-----END PRIVATE KEY-----\\n",
  "client_email": "assesiq@assessiq-484512.iam.gserviceaccount.com",
  "client_id": "101208713718791691757",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/assesiq%40assessiq-484512.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}"""

project_id = "assessiq-484512"

print("=" * 80)
print("LISTING BIGQUERY DATASETS")
print("=" * 80)

try:
    # Parse credentials
    print("\n1. Parsing credentials...")
    credentials_dict = json.loads(credentials_json)
    credentials = service_account.Credentials.from_service_account_info(credentials_dict)
    print(f"   ✓ Service Account: {credentials_dict['client_email']}")
    
    # Create client
    print("\n2. Creating BigQuery client...")
    client = bigquery.Client(credentials=credentials, project=project_id)
    print(f"   ✓ Project: {project_id}")
    
    # List datasets
    print("\n3. Listing datasets...")
    datasets = list(client.list_datasets())
    
    if datasets:
        print(f"\n   Found {len(datasets)} dataset(s):\n")
        for dataset in datasets:
            print(f"   📁 {dataset.dataset_id}")
            
            # List tables in each dataset
            try:
                tables = list(client.list_tables(dataset.dataset_id))
                if tables:
                    print(f"      Tables ({len(tables)}):")
                    for table in tables:
                        print(f"        - {table.table_id}")
                else:
                    print(f"      (No tables)")
            except Exception as e:
                print(f"      Error listing tables: {e}")
            print()
    else:
        print("\n   ⚠️  No datasets found in this project")
        print("\n   This could mean:")
        print("   1. No datasets have been created yet")
        print("   2. Service account doesn't have permission to list datasets")
        print("   3. Wrong project ID")
    
    print("=" * 80)
    
except Exception as e:
    print(f"\n✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
