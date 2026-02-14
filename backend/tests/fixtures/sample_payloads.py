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
    "short": "Pass1",  # Too short
    "no_uppercase": "password123",  # No uppercase
    "no_lowercase": "PASSWORD123",  # No lowercase
    "no_number": "PasswordOnly",  # No number
    "empty": "",  # Empty
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
    "exp": 1706198400,  # Example expiration timestamp
    "iat": 1706169600   # Example issued at timestamp
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
