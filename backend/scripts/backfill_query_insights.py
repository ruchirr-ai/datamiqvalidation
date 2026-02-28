"""
Backfill Query Insights for Existing Assessments

This script collects query statistics for assessments that don't have any query data.
It uses the fixed BigQueryAssessmentService to collect query insights retroactively.
"""

import os
import sys
import asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.bigquery_assessment_service import BigQueryAssessmentService
from repositories.assessment_repository import AssessmentRepository
from repositories.connection_repository import ConnectionRepository

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
    sys.exit(1)

# Create database URL
if db_password:
    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
else:
    database_url = f"postgresql://{db_user}@{db_host}:{db_port}/{db_name}"

# Create engine and session
engine = create_engine(database_url)
SessionLocal = sessionmaker(bind=engine)


async def backfill_assessment_query_insights(assessment_id: int, db):
    """Backfill query insights for a single assessment"""
    
    print(f"\n{'='*80}")
    print(f"Processing Assessment ID: {assessment_id}")
    print(f"{'='*80}\n")
    
    try:
        assessment_repo = AssessmentRepository(db)
        connection_repo = ConnectionRepository(db)
        
        # Get assessment
        assessment = assessment_repo.get_by_id(assessment_id)
        if not assessment:
            print(f"❌ Assessment {assessment_id} not found")
            return False
        
        print(f"Assessment: {assessment.name}")
        print(f"Status: {assessment.status}")
        print(f"Project ID: {assessment.project_id}")
        
        # Check if already has query stats
        existing_stats = assessment_repo.get_query_stats(assessment_id)
        if existing_stats:
            print(f"⚠️  Assessment already has {len(existing_stats)} query statistics")
            response = input("Do you want to replace them? (yes/no): ")
            if response.lower() != 'yes':
                print("Skipping...")
                return False
            
            # Delete existing stats
            with engine.connect() as conn:
                conn.execute(
                    text("DELETE FROM assessment_query_stats WHERE assessment_id = :id"),
                    {"id": assessment_id}
                )
                conn.commit()
            print("✓ Deleted existing query statistics")
        
        # Get source connection
        source_conn = connection_repo.get_by_id(assessment.source_connection_id)
        if not source_conn:
            print(f"❌ Source connection {assessment.source_connection_id} not found")
            return False
        
        print(f"Source Connection: {source_conn.name}")
        print(f"Connection Type: {source_conn.database}")
        
        # Verify it's a BigQuery connection
        if source_conn.database != 'bigquery':
            print(f"❌ Source connection is not BigQuery (type: {source_conn.database})")
            return False
        
        # Initialize BigQuery assessment service
        print("\nInitializing BigQuery service...")
        bq_service = BigQueryAssessmentService(source_conn.connection_params)
        print(f"✓ Service initialized with project: {bq_service.project_id}")
        
        # Collect query statistics
        print("\nCollecting query statistics (180 days)...")
        query_stats = await bq_service.collect_query_statistics_detailed()
        
        if not query_stats:
            print("⚠️  No query statistics found")
            print("\nPossible reasons:")
            print("1. No queries executed in BigQuery in last 180 days")
            print("2. Service account lacks permissions")
            print("3. INFORMATION_SCHEMA not accessible")
            return False
        
        print(f"✓ Collected {len(query_stats)} query statistics")
        
        # Store query statistics in database
        print("\nStoring query statistics in database...")
        assessment_repo.bulk_create_query_stats(assessment_id, query_stats)
        print(f"✓ Stored {len(query_stats)} query statistics")
        
        # Show summary
        print(f"\n{'='*80}")
        print("Summary")
        print(f"{'='*80}")
        print(f"Assessment ID: {assessment_id}")
        print(f"Assessment Name: {assessment.name}")
        print(f"Query Statistics: {len(query_stats)}")
        
        if query_stats:
            # Calculate time range
            times = [q['execution_time'] for q in query_stats if q.get('execution_time')]
            if times:
                oldest = min(times)
                newest = max(times)
                days = (newest - oldest).days
                print(f"Time Range: {oldest} to {newest} ({days} days)")
            
            # Calculate unique users
            users = set(q['user_email'] for q in query_stats if q.get('user_email'))
            print(f"Unique Users: {len(users)}")
            
            # Calculate total bytes
            total_bytes = sum(q.get('bytes_scanned', 0) for q in query_stats)
            print(f"Total Bytes Scanned: {total_bytes:,} bytes ({total_bytes / (1024**3):.2f} GB)")
        
        print(f"{'='*80}\n")
        print("✅ Successfully backfilled query insights!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error backfilling assessment {assessment_id}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def backfill_all_assessments():
    """Backfill query insights for all assessments without query stats"""
    
    print("="*80)
    print("Backfill Query Insights for Existing Assessments")
    print("="*80)
    print()
    
    db = SessionLocal()
    
    try:
        # Find assessments without query stats
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT a.id, a.name, a.status, a.project_id, a.started_at,
                       COUNT(q.id) as query_count
                FROM assessments a
                LEFT JOIN assessment_query_stats q ON a.id = q.assessment_id
                WHERE a.status = 'completed'
                GROUP BY a.id, a.name, a.status, a.project_id, a.started_at
                ORDER BY a.started_at DESC
            """))
            
            assessments = result.fetchall()
        
        if not assessments:
            print("No completed assessments found")
            return
        
        print(f"Found {len(assessments)} completed assessment(s):\n")
        
        # Show all assessments
        for idx, row in enumerate(assessments, 1):
            print(f"{idx}. ID: {row[0]}, Name: {row[1]}, Query Stats: {row[5]}")
        
        print()
        
        # Ask which assessments to backfill
        print("Options:")
        print("  - Enter assessment ID(s) separated by commas (e.g., 10,11)")
        print("  - Enter 'all' to backfill all assessments without query stats")
        print("  - Enter 'none' to exit")
        print()
        
        choice = input("Your choice: ").strip().lower()
        
        if choice == 'none':
            print("Exiting...")
            return
        
        # Determine which assessments to process
        if choice == 'all':
            # Only process assessments with 0 query stats
            to_process = [row[0] for row in assessments if row[5] == 0]
            if not to_process:
                print("\n✓ All assessments already have query statistics!")
                return
        else:
            # Parse comma-separated IDs
            try:
                to_process = [int(id.strip()) for id in choice.split(',')]
            except ValueError:
                print("❌ Invalid input. Please enter valid assessment IDs.")
                return
        
        print(f"\nWill process {len(to_process)} assessment(s): {to_process}")
        print()
        
        # Confirm
        confirm = input("Continue? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("Cancelled.")
            return
        
        # Process each assessment
        success_count = 0
        for assessment_id in to_process:
            success = await backfill_assessment_query_insights(assessment_id, db)
            if success:
                success_count += 1
        
        # Final summary
        print(f"\n{'='*80}")
        print("Backfill Complete!")
        print(f"{'='*80}")
        print(f"Successfully backfilled: {success_count}/{len(to_process)} assessments")
        print()
        
        if success_count > 0:
            print("Next steps:")
            print("1. Refresh the frontend")
            print("2. Open the assessment report")
            print("3. Go to Query Insights tab")
            print("4. Verify data is displayed")
        
    finally:
        db.close()


if __name__ == "__main__":
    # Run the backfill
    asyncio.run(backfill_all_assessments())
