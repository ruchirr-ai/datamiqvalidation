"""
Test script to verify the BigQueryAssessmentService fix is working
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import json

# Load environment variables
load_dotenv()

# Get database configuration
db_host = os.getenv('APP_DB_HOST', 'localhost')
db_port = os.getenv('APP_DB_PORT', '5432')
db_name = os.getenv('APP_DB_NAME')
db_user = os.getenv('APP_DB_USER')
db_password = os.getenv('APP_DB_PASSWORD', '')

if db_password:
    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
else:
    database_url = f"postgresql://{db_user}@{db_host}:{db_port}/{db_name}"

engine = create_engine(database_url)

print("=" * 80)
print("Testing BigQueryAssessmentService Fix")
print("=" * 80)
print()

# Get BigQuery connection
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT id, name, database, connection_params
        FROM connections
        WHERE database = 'bigquery'
        AND is_active = true
        ORDER BY created_at DESC
        LIMIT 1
    """))
    
    row = result.fetchone()
    if not row:
        print("❌ No BigQuery connection found")
        sys.exit(1)
    
    connection_params = row[3]
    print(f"✓ Found connection: {row[1]}")
    print(f"  Database field: {row[2]}")

# Test the fix
print()
print("Testing BigQueryAssessmentService initialization...")
print()

try:
    from services.bigquery_assessment_service import BigQueryAssessmentService
    
    # Initialize service (this will test the fix)
    service = BigQueryAssessmentService(connection_params)
    
    print(f"✓ Service initialized successfully")
    print(f"  Project ID extracted: {service.project_id}")
    print()
    
    if service.project_id == 'bigquery':
        print("❌ FIX NOT WORKING - Still using 'bigquery' as project_id")
        print("   Expected: assessiq-484512 (or similar)")
        print()
        print("Action required:")
        print("1. Restart the backend server")
        print("2. Run this test again")
    else:
        print("✅ FIX IS WORKING - Correct project_id extracted from credentials")
        print()
        print("Next steps:")
        print("1. Go to http://localhost:3000/assessments")
        print("2. Create a new assessment")
        print("3. Wait for completion")
        print("4. Check Query Insights tab")
    
except Exception as e:
    print(f"❌ Error initializing service: {e}")
    import traceback
    traceback.print_exc()
    print()
    print("This might mean:")
    print("1. The fix hasn't been loaded yet (restart backend)")
    print("2. There's an issue with the connection parameters")

print()
print("=" * 80)
