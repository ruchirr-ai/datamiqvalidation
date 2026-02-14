"""
Verify that column indicators are properly set.
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

def verify_indicators():
    """Verify column indicators are properly set"""
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("VERIFYING COLUMN INDICATORS")
        print("=" * 80)
        
        # Get columns with indicators
        query = text("""
            SELECT 
                t.table_name,
                c.column_name,
                c.is_partitioning_column,
                c.clustering_ordinal_position
            FROM assessment_columns c
            JOIN assessment_tables t ON c.table_id = t.id
            WHERE c.is_partitioning_column = true
               OR c.clustering_ordinal_position IS NOT NULL
            ORDER BY t.table_name, c.column_name
        """)
        
        results = db.execute(query).fetchall()
        
        if not results:
            print("\n⚠️  No columns with partitioning or clustering indicators found")
        else:
            print(f"\n✓ Found {len(results)} columns with indicators:\n")
            
            current_table = None
            for row in results:
                if row.table_name != current_table:
                    if current_table is not None:
                        print()
                    print(f"Table: {row.table_name}")
                    current_table = row.table_name
                
                indicators = []
                if row.is_partitioning_column:
                    indicators.append("Partitioning")
                if row.clustering_ordinal_position is not None:
                    indicators.append(f"Clustering (position {row.clustering_ordinal_position})")
                
                print(f"  - {row.column_name}: {', '.join(indicators)}")
        
        print("\n" + "=" * 80)
        print("✓ VERIFICATION COMPLETE")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    verify_indicators()
