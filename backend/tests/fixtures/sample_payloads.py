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

# Conversion payloads
VALID_STANDALONE_CONVERSION = {
    "source_code": "SELECT * FROM dataset.my_table WHERE created_at > CURRENT_TIMESTAMP()",
    "source_dialect": "bigquery",
    "target_dialect": "redshift",
    "asset_type": "view",
    "use_sqlglot": True,
}

VALID_BATCH_CONVERSION = {
    "source_connection_id": 1,
    "target_connection_id": 2,
    "asset_list": [
        {"asset_type": "view", "asset_name": "users_view", "source_code": "CREATE VIEW users_view AS SELECT * FROM users"},
        {"asset_type": "stored_procedure", "asset_name": "update_user", "source_code": "CREATE PROCEDURE update_user..."},
    ],
}

# ConversionJob model payloads
VALID_CONVERSION_JOB_DATA = {
    "workspace_id": 1,
    "source_code": "SELECT * FROM dataset.my_table",
    "source_dialect": "bigquery",
    "target_dialect": "redshift",
    "asset_type": "view",
    "use_sqlglot": True,
    "status": "pending",
    "retry_count": 0,
}

# ConversionBatch model payloads
VALID_CONVERSION_BATCH_DATA = {
    "workspace_id": 1,
    "source_connection_id": 1,
    "target_connection_id": 2,
    "total_assets": 5,
    "completed_assets": 0,
    "failed_assets": 0,
    "status": "pending",
}

# Copy History payloads
VALID_COPY_HISTORY_DATA = {
    "migration_id": 1,
    "schema_name": "public",
    "table_name": "users",
    "copy_command": "COPY users FROM 's3://bucket/users.csv'",
    "status": "running",
}

# Task History payloads
VALID_TASK_HISTORY_DATA = {
    "migration_id": 1,
    "task_name": "Copy users table",
    "task_arn": "arn:aws:datasync:us-east-1:123456789:task/task-123",
    "agent_arn": "arn:aws:datasync:us-east-1:123456789:agent/agent-456",
    "agent_ip": "10.0.1.100",
    "source_uri": "s3://source-bucket/data/",
    "dest_uri": "s3://dest-bucket/data/",
    "status": "running",
}

# DataSync Agent payloads
VALID_DATASYNC_AGENT_DATA = {
    "workspace_id": 1,
    "vm_ip": "10.0.1.100",
    "agent_arn": "arn:aws:datasync:us-east-1:123456789:agent/agent-456",
    "aws_region": "us-east-1",
    "status": "online",
}

# Asset types
VALID_ASSET_TYPES = [
    "view",
    "stored_procedure",
    "function",
    "trigger",
    "table_ddl",
]

# Job statuses
VALID_JOB_STATUSES = ["pending", "processing", "completed", "failed"]

# Batch statuses
VALID_BATCH_STATUSES = ["pending", "processing", "completed", "failed"]
