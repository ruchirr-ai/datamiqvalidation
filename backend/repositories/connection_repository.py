"""
Connection Repository

Database operations for connections
"""

from sqlalchemy.orm import Session
from typing import List, Optional

from models.connection import Connection


class ConnectionRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_id(self, connection_id: int) -> Optional[Connection]:
        """Get connection by ID"""
        return self.db.query(Connection).filter(
            Connection.id == connection_id
        ).first()
    
    def list_connections(self) -> List[Connection]:
        """List all connections"""
        return self.db.query(Connection).filter(
            Connection.is_active == True
        ).all()
    
    def get_by_type(self, connection_type: str) -> List[Connection]:
        """Get connections by type (source/target)"""
        return self.db.query(Connection).filter(
            Connection.type == connection_type,
            Connection.is_active == True
        ).all()
    
    def get_by_database(self, database: str) -> List[Connection]:
        """Get connections by database type"""
        return self.db.query(Connection).filter(
            Connection.database == database,
            Connection.is_active == True
        ).all()
