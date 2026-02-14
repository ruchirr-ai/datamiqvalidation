"""
Fix policy_tags format in assessment_columns table.
Converts JSON strings to proper PostgreSQL arrays.
"""
import sys
import os
import json

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in environment variables")
    sys.exit(1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def fix_policy_tags():
    """Fix policy_tags that are stored as JSON strings"""
    session = SessionLocal()
    
    try:
        print("Fixing policy_tags format in assessment_columns...")
        
        # Get all columns with policy_tags
        query = text("""
            SELECT id, policy_tags
            FROM assessment_columns
            WHERE policy_tags IS NOT NULL
        """)
        
        result = session.execute(query)
        rows = result.fetchall()
        
        print(f"Found {len(rows)} columns with policy_tags")
        
        fixed_count = 0
        for row in rows:
            col_id = row[0]
            policy_tags = row[1]
            
            # Check if it's a string (needs fixing)
            if isinstance(policy_tags, str):
                try:
                    # Parse JSON string to array
                    tags_array = json.loads(policy_tags)
                    
                    # Update with proper array
                    update_query = text("""
                        UPDATE assessment_columns
                        SET policy_tags = :tags
                        WHERE id = :id
                    """)
                    
                    session.execute(update_query, {"tags": tags_array, "id": col_id})
                    fixed_count += 1
                    
                    if fixed_count % 100 == 0:
                        print(f"Fixed {fixed_count} columns...")
                        session.commit()
                        
                except json.JSONDecodeError as e:
                    print(f"Warning: Could not parse policy_tags for column {col_id}: {e}")
                    continue
        
        session.commit()
        print(f"\n✓ Fixed {fixed_count} columns with policy_tags")
        
    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Fix Policy Tags Format Script")
    print("=" * 60)
    
    fix_policy_tags()
    
    print("\n" + "=" * 60)
    print("Script completed successfully!")
    print("=" * 60)
