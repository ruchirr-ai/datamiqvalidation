"""
Conversion Job Database Models

SQLAlchemy ORM models for conversion tables.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, BigInteger, JSON
from sqlalchemy.orm import relationship
from database import Base


class ConversionJob(Base):
    """SQLAlchemy model for conversion_jobs table"""
    __tablename__ = 'conversion_jobs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(Integer, nullable=False, index=True)
    batch_id = Column(Integer, ForeignKey('conversion_batches.id', ondelete='CASCADE'), nullable=True, index=True)
    source_code = Column(Text, nullable=False)
    target_code = Column(Text, nullable=True)
    source_dialect = Column(String(50), nullable=False)
    target_dialect = Column(String(50), nullable=False)
    asset_type = Column(String(50), nullable=False)
    asset_name = Column(String(255), nullable=True)
    bedrock_model = Column(String(100), nullable=True)
    aws_region = Column(String(50), nullable=True)
    use_sqlglot = Column(Boolean, nullable=False, default=True)
    sqlglot_success = Column(Boolean, nullable=True)
    prompt_template_path = Column(String(500), nullable=True)
    status = Column(String(50), nullable=False, default='pending', index=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    batch = relationship("ConversionBatch", back_populates="jobs")
    logs = relationship("ConversionLog", back_populates="job", cascade="all, delete-orphan")
    
    def to_dict(self):
        """Convert to dictionary"""
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
            'use_sqlglot': self.use_sqlglot,
            'sqlglot_success': self.sqlglot_success,
            'prompt_template_path': self.prompt_template_path,
            'status': self.status,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'created_by': self.created_by,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }


class ConversionBatch(Base):
    """SQLAlchemy model for conversion_batches table"""
    __tablename__ = 'conversion_batches'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(Integer, nullable=False, index=True)
    source_connection_id = Column(Integer, ForeignKey('connections.id'), nullable=False)
    target_connection_id = Column(Integer, ForeignKey('connections.id'), nullable=False)
    total_assets = Column(Integer, nullable=False, default=0)
    completed_assets = Column(Integer, nullable=False, default=0)
    failed_assets = Column(Integer, nullable=False, default=0)
    status = Column(String(50), nullable=False, default='pending', index=True)
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    jobs = relationship("ConversionJob", back_populates="batch")
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'source_connection_id': self.source_connection_id,
            'target_connection_id': self.target_connection_id,
            'total_assets': self.total_assets,
            'completed_assets': self.completed_assets,
            'failed_assets': self.failed_assets,
            'status': self.status,
            'created_by': self.created_by,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }


class ConversionLog(Base):
    """SQLAlchemy model for conversion_logs table"""
    __tablename__ = 'conversion_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey('conversion_jobs.id', ondelete='CASCADE'), nullable=False, index=True)
    workspace_id = Column(Integer, nullable=False, index=True)
    log_level = Column(String(20), nullable=False, default='INFO')
    step_name = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    duration_ms = Column(Integer, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Relationship
    job = relationship("ConversionJob", back_populates="logs")
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'job_id': self.job_id,
            'workspace_id': self.workspace_id,
            'log_level': self.log_level,
            'step_name': self.step_name,
            'message': self.message,
            'duration_ms': self.duration_ms,
            'timestamp': self.timestamp
        }
