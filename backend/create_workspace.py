"""Create default workspace for development"""

from sqlalchemy import text
from database import db_instance

def create_default_workspace():
    """Create default organization and workspace if they don't exist"""
    with db_instance.get_session() as db:
        # Check if organization exists
        result = db.execute(text("SELECT id FROM organizations WHERE id = 1"))
        existing_org = result.fetchone()
        
        if not existing_org:
            # Create organization
            db.execute(text("""
                INSERT INTO organizations (id, name, slug)
                VALUES (1, 'Default Organization', 'default-org')
            """))
            db.commit()
            print("Default organization created")
        else:
            print("Organization 1 already exists")
        
        # Check if workspace exists
        result = db.execute(text("SELECT id FROM workspaces WHERE id = 1"))
        existing_ws = result.fetchone()
        
        if not existing_ws:
            # Create workspace
            db.execute(text("""
                INSERT INTO workspaces (id, name, slug, organization_id, description)
                VALUES (1, 'Default Workspace', 'default-workspace', 1, 'Default workspace for development')
            """))
            db.commit()
            print("Default workspace created successfully")
        else:
            print("Workspace 1 already exists")

if __name__ == "__main__":
    create_default_workspace()
