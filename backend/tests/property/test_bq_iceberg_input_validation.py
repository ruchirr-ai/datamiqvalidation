# Feature: bq-to-iceberg-migration, Property 6: Input validation
"""
Property tests for Iceberg configuration field input validation.

Tests cover:
- Property 6: Input validation for Iceberg configuration fields
  - S3 bucket name validation (AWS naming rules)
  - Glue database name validation ([a-z0-9_]+, 1-255 chars)
  - Table bucket ARN format validation
  - IAM Role ARN format validation

Uses Hypothesis with minimum 100 iterations per property.
"""

from hypothesis import given, settings, assume, strategies as st

from services.bq_iceberg_migration.validators import (
    validate_s3_bucket_name,
    validate_glue_database_name,
    validate_table_bucket_arn,
    validate_iam_role_arn,
)


# =============================================================================
# Strategies
# =============================================================================

# --- S3 Bucket Name Strategies ---

# Valid S3 bucket names: 3-63 chars, lowercase letters/numbers/hyphens/dots,
# starts and ends with alphanumeric, no consecutive dots, no IP format
valid_s3_bucket_strategy = st.from_regex(
    r"[a-z0-9][a-z0-9\-]{1,61}[a-z0-9]",
    fullmatch=True,
).filter(
    lambda s: ".." not in s
    and len(s) >= 3
    and len(s) <= 63
    and "_" not in s
    # Exclude IP-like patterns
    and not all(
        part.isdigit() and 0 <= int(part) <= 255
        for part in s.split(".")
        if s.count(".") == 3
    )
)

# Invalid S3 bucket names: various violations
# Too short (1-2 chars)
too_short_bucket_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L",)),
    min_size=1,
    max_size=2,
).map(str.lower)

# Contains uppercase
uppercase_bucket_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=3,
    max_size=20,
).filter(lambda s: any(c.isupper() for c in s))

# Contains underscores
underscore_bucket_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"), whitelist_characters="_-"
    ),
    min_size=3,
    max_size=20,
).map(str.lower).filter(lambda s: "_" in s)

# Too long (>63 chars)
too_long_bucket_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789"),
    min_size=64,
    max_size=100,
)

# --- Glue Database Name Strategies ---

# Valid Glue DB names: [a-z0-9_]+, 1-255 chars
valid_glue_db_strategy = st.from_regex(
    r"[a-z0-9_]{1,255}",
    fullmatch=True,
)

# Invalid Glue DB names: contain uppercase, hyphens, spaces, or special chars
invalid_glue_db_chars_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P"),
        whitelist_characters="-. !@#$%",
    ),
    min_size=1,
    max_size=30,
).filter(
    lambda s: not all(c in "abcdefghijklmnopqrstuvwxyz0123456789_" for c in s)
    and len(s) > 0
)

# --- Table Bucket ARN Strategies ---

# Valid AWS regions
aws_region_strategy = st.sampled_from([
    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
    "eu-west-1", "eu-west-2", "eu-central-1",
    "ap-southeast-1", "ap-northeast-1",
])

# Valid 12-digit account IDs
account_id_strategy = st.from_regex(r"\d{12}", fullmatch=True)

# Valid bucket names for ARN (3-63 chars, lowercase alphanumeric + hyphens)
arn_bucket_name_strategy = st.from_regex(
    r"[a-z0-9][a-z0-9\-]{1,61}[a-z0-9]",
    fullmatch=True,
)

# Valid table bucket ARN strategy
valid_table_bucket_arn_strategy = st.builds(
    lambda region, account, bucket: f"arn:aws:s3tables:{region}:{account}:bucket/{bucket}",
    region=aws_region_strategy,
    account=account_id_strategy,
    bucket=arn_bucket_name_strategy,
)

# Invalid ARN: wrong service prefix
invalid_arn_prefix_strategy = st.builds(
    lambda region, account, bucket: f"arn:aws:s3:{region}:{account}:bucket/{bucket}",
    region=aws_region_strategy,
    account=account_id_strategy,
    bucket=arn_bucket_name_strategy,
)

# --- IAM Role ARN Strategies ---

# Valid role name characters
role_name_strategy = st.from_regex(
    r"[a-zA-Z0-9+=,.@\-_]{1,64}",
    fullmatch=True,
)

