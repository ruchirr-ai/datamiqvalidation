"""
Simple script to update connection status in database using psycopg2 directly
"""

import psycopg2
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection parameters
DB_HOST = os.getenv('APP_DB_HOST', 'localhost')
DB_PORT = os.getenv('APP_DB_PORT', '5432')
DB_NAME = os.getenv('APP_DB_NAME', 'datamiq')
DB_USER = os.getenv('APP_DB_USER', 'manasakallakuri')
DB_PASSWORD = os.getenv('APP_DB_PASSWORD', '')

def update_connections():
    """Update all existing connections to 'connected' status"""
    try:
        # Connect to database
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        cursor = conn.cursor()
        
        # Get current connections
        cursor.execute("""
            SELECT id, name, database, status 
            FROM connections 
            WHERE is_active = TRUE
            ORDER BY id
        """)
        
        connections = cursor.fetchall()
        print(f"\nFound {len(connections)} connections:")
        print("-" * 80)
        
        for conn_id, name, database, status in connections:
            print(f"ID: {conn_id:3d} | Name: {name:30s} | DB: {database:15s} | Status: {status}")
        
        print("-" * 80)
        
        # Update all connections to 'connected' status
        cursor.execute("""
            UPDATE connections 
            SET 
                status = 'connected',
                last_tested_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE 
                is_active = TRUE 
                AND status != 'connected'
        """)
        
        updated_count = cursor.rowcount
        conn.commit()
        
        print(f"\n✓ Updated {updated_count} connections to 'connected' status")
        
        # Show updated connections
        cursor.execute("""
            SELECT id, name, database, status, last_tested_at 
            FROM connections 
            WHERE is_active = TRUE
            ORDER BY id
        """)
        
        connections = cursor.fetchall()
        print(f"\nUpdated connections:")
        print("-" * 80)
        
        for conn_id, name, database, status, last_tested in connections:
            last_tested_str = last_tested.strftime('%Y-%m-%d %H:%M:%S') if last_tested else 'Never'
            print(f"ID: {conn_id:3d} | Name: {name:30s} | Status: {status:12s} | Last Tested: {last_tested_str}")
        
        print("-" * 80)
        print("\n✓ All connections updated successfully!")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        raise


if __name__ == "__main__":
    print("=" * 80)
    print("Updating Connection Status in Database")
    print("=" * 80)
    update_connections()
