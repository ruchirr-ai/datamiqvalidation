"""
DataSync Client Factory

Creates boto3 DataSync clients using STS AssumeRole for proper IAM role-based access.
Falls back to default credentials if no role ARN is configured.
"""

import os
import logging
from typing import Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Cache assumed-role credentials to avoid excessive STS calls
_cached_credentials: Optional[dict] = None
_cached_expiration = None


def create_datasync_client(
    region: Optional[str] = None,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    role_arn: Optional[str] = None,
):
    """
    Create a boto3 DataSync client, assuming an IAM role if configured.

    Role ARN resolution order:
      1. Explicit role_arn parameter (e.g. per-migration DataSync S3 role)
      2. DATASYNC_ROLE_ARN environment variable
      3. No role — use explicit or default credentials directly

    When a role ARN is provided, uses STS AssumeRole with the base credentials
    to get temporary credentials, then creates the DataSync client with those.

    Args:
        region: AWS region for DataSync. Defaults to AWS_DATASYNC_REGION or us-east-1.
        aws_access_key_id: Explicit access key (used as base credentials for STS call).
        aws_secret_access_key: Explicit secret key (used as base credentials for STS call).
        role_arn: IAM role ARN to assume for DataSync API calls.

    Returns:
        boto3 DataSync client
    """
    region = region or os.getenv('AWS_DATASYNC_REGION', os.getenv('AWS_REGION', 'us-east-1'))
    effective_role_arn = (role_arn or '').strip() or os.getenv('DATASYNC_ROLE_ARN', '').strip()

    if effective_role_arn:
        return _create_client_with_role(effective_role_arn, region, aws_access_key_id, aws_secret_access_key)

    # No role configured — use explicit or default credentials
    boto_kwargs = {"region_name": region}
    if aws_access_key_id and aws_secret_access_key:
        boto_kwargs["aws_access_key_id"] = aws_access_key_id
        boto_kwargs["aws_secret_access_key"] = aws_secret_access_key

    logger.info("Creating DataSync client with default credentials (no DATASYNC_ROLE_ARN set)")
    return boto3.client("datasync", **boto_kwargs)


def _create_client_with_role(
    role_arn: str,
    region: str,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
):
    """
    Assume the DataSync IAM role via STS and create a DataSync client
    with the temporary credentials.
    """
    try:
        # Build STS client with base credentials
        sts_kwargs = {"region_name": region}
        if aws_access_key_id and aws_secret_access_key:
            sts_kwargs["aws_access_key_id"] = aws_access_key_id
            sts_kwargs["aws_secret_access_key"] = aws_secret_access_key
            logger.info(
                f"STS AssumeRole will use explicit credentials "
                f"(key starts with: {aws_access_key_id[:8]}...)"
            )
        else:
            logger.info(
                "STS AssumeRole will use default/env credentials "
                "(no explicit key passed to create_datasync_client)"
            )

        sts_client = boto3.client("sts", **sts_kwargs)

        logger.info(f"Assuming DataSync role: {role_arn}")
        response = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName="datamiq-datasync",
            DurationSeconds=3600,
        )

        credentials = response["Credentials"]
        logger.info("Successfully assumed DataSync role")

        return boto3.client(
            "datasync",
            region_name=region,
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
        )

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "AccessDenied":
            logger.error(
                f"Failed to assume DataSync role {role_arn}: {e}\n"
                f"FIX REQUIRED — two things must be configured in AWS:\n"
                f"  1. The IAM user/role making this call needs an IAM policy with:\n"
                f"     {{'Effect': 'Allow', 'Action': 'sts:AssumeRole', 'Resource': '{role_arn}'}}\n"
                f"  2. The target role's Trust Policy must include the calling principal.\n"
                f"     Go to IAM → Roles → {role_arn.split('/')[-1]} → Trust relationships → Edit,\n"
                f"     and add the calling IAM user/role ARN as a trusted principal."
            )
        else:
            logger.error(f"Failed to assume DataSync role {role_arn}: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error assuming DataSync role: {e}")
        raise
