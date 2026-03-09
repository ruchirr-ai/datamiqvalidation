"""
ConversionJob Model

Database model for individual code conversion jobs (standalone or batch items).
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Index
from database import Base


class ConversionJob(Base):
    """
    Individual conversion job record.

    Represents a single code conversion request. Standalone conversions have
    batch_id=None; batch items reference a parent ConversionBatch.
    """
    __tablename__ = 'conversion_jobs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(Integer, nullable=False)
    batch_id = Column(
        Integer,
        ForeignKey('conversion_batches.id', ondelete='SET NULL'),
        nullable=True,
    )
    source_code = Column(Text, nullable=False)
    target_code = Column(Text, nullable=True)
    source_dialect = Column(String(50), nullable=False)
    target_dialect = Column(String(50), nullable=False)
    asset_type = Column(String(50), nullable=False)
    asset_name = Column(String(255), nullable=True)
    bedrock_model = Column(String(255), nullable=False)
    aws_region = Column(String(50), nullable=False)
    prompt_template_path = Column(String(1024), nullable=False)
    use_sqlglot = Column(Boolean, nullable=False, default=False)
    sqlglot_success = Column(Boolean, nullable=True)
    status = Column(String(50), nullable=False, default='pending')
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    created_by = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_conversion_jobs_workspace', 'workspace_id'),
        Index('idx_conversion_jobs_batch', 'batch_id'),
        Index('idx_conversion_jobs_status', 'status'),
        Index('idx_conversion_jobs_asset_type', 'asset_type'),
    )

    def __repr__(self):
        return (
            f"<ConversionJob(id={self.id}, workspace_id={self.workspace_id}, "
            f"status='{self.status}', asset_type='{self.asset_type}')>"
        )

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'batch_id': self.batch_id,
            'source_code': self.source_code,
            'target_code': self.target_code,
            'source_dialect': self.source_dialect,
            'target_dialect': self.target_dialect,
            'asset_type': self.asset_type,
            'asset_name': self.asset_name,
            'bedrock_model': self.bedrock_model,
            'aws_region': self.aws_region,
            'prompt_template_path': self.prompt_template_path,
            'use_sqlglot': self.use_sqlglot,
            'sqlglot_success': self.sqlglot_success,
            'status': self.status,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'created_by': self.created_by,
            'created_at': (self.created_at.isoformat() + 'Z') if self.created_at else None,
            'updated_at': (self.updated_at.isoformat() + 'Z') if self.updated_at else None,
        }
