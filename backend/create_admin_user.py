#!/usr/bin/env python3
"""
Create admin user for DataMIQ
"""

import os
import sys
from dotenv import load_dotenv
import bcrypt
from sqlalchemy import text
from database import db_instance

# Load environment variables
load_dotenv()


def create_admin_user():
    """Create admin user from environment variables"""
    admin_username = os.getenv('ADMIN_USER', 'admin')
    admin_password = os.getenv('ADMIN_PASSWORD', 'AdminPass123!')
    
    print(f"Creating admin user: {admin_username}")
    
    try:
        with db_instance.get_session() as db:
            # Check if admin user already exists
            result = db.execute(
                text("SELECT id, username FROM users WHERE username = :username"),
                {"username": admin_username}
            )
            existing_user = result.fetchone()
            
            # Hash password using bcrypt
            password_hash = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            if existing_user:
                print(f"Admin user '{admin_username}' already exists")
                print("Updating password...")
                db.execute(
                    text("UPDATE users SET password_hash = :password_hash, updated_at = CURRENT_TIMESTAMP WHERE username = :username"),
                    {"password_hash": password_hash, "username": admin_username}
                )
                print("Password updated successfully!")
            else:
                # Create new admin user
                db.execute(
                    text("""
                        INSERT INTO users (username, password_hash, role, created_at, updated_at)
                        VALUES (:username, :password_hash, :role, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """),
                    {
                        "username": admin_username,
                        "password_hash": password_hash,
                        "role": "admin"
                    }
                )
                print(f"Admin user '{admin_username}' created successfully!")
            
            print(f"\nLogin credentials:")
            print(f"Username: {admin_username}")
            print(f"Password: {admin_password}")
            
    except Exception as e:
        print(f"Error creating admin user: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    create_admin_user()
