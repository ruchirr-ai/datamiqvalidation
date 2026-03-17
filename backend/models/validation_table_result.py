"""
ValidationTableResult Model

Database model for per-table validation results including DDL comparison,
row count verification, and record-level data matching outcomes.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from database import Base


class ValidationTableResult(Base):
    """
    Per-table validation outcome for a ValidationRun.

    Stores DDL comparison, row count check, and record-level match results
    along with optional AI-powered discrepancy analysis. Scoped to a
    workspace for tenant isolation.
    """
    __tablename__ = 'validation_table_results'

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey('validation_runs.id', ondelete='CASCADE'), nullable=False)
    workspace_id = Column(Integer, nullable=False)
    table_name = Column(String(255), nullable=False)
    dataset_name = Column(String(255), nullable=True)
    ddl_check = Column(Boolean, nullable=False, server_default='true')
    row_count_check = Column(Boolean, nullable=False, server_default='true')
    data_match_check = Column(Boolean, nullable=False, server_default='true')
    ddl_status = Column(String(50), nullable=True)
    ddl_comparison_result = Column(JSONB, nullable=True)
    row_count_status = Column(String(50), nullable=True)
    row_count_result = Column(JSONB, nullable=True)
    data_match_status = Column(String(50), nullable=True)
    data_match_result = Column(JSONB, nullable=True)
    ai_analysis = Column(JSONB, nullable=True)
    status = Column(String(50), nullable=False, default='pending')
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(),
                        onupdate=func.current_timestamp())

    __table_args__ = (
        Index('idx_vtresults_run', 'run_id'),
        Index('idx_vtresults_workspace', 'workspace_id'),
        Index('idx_vtresults_table_name', 'table_name'),
        Index('idx_vtresults_status', 'status'),
    )

    def __repr__(self):
        return (
            f"<ValidationTableResult(id={self.id}, run_id={self.run_id}, "
            f"table_name='{self.table_name}', status='{self.status}')>"
        )

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'run_id': self.run_id,
            'workspace_id': self.workspace_id,
            'table_name': self.table_name,
            'dataset_name': self.dataset_name,
            'ddl_check': self.ddl_check,
            'row_count_check': self.row_count_check,
            'data_match_check': self.data_match_check,
            'ddl_status': self.ddl_status,
            'ddl_comparison_result': self.ddl_comparison_result,
            'row_count_status': self.row_count_status,
            'row_count_result': self.row_count_result,
            'data_match_status': self.data_match_status,
            'data_match_result': self.data_match_result,
            'ai_analysis': self.ai_analysis,
            'status': self.status,
            'error_message': self.error_message,
            'started_at': (self.started_at.isoformat() + 'Z') if self.started_at else None,
            'completed_at': (self.completed_at.isoformat() + 'Z') if self.completed_at else None,
            'duration_seconds': self.duration_seconds,
            'created_at': (self.created_at.isoformat() + 'Z') if self.created_at else None,
            'updated_at': (self.updated_at.isoformat() + 'Z') if self.updated_at else None,
        }
