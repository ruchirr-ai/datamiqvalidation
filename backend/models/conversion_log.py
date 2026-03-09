"""
ConversionLog Model

Database model for structured conversion processing step logs,
associated with individual ConversionJob records.
"""

from enum import Enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from database import Base


class ConversionLogStepName(str, Enum):
    """Step names emitted during conversion processing."""
    TEMPLATE_LOADED = "template_loaded"
    SQLGLOT_PARSE_STARTED = "sqlglot_parse_started"
    SQLGLOT_PARSE_COMPLETED = "sqlglot_parse_completed"
    SQLGLOT_PARSE_FAILED = "sqlglot_parse_failed"
    BEDROCK_INVOCATION_STARTED = "bedrock_invocation_started"
    BEDROCK_INVOCATION_COMPLETED = "bedrock_invocation_completed"
    BEDROCK_INVOCATION_FAILED = "bedrock_invocation_failed"
    RETRY_ATTEMPTED = "retry_attempted"
    CONVERSION_COMPLETED = "conversion_completed"
    CONVERSION_FAILED = "conversion_failed"


class ConversionLog(Base):
    """
    Structured log entry for a conversion processing step.

    Each record captures one step in the conversion pipeline
    (template loading, parsing, Bedrock invocation, etc.) and is
    associated with a ConversionJob via job_id.
    """
    __tablename__ = 'conversion_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(
        Integer,
        ForeignKey('conversion_jobs.id', ondelete='CASCADE'),
        nullable=False,
    )
    workspace_id = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    log_level = Column(String(10), nullable=False, default='INFO')
    step_name = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    duration_ms = Column(Integer, nullable=True)

    __table_args__ = (
        Index('idx_conversion_logs_job', 'job_id'),
        Index('idx_conversion_logs_workspace', 'workspace_id'),
    )

    def __repr__(self):
        return (
            f"<ConversionLog(id={self.id}, job_id={self.job_id}, "
            f"step='{self.step_name}', level='{self.log_level}')>"
        )
