"""
Copy History Model

Tracks all Redshift COPY commands executed during migrations.
"""

from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Text, Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from database import Base


class CopyHistory(Base):
    """Tracks every Redshift COPY command executed during migrations."""
    __tablename__ = 'copy_history'

    id = Column(Integer, primary_key=True)
    migration_id = Column(Integer, nullable=False)
    migration_name = Column(String(255), nullable=False)
    
    # Table info
    schema_name = Column(String(255), nullable=False)
    table_name = Column(String(255), nullable=False)
    
    # COPY command details
    copy_command = Column(Text, nullable=False)
    source_uri = Column(Text)  # manifest or S3 prefix
    file_format = Column(String(50))
    compression = Column(String(50))
    iam_role_arn = Column(String(500))
    
    # Execution details
    status = Column(String(50), nullable=False, default='running')  # running, completed, failed
    started_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    completed_at = Column(DateTime)
    duration_seconds = Column(Float)
    
    # Results
    rows_loaded = Column(BigInteger, default=0)
    bytes_loaded = Column(BigInteger, default=0)
    
    # Error info
    error_message = Column(Text)
    error_details = Column(JSONB)
    
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

    def to_dict(self):
        return {
            'id': self.id,
            'migration_id': self.migration_id,
            'migration_name': self.migration_name,
            'schema_name': self.schema_name,
            'table_name': self.table_name,
            'copy_command': self.copy_command,
            'source_uri': self.source_uri,
            'file_format': self.file_format,
            'compression': self.compression,
            'iam_role_arn': self.iam_role_arn,
            'status': self.status,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_seconds': self.duration_seconds,
            'rows_loaded': self.rows_loaded,
            'bytes_loaded': self.bytes_loaded,
            'error_message': self.error_message,
            'error_details': self.error_details,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
