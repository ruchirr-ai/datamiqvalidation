"""
Task History Model

Tracks all AWS DataSync tasks executed during migrations.
"""

from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Text, Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from database import Base


class TaskHistory(Base):
    """Tracks every DataSync task executed during migrations."""
    __tablename__ = 'task_history'

    id = Column(Integer, primary_key=True)
    migration_id = Column(Integer, nullable=False)
    migration_name = Column(String(255), nullable=False)

    # Task info
    task_arn = Column(String(500))
    execution_arn = Column(String(500))
    task_name = Column(String(255))
    task_type = Column(String(50), default='datasync')  # datasync, storage_transfer, etc.

    # Agent info
    agent_arn = Column(String(500))
    agent_ip = Column(String(100))

    # Source / Destination
    source_location_arn = Column(String(500))
    source_uri = Column(Text)  # e.g. gs://bucket/path
    dest_location_arn = Column(String(500))
    dest_uri = Column(Text)  # e.g. s3://bucket/path

    # Table info (if per-table task)
    table_name = Column(String(255))

    # Execution details
    status = Column(String(50), nullable=False, default='running')  # running, completed, failed, agent_offline
    started_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    completed_at = Column(DateTime)
    duration_seconds = Column(Float)

    # Results
    files_transferred = Column(BigInteger, default=0)
    bytes_transferred = Column(BigInteger, default=0)

    # Error info
    error_message = Column(Text)
    error_code = Column(String(100))
    error_details = Column(JSONB)

    # Raw result from AWS
    raw_result = Column(JSONB)

    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

    def to_dict(self):
        return {
            'id': self.id,
            'migration_id': self.migration_id,
            'migration_name': self.migration_name,
            'task_arn': self.task_arn,
            'execution_arn': self.execution_arn,
            'task_name': self.task_name,
            'task_type': self.task_type,
            'agent_arn': self.agent_arn,
            'agent_ip': self.agent_ip,
            'source_location_arn': self.source_location_arn,
            'source_uri': self.source_uri,
            'dest_location_arn': self.dest_location_arn,
            'dest_uri': self.dest_uri,
            'table_name': self.table_name,
            'status': self.status,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_seconds': self.duration_seconds,
            'files_transferred': self.files_transferred,
            'bytes_transferred': self.bytes_transferred,
            'error_message': self.error_message,
            'error_code': self.error_code,
            'error_details': self.error_details,
            'raw_result': self.raw_result,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
