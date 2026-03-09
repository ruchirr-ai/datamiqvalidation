"""
Connection Model

Database model for connection management.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, Text
from database import Base


class Connection(Base):
    """
    Connection model for database connections.
    
    Stores connection information for source and target databases.
    """
    __tablename__ = 'connections'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)  # bigquery, redshift, postgresql, etc.
    database = Column(String(100), nullable=False)
    connection_params = Column(JSON, nullable=False)  # Unencrypted (backward compatibility)
    connection_params_encrypted = Column(Text, nullable=True)  # KMS encrypted connection params
    created_by = Column(String(255), nullable=False, default='system')
    status = Column(String(50), nullable=False, default='disconnected')  # connected, disconnected, error
    last_tested_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, nullable=False, default=True)
    
    def __repr__(self):
        return f"<Connection(id={self.id}, name='{self.name}', type='{self.type}', database='{self.database}')>"
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'database': self.database,
            'connection_params': self.connection_params,
            'created_by': self.created_by,
            'status': self.status,
            'last_tested_at': self.last_tested_at.isoformat() if self.last_tested_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_active': self.is_active
        }
