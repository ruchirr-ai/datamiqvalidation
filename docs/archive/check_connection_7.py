"""Check connection 7 details"""
import sys
sys.path.insert(0, '.')

from database import get_db
from models.connection import Connection
import json

db = next(get_db())

# Get connection 7
conn = db.query(Connection).filter_by(id=7).first()

if conn:
    print(f"Connection ID: {conn.id}")
    print(f"Name: {conn.name}")
    print(f"Type: {conn.type}")
    print(f"Database: {conn.database}")
    print(f"\nConnection Params:")
    print(json.dumps(conn.connection_params, indent=2))
    
    # Check for password_encrypted
    if 'password_encrypted' in conn.connection_params:
        print("\n✓ password_encrypted found in connection_params")
        print(f"  Value: {conn.connection_params['password_encrypted'][:50]}...")
    else:
        print("\n❌ password_encrypted NOT found in connection_params")
        print(f"  Available keys: {list(conn.connection_params.keys())}")
else:
    print("Connection 7 not found")

db.close()
