"""
AWS Pricing Service - Fetches real-time pricing from AWS public bulk pricing API.
No IAM credentials required - uses publicly accessible pricing endpoint.
"""
import json
import logging
import urllib.request
from typing import Dict, Optional, Tuple
from functools import lru_cache

logger = logging.getLogger(__name__)

# Public AWS pricing endpoint (no auth needed)
PRICING_BASE_URL = "https://pricing.us-east-1.amazonaws.com"
INDEX_URL = f"{PRICING_BASE_URL}/offers/v1.0/aws/index.json"


class AWSPricingService:
    """Fetches real-time Redshift pricing from AWS public bulk pricing files."""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self._region_pricing_cache: Dict[str, Dict] = {}

    def _fetch_json(self, url: str) -> Optional[dict]:
        """Fetch and parse JSON from a URL."""
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read())
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return None

    @lru_cache(maxsize=1)
    def _get_redshift_index(self) -> Optional[str]:
        """Get the Redshift regional index URL."""
        index = self._fetch_json(INDEX_URL)
        if not index:
            return None
        return index.get("offers", {}).get("AmazonRedshift", {}).get(
            "currentRegionIndexUrl"
        )

    def _load_region_pricing(self, region: str) -> Optional[Dict]:
        """Load and cache all Redshift pricing for a region."""
        if region in self._region_pricing_cache:
            return self._region_pricing_cache[region]

        redshift_index_path = self._get_redshift_index()
        if not redshift_index_path:
            return None

        region_index = self._fetch_json(f"{PRICING_BASE_URL}{redshift_index_path}")
        if not region_index:
            return None

        region_info = region_index.get("regions", {}).get(region)
        if not region_info:
            logger.warning(f"Region {region} not found in Redshift pricing index")
            return None

        version_url = region_info.get("currentVersionUrl")
        if not version_url:
            return None

        # This file can be a few MB, but we cache it
        pricing_data = self._fetch_json(f"{PRICING_BASE_URL}{version_url}")
        if pricing_data:
            self._region_pricing_cache[region] = pricing_data
        return pricing_data

    def get_redshift_node_pricing(
        self, instance_type: str, region: str = "us-east-1"
    ) -> Optional[float]:
        """
        Get on-demand hourly price for a Redshift node type.

        Args:
            instance_type: e.g. 'ra3.xlplus', 'ra3.4xlarge'
            region: AWS region code

        Returns:
            Hourly price in USD, or None if not found.
        """
        pricing_data = self._load_region_pricing(region)
        if not pricing_data:
            return None

        products = pricing_data.get("products", {})
        terms = pricing_data.get("terms", {})

        for sku, product in products.items():
            attrs = product.get("attributes", {})
            if (
                attrs.get("instanceType") == instance_type
                and "Node:" in attrs.get("usagetype", "")
                and "CS" not in attrs.get("usagetype", "")
            ):
                on_demand = terms.get("OnDemand", {}).get(sku, {})
                for term_data in on_demand.values():
                    for dim_data in term_data.get("priceDimensions", {}).values():
                        price = dim_data.get("pricePerUnit", {}).get("USD")
                        if price and float(price) > 0:
                            return float(price)
        return None

    def get_redshift_serverless_pricing(
        self, region: str = "us-east-1"
    ) -> Optional[float]:
        """Get Redshift Serverless RPU-hour price."""
        pricing_data = self._load_region_pricing(region)
        if not pricing_data:
            return None

        products = pricing_data.get("products", {})
        terms = pricing_data.get("terms", {})

        for sku, product in products.items():
            attrs = product.get("attributes", {})
            usage_type = attrs.get("usagetype", "")
            product_family = attrs.get("productFamily", "")
            # Match serverless RPU pricing - check multiple patterns:
            # usagetype may contain "ServerlessUsage" or "RPU" 
            # productFamily may be "Redshift Serverless" or "ServerlessUsage"
            is_serverless = (
                ("RPU" in usage_type)
                or ("Serverless" in product_family and "Redshift" in product_family)
                or ("ServerlessUsage" in usage_type)
            )
            if is_serverless:
                on_demand = terms.get("OnDemand", {}).get(sku, {})
                for term_data in on_demand.values():
                    for dim_data in term_data.get("priceDimensions", {}).values():
                        price = dim_data.get("pricePerUnit", {}).get("USD")
                        if price and float(price) > 0:
                            return float(price)
        return None

    def get_managed_storage_pricing(
        self, region: str = "us-east-1"
    ) -> Optional[float]:
        """Get Redshift Managed Storage (RMS) price per GB-month."""
        pricing_data = self._load_region_pricing(region)
        if not pricing_data:
            return None

        products = pricing_data.get("products", {})
        terms = pricing_data.get("terms", {})

        for sku, product in products.items():
            attrs = product.get("attributes", {})
            usage_type = attrs.get("usagetype", "")
            product_family = attrs.get("productFamily", "")
            # Match managed storage: usagetype contains "RMS:" or 
            # productFamily contains "Managed Storage"
            is_rms = (
                "RMS:" in usage_type
                or ("ManagedStorage" in usage_type)
                or ("Managed Storage" in product_family and "Redshift" in str(attrs))
            )
            if is_rms:
                on_demand = terms.get("OnDemand", {}).get(sku, {})
                for term_data in on_demand.values():
                    for dim_data in term_data.get("priceDimensions", {}).values():
                        price = dim_data.get("pricePerUnit", {}).get("USD")
                        if price and float(price) > 0:
                            return float(price)
        return None

    def get_all_redshift_pricing(
        self, region: str = "us-east-1"
    ) -> Dict:
        """
        Get all Redshift pricing for a region in one call.
        Returns dict matching the REDSHIFT_PRICING format used by TCOEngine.
        """
        node_types = ["ra3.xlplus", "ra3.4xlarge", "ra3.16xlarge",
                       "dc2.large", "dc2.8xlarge"]

        provisioned = {}
        for nt in node_types:
            price = self.get_redshift_node_pricing(nt, region)
            if price:
                provisioned[nt] = price

        serverless = self.get_redshift_serverless_pricing(region)
        storage = self.get_managed_storage_pricing(region)

        return {
            "provisioned": provisioned,
            "serverless_per_rpu_hour": serverless,
            "managed_storage_per_gb_month": storage,
        }
