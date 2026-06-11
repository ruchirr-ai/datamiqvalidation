"""
Sample payloads for testing
Centralized repository of test data
"""

# Authentication payloads
VALID_LOGIN = {
    "username": "admin",
    "password": "AdminPass123!"
}

INVALID_LOGIN_WRONG_PASSWORD = {
    "username": "admin",
    "password": "WrongPassword"
}

INVALID_LOGIN_MISSING_FIELD = {
    "username": "admin"
    # password missing
}

INVALID_LOGIN_EMPTY_PASSWORD = {
    "username": "admin",
    "password": ""
}

# User creation payloads
VALID_USER_CREATE = {
    "username": "newuser",
    "password": "NewPass123!",
    "role": "user"
}

VALID_ADMIN_CREATE = {
    "username": "admin",
    "password": "AdminPass123!",
    "role": "admin"
}

# Password validation test cases
VALID_PASSWORDS = [
    "ValidPass123",
    "SecureP@ss1",
    "MyPassword1",
    "Test1234Pass",
    "Admin123!@#"
]

INVALID_PASSWORDS = {
    "short": "Pass1",
    "no_uppercase": "password123",
    "no_lowercase": "PASSWORD123",
    "no_number": "PasswordOnly",
    "empty": "",
}

# Database connection payloads
VALID_DB_CONNECTION = {
    "name": "Production DB",
    "type": "postgresql",
    "host": "db.example.com",
    "port": 5432,
    "database": "mydb",
    "username": "dbuser",
    "password": "DbPass123!"
}

# Migration project payloads
VALID_MIGRATION_PROJECT = {
    "name": "Customer Data Migration",
    "source_connection_id": 1,
    "target_connection_id": 2,
    "description": "Migrate customer data from MySQL to PostgreSQL"
}

# JWT token payloads
VALID_TOKEN_PAYLOAD = {
    "user_id": 1,
    "username": "testuser",
    "role": "user",
    "exp": 1706198400,
    "iat": 1706169600
}

# Session data
VALID_SESSION_DATA = {
    "user_id": 1,
    "token_hash": "abc123hash",
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0"
}

# Audit log data
VALID_AUDIT_LOG = {
    "event_type": "login_attempt",
    "user_id": 1,
    "username": "testuser",
    "ip_address": "192.168.1.1",
    "details": {"success": True},
    "success": True
}

# ---------------------------------------------------------------------------
# Code Conversion payloads
# ---------------------------------------------------------------------------

# Standalone conversion request payloads
VALID_STANDALONE_CONVERSION = {
    "source_code": "SELECT * FROM dataset.my_table WHERE created_at > CURRENT_TIMESTAMP()",
    "source_dialect": "Bigquery",
    "target_dialect": "Redshift",
    "asset_type": "TABLE_DDL",
    "asset_name": "my_table",
    "aws_region": "us-east-1",
    "bedrock_model": "anthropic.claude-3-sonnet-20240229-v1:0",
    "prompt_template_path": "s3://my-bucket/templates/bq-to-redshift.txt",
    "max_retries": 3,
    "use_sqlglot": False,
}

VALID_STANDALONE_CONVERSION_SQLGLOT = {
    **VALID_STANDALONE_CONVERSION,
    "use_sqlglot": True,
}

VALID_STANDALONE_CONVERSION_MINIMAL = {
    "source_code": "SELECT 1",
    "source_dialect": "Bigquery",
    "target_dialect": "Redshift",
    "asset_type": "VIEW",
    "aws_region": "us-west-2",
    "bedrock_model": "anthropic.claude-3-haiku-20240307-v1:0",
    "prompt_template_path": "s3://bucket/template.txt",
}

