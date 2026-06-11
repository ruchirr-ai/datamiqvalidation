"""
Input Validators for Iceberg Configuration Fields

Provides validation functions for all user-supplied Iceberg migration
configuration values. Each validator returns a tuple of (is_valid, error_message)
where error_message is None when validation passes.

Validation rules:
- S3 bucket name: AWS S3 naming rules (1-63 chars, lowercase, no underscores,
  no consecutive dots, no IP format, starts/ends with alphanumeric)
- Glue database name: [a-z0-9_]+, 1-255 characters
- Table bucket ARN: arn:aws:s3tables:<region>:<account-id>:bucket/<name>
- IAM Role ARN: arn:aws:iam::<account-id>:role/<path>
- Parallelism: integer 1-16

Requirements: 1.2, 1.3, 1.5, 9.4
"""

import re
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# Type alias for validator return type
ValidationResult = Tuple[bool, Optional[str]]


# --- S3 Bucket Name Validation ---

# S3 bucket naming rules:
# - 3 to 63 characters (AWS docs say 3 minimum, but requirement says 1;
#   we follow AWS actual rules: 3-63)
# - Only lowercase letters, numbers, hyphens, and dots
# - Must start and end with a letter or number
# - No consecutive dots (..)
# - Must not be formatted as an IP address (e.g., 192.168.5.4)
# - No underscores allowed
_S3_BUCKET_MIN_LENGTH = 3
_S3_BUCKET_MAX_LENGTH = 63
_S3_BUCKET_VALID_CHARS_PATTERN = re.compile(r'^[a-z0-9][a-z0-9.\-]*[a-z0-9]$')
_S3_BUCKET_SINGLE_CHAR_PATTERN = re.compile(r'^[a-z0-9]$')
_IP_ADDRESS_PATTERN = re.compile(
    r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$'
)


def validate_s3_bucket_name(bucket_name: str) -> ValidationResult:
    """
    Validate an S3 bucket name against AWS S3 naming rules.

    Rules enforced:
    - Length between 3 and 63 characters
    - Only lowercase letters, numbers, hyphens, and dots allowed
    - Must start and end with a lowercase letter or number
    - No consecutive dots (..)
    - Must not be formatted as an IP address (e.g., 192.168.5.4)
    - No underscores allowed

    Args:
        bucket_name: The S3 bucket name to validate.

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.

    Examples:
        >>> validate_s3_bucket_name("my-bucket")
        (True, None)
        >>> validate_s3_bucket_name("My-Bucket")
        (False, "S3 bucket name must contain only lowercase letters, ...")
    """
    if not bucket_name:
        return (False, "S3 bucket name is required and cannot be empty.")

    if len(bucket_name) < _S3_BUCKET_MIN_LENGTH:
        return (
            False,
            f"S3 bucket name must be at least {_S3_BUCKET_MIN_LENGTH} characters long. "
            f"Got {len(bucket_name)} character(s)."
        )

    if len(bucket_name) > _S3_BUCKET_MAX_LENGTH:
        return (
            False,
            f"S3 bucket name must be at most {_S3_BUCKET_MAX_LENGTH} characters long. "
            f"Got {len(bucket_name)} characters."
        )

    # Check for underscores explicitly (common mistake)
    if '_' in bucket_name:
        return (
            False,
            "S3 bucket name must not contain underscores. "
            "Use hyphens (-) instead."
        )

    # Check start/end characters (must be lowercase letter or digit)
    if not re.match(r'^[a-z0-9]', bucket_name):
        return (
            False,
            "S3 bucket name must start with a lowercase letter or number."
        )

    if not re.match(r'[a-z0-9]$', bucket_name):
        return (
            False,
            "S3 bucket name must end with a lowercase letter or number."
        )

    # Check for valid characters (lowercase letters, numbers, hyphens, dots)
    if not re.match(r'^[a-z0-9.\-]+$', bucket_name):
        return (
            False,
            "S3 bucket name must contain only lowercase letters, numbers, "
            "hyphens (-), and dots (.)."
        )

    # Check for consecutive dots
    if '..' in bucket_name:
        return (
            False,
            "S3 bucket name must not contain consecutive dots (..)."
        )

    # Check for IP address format
    if _IP_ADDRESS_PATTERN.match(bucket_name):
        return (
            False,
            "S3 bucket name must not be formatted as an IP address "
            "(e.g., 192.168.5.4)."
        )

    return (True, None)


# --- Glue ID (S3 Tables Catalog Identifier) Validation ---

