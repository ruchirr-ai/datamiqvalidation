"""
Verify that array columns are now properly formatted.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(env_path)

# Database connection
db_host = os.getenv('APP_DB_HOST', 'localhost')
db_port = os.getenv('APP_DB_PORT', '5432')
db_name = os.getenv('APP_DB_NAME')
db_user = os.getenv('APP_DB_USER')
db_password = os.getenv('APP_DB_PASSWORD', '')

if not db_name or not db_user:
    print("ERROR: Missing required database environment variables")
    sys.exit(1)

if db_password:
    DATABASE_URL = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
else:
    DATABASE_URL = f"postgresql://{db_user}@{db_host}:{db_port}/{db_name}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def verify_fix():
    """Verify array columns are properly formatted"""
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("VERIFYING ARRAY COLUMNS FIX")
        print("=" * 80)
        
        # Get tables with non-empty array columns
        query = text("""
            SELECT 
                table_name,
                partitioning_columns,
                clustering_columns
            FROM assessment_tables
            WHERE array_length(partitioning_columns, 1) > 0
               OR array_length(clustering_columns, 1) > 0
            ORDER BY table_name
        """)
        
        results = db.execute(query).fetchall()
        
        if not results:
            print("\n✓ No tables with non-empty array columns found")
            print("  (This is expected if all arrays were empty '[]')")
        else:
            print(f"\n✓ Found {len(results)} tables with non-empty array columns:\n")
            
            for row in results:
                print(f"Table: {row.table_name}")
                if row.partitioning_columns:
                    print(f"  Partitioning: {row.partitioning_columns}")
                if row.clustering_columns:
                    print(f"  Clustering: {row.clustering_columns}")
                print()
        
        # Check for any malformed arrays (containing '[', ']', or '"')
        malformed_query = text("""
            SELECT 
                table_name,
                partitioning_columns,
                clustering_columns
            FROM assessment_tables
            WHERE 
                '[' = ANY(partitioning_columns) OR
                ']' = ANY(partitioning_columns) OR
                '"' = ANY(partitioning_columns) OR
                '[' = ANY(clustering_columns) OR
                ']' = ANY(clustering_columns) OR
                '"' = ANY(clustering_columns)
        """)
        
        malformed = db.execute(malformed_query).fetchall()
        
        if malformed:
            print("=" * 80)
            print("⚠️  WARNING: Found malformed arrays:")
            print("=" * 80)
            for row in malformed:
                print(f"Table: {row.table_name}")
                print(f"  Partitioning: {row.partitioning_columns}")
                print(f"  Clustering: {row.clustering_columns}")
                print()
        else:
            print("=" * 80)
            print("✓ SUCCESS: All array columns are properly formatted!")
            print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    verify_fix()