# Batch conversion request payloads
VALID_BATCH_CONVERSION = {
    "migration_project_id": 1,
    "source_connection_id": 10,
    "target_connection_id": 20,
    "assets": [
        {"asset_type": "TABLE_DDL", "asset_name": "users", "source_code": "CREATE TABLE users (id INT64)"},
        {"asset_type": "VIEW", "asset_name": "active_users", "source_code": "CREATE VIEW active_users AS SELECT * FROM users WHERE active = TRUE"},
    ],
    "source_dialect": "Bigquery",
    "target_dialect": "Redshift",
    "aws_region": "us-east-1",
    "bedrock_model": "anthropic.claude-3-sonnet-20240229-v1:0",
    "prompt_template_path": "s3://my-bucket/templates/bq-to-redshift.txt",
    "max_retries": 5,
    "use_sqlglot": True,
}

# S3 export request payloads
VALID_S3_EXPORT = {
    "s3_path": "s3://my-bucket/exports/batch-1/",
    "region": "us-east-1",
}

# Deploy request payloads
VALID_DEPLOY_REQUEST = {
    "target_connection_id": 20,
}

# ConversionJob model payloads (for SQLAlchemy model tests)
VALID_CONVERSION_JOB_DATA = {
    "workspace_id": 1,
    "source_code": "SELECT * FROM dataset.my_table",
    "source_dialect": "Bigquery",
    "target_dialect": "Redshift",
    "asset_type": "TABLE_DDL",
    "asset_name": "my_table",
    "bedrock_model": "anthropic.claude-3-sonnet-20240229-v1:0",
    "aws_region": "us-east-1",
    "prompt_template_path": "s3://bucket/template.txt",
    "use_sqlglot": False,
    "status": "pending",
    "retry_count": 0,
    "created_by": "testuser",
}

VALID_CONVERSION_JOB_COMPLETED = {
    **VALID_CONVERSION_JOB_DATA,
    "target_code": "SELECT * FROM my_schema.my_table",
    "status": "completed",
    "sqlglot_success": True,
}

# ConversionBatch model payloads
VALID_CONVERSION_BATCH_DATA = {
    "workspace_id": 1,
    "migration_project_id": 1,
    "source_connection_id": 10,
    "target_connection_id": 20,
    "bedrock_model": "anthropic.claude-3-sonnet-20240229-v1:0",
    "aws_region": "us-east-1",
    "prompt_template_path": "s3://bucket/template.txt",
    "use_sqlglot": False,
    "max_retries": 3,
    "status": "pending",
    "total_assets": 5,
    "completed_assets": 0,
    "failed_assets": 0,
    "created_by": "testuser",
}

# Asset type enum values
VALID_ASSET_TYPES = [
    "TABLE_DDL",
    "STORED_PROCEDURE",
    "FUNCTION",
    "VIEW",
    "MATERIALIZED_VIEW",
    "SCHEDULED_QUERY",
]

INVALID_ASSET_TYPES = [
    "INVALID_TYPE",
    "table_ddl",
    "TABLE",
    "",
    "INDEX",
]

# Job status enum values
VALID_JOB_STATUSES = ["pending", "in_progress", "completed", "failed"]

# Batch status enum values
VALID_BATCH_STATUSES = ["pending", "in_progress", "completed", "failed", "completed_with_errors"]

# ---------------------------------------------------------------------------
# Code Conversion Enhancements payloads
# ---------------------------------------------------------------------------

# Valid conversion log entry
VALID_CONVERSION_LOG_ENTRY = {
    "job_id": 1,
    "workspace_id": 1,
    "log_level": "INFO",
    "step_name": "template_loaded",
    "message": "Prompt template loaded from S3",
    "duration_ms": 120,
}

# Standalone conversion with additional_context
VALID_STANDALONE_WITH_CONTEXT = {
    "source_code": "SELECT * FROM my_table",
    "source_dialect": "Bigquery",
    "target_dialect": "Redshift",
    "asset_type": "QUERY",
    "asset_name": "My Test Query",
    "aws_region": "us-east-1",
    "bedrock_model": "anthropic.claude-3-sonnet-20240229-v1:0",
    "prompt_template_path": "prompts/bigquery-to-redshift-conversion.txt",
    "additional_context": "Schema: users(id INT, name VARCHAR(255))",
    "use_sqlglot": False,
}

