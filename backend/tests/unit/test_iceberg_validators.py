"""
Unit tests for Iceberg configuration field validators.

Tests S3 bucket name, Glue database name, table bucket ARN,
IAM Role ARN, and parallelism validation with sample payloads
for valid and invalid inputs.

Requirements: 1.2, 1.3, 1.5, 9.4
"""

import pytest

from services.bq_iceberg_migration.validators import (
    validate_s3_bucket_name,
    validate_glue_database_name,
    validate_table_bucket_arn,
    validate_iam_role_arn,
    validate_parallelism,
    validate_iceberg_s3_config,
    validate_iceberg_s3_tables_config,
    validate_maintenance_config,
)


# =============================================================================
# Sample Payloads
# =============================================================================

# --- S3 Bucket Name Samples ---

VALID_S3_BUCKET_NAMES = [
    "my-bucket",
    "my.bucket.name",
    "bucket123",
    "123bucket",
    "a-b",                          # minimum 3 chars
    "my-data-lake-bucket-2025",
    "a" * 63,                       # maximum 63 chars
    "test.bucket.with.dots",
    "bucket-with-hyphens",
    "a1b",                          # 3 chars, starts/ends alphanumeric
]

INVALID_S3_BUCKET_NAMES = [
    ("", "required and cannot be empty"),
    ("ab", "at least 3 characters"),                    # too short
    ("a" * 64, "at most 63 characters"),                # too long
    ("My-Bucket", "only lowercase"),                    # uppercase
    ("my_bucket", "must not contain underscores"),      # underscores
    ("my..bucket", "consecutive dots"),                 # consecutive dots
    ("-my-bucket", "must start with"),                  # starts with hyphen
    ("my-bucket-", "must end with"),                    # ends with hyphen
    (".my-bucket", "must start with"),                  # starts with dot
    ("my-bucket.", "must end with"),                    # ends with dot
    ("192.168.1.1", "IP address"),                      # IP address format
    ("my bucket", "only lowercase"),                    # spaces
    ("my@bucket", "only lowercase"),                    # special chars
]

# --- Glue Database Name Samples ---

VALID_GLUE_DB_NAMES = [
    "my_database",
    "db",
    "a",                            # minimum 1 char
    "database_2025",
    "analytics_prod",
    "a" * 255,                      # maximum 255 chars
    "123",                          # numbers only
    "_underscore_start",
    "all_lowercase_with_numbers_123",
]

INVALID_GLUE_DB_NAMES = [
    ("", "required and cannot be empty"),
    ("a" * 256, "at most 255 characters"),              # too long
    ("My-Database", "only lowercase"),                  # uppercase + hyphens
    ("my-database", "only lowercase"),                  # hyphens
    ("my database", "only lowercase"),                  # spaces
    ("my.database", "only lowercase"),                  # dots
    ("db@name", "only lowercase"),                      # special chars
    ("UPPERCASE", "only lowercase"),                    # all uppercase
]

# --- Table Bucket ARN Samples ---

VALID_TABLE_BUCKET_ARNS = [
    "arn:aws:s3tables:us-east-1:123456789012:bucket/my-bucket",
    "arn:aws:s3tables:eu-west-2:987654321098:bucket/data-lake-bucket",
    "arn:aws:s3tables:ap-southeast-1:111222333444:bucket/analytics-bucket-01",
    "arn:aws:s3tables:us-gov-west-1:123456789012:bucket/gov-bucket",
]

INVALID_TABLE_BUCKET_ARNS = [
    ("", "required and cannot be empty"),
    ("arn:aws:s3:us-east-1:123456789012:bucket/my-bucket",
     "must start with 'arn:aws:s3tables:'"),
    ("arn:aws:s3tables:us-east-1:12345:bucket/my-bucket",
     "must match the format"),                          # short account ID
    ("arn:aws:s3tables:us-east-1:123456789012:table/my-table",
     "must match the format"),                          # wrong resource type
    ("arn:aws:s3tables:INVALID:123456789012:bucket/my-bucket",
     "must match the format"),                          # invalid region
    ("arn:aws:s3tables:us-east-1:123456789012:bucket/",
     "must match the format"),                          # empty bucket name
    ("not-an-arn-at-all",
     "must start with 'arn:aws:s3tables:'"),
]

