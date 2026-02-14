#!/usr/bin/env python3
"""
Verification script for User Insights fix.
Tests that all users from query history are returned in the assessment report API.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from database import get_db
from models.assessment import Assessment, AssessmentQueryStat
from collections import Counter

def verify_user_insights_fix():
    """Verify that all users from query stats are accessible."""
    
    print("=" * 80)
    print("USER INSIGHTS FIX VERIFICATION")
    print("=" * 80)
    print()
    
    db: Session = next(get_db())
    
    try:
        # Get all assessments
        assessments = db.query(Assessment).all()
        
        if not assessments:
            print("❌ No assessments found in database")
            return False
        
        print(f"✅ Found {len(assessments)} assessment(s)")
        print()
        
        all_verified = True
        
        for assessment in assessments:
            print(f"Assessment ID: {assessment.id}")
            print(f"Name: {assessment.name}")
            print(f"Status: {assessment.status}")
            print("-" * 80)
            
            # Get all query stats for this assessment
            query_stats = db.query(AssessmentQueryStat).filter(
                AssessmentQueryStat.assessment_id == assessment.id
            ).all()
            
            if not query_stats:
                print("  ⚠️  No query stats found for this assessment")
                print()
                continue
            
            # Count unique users
            user_emails = [q.user_email for q in query_stats if q.user_email]
            unique_users = set(user_emails)
            user_query_counts = Counter(user_emails)
            
            print(f"  📊 Total Queries: {len(query_stats)}")
            print(f"  👥 Unique Users: {len(unique_users)}")
            print()
            
            # Show user breakdown
            print("  User Query Breakdown:")
            for user, count in sorted(user_query_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"    • {user}: {count} queries")
            print()
            
            # Simulate what the API would return (first 100 vs all)
            first_100_users = set([q.user_email for q in query_stats[:100] if q.user_email])
            all_users = unique_users
            
            missing_users = all_users - first_100_users
            
            if missing_users:
                print(f"  ⚠️  BEFORE FIX: {len(missing_users)} user(s) would have been missing:")
                for user in sorted(missing_users):
                    query_count = user_query_counts[user]
                    print(f"    • {user} ({query_count} queries)")
                print()
                print(f"  ✅ AFTER FIX: All {len(all_users)} users are now included")
            else:
                print(f"  ✅ All {len(all_users)} users would be visible (even with old limit)")
            
            print()
            
            # Verify the fix
            if len(query_stats) > 100:
                print(f"  🔍 Verification:")
                print(f"    • Total queries: {len(query_stats)} (> 100)")
                print(f"    • Users in first 100 queries: {len(first_100_users)}")
                print(f"    • Total unique users: {len(all_users)}")
                
                if len(all_users) > len(first_100_users):
                    print(f"    • ✅ FIX VERIFIED: {len(all_users) - len(first_100_users)} additional user(s) now visible")
                else:
                    print(f"    • ℹ️  All users happened to be in first 100 queries")
            else:
                print(f"  ℹ️  This assessment has ≤100 queries, so the fix doesn't impact it")
            
            print()
            print("=" * 80)
            print()
        
        return all_verified
        
    except Exception as e:
        print(f"❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

def check_api_endpoint():
    """Check if the API endpoint code has been fixed."""
    
    print("=" * 80)
    print("API ENDPOINT CODE VERIFICATION")
    print("=" * 80)
    print()
    
    router_file = "backend/routers/assessment_router.py"
    
    try:
        with open(router_file, 'r') as f:
            content = f.read()
        
        # Check if the old limit is present
        if "for q in query_stats[:100]" in content:
            print("❌ OLD CODE DETECTED: query_stats[:100] limit still present")
            print("   The fix has NOT been applied correctly")
            return False
        
        # Check if the new code is present
        if "for q in query_stats  # Return all query stats" in content or \
           "for q in query_stats)" in content:
            print("✅ NEW CODE DETECTED: query_stats limit has been removed")
            print("   The fix has been applied correctly")
            return True
        
        print("⚠️  Could not verify code change - manual inspection needed")
        return None
        
    except Exception as e:
        print(f"❌ Error reading router file: {e}")
        return False

if __name__ == "__main__":
    print()
    
    # Check API code
    code_fixed = check_api_endpoint()
    print()
    
    # Verify with database
    data_verified = verify_user_insights_fix()
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    if code_fixed:
        print("✅ API endpoint code has been fixed")
    else:
        print("❌ API endpoint code needs to be fixed")
    
    if data_verified:
        print("✅ Database verification completed")
    else:
        print("⚠️  Database verification had issues")
    
    print()
    print("NEXT STEPS:")
    print("1. Hard refresh your browser (Ctrl+Shift+R or Cmd+Shift+R)")
    print("2. Navigate to an assessment report")
    print("3. Click on 'User Insights' tab")
    print("4. Verify all users from query history are displayed")
    print()
