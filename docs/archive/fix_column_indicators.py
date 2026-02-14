"""
Fix partitioning and clustering indicators in assessment_columns table.
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

def fix_column_indicators():
    """Fix partitioning and clustering indicators in columns"""
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("FIXING COLUMN PARTITIONING AND CLUSTERING INDICATORS")
        print("=" * 80)
        
        # Get all tables with their partitioning and clustering info
        tables_query = text("""
            SELECT 
                id,
                table_name,
                partitioning_columns,
                clustering_columns
            FROM assessment_tables
            WHERE partitioning_columns IS NOT NULL 
               OR clustering_columns IS NOT NULL
        """)
        
        tables = db.execute(tables_query).fetchall()
        
        if not tables:
            print("\n✓ No tables with partitioning or clustering columns found")
            return
        
        print(f"\n✓ Found {len(tables)} tables with partitioning/clustering\n")
        
        updated_count = 0
        
        for table in tables:
            table_id = table.id
            table_name = table.table_name
            part_cols = table.partitioning_columns or []
            clust_cols = table.clustering_columns or []
            
            if not part_cols and not clust_cols:
                continue
            
            print(f"Processing table: {table_name}")
            if part_cols:
                print(f"  Partitioning columns: {part_cols}")
            if clust_cols:
                print(f"  Clustering columns: {clust_cols}")
            
            # Update partitioning columns
            if part_cols:
                for col_name in part_cols:
                    update_query = text("""
                        UPDATE assessment_columns
                        SET is_partitioning_column = true
                        WHERE table_id = :table_id
                          AND column_name = :col_name
                    """)
                    result = db.execute(update_query, {
                        'table_id': table_id,
                        'col_name': col_name
                    })
                    if result.rowcount > 0:
                        print(f"    ✓ Marked {col_name} as partitioning column")
                        updated_count += 1
            
            # Update clustering columns with ordinal positions
            if clust_cols:
                for idx, col_name in enumerate(clust_cols, start=1):
                    update_query = text("""
                        UPDATE assessment_columns
                        SET clustering_ordinal_position = :position
                        WHERE table_id = :table_id
                          AND column_name = :col_name
                    """)
                    result = db.execute(update_query, {
                        'table_id': table_id,
                        'col_name': col_name,
                        'position': idx
                    })
                    if result.rowcount > 0:
                        print(f"    ✓ Marked {col_name} as clustering column (position {idx})")
                        updated_count += 1
            
            print()
        
        db.commit()
        
        print("=" * 80)
        print(f"SUMMARY: Updated {updated_count} column indicators")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_column_indicators()
