"""
DirectValidationConfig Model

Database model for saved direct (connection-to-connection) validation
configurations. Stores the reusable *setup* (source/target connections,
table pairs, and per-pair checks) so a direct validation can be re-run
with a single click. Results are intentionally NOT persisted here;
direct validations remain ephemeral by product decision.

Scoped to a workspace for tenant isolation.
"""

from sqlalchemy import Column, Integer, String, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from database import Base


class DirectValidationConfig(Base):
    """
    Saved configuration for a direct connection-to-connection validation.

    The ``config`` JSON holds the table pairs and per-pair check settings
    exactly as produced by the validation wizard in connection mode, so the
    frontend can repopulate the form on load.
    """
    __tablename__ = 'direct_validation_configs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(Integer, nullable=False)
    name = Column(String(255), nullable=False)
    source_connection_id = Column(Integer, nullable=False)
    target_connection_id = Column(Integer, nullable=False)

    # Stores table pairs and their per-pair validation check configuration.
    config = Column(JSONB, nullable=False)

    created_by = Column(String(255), nullable=False)

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp()
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp()
    )

    __table_args__ = (
        Index('idx_direct_validation_configs_workspace', 'workspace_id'),
    )

    def __repr__(self):
        return (
            f"<DirectValidationConfig(id={self.id}, "
            f"workspace_id={self.workspace_id}, name='{self.name}')>"
        )

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'name': self.name,
            'source_connection_id': self.source_connection_id,
            'target_connection_id': self.target_connection_id,
            'config': self.config,
            'created_by': self.created_by,
            'created_at': (
                self.created_at.isoformat() + 'Z'
                if self.created_at
                else None
            ),
            'updated_at': (
                self.updated_at.isoformat() + 'Z'
                if self.updated_at
                else None
            ),
        }