# ---------------------------------------------------------------------------
# ClickHouse conversion payloads
# ---------------------------------------------------------------------------

# BigQuery → ClickHouse: basic SELECT query
VALID_BQ_TO_CLICKHOUSE_QUERY = {
    "source_code": (
        "SELECT user_id, TIMESTAMP_TRUNC(event_time, DAY) AS event_day, "
        "COUNT(DISTINCT session_id) AS sessions, "
        "STRING_AGG(event_name, ', ' ORDER BY event_time) AS event_list "
        "FROM `my_project.analytics.events` "
        "WHERE DATE(event_time) >= '2024-01-01' "
        "GROUP BY 1, 2"
    ),
    "source_dialect": "Bigquery",
    "target_dialect": "ClickHouse",
    "asset_type": "QUERY",
    "asset_name": "daily_session_summary",
    "aws_region": "us-east-1",
    "bedrock_model": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
    "prompt_template_path": "prompts/bigquery-to-clickhouse-conversion.txt",
    "max_retries": 3,
    "use_sqlglot": False,
}

# BigQuery → ClickHouse: TABLE DDL with PARTITION BY and CLUSTER BY
VALID_BQ_TO_CLICKHOUSE_TABLE_DDL = {
    "source_code": (
        "CREATE OR REPLACE TABLE `my_project.analytics.user_events` (\n"
        "  user_id INT64 NOT NULL,\n"
        "  session_id STRING,\n"
        "  event_name STRING,\n"
        "  event_time TIMESTAMP,\n"
        "  properties JSON,\n"
        "  tags ARRAY<STRING>,\n"
        "  location STRUCT<city STRING, country STRING>,\n"
        "  revenue NUMERIC(18, 4)\n"
        ")\n"
        "PARTITION BY DATE(event_time)\n"
        "CLUSTER BY user_id, event_name\n"
        "OPTIONS (partition_expiration_days=90)"
    ),
    "source_dialect": "Bigquery",
    "target_dialect": "ClickHouse",
    "asset_type": "TABLE_DDL",
    "asset_name": "user_events",
    "aws_region": "us-east-1",
    "bedrock_model": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
    "prompt_template_path": "prompts/bigquery-to-clickhouse-conversion.txt",
    "max_retries": 3,
    "use_sqlglot": False,
}

# BigQuery → ClickHouse: VIEW with window function and QUALIFY
VALID_BQ_TO_CLICKHOUSE_VIEW = {
    "source_code": (
        "CREATE OR REPLACE VIEW `my_project.analytics.latest_user_events` AS\n"
        "SELECT * FROM (\n"
        "  SELECT *, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY event_time DESC) AS rn\n"
        "  FROM `my_project.analytics.user_events`\n"
        ")\n"
        "WHERE rn = 1"
    ),
    "source_dialect": "Bigquery",
    "target_dialect": "ClickHouse",
    "asset_type": "VIEW",
    "asset_name": "latest_user_events",
    "aws_region": "us-east-1",
    "bedrock_model": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
    "prompt_template_path": "prompts/bigquery-to-clickhouse-conversion.txt",
    "max_retries": 3,
    "use_sqlglot": False,
}

# BigQuery → ClickHouse: SQLGlot pre-processing enabled
VALID_BQ_TO_CLICKHOUSE_SQLGLOT = {
    **VALID_BQ_TO_CLICKHOUSE_QUERY,
    "use_sqlglot": True,
    "asset_name": "daily_session_summary_sqlglot",
}

# BigQuery → ClickHouse: ARRAY / UNNEST patterns
VALID_BQ_TO_CLICKHOUSE_ARRAY_QUERY = {
    "source_code": (
        "SELECT t.user_id, item\n"
        "FROM `my_project.analytics.user_events` AS t,\n"
        "UNNEST(t.tags) AS item\n"
        "WHERE ARRAY_LENGTH(t.tags) > 0"
    ),
    "source_dialect": "Bigquery",
    "target_dialect": "ClickHouse",
    "asset_type": "QUERY",
    "asset_name": "unnested_tags",
    "aws_region": "us-east-1",
    "bedrock_model": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
    "prompt_template_path": "prompts/bigquery-to-clickhouse-conversion.txt",
    "max_retries": 2,
    "use_sqlglot": False,
}

