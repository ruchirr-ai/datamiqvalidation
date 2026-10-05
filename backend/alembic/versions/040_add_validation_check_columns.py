"""Add validation check columns to validation table results

Revision ID: 040
Revises: 039
"""

from alembic import op
import sqlalchemy as sa


revision = "040"
down_revision = "039"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "validation_table_results",
        sa.Column("null_check", sa.Boolean(), nullable=False, server_default="false")
    )
    op.add_column(
        "validation_table_results",
        sa.Column("duplicate_check", sa.Boolean(), nullable=False, server_default="false")
    )
    op.add_column(
        "validation_table_results",
        sa.Column("sum_check", sa.Boolean(), nullable=False, server_default="false")
    )
    op.add_column(
        "validation_table_results",
        sa.Column("average_check", sa.Boolean(), nullable=False, server_default="false")
    )
    op.add_column(
        "validation_table_results",
        sa.Column("specific_row_check", sa.Boolean(), nullable=False, server_default="false")
    )

    op.add_column(
        "validation_table_results",
        sa.Column("null_status", sa.String(50), nullable=True)
    )
    op.add_column(
        "validation_table_results",
        sa.Column("null_result", sa.JSON(), nullable=True)
    )
    op.add_column(
        "validation_table_results",
        sa.Column("duplicate_status", sa.String(50), nullable=True)
    )
    op.add_column(
        "validation_table_results",
        sa.Column("duplicate_result", sa.JSON(), nullable=True)
    )
    op.add_column(
        "validation_table_results",
        sa.Column("sum_status", sa.String(50), nullable=True)
    )
    op.add_column(
        "validation_table_results",
        sa.Column("sum_result", sa.JSON(), nullable=True)
    )
    op.add_column(
        "validation_table_results",
        sa.Column("average_status", sa.String(50), nullable=True)
    )
    op.add_column(
        "validation_table_results",
        sa.Column("average_result", sa.JSON(), nullable=True)
    )
    op.add_column(
        "validation_table_results",
        sa.Column("specific_row_status", sa.String(50), nullable=True)
    )
    op.add_column(
        "validation_table_results",
        sa.Column("specific_row_result", sa.JSON(), nullable=True)
    )


def downgrade():
    op.drop_column("validation_table_results", "specific_row_result")
    op.drop_column("validation_table_results", "specific_row_status")
    op.drop_column("validation_table_results", "average_result")
    op.drop_column("validation_table_results", "average_status")
    op.drop_column("validation_table_results", "sum_result")
    op.drop_column("validation_table_results", "sum_status")
    op.drop_column("validation_table_results", "duplicate_result")
    op.drop_column("validation_table_results", "duplicate_status")
    op.drop_column("validation_table_results", "null_result")
    op.drop_column("validation_table_results", "null_status")
    op.drop_column("validation_table_results", "specific_row_check")
    op.drop_column("validation_table_results", "average_check")
    op.drop_column("validation_table_results", "sum_check")
    op.drop_column("validation_table_results", "duplicate_check")
    op.drop_column("validation_table_results", "null_check")
