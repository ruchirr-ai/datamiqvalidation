"""
DataSync Agent Registry Model

Tracks DataSync agents by VM IP to avoid creating duplicate agents
when multiple migrations use the same VM.
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from database import Base


class DataSyncAgent(Base):
    """
    Registry of DataSync agents mapped to VM IPs.
    
    When a migration needs a DataSync agent, it first checks this table
    for an existing agent on the same VM IP. If found and online, it reuses it.
    If not found or offline, it creates a new one and updates this table.
    """
    __tablename__ = 'datasync_agents'
    
    id = Column(Integer, primary_key=True)
    vm_ip = Column(String(255), nullable=False, unique=True, index=True)
    agent_arn = Column(String(512), nullable=False)
    aws_region = Column(String(50), nullable=False, default='us-east-1')
    is_active = Column(Boolean, default=True)
    last_verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def to_dict(self):
        return {
            'id': self.id,
            'vm_ip': self.vm_ip,
            'agent_arn': self.agent_arn,
            'aws_region': self.aws_region,
            'is_active': self.is_active,
            'last_verified_at': self.last_verified_at.isoformat() if self.last_verified_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
