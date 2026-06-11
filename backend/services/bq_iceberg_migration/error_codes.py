"""
Error Code Categorization and Structured Logging for BQ-to-Iceberg Migrations

Defines error code constants matching the design's error table, provides
structured error logging with categorized error_codes, and ensures no
credentials are logged in migration logs.

Error Categories:
- Auth: Permission/credential errors (non-retryable)
- Glue: AWS Glue Data Catalog errors (retryable)
- Iceberg: Iceberg table operation errors (retryable)
- S3: S3 access errors (retryable)
- Schema: Schema evolution errors (non-retryable)
- S3 Tables: S3 Tables API errors (retryable)
- Athena: Athena verification errors (non-retryable)
- Cost: Cost calculation errors (non-retryable)
- Validation: Structure validation errors (non-retryable)

Requirements: 11.1, 11.2, 11.3, 11.4, 11.5
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# --- Error Code Constants ---

class ErrorCode(str, Enum):
    """Categorized error codes for Iceberg migration operations.

    Each error code maps to a specific failure category and indicates
    whether the operation is retryable.
    """

    # Auth errors (non-retryable)
    GLUE_PERMISSION_DENIED = "GLUE_PERMISSION_DENIED"

    # Glue errors (retryable)
    GLUE_REGISTRATION_FAILED = "GLUE_REGISTRATION_FAILED"

    # Iceberg errors (retryable)
    ICEBERG_TABLE_CREATE_FAILED = "ICEBERG_TABLE_CREATE_FAILED"
    ICEBERG_APPEND_FAILED = "ICEBERG_APPEND_FAILED"

    # S3 errors (retryable)
    ICEBERG_S3_ACCESS_ERROR = "ICEBERG_S3_ACCESS_ERROR"

    # Schema errors (non-retryable)
    ICEBERG_SCHEMA_EVOLUTION_FAILED = "ICEBERG_SCHEMA_EVOLUTION_FAILED"
    SCHEMA_EVOLUTION_INCOMPATIBLE = "SCHEMA_EVOLUTION_INCOMPATIBLE"

    # S3 Tables errors (retryable)
    S3_TABLES_API_FAILED = "S3_TABLES_API_FAILED"
    S3_TABLES_THROTTLED = "S3_TABLES_THROTTLED"

    # S3 Tables maintenance errors (non-retryable after exhausting retries)
    S3_TABLES_MAINTENANCE_CONFIG_FAILED = "S3_TABLES_MAINTENANCE_CONFIG_FAILED"

    # Glue ID validation errors (non-retryable)
    GLUE_ID_INVALID = "GLUE_ID_INVALID"

    # Compaction strategy validation errors (non-retryable)
    COMPACTION_STRATEGY_INVALID = "COMPACTION_STRATEGY_INVALID"

    # Athena errors (non-retryable)
    ATHENA_VERIFICATION_TIMEOUT = "ATHENA_VERIFICATION_TIMEOUT"

    # Cost errors (non-retryable)
    COST_CALCULATION_FAILED = "COST_CALCULATION_FAILED"

    # Validation errors (non-retryable)
    CUSTOM_STRUCTURE_INVALID = "CUSTOM_STRUCTURE_INVALID"


class ErrorCategory(str, Enum):
    """High-level error categories for grouping error codes."""

    AUTH = "Auth"
    GLUE = "Glue"
    ICEBERG = "Iceberg"
    S3 = "S3"
    SCHEMA = "Schema"
    S3_TABLES = "S3 Tables"
    ATHENA = "Athena"
    COST = "Cost"
    VALIDATION = "Validation"


# --- Error Code Metadata ---

@dataclass(frozen=True)
class ErrorCodeMetadata:
    """Metadata for an error code including category and retry behavior.

    Attributes:
        code: The error code enum value.
        category: The high-level error category.
        retryable: Whether the operation can be retried.
        max_retries: Maximum number of retry attempts (0 if non-retryable).
        description: Human-readable description of the error.
    """

    code: ErrorCode
    category: ErrorCategory
    retryable: bool
    max_retries: int
    description: str


# Error code registry mapping each code to its metadata
ERROR_CODE_REGISTRY: Dict[ErrorCode, ErrorCodeMetadata] = {
    ErrorCode.GLUE_PERMISSION_DENIED: ErrorCodeMetadata(
        code=ErrorCode.GLUE_PERMISSION_DENIED,
        category=ErrorCategory.AUTH,
        retryable=False,
        max_retries=0,
        description="Missing IAM permissions for Glue operations",
    ),
    ErrorCode.GLUE_REGISTRATION_FAILED: ErrorCodeMetadata(
        code=ErrorCode.GLUE_REGISTRATION_FAILED,
        category=ErrorCategory.GLUE,
        retryable=True,
        max_retries=3,
        description="Failed to register table in Glue Data Catalog",
    ),
    ErrorCode.ICEBERG_TABLE_CREATE_FAILED: ErrorCodeMetadata(
        code=ErrorCode.ICEBERG_TABLE_CREATE_FAILED,
        category=ErrorCategory.ICEBERG,
        retryable=True,
        max_retries=3,
        description="Iceberg table creation failed",
    ),
    ErrorCode.ICEBERG_APPEND_FAILED: ErrorCodeMetadata(
        code=ErrorCode.ICEBERG_APPEND_FAILED,
        category=ErrorCategory.ICEBERG,
        retryable=True,
        max_retries=3,
        description="Data file append to Iceberg table failed",
    ),
    ErrorCode.ICEBERG_S3_ACCESS_ERROR: ErrorCodeMetadata(
        code=ErrorCode.ICEBERG_S3_ACCESS_ERROR,
        category=ErrorCategory.S3,
        retryable=True,
        max_retries=3,
        description="S3 bucket or object access denied",
    ),
    ErrorCode.ICEBERG_SCHEMA_EVOLUTION_FAILED: ErrorCodeMetadata(
        code=ErrorCode.ICEBERG_SCHEMA_EVOLUTION_FAILED,
        category=ErrorCategory.SCHEMA,
        retryable=False,
        max_retries=0,
        description="Schema evolution operation failed",
    ),
    ErrorCode.SCHEMA_EVOLUTION_INCOMPATIBLE: ErrorCodeMetadata(
        code=ErrorCode.SCHEMA_EVOLUTION_INCOMPATIBLE,
        category=ErrorCategory.SCHEMA,
        retryable=False,
        max_retries=0,
        description="Incompatible schema change detected",
    ),
    ErrorCode.S3_TABLES_API_FAILED: ErrorCodeMetadata(
        code=ErrorCode.S3_TABLES_API_FAILED,
        category=ErrorCategory.S3_TABLES,
        retryable=True,
        max_retries=3,
        description="S3 Tables API call failed",
    ),
    ErrorCode.S3_TABLES_THROTTLED: ErrorCodeMetadata(
        code=ErrorCode.S3_TABLES_THROTTLED,
        category=ErrorCategory.S3_TABLES,
        retryable=True,
        max_retries=5,
        description="S3 Tables API throttled (HTTP 429 or SlowDown)",
    ),
    ErrorCode.S3_TABLES_MAINTENANCE_CONFIG_FAILED: ErrorCodeMetadata(
        code=ErrorCode.S3_TABLES_MAINTENANCE_CONFIG_FAILED,
        category=ErrorCategory.S3_TABLES,
        retryable=False,
        max_retries=0,
        description="S3 Tables maintenance configuration failed after retries exhausted",
    ),
    ErrorCode.GLUE_ID_INVALID: ErrorCodeMetadata(
        code=ErrorCode.GLUE_ID_INVALID,
        category=ErrorCategory.VALIDATION,
        retryable=False,
        max_retries=0,
        description="Invalid glue.id format for S3 Tables catalog",
    ),
    ErrorCode.COMPACTION_STRATEGY_INVALID: ErrorCodeMetadata(
        code=ErrorCode.COMPACTION_STRATEGY_INVALID,
        category=ErrorCategory.VALIDATION,
        retryable=False,
        max_retries=0,
        description="Invalid compaction strategy or sort columns not in table schema",
    ),
    ErrorCode.ATHENA_VERIFICATION_TIMEOUT: ErrorCodeMetadata(
        code=ErrorCode.ATHENA_VERIFICATION_TIMEOUT,
        category=ErrorCategory.ATHENA,
        retryable=False,
        max_retries=0,
        description="Athena verification query timed out",
    ),
    ErrorCode.COST_CALCULATION_FAILED: ErrorCodeMetadata(
        code=ErrorCode.COST_CALCULATION_FAILED,
        category=ErrorCategory.COST,
        retryable=False,
        max_retries=0,
        description="Cost analysis calculation error",
    ),
    ErrorCode.CUSTOM_STRUCTURE_INVALID: ErrorCodeMetadata(
        code=ErrorCode.CUSTOM_STRUCTURE_INVALID,
        category=ErrorCategory.VALIDATION,
        retryable=False,
        max_retries=0,
        description="User-defined table structure is invalid",
    ),
}


# Retry delays for exponential backoff (seconds): 5s, 15s, 45s
RETRY_DELAYS_SECONDS: List[int] = [5, 15, 45]


def is_retryable(error_code: ErrorCode) -> bool:
    """Check if an error code is retryable.

    Args:
        error_code: The error code to check.

    Returns:
        True if the error is retryable, False otherwise.
    """
    metadata = ERROR_CODE_REGISTRY.get(error_code)
    if metadata is None:
        return False
    return metadata.retryable


def get_retry_delays(error_code: ErrorCode) -> List[int]:
    """Get the retry delay sequence for a retryable error code.

    Returns exponential backoff delays: [5, 15, 45] seconds.
    Returns empty list for non-retryable errors.

    Args:
        error_code: The error code to get delays for.

    Returns:
        List of delay values in seconds, or empty list if non-retryable.
    """
    if not is_retryable(error_code):
        return []
    metadata = ERROR_CODE_REGISTRY.get(error_code)
    if metadata is None:
        return []
    return RETRY_DELAYS_SECONDS[:metadata.max_retries]


def get_error_category(error_code: ErrorCode) -> Optional[ErrorCategory]:
    """Get the category for an error code.

    Args:
        error_code: The error code to look up.

    Returns:
        The ErrorCategory, or None if the code is not registered.
    """
    metadata = ERROR_CODE_REGISTRY.get(error_code)
    if metadata is None:
        return None
    return metadata.category


# --- Credential Sanitization ---

# Patterns that indicate sensitive data in log messages
_SENSITIVE_PATTERNS = [
    re.compile(r'(aws_secret_access_key["\s:=]+)[^\s,}"\']+', re.IGNORECASE),
    re.compile(r'(secret_key["\s:=]+)[^\s,}"\']+', re.IGNORECASE),
    re.compile(r'(password["\s:=]+)[^\s,}"\']+', re.IGNORECASE),
    re.compile(r'(session_token["\s:=]+)[^\s,}"\']+', re.IGNORECASE),
    re.compile(r'(access_key["\s:=]+)AKIA[A-Z0-9]{16}', re.IGNORECASE),
    re.compile(r'(token["\s:=]+)[^\s,}"\']+', re.IGNORECASE),
]

_REDACTED = "***REDACTED***"


def sanitize_message(message: str) -> str:
    """Remove any credential values from a log message.

    Scans the message for patterns that look like credentials (secret keys,
    passwords, tokens) and replaces the values with '***REDACTED***'.

    Args:
        message: The log message to sanitize.

    Returns:
        The sanitized message with credential values redacted.
    """
    sanitized = message
    for pattern in _SENSITIVE_PATTERNS:
        sanitized = pattern.sub(rf'\1{_REDACTED}', sanitized)
    return sanitized


def sanitize_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """Remove credential values from a context dictionary.

    Checks keys for sensitive names and redacts their values.
    Does not modify the original dictionary.

    Args:
        context: Dictionary of context values to sanitize.

    Returns:
        A new dictionary with sensitive values redacted.
    """
    sensitive_keys = {
        "aws_secret_access_key",
        "secret_key",
        "password",
        "session_token",
        "access_token",
        "credentials",
        "service_account_json",
        "service_account_json_encrypted",
        "aws_secret_access_key_encrypted",
    }

    sanitized = {}
    for key, value in context.items():
        if key.lower() in sensitive_keys:
            sanitized[key] = _REDACTED
        elif isinstance(value, str) and len(value) > 20 and key.lower().endswith(("_key", "_secret", "_token")):
            sanitized[key] = _REDACTED
        else:
            sanitized[key] = value
    return sanitized


# --- Structured Migration Logger ---

@dataclass
class MigrationLogEntry:
    """A structured log entry for migration operations.

    Attributes:
        timestamp: When the log entry was created (UTC).
        level: Log level (INFO, WARNING, ERROR, DEBUG).
        stage: Migration stage (export, transfer, review, load).
        operation: The specific operation being performed.
        message: Human-readable log message.
        error_code: Categorized error code (for ERROR entries).
        table_name: The table being operated on (if applicable).
        migration_id: The migration this log belongs to.
        context: Additional structured context data.
    """

    timestamp: datetime
    level: str
    stage: str
    operation: str
    message: str
    error_code: Optional[str] = None
    table_name: Optional[str] = None
    migration_id: Optional[int] = None
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary suitable for JSON serialization or DB storage."""
        result = {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level,
            "stage": self.stage,
            "operation": self.operation,
            "message": self.message,
        }
        if self.error_code:
            result["error_code"] = self.error_code
        if self.table_name:
            result["table_name"] = self.table_name
        if self.migration_id is not None:
            result["migration_id"] = self.migration_id
        if self.context:
            result["context"] = sanitize_context(self.context)
        return result


