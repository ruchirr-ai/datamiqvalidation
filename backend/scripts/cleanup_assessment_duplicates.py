"""
Cleanup script to remove duplicate records from assessment tables

This script removes duplicate records that may have been created before
unique constraints were added.
"""

import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func, text
from database import db_instance


def cleanup_duplicates():
    """Remove duplicate records from all assessment tables"""
    db = db_instance.SessionLocal()
    
    try:
        print("Starting duplicate cleanup...")
        
        # 1. Cleanup duplicate datasets
        print("\n1. Cleaning up duplicate datasets...")
        result = db.execute(text("""
            SELECT assessment_id, dataset_name, COUNT(*) as count
            FROM assessment_datasets
            GROUP BY assessment_id, dataset_name
            HAVING COUNT(*) > 1
        """))
        duplicates = result.fetchall()
        
        for dup in duplicates:
            # Keep the first record, delete the rest
            db.execute(text("""
                DELETE FROM assessment_datasets
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM assessment_datasets
                    WHERE assessment_id = :assessment_id
                    AND dataset_name = :dataset_name
                )
                AND assessment_id = :assessment_id
                AND dataset_name = :dataset_name
            """), {"assessment_id": dup[0], "dataset_name": dup[1]})
            
            print(f"  Removed duplicate(s) for dataset: {dup[1]}")
        
        db.commit()
        print(f"✓ Cleaned up {len(duplicates)} duplicate dataset groups")
        
        # 2. Cleanup duplicate tables
        print("\n2. Cleaning up duplicate tables...")
        result = db.execute(text("""
            SELECT assessment_id, dataset_name, table_name, COUNT(*) as count
            FROM assessment_tables
            GROUP BY assessment_id, dataset_name, table_name
            HAVING COUNT(*) > 1
        """))
        duplicates = result.fetchall()
        
        for dup in duplicates:
            db.execute(text("""
                DELETE FROM assessment_tables
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM assessment_tables
                    WHERE assessment_id = :assessment_id
                    AND dataset_name = :dataset_name
                    AND table_name = :table_name
                )
                AND assessment_id = :assessment_id
                AND dataset_name = :dataset_name
                AND table_name = :table_name
            """), {"assessment_id": dup[0], "dataset_name": dup[1], "table_name": dup[2]})
            
            print(f"  Removed duplicate(s) for table: {dup[1]}.{dup[2]}")
        
        db.commit()
        print(f"✓ Cleaned up {len(duplicates)} duplicate table groups")
        
        # 3. Cleanup duplicate columns
        print("\n3. Cleaning up duplicate columns...")
        result = db.execute(text("""
            SELECT assessment_id, table_id, column_name, COUNT(*) as count
            FROM assessment_columns
            GROUP BY assessment_id, table_id, column_name
            HAVING COUNT(*) > 1
        """))
        duplicates = result.fetchall()
        
        for dup in duplicates:
            db.execute(text("""
                DELETE FROM assessment_columns
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM assessment_columns
                    WHERE assessment_id = :assessment_id
                    AND table_id = :table_id
                    AND column_name = :column_name
                )
                AND assessment_id = :assessment_id
                AND table_id = :table_id
                AND column_name = :column_name
            """), {"assessment_id": dup[0], "table_id": dup[1], "column_name": dup[2]})
            
            print(f"  Removed duplicate(s) for column: {dup[2]}")
        
        db.commit()
        print(f"✓ Cleaned up {len(duplicates)} duplicate column groups")
        
        # 4. Cleanup duplicate views
        print("\n4. Cleaning up duplicate views...")
        result = db.execute(text("""
            SELECT assessment_id, view_name, COUNT(*) as count
            FROM assessment_views
            GROUP BY assessment_id, view_name
            HAVING COUNT(*) > 1
        """))
        duplicates = result.fetchall()
        
        for dup in duplicates:
            db.execute(text("""
                DELETE FROM assessment_views
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM assessment_views
                    WHERE assessment_id = :assessment_id
                    AND view_name = :view_name
                )
                AND assessment_id = :assessment_id
                AND view_name = :view_name
            """), {"assessment_id": dup[0], "view_name": dup[1]})
            
            print(f"  Removed duplicate(s) for view: {dup[1]}")
        
        db.commit()
        print(f"✓ Cleaned up {len(duplicates)} duplicate view groups")
        
        # 5. Cleanup duplicate routines
        print("\n5. Cleaning up duplicate routines...")
        result = db.execute(text("""
            SELECT assessment_id, routine_name, COUNT(*) as count
            FROM assessment_routines
            GROUP BY assessment_id, routine_name
            HAVING COUNT(*) > 1
        """))
        duplicates = result.fetchall()
        
        for dup in duplicates:
            db.execute(text("""
                DELETE FROM assessment_routines
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM assessment_routines
                    WHERE assessment_id = :assessment_id
                    AND routine_name = :routine_name
                )
                AND assessment_id = :assessment_id
                AND routine_name = :routine_name
            """), {"assessment_id": dup[0], "routine_name": dup[1]})
            
            print(f"  Removed duplicate(s) for routine: {dup[1]}")
        
        db.commit()
        print(f"✓ Cleaned up {len(duplicates)} duplicate routine groups")
        
        # 6. Cleanup duplicate query stats
        print("\n6. Cleaning up duplicate query stats...")
        result = db.execute(text("""
            SELECT assessment_id, job_id, COUNT(*) as count
            FROM assessment_query_stats
            GROUP BY assessment_id, job_id
            HAVING COUNT(*) > 1
        """))
        duplicates = result.fetchall()
        
        for dup in duplicates:
            db.execute(text("""
                DELETE FROM assessment_query_stats
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM assessment_query_stats
                    WHERE assessment_id = :assessment_id
                    AND job_id = :job_id
                )
                AND assessment_id = :assessment_id
                AND job_id = :job_id
            """), {"assessment_id": dup[0], "job_id": dup[1]})
            
            print(f"  Removed duplicate(s) for job: {dup[1]}")
        
        db.commit()
        print(f"✓ Cleaned up {len(duplicates)} duplicate query stat groups")
        
        # 7. Cleanup duplicate ML models
        print("\n7. Cleaning up duplicate ML models...")
        result = db.execute(text("""
            SELECT assessment_id, model_name, COUNT(*) as count
            FROM assessment_ml_models
            GROUP BY assessment_id, model_name
            HAVING COUNT(*) > 1
        """))
        duplicates = result.fetchall()
        
        for dup in duplicates:
            db.execute(text("""
                DELETE FROM assessment_ml_models
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM assessment_ml_models
                    WHERE assessment_id = :assessment_id
                    AND model_name = :model_name
                )
                AND assessment_id = :assessment_id
                AND model_name = :model_name
            """), {"assessment_id": dup[0], "model_name": dup[1]})
            
            print(f"  Removed duplicate(s) for model: {dup[1]}")
        
        db.commit()
        print(f"✓ Cleaned up {len(duplicates)} duplicate ML model groups")
        
        # 8. Cleanup duplicate sharded tables
        print("\n8. Cleaning up duplicate sharded tables...")
        result = db.execute(text("""
            SELECT assessment_id, shard_group, COUNT(*) as count
            FROM assessment_sharded_tables
            GROUP BY assessment_id, shard_group
            HAVING COUNT(*) > 1
        """))
        duplicates = result.fetchall()
        
        for dup in duplicates:
            db.execute(text("""
                DELETE FROM assessment_sharded_tables
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM assessment_sharded_tables
                    WHERE assessment_id = :assessment_id
                    AND shard_group = :shard_group
                )
                AND assessment_id = :assessment_id
                AND shard_group = :shard_group
            """), {"assessment_id": dup[0], "shard_group": dup[1]})
            
            print(f"  Removed duplicate(s) for shard group: {dup[1]}")
        
        db.commit()
        print(f"✓ Cleaned up {len(duplicates)} duplicate sharded table groups")
        
        print("\n✅ Duplicate cleanup completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error during cleanup: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    cleanup_duplicates()
