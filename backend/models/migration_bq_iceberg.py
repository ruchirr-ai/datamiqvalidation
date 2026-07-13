"""
BigQuery to Iceberg Migration Model

Database model for managing data migrations from BigQuery to Apache Iceberg tables on AWS.
Supports two destination variants: standard Apache Iceberg on S3 and AWS S3 Tables (managed Iceberg).
"""

from sqlalchemy import (
    Column, Integer, String, BigInteger, Boolean, DateTime, Text,
    CheckConstraint, Index
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.sql import func
from database import Base


class MigrationBQIceberg(Base):
    """
    Main migration configuration and state tracking for BigQuery to Iceberg migrations.

    Supports three transfer pathways (A, B, C), two Iceberg destination types
    (iceberg_s3, iceberg_s3_tables), parallel table loading, checkpoint-based resume,
    and a structure review approval checkpoint before the load stage.
    """
    __tablename__ = 'migrations_bq_iceberg'

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, nullable=False)
    migration_name = Column(String(255), nullable=False)
    pathway = Column(String(10), nullable=False)  # A, B, C

    # Source Configuration (BigQuery)
    source_connection_id = Column(Integer, nullable=True)
    source_project_id = Column(String(255))
    source_dataset = Column(String(255))
    source_tables = Column(ARRAY(Text))  # List of table names to migrate

    # Target Configuration (Iceberg)
    target_connection_id = Column(Integer, nullable=True)
    destination_type = Column(String(50), nullable=False)  # iceberg_s3 | iceberg_s3_tables
    s3_bucket = Column(String(255))            # For iceberg_s3
    s3_path_prefix = Column(String(512))       # For iceberg_s3
    table_bucket_arn = Column(String(500))     # For iceberg_s3_tables
    s3_tables_namespace = Column(String(255))  # User-provided namespace for S3 Tables
    aws_region = Column(String(50), nullable=False)
    glue_database_name = Column(String(255), nullable=False)
    dataset_to_db_mapping = Column(JSONB)      # BQ dataset → Glue DB name mapping

    # AWS Credentials (access keys OR role ARN)
    aws_access_key_id = Column(String(255))
    aws_secret_access_key_encrypted = Column(Text)  # Encrypted with KMS
    aws_role_arn = Column(String(500))               # Alternative: IAM Role ARN

    # Intermediate Storage
    gcs_bucket = Column(String(255))
    gcs_path = Column(String(500))
    gcs_region = Column(String(100))
    export_format = Column(String(50), default='PARQUET')
    compression = Column(String(50), default='ZSTD')
    service_account_json_encrypted = Column(Text)

    # Load Configuration
    load_type = Column(String(20), default='full')  # full | incremental
    table_load_configs = Column(JSONB)
    parallelism = Column(Integer, default=4)  # 1-16 concurrent tables
    enable_load_stage_verification = Column(Boolean, default=False)  # Optional Athena check during load

    # State Management
    status = Column(String(50), nullable=False, default='pending')
    # Status values: pending, running, pending_review, approved, paused, completed, failed, cancelled
    current_stage = Column(String(50))   # export, transfer, review, load
    checkpoint_data = Column(JSONB)      # Includes iceberg_structure_plan when approved
    resume_point = Column(String(100))

    # Structure Review
    structure_report = Column(JSONB)
    cost_analysis_report = Column(JSONB)
    structure_approved_at = Column(DateTime)
    structure_approved_by = Column(Integer)

    # Scheduling
    schedule_type = Column(String(50))       # one-time, recurring
    cron_expression = Column(String(100))
    next_run_time = Column(DateTime)

    # Metrics
    total_rows_source = Column(BigInteger)
    total_rows_target = Column(BigInteger)
    total_bytes_transferred = Column(BigInteger)
    progress_percentage = Column(Integer, default=0)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    duration_seconds = Column(Integer)
    last_run_at = Column(DateTime)

    # Metadata
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(),
                        onupdate=func.current_timestamp())

    __table_args__ = (
        CheckConstraint(
            "destination_type IN ('iceberg_s3', 'iceberg_s3_tables')",
            name='check_iceberg_dest_type'
        ),
        CheckConstraint(
            "pathway IN ('A', 'B', 'C')",
            name='check_iceberg_pathway'
        ),
        CheckConstraint(
            "parallelism >= 1 AND parallelism <= 16",
            name='check_parallelism_range'
        ),
        Index('idx_bq_iceberg_workspace_id', 'workspace_id'),
        Index('idx_bq_iceberg_status', 'status'),
        Index('idx_bq_iceberg_destination_type', 'destination_type'),
    )

    def __repr__(self):
        return (
            f"<MigrationBQIceberg(id={self.id}, workspace_id={self.workspace_id}, "
            f"migration_name='{self.migration_name}', status='{self.status}')>"
        )

    def to_dict(self):
        """Convert model to dictionary with both flat and nested field access."""
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'migration_name': self.migration_name,
            'pathway': self.pathway,
            # Flat fields (used by edit form)
            'source_connection_id': self.source_connection_id,
            'source_project_id': self.source_project_id,
            'source_dataset': self.source_dataset,
            'source_tables': self.source_tables,
            'destination_type': self.destination_type,
            's3_bucket': self.s3_bucket,
            's3_path_prefix': self.s3_path_prefix,
            'table_bucket_arn': self.table_bucket_arn,
            's3_tables_namespace': self.s3_tables_namespace,
            'aws_region': self.aws_region,
            'glue_database_name': self.glue_database_name,
            'gcs_bucket': self.gcs_bucket,
            'gcs_path': self.gcs_path,
            'gcs_region': self.gcs_region,
            'status': self.status,
            'current_stage': self.current_stage,
            'progress_percentage': self.progress_percentage,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
            'updated_at': self.updated_at.isoformat() + 'Z' if self.updated_at else None,
            # Nested structure (for backwards compatibility)
            'source': {
                'connection_id': self.source_connection_id,
                'project_id': self.source_project_id,
                'dataset': self.source_dataset,
                'tables': self.source_tables,
            },
            'target': {
                'connection_id': self.target_connection_id,
                'destination_type': self.destination_type,
                's3_bucket': self.s3_bucket,
                's3_path_prefix': self.s3_path_prefix,
                'table_bucket_arn': self.table_bucket_arn,
                's3_tables_namespace': self.s3_tables_namespace,
                'aws_region': self.aws_region,
                'glue_database_name': self.glue_database_name,
                'dataset_to_db_mapping': self.dataset_to_db_mapping,
            },
            'credentials': {
                'aws_access_key_id': self.aws_access_key_id,
                'has_aws_secret_access_key': bool(self.aws_secret_access_key_encrypted),
                'aws_role_arn': self.aws_role_arn,
            },
            'storage': {
                'gcs_bucket': self.gcs_bucket,
                'gcs_path': self.gcs_path,
                'gcs_region': self.gcs_region,
                'export_format': self.export_format,
                'compression': self.compression,
                'has_service_account_json': bool(self.service_account_json_encrypted),
            },
            'load_config': {
                'load_type': self.load_type,
                'table_load_configs': self.table_load_configs,
                'parallelism': self.parallelism,
                'enable_load_stage_verification': self.enable_load_stage_verification,
            },
            'state': {
                'status': self.status,
                'current_stage': self.current_stage,
                'checkpoint_data': self.checkpoint_data,
                'resume_point': self.resume_point,
            },
            'structure_review': {
                'structure_report': self.structure_report,
                'cost_analysis_report': self.cost_analysis_report,
                'structure_approved_at': (
                    self.structure_approved_at.isoformat() + 'Z'
                    if self.structure_approved_at else None
                ),
                'structure_approved_by': self.structure_approved_by,
            },
            'schedule': {
                'type': self.schedule_type,
                'cron_expression': self.cron_expression,
                'next_run_time': (
                    self.next_run_time.isoformat() + 'Z' if self.next_run_time else None
                ),
            },
            'metrics': {
                'total_rows_source': self.total_rows_source,
                'total_rows_target': self.total_rows_target,
                'total_bytes_transferred': self.total_bytes_transferred,
                'progress_percentage': self.progress_percentage,
                'start_time': self.start_time.isoformat() + 'Z' if self.start_time else None,
                'end_time': self.end_time.isoformat() + 'Z' if self.end_time else None,
                'duration_seconds': self.duration_seconds,
                'last_run_at': self.last_run_at.isoformat() + 'Z' if self.last_run_at else None,
            },
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
            'updated_at': self.updated_at.isoformat() + 'Z' if self.updated_at else None,
        }