# --- IAM Role ARN Samples ---

VALID_IAM_ROLE_ARNS = [
    "arn:aws:iam::123456789012:role/MyRole",
    "arn:aws:iam::123456789012:role/service-role/AWSGlueServiceRole",
    "arn:aws:iam::987654321098:role/DataMIQ-Iceberg-Migration-Role",
    "arn:aws:iam::111222333444:role/path/to/my-role",
    "arn:aws:iam::123456789012:role/role_with_underscores",
    "arn:aws:iam::123456789012:role/role.with.dots",
    "arn:aws:iam::123456789012:role/role+plus=equals,comma@at",
]

INVALID_IAM_ROLE_ARNS = [
    ("", "required and cannot be empty"),
    ("arn:aws:iam::123456789012:user/MyUser",
     "must contain ':role/'"),                           # user, not role
    ("arn:aws:iam::12345:role/MyRole",
     "must match the format"),                          # short account ID
    ("arn:aws:iam:us-east-1:123456789012:role/MyRole",
     "must start with 'arn:aws:iam::'"),                # region in IAM ARN
    ("arn:aws:s3:::my-bucket",
     "must start with 'arn:aws:iam::'"),                # wrong service
    ("not-an-arn",
     "must start with 'arn:aws:iam::'"),
    ("arn:aws:iam::123456789012:role/",
     "must match the format"),                          # empty role name
]

# --- Parallelism Samples ---

VALID_PARALLELISM_VALUES = [1, 2, 4, 8, 12, 16]

INVALID_PARALLELISM_VALUES = [
    (0, "must be between 1 and 16"),
    (-1, "must be between 1 and 16"),
    (17, "must be between 1 and 16"),
    (100, "must be between 1 and 16"),
]


# =============================================================================
# S3 Bucket Name Validation Tests
# =============================================================================

class TestValidateS3BucketName:
    """Tests for validate_s3_bucket_name validator."""

    @pytest.mark.parametrize("bucket_name", VALID_S3_BUCKET_NAMES)
    def test_valid_bucket_names(self, bucket_name):
        """Test that valid S3 bucket names pass validation."""
        is_valid, error = validate_s3_bucket_name(bucket_name)
        assert is_valid is True
        assert error is None

    @pytest.mark.parametrize("bucket_name,expected_error_fragment", INVALID_S3_BUCKET_NAMES)
    def test_invalid_bucket_names(self, bucket_name, expected_error_fragment):
        """Test that invalid S3 bucket names fail with appropriate error messages."""
        is_valid, error = validate_s3_bucket_name(bucket_name)
        assert is_valid is False
        assert error is not None
        assert expected_error_fragment.lower() in error.lower()

    def test_bucket_name_exactly_3_chars(self):
        """Test minimum valid length (3 characters)."""
        is_valid, error = validate_s3_bucket_name("abc")
        assert is_valid is True
        assert error is None

    def test_bucket_name_exactly_63_chars(self):
        """Test maximum valid length (63 characters)."""
        name = "a" + "b" * 61 + "c"  # 63 chars, starts/ends alphanumeric
        is_valid, error = validate_s3_bucket_name(name)
        assert is_valid is True
        assert error is None

    def test_bucket_name_with_single_dot(self):
        """Test that single dots between labels are allowed."""
        is_valid, error = validate_s3_bucket_name("my.bucket")
        assert is_valid is True
        assert error is None

    def test_bucket_name_ip_like_but_not_ip(self):
        """Test that names resembling IPs but with invalid octets pass."""
        # 999 is not a valid IP octet, so this is not an IP address
        is_valid, error = validate_s3_bucket_name("999.999.999.999")
        # This still matches the IP regex pattern (digits.digits.digits.digits)
        assert is_valid is False
        assert "IP address" in error