# Format: {account_id}:s3tablescatalog/{bucket-name}
# - account_id: exactly 12 digits
# - bucket-name: valid S3 bucket name (3-63 chars, lowercase alphanumeric + dots/hyphens)
_GLUE_ID_PATTERN = re.compile(
    r'^\d{12}:s3tablescatalog/[a-z0-9][a-z0-9.\-]{1,61}[a-z0-9]$'
)


def validate_glue_id(glue_id: str) -> ValidationResult:
    """
    Validate a glue.id catalog identifier for S3 Tables.

    Expected format: {account_id}:s3tablescatalog/{bucket-name}
    - account_id: 12-digit AWS account ID
    - bucket-name: valid S3 bucket name (3-63 chars)

    Args:
        glue_id: The glue.id value to validate.

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.

    Examples:
        >>> validate_glue_id("123456789012:s3tablescatalog/my-bucket")
        (True, None)
        >>> validate_glue_id("invalid-format")
        (False, "Invalid glue.id format. Expected: ...")
    """
    if not glue_id:
        return (
            False,
            "Invalid glue.id format. Expected: "
            "{account_id}:s3tablescatalog/{bucket-name}. "
            "Verify your table bucket ARN is correct."
        )

    if not _GLUE_ID_PATTERN.match(glue_id):
        return (
            False,
            "Invalid glue.id format. Expected: "
            "{account_id}:s3tablescatalog/{bucket-name}. "
            "Verify your table bucket ARN is correct."
        )

    return (True, None)


# --- Glue Database Name Validation ---

_GLUE_DB_MIN_LENGTH = 1
_GLUE_DB_MAX_LENGTH = 255
_GLUE_DB_PATTERN = re.compile(r'^[a-z0-9_]+$')


def validate_glue_database_name(database_name: str) -> ValidationResult:
    """
    Validate an AWS Glue Data Catalog database name.

    Rules enforced:
    - Length between 1 and 255 characters
    - Only lowercase letters, numbers, and underscores allowed
    - Pattern: [a-z0-9_]+

    Args:
        database_name: The Glue database name to validate.

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.

    Examples:
        >>> validate_glue_database_name("my_database")
        (True, None)
        >>> validate_glue_database_name("My-Database")
        (False, "Glue database name must contain only lowercase letters, ...")
    """
    if not database_name:
        return (False, "Glue database name is required and cannot be empty.")

    if len(database_name) > _GLUE_DB_MAX_LENGTH:
        return (
            False,
            f"Glue database name must be at most {_GLUE_DB_MAX_LENGTH} characters long. "
            f"Got {len(database_name)} characters."
        )

    if not _GLUE_DB_PATTERN.match(database_name):
        return (
            False,
            "Glue database name must contain only lowercase letters (a-z), "
            "numbers (0-9), and underscores (_)."
        )

    return (True, None)


# --- Table Bucket ARN Validation ---

# Format: arn:aws:s3tables:<region>:<account-id>:bucket/<bucket-name>
# Region: e.g., us-east-1, eu-west-2, ap-southeast-1
# Account ID: 12-digit number
# Bucket name: alphanumeric, hyphens, 3-63 chars
_TABLE_BUCKET_ARN_PATTERN = re.compile(
    r'^arn:aws:s3tables:'
    r'[a-z]{2}(-gov)?-[a-z]+-\d+:'  # region (e.g., us-east-1, us-gov-west-1)
    r'\d{12}:'                        # 12-digit account ID
    r'bucket/'                        # literal "bucket/"
    r'[a-z0-9][a-z0-9\-]{1,61}[a-z0-9]$'  # bucket name (3-63 chars)
)


def validate_table_bucket_arn(arn: str) -> ValidationResult:
    """
    Validate an AWS S3 Tables table bucket ARN.

    Expected format: arn:aws:s3tables:<region>:<account-id>:bucket/<bucket-name>

    Where:
    - region: Valid AWS region (e.g., us-east-1, eu-west-2)
    - account-id: 12-digit AWS account ID
    - bucket-name: Valid S3 bucket name (3-63 chars, lowercase alphanumeric + hyphens)

    Args:
        arn: The table bucket ARN to validate.

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.

    Examples:
        >>> validate_table_bucket_arn("arn:aws:s3tables:us-east-1:123456789012:bucket/my-bucket")
        (True, None)
        >>> validate_table_bucket_arn("arn:aws:s3:us-east-1:123456789012:bucket/my-bucket")
        (False, "Table bucket ARN must match the format ...")
    """
    if not arn:
        return (False, "Table bucket ARN is required and cannot be empty.")

    if not arn.startswith("arn:aws:s3tables:"):
        return (
            False,
            "Table bucket ARN must start with 'arn:aws:s3tables:'. "
            "Expected format: arn:aws:s3tables:<region>:<account-id>:bucket/<bucket-name>"
        )

    if not _TABLE_BUCKET_ARN_PATTERN.match(arn):
        return (
            False,
            "Table bucket ARN must match the format "
            "'arn:aws:s3tables:<region>:<account-id>:bucket/<bucket-name>' "
            "where region is a valid AWS region (e.g., us-east-1), "
            "account-id is a 12-digit number, and bucket-name is 3-63 "
            "lowercase alphanumeric characters with hyphens."
        )

    return (True, None)