# Valid IAM Role ARN strategy
valid_iam_role_arn_strategy = st.builds(
    lambda account, role: f"arn:aws:iam::{account}:role/{role}",
    account=account_id_strategy,
    role=role_name_strategy,
)

# Invalid IAM Role ARN: uses :user/ instead of :role/
invalid_iam_role_arn_strategy = st.builds(
    lambda account, role: f"arn:aws:iam::{account}:user/{role}",
    account=account_id_strategy,
    role=role_name_strategy,
)


# =============================================================================
# Property 6: Input validation for Iceberg configuration fields
# =============================================================================


# --- S3 Bucket Name Validation ---


@given(bucket_name=valid_s3_bucket_strategy)
@settings(max_examples=100)
def test_s3_bucket_valid_names_accepted(bucket_name):
    """Property 6a: Valid S3 bucket names are accepted.

    For any string matching S3 bucket naming rules (3-63 chars, lowercase
    alphanumeric + hyphens/dots, no consecutive dots, no IP format),
    the validator SHALL accept it.

    **Validates: Requirements 1.2, 1.3, 1.5, 9.4**
    """
    is_valid, error = validate_s3_bucket_name(bucket_name)
    assert is_valid, (
        f"Valid S3 bucket name '{bucket_name}' was rejected: {error}"
    )
    assert error is None


@given(bucket_name=too_short_bucket_strategy)
@settings(max_examples=100)
def test_s3_bucket_too_short_rejected(bucket_name):
    """Property 6b: S3 bucket names shorter than 3 chars are rejected.

    For any string with length < 3, the validator SHALL reject it.

    **Validates: Requirements 1.2, 1.3, 1.5, 9.4**
    """
    is_valid, error = validate_s3_bucket_name(bucket_name)
    assert not is_valid, (
        f"Too-short bucket name '{bucket_name}' (len={len(bucket_name)}) "
        f"should be rejected"
    )
    assert error is not None


@given(bucket_name=underscore_bucket_strategy)
@settings(max_examples=100)
def test_s3_bucket_underscores_rejected(bucket_name):
    """Property 6c: S3 bucket names with underscores are rejected.

    For any string containing underscores, the validator SHALL reject it
    since S3 bucket names do not allow underscores.

    **Validates: Requirements 1.2, 1.3, 1.5, 9.4**
    """
    is_valid, error = validate_s3_bucket_name(bucket_name)
    assert not is_valid, (
        f"Bucket name with underscore '{bucket_name}' should be rejected"
    )
    assert error is not None
    assert "underscore" in error.lower() or "must not contain" in error.lower()


@given(bucket_name=too_long_bucket_strategy)
@settings(max_examples=100)
def test_s3_bucket_too_long_rejected(bucket_name):
    """Property 6d: S3 bucket names longer than 63 chars are rejected.

    For any string with length > 63, the validator SHALL reject it.

    **Validates: Requirements 1.2, 1.3, 1.5, 9.4**
    """
    is_valid, error = validate_s3_bucket_name(bucket_name)
    assert not is_valid, (
        f"Too-long bucket name (len={len(bucket_name)}) should be rejected"
    )
    assert error is not None


# --- Glue Database Name Validation ---


@given(db_name=valid_glue_db_strategy)
@settings(max_examples=100)
def test_glue_db_valid_names_accepted(db_name):
    """Property 6e: Valid Glue database names are accepted.

    For any string matching [a-z0-9_]+ with length 1-255,
    the validator SHALL accept it.

    **Validates: Requirements 1.2, 1.3, 1.5, 9.4**
    """
    is_valid, error = validate_glue_database_name(db_name)
    assert is_valid, (
        f"Valid Glue DB name '{db_name}' was rejected: {error}"
    )
    assert error is None


@given(db_name=invalid_glue_db_chars_strategy)
@settings(max_examples=100)
def test_glue_db_invalid_chars_rejected(db_name):
    """Property 6f: Glue database names with invalid characters are rejected.

    For any string containing characters outside [a-z0-9_],
    the validator SHALL reject it.

    **Validates: Requirements 1.2, 1.3, 1.5, 9.4**
    """
    is_valid, error = validate_glue_database_name(db_name)
    assert not is_valid, (
        f"Invalid Glue DB name '{db_name}' should be rejected"
    )
    assert error is not None


