"""
ConversionBatch Model

Database model for batch conversion operations grouping multiple ConversionJobs
under a single migration project batch.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from database import Base


class ConversionBatch(Base):
    """
    Batch conversion record grouping multiple ConversionJobs.

    Tied to a migration project with source/target connections,
    tracks overall batch progress and configuration.
    """
    __tablename__ = 'conversion_batches'

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(Integer, nullable=False)
    batch_name = Column(String(255), nullable=True)
    migration_project_id = Column(Integer, nullable=True)
    source_connection_id = Column(Integer, ForeignKey('connections.id'), nullable=False)
    target_connection_id = Column(Integer, ForeignKey('connections.id'), nullable=False)
    bedrock_model = Column(String(255), nullable=False)
    aws_region = Column(String(50), nullable=False)
    prompt_template_path = Column(String(1024), nullable=False)
    use_sqlglot = Column(Boolean, nullable=False, default=False)
    max_retries = Column(Integer, nullable=False, default=3)
    status = Column(String(50), nullable=False, default='pending')
    total_assets = Column(Integer, nullable=False, default=0)
    completed_assets = Column(Integer, nullable=False, default=0)
    failed_assets = Column(Integer, nullable=False, default=0)
    created_by = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    jobs = relationship("ConversionJob", backref="batch", passive_deletes=True)

    __table_args__ = (
        Index('idx_conversion_batches_workspace', 'workspace_id'),
        Index('idx_conversion_batches_status', 'status'),
        Index('idx_conversion_batches_project', 'migration_project_id'),
    )

    def __repr__(self):
        return (
            f"<ConversionBatch(id={self.id}, workspace_id={self.workspace_id}, "
            f"status='{self.status}', total={self.total_assets})>"
        )

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'batch_name': self.batch_name,
            'migration_project_id': self.migration_project_id,
            'source_connection_id': self.source_connection_id,
            'target_connection_id': self.target_connection_id,
            'bedrock_model': self.bedrock_model,
            'aws_region': self.aws_region,
            'prompt_template_path': self.prompt_template_path,
            'use_sqlglot': self.use_sqlglot,
            'max_retries': self.max_retries,
            'status': self.status,
            'total_assets': self.total_assets,
            'completed_assets': self.completed_assets,
            'failed_assets': self.failed_assets,
            'created_by': self.created_by,
            'created_at': (self.created_at.isoformat() + 'Z') if self.created_at else None,
            'updated_at': (self.updated_at.isoformat() + 'Z') if self.updated_at else None,
        }
