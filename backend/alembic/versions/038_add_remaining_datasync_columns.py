"""Add remaining DataSync columns

Revision ID: 038
Revises: 037
"""

from alembic import op
import sqlalchemy as sa


revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("migrations_bq_redshift", sa.Column("datasync_gcp_zone", sa.String(100), nullable=True))
    op.add_column("migrations_bq_redshift", sa.Column("datasync_gcp_machine_type", sa.String(50), nullable=True, server_default="n1-standard-4"))
    op.add_column("migrations_bq_redshift", sa.Column("datasync_gcp_network", sa.String(255), nullable=True))
    op.add_column("migrations_bq_redshift", sa.Column("datasync_gcp_subnet", sa.String(255), nullable=True))
    op.add_column("migrations_bq_redshift", sa.Column("datasync_existing_vm_ip", sa.String(100), nullable=True))
    op.add_column("migrations_bq_redshift", sa.Column("datasync_s3_role_arn", sa.String(500), nullable=True))
    op.add_column("migrations_bq_redshift", sa.Column("datasync_agent_arn", sa.String(500), nullable=True))
    op.add_column("migrations_bq_redshift", sa.Column("datasync_vm_instance_name", sa.String(255), nullable=True))


def downgrade():
    op.drop_column("migrations_bq_redshift", "datasync_vm_instance_name")
    op.drop_column("migrations_bq_redshift", "datasync_agent_arn")
    op.drop_column("migrations_bq_redshift", "datasync_s3_role_arn")
    op.drop_column("migrations_bq_redshift", "datasync_existing_vm_ip")
    op.drop_column("migrations_bq_redshift", "datasync_gcp_subnet")
    op.drop_column("migrations_bq_redshift", "datasync_gcp_network")
    op.drop_column("migrations_bq_redshift", "datasync_gcp_machine_type")
    op.drop_column("migrations_bq_redshift", "datasync_gcp_zone")
