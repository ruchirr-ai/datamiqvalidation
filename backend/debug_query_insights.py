"""
Debug script to check Query Insights and User Insights data
"""

import os
import sys
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

load_dotenv()

from database import db_instance
from repositories.assessment_repository import AssessmentRepository

def debug_query_insights(assessment_id: int):
    """Debug query insights data for an assessment"""
    
    with db_instance.get_session() as db:
        repo = AssessmentRepository(db)
        
        # Get assessment
        assessment = repo.get_by_id(assessment_id)  # Fixed: use get_by_id instead of get_assessment
        if not assessment:
            print(f"❌ Assessment {assessment_id} not found")
            return
        
        print(f"\n{'='*80}")
        print(f"Assessment: {assessment.name} (ID: {assessment_id})")
        print(f"Status: {assessment.status}")
        print(f"Project ID: {assessment.project_id}")
        print(f"{'='*80}\n")
        
        # Get query stats
        query_stats = repo.get_query_stats(assessment_id)
        
        print(f"📊 Query Statistics")
        print(f"{'='*80}")
        print(f"Total query_stats records: {len(query_stats)}")
        
        if len(query_stats) == 0:
            print("\n❌ NO QUERY STATS FOUND!")
            print("\nPossible reasons:")
            print("1. Assessment didn't collect query statistics")
            print("2. BigQuery INFORMATION_SCHEMA.JOBS_BY_PROJECT query failed")
            print("3. No queries were executed in the last 180 days")
            print("4. Region detection failed (check assessment logs)")
            print("\nTo fix:")
            print("- Re-run the assessment")
            print("- Check backend logs for INFORMATION_SCHEMA errors")
            print("- Verify BigQuery has query history")
            return
        
        print(f"\n✅ Found {len(query_stats)} query statistics\n")
        
        # Analyze query stats
        unique_users = set(q.user_email for q in query_stats if q.user_email)
        print(f"Unique users: {len(unique_users)}")
        print(f"Users: {', '.join(sorted(unique_users))}\n")
        
        # Time range
        execution_times = [q.execution_time for q in query_stats if q.execution_time]
        if execution_times:
            min_time = min(execution_times)
            max_time = max(execution_times)
            print(f"Time range: {min_time} to {max_time}")
            print(f"Duration: {(max_time - min_time).days} days\n")
        
        # Sample queries
        print(f"Sample Query Stats (first 5):")
        print(f"{'-'*80}")
        for i, q in enumerate(query_stats[:5], 1):
            print(f"\n{i}. Job ID: {q.job_id}")
            print(f"   User: {q.user_email}")
            print(f"   Execution Time: {q.execution_time}")
            print(f"   Bytes Scanned: {q.bytes_scanned:,} bytes")
            print(f"   Slot Milliseconds: {q.slot_milliseconds:,} ms")
            print(f"   Cache Hit: {q.cache_hit}")
            print(f"   Referenced Tables: {len(q.referenced_tables or [])} tables")
            if q.query_text:
                print(f"   Query: {q.query_text[:100]}...")
        
        # User breakdown
        print(f"\n\n📈 User Breakdown")
        print(f"{'='*80}")
        user_stats = {}
        for q in query_stats:
            user = q.user_email or 'Unknown'
            if user not in user_stats:
                user_stats[user] = {
                    'count': 0,
                    'bytes': 0,
                    'slots': 0,
                    'cache_hits': 0
                }
            user_stats[user]['count'] += 1
            user_stats[user]['bytes'] += q.bytes_scanned or 0
            user_stats[user]['slots'] += q.slot_milliseconds or 0
            if q.cache_hit:
                user_stats[user]['cache_hits'] += 1
        
        # Sort by query count
        sorted_users = sorted(user_stats.items(), key=lambda x: x[1]['count'], reverse=True)
        
        print(f"\n{'User':<40} {'Queries':<10} {'Bytes Scanned':<20} {'Cache Hit %':<12}")
        print(f"{'-'*80}")
        for user, stats in sorted_users:
            cache_pct = (stats['cache_hits'] / stats['count'] * 100) if stats['count'] > 0 else 0
            bytes_gb = stats['bytes'] / (1024**3)
            print(f"{user:<40} {stats['count']:<10} {bytes_gb:>15.2f} GB {cache_pct:>10.1f}%")
        
        print(f"\n{'='*80}")
        print(f"✅ Query Insights and User Insights should work correctly!")
        print(f"{'='*80}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_query_insights.py <assessment_id>")
        print("\nExample: python debug_query_insights.py 1")
        sys.exit(1)
    
    assessment_id = int(sys.argv[1])
    debug_query_insights(assessment_id)
