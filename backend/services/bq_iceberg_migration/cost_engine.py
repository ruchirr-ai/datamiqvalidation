"""
Cost Analysis Engine

Calculates and projects costs for Iceberg migration setup and operations.
Provides one-time setup costs, recurring monthly costs, and projections
at 3/6/12 month horizons with configurable growth rates. Includes TCO
comparison between BigQuery and Iceberg when current BQ costs are available.

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class CostReport:
    """Complete cost analysis report for an Iceberg migration.

    Attributes:
        generated_at: ISO timestamp when the report was generated.
        data_size_gb: Raw data size in GB from assessment.
        compressed_size_gb_optimistic: Estimated compressed size (5:1 ratio).
        compressed_size_gb_conservative: Estimated compressed size (3:1 ratio).
        setup_costs: One-time setup cost breakdown.
        recurring_monthly: Monthly recurring cost breakdown.
        projections: Cost projections at 3/6/12 month horizons.
        tco_comparison: TCO comparison vs BigQuery (if BQ costs available).
        growth_rate_monthly: Monthly data growth rate used for projections.
        destination_type: The Iceberg destination type.
    """

    generated_at: str
    data_size_gb: float
    compressed_size_gb_optimistic: float
    compressed_size_gb_conservative: float
    setup_costs: dict[str, float]
    recurring_monthly: dict[str, float]
    projections: dict[str, float]
    tco_comparison: Optional[dict[str, float]] = None
    growth_rate_monthly: float = 0.05
    destination_type: str = "iceberg_s3"

    def to_dict(self) -> dict:
        """Serialize the cost report to a JSON-compatible dict."""
        return {
            "generated_at": self.generated_at,
            "data_size_gb": round(self.data_size_gb, 2),
            "compressed_size_gb_optimistic": round(
                self.compressed_size_gb_optimistic, 2
            ),
            "compressed_size_gb_conservative": round(
                self.compressed_size_gb_conservative, 2
            ),
            "setup_costs": {
                k: round(v, 2) for k, v in self.setup_costs.items()
            },
            "recurring_monthly": {
                k: round(v, 2) for k, v in self.recurring_monthly.items()
            },
            "projections": {
                k: round(v, 2) for k, v in self.projections.items()
            },
            "tco_comparison": (
                {k: round(v, 2) for k, v in self.tco_comparison.items()}
                if self.tco_comparison
                else None
            ),
            "growth_rate_monthly": self.growth_rate_monthly,
            "destination_type": self.destination_type,
        }


class CostAnalysisEngine:
    """Calculates and projects costs for Iceberg migration setup and operations.

    Uses AWS pricing constants (configurable per region) to estimate one-time
    setup costs, recurring monthly costs, and projected costs at 3/6/12 month
    horizons. Supports both standard S3 Iceberg and S3 Tables pricing.

    Attributes:
        S3_STORAGE_PER_GB_MONTH: Standard S3 storage cost per GB per month.
        S3_PUT_REQUEST_PER_1000: Cost per 1000 PUT requests.
        GLUE_CATALOG_PER_MILLION_REQUESTS: Glue catalog request cost.
        GLUE_STORAGE_PER_100K_OBJECTS_MONTH: Glue storage cost.
        ATHENA_PER_TB_SCANNED: Athena query cost per TB scanned.
        S3_TABLES_STORAGE_PER_GB_MONTH: S3 Tables storage premium.
        DATA_TRANSFER_PER_GB: Data transfer cost per GB (cross-region).
        ZSTD_COMPRESSION_RATIO_OPTIMISTIC: Best-case compression ratio.
        ZSTD_COMPRESSION_RATIO_CONSERVATIVE: Worst-case compression ratio.

    Usage:
        engine = CostAnalysisEngine()
        report = engine.calculate(
            assessment_data={"total_size_bytes": 240 * 1024**3, "table_count": 10},
            destination_type="iceberg_s3",
            aws_region="us-east-1",
            growth_rate_monthly=0.05,
            bq_current_costs={"monthly_cost": 45.00},
        )
    """

    # AWS pricing constants (US East 1 defaults)
    S3_STORAGE_PER_GB_MONTH: float = 0.023
    S3_PUT_REQUEST_PER_1000: float = 0.005
    GLUE_CATALOG_PER_MILLION_REQUESTS: float = 1.00
    GLUE_STORAGE_PER_100K_OBJECTS_MONTH: float = 1.00
    ATHENA_PER_TB_SCANNED: float = 5.00
    S3_TABLES_STORAGE_PER_GB_MONTH: float = 0.028
    DATA_TRANSFER_PER_GB: float = 0.09
    ZSTD_COMPRESSION_RATIO_OPTIMISTIC: float = 5.0
    ZSTD_COMPRESSION_RATIO_CONSERVATIVE: float = 3.0

    # Estimated Glue API calls per table during setup
    GLUE_API_CALLS_PER_TABLE: int = 5
    # Estimated Athena queries per table per month (for verification)
    ATHENA_QUERIES_PER_TABLE_MONTH: int = 2
    # Average data scanned per Athena query (fraction of table size)
    ATHENA_SCAN_FRACTION: float = 0.1

    def calculate(
        self,
        assessment_data: dict,
        destination_type: str,
        aws_region: str,
        growth_rate_monthly: float = 0.05,
        bq_current_costs: Optional[dict] = None,
    ) -> CostReport:
        """Generate full cost analysis report.

        Calculates one-time setup costs, recurring monthly costs, and
        projects costs at 3/6/12 month horizons based on estimated data
        growth.

        Args:
            assessment_data: Dict containing:
                - total_size_bytes: Total raw data size in bytes.
                - table_count: Number of tables to migrate.
            destination_type: Either 'iceberg_s3' or 'iceberg_s3_tables'.
            aws_region: AWS region for pricing context.
            growth_rate_monthly: Monthly data growth rate (default 5%).
            bq_current_costs: Optional dict with BigQuery cost data:
                - monthly_cost: Current monthly BQ cost.

        Returns:
            A CostReport with complete cost analysis.
        """
        total_size_bytes = assessment_data.get("total_size_bytes", 0)
        table_count = assessment_data.get("table_count", 0)

        data_size_gb = total_size_bytes / (1024**3)
        compressed_optimistic = data_size_gb / self.ZSTD_COMPRESSION_RATIO_OPTIMISTIC
        compressed_conservative = (
            data_size_gb / self.ZSTD_COMPRESSION_RATIO_CONSERVATIVE
        )

        setup_costs = self._calculate_setup_costs(
            total_size_bytes, table_count, destination_type
        )
        recurring_costs = self._calculate_recurring_costs(
            total_size_bytes, table_count, destination_type
        )
        projections = self._project_costs(
            recurring_costs["total_monthly_conservative"],
            growth_rate_monthly,
        )

        tco_comparison = None
        if bq_current_costs and "monthly_cost" in bq_current_costs:
            tco_comparison = self._calculate_tco_comparison(
                bq_current_costs, recurring_costs
            )

        report = CostReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            data_size_gb=data_size_gb,
            compressed_size_gb_optimistic=compressed_optimistic,
            compressed_size_gb_conservative=compressed_conservative,
            setup_costs=setup_costs,
            recurring_monthly=recurring_costs,
            projections={
                "growth_rate_monthly": growth_rate_monthly,
                **projections,
            },
            tco_comparison=tco_comparison,
            growth_rate_monthly=growth_rate_monthly,
            destination_type=destination_type,
        )

        logger.info(
            "Generated cost analysis: data_size=%.1f GB, "
            "setup_total=%.2f, monthly_conservative=%.2f",
            data_size_gb,
            setup_costs["total_setup"],
            recurring_costs["total_monthly_conservative"],
        )

        return report

    def _calculate_setup_costs(
        self,
        data_size_bytes: int,
        table_count: int,
        destination_type: str,
    ) -> dict[str, float]:
        """Calculate one-time setup costs.

        Includes initial S3 storage provisioning, Glue API calls for
        table creation, and data transfer costs.

        Args:
            data_size_bytes: Total raw data size in bytes.
            table_count: Number of tables to create.
            destination_type: Iceberg destination type.

        Returns:
            Dict with itemized setup costs and total.
        """
        data_size_gb = data_size_bytes / (1024**3)

        # Initial storage cost (first month of compressed data)
        compressed_gb = data_size_gb / self.ZSTD_COMPRESSION_RATIO_CONSERVATIVE
        if destination_type == "iceberg_s3_tables":
            s3_initial_storage = (
                compressed_gb * self.S3_TABLES_STORAGE_PER_GB_MONTH
            )
        else:
            s3_initial_storage = (
                compressed_gb * self.S3_STORAGE_PER_GB_MONTH
            )

        # Glue API calls for table creation
        glue_api_calls = table_count * self.GLUE_API_CALLS_PER_TABLE
        glue_cost = (glue_api_calls / 1_000_000) * self.GLUE_CATALOG_PER_MILLION_REQUESTS

        # Data transfer cost (GCS → S3)
        data_transfer = data_size_gb * self.DATA_TRANSFER_PER_GB

        # S3 PUT requests for data files (estimate ~10 files per table)
        put_requests = table_count * 10
        s3_put_cost = (put_requests / 1000) * self.S3_PUT_REQUEST_PER_1000

        total_setup = (
            s3_initial_storage + glue_cost + data_transfer + s3_put_cost
        )

        return {
            "s3_initial_storage": s3_initial_storage,
            "glue_api_calls": glue_cost,
            "data_transfer": data_transfer,
            "s3_put_requests": s3_put_cost,
            "total_setup": total_setup,
        }

    def _calculate_recurring_costs(
        self,
        data_size_bytes: int,
        table_count: int,
        destination_type: str,
    ) -> dict[str, float]:
        """Calculate monthly recurring costs.

        Includes S3 storage (optimistic and conservative), Glue catalog
        requests, and Athena query costs.

        Args:
            data_size_bytes: Total raw data size in bytes.
            table_count: Number of tables.
            destination_type: Iceberg destination type.

        Returns:
            Dict with itemized recurring costs and totals.
        """
        data_size_gb = data_size_bytes / (1024**3)

        # Storage costs (optimistic = 5:1, conservative = 3:1)
        compressed_optimistic = data_size_gb / self.ZSTD_COMPRESSION_RATIO_OPTIMISTIC
        compressed_conservative = data_size_gb / self.ZSTD_COMPRESSION_RATIO_CONSERVATIVE

        if destination_type == "iceberg_s3_tables":
            storage_rate = self.S3_TABLES_STORAGE_PER_GB_MONTH
        else:
            storage_rate = self.S3_STORAGE_PER_GB_MONTH

        s3_storage_optimistic = compressed_optimistic * storage_rate
        s3_storage_conservative = compressed_conservative * storage_rate

        # Glue catalog monthly requests (reads for queries)
        # Estimate: table_count * 100 requests/month for metadata reads
        glue_monthly_requests = table_count * 100
        glue_catalog = (
            glue_monthly_requests / 1_000_000
        ) * self.GLUE_CATALOG_PER_MILLION_REQUESTS

        # Athena verification queries
        athena_queries = table_count * self.ATHENA_QUERIES_PER_TABLE_MONTH
        avg_scan_gb = (
            compressed_conservative / max(table_count, 1)
        ) * self.ATHENA_SCAN_FRACTION
        athena_cost = (
            athena_queries * avg_scan_gb / 1024
        ) * self.ATHENA_PER_TB_SCANNED

        total_optimistic = s3_storage_optimistic + glue_catalog + athena_cost
        total_conservative = s3_storage_conservative + glue_catalog + athena_cost

        return {
            "s3_storage_optimistic": s3_storage_optimistic,
            "s3_storage_conservative": s3_storage_conservative,
            "glue_catalog": glue_catalog,
            "athena_verification": athena_cost,
            "total_monthly_optimistic": total_optimistic,
            "total_monthly_conservative": total_conservative,
        }

    def _project_costs(
        self,
        base_monthly: float,
        growth_rate: float,
    ) -> dict[str, float]:
        """Project costs at 3, 6, and 12 month horizons.

        Uses compound growth to project cumulative costs over time.
        Each month's cost grows by the growth_rate factor.

        Args:
            base_monthly: Base monthly cost (conservative estimate).
            growth_rate: Monthly data growth rate (e.g., 0.05 for 5%).

        Returns:
            Dict with projected cumulative costs at 3/6/12 months.
        """
        three_month = base_monthly * sum(
            (1 + growth_rate) ** i for i in range(3)
        )
        six_month = base_monthly * sum(
            (1 + growth_rate) ** i for i in range(6)
        )
        twelve_month = base_monthly * sum(
            (1 + growth_rate) ** i for i in range(12)
        )

        return {
            "3_month_total": three_month,
            "6_month_total": six_month,
            "12_month_total": twelve_month,
        }

    def _calculate_tco_comparison(
        self,
        bq_costs: dict,
        iceberg_recurring: dict,
    ) -> dict[str, float]:
        """Compare BigQuery current costs vs projected Iceberg costs.

        Args:
            bq_costs: Dict with 'monthly_cost' for current BQ spend.
            iceberg_recurring: Dict with recurring cost breakdown.

        Returns:
            Dict with TCO comparison metrics.
        """
        bq_monthly = bq_costs.get("monthly_cost", 0.0)
        iceberg_monthly = iceberg_recurring.get(
            "total_monthly_conservative", 0.0
        )

        monthly_savings = bq_monthly - iceberg_monthly
        annual_savings = monthly_savings * 12

        return {
            "bigquery_current_monthly": bq_monthly,
            "iceberg_projected_monthly": iceberg_monthly,
            "monthly_savings": monthly_savings,
            "annual_savings_projected": annual_savings,
        }

    def recalculate_with_growth_rate(
        self,
        report: CostReport,
        new_growth_rate: float,
    ) -> CostReport:
        """Re-calculate projections with user-adjusted growth rate.

        Creates a new CostReport with updated projections based on the
        new growth rate while preserving all other cost data.

        Args:
            report: Existing CostReport to recalculate.
            new_growth_rate: New monthly growth rate (e.g., 0.10 for 10%).

        Returns:
            New CostReport with updated projections.
        """
        base_monthly = report.recurring_monthly.get(
            "total_monthly_conservative", 0.0
        )
        new_projections = self._project_costs(base_monthly, new_growth_rate)

        return CostReport(
            generated_at=report.generated_at,
            data_size_gb=report.data_size_gb,
            compressed_size_gb_optimistic=report.compressed_size_gb_optimistic,
            compressed_size_gb_conservative=report.compressed_size_gb_conservative,
            setup_costs=report.setup_costs,
            recurring_monthly=report.recurring_monthly,
            projections={
                "growth_rate_monthly": new_growth_rate,
                **new_projections,
            },
            tco_comparison=report.tco_comparison,
            growth_rate_monthly=new_growth_rate,
            destination_type=report.destination_type,
        )