class MigrationLogger:
    """Structured logger for Iceberg migration operations.

    Provides methods for logging stage transitions, table operations,
    schema evolution, and errors with proper categorization. Ensures
    no credentials are included in log output.

    Args:
        migration_id: The ID of the migration being logged.
        logger_name: Optional custom logger name (defaults to module logger).
    """

    def __init__(self, migration_id: int, logger_name: Optional[str] = None) -> None:
        self._migration_id = migration_id
        self._logger = logging.getLogger(logger_name or __name__)
        self._entries: List[MigrationLogEntry] = []

    @property
    def entries(self) -> List[MigrationLogEntry]:
        """Get all log entries recorded by this logger."""
        return self._entries.copy()

    def log_stage_transition(self, from_stage: str, to_stage: str) -> MigrationLogEntry:
        """Log a migration stage transition as INFO.

        Args:
            from_stage: The stage being exited.
            to_stage: The stage being entered.

        Returns:
            The created log entry.
        """
        entry = MigrationLogEntry(
            timestamp=datetime.now(timezone.utc),
            level="INFO",
            stage=to_stage,
            operation="stage_transition",
            message=f"Migration stage transition: {from_stage} → {to_stage}",
            migration_id=self._migration_id,
            context={"from_stage": from_stage, "to_stage": to_stage},
        )
        self._record(entry)
        return entry

    def log_table_creation_start(
        self, table_name: str, column_count: int, partition_spec: Optional[str] = None
    ) -> MigrationLogEntry:
        """Log the start of Iceberg table creation as INFO.

        Args:
            table_name: Name of the table being created.
            column_count: Number of columns in the table schema.
            partition_spec: Description of the partition spec (optional).

        Returns:
            The created log entry.
        """
        entry = MigrationLogEntry(
            timestamp=datetime.now(timezone.utc),
            level="INFO",
            stage="load",
            operation="table_creation_start",
            message=f"Creating Iceberg table '{table_name}' with {column_count} columns",
            table_name=table_name,
            migration_id=self._migration_id,
            context={
                "column_count": column_count,
                "partition_spec": partition_spec or "none",
            },
        )
        self._record(entry)
        return entry

    def log_schema_mapping(
        self, table_name: str, column_count: int, partition_spec: Optional[str] = None,
        sort_order: Optional[str] = None
    ) -> MigrationLogEntry:
        """Log schema mapping details for a table as INFO.

        Args:
            table_name: Name of the table being mapped.
            column_count: Number of columns mapped.
            partition_spec: Description of the partition spec.
            sort_order: Description of the sort order.

        Returns:
            The created log entry.
        """
        entry = MigrationLogEntry(
            timestamp=datetime.now(timezone.utc),
            level="INFO",
            stage="load",
            operation="schema_mapping",
            message=(
                f"Schema mapping for '{table_name}': "
                f"{column_count} columns, partition={partition_spec or 'none'}, "
                f"sort_order={sort_order or 'none'}"
            ),
            table_name=table_name,
            migration_id=self._migration_id,
            context={
                "column_count": column_count,
                "partition_spec": partition_spec,
                "sort_order": sort_order,
            },
        )
        self._record(entry)
        return entry

    def log_data_file_registration(
        self, table_name: str, file_count: int
    ) -> MigrationLogEntry:
        """Log data file registration (append) for a table as INFO.

        Args:
            table_name: Name of the table receiving data files.
            file_count: Number of data files being registered.

        Returns:
            The created log entry.
        """
        entry = MigrationLogEntry(
            timestamp=datetime.now(timezone.utc),
            level="INFO",
            stage="load",
            operation="data_file_registration",
            message=f"Registering {file_count} data file(s) for table '{table_name}'",
            table_name=table_name,
            migration_id=self._migration_id,
            context={"file_count": file_count},
        )
        self._record(entry)
        return entry

    def log_table_creation_complete(
        self, table_name: str, duration_seconds: Optional[float] = None
    ) -> MigrationLogEntry:
        """Log successful table creation completion as INFO.

        Args:
            table_name: Name of the table that was created.
            duration_seconds: Time taken to create the table (optional).

        Returns:
            The created log entry.
        """
        msg = f"Iceberg table '{table_name}' created successfully"
        if duration_seconds is not None:
            msg += f" in {duration_seconds:.2f}s"

        entry = MigrationLogEntry(
            timestamp=datetime.now(timezone.utc),
            level="INFO",
            stage="load",
            operation="table_creation_complete",
            message=msg,
            table_name=table_name,
            migration_id=self._migration_id,
            context={"duration_seconds": duration_seconds},
        )
        self._record(entry)
        return entry

    def log_schema_evolution(
        self, table_name: str, column_name: str, operation_type: str,
        old_type: Optional[str] = None, new_type: Optional[str] = None
    ) -> MigrationLogEntry:
        """Log a schema evolution operation as INFO.

        Args:
            table_name: Name of the table being evolved.
            column_name: Name of the column being added or promoted.
            operation_type: Type of evolution ('column_addition' or 'type_promotion').
            old_type: Previous type (for promotions).
            new_type: New type being applied.

        Returns:
            The created log entry.
        """
        if operation_type == "type_promotion":
            message = (
                f"Schema evolution on '{table_name}': "
                f"type promotion for column '{column_name}' from {old_type} to {new_type}"
            )
        else:
            message = (
                f"Schema evolution on '{table_name}': "
                f"added column '{column_name}' as optional {new_type}"
            )

        entry = MigrationLogEntry(
            timestamp=datetime.now(timezone.utc),
            level="INFO",
            stage="load",
            operation="schema_evolution",
            message=message,
            table_name=table_name,
            migration_id=self._migration_id,
            context={
                "column_name": column_name,
                "operation_type": operation_type,
                "old_type": old_type,
                "new_type": new_type,
            },
        )
        self._record(entry)
        return entry

    def log_error(
        self, error_code: ErrorCode, operation: str, message: str,
        table_name: Optional[str] = None, context: Optional[Dict[str, Any]] = None
    ) -> MigrationLogEntry:
        """Log an error with a categorized error code.

        Ensures the message and context are sanitized to remove any
        credential values before logging.

        Args:
            error_code: The categorized error code from ErrorCode enum.
            operation: The operation that failed.
            message: Human-readable error description.
            table_name: The table involved (if applicable).
            context: Additional context (will be sanitized).

        Returns:
            The created log entry.
        """
        sanitized_msg = sanitize_message(message)
        sanitized_ctx = sanitize_context(context or {})

        # Add error code metadata to context
        metadata = ERROR_CODE_REGISTRY.get(error_code)
        if metadata:
            sanitized_ctx["error_category"] = metadata.category.value
            sanitized_ctx["retryable"] = metadata.retryable

        entry = MigrationLogEntry(
            timestamp=datetime.now(timezone.utc),
            level="ERROR",
            stage="load",
            operation=operation,
            message=sanitized_msg,
            error_code=error_code.value,
            table_name=table_name,
            migration_id=self._migration_id,
            context=sanitized_ctx,
        )
        self._record(entry)
        return entry

    def log_warning(
        self, operation: str, message: str,
        table_name: Optional[str] = None, error_code: Optional[ErrorCode] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> MigrationLogEntry:
        """Log a warning-level entry.

        Args:
            operation: The operation that triggered the warning.
            message: Human-readable warning description.
            table_name: The table involved (if applicable).
            error_code: Optional error code for categorization.
            context: Additional context (will be sanitized).

        Returns:
            The created log entry.
        """
        sanitized_msg = sanitize_message(message)
        sanitized_ctx = sanitize_context(context or {})

        entry = MigrationLogEntry(
            timestamp=datetime.now(timezone.utc),
            level="WARNING",
            stage="load",
            operation=operation,
            message=sanitized_msg,
            error_code=error_code.value if error_code else None,
            table_name=table_name,
            migration_id=self._migration_id,
            context=sanitized_ctx,
        )
        self._record(entry)
        return entry

    def log_progress(
        self, completed_tables: int, total_tables: int, progress_percentage: int
    ) -> MigrationLogEntry:
        """Log migration progress update as INFO.

        Args:
            completed_tables: Number of tables completed so far.
            total_tables: Total number of tables to process.
            progress_percentage: Current progress percentage (0-100).

        Returns:
            The created log entry.
        """
        entry = MigrationLogEntry(
            timestamp=datetime.now(timezone.utc),
            level="INFO",
            stage="load",
            operation="progress_update",
            message=(
                f"Load progress: {completed_tables}/{total_tables} tables "
                f"({progress_percentage}%)"
            ),
            migration_id=self._migration_id,
            context={
                "completed_tables": completed_tables,
                "total_tables": total_tables,
                "progress_percentage": progress_percentage,
            },
        )
        self._record(entry)
        return entry

    def _record(self, entry: MigrationLogEntry) -> None:
        """Record a log entry and emit it via the Python logger.

        Args:
            entry: The log entry to record.
        """
        self._entries.append(entry)

        # Emit via Python logging at the appropriate level
        log_level = getattr(logging, entry.level, logging.INFO)
        extra = {
            "migration_id": entry.migration_id,
            "stage": entry.stage,
            "operation": entry.operation,
        }
        if entry.error_code:
            extra["error_code"] = entry.error_code
        if entry.table_name:
            extra["table_name"] = entry.table_name

        self._logger.log(log_level, entry.message, extra=extra)
