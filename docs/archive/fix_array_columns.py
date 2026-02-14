"""
Fix partitioning_columns and clustering_columns that were stored as character arrays
instead of proper string arrays.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import json

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

def parse_malformed_array(arr):
    """
    Parse a malformed array like ['[', '"', 'c', 'o', 'l', '"', ']']
    back into a proper array like ['col']
    """
    if not arr or len(arr) == 0:
        return []
    
    # If it's already a proper array (no '[' or ']' characters), return as-is
    if '[' not in arr and ']' not in arr:
        return arr
    
    # Join the characters back into a string
    joined = ''.join(arr)
    
    # Try to parse as JSON
    try:
        parsed = json.loads(joined)
        if isinstance(parsed, list):
            return parsed
        return []
    except:
        return []

def fix_array_columns():
    """Fix malformed array columns in assessment_tables"""
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("FIXING ARRAY COLUMNS IN ASSESSMENT TABLES")
        print("=" * 80)
        
        # Get all tables with array columns
        query = text("""
            SELECT 
                id,
                table_name,
                partitioning_columns,
                clustering_columns
            FROM assessment_tables
            WHERE partitioning_columns IS NOT NULL 
               OR clustering_columns IS NOT NULL
        """)
        
        results = db.execute(query).fetchall()
        
        if not results:
            print("\n✓ No tables found with array columns")
            return
        
        print(f"\n✓ Found {len(results)} tables with array columns\n")
        
        fixed_count = 0
        
        for row in results:
            table_id = row.id
            table_name = row.table_name
            part_cols = row.partitioning_columns
            clust_cols = row.clustering_columns
            
            # Parse malformed arrays
            fixed_part = parse_malformed_array(part_cols) if part_cols else []
            fixed_clust = parse_malformed_array(clust_cols) if clust_cols else []
            
            # Check if we need to update
            needs_update = False
            
            if part_cols and part_cols != fixed_part:
                needs_update = True
                print(f"Table: {table_name}")
                print(f"  Partitioning: {part_cols} → {fixed_part}")
            
            if clust_cols and clust_cols != fixed_clust:
                needs_update = True
                if not (part_cols and part_cols != fixed_part):
                    print(f"Table: {table_name}")
                print(f"  Clustering: {clust_cols} → {fixed_clust}")
            
            if needs_update:
                # Update the record
                update_query = text("""
                    UPDATE assessment_tables
                    SET 
                        partitioning_columns = :part_cols,
                        clustering_columns = :clust_cols
                    WHERE id = :table_id
                """)
                
                db.execute(update_query, {
                    'part_cols': fixed_part,
                    'clust_cols': fixed_clust,
                    'table_id': table_id
                })
                
                fixed_count += 1
                print(f"  ✓ Fixed\n")
        
        db.commit()
        
        print("=" * 80)
        print(f"SUMMARY: Fixed {fixed_count} tables")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_array_columns()
