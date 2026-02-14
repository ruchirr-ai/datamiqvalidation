"""
Direct test of BigQuery export to GCS
Tests the actual BigQuery API call without going through the full migration flow
"""

import json
import sys
from services.bq_redshift_migration.bigquery_exporter import BigQueryExporter

# Service account credentials from database
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

# Migration configuration from database
project_id = "assessiq-484512"
dataset = "sales_analytics"  # FIXED: Was "analytics", should be "sales_analytics"
tables = ["customers", "orders"]  # Testing with 2 tables first
gcs_bucket = "bq_data_transfer_rs"
gcs_path = ""  # Empty - files will go directly to bucket/dataset/table/
export_format = "AVRO"
compression = "SNAPPY"

def main():
    print("=" * 80)
    print("DIRECT BIGQUERY EXPORT TEST")
    print("=" * 80)
    
    try:
        # Parse credentials
        print("\n1. Parsing service account credentials...")
        credentials_dict = json.loads(credentials_json)
        print(f"   ✓ Project ID: {credentials_dict['project_id']}")
        print(f"   ✓ Service Account: {credentials_dict['client_email']}")
        
        # Initialize exporter
        print("\n2. Initializing BigQuery exporter...")
        exporter = BigQueryExporter(
            credentials_dict=credentials_dict,
            project_id=project_id
        )
        print("   ✓ Exporter initialized")
        
        # Test export
        print(f"\n3. Starting export test...")
        print(f"   Dataset: {dataset}")
        print(f"   Tables: {tables}")
        print(f"   GCS Bucket: gs://{gcs_bucket}")
        print(f"   GCS Path: {gcs_path}")
        print(f"   Format: {export_format}")
        print(f"   Compression: {compression}")
        
        print("\n4. Calling export_tables()...")
        results = exporter.export_tables(
            dataset=dataset,
            tables=tables,
            gcs_bucket=gcs_bucket,
            gcs_path=gcs_path,
            export_format=export_format,
            compression=compression
        )
        
        # Display results
        print("\n5. Export Results:")
        print("=" * 80)
        
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        print(f"\n   Total tables: {len(results)}")
        print(f"   Successful: {len(successful)}")
        print(f"   Failed: {len(failed)}")
        
        if successful:
            print("\n   ✓ Successful exports:")
            for r in successful:
                print(f"      - {r['table']}")
                print(f"        Job ID: {r.get('job_id', 'N/A')}")
                print(f"        Destination: {r.get('destination_uri', 'N/A')}")
        
        if failed:
            print("\n   ✗ Failed exports:")
            for r in failed:
                print(f"      - {r['table']}")
                print(f"        Error: {r.get('error', 'Unknown error')}")
        
        print("\n" + "=" * 80)
        
        if len(successful) == len(results):
            print("✓ ALL EXPORTS SUCCESSFUL!")
            print("\nCheck GCP Console:")
            print(f"  - BigQuery Jobs: https://console.cloud.google.com/bigquery?project={project_id}")
            print(f"  - GCS Bucket: https://console.cloud.google.com/storage/browser/{gcs_bucket}")
            return 0
        else:
            print("✗ SOME EXPORTS FAILED")
            return 1
            
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