# =============================================================================
# Glue Database Name Validation Tests
# =============================================================================

class TestValidateGlueDatabaseName:
    """Tests for validate_glue_database_name validator."""

    @pytest.mark.parametrize("db_name", VALID_GLUE_DB_NAMES)
    def test_valid_database_names(self, db_name):
        """Test that valid Glue database names pass validation."""
        is_valid, error = validate_glue_database_name(db_name)
        assert is_valid is True
        assert error is None

    @pytest.mark.parametrize("db_name,expected_error_fragment", INVALID_GLUE_DB_NAMES)
    def test_invalid_database_names(self, db_name, expected_error_fragment):
        """Test that invalid Glue database names fail with appropriate error messages."""
        is_valid, error = validate_glue_database_name(db_name)
        assert is_valid is False
        assert error is not None
        assert expected_error_fragment.lower() in error.lower()

    def test_database_name_single_char(self):
        """Test minimum valid length (1 character)."""
        is_valid, error = validate_glue_database_name("a")
        assert is_valid is True
        assert error is None

    def test_database_name_max_length(self):
        """Test maximum valid length (255 characters)."""
        is_valid, error = validate_glue_database_name("a" * 255)
        assert is_valid is True
        assert error is None

    def test_database_name_numbers_only(self):
        """Test that all-numeric names are valid."""
        is_valid, error = validate_glue_database_name("12345")
        assert is_valid is True
        assert error is None

    def test_database_name_underscores_only(self):
        """Test that all-underscore names are valid."""
        is_valid, error = validate_glue_database_name("___")
        assert is_valid is True
        assert error is None


# =============================================================================
# Table Bucket ARN Validation Tests
# =============================================================================

class TestValidateTableBucketArn:
    """Tests for validate_table_bucket_arn validator."""

    @pytest.mark.parametrize("arn", VALID_TABLE_BUCKET_ARNS)
    def test_valid_arns(self, arn):
        """Test that valid table bucket ARNs pass validation."""
        is_valid, error = validate_table_bucket_arn(arn)
        assert is_valid is True
        assert error is None

    @pytest.mark.parametrize("arn,expected_error_fragment", INVALID_TABLE_BUCKET_ARNS)
    def test_invalid_arns(self, arn, expected_error_fragment):
        """Test that invalid table bucket ARNs fail with appropriate error messages."""
        is_valid, error = validate_table_bucket_arn(arn)
        assert is_valid is False
        assert error is not None
        assert expected_error_fragment.lower() in error.lower()

    def test_arn_with_valid_gov_region(self):
        """Test that GovCloud regions are accepted."""
        arn = "arn:aws:s3tables:us-gov-west-1:123456789012:bucket/my-bucket"
        is_valid, error = validate_table_bucket_arn(arn)
        assert is_valid is True
        assert error is None

    def test_arn_with_long_bucket_name(self):
        """Test ARN with maximum-length bucket name (63 chars)."""
        bucket_name = "a" + "b" * 61 + "c"  # 63 chars
        arn = f"arn:aws:s3tables:us-east-1:123456789012:bucket/{bucket_name}"
        is_valid, error = validate_table_bucket_arn(arn)
        assert is_valid is True
        assert error is None


# =============================================================================
# IAM Role ARN Validation Tests
# =============================================================================