@given(
    db_name=st.text(
        alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789_"),
        min_size=256,
        max_size=300,
    )
)
@settings(max_examples=100)
def test_glue_db_too_long_rejected(db_name):
    """Property 6g: Glue database names longer than 255 chars are rejected.

    For any valid-character string with length > 255,
    the validator SHALL reject it.

    **Validates: Requirements 1.2, 1.3, 1.5, 9.4**
    """
    is_valid, error = validate_glue_database_name(db_name)
    assert not is_valid, (
        f"Too-long Glue DB name (len={len(db_name)}) should be rejected"
    )
    assert error is not None


# --- Table Bucket ARN Validation ---


@given(arn=valid_table_bucket_arn_strategy)
@settings(max_examples=100)
def test_table_bucket_arn_valid_accepted(arn):
    """Property 6h: Valid table bucket ARNs are accepted.

    For any string matching arn:aws:s3tables:<region>:<account-id>:bucket/<name>,
    the validator SHALL accept it.

    **Validates: Requirements 1.2, 1.3, 1.5, 9.4**
    """
    is_valid, error = validate_table_bucket_arn(arn)
    assert is_valid, (
        f"Valid table bucket ARN '{arn}' was rejected: {error}"
    )
    assert error is None


@given(arn=invalid_arn_prefix_strategy)
@settings(max_examples=100)
def test_table_bucket_arn_wrong_service_rejected(arn):
    """Property 6i: Table bucket ARNs with wrong service prefix are rejected.

    For any ARN using 's3' instead of 's3tables' service,
    the validator SHALL reject it.

    **Validates: Requirements 1.2, 1.3, 1.5, 9.4**
    """
    is_valid, error = validate_table_bucket_arn(arn)
    assert not is_valid, (
        f"ARN with wrong service '{arn}' should be rejected"
    )
    assert error is not None


# --- IAM Role ARN Validation ---


@given(arn=valid_iam_role_arn_strategy)
@settings(max_examples=100)
def test_iam_role_arn_valid_accepted(arn):
    """Property 6j: Valid IAM Role ARNs are accepted.

    For any string matching arn:aws:iam::<account-id>:role/<path>,
    the validator SHALL accept it.

    **Validates: Requirements 1.2, 1.3, 1.5, 9.4**
    """
    is_valid, error = validate_iam_role_arn(arn)
    assert is_valid, (
        f"Valid IAM Role ARN '{arn}' was rejected: {error}"
    )
    assert error is None


@given(arn=invalid_iam_role_arn_strategy)
@settings(max_examples=100)
def test_iam_role_arn_user_resource_rejected(arn):
    """Property 6k: IAM ARNs with :user/ instead of :role/ are rejected.

    For any ARN using ':user/' resource type instead of ':role/',
    the validator SHALL reject it.

    **Validates: Requirements 1.2, 1.3, 1.5, 9.4**
    """
    is_valid, error = validate_iam_role_arn(arn)
    assert not is_valid, (
        f"IAM ARN with :user/ resource '{arn}' should be rejected"
    )
    assert error is not None


@given(
    arbitrary_string=st.text(min_size=0, max_size=100),
)
@settings(max_examples=100)
def test_validators_never_crash_on_arbitrary_input(arbitrary_string):
    """Property 6l: Validators never crash on arbitrary input.

    For any arbitrary string, all validators SHALL return a valid
    (bool, Optional[str]) tuple without raising exceptions.

    **Validates: Requirements 1.2, 1.3, 1.5, 9.4**
    """
    # S3 bucket
    result = validate_s3_bucket_name(arbitrary_string)
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], bool)
    assert result[1] is None or isinstance(result[1], str)

    # Glue database
    result = validate_glue_database_name(arbitrary_string)
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], bool)
    assert result[1] is None or isinstance(result[1], str)

    # Table bucket ARN
    result = validate_table_bucket_arn(arbitrary_string)
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], bool)
    assert result[1] is None or isinstance(result[1], str)

    # IAM Role ARN
    result = validate_iam_role_arn(arbitrary_string)
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], bool)
    assert result[1] is None or isinstance(result[1], str)