# --- IAM Role ARN Validation ---

# Format: arn:aws:iam::<account-id>:role/<role-path>
# Account ID: 12-digit number
# Role path: can include forward slashes for path-based roles
# Role name: alphanumeric, hyphens, underscores, dots, plus signs, equals, commas, @
_IAM_ROLE_ARN_PATTERN = re.compile(
    r'^arn:aws:iam::'
    r'\d{12}:'                        # 12-digit account ID
    r'role/'                          # literal "role/"
    r'[a-zA-Z0-9+=,.@\-_/]+$'        # role path and name
)


def validate_iam_role_arn(arn: str) -> ValidationResult:
    """
    Validate an AWS IAM Role ARN.

    Expected format: arn:aws:iam::<account-id>:role/<role-path>

    Where:
    - account-id: 12-digit AWS account ID
    - role-path: Role name with optional path prefix (e.g., service-role/MyRole)

    Args:
        arn: The IAM Role ARN to validate.

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.

    Examples:
        >>> validate_iam_role_arn("arn:aws:iam::123456789012:role/MyRole")
        (True, None)
        >>> validate_iam_role_arn("arn:aws:iam::123456789012:user/MyUser")
        (False, "IAM Role ARN must match the format ...")
    """
    if not arn:
        return (False, "IAM Role ARN is required and cannot be empty.")

    if not arn.startswith("arn:aws:iam::"):
        return (
            False,
            "IAM Role ARN must start with 'arn:aws:iam::'. "
            "Expected format: arn:aws:iam::<account-id>:role/<role-path>"
        )

    if ":role/" not in arn:
        return (
            False,
            "IAM Role ARN must contain ':role/' to specify a role resource. "
            "Expected format: arn:aws:iam::<account-id>:role/<role-path>"
        )

    if not _IAM_ROLE_ARN_PATTERN.match(arn):
        return (
            False,
            "IAM Role ARN must match the format "
            "'arn:aws:iam::<account-id>:role/<role-path>' "
            "where account-id is a 12-digit number and role-path contains "
            "alphanumeric characters, hyphens, underscores, dots, plus signs, "
            "equals, commas, at signs, and forward slashes."
        )

    return (True, None)


# --- Parallelism Range Validation ---

_PARALLELISM_MIN = 1
_PARALLELISM_MAX = 16


def validate_parallelism(parallelism: int) -> ValidationResult:
    """
    Validate the parallelism level for Iceberg table loading.

    Rules enforced:
    - Must be an integer between 1 and 16 (inclusive)

    Args:
        parallelism: The number of concurrent tables to load.

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.

    Examples:
        >>> validate_parallelism(4)
        (True, None)
        >>> validate_parallelism(0)
        (False, "Parallelism must be between 1 and 16. Got 0.")
    """
    if not isinstance(parallelism, int) or isinstance(parallelism, bool):
        return (
            False,
            f"Parallelism must be an integer. Got {type(parallelism).__name__}."
        )

    if parallelism < _PARALLELISM_MIN or parallelism > _PARALLELISM_MAX:
        return (
            False,
            f"Parallelism must be between {_PARALLELISM_MIN} and "
            f"{_PARALLELISM_MAX}. Got {parallelism}."
        )

    return (True, None)


# --- Maintenance Configuration Validation ---

_MAINTENANCE_TARGET_FILE_SIZE_MIN = 64
_MAINTENANCE_TARGET_FILE_SIZE_MAX = 512