class TestValidateIamRoleArn:
    """Tests for validate_iam_role_arn validator."""

    @pytest.mark.parametrize("arn", VALID_IAM_ROLE_ARNS)
    def test_valid_arns(self, arn):
        """Test that valid IAM Role ARNs pass validation."""
        is_valid, error = validate_iam_role_arn(arn)
        assert is_valid is True
        assert error is None

    @pytest.mark.parametrize("arn,expected_error_fragment", INVALID_IAM_ROLE_ARNS)
    def test_invalid_arns(self, arn, expected_error_fragment):
        """Test that invalid IAM Role ARNs fail with appropriate error messages."""
        is_valid, error = validate_iam_role_arn(arn)
        assert is_valid is False
        assert error is not None
        assert expected_error_fragment.lower() in error.lower()

    def test_arn_with_nested_path(self):
        """Test that deeply nested role paths are accepted."""
        arn = "arn:aws:iam::123456789012:role/org/team/service/MyRole"
        is_valid, error = validate_iam_role_arn(arn)
        assert is_valid is True
        assert error is None

    def test_arn_with_special_chars_in_name(self):
        """Test that allowed special characters in role name are accepted."""
        arn = "arn:aws:iam::123456789012:role/My.Role+Name=Tag,Value@Domain"
        is_valid, error = validate_iam_role_arn(arn)
        assert is_valid is True
        assert error is None


# =============================================================================
# Parallelism Validation Tests
# =============================================================================

class TestValidateParallelism:
    """Tests for validate_parallelism validator."""

    @pytest.mark.parametrize("value", VALID_PARALLELISM_VALUES)
    def test_valid_parallelism(self, value):
        """Test that valid parallelism values pass validation."""
        is_valid, error = validate_parallelism(value)
        assert is_valid is True
        assert error is None

    @pytest.mark.parametrize("value,expected_error_fragment", INVALID_PARALLELISM_VALUES)
    def test_invalid_parallelism(self, value, expected_error_fragment):
        """Test that invalid parallelism values fail with appropriate error messages."""
        is_valid, error = validate_parallelism(value)
        assert is_valid is False
        assert error is not None
        assert expected_error_fragment.lower() in error.lower()

    def test_parallelism_boundary_min(self):
        """Test minimum boundary (1)."""
        is_valid, error = validate_parallelism(1)
        assert is_valid is True
        assert error is None

    def test_parallelism_boundary_max(self):
        """Test maximum boundary (16)."""
        is_valid, error = validate_parallelism(16)
        assert is_valid is True
        assert error is None

    def test_parallelism_non_integer_float(self):
        """Test that float values are rejected."""
        is_valid, error = validate_parallelism(4.5)
        assert is_valid is False
        assert "integer" in error.lower()

    def test_parallelism_non_integer_string(self):
        """Test that string values are rejected."""
        is_valid, error = validate_parallelism("4")
        assert is_valid is False
        assert "integer" in error.lower()


# =============================================================================
# Convenience Validator Tests
# =============================================================================

class TestValidateIcebergS3Config:
    """Tests for validate_iceberg_s3_config convenience validator."""

    def test_valid_config_without_role(self):
        """Test valid S3 config without IAM Role ARN."""
        is_valid, error = validate_iceberg_s3_config(
            s3_bucket="my-data-bucket",
            glue_database_name="analytics_db",
            parallelism=4,
        )
        assert is_valid is True
        assert error is None

    def test_valid_config_with_role(self):
        """Test valid S3 config with IAM Role ARN."""
        is_valid, error = validate_iceberg_s3_config(
            s3_bucket="my-data-bucket",
            glue_database_name="analytics_db",
            parallelism=8,
            aws_role_arn="arn:aws:iam::123456789012:role/DataMIQRole",
        )
        assert is_valid is True
        assert error is None

    def test_invalid_bucket_in_config(self):
        """Test that invalid bucket name fails the combined validator."""
        is_valid, error = validate_iceberg_s3_config(
            s3_bucket="INVALID_BUCKET",
            glue_database_name="analytics_db",
            parallelism=4,
        )
        assert is_valid is False
        assert "S3 bucket" in error

    def test_invalid_glue_db_in_config(self):
        """Test that invalid Glue DB name fails the combined validator."""
        is_valid, error = validate_iceberg_s3_config(
            s3_bucket="my-data-bucket",
            glue_database_name="INVALID-DB",
            parallelism=4,
        )
        assert is_valid is False
        assert "Glue database" in error

    def test_invalid_parallelism_in_config(self):
        """Test that invalid parallelism fails the combined validator."""
        is_valid, error = validate_iceberg_s3_config(
            s3_bucket="my-data-bucket",
            glue_database_name="analytics_db",
            parallelism=20,
        )
        assert is_valid is False
        assert "Parallelism" in error

    def test_invalid_role_arn_in_config(self):
        """Test that invalid IAM Role ARN fails the combined validator."""
        is_valid, error = validate_iceberg_s3_config(
            s3_bucket="my-data-bucket",
            glue_database_name="analytics_db",
            parallelism=4,
            aws_role_arn="not-a-valid-arn",
        )
        assert is_valid is False
        assert "IAM Role ARN" in error


