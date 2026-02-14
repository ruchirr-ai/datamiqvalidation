"""add redshift credentials

Revision ID: 008
Revises: 007
Create Date: 2026-02-09

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade():
    """Add Redshift credential fields to migrations_bq_redshift table"""
    
    # Add target_username column
    op.add_column(
        'migrations_bq_redshift',
        sa.Column('target_username', sa.String(255), nullable=True)
    )
    
    # Add target_password_encrypted column
    op.add_column(
        'migrations_bq_redshift',
        sa.Column('target_password_encrypted', sa.Text(), nullable=True)
    )
    
    # Add iam_role_arn column
    op.add_column(
        'migrations_bq_redshift',
        sa.Column('iam_role_arn', sa.String(500), nullable=True)
    )


def downgrade():
    """Remove Redshift credential fields from migrations_bq_redshift table"""
    
    op.drop_column('migrations_bq_redshift', 'iam_role_arn')
    op.drop_column('migrations_bq_redshift', 'target_password_encrypted')
    op.drop_column('migrations_bq_redshift', 'target_username')