def validate_maintenance_config(
    target_file_size_mb: int,
    min_snapshots_to_keep: int,
    max_snapshot_age_hours: int,
) -> ValidationResult:
    """
    Validate S3 Tables maintenance configuration values.

    Rules enforced:
    - target_file_size_mb: integer in [64, 512]
    - min_snapshots_to_keep: positive integer (> 0)
    - max_snapshot_age_hours: positive integer (> 0)

    Args:
        target_file_size_mb: Target file size for compaction in megabytes.
        min_snapshots_to_keep: Minimum number of snapshots to retain.
        max_snapshot_age_hours: Maximum age of snapshots in hours.

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.

    Examples:
        >>> validate_maintenance_config(512, 30, 720)
        (True, None)
        >>> validate_maintenance_config(32, 30, 720)
        (False, "Target file size must be between 64 MB and 512 MB. Got 32.")
        >>> validate_maintenance_config(512, 0, 720)
        (False, "Minimum snapshots to keep must be a positive integer. Got 0.")
    """
    if not isinstance(target_file_size_mb, int) or isinstance(target_file_size_mb, bool):
        return (
            False,
            f"Target file size must be an integer. Got {type(target_file_size_mb).__name__}."
        )

    if not isinstance(min_snapshots_to_keep, int) or isinstance(min_snapshots_to_keep, bool):
        return (
            False,
            f"Minimum snapshots to keep must be an integer. Got {type(min_snapshots_to_keep).__name__}."
        )

    if not isinstance(max_snapshot_age_hours, int) or isinstance(max_snapshot_age_hours, bool):
        return (
            False,
            f"Maximum snapshot age must be an integer. Got {type(max_snapshot_age_hours).__name__}."
        )

    if target_file_size_mb == 0 or target_file_size_mb is None:
        return (
            False,
            "Target file size is required."
        )

    if (
        target_file_size_mb < _MAINTENANCE_TARGET_FILE_SIZE_MIN
        or target_file_size_mb > _MAINTENANCE_TARGET_FILE_SIZE_MAX
    ):
        return (
            False,
            f"Target file size must be between {_MAINTENANCE_TARGET_FILE_SIZE_MIN} MB "
            f"and {_MAINTENANCE_TARGET_FILE_SIZE_MAX} MB. Got {target_file_size_mb}."
        )

    if min_snapshots_to_keep <= 0:
        return (
            False,
            f"Minimum snapshots to keep must be a positive integer. Got {min_snapshots_to_keep}."
        )

    if max_snapshot_age_hours <= 0:
        return (
            False,
            f"Maximum snapshot age must be a positive integer (hours). Got {max_snapshot_age_hours}."
        )

    return (True, None)


# --- S3 Tables Parallelism Validation ---

_S3_TABLES_PARALLELISM_MIN = 1
_S3_TABLES_PARALLELISM_MAX = 8


def validate_s3_tables_parallelism(parallelism: int) -> ValidationResult:
    """
    Validate the parallelism level for S3 Tables destinations (max 8).

    S3 Tables has lower API concurrency limits than standard S3 Iceberg.
    The maximum parallelism is capped at 8 to avoid throttling errors.

    Rules enforced:
    - Must be an integer between 1 and 8 (inclusive)

    Args:
        parallelism: The number of concurrent tables to load for S3 Tables.

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.

    Examples:
        >>> validate_s3_tables_parallelism(4)
        (True, None)
        >>> validate_s3_tables_parallelism(9)
        (False, "S3 Tables parallelism must be between 1 and 8. Got 9. ...")
        >>> validate_s3_tables_parallelism(0)
        (False, "S3 Tables parallelism must be between 1 and 8. Got 0. ...")
    """
    if not isinstance(parallelism, int) or isinstance(parallelism, bool):
        return (
            False,
            f"S3 Tables parallelism must be an integer. Got {type(parallelism).__name__}."
        )

    if parallelism < _S3_TABLES_PARALLELISM_MIN or parallelism > _S3_TABLES_PARALLELISM_MAX:
        return (
            False,
            f"S3 Tables parallelism must be between {_S3_TABLES_PARALLELISM_MIN} and "
            f"{_S3_TABLES_PARALLELISM_MAX}. Got {parallelism}. "
            f"S3 Tables has lower concurrency limits than standard S3."
        )

    return (True, None)


# --- Compaction Strategy Validation ---

_VALID_COMPACTION_STRATEGIES = {"binpack", "sort", "z-order"}


