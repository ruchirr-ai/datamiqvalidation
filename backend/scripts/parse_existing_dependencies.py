"""
Parse dependencies for existing assessments.
Updates views and routines with dependency information using direct SQL.
"""
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from utils.sql_dependency_parser import SQLDependencyParser
import re

# Load environment variables
load_dotenv()

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    # Try constructing from individual components
    db_host = os.getenv('APP_DB_HOST', 'localhost')
    db_port = os.getenv('APP_DB_PORT', '5432')
    db_name = os.getenv('APP_DB_NAME', 'db_migrator')
    db_user = os.getenv('APP_DB_USER', 'db_migrator_user')
    db_password = os.getenv('APP_DB_PASSWORD', '')
    
    DATABASE_URL = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def extract_procedure_calls(sql: str) -> list:
    """Extract CALL statements for stored procedures"""
    if not sql:
        return []
    
    pattern = r'CALL\s+`?([a-zA-Z0-9_.-]+)`?'
    matches = re.findall(pattern, sql, re.IGNORECASE)
    return list(set(matches))  # Remove duplicates

def parse_view_dependencies():
    """Parse dependencies for all views using direct SQL"""
    session = SessionLocal()
    parser = SQLDependencyParser()
    
    try:
        print("Parsing dependencies for views...")
        
        # Get all views using raw SQL
        query = text("SELECT id, view_name, view_definition FROM assessment_views")
        result = session.execute(query)
        views = result.fetchall()
        
        print(f"Found {len(views)} views to process")
        
        if len(views) == 0:
            print("No views found in database")
            return
        
        # First pass: collect all view names for categorization
        view_names = {row[1] for row in views}  # row[1] is view_name
        
        updated_count = 0
        for row in views:
            view_id = row[0]
            view_name = row[1]
            view_definition = row[2]
            
            if not view_definition:
                continue
            
            # Parse dependencies
            dependencies = parser.parse_dependencies(view_definition)
            
            # Categorize dependencies
            dependent_tables = []
            dependent_views = []
            
            for dep in dependencies['tables']:
                if dep in view_names:
                    dependent_views.append(dep)
                else:
                    dependent_tables.append(dep)
            
            # Update view using raw SQL
            update_query = text("""
                UPDATE assessment_views
                SET dependencies = :dependencies,
                    dependent_tables = :dependent_tables,
                    dependent_views = :dependent_views,
                    dependent_functions = :dependent_functions,
                    dependency_depth = 1
                WHERE id = :id
            """)
            
            session.execute(update_query, {
                'id': view_id,
                'dependencies': dependencies['tables'],
                'dependent_tables': dependent_tables,
                'dependent_views': dependent_views,
                'dependent_functions': dependencies['functions']
            })
            
            updated_count += 1
            
            if updated_count % 10 == 0:
                print(f"Processed {updated_count} views...")
                session.commit()
        
        session.commit()
        print(f"\n✓ Updated {updated_count} views with dependencies")
        
    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        session.close()

def parse_routine_dependencies():
    """Parse dependencies for all routines using direct SQL"""
    session = SessionLocal()
    parser = SQLDependencyParser()
    
    try:
        print("\nParsing dependencies for routines...")
        
        # Get all routines using raw SQL
        query = text("SELECT id, routine_name, definition FROM assessment_routines")
        result = session.execute(query)
        routines = result.fetchall()
        
        print(f"Found {len(routines)} routines to process")
        
        if len(routines) == 0:
            print("No routines found in database")
            return
        
        # Get all views for categorization
        view_query = text("SELECT view_name FROM assessment_views")
        view_result = session.execute(view_query)
        view_names = {row[0] for row in view_result.fetchall()}
        
        updated_count = 0
        for row in routines:
            routine_id = row[0]
            routine_name = row[1]
            definition = row[2]
            
            if not definition:
                continue
            
            # Parse dependencies
            dependencies = parser.parse_dependencies(definition)
            
            # Extract procedure calls
            calls_procedures = extract_procedure_calls(definition)
            
            # Categorize dependencies
            dependent_tables = []
            dependent_views = []
            
            for dep in dependencies['tables']:
                if dep in view_names:
                    dependent_views.append(dep)
                else:
                    dependent_tables.append(dep)
            
            # Update routine using raw SQL
            update_query = text("""
                UPDATE assessment_routines
                SET dependent_tables = :dependent_tables,
                    dependent_views = :dependent_views,
                    dependent_functions = :dependent_functions,
                    calls_procedures = :calls_procedures,
                    dependency_depth = 1
                WHERE id = :id
            """)
            
            session.execute(update_query, {
                'id': routine_id,
                'dependent_tables': dependent_tables,
                'dependent_views': dependent_views,
                'dependent_functions': dependencies['functions'],
                'calls_procedures': calls_procedures
            })
            
            updated_count += 1
            
            if updated_count % 10 == 0:
                print(f"Processed {updated_count} routines...")
                session.commit()
        
        session.commit()
        print(f"\n✓ Updated {updated_count} routines with dependencies")
        
    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        session.close()

def main():
    print("=" * 60)
    print("Parse Dependencies for Existing Assessments")
    print("=" * 60)
    print()
    
    # Parse views
    parse_view_dependencies()
    
    # Parse routines
    parse_routine_dependencies()
    
    print()
    print("=" * 60)
    print("Script completed successfully!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Refresh the assessment report page in your browser")
    print("2. Click on any view or stored procedure name")
    print("3. You should now see all dependencies listed")

if __name__ == "__main__":
    main()
