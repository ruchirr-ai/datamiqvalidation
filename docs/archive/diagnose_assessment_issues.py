"""
Diagnostic script to identify assessment report issues
"""

import asyncio
from sqlalchemy.orm import Session
from database import db_instance
from repositories.assessment_repository import AssessmentRepository


def diagnose_duplicates(db: Session, assessment_id: int):
    """Check for duplicate records"""
    print(f"\n=== Checking for Duplicates in Assessment {assessment_id} ===\n")
    
    repo = AssessmentRepository(db)
    
    # Check tables
    tables = repo.get_tables(assessment_id)
    table_names = [f"{t.dataset_name}.{t.table_name}" for t in tables]
    duplicates = [name for name in table_names if table_names.count(name) > 1]
    
    if duplicates:
        print(f"❌ DUPLICATE TABLES FOUND: {len(set(duplicates))} unique duplicates")
        for dup in set(duplicates):
            count = table_names.count(dup)
            print(f"   - {dup}: appears {count} times")
    else:
        print("✅ No duplicate tables found")
    
    # Check columns
    columns = repo.get_columns(assessment_id)
    print(f"\n📊 Total columns: {len(columns)}")
    
    # Check views
    views = repo.get_views(assessment_id)
    view_names = [v.view_name for v in views]
    view_duplicates = [name for name in view_names if view_names.count(name) > 1]
    
    if view_duplicates:
        print(f"❌ DUPLICATE VIEWS FOUND: {len(set(view_duplicates))} unique duplicates")
    else:
        print("✅ No duplicate views found")
    
    # Check query stats
    query_stats = repo.get_query_stats(assessment_id)
    print(f"\n📊 Total query stats: {len(query_stats)}")
    
    return {
        "duplicate_tables": len(set(duplicates)),
        "duplicate_views": len(set(view_duplicates)),
        "total_tables": len(tables),
        "total_columns": len(columns),
        "total_views": len(views),
        "total_queries": len(query_stats)
    }


def diagnose_array_fields(db: Session, assessment_id: int):
    """Check array field formats"""
    print(f"\n=== Checking Array Field Formats ===\n")
    
    repo = AssessmentRepository(db)
    tables = repo.get_tables(assessment_id)
    
    if not tables:
        print("❌ No tables found")
        return
    
    # Check first table
    table = tables[0]
    print(f"Sample Table: {table.dataset_name}.{table.table_name}")
    print(f"  Partitioning Columns Type: {type(table.partitioning_columns)}")
    print(f"  Partitioning Columns Value: {table.partitioning_columns}")
    print(f"  Clustering Columns Type: {type(table.clustering_columns)}")
    print(f"  Clustering Columns Value: {table.clustering_columns}")
    
    # Check columns
    columns = repo.get_columns(assessment_id)
    if columns:
        col = columns[0]
        print(f"\nSample Column: {col.column_name}")
        print(f"  Policy Tags Type: {type(col.policy_tags)}")
        print(f"  Policy Tags Value: {col.policy_tags}")


def diagnose_query_insights(db: Session, assessment_id: int):
    """Check query insights data"""
    print(f"\n=== Checking Query Insights Data ===\n")
    
    repo = AssessmentRepository(db)
    query_stats = repo.get_query_stats(assessment_id)
    
    if not query_stats:
        print("❌ No query stats found")
        return
    
    # Check first query
    query = query_stats[0]
    print(f"Sample Query:")
    print(f"  Job ID: {query.job_id}")
    print(f"  Execution Time: {query.execution_time}")
    print(f"  Query Text Length: {len(query.query_text) if query.query_text else 0}")
    print(f"  Bytes Scanned: {query.bytes_scanned}")
    print(f"  Slot Milliseconds: {query.slot_milliseconds}")
    print(f"  Cache Hit: {query.cache_hit}")
    print(f"  Referenced Tables Type: {type(query.referenced_tables)}")
    print(f"  Referenced Tables Value: {query.referenced_tables}")
    print(f"  User Email: {query.user_email}")
    
    # Check for missing data
    missing_fields = []
    if not query.job_id:
        missing_fields.append("job_id")
    if not query.execution_time:
        missing_fields.append("execution_time")
    if not query.user_email:
        missing_fields.append("user_email")
    
    if missing_fields:
        print(f"\n❌ Missing fields: {', '.join(missing_fields)}")
    else:
        print(f"\n✅ All required fields present")


def diagnose_security_data(db: Session, assessment_id: int):
    """Check security data"""
    print(f"\n=== Checking Security Data ===\n")
    
    repo = AssessmentRepository(db)
    security_policies = repo.get_security_policies(assessment_id)
    
    print(f"Total Security Policies: {len(security_policies)}")
    
    if not security_policies:
        print("❌ No security policies found - this data may not be collected yet")
    else:
        policy = security_policies[0]
        print(f"\nSample Policy:")
        print(f"  Type: {policy.security_type}")
        print(f"  Table: {policy.table_name}")
        print(f"  Policy Name: {policy.policy_name}")


def main():
    """Run all diagnostics"""
    print("=" * 80)
    print("ASSESSMENT REPORT DIAGNOSTIC TOOL")
    print("=" * 80)
    
    # Get assessment ID
    assessment_id = input("\nEnter Assessment ID to diagnose: ")
    
    try:
        assessment_id = int(assessment_id)
    except ValueError:
        print("❌ Invalid assessment ID")
        return
    
    db = db_instance.SessionLocal()
    
    try:
        # Run diagnostics
        stats = diagnose_duplicates(db, assessment_id)
        diagnose_array_fields(db, assessment_id)
        diagnose_query_insights(db, assessment_id)
        diagnose_security_data(db, assessment_id)
        
        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Total Tables: {stats['total_tables']}")
        print(f"Duplicate Tables: {stats['duplicate_tables']}")
        print(f"Total Columns: {stats['total_columns']}")
        print(f"Total Views: {stats['total_views']}")
        print(f"Duplicate Views: {stats['duplicate_views']}")
        print(f"Total Queries: {stats['total_queries']}")
        
        if stats['duplicate_tables'] > 0 or stats['duplicate_views'] > 0:
            print("\n⚠️  DUPLICATES DETECTED - Need to fix data collection")
        else:
            print("\n✅ No duplicates detected")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