# BigQuery → ClickHouse: STORED PROCEDURE (unsupported — should produce High risk flags)
VALID_BQ_TO_CLICKHOUSE_STORED_PROCEDURE = {
    "source_code": (
        "CREATE OR REPLACE PROCEDURE `my_project.analytics.refresh_daily_stats`()\n"
        "BEGIN\n"
        "  DECLARE cutoff_date DATE DEFAULT DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY);\n"
        "  DELETE FROM `my_project.analytics.daily_stats` WHERE stat_date < cutoff_date;\n"
        "  INSERT INTO `my_project.analytics.daily_stats`\n"
        "  SELECT DATE(event_time), COUNT(*) FROM `my_project.analytics.user_events`\n"
        "  WHERE DATE(event_time) >= cutoff_date\n"
        "  GROUP BY 1;\n"
        "END"
    ),
    "source_dialect": "Bigquery",
    "target_dialect": "ClickHouse",
    "asset_type": "STORED_PROCEDURE",
    "asset_name": "refresh_daily_stats",
    "aws_region": "us-east-1",
    "bedrock_model": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
    "prompt_template_path": "prompts/bigquery-to-clickhouse-conversion.txt",
    "max_retries": 3,
    "use_sqlglot": False,
}

# BigQuery → ClickHouse: batch conversion payload
VALID_BQ_TO_CLICKHOUSE_BATCH = {
    "migration_project_id": 1,
    "source_connection_id": 10,
    "target_connection_id": 20,
    "batch_name": "BQ to ClickHouse Analytics Migration",
    "assets": [
        {
            "asset_type": "TABLE_DDL",
            "asset_name": "user_events",
            "source_code": (
                "CREATE TABLE `my_project.analytics.user_events` (\n"
                "  user_id INT64,\n"
                "  event_time TIMESTAMP,\n"
                "  event_name STRING\n"
                ") PARTITION BY DATE(event_time) CLUSTER BY user_id"
            ),
        },
        {
            "asset_type": "VIEW",
            "asset_name": "active_users",
            "source_code": (
                "CREATE VIEW `my_project.analytics.active_users` AS\n"
                "SELECT DISTINCT user_id FROM `my_project.analytics.user_events`\n"
                "WHERE event_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)"
            ),
        },
        {
            "asset_type": "QUERY",
            "asset_name": "daily_revenue",
            "source_code": (
                "SELECT DATE_TRUNC(event_time, DAY) AS day,\n"
                "SUM(SAFE_DIVIDE(revenue, 100.0)) AS total_revenue\n"
                "FROM `my_project.analytics.user_events`\n"
                "GROUP BY 1 ORDER BY 1 DESC"
            ),
        },
    ],
    "source_dialect": "Bigquery",
    "target_dialect": "ClickHouse",
    "aws_region": "us-east-1",
    "bedrock_model": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
    "prompt_template_path": "prompts/bigquery-to-clickhouse-conversion.txt",
    "max_retries": 3,
    "use_sqlglot": False,
}

# Invalid dialect payload
INVALID_DIALECT_PAYLOAD = {
    "source_code": "SELECT 1",
    "source_dialect": "oracle",
    "target_dialect": "Redshift",
    "asset_type": "QUERY",
    "aws_region": "us-east-1",
    "bedrock_model": "anthropic.claude-3-sonnet-20240229-v1:0",
    "prompt_template_path": "prompts/test.txt",
}

# Bulk delete payload
BULK_DELETE_PAYLOAD = {
    "job_ids": [1, 2, 3],
}

# Context at boundary (50,000 chars)
CONTEXT_AT_BOUNDARY = "x" * 50000

