"""
Check connection details
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database import get_db
from models.connection import Connection
import json

def check_connections():
    """Check all connections"""
    db = next(get_db())
    try:
        connections = db.query(Connection).all()
        
        print("="*80)
        print(f"ALL CONNECTIONS ({len(connections)} total)")
        print("="*80)
        print()
        
        for conn in connections:
            print(f"ID: {conn.id}")
            print(f"Name: {conn.name}")
            print(f"Type: {conn.type}")
            print(f"Status: {conn.status}")
            
            params = conn.connection_params or {}
            print(f"Connection Params:")
            for key, value in params.items():
                if 'password' in key.lower() or 'secret' in key.lower() or 'key' in key.lower():
                    print(f"  {key}: [ENCRYPTED]")
                else:
                    print(f"  {key}: {value}")
            
            print("-" * 80)
        
    finally:
        db.close()

if __name__ == "__main__":
    check_connections()
