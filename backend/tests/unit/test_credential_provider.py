"""
Unit tests for AWSCredentialProvider

Tests credential management for Iceberg migrations, including:
- IAM Role ARN path (STS AssumeRole)
- Access key path (KMS decryption)
- Error handling for missing parameters
- Graceful handling of failures
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from services.bq_iceberg_migration.credential_provider import (
    AWSCredentialProvider,
    SESSION_NAME,
)


# --- Fixtures ---

@pytest.fixture
def mock_kms_service():
    """Mock KMS service that decrypts by returning a known plaintext."""
    kms = MagicMock()
    kms.decrypt_credential.return_value = "decrypted-secret-key-value"
    return kms


@pytest.fixture
def mock_sts_client():
    """Mock STS client that returns temporary credentials on assume_role."""
    sts = MagicMock()
    sts.assume_role.return_value = {
        "Credentials": {
            "AccessKeyId": "ASIA_TEMP_KEY_ID",
            "SecretAccessKey": "temp-secret-key",
            "SessionToken": "temp-session-token",
            "Expiration": datetime.utcnow() + timedelta(hours=1),
        }
    }
    return sts


@pytest.fixture
def provider(mock_kms_service, mock_sts_client):
    """AWSCredentialProvider with mocked dependencies."""
    return AWSCredentialProvider(
        kms_service=mock_kms_service,
        sts_client=mock_sts_client,
    )


# --- Sample Payloads ---

VALID_ROLE_ARN_PARAMS = {
    "aws_role_arn": "arn:aws:iam::123456789012:role/DataMiqIcebergRole",
    "aws_region": "us-east-1",
}

VALID_ACCESS_KEY_PARAMS = {
    "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "aws_secret_access_key": "encrypted-base64-secret-key",
    "aws_region": "us-west-2",
}

PARAMS_MISSING_REGION = {
    "aws_role_arn": "arn:aws:iam::123456789012:role/SomeRole",
}

PARAMS_MISSING_CREDENTIALS = {
    "aws_region": "eu-west-1",
}

PARAMS_MISSING_SECRET_KEY = {
    "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "aws_region": "us-east-1",
}


# --- Tests: IAM Role ARN Path ---

class TestGetSessionWithRoleARN:
    """Test get_session() when aws_role_arn is provided."""

    def test_get_session_role_arn_calls_assume_role(self, provider, mock_sts_client):
        """Test that get_session with role ARN calls STS AssumeRole."""
        with patch("services.bq_iceberg_migration.credential_provider.boto3") as mock_boto3:
            mock_boto3.Session.return_value = MagicMock()
            provider.get_session(VALID_ROLE_ARN_PARAMS)

            mock_sts_client.assume_role.assert_called_once_with(
                RoleArn=VALID_ROLE_ARN_PARAMS["aws_role_arn"],
                RoleSessionName=SESSION_NAME,
            )

    def test_get_session_role_arn_creates_session_with_temp_creds(
        self, provider, mock_sts_client
    ):
        """Test that the returned session uses temporary credentials."""
        with patch("services.bq_iceberg_migration.credential_provider.boto3") as mock_boto3:
            mock_session = MagicMock()
            mock_boto3.Session.return_value = mock_session

            result = provider.get_session(VALID_ROLE_ARN_PARAMS)

            mock_boto3.Session.assert_called_once_with(
                aws_access_key_id="ASIA_TEMP_KEY_ID",
                aws_secret_access_key="temp-secret-key",
                aws_session_token="temp-session-token",
                region_name="us-east-1",
            )
            assert result == mock_session

    def test_get_session_role_arn_does_not_call_kms(
        self, provider, mock_kms_service
    ):
        """Test that KMS decryption is NOT called when using role ARN."""
        with patch("services.bq_iceberg_migration.credential_provider.boto3") as mock_boto3:
            mock_boto3.Session.return_value = MagicMock()
            provider.get_session(VALID_ROLE_ARN_PARAMS)

            mock_kms_service.decrypt_credential.assert_not_called()

    def test_get_session_role_arn_assume_role_failure(
        self, provider, mock_sts_client
    ):
        """Test that AssumeRole failure raises ValueError."""
        mock_sts_client.assume_role.side_effect = Exception(
            "AccessDenied: Not authorized to perform sts:AssumeRole"
        )

        with pytest.raises(ValueError, match="Failed to assume IAM role"):
            provider.get_session(VALID_ROLE_ARN_PARAMS)


# --- Tests: Access Key Path ---

class TestGetSessionWithAccessKeys:
    """Test get_session() when access keys are provided."""

    def test_get_session_access_keys_decrypts_secret(
        self, provider, mock_kms_service
    ):
        """Test that get_session decrypts the secret access key via KMS."""
        with patch("services.bq_iceberg_migration.credential_provider.boto3") as mock_boto3:
            mock_boto3.Session.return_value = MagicMock()
            provider.get_session(VALID_ACCESS_KEY_PARAMS)

            mock_kms_service.decrypt_credential.assert_called_once_with(
                ciphertext="encrypted-base64-secret-key",
                credential_type="aws_secret_key",
                resource_type="iceberg_migration",
                allow_plaintext_fallback=True,
            )

    def test_get_session_access_keys_creates_session(
        self, provider, mock_kms_service
    ):
        """Test that the session is created with decrypted credentials."""
        with patch("services.bq_iceberg_migration.credential_provider.boto3") as mock_boto3:
            mock_session = MagicMock()
            mock_boto3.Session.return_value = mock_session

            result = provider.get_session(VALID_ACCESS_KEY_PARAMS)

            mock_boto3.Session.assert_called_once_with(
                aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
                aws_secret_access_key="decrypted-secret-key-value",
                region_name="us-west-2",
            )
            assert result == mock_session

    def test_get_session_access_keys_does_not_call_sts(
        self, provider, mock_sts_client
    ):
        """Test that STS AssumeRole is NOT called when using access keys."""
        with patch("services.bq_iceberg_migration.credential_provider.boto3") as mock_boto3:
            mock_boto3.Session.return_value = MagicMock()
            provider.get_session(VALID_ACCESS_KEY_PARAMS)

            mock_sts_client.assume_role.assert_not_called()

    def test_get_session_access_keys_kms_failure(
        self, provider, mock_kms_service
    ):
        """Test that KMS decryption failure raises ValueError."""
        mock_kms_service.decrypt_credential.side_effect = ValueError(
            "KMS decryption failed: Access denied"
        )

        with pytest.raises(ValueError, match="Failed to decrypt AWS secret access key"):
            provider.get_session(VALID_ACCESS_KEY_PARAMS)


# --- Tests: Validation and Error Handling ---

class TestGetSessionValidation:
    """Test input validation in get_session()."""

    def test_get_session_missing_region_raises_error(self, provider):
        """Test that missing aws_region raises ValueError."""
        with pytest.raises(ValueError, match="aws_region is required"):
            provider.get_session(PARAMS_MISSING_REGION)

    def test_get_session_missing_credentials_raises_error(self, provider):
        """Test that missing both role ARN and access key raises ValueError."""
        with pytest.raises(
            ValueError,
            match="Either aws_role_arn or aws_access_key_id must be provided",
        ):
            provider.get_session(PARAMS_MISSING_CREDENTIALS)

    def test_get_session_missing_secret_key_raises_error(self, provider):
        """Test that access key without secret key raises ValueError."""
        with pytest.raises(
            ValueError,
            match="aws_secret_access_key is required",
        ):
            provider.get_session(PARAMS_MISSING_SECRET_KEY)

    def test_get_session_empty_params_raises_error(self, provider):
        """Test that empty params dict raises ValueError."""
        with pytest.raises(ValueError, match="aws_region is required"):
            provider.get_session({})

    def test_get_session_role_arn_takes_priority_over_access_keys(
        self, provider, mock_sts_client, mock_kms_service
    ):
        """Test that role ARN is preferred when both are provided."""
        params = {
            "aws_role_arn": "arn:aws:iam::123456789012:role/MyRole",
            "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "aws_secret_access_key": "encrypted-secret",
            "aws_region": "us-east-1",
        }

        with patch("services.bq_iceberg_migration.credential_provider.boto3") as mock_boto3:
            mock_boto3.Session.return_value = MagicMock()
            provider.get_session(params)

            # Should use role ARN path
            mock_sts_client.assume_role.assert_called_once()
            # Should NOT decrypt access keys
            mock_kms_service.decrypt_credential.assert_not_called()


# --- Tests: _assume_role ---

class TestAssumeRole:
    """Test the _assume_role private method."""

    def test_assume_role_uses_correct_session_name(
        self, provider, mock_sts_client
    ):
        """Test that _assume_role uses 'datamiq-iceberg-migration' session name."""
        with patch("services.bq_iceberg_migration.credential_provider.boto3") as mock_boto3:
            mock_boto3.Session.return_value = MagicMock()
            provider._assume_role(
                role_arn="arn:aws:iam::123456789012:role/TestRole",
                region="eu-west-1",
            )

            mock_sts_client.assume_role.assert_called_once_with(
                RoleArn="arn:aws:iam::123456789012:role/TestRole",
                RoleSessionName="datamiq-iceberg-migration",
            )

    def test_assume_role_passes_region_to_session(
        self, provider, mock_sts_client
    ):
        """Test that _assume_role passes the region to the boto3 Session."""
        with patch("services.bq_iceberg_migration.credential_provider.boto3") as mock_boto3:
            mock_boto3.Session.return_value = MagicMock()
            provider._assume_role(
                role_arn="arn:aws:iam::123456789012:role/TestRole",
                region="ap-southeast-1",
            )

            mock_boto3.Session.assert_called_once_with(
                aws_access_key_id="ASIA_TEMP_KEY_ID",
                aws_secret_access_key="temp-secret-key",
                aws_session_token="temp-session-token",
                region_name="ap-southeast-1",
            )

    def test_assume_role_failure_raises_value_error(
        self, provider, mock_sts_client
    ):
        """Test that STS failure in _assume_role raises ValueError."""
        mock_sts_client.assume_role.side_effect = Exception("Throttling")

        with pytest.raises(ValueError, match="Failed to assume IAM role"):
            provider._assume_role(
                role_arn="arn:aws:iam::123456789012:role/TestRole",
                region="us-east-1",
            )


# --- Tests: Session Name Constant ---

class TestSessionNameConstant:
    """Test the SESSION_NAME module constant."""

    def test_session_name_value(self):
        """Test that SESSION_NAME is 'datamiq-iceberg-migration'."""
        assert SESSION_NAME == "datamiq-iceberg-migration"
