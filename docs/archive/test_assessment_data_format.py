"""
Quick test to check assessment data format
"""

from database import db_instance
from repositories.assessment_repository import AssessmentRepository
import json


def test_data_format(assessment_id: int):
    """Test what format the data is in"""
    db = db_instance.SessionLocal()
    
    try:
        repo = AssessmentRepository(db)
        
        print(f"\n=== Testing Assessment {assessment_id} Data Format ===\n")
        
        # Get one table
        tables = repo.get_tables(assessment_id)
        if tables:
            table = tables[0]
            print("SAMPLE TABLE:")
            print(f"  Table Name: {table.table_name}")
            print(f"  Partitioning Columns:")
            print(f"    Type: {type(table.partitioning_columns)}")
            print(f"    Value: {table.partitioning_columns}")
            print(f"    Repr: {repr(table.partitioning_columns)}")
            
            if table.partitioning_columns:
                print(f"    Is List: {isinstance(table.partitioning_columns, list)}")
                if isinstance(table.partitioning_columns, list):
                    print(f"    Length: {len(table.partitioning_columns)}")
                    print(f"    Items: {[repr(item) for item in table.partitioning_columns]}")
            
            print(f"\n  Clustering Columns:")
            print(f"    Type: {type(table.clustering_columns)}")
            print(f"    Value: {table.clustering_columns}")
            print(f"    Repr: {repr(table.clustering_columns)}")
        
        # Get one column
        columns = repo.get_columns(assessment_id)
        if columns:
            col = columns[0]
            print(f"\nSAMPLE COLUMN:")
            print(f"  Column Name: {col.column_name}")
            print(f"  Policy Tags:")
            print(f"    Type: {type(col.policy_tags)}")
            print(f"    Value: {col.policy_tags}")
            print(f"    Repr: {repr(col.policy_tags)}")
        
        # Get one query
        queries = repo.get_query_stats(assessment_id)
        if queries:
            query = queries[0]
            print(f"\nSAMPLE QUERY:")
            print(f"  Job ID: {query.job_id}")
            print(f"  Execution Time: {query.execution_time}")
            print(f"  User Email: {query.user_email}")
            print(f"  Bytes Scanned: {query.bytes_scanned}")
            print(f"  Slot MS: {query.slot_milliseconds}")
            print(f"  Cache Hit: {query.cache_hit}")
            print(f"  Referenced Tables:")
            print(f"    Type: {type(query.referenced_tables)}")
            print(f"    Value: {query.referenced_tables}")
            print(f"    Repr: {repr(query.referenced_tables)}")
            
            if query.query_text:
                print(f"  Query Text (first 100 chars): {query.query_text[:100]}")
        
        # Test JSON serialization
        print(f"\n=== Testing JSON Serialization ===\n")
        
        if tables:
            table_dict = {
                "table_name": tables[0].table_name,
                "partitioning_columns": tables[0].partitioning_columns or [],
                "clustering_columns": tables[0].clustering_columns or [],
            }
            print("Table as dict:")
            print(json.dumps(table_dict, indent=2, default=str))
        
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python test_assessment_data_format.py <assessment_id>")
        sys.exit(1)
    
    assessment_id = int(sys.argv[1])
    test_data_format(assessment_id)
