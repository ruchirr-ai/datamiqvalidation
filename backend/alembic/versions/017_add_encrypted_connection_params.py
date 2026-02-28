"""add encrypted connection params

Revision ID: 017
Revises: 016
Create Date: 2026-02-16 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '017'
down_revision = '016_add_dependency_fields'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add connection_params_encrypted column to connections table.
    
    This column will store KMS-encrypted connection parameters for enhanced security.
    The old connection_params column is kept for backward compatibility during migration.
    """
    # Add new encrypted column
    op.add_column('connections', sa.Column('connection_params_encrypted', sa.Text(), nullable=True))
    
    # Add index for faster lookups
    op.create_index(
        'idx_connections_encrypted_params',
        'connections',
        ['connection_params_encrypted'],
        unique=False,
        postgresql_where=sa.text('connection_params_encrypted IS NOT NULL')
    )
    
    print("✓ Added connection_params_encrypted column to connections table")
    print("✓ Added index on connection_params_encrypted")
    print("")
    print("NEXT STEPS:")
    print("1. Run migration script: python scripts/migrate_to_kms_encryption.py")
    print("2. Verify all connections have encrypted params")
    print("3. After verification, optionally drop connection_params column")


def downgrade():
    """
    Remove connection_params_encrypted column.
    
    WARNING: This will remove all encrypted connection parameters!
    Make sure to backup data before downgrading.
    """
    # Drop index
    op.drop_index('idx_connections_encrypted_params', table_name='connections')
    
    # Drop column
    op.drop_column('connections', 'connection_params_encrypted')
    
    print("✗ Removed connection_params_encrypted column from connections table")
    print("⚠️  WARNING: All encrypted connection parameters have been removed!")
