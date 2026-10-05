"""add validation config to validation runs

Revision ID: fa9d4cb18f15
Revises: 040
Create Date: 2026-09-26 17:49:23.051289
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "fa9d4cb18f15"
down_revision = "040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "validation_runs",
        sa.Column(
            "validation_config",
            sa.JSON(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "validation_runs",
        "validation_config",
    )
