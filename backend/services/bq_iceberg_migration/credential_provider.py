"""
AWS Credential Provider for BigQuery to Iceberg Migration

Provides AWS credentials via IAM Role (STS AssumeRole) or direct access keys
(decrypted via KMS). Used by the Iceberg Loader, S3 Tables Adapter, and Athena
Verifier to authenticate with AWS services.

Supports:
- IAM Role ARN: Assumes the specified role via STS AssumeRole
- Access Keys: Decrypts the secret access key via the unified KMS service

Usage:
    from services.unified_kms_service import get_unified_kms_service
    from services.bq_iceberg_migration.credential_provider import AWSCredentialProvider

    kms = get_unified_kms_service()
    sts_client = boto3.client('sts', region_name='us-east-1')
    provider = AWSCredentialProvider(kms_service=kms, sts_client=sts_client)

    session = provider.get_session(connection_params={
        "aws_role_arn": "arn:aws:iam::123456789012:role/MyRole",
        "aws_region": "us-east-1"
    })
"""

import logging
from typing import Any, Dict

try:
    import boto3
except ImportError:
    boto3 = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Session name used when assuming IAM roles for Iceberg migrations
SESSION_NAME = "datamiq-iceberg-migration"


class AWSCredentialProvider:
    """Provides AWS credentials via IAM Role (STS AssumeRole) or direct access keys.

    This class abstracts credential management for the Iceberg migration service,
    supporting both IAM Role-based access (preferred) and direct access key
    credentials (decrypted via KMS).

    Args:
        kms_service: Instance of UnifiedKMSService for decrypting secret keys.
        sts_client: A boto3 STS client used for AssumeRole operations.
    """

    def __init__(self, kms_service: Any, sts_client: Any) -> None:
        self._kms = kms_service
        self._sts = sts_client

    def get_session(self, connection_params: Dict[str, Any]) -> "boto3.Session":
        """Return a boto3 Session using either IAM Role or access keys.

        If ``aws_role_arn`` is provided in connection_params, uses STS AssumeRole
        to obtain temporary credentials. Otherwise, decrypts the secret access key
        via KMS and creates a session with static credentials.

        Args:
            connection_params: Dictionary containing connection configuration.
                Required keys depend on auth method:
                - IAM Role path: ``aws_role_arn``, ``aws_region``
                - Access key path: ``aws_access_key_id``,
                  ``aws_secret_access_key`` (encrypted), ``aws_region``

        Returns:
            A configured boto3.Session ready for AWS API calls.

        Raises:
            ValueError: If required parameters are missing or decryption fails.
            RuntimeError: If boto3 is not installed.
        """
        if boto3 is None:
            raise RuntimeError(
                "boto3 is required for AWS credential management. "
                "Install it with: uv pip install boto3"
            )

        aws_region = connection_params.get("aws_region")
        if not aws_region:
            raise ValueError("aws_region is required in connection_params")

        # IAM Role ARN path (preferred)
        role_arn = connection_params.get("aws_role_arn")
        if role_arn:
            logger.info(
                "Using IAM Role ARN for AWS session (role: %s, region: %s)",
                role_arn,
                aws_region,
            )
            return self._assume_role(role_arn=role_arn, region=aws_region)

        # Access key path
        access_key_id = connection_params.get("aws_access_key_id")
        secret_access_key_encrypted = connection_params.get("aws_secret_access_key")

        if not access_key_id:
            raise ValueError(
                "Either aws_role_arn or aws_access_key_id must be provided "
                "in connection_params"
            )
        if not secret_access_key_encrypted:
            raise ValueError(
                "aws_secret_access_key is required when using access key credentials"
            )

        # Decrypt the secret access key via KMS
        logger.info("Decrypting AWS secret access key via KMS")
        try:
            secret_access_key = self._kms.decrypt_credential(
                ciphertext=secret_access_key_encrypted,
                credential_type="aws_secret_key",
                resource_type="iceberg_migration",
                allow_plaintext_fallback=True,
            )
        except Exception as e:
            logger.error("Failed to decrypt AWS secret access key: %s", e)
            raise ValueError(f"Failed to decrypt AWS secret access key: {e}") from e

        logger.info(
            "Creating AWS session with access key credentials (region: %s)",
            aws_region,
        )
        return boto3.Session(
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=aws_region,
        )

    def _assume_role(self, role_arn: str, region: str) -> "boto3.Session":
        """Assume an IAM role and return a session with temporary credentials.

        Uses STS AssumeRole with session name 'datamiq-iceberg-migration' to
        obtain temporary credentials scoped to the specified role.

        Args:
            role_arn: The ARN of the IAM role to assume.
            region: The AWS region for the resulting session.

        Returns:
            A boto3.Session configured with the temporary credentials.

        Raises:
            ValueError: If the AssumeRole call fails.
        """
        if boto3 is None:
            raise RuntimeError(
                "boto3 is required for AWS credential management. "
                "Install it with: uv pip install boto3"
            )

        try:
            logger.debug(
                "Assuming IAM role: %s (session: %s, region: %s)",
                role_arn,
                SESSION_NAME,
                region,
            )
            response = self._sts.assume_role(
                RoleArn=role_arn,
                RoleSessionName=SESSION_NAME,
            )
        except Exception as e:
            logger.error("Failed to assume IAM role %s: %s", role_arn, e)
            raise ValueError(
                f"Failed to assume IAM role '{role_arn}': {e}"
            ) from e

        credentials = response["Credentials"]

        logger.info(
            "Successfully assumed IAM role %s (expires: %s)",
            role_arn,
            credentials.get("Expiration", "unknown"),
        )

        return boto3.Session(
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
            region_name=region,
        )