class TestValidateIcebergS3TablesConfig:
    """Tests for validate_iceberg_s3_tables_config convenience validator."""

    def test_valid_config_without_role(self):
        """Test valid S3 Tables config without IAM Role ARN."""
        is_valid, error = validate_iceberg_s3_tables_config(
            table_bucket_arn="arn:aws:s3tables:us-east-1:123456789012:bucket/my-bucket",
            glue_database_name="analytics_db",
            parallelism=4,
        )
        assert is_valid is True
        assert error is None

    def test_valid_config_with_role(self):
        """Test valid S3 Tables config with IAM Role ARN."""
        is_valid, error = validate_iceberg_s3_tables_config(
            table_bucket_arn="arn:aws:s3tables:us-east-1:123456789012:bucket/my-bucket",
            glue_database_name="analytics_db",
            parallelism=8,
            aws_role_arn="arn:aws:iam::123456789012:role/DataMIQRole",
        )
        assert is_valid is True
        assert error is None

    def test_invalid_arn_in_config(self):
        """Test that invalid table bucket ARN fails the combined validator."""
        is_valid, error = validate_iceberg_s3_tables_config(
            table_bucket_arn="not-a-valid-arn",
            glue_database_name="analytics_db",
            parallelism=4,
        )
        assert is_valid is False
        assert "Table bucket ARN" in error

    def test_invalid_glue_db_in_config(self):
        """Test that invalid Glue DB name fails the combined validator."""
        is_valid, error = validate_iceberg_s3_tables_config(
            table_bucket_arn="arn:aws:s3tables:us-east-1:123456789012:bucket/my-bucket",
            glue_database_name="INVALID",
            parallelism=4,
        )
        assert is_valid is False
        assert "Glue database" in error


# =============================================================================
# Maintenance Config Validation Tests
# =============================================================================

# --- Maintenance Config Samples ---

VALID_MAINTENANCE_CONFIGS = [
    (64, 1, 1),          # minimum valid values
    (512, 30, 720),      # default values
    (256, 10, 168),      # mid-range values
    (64, 100, 8760),     # min file size, large retention
    (512, 1, 1),         # max file size, min retention
    (128, 50, 360),      # typical production config
]

INVALID_MAINTENANCE_CONFIGS = [
    # (target_file_size_mb, min_snapshots, max_age, expected_error_fragment)
    (63, 30, 720, "between 64 MB and 512 MB"),       # below min file size
    (513, 30, 720, "between 64 MB and 512 MB"),      # above max file size
    (0, 30, 720, "required"),                         # zero file size
    (-1, 30, 720, "between 64 MB and 512 MB"),       # negative file size
    (1000, 30, 720, "between 64 MB and 512 MB"),     # way above max
    (256, 0, 720, "positive integer"),                # zero snapshots
    (256, -1, 720, "positive integer"),               # negative snapshots
    (256, 30, 0, "positive integer"),                 # zero age
    (256, 30, -1, "positive integer"),                # negative age
]


