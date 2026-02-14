"""
Diagnostic script to check how partitioning_columns and clustering_columns are stored and retrieved.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import json

# Load environment variables from backend/.env
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

# Database connection using the same variables as database.py
db_host = os.getenv('APP_DB_HOST', 'localhost')
db_port = os.getenv('APP_DB_PORT', '5432')
db_name = os.getenv('APP_DB_NAME')
db_user = os.getenv('APP_DB_USER')
db_password = os.getenv('APP_DB_PASSWORD', '')

if not db_name or not db_user:
    print("ERROR: Missing required database environment variables: APP_DB_NAME and APP_DB_USER")
    sys.exit(1)

# Construct database URL
if db_password:
    DATABASE_URL = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
else:
    DATABASE_URL = f"postgresql://{db_user}@{db_host}:{db_port}/{db_name}"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def diagnose_array_columns():
    """Check how array columns are stored and retrieved"""
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("DIAGNOSING ARRAY COLUMNS IN ASSESSMENT TABLES")
        print("=" * 80)
        
        # Get a sample table with partitioning or clustering columns
        query = text("""
            SELECT 
                id,
                table_name,
                partitioning_columns,
                clustering_columns,
                pg_typeof(partitioning_columns) as part_type,
                pg_typeof(clustering_columns) as clust_type
            FROM assessment_tables
            WHERE partitioning_columns IS NOT NULL 
               OR clustering_columns IS NOT NULL
            LIMIT 5
        """)
        
        results = db.execute(query).fetchall()
        
        if not results:
            print("\n❌ No tables found with partitioning or clustering columns")
            return
        
        print(f"\n✓ Found {len(results)} tables with array columns\n")
        
        for row in results:
            print(f"Table: {row.table_name}")
            print(f"  Partitioning Columns:")
            print(f"    Type: {row.part_type}")
            print(f"    Value: {row.partitioning_columns}")
            print(f"    Python Type: {type(row.partitioning_columns)}")
            if row.partitioning_columns:
                print(f"    Is List: {isinstance(row.partitioning_columns, list)}")
                if isinstance(row.partitioning_columns, list):
                    print(f"    Items: {row.partitioning_columns}")
                else:
                    print(f"    String Repr: {repr(row.partitioning_columns)}")
            
            print(f"  Clustering Columns:")
            print(f"    Type: {row.clust_type}")
            print(f"    Value: {row.clustering_columns}")
            print(f"    Python Type: {type(row.clustering_columns)}")
            if row.clustering_columns:
                print(f"    Is List: {isinstance(row.clustering_columns, list)}")
                if isinstance(row.clustering_columns, list):
                    print(f"    Items: {row.clustering_columns}")
                else:
                    print(f"    String Repr: {repr(row.clustering_columns)}")
            print()
        
        # Now test with SQLAlchemy ORM
        print("=" * 80)
        print("TESTING WITH SQLALCHEMY ORM")
        print("=" * 80)
        
        from models.assessment import AssessmentTable
        
        tables = db.query(AssessmentTable).filter(
            (AssessmentTable.partitioning_columns.isnot(None)) |
            (AssessmentTable.clustering_columns.isnot(None))
        ).limit(5).all()
        
        for table in tables:
            print(f"\nTable: {table.table_name}")
            print(f"  Partitioning Columns: {table.partitioning_columns}")
            print(f"    Type: {type(table.partitioning_columns)}")
            print(f"    Is List: {isinstance(table.partitioning_columns, list)}")
            
            print(f"  Clustering Columns: {table.clustering_columns}")
            print(f"    Type: {type(table.clustering_columns)}")
            print(f"    Is List: {isinstance(table.clustering_columns, list)}")
            
            # Test JSON serialization
            try:
                data = {
                    "partitioning_columns": table.partitioning_columns,
                    "clustering_columns": table.clustering_columns
                }
                json_str = json.dumps(data)
                print(f"  JSON Serialization: ✓ Success")
                print(f"    {json_str}")
            except Exception as e:
                print(f"  JSON Serialization: ✗ Failed - {e}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    diagnose_array_columns()
