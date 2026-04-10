"""
Assessment models for BigQuery metadata extraction and analysis.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, Float, TIMESTAMP, BigInteger, ARRAY, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Assessment(Base):
    """Main assessment record tracking BigQuery metadata extraction."""
    
    __tablename__ = 'assessments'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    source_connection_id = Column(Integer, ForeignKey('connections.id'), nullable=False)
    target_connection_id = Column(Integer, ForeignKey('connections.id'), nullable=True)
    project_id = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default='pending')  # pending, running, completed, failed
    started_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    completed_at = Column(TIMESTAMP, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Summary statistics
    total_datasets = Column(Integer, default=0)
    total_tables = Column(Integer, default=0)
    total_views = Column(Integer, default=0)
    total_routines = Column(Integer, default=0)
    total_ml_models = Column(Integer, default=0)
    total_size_mb = Column(BigInteger, default=0)
    
    # Full assessment data (JSONB for flexibility)
    assessment_data = Column(JSONB, nullable=True)
    
    # Audit fields
    created_by = Column(String(255), nullable=True)
    workspace_id = Column(Integer, nullable=False)
    version = Column(Integer, nullable=False, default=1, server_default='1')
    
    # Relationships
    datasets = relationship("AssessmentDataset", back_populates="assessment", cascade="all, delete-orphan")
    tables = relationship("AssessmentTable", back_populates="assessment", cascade="all, delete-orphan")
    views = relationship("AssessmentView", back_populates="assessment", cascade="all, delete-orphan")
    routines = relationship("AssessmentRoutine", back_populates="assessment", cascade="all, delete-orphan")
    query_stats = relationship("AssessmentQueryStat", back_populates="assessment", cascade="all, delete-orphan")
    ml_models = relationship("AssessmentMLModel", back_populates="assessment", cascade="all, delete-orphan")
    security_policies = relationship("AssessmentSecurity", back_populates="assessment", cascade="all, delete-orphan")
    sharded_tables = relationship("AssessmentShardedTable", back_populates="assessment", cascade="all, delete-orphan")
    indexes = relationship("AssessmentIndex", back_populates="assessment", cascade="all, delete-orphan")
    logs = relationship("AssessmentLog", back_populates="assessment", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_assessments_source_connection', 'source_connection_id'),
        Index('idx_assessments_target_connection', 'target_connection_id'),
        Index('idx_assessments_workspace', 'workspace_id'),
        Index('idx_assessments_status', 'status'),
    )


class AssessmentDataset(Base):
    """Dataset (database) metadata."""
    
    __tablename__ = 'assessment_datasets'
    
    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey('assessments.id', ondelete='CASCADE'), nullable=False)
    dataset_name = Column(String(255), nullable=False)
    creation_time = Column(TIMESTAMP, nullable=True)
    location = Column(String(100), nullable=True)
    table_count = Column(Integer, default=0)
    total_size_mb = Column(BigInteger, default=0)
    dataset_metadata = Column(JSONB, nullable=True)
    
    # Relationships
    assessment = relationship("Assessment", back_populates="datasets")
    
    __table_args__ = (
        Index('idx_assessment_datasets_assessment', 'assessment_id'),
        Index('idx_assessment_datasets_unique', 'assessment_id', 'dataset_name', unique=True),
    )


class AssessmentTable(Base):
    """Table metadata including partitioning, clustering, and security."""
    
    __tablename__ = 'assessment_tables'
    
    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey('assessments.id', ondelete='CASCADE'), nullable=False)
    project_id = Column(String(255), nullable=False)
    dataset_name = Column(String(255), nullable=False)
    table_name = Column(String(255), nullable=False)
    table_type = Column(String(50), nullable=True)  # BASE TABLE, VIEW, MATERIALIZED VIEW, EXTERNAL
    creation_time = Column(TIMESTAMP, nullable=True)
    row_count = Column(BigInteger, nullable=True)
    size_mb = Column(BigInteger, nullable=True)
    
    # Partitioning and clustering
    partitioning_columns = Column(ARRAY(Text), nullable=True)
    clustering_columns = Column(ARRAY(Text), nullable=True)
    
    # Security flags
    has_column_security = Column(Boolean, default=False)
    has_row_security = Column(Boolean, default=False)
    
    # Sharding detection
    is_sharded = Column(Boolean, default=False)
    shard_group = Column(String(255), nullable=True)
    
    # Usage patterns
    update_frequency = Column(String(50), nullable=True)  # daily, weekly, monthly, rarely
    
    # Additional metadata
    table_metadata = Column(JSONB, nullable=True)
    
    # Relationships
    assessment = relationship("Assessment", back_populates="tables")
    columns = relationship("AssessmentColumn", back_populates="table", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_assessment_tables_assessment', 'assessment_id'),
        Index('idx_assessment_tables_dataset', 'dataset_name'),
        Index('idx_assessment_tables_sharded', 'is_sharded'),
        Index('idx_assessment_tables_unique', 'assessment_id', 'dataset_name', 'table_name', unique=True),
    )


class AssessmentColumn(Base):
    """Column-level metadata including data types and security tags."""
    
    __tablename__ = 'assessment_columns'
    
    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey('assessments.id', ondelete='CASCADE'), nullable=False)
    table_id = Column(Integer, ForeignKey('assessment_tables.id', ondelete='CASCADE'), nullable=False)
    column_name = Column(String(255), nullable=False)
    data_type = Column(String(100), nullable=False)
    is_nullable = Column(Boolean, default=True)
    ordinal_position = Column(Integer, nullable=True)
    
    # Partitioning and clustering
    is_partitioning_column = Column(Boolean, default=False)
    clustering_ordinal_position = Column(Integer, nullable=True)
    
    # Security
    policy_tags = Column(ARRAY(Text), nullable=True)
    
    # Data characteristics
    max_length = Column(Integer, nullable=True)  # For STRING types
    
    # Additional metadata
    column_metadata = Column(JSONB, nullable=True)
    
    # Relationships
    table = relationship("AssessmentTable", back_populates="columns")
    
    __table_args__ = (
        Index('idx_assessment_columns_assessment', 'assessment_id'),
        Index('idx_assessment_columns_table', 'table_id'),
        Index('idx_assessment_columns_unique', 'assessment_id', 'table_id', 'column_name', unique=True),
    )


class AssessmentView(Base):
    """View and materialized view definitions."""
    
    __tablename__ = 'assessment_views'
    
    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey('assessments.id', ondelete='CASCADE'), nullable=False)
    view_name = Column(String(255), nullable=False)
    view_type = Column(String(50), nullable=True)  # VIEW or MATERIALIZED VIEW
    view_definition = Column(Text, nullable=True)
    creation_time = Column(TIMESTAMP, nullable=True)
    dependencies = Column(ARRAY(Text), nullable=True)  # Referenced tables
    
    # Dependency analysis fields
    dependent_tables = Column(ARRAY(Text), nullable=True)
    dependent_views = Column(ARRAY(Text), nullable=True)
    dependent_functions = Column(ARRAY(Text), nullable=True)
    dependency_depth = Column(Integer, nullable=True)
    
    view_metadata = Column(JSONB, nullable=True)
    
    # Relationships
    assessment = relationship("Assessment", back_populates="views")
    
    __table_args__ = (
        Index('idx_assessment_views_assessment', 'assessment_id'),
        Index('idx_assessment_views_unique', 'assessment_id', 'view_name', unique=True),
    )


class AssessmentRoutine(Base):
    """Stored procedures and functions (routines)."""
    
    __tablename__ = 'assessment_routines'
    
    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey('assessments.id', ondelete='CASCADE'), nullable=False)
    routine_name = Column(String(255), nullable=False)
    routine_type = Column(String(50), nullable=True)  # PROCEDURE or FUNCTION
    return_type = Column(String(100), nullable=True)
    definition = Column(Text, nullable=True)
    external_language = Column(String(50), nullable=True)  # Python, JavaScript
    creation_time = Column(TIMESTAMP, nullable=True)
    call_frequency = Column(Integer, default=0)  # Calculated from job history
    
    # Dependency analysis fields
    dependent_tables = Column(ARRAY(Text), nullable=True)
    dependent_views = Column(ARRAY(Text), nullable=True)
    dependent_functions = Column(ARRAY(Text), nullable=True)
    calls_procedures = Column(ARRAY(Text), nullable=True)
    dependency_depth = Column(Integer, nullable=True)
    
    routine_metadata = Column(JSONB, nullable=True)
    
    # Relationships
    assessment = relationship("Assessment", back_populates="routines")
    
    __table_args__ = (
        Index('idx_assessment_routines_assessment', 'assessment_id'),
        Index('idx_assessment_routines_unique', 'assessment_id', 'routine_name', unique=True),
    )


class AssessmentQueryStat(Base):
    """Query/job statistics from INFORMATION_SCHEMA.JOBS."""
    
    __tablename__ = 'assessment_query_stats'
    
    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey('assessments.id', ondelete='CASCADE'), nullable=False)
    job_id = Column(String(255), nullable=True)
    execution_time = Column(TIMESTAMP, nullable=True)
    query_text = Column(Text, nullable=True)
    bytes_scanned = Column(BigInteger, nullable=True)
    slot_milliseconds = Column(BigInteger, nullable=True)
    cache_hit = Column(Boolean, nullable=True)
    referenced_tables = Column(ARRAY(Text), nullable=True)
    user_email = Column(String(255), nullable=True)
    query_metadata = Column(JSONB, nullable=True)
    
    # Relationships
    assessment = relationship("Assessment", back_populates="query_stats")
    
    __table_args__ = (
        Index('idx_assessment_query_stats_assessment', 'assessment_id'),
        Index('idx_assessment_query_stats_unique', 'assessment_id', 'job_id', unique=True),
    )


class AssessmentMLModel(Base):
    """BigQuery ML model metadata."""
    
    __tablename__ = 'assessment_ml_models'
    
    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey('assessments.id', ondelete='CASCADE'), nullable=False)
    model_name = Column(String(255), nullable=False)
    model_type = Column(String(100), nullable=True)  # LOGISTIC_REG, DNN_CLASSIFIER, etc.
    dataset_name = Column(String(255), nullable=True)
    creation_time = Column(TIMESTAMP, nullable=True)
    last_modified_time = Column(TIMESTAMP, nullable=True)
    model_metadata = Column(JSONB, nullable=True)
    
    # Relationships
    assessment = relationship("Assessment", back_populates="ml_models")
    
    __table_args__ = (
        Index('idx_assessment_ml_models_assessment', 'assessment_id'),
        Index('idx_assessment_ml_models_unique', 'assessment_id', 'model_name', unique=True),
    )


class AssessmentSecurity(Base):
    """Row-level and column-level security policies."""
    
    __tablename__ = 'assessment_security'
    
    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey('assessments.id', ondelete='CASCADE'), nullable=False)
    security_type = Column(String(50), nullable=True)  # RLS or CLS
    table_name = Column(String(255), nullable=True)
    policy_name = Column(String(255), nullable=True)
    filter_predicate = Column(Text, nullable=True)
    grantees = Column(ARRAY(Text), nullable=True)
    creation_time = Column(TIMESTAMP, nullable=True)
    security_metadata = Column(JSONB, nullable=True)
    
    # Relationships
    assessment = relationship("Assessment", back_populates="security_policies")
    
    __table_args__ = (
        Index('idx_assessment_security_assessment', 'assessment_id'),
        Index('idx_assessment_security_type', 'security_type'),
    )


class AssessmentShardedTable(Base):
    """Sharded table groups (date-suffixed tables)."""
    
    __tablename__ = 'assessment_sharded_tables'
    
    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey('assessments.id', ondelete='CASCADE'), nullable=False)
    shard_group = Column(String(255), nullable=False)
    table_prefix = Column(String(255), nullable=False)
    shard_count = Column(Integer, default=0)
    total_size_mb = Column(BigInteger, default=0)
    date_range_start = Column(TIMESTAMP, nullable=True)
    date_range_end = Column(TIMESTAMP, nullable=True)
    shard_tables = Column(ARRAY(Text), nullable=True)
    shard_metadata = Column(JSONB, nullable=True)
    
    # Relationships
    assessment = relationship("Assessment", back_populates="sharded_tables")
    
    __table_args__ = (
        Index('idx_assessment_sharded_assessment', 'assessment_id'),
        Index('idx_assessment_sharded_unique', 'assessment_id', 'shard_group', unique=True),
    )


class AssessmentIndex(Base):
    """Database indexes for tables and views."""

    __tablename__ = 'assessment_indexes'

    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey('assessments.id', ondelete='CASCADE'), nullable=False)
    table_id = Column(Integer, nullable=True)
    schema_name = Column(String(255), nullable=True)
    table_name = Column(String(255), nullable=True)
    object_type = Column(String(50), nullable=True, default='TABLE')
    index_name = Column(String(255), nullable=False)
    index_type = Column(String(50), nullable=True)
    is_unique = Column(Boolean, default=False)
    is_primary_key = Column(Boolean, default=False)
    is_clustered = Column(Boolean, default=False)
    key_columns = Column(Text, nullable=True)
    included_columns = Column(Text, nullable=True)
    filter_definition = Column(Text, nullable=True)
    size_mb = Column(Float, default=0.0)
    row_count = Column(BigInteger, default=0)
    index_metadata = Column(JSONB, nullable=True)

    # Relationships
    assessment = relationship("Assessment", back_populates="indexes")

    __table_args__ = (
        Index('idx_assessment_indexes_assessment', 'assessment_id'),
        Index('idx_assessment_indexes_table', 'table_id'),
        Index('idx_assessment_indexes_name', 'index_name'),
    )
