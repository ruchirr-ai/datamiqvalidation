"""
BigQuery to Redshift Migration Models

Database models for managing large-scale data migrations from BigQuery to Redshift.
"""

from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Text, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class MigrationBQRedshift(Base):
    """
    Main migration configuration and state tracking table.
    Supports four migration pathways (A, B, C, D) with checkpointing and resumability.
    """
    __tablename__ = 'migrations_bq_redshift'
    
    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, nullable=False, default=1)  # Temporarily removed FK constraint
    migration_name = Column(String(255), nullable=False)
    pathway = Column(String(10), nullable=False)  # A, B, C, or D
    
    # Source Configuration (BigQuery)
    source_connection_id = Column(Integer, nullable=True)  # FK removed - references connections.id
    source_project_id = Column(String(255))
    source_dataset = Column(String(255))
    source_tables = Column(ARRAY(Text))  # List of table names to migrate
    
    # Target Configuration (Redshift)
    target_connection_id = Column(Integer, nullable=True)  # FK removed - references connections.id
    target_cluster = Column(String(255))
    target_database = Column(String(255))
    target_schema = Column(String(255))
    # target_username and target_password_encrypted removed - use target_connection_id instead
    iam_role_arn = Column(String(500))  # IAM role for Redshift S3 access
    
    # Intermediate Storage
    gcs_bucket = Column(String(255))  # Google Cloud Storage bucket
    gcs_path = Column(String(500))    # Path within GCS bucket
    s3_bucket = Column(String(255))   # AWS S3 bucket
    s3_path = Column(String(500))     # Path within S3 bucket
    
    # Export Configuration
    export_format = Column(String(50), default='AVRO')  # AVRO, PARQUET, CSV, JSON
    compression = Column(String(50), default='NONE')    # NONE, GZIP, SNAPPY, DEFLATE, ZSTD
    
    # AWS Credentials for GCS → S3 Transfer
    aws_access_key_id = Column(String(255))
    aws_secret_access_key_encrypted = Column(Text)  # Encrypted with KMS
    
    # Transfer Configuration
    transfer_job_name = Column(String(500))  # GCP Storage Transfer Service job name
    overwrite_existing_files = Column(String(10), default='false')
    delete_source_after_transfer = Column(String(10), default='false')
    
    # State Management
    status = Column(String(50), nullable=False, default='pending')
    # Status values: pending, running, paused, completed, failed, cancelled
    current_stage = Column(String(50))  # export, transfer, load
    checkpoint_data = Column(JSONB)     # Detailed checkpoint information
    manifest_uri = Column(Text)         # URI to manifest file
    resume_point = Column(String(100))  # Where to resume from
    
    # Scheduling
    schedule_type = Column(String(50))  # one-time, recurring
    cron_expression = Column(String(100))  # CRON expression for recurring
    next_run_time = Column(DateTime)    # Next scheduled run
    
    # Metrics
    total_rows_source = Column(BigInteger)      # Total rows in source
    total_rows_target = Column(BigInteger)      # Total rows loaded to target
    total_bytes_transferred = Column(BigInteger)  # Total bytes transferred
    progress_percentage = Column(Integer, default=0)  # Overall progress (0-100)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    duration_seconds = Column(Integer)
    last_run_at = Column(DateTime)              # Last execution timestamp
    
    # Metadata
    created_by = Column(Integer, nullable=True)  # Temporarily removed FK constraint
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # Relationships removed - no FK constraints in database
    
    # Constraints
    __table_args__ = (
        CheckConstraint("pathway IN ('A', 'B', 'C')", name='check_pathway'),
        # UniqueConstraint removed temporarily until workspace support is added
    )
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'migration_name': self.migration_name,
            'pathway': self.pathway,
            'source': {
                'connection_id': self.source_connection_id,
                'project_id': self.source_project_id,
                'dataset': self.source_dataset,
                'tables': self.source_tables
            },
            'target': {
                'connection_id': self.target_connection_id,
                'cluster': self.target_cluster,
                'database': self.target_database,
                'schema': self.target_schema
            },
            'storage': {
                'gcs_bucket': self.gcs_bucket,
                'gcs_path': self.gcs_path,
                's3_bucket': self.s3_bucket,
                's3_path': self.s3_path,
                'export_format': self.export_format,
                'compression': self.compression
            },
            'state': {
                'status': self.status,
                'current_stage': self.current_stage,
                'checkpoint_data': self.checkpoint_data,
                'manifest_uri': self.manifest_uri,
                'resume_point': self.resume_point
            },
            'schedule': {
                'type': self.schedule_type,
                'cron_expression': self.cron_expression,
                'next_run_time': self.next_run_time.isoformat() if self.next_run_time else None
            },
            'metrics': {
                'total_rows_source': self.total_rows_source,
                'total_rows_target': self.total_rows_target,
                'total_bytes_transferred': self.total_bytes_transferred,
                'start_time': self.start_time.isoformat() if self.start_time else None,
                'end_time': self.end_time.isoformat() if self.end_time else None,
                'duration_seconds': self.duration_seconds,
                'last_run_at': self.last_run_at.isoformat() if self.last_run_at else None
            },
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class MigrationShard(Base):
    """
    Individual shard tracking for granular resume capability.
    Each BigQuery export creates multiple shards (files) that are tracked independently.
    """
    __tablename__ = 'migration_shards'
    
    id = Column(Integer, primary_key=True)
    migration_id = Column(Integer, nullable=False)  # FK removed - references migrations_bq_redshift.id
    shard_index = Column(Integer, nullable=False)
    table_name = Column(String(255), nullable=False)
    
    # Shard Details
    gcs_uri = Column(Text)              # Full GCS URI (gs://bucket/path/file)
    s3_uri = Column(Text)               # Full S3 URI (s3://bucket/path/file)
    file_size_bytes = Column(BigInteger)
    row_count = Column(BigInteger)
    checksum = Column(String(64))       # SHA256 checksum for validation
    
    # Status Tracking (each stage tracked independently)
    export_status = Column(String(50), nullable=False, default='pending')
    export_completed_at = Column(DateTime)
    transfer_status = Column(String(50), nullable=False, default='pending')
    transfer_completed_at = Column(DateTime)
    load_status = Column(String(50), nullable=False, default='pending')
    load_completed_at = Column(DateTime)
    # Status values: pending, running, completed, failed
    
    # Error Handling
    retry_count = Column(Integer, nullable=False, default=0)
    last_error = Column(Text)
    last_error_time = Column(DateTime)
    
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # Relationships removed - no FK constraints in database
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('migration_id', 'table_name', 'shard_index', name='unique_shard_per_migration'),
    )
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'migration_id': self.migration_id,
            'shard_index': self.shard_index,
            'table_name': self.table_name,
            'gcs_uri': self.gcs_uri,
            's3_uri': self.s3_uri,
            'file_size_bytes': self.file_size_bytes,
            'row_count': self.row_count,
            'checksum': self.checksum,
            'status': {
                'export': self.export_status,
                'export_completed_at': self.export_completed_at.isoformat() if self.export_completed_at else None,
                'transfer': self.transfer_status,
                'transfer_completed_at': self.transfer_completed_at.isoformat() if self.transfer_completed_at else None,
                'load': self.load_status,
                'load_completed_at': self.load_completed_at.isoformat() if self.load_completed_at else None
            },
            'retry_count': self.retry_count,
            'last_error': self.last_error,
            'last_error_time': self.last_error_time.isoformat() if self.last_error_time else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def is_completed(self):
        """Check if shard is fully completed"""
        return (
            self.export_status == 'completed' and
            self.transfer_status == 'completed' and
            self.load_status == 'completed'
        )
    
    def has_failed(self):
        """Check if shard has failed at any stage"""
        return (
            self.export_status == 'failed' or
            self.transfer_status == 'failed' or
            self.load_status == 'failed'
        )


class MigrationLog(Base):
    """
    Detailed logging for migration operations.
    Provides observability and debugging capabilities.
    """
    __tablename__ = 'migration_logs'
    
    id = Column(Integer, primary_key=True)
    migration_id = Column(Integer, nullable=False)  # FK removed - references migrations_bq_redshift.id
    shard_id = Column(Integer, nullable=True)  # FK removed - references migration_shards.id
    
    log_level = Column(String(20), nullable=False)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    stage = Column(String(50), nullable=False)      # export, transfer, load
    message = Column(Text, nullable=False)
    error_code = Column(String(50))                 # Specific error code for categorization
    stack_trace = Column(Text)                      # Full stack trace for errors
    log_metadata = Column(JSONB)                    # Additional context data (renamed from metadata)
    
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    
    # Relationships removed - no FK constraints in database
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'migration_id': self.migration_id,
            'shard_id': self.shard_id,
            'log_level': self.log_level,
            'stage': self.stage,
            'message': self.message,
            'error_code': self.error_code,
            'stack_trace': self.stack_trace,
            'log_metadata': self.log_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
