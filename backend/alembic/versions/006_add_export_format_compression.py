"""Add export_format and compression columns to migrations_bq_redshift

Revision ID: 006
Revises: 005
Create Date: 2026-02-08

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    """Add export_format, compression, and progress_percentage columns"""
    op.add_column(
        'migrations_bq_redshift',
        sa.Column('export_format', sa.String(50), nullable=True, server_default='AVRO')
    )
    op.add_column(
        'migrations_bq_redshift',
        sa.Column('compression', sa.String(50), nullable=True, server_default='NONE')
    )
    op.add_column(
        'migrations_bq_redshift',
        sa.Column('progress_percentage', sa.Integer, nullable=True, server_default='0')
    )
    
    # Update existing rows to have default values
    op.execute("UPDATE migrations_bq_redshift SET export_format = 'AVRO' WHERE export_format IS NULL")
    op.execute("UPDATE migrations_bq_redshift SET compression = 'NONE' WHERE compression IS NULL")
    op.execute("UPDATE migrations_bq_redshift SET progress_percentage = 0 WHERE progress_percentage IS NULL")


def downgrade():
    """Remove export_format, compression, and progress_percentage columns"""
    op.drop_column('migrations_bq_redshift', 'progress_percentage')
    op.drop_column('migrations_bq_redshift', 'compression')
    op.drop_column('migrations_bq_redshift', 'export_format')
