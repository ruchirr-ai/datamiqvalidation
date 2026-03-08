"""
History Database Models

SQLAlchemy ORM models for history tracking tables.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, BigInteger, JSON, ForeignKey
from database import Base


class CopyHistory(Base):
    """SQLAlchemy model for copy_history table"""
    __tablename__ = 'copy_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    migration_id = Column(Integer, nullable=False, index=True)
    schema_name = Column(String(255), nullable=False)
    table_name = Column(String(255), nullable=False)
    copy_command = Column(Text, nullable=False)
    status = Column(String(50), nullable=False, default='running', index=True)
    rows_loaded = Column(BigInteger, nullable=True)
    bytes_loaded = Column(BigInteger, nullable=True)
    error_details = Column(JSON, nullable=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'migration_id': self.migration_id,
            'schema_name': self.schema_name,
            'table_name': self.table_name,
            'copy_command': self.copy_command,
            'status': self.status,
            'rows_loaded': self.rows_loaded,
            'bytes_loaded': self.bytes_loaded,
            'error_details': self.error_details,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'duration_seconds': self.duration_seconds
        }


class TaskHistory(Base):
    """SQLAlchemy model for task_history table"""
    __tablename__ = 'task_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    migration_id = Column(Integer, nullable=False, index=True)
    task_name = Column(String(255), nullable=False)
    task_arn = Column(String(500), nullable=False)
    agent_arn = Column(String(500), nullable=False)
    agent_ip = Column(String(50), nullable=False, index=True)
    source_uri = Column(Text, nullable=False)
    dest_uri = Column(Text, nullable=False)
    status = Column(String(50), nullable=False, default='running', index=True)
    files_transferred = Column(BigInteger, nullable=True)
    bytes_transferred = Column(BigInteger, nullable=True)
    error_details = Column(JSON, nullable=True)
    raw_result = Column(JSON, nullable=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'migration_id': self.migration_id,
            'task_name': self.task_name,
            'task_arn': self.task_arn,
            'agent_arn': self.agent_arn,
            'agent_ip': self.agent_ip,
            'source_uri': self.source_uri,
            'dest_uri': self.dest_uri,
            'status': self.status,
            'files_transferred': self.files_transferred,
            'bytes_transferred': self.bytes_transferred,
            'error_details': self.error_details,
            'raw_result': self.raw_result,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'duration_seconds': self.duration_seconds
        }


class DataSyncAgent(Base):
    """SQLAlchemy model for datasync_agents table"""
    __tablename__ = 'datasync_agents'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(Integer, nullable=False, index=True)
    agent_arn = Column(String(500), nullable=False)
    vm_ip = Column(String(50), nullable=False, unique=True)
    aws_region = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False, default='unknown')
    last_used_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'agent_arn': self.agent_arn,
            'vm_ip': self.vm_ip,
            'aws_region': self.aws_region,
            'status': self.status,
            'last_used_at': self.last_used_at,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
