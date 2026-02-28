"""
Simple script to check query statistics in database
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database configuration
db_host = os.getenv('APP_DB_HOST', 'localhost')
db_port = os.getenv('APP_DB_PORT', '5432')
db_name = os.getenv('APP_DB_NAME')
db_user = os.getenv('APP_DB_USER')
db_password = os.getenv('APP_DB_PASSWORD', '')

if not db_name or not db_user:
    print("❌ Missing database configuration")
    print("Required: APP_DB_NAME and APP_DB_USER")
    sys.exit(1)

# Create database URL
if db_password:
    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
else:
    database_url = f"postgresql://{db_user}@{db_host}:{db_port}/{db_name}"

# Create engine
engine = create_engine(database_url)

def check_assessments():
    """Check assessments in database"""
    with engine.connect() as conn:
        # Get assessments
        result = conn.execute(text("""
            SELECT id, name, status, project_id, started_at, completed_at
            FROM assessments
            ORDER BY started_at DESC
        """))
        
        assessments = result.fetchall()
        
        if not assessments:
            print("❌ No assessments found in database")
            print()
            print("To create an assessment:")
            print("1. Go to http://localhost:3000/assessments")
            print("2. Click 'Create Assessment'")
            print("3. Select a BigQuery connection")
            print("4. Run the assessment")
            return None
        
        print(f"✅ Found {len(assessments)} assessment(s):")
        print()
        
        for a in assessments:
            print(f"ID: {a[0]}")
            print(f"Name: {a[1]}")
            print(f"Status: {a[2]}")
            print(f"Project ID: {a[3]}")
            print(f"Started: {a[4]}")
            print(f"Completed: {a[5]}")
            print('-' * 60)
        
        return assessments

def check_query_stats(assessment_id):
    """Check query statistics for an assessment"""
    with engine.connect() as conn:
        # Get query stats count
        result = conn.execute(text("""
            SELECT COUNT(*) as count
            FROM assessment_query_stats
            WHERE assessment_id = :assessment_id
        """), {"assessment_id": assessment_id})
        
        count = result.fetchone()[0]
        
        print(f"\n{'='*80}")
        print(f"Query Statistics for Assessment ID: {assessment_id}")
        print(f"{'='*80}\n")
        
        if count == 0:
            print("❌ NO QUERY STATISTICS FOUND!")
            print()
            print("Possible reasons:")
            print("1. Assessment didn't collect query statistics")
            print("2. BigQuery INFORMATION_SCHEMA.JOBS_BY_PROJECT query failed")
            print("3. No queries were executed in BigQuery (last 180 days)")
            print("4. BigQuery region detection failed")
            print("5. Service account lacks permissions")
            print()
            print("To fix:")
            print("- Check backend logs for INFORMATION_SCHEMA errors")
            print("- Verify service account has 'bigquery.jobUser' role")
            print("- Re-run the assessment")
            return
        
        print(f"✅ Found {count} query statistics\n")
        
        # Get unique users
        result = conn.execute(text("""
            SELECT DISTINCT user_email
            FROM assessment_query_stats
            WHERE assessment_id = :assessment_id
            AND user_email IS NOT NULL
            ORDER BY user_email
        """), {"assessment_id": assessment_id})
        
        users = [row[0] for row in result.fetchall()]
        print(f"Unique users: {len(users)}")
        if users:
            for user in users:
                print(f"  - {user}")
        print()
        
        # Get time range
        result = conn.execute(text("""
            SELECT 
                MIN(execution_time) as min_time,
                MAX(execution_time) as max_time
            FROM assessment_query_stats
            WHERE assessment_id = :assessment_id
            AND execution_time IS NOT NULL
        """), {"assessment_id": assessment_id})
        
        row = result.fetchone()
        if row[0] and row[1]:
            print(f"Time range: {row[0]} to {row[1]}")
            days = (row[1] - row[0]).days
            print(f"Duration: {days} days\n")
        
        # Get sample queries
        result = conn.execute(text("""
            SELECT 
                job_id,
                user_email,
                execution_time,
                bytes_scanned,
                slot_milliseconds,
                cache_hit,
                query_text
            FROM assessment_query_stats
            WHERE assessment_id = :assessment_id
            ORDER BY execution_time DESC
            LIMIT 5
        """), {"assessment_id": assessment_id})
        
        print("Sample Query Stats (first 5):")
        print('-' * 80)
        
        for i, row in enumerate(result.fetchall(), 1):
            print(f"\n{i}. Job ID: {row[0]}")
            print(f"   User: {row[1]}")
            print(f"   Execution Time: {row[2]}")
            print(f"   Bytes Scanned: {row[3]:,} bytes")
            print(f"   Slot Milliseconds: {row[4]:,} ms")
            print(f"   Cache Hit: {row[5]}")
            if row[6]:
                print(f"   Query: {row[6][:100]}...")
        
        # User breakdown
        result = conn.execute(text("""
            SELECT 
                user_email,
                COUNT(*) as query_count,
                SUM(bytes_scanned) as total_bytes,
                SUM(slot_milliseconds) as total_slots,
                SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END) as cache_hits
            FROM assessment_query_stats
            WHERE assessment_id = :assessment_id
            GROUP BY user_email
            ORDER BY query_count DESC
        """), {"assessment_id": assessment_id})
        
        print(f"\n\n📈 User Breakdown")
        print(f"{'='*80}")
        print(f"\n{'User':<40} {'Queries':<10} {'Bytes Scanned':<20} {'Cache Hit %':<12}")
        print(f"{'-'*80}")
        
        for row in result.fetchall():
            user = row[0] or 'Unknown'
            query_count = row[1]
            total_bytes = row[2] or 0
            cache_hits = row[4] or 0
            cache_pct = (cache_hits / query_count * 100) if query_count > 0 else 0
            bytes_gb = total_bytes / (1024**3)
            print(f"{user:<40} {query_count:<10} {bytes_gb:>15.2f} GB {cache_pct:>10.1f}%")
        
        print(f"\n{'='*80}")
        print(f"✅ Query Insights and User Insights should work correctly!")
        print(f"{'='*80}\n")

if __name__ == "__main__":
    # Check assessments
    assessments = check_assessments()
    
    if not assessments:
        sys.exit(1)
    
    # If assessment ID provided, check that one
    if len(sys.argv) > 1:
        assessment_id = int(sys.argv[1])
    else:
        # Use the first assessment
        assessment_id = assessments[0][0]
        print(f"\nUsing assessment ID: {assessment_id}")
    
    # Check query stats
    check_query_stats(assessment_id)