class TestValidateMaintenanceConfig:
    """Tests for validate_maintenance_config validator."""

    @pytest.mark.parametrize(
        "target_file_size_mb,min_snapshots,max_age",
        VALID_MAINTENANCE_CONFIGS,
    )
    def test_valid_configs(self, target_file_size_mb, min_snapshots, max_age):
        """Test that valid maintenance configurations pass validation."""
        is_valid, error = validate_maintenance_config(
            target_file_size_mb, min_snapshots, max_age
        )
        assert is_valid is True
        assert error is None

    @pytest.mark.parametrize(
        "target_file_size_mb,min_snapshots,max_age,expected_error_fragment",
        INVALID_MAINTENANCE_CONFIGS,
    )
    def test_invalid_configs(
        self, target_file_size_mb, min_snapshots, max_age, expected_error_fragment
    ):
        """Test that invalid maintenance configurations fail with appropriate errors."""
        is_valid, error = validate_maintenance_config(
            target_file_size_mb, min_snapshots, max_age
        )
        assert is_valid is False
        assert error is not None
        assert expected_error_fragment.lower() in error.lower()

    def test_boundary_min_file_size(self):
        """Test minimum boundary for target file size (64 MB)."""
        is_valid, error = validate_maintenance_config(64, 30, 720)
        assert is_valid is True
        assert error is None

    def test_boundary_max_file_size(self):
        """Test maximum boundary for target file size (512 MB)."""
        is_valid, error = validate_maintenance_config(512, 30, 720)
        assert is_valid is True
        assert error is None

    def test_boundary_just_below_min_file_size(self):
        """Test value just below minimum file size (63 MB)."""
        is_valid, error = validate_maintenance_config(63, 30, 720)
        assert is_valid is False
        assert "64 MB" in error

    def test_boundary_just_above_max_file_size(self):
        """Test value just above maximum file size (513 MB)."""
        is_valid, error = validate_maintenance_config(513, 30, 720)
        assert is_valid is False
        assert "512 MB" in error

    def test_min_snapshots_boundary_one(self):
        """Test minimum valid snapshots to keep (1)."""
        is_valid, error = validate_maintenance_config(256, 1, 720)
        assert is_valid is True
        assert error is None

    def test_min_snapshots_boundary_zero(self):
        """Test zero snapshots to keep is rejected."""
        is_valid, error = validate_maintenance_config(256, 0, 720)
        assert is_valid is False
        assert "positive integer" in error.lower()

    def test_max_age_boundary_one(self):
        """Test minimum valid max snapshot age (1 hour)."""
        is_valid, error = validate_maintenance_config(256, 30, 1)
        assert is_valid is True
        assert error is None

    def test_max_age_boundary_zero(self):
        """Test zero max snapshot age is rejected."""
        is_valid, error = validate_maintenance_config(256, 30, 0)
        assert is_valid is False
        assert "positive integer" in error.lower()

    def test_non_integer_file_size(self):
        """Test that non-integer file size is rejected."""
        is_valid, error = validate_maintenance_config(256.5, 30, 720)
        assert is_valid is False
        assert "integer" in error.lower()

    def test_non_integer_snapshots(self):
        """Test that non-integer snapshots value is rejected."""
        is_valid, error = validate_maintenance_config(256, 30.5, 720)
        assert is_valid is False
        assert "integer" in error.lower()

    def test_non_integer_age(self):
        """Test that non-integer age value is rejected."""
        is_valid, error = validate_maintenance_config(256, 30, 720.5)
        assert is_valid is False
        assert "integer" in error.lower()

    def test_boolean_file_size_rejected(self):
        """Test that boolean values are rejected for file size."""
        is_valid, error = validate_maintenance_config(True, 30, 720)
        assert is_valid is False
        assert "integer" in error.lower()

    def test_default_values_valid(self):
        """Test that the documented default values (512, 30, 720) are valid."""
        is_valid, error = validate_maintenance_config(512, 30, 720)
        assert is_valid is True
        assert error is None
