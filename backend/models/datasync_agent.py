"""
DataSync Agent Registry Model

Tracks DataSync agent VMs and their agent ARNs to enable reuse across migrations.
One VM = one agent. When a user provides a VM IP, we check this table first
before creating a new agent registration.
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from database import Base


class DataSyncAgent(Base):
    """
    Registry of DataSync agents mapped to their VM IPs.
    
    Prevents creating duplicate agent registrations for the same VM.
    Shared across all migrations — any migration using the same VM IP
    will reuse the same agent ARN.
    """
    __tablename__ = 'datasync_agents'

    id = Column(Integer, primary_key=True)
    vm_ip = Column(String(255), nullable=False, unique=True, index=True)
    agent_arn = Column(String(512), nullable=False)
    aws_region = Column(String(50), nullable=False, default='us-east-1')
    status = Column(String(50), default='online')  # online, offline, unknown
    last_used_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'vm_ip': self.vm_ip,
            'agent_arn': self.agent_arn,
            'aws_region': self.aws_region,
            'status': self.status,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