# Context exceeding limit (50,001 chars)
CONTEXT_EXCEEDS_LIMIT = "x" * 50001

# Valid batch delete payload
VALID_BATCH_DELETE = {
    "batch_id": 1,
    "workspace_id": 1,
}

# Updated asset types including QUERY
VALID_ASSET_TYPES_WITH_QUERY = [
    "QUERY",
    "TABLE_DDL",
    "STORED_PROCEDURE",
    "FUNCTION",
    "VIEW",
    "MATERIALIZED_VIEW",
    "SCHEDULED_QUERY",
]

# ---------------------------------------------------------------------------
# Data Validation Module payloads
# ---------------------------------------------------------------------------

# ValidationRun model payloads (for SQLAlchemy model tests)
VALID_VALIDATION_RUN_DATA = {
    "workspace_id": 1,
    "migration_id": 10,
    "source_connection_id": 100,
    "target_connection_id": 200,
    "bedrock_model": "anthropic.claude-3-sonnet-20240229-v1:0",
    "batch_size": 10000,
    "type_mapping_overrides": {"STRING": "TEXT"},
    "status": "pending",
    "progress_percentage": 0,
    "tables_total": 5,
    "tables_passed": 0,
    "tables_failed": 0,
    "tables_error": 0,
    "created_by": "testuser",
}

VALID_VALIDATION_RUN_COMPLETED = {
    "workspace_id": 1,
    "migration_id": 10,
    "source_connection_id": 100,
    "target_connection_id": 200,
    "batch_size": 10000,
    "status": "completed",
    "progress_percentage": 100,
    "tables_total": 3,
    "tables_passed": 2,
    "tables_failed": 1,
    "tables_error": 0,
    "created_by": "testuser",
}

VALID_VALIDATION_RUN_MINIMAL = {
    "workspace_id": 1,
    "migration_id": 10,
    "source_connection_id": 100,
    "target_connection_id": 200,
    "created_by": "testuser",
}

# ValidationTableResult model payloads
VALID_VALIDATION_TABLE_RESULT_DATA = {
    "run_id": 1,
    "workspace_id": 1,
    "table_name": "users",
    "dataset_name": "my_dataset",
    "ddl_status": "passed",
    "ddl_comparison_result": {
        "discrepancies": [],
        "source_column_count": 5,
        "target_column_count": 5,
        "columns_compared": 5,
    },
    "row_count_status": "passed",
    "row_count_result": {
        "source_count": 1000,
        "target_count": 1000,
        "difference": 0,
        "percentage_difference": 0.0,
    },
    "data_match_status": "passed",
    "data_match_result": {
        "total_compared": 1000,
        "matched_count": 1000,
        "missing_count": 0,
        "extra_count": 0,
        "mismatch_count": 0,
        "sample_discrepancies": [],
    },
    "status": "completed",
}

VALID_VALIDATION_TABLE_RESULT_FAILED = {
    "run_id": 1,
    "workspace_id": 1,
    "table_name": "orders",
    "dataset_name": "my_dataset",
    "ddl_status": "failed",
    "ddl_comparison_result": {
        "discrepancies": [
            {
                "type": "missing_column",
                "column_name": "discount",
                "source_type": "FLOAT64",
                "target_type": None,
                "expected_type": "DOUBLE PRECISION",
            }
        ],
        "source_column_count": 8,
        "target_column_count": 7,
        "columns_compared": 8,
    },
    "row_count_status": "failed",
    "row_count_result": {
        "source_count": 5000,
        "target_count": 4998,
        "difference": 2,
        "percentage_difference": 0.04,
    },
    "data_match_status": "failed",
    "data_match_result": {
        "total_compared": 5000,
        "matched_count": 4995,
        "missing_count": 2,
        "extra_count": 0,
        "mismatch_count": 3,
        "sample_discrepancies": [
            {"type": "missing_in_target", "primary_key": {"id": 42}, "details": None},
        ],
    },
    "ai_analysis": {
        "root_cause": "Two rows lost during AVRO export",
        "impact_assessment": "Minor data loss in orders table",
        "recommended_workarounds": ["Re-export affected rows"],
    },
    "status": "failed",
    "error_message": None,
}