def validate_compaction_strategy(
    strategy: str,
    sort_columns: list[str],
    table_schema_columns: list[str],
) -> ValidationResult:
    """
    Validate compaction strategy and sort column references.

    Rules enforced:
    - strategy must be one of: binpack, sort, z-order
    - If strategy is sort or z-order, sort_columns must be non-empty
    - Each sort column must exist in table_schema_columns

    Args:
        strategy: The compaction strategy name.
        sort_columns: List of column names to sort by (for sort/z-order strategies).
        table_schema_columns: List of valid column names in the table schema.

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.

    Examples:
        >>> validate_compaction_strategy("binpack", [], ["col_a", "col_b"])
        (True, None)
        >>> validate_compaction_strategy("sort", ["col_a"], ["col_a", "col_b"])
        (True, None)
        >>> validate_compaction_strategy("invalid", [], ["col_a"])
        (False, "Compaction strategy must be one of: binpack, sort, z-order. Got 'invalid'.")
        >>> validate_compaction_strategy("sort", [], ["col_a"])
        (False, "Sort columns must be specified when using 'sort' compaction strategy.")
        >>> validate_compaction_strategy("z-order", ["missing_col"], ["col_a"])
        (False, "Sort columns not found in table schema: missing_col")
    """
    if strategy not in _VALID_COMPACTION_STRATEGIES:
        return (
            False,
            f"Compaction strategy must be one of: binpack, sort, z-order. "
            f"Got '{strategy}'."
        )

    if strategy in ("sort", "z-order"):
        if not sort_columns:
            return (
                False,
                f"Sort columns must be specified when using '{strategy}' "
                f"compaction strategy."
            )

        # Check that all sort columns exist in the table schema
        schema_set = set(table_schema_columns)
        invalid_columns = [col for col in sort_columns if col not in schema_set]
        if invalid_columns:
            return (
                False,
                f"Sort columns not found in table schema: "
                f"{', '.join(invalid_columns)}"
            )

    return (True, None)


# --- Convenience: Validate All Iceberg S3 Configuration ---


def validate_iceberg_s3_config(
    s3_bucket: str,
    glue_database_name: str,
    parallelism: int = 4,
    aws_role_arn: Optional[str] = None,
) -> ValidationResult:
    """
    Validate all configuration fields for an Iceberg S3 destination.

    Validates S3 bucket name, Glue database name, parallelism, and
    optionally the IAM Role ARN.

    Args:
        s3_bucket: S3 bucket name for Iceberg data storage.
        glue_database_name: AWS Glue Data Catalog database name.
        parallelism: Number of concurrent tables to load (1-16).
        aws_role_arn: Optional IAM Role ARN for authentication.

    Returns:
        Tuple of (is_valid, error_message). error_message is None if all valid.
    """
    is_valid, error = validate_s3_bucket_name(s3_bucket)
    if not is_valid:
        return (False, f"S3 bucket: {error}")

    is_valid, error = validate_glue_database_name(glue_database_name)
    if not is_valid:
        return (False, f"Glue database: {error}")

    is_valid, error = validate_parallelism(parallelism)
    if not is_valid:
        return (False, f"Parallelism: {error}")

    if aws_role_arn is not None:
        is_valid, error = validate_iam_role_arn(aws_role_arn)
        if not is_valid:
            return (False, f"IAM Role ARN: {error}")

    return (True, None)


# --- Convenience: Validate All Iceberg S3 Tables Configuration ---


def validate_iceberg_s3_tables_config(
    table_bucket_arn: str,
    glue_database_name: str,
    parallelism: int = 4,
    aws_role_arn: Optional[str] = None,
) -> ValidationResult:
    """
    Validate all configuration fields for an Iceberg S3 Tables destination.

    Validates table bucket ARN, Glue database name, parallelism, and
    optionally the IAM Role ARN.

    Args:
        table_bucket_arn: S3 Tables table bucket ARN.
        glue_database_name: AWS Glue Data Catalog database name.
        parallelism: Number of concurrent tables to load (1-16).
        aws_role_arn: Optional IAM Role ARN for authentication.

    Returns:
        Tuple of (is_valid, error_message). error_message is None if all valid.
    """
    is_valid, error = validate_table_bucket_arn(table_bucket_arn)
    if not is_valid:
        return (False, f"Table bucket ARN: {error}")

    is_valid, error = validate_glue_database_name(glue_database_name)
    if not is_valid:
        return (False, f"Glue database: {error}")

    is_valid, error = validate_parallelism(parallelism)
    if not is_valid:
        return (False, f"Parallelism: {error}")

    if aws_role_arn is not None:
        is_valid, error = validate_iam_role_arn(aws_role_arn)
        if not is_valid:
            return (False, f"IAM Role ARN: {error}")

    return (True, None)
