#!/usr/bin/env python3
"""
Check actual users in the database for the assessment.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def check_users():
    """Check actual users in assessment query stats."""
    
    print("=" * 80)
    print("CHECKING ACTUAL USERS IN DATABASE")
    print("=" * 80)
    print()
    
    # Get database URL from environment
    db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/datamiq')
    
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        # Get all assessments
        result = conn.execute(text("SELECT id, name, status FROM assessments ORDER BY id"))
        assessments = result.fetchall()
        
        if not assessments:
            print("❌ No assessments found")
            return
        
        print(f"Found {len(assessments)} assessment(s)\n")
        
        for assessment in assessments:
            assessment_id, name, status = assessment
            
            print(f"Assessment ID: {assessment_id}")
            print(f"Name: {name}")
            print(f"Status: {status}")
            print("-" * 80)
            
            # Get query stats for this assessment
            query = text("""
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
            """)
            
            result = conn.execute(query, {"assessment_id": assessment_id})
            users = result.fetchall()
            
            if not users:
                print("  ⚠️  No query stats found for this assessment")
                print()
                continue
            
            print(f"  👥 Total Unique Users: {len(users)}")
            print()
            print("  User Breakdown:")
            print("  " + "-" * 76)
            print(f"  {'User Email':<40} {'Queries':<10} {'Cache Hits':<12} {'Data Scanned'}")
            print("  " + "-" * 76)
            
            for user in users:
                user_email, query_count, total_bytes, total_slots, cache_hits = user
                
                # Format bytes
                if total_bytes:
                    gb = total_bytes / (1024 * 1024 * 1024)
                    if gb >= 1:
                        bytes_str = f"{gb:.2f} GB"
                    else:
                        mb = total_bytes / (1024 * 1024)
                        bytes_str = f"{mb:.2f} MB"
                else:
                    bytes_str = "0 B"
                
                cache_rate = (cache_hits / query_count * 100) if query_count > 0 else 0
                
                print(f"  {user_email:<40} {query_count:<10} {cache_hits}/{query_count} ({cache_rate:.1f}%)  {bytes_str}")
            
            print()
            
            # Check total query count
            total_query = text("""
                SELECT COUNT(*) as total
                FROM assessment_query_stats
                WHERE assessment_id = :assessment_id
            """)
            
            result = conn.execute(total_query, {"assessment_id": assessment_id})
            total_count = result.fetchone()[0]
            
            print(f"  📊 Total Queries in Database: {total_count}")
            
            if len(users) == 1:
                print(f"  ℹ️  This assessment has queries from only 1 user")
                print(f"     This is the actual data - not a bug!")
            else:
                print(f"  ✅ This assessment has queries from {len(users)} different users")
            
            print()
            print("=" * 80)
            print()

if __name__ == "__main__":
    try:
        check_users()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
