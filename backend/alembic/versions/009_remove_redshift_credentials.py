"""Remove Redshift credentials from migrations table

Revision ID: 009
Revises: 008
Create Date: 2026-02-09

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade():
    """
    Remove target_username and target_password_encrypted columns.
    These are no longer needed as we use target_connection_id to fetch
    connection details from the connections table.
    """
    # Drop columns if they exist
    op.drop_column('migrations_bq_redshift', 'target_username')
    op.drop_column('migrations_bq_redshift', 'target_password_encrypted')


def downgrade():
    """
    Re-add target_username and target_password_encrypted columns.
    """
    op.add_column('migrations_bq_redshift', 
                  sa.Column('target_username', sa.String(255), nullable=True))
    op.add_column('migrations_bq_redshift', 
                  sa.Column('target_password_encrypted', sa.Text(), nullable=True))

