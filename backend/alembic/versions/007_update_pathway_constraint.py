"""Update pathway constraint to A, B, C

Revision ID: 007
Revises: 006
Create Date: 2026-02-09

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    """
    Update pathway constraint from (A, B, C, D) to (A, B, C)
    
    Pathway restructuring:
    - Old Path A (GCP Transfer Service) removed - not supported for GCS→S3
    - Old Path B → New Path A (AWS DMS)
    - Old Path C → New Path B (AWS DataSync)
    - Old Path D → New Path C (CLI/Legacy)
    """
    # Drop old constraint if it exists
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT constraint_name 
        FROM information_schema.table_constraints 
        WHERE table_name = 'migrations_bq_redshift' 
        AND constraint_name = 'check_pathway'
    """))
    
    if result.fetchone():
        op.drop_constraint('check_pathway', 'migrations_bq_redshift', type_='check')
    
    # Update existing data
    # Convert old Path B to new Path A
    op.execute("UPDATE migrations_bq_redshift SET pathway = 'A' WHERE pathway = 'B'")
    
    # Convert old Path C to new Path B
    op.execute("UPDATE migrations_bq_redshift SET pathway = 'B' WHERE pathway = 'C'")
    
    # Convert old Path D to new Path C
    op.execute("UPDATE migrations_bq_redshift SET pathway = 'C' WHERE pathway = 'D'")
    
    # Note: Old Path A migrations will fail validation after this migration
    # They should be deleted or manually updated before running this migration
    
    # Add new constraint
    op.create_check_constraint(
        'check_pathway',
        'migrations_bq_redshift',
        "pathway IN ('A', 'B', 'C')"
    )


def downgrade():
    """Revert to old pathway constraint"""
    # Drop new constraint
    op.drop_constraint('check_pathway', 'migrations_bq_redshift', type_='check')
    
    # Revert data (reverse mapping)
    # New Path A → Old Path B
    op.execute("UPDATE migrations_bq_redshift SET pathway = 'B' WHERE pathway = 'A'")
    
    # New Path B → Old Path C
    op.execute("UPDATE migrations_bq_redshift SET pathway = 'C' WHERE pathway = 'B'")
    
    # New Path C → Old Path D
    op.execute("UPDATE migrations_bq_redshift SET pathway = 'D' WHERE pathway = 'C'")
    
    # Add old constraint
    op.create_check_constraint(
        'check_pathway',
        'migrations_bq_redshift',
        "pathway IN ('A', 'B', 'C', 'D')"
    )
