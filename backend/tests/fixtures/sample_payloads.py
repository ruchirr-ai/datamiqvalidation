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
