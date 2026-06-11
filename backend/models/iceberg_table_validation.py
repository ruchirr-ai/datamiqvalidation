"""
Iceberg Table Validation Model

Database model for per-table validation results of BigQuery to Iceberg migrations.
Tracks row count comparisons and match status for each migrated table.
"""

from sqlalchemy import (
    Column, Integer, String, BigInteger, DateTime, Text,
    ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.sql import func
from database import Base


class IcebergTableValidation(Base):
    """
    Per-table validation results for Iceberg migrations.

    Stores row count comparisons between BigQuery source and Iceberg target,
    supporting both full-load (exact match) and incremental-load (delta check) validation.
    """
    __tablename__ = 'iceberg_table_validations'

    id = Column(Integer, primary_key=True)
    migration_id = Column(Integer, ForeignKey('migrations_bq_iceberg.id'), nullable=False)
    table_name = Column(String(255), nullable=False)
    source_row_count = Column(BigInteger)
    target_row_count = Column(BigInteger)
    match_status = Column(String(50))  # passed, failed, skipped
    validation_type = Column(String(20))  # full, incremental
    batch_export_count = Column(BigInteger)  # For incremental: rows in this batch
    previous_snapshot_count = Column(BigInteger)  # For incremental: count before load
    error_reason = Column(Text)
    validated_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint('migration_id', 'table_name', name='unique_iceberg_validation'),
        Index('idx_iceberg_validation_migration_id', 'migration_id'),
    )

    def __repr__(self):
        return (
            f"<IcebergTableValidation(id={self.id}, migration_id={self.migration_id}, "
            f"table_name='{self.table_name}', match_status='{self.match_status}')>"
        )

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'migration_id': self.migration_id,
            'table_name': self.table_name,
            'source_row_count': self.source_row_count,
            'target_row_count': self.target_row_count,
            'match_status': self.match_status,
            'validation_type': self.validation_type,
            'batch_export_count': self.batch_export_count,
            'previous_snapshot_count': self.previous_snapshot_count,
            'error_reason': self.error_reason,
            'validated_at': (
                self.validated_at.isoformat() + 'Z' if self.validated_at else None
            ),
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
        }
