"""
ClickHouse Migration Model

Database model for persisting BigQuery → GCS → ClickHouse migration state.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, BigInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from database import Base


class ClickHouseMigration(Base):
    """Tracks ClickHouse migration jobs and their state."""

    __tablename__ = 'migrations_clickhouse'

    id = Column(Integer, primary_key=True)
    migration_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default='pending')
    # pending, running, completed, failed

    source_connection_id = Column(Integer, nullable=False)
    target_connection_id = Column(Integer, nullable=False)

    total_tables = Column(Integer, default=0)
    completed_tables = Column(Integer, default=0)
    failed_tables = Column(Integer, default=0)

    current_table = Column(String(255), nullable=True)
    current_stage = Column(String(50), nullable=True)

    # Configuration stored as JSON
    config = Column(JSONB, nullable=True)
    selected_tables = Column(JSONB, nullable=True)

    # Results per table
    table_results = Column(JSONB, default=[])

    # Logs
    logs = Column(JSONB, default=[])

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
