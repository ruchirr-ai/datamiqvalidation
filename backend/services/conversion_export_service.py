"""
Export Service

Handles .sql file generation and S3 upload for conversion results.
Supports single job export, batch export (combined .sql), and S3 export
with files organized by asset_type subdirectories.
"""

import io
import logging
from typing import Optional

import boto3

from models.conversion_job import ConversionJob

logger = logging.getLogger(__name__)


class ExportService:
    """Generates .sql files and exports conversion results to S3."""

    def generate_single_sql(self, job: ConversionJob) -> tuple[bytes, str]:
        """Generate a downloadable .sql file for a single conversion job.

        Args:
            job: A completed ConversionJob with target_code.

        Returns:
            Tuple of (file_bytes, filename).

        Raises:
            ValueError: If the job has no target_code.
        """
        if not job.target_code:
            raise ValueError(f"Job {job.id} has no converted code to export")

        asset_name = job.asset_name or f"job_{job.id}"
        filename = f"{asset_name}_{job.target_dialect}.sql"
        content = job.target_code.encode("utf-8")

        logger.info(
            "Generated single .sql export",
            extra={"job_id": job.id, "filename": filename},
        )
        return content, filename

    def generate_batch_sql(self, jobs: list[ConversionJob]) -> bytes:
        """Combine all successfully converted jobs into a single .sql file.

        Each asset is separated by a comment header identifying the asset
        name and type. Jobs without target_code are skipped.

        Args:
            jobs: List of ConversionJob instances from a batch.

        Returns:
            Combined .sql content as bytes.
        """
        buf = io.StringIO()
        included = 0

        for job in jobs:
            if not job.target_code:
                continue

            asset_name = job.asset_name or f"job_{job.id}"
            if included > 0:
                buf.write("\n\n")
            buf.write(f"-- Asset: {asset_name} ({job.asset_type})\n")
            buf.write(job.target_code)
            included += 1

        logger.info(
            "Generated batch .sql export",
            extra={"included_assets": included, "total_jobs": len(jobs)},
        )
        return buf.getvalue().encode("utf-8")

    def export_to_s3(
        self,
        jobs: list[ConversionJob],
        s3_path: str,
        region: str,
    ) -> None:
        """Write individual .sql files to S3 organized by asset_type.

        Files are stored as: {s3_path}/{asset_type}/{asset_name}.sql
        Jobs without target_code are skipped.

        Args:
            jobs: List of ConversionJob instances to export.
            s3_path: S3 destination in the form s3://bucket/prefix.
            region: AWS region for the S3 client.

        Raises:
            ValueError: If s3_path format is invalid.
        """
        bucket, prefix = self._parse_s3_path(s3_path)
        s3_client = boto3.client("s3", region_name=region)
        exported = 0

        for job in jobs:
            if not job.target_code:
                continue

            asset_name = job.asset_name or f"job_{job.id}"
            key = f"{prefix}/{job.asset_type}/{asset_name}.sql" if prefix else f"{job.asset_type}/{asset_name}.sql"

            s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=job.target_code.encode("utf-8"),
                ContentType="application/sql",
            )
            exported += 1

        logger.info(
            "Exported batch to S3",
            extra={
                "bucket": bucket,
                "prefix": prefix,
                "exported_assets": exported,
                "total_jobs": len(jobs),
            },
        )

    @staticmethod
    def _parse_s3_path(s3_path: str) -> tuple[str, str]:
        """Parse an s3://bucket/prefix path into (bucket, prefix).

        Raises:
            ValueError: If the path does not start with s3://.
        """
        if not s3_path.startswith("s3://"):
            raise ValueError(f"Invalid S3 path: {s3_path}. Must start with s3://")

        path = s3_path[5:]  # strip "s3://"
        parts = path.split("/", 1)
        bucket = parts[0]
        prefix = parts[1].rstrip("/") if len(parts) > 1 else ""
        return bucket, prefix
