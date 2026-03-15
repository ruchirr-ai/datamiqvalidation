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
