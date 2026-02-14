"""
Assessment Log Model

Stores execution logs for assessments
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base


class AssessmentLog(Base):
    __tablename__ = "assessment_logs"

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, index=True)
    log_level = Column(String(20), nullable=False, index=True)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    message = Column(Text, nullable=False)
    stage = Column(String(100), nullable=True)  # e.g., "initialization", "metadata_collection", "analysis"
    error_code = Column(String(50), nullable=True)
    stack_trace = Column(Text, nullable=True)
    log_metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Relationship
    assessment = relationship("Assessment", back_populates="logs")