VALID_VALIDATION_TABLE_RESULT_MINIMAL = {
    "run_id": 1,
    "workspace_id": 1,
    "table_name": "products",
    "status": "pending",
}

VALID_VALIDATION_TABLE_RESULT_ERROR = {
    "run_id": 1,
    "workspace_id": 1,
    "table_name": "events",
    "status": "error",
    "error_message": "Connection timeout after 300 seconds",
}

# CreateValidationRunRequest Pydantic payloads
VALID_CREATE_VALIDATION_RUN_REQUEST = {
    "migration_id": 10,
    "source_connection_id": 100,
    "target_connection_id": 200,
    "tables": ["users", "orders"],
    "bedrock_model": "anthropic.claude-3-sonnet-20240229-v1:0",
    "batch_size": 10000,
    "type_mapping_overrides": {"STRING": "TEXT"},
}

VALID_CREATE_VALIDATION_RUN_MINIMAL = {
    "migration_id": 10,
    "source_connection_id": 100,
    "target_connection_id": 200,
}

INVALID_CREATE_VALIDATION_RUN_MISSING_MIGRATION = {
    "source_connection_id": 100,
    "target_connection_id": 200,
}

INVALID_CREATE_VALIDATION_RUN_MISSING_CONNECTION = {
    "migration_id": 10,
    "target_connection_id": 200,
}

INVALID_CREATE_VALIDATION_RUN_WRONG_TYPES = {
    "migration_id": "not_an_int",
    "source_connection_id": 100,
    "target_connection_id": 200,
}

# ---------------------------------------------------------------------------
# run_name validation payloads (Validation UX Redesign)
# ---------------------------------------------------------------------------

VALID_CREATE_VALIDATION_RUN_WITH_RUN_NAME = {
    "migration_id": 10,
    "source_connection_id": 100,
    "target_connection_id": 200,
    "run_name": "Pre-release check",
}

VALID_CREATE_VALIDATION_RUN_RUN_NAME_MAX_LENGTH = {
    "migration_id": 10,
    "source_connection_id": 100,
    "target_connection_id": 200,
    "run_name": "A" * 255,
}

VALID_CREATE_VALIDATION_RUN_RUN_NAME_NONE = {
    "migration_id": 10,
    "source_connection_id": 100,
    "target_connection_id": 200,
    "run_name": None,
}

INVALID_CREATE_VALIDATION_RUN_RUN_NAME_TOO_LONG = {
    "migration_id": 10,
    "source_connection_id": 100,
    "target_connection_id": 200,
    "run_name": "A" * 256,
}

# ---------------------------------------------------------------------------
# BQ-to-Iceberg Migration Model payloads
# ---------------------------------------------------------------------------

# MigrationBQIceberg model payloads
VALID_BQ_ICEBERG_MIGRATION_S3 = {
    "workspace_id": 1,
    "migration_name": "BQ to Iceberg S3 Migration",
    "pathway": "A",
    "source_connection_id": 10,
    "source_project_id": "my-gcp-project",
    "source_dataset": "analytics",
    "source_tables": ["users", "orders", "events"],
    "target_connection_id": 20,
    "destination_type": "iceberg_s3",
    "s3_bucket": "my-data-lake-bucket",
    "s3_path_prefix": "iceberg/analytics/",
    "aws_region": "us-east-1",
    "glue_database_name": "analytics_db",
    "dataset_to_db_mapping": {"analytics": "analytics_db", "reporting": "reporting_db"},
    "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "aws_secret_access_key_encrypted": "encrypted-secret-key-value",
    "gcs_bucket": "my-gcs-export-bucket",
    "gcs_path": "exports/analytics/",
    "gcs_region": "us-central1",
    "export_format": "PARQUET",
    "compression": "ZSTD",
    "load_type": "full",
    "table_load_configs": {
        "users": {"priority": 1, "batch_size": 10000},
        "orders": {"priority": 2, "batch_size": 50000},
    },
    "parallelism": 4,
    "enable_load_stage_verification": False,
    "status": "pending",
    "current_stage": None,
    "created_by": 1,
}

