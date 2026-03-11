"""
ValidationRun Model

Database model for validation run records tracking post-migration
data integrity verification between BigQuery and Redshift.
"""

from sqlalchemy import Column, Integer, String, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from database import Base


class ValidationRun(Base):
    """
    Validation run record for a set of migrated tables.

    Tracks overall validation status, progress, and summary statistics
    for DDL comparison, row count checks, and record-level matching.
    Scoped to a workspace for tenant isolation.
    """
    __tablename__ = 'validation_runs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(Integer, nullable=False)
    migration_id = Column(Integer, nullable=False)
    source_connection_id = Column(Integer, nullable=False)
    target_connection_id = Column(Integer, nullable=False)
    bedrock_model = Column(String(255), nullable=True)
    batch_size = Column(Integer, nullable=False, default=10000)
    type_mapping_overrides = Column(JSONB, nullable=True)
    status = Column(String(50), nullable=False, default='pending')
    progress_percentage = Column(Integer, nullable=False, default=0)
    tables_total = Column(Integer, nullable=False, default=0)
    tables_passed = Column(Integer, nullable=False, default=0)
    tables_failed = Column(Integer, nullable=False, default=0)
    tables_error = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    created_by = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(),
                        onupdate=func.current_timestamp())

    __table_args__ = (
        Index('idx_validation_runs_workspace', 'workspace_id'),
        Index('idx_validation_runs_migration', 'migration_id'),
        Index('idx_validation_runs_status', 'status'),
    )

    def __repr__(self):
        return (
            f"<ValidationRun(id={self.id}, workspace_id={self.workspace_id}, "
            f"migration_id={self.migration_id}, status='{self.status}')>"
        )

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'migration_id': self.migration_id,
            'source_connection_id': self.source_connection_id,
            'target_connection_id': self.target_connection_id,
            'bedrock_model': self.bedrock_model,
            'batch_size': self.batch_size,
            'type_mapping_overrides': self.type_mapping_overrides,
            'status': self.status,
            'progress_percentage': self.progress_percentage,
            'tables_total': self.tables_total,
            'tables_passed': self.tables_passed,
            'tables_failed': self.tables_failed,
            'tables_error': self.tables_error,
            'started_at': (self.started_at.isoformat() + 'Z') if self.started_at else None,
            'completed_at': (self.completed_at.isoformat() + 'Z') if self.completed_at else None,
            'duration_seconds': self.duration_seconds,
            'created_by': self.created_by,
            'created_at': (self.created_at.isoformat() + 'Z') if self.created_at else None,
            'updated_at': (self.updated_at.isoformat() + 'Z') if self.updated_at else None,
        }