VALID_BQ_ICEBERG_MIGRATION_S3_TABLES = {
    "workspace_id": 2,
    "migration_name": "BQ to S3 Tables Migration",
    "pathway": "B",
    "source_connection_id": 11,
    "source_project_id": "another-gcp-project",
    "source_dataset": "warehouse",
    "source_tables": ["products", "inventory"],
    "target_connection_id": 21,
    "destination_type": "iceberg_s3_tables",
    "table_bucket_arn": "arn:aws:s3tables:us-east-1:123456789012:bucket/my-table-bucket",
    "s3_tables_namespace": "warehouse_ns",
    "aws_region": "us-east-1",
    "glue_database_name": "warehouse_db",
    "aws_role_arn": "arn:aws:iam::123456789012:role/DataMIQIcebergRole",
    "gcs_bucket": "gcs-export-bucket",
    "gcs_path": "exports/warehouse/",
    "gcs_region": "us-central1",
    "export_format": "PARQUET",
    "compression": "ZSTD",
    "load_type": "incremental",
    "parallelism": 8,
    "enable_load_stage_verification": True,
    "status": "pending",
    "created_by": 2,
}

VALID_BQ_ICEBERG_MIGRATION_MINIMAL = {
    "workspace_id": 1,
    "migration_name": "Minimal Migration",
    "pathway": "C",
    "destination_type": "iceberg_s3",
    "aws_region": "eu-west-1",
    "glue_database_name": "default_db",
}

VALID_BQ_ICEBERG_MIGRATION_PATHWAY_C = {
    "workspace_id": 3,
    "migration_name": "Direct Pathway Migration",
    "pathway": "C",
    "destination_type": "iceberg_s3",
    "s3_bucket": "direct-lake",
    "s3_path_prefix": "",
    "aws_region": "us-west-2",
    "glue_database_name": "direct_db",
    "parallelism": 1,
    "status": "pending",
}

VALID_BQ_ICEBERG_MIGRATION_MAX_PARALLELISM = {
    "workspace_id": 1,
    "migration_name": "Max Parallel Migration",
    "pathway": "A",
    "destination_type": "iceberg_s3",
    "aws_region": "us-east-1",
    "glue_database_name": "parallel_db",
    "parallelism": 16,
    "status": "pending",
}

# IcebergTableValidation model payloads
VALID_ICEBERG_TABLE_VALIDATION_PASSED = {
    "migration_id": 1,
    "table_name": "users",
    "source_row_count": 100000,
    "target_row_count": 100000,
    "match_status": "passed",
    "validation_type": "full",
}

VALID_ICEBERG_TABLE_VALIDATION_FAILED = {
    "migration_id": 1,
    "table_name": "orders",
    "source_row_count": 50000,
    "target_row_count": 49998,
    "match_status": "failed",
    "validation_type": "full",
    "error_reason": "Row count mismatch: expected 50000, got 49998",
}

VALID_ICEBERG_TABLE_VALIDATION_INCREMENTAL = {
    "migration_id": 1,
    "table_name": "events",
    "source_row_count": 200000,
    "target_row_count": 200000,
    "match_status": "passed",
    "validation_type": "incremental",
    "batch_export_count": 5000,
    "previous_snapshot_count": 195000,
}

VALID_ICEBERG_TABLE_VALIDATION_SKIPPED = {
    "migration_id": 1,
    "table_name": "logs",
    "match_status": "skipped",
    "validation_type": "full",
    "error_reason": "Athena query execution failed: GENERIC_INTERNAL_ERROR",
}

VALID_ICEBERG_TABLE_VALIDATION_MINIMAL = {
    "migration_id": 1,
    "table_name": "products",
}
