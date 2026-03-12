"""
TCO (Total Cost of Ownership) Analysis Engine

Compares BigQuery costs vs Redshift costs (Provisioned & Serverless)
with real AWS pricing data per region.

Key improvements over naive calculation:
- BQ costs extrapolated from actual query window to monthly/annual
- Serverless RPU-hours derived from actual BQ slot usage (not flat %)
- Provisioned costs include RI pricing options
- Migration costs include DataSync transfer
- Real-time AWS pricing via AWS Pricing API (with fallback to cached prices)
"""

import logging
import math
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


def _fmt(n: float) -> str:
    """Format a number as a dollar amount."""
    return f'${n:,.2f}'


# Fallback AWS Redshift pricing by region (USD/hour per node for Provisioned,
# USD/RPU-hour for Serverless). Prices as of early 2026.
# Used when AWS Pricing API is unavailable.
REDSHIFT_PRICING = {
    'us-east-1': {
        'label': 'US East (N. Virginia)',
        'provisioned': {
            'ra3.xlplus': 1.086, 'ra3.4xlarge': 3.26, 'ra3.16xlarge': 13.04,
            'dc2.large': 0.25, 'dc2.8xlarge': 4.80,
        },
        'serverless_per_rpu_hour': 0.375,
        'managed_storage_per_gb_month': 0.024,
    },
    'us-east-2': {
        'label': 'US East (Ohio)',
        'provisioned': {
            'ra3.xlplus': 1.086, 'ra3.4xlarge': 3.26, 'ra3.16xlarge': 13.04,
            'dc2.large': 0.25, 'dc2.8xlarge': 4.80,
        },
        'serverless_per_rpu_hour': 0.375,
        'managed_storage_per_gb_month': 0.024,
    },
    'us-west-1': {
        'label': 'US West (N. California)',
        'provisioned': {
            'ra3.xlplus': 1.221, 'ra3.4xlarge': 3.67, 'ra3.16xlarge': 14.672,
            'dc2.large': 0.28, 'dc2.8xlarge': 5.40,
        },
        'serverless_per_rpu_hour': 0.42,
        'managed_storage_per_gb_month': 0.027,
    },
    'us-west-2': {
        'label': 'US West (Oregon)',
        'provisioned': {
            'ra3.xlplus': 1.086, 'ra3.4xlarge': 3.26, 'ra3.16xlarge': 13.04,
            'dc2.large': 0.25, 'dc2.8xlarge': 4.80,
        },
        'serverless_per_rpu_hour': 0.375,
        'managed_storage_per_gb_month': 0.024,
    },
    'ca-central-1': {
        'label': 'Canada (Central)',
        'provisioned': {
            'ra3.xlplus': 1.196, 'ra3.4xlarge': 3.586, 'ra3.16xlarge': 14.344,
            'dc2.large': 0.275, 'dc2.8xlarge': 5.28,
        },
        'serverless_per_rpu_hour': 0.413,
        'managed_storage_per_gb_month': 0.026,
    },
    'eu-west-1': {
        'label': 'EU (Ireland)',
        'provisioned': {
            'ra3.xlplus': 1.196, 'ra3.4xlarge': 3.586, 'ra3.16xlarge': 14.344,
            'dc2.large': 0.275, 'dc2.8xlarge': 5.28,
        },
        'serverless_per_rpu_hour': 0.413,
        'managed_storage_per_gb_month': 0.026,
    },
    'eu-west-2': {
        'label': 'EU (London)',
        'provisioned': {
            'ra3.xlplus': 1.253, 'ra3.4xlarge': 3.76, 'ra3.16xlarge': 15.04,
            'dc2.large': 0.289, 'dc2.8xlarge': 5.544,
        },
        'serverless_per_rpu_hour': 0.433,
        'managed_storage_per_gb_month': 0.028,
    },
    'eu-west-3': {
        'label': 'EU (Paris)',
        'provisioned': {
            'ra3.xlplus': 1.253, 'ra3.4xlarge': 3.76, 'ra3.16xlarge': 15.04,
            'dc2.large': 0.289, 'dc2.8xlarge': 5.544,
        },
        'serverless_per_rpu_hour': 0.433,
        'managed_storage_per_gb_month': 0.028,
    },
    'eu-central-1': {
        'label': 'EU (Frankfurt)',
        'provisioned': {
            'ra3.xlplus': 1.253, 'ra3.4xlarge': 3.76, 'ra3.16xlarge': 15.04,
            'dc2.large': 0.289, 'dc2.8xlarge': 5.544,
        },
        'serverless_per_rpu_hour': 0.433,
        'managed_storage_per_gb_month': 0.028,
    },
    'eu-north-1': {
        'label': 'EU (Stockholm)',
        'provisioned': {
            'ra3.xlplus': 1.164, 'ra3.4xlarge': 3.49, 'ra3.16xlarge': 13.96,
            'dc2.large': 0.268, 'dc2.8xlarge': 5.136,
        },
        'serverless_per_rpu_hour': 0.401,
        'managed_storage_per_gb_month': 0.026,
    },
    'eu-south-1': {
        'label': 'EU (Milan)',
        'provisioned': {
            'ra3.xlplus': 1.296, 'ra3.4xlarge': 3.888, 'ra3.16xlarge': 15.552,
            'dc2.large': 0.299, 'dc2.8xlarge': 5.736,
        },
        'serverless_per_rpu_hour': 0.448,
        'managed_storage_per_gb_month': 0.029,
    },
    'ap-south-1': {
        'label': 'Asia Pacific (Mumbai)',
        'provisioned': {
            'ra3.xlplus': 1.086, 'ra3.4xlarge': 3.26, 'ra3.16xlarge': 13.04,
            'dc2.large': 0.25, 'dc2.8xlarge': 4.80,
        },
        'serverless_per_rpu_hour': 0.360,
        'managed_storage_per_gb_month': 0.024,
    },
    'ap-northeast-1': {
        'label': 'Asia Pacific (Tokyo)',
        'provisioned': {
            'ra3.xlplus': 1.32, 'ra3.4xlarge': 3.96, 'ra3.16xlarge': 15.84,
            'dc2.large': 0.304, 'dc2.8xlarge': 5.832,
        },
        'serverless_per_rpu_hour': 0.455,
        'managed_storage_per_gb_month': 0.029,
    },
    'ap-northeast-2': {
        'label': 'Asia Pacific (Seoul)',
        'provisioned': {
            'ra3.xlplus': 1.253, 'ra3.4xlarge': 3.76, 'ra3.16xlarge': 15.04,
            'dc2.large': 0.289, 'dc2.8xlarge': 5.544,
        },
        'serverless_per_rpu_hour': 0.433,
        'managed_storage_per_gb_month': 0.028,
    },
    'ap-northeast-3': {
        'label': 'Asia Pacific (Osaka)',
        'provisioned': {
            'ra3.xlplus': 1.32, 'ra3.4xlarge': 3.96, 'ra3.16xlarge': 15.84,
            'dc2.large': 0.304, 'dc2.8xlarge': 5.832,
        },
        'serverless_per_rpu_hour': 0.455,
        'managed_storage_per_gb_month': 0.029,
    },
    'ap-southeast-1': {
        'label': 'Asia Pacific (Singapore)',
        'provisioned': {
            'ra3.xlplus': 1.253, 'ra3.4xlarge': 3.76, 'ra3.16xlarge': 15.04,
            'dc2.large': 0.289, 'dc2.8xlarge': 5.544,
        },
        'serverless_per_rpu_hour': 0.433,
        'managed_storage_per_gb_month': 0.028,
    },
    'ap-southeast-2': {
        'label': 'Asia Pacific (Sydney)',
        'provisioned': {
            'ra3.xlplus': 1.32, 'ra3.4xlarge': 3.96, 'ra3.16xlarge': 15.84,
            'dc2.large': 0.304, 'dc2.8xlarge': 5.832,
        },
        'serverless_per_rpu_hour': 0.455,
        'managed_storage_per_gb_month': 0.029,
    },
    'ap-southeast-3': {
        'label': 'Asia Pacific (Jakarta)',
        'provisioned': {
            'ra3.xlplus': 1.253, 'ra3.4xlarge': 3.76, 'ra3.16xlarge': 15.04,
            'dc2.large': 0.289, 'dc2.8xlarge': 5.544,
        },
        'serverless_per_rpu_hour': 0.433,
        'managed_storage_per_gb_month': 0.028,
    },
    'ap-east-1': {
        'label': 'Asia Pacific (Hong Kong)',
        'provisioned': {
            'ra3.xlplus': 1.386, 'ra3.4xlarge': 4.158, 'ra3.16xlarge': 16.632,
            'dc2.large': 0.319, 'dc2.8xlarge': 6.12,
        },
        'serverless_per_rpu_hour': 0.478,
        'managed_storage_per_gb_month': 0.031,
    },
    'sa-east-1': {
        'label': 'South America (São Paulo)',
        'provisioned': {
            'ra3.xlplus': 1.58, 'ra3.4xlarge': 4.74, 'ra3.16xlarge': 18.96,
            'dc2.large': 0.364, 'dc2.8xlarge': 6.984,
        },
        'serverless_per_rpu_hour': 0.545,
        'managed_storage_per_gb_month': 0.035,
    },
}

# BigQuery pricing constants
BQ_STORAGE_ACTIVE_PER_GB_MONTH = 0.02
BQ_STORAGE_LONGTERM_PER_GB_MONTH = 0.01
BQ_QUERY_ON_DEMAND_PER_TB = 6.25  # Updated 2025+ pricing
BQ_EDITIONS_STANDARD_PER_SLOT_HOUR = 0.04  # Standard edition
BQ_EDITIONS_ENTERPRISE_PER_SLOT_HOUR = 0.06  # Enterprise edition

# Data transfer pricing (GCP egress to AWS)
DATA_TRANSFER_PER_GB = 0.12


class TCOEngine:
    """
    Calculates and compares Total Cost of Ownership between
    BigQuery (current) and Redshift (target) configurations.
    Uses AWS Pricing API for real-time pricing with fallback to cached prices.
    """
    
    def __init__(self, use_live_pricing: bool = True):
        """
        Initialize TCO Engine.
        
        Args:
            use_live_pricing: If True, fetch real-time pricing from AWS API.
                            If False or API fails, use fallback cached prices.
        """
        self.use_live_pricing = use_live_pricing
        self.pricing_service = None
        
        if use_live_pricing:
            try:
                from .aws_pricing_service import AWSPricingService
                self.pricing_service = AWSPricingService()
                logger.info("AWS Pricing Service initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize AWS Pricing Service: {e}. Using fallback prices.")
                self.pricing_service = None
    
    def _get_region_pricing(self, aws_region: str, provisioned_config: Dict) -> Dict:
        """
        Get pricing for a region, using live AWS API if available, otherwise fallback.
        
        Args:
            aws_region: AWS region code
            provisioned_config: Provisioned cluster config with node_type
        
        Returns:
            Pricing dictionary with provisioned, serverless, and storage rates
        """
        # Start with fallback pricing
        fallback_pricing = REDSHIFT_PRICING.get(aws_region, REDSHIFT_PRICING['us-east-1'])
        
        if not self.pricing_service:
            return fallback_pricing
        
        try:
            # Fetch all Redshift pricing for this region in one call
            all_pricing = self.pricing_service.get_all_redshift_pricing(aws_region)
            
            # Build pricing dict with live prices where available, fallback for missing
            live_pricing = {
                'label': fallback_pricing['label'],
                'provisioned': fallback_pricing['provisioned'].copy(),
                'serverless_per_rpu_hour': fallback_pricing['serverless_per_rpu_hour'],
                'managed_storage_per_gb_month': fallback_pricing['managed_storage_per_gb_month'],
            }
            
            # Update provisioned node prices from live data
            for nt, price in all_pricing.get('provisioned', {}).items():
                live_pricing['provisioned'][nt] = price
                logger.info(f"Live AWS pricing for {nt} in {aws_region}: ${price}/hr")
            
            # Update serverless and storage prices if available
            if all_pricing.get('serverless_per_rpu_hour'):
                live_pricing['serverless_per_rpu_hour'] = all_pricing['serverless_per_rpu_hour']
                logger.info(f"Live serverless pricing in {aws_region}: ${all_pricing['serverless_per_rpu_hour']}/RPU-hr")
            
            if all_pricing.get('managed_storage_per_gb_month'):
                live_pricing['managed_storage_per_gb_month'] = all_pricing['managed_storage_per_gb_month']
                logger.info(f"Live storage pricing in {aws_region}: ${all_pricing['managed_storage_per_gb_month']}/GB-mo")
            
            return live_pricing
            
        except Exception as e:
            logger.warning(f"Error fetching live AWS pricing: {e}. Using fallback prices.")
            return fallback_pricing

    def calculate_tco(
        self,
        assessment: Dict,
        tables: List[Dict],
        query_stats: List[Dict],
        provisioned_config: Dict,
        serverless_config: Dict,
        workload_metrics: Dict,
        aws_region: str = 'us-east-1',
    ) -> Dict[str, Any]:
        """Calculate comprehensive TCO comparison."""
        total_size_gb = assessment.get('total_size_mb', 0) / 1024
        total_queries = len(query_stats)
        total_bytes_scanned = sum(q.get('bytes_scanned', 0) for q in query_stats)

        # Use workload metrics for accurate extrapolation
        query_time_span_days = workload_metrics.get('query_time_span_days', 30)
        monthly_slot_hours = workload_metrics.get('estimated_monthly_slot_hours', 0)
        rpu_hours_monthly = workload_metrics.get('estimated_rpu_hours_monthly', 0)

        # Extrapolate bytes scanned to monthly
        if query_time_span_days > 0:
            daily_bytes = total_bytes_scanned / query_time_span_days
            monthly_bytes = daily_bytes * 30
        else:
            monthly_bytes = total_bytes_scanned

        monthly_tb_scanned = monthly_bytes / (1024 ** 4) if monthly_bytes else 0

        # Get region pricing (with live AWS API or fallback)
        region_pricing = self._get_region_pricing(aws_region, provisioned_config)

        # 1. Current BigQuery costs (extrapolated to monthly)
        bq_costs = self._calculate_bq_costs(
            total_size_gb, monthly_tb_scanned, total_queries,
            monthly_slot_hours, query_time_span_days
        )

        # 2. Redshift Provisioned costs
        provisioned_costs = self._calculate_provisioned_costs(
            provisioned_config, total_size_gb, region_pricing
        )

        # 3. Redshift Serverless costs (using actual RPU-hours)
        serverless_costs = self._calculate_serverless_costs(
            serverless_config, total_size_gb, region_pricing, rpu_hours_monthly
        )

        # 4. One-time migration costs
        migration_costs = self._calculate_migration_costs(total_size_gb)

        # 5. 3-year TCO comparison
        # Use on-demand pricing for provisioned (consistent with detail card display)
        bq_3yr = bq_costs['annual'] * 3
        prov_3yr = provisioned_costs['annual'] * 3 + migration_costs['total']
        svls_3yr = serverless_costs['annual'] * 3 + migration_costs['total']

        # Check if provisioned is overkill for light workloads
        provisioned_viable = True
        provisioned_note = None
        if monthly_slot_hours < 10:
            provisioned_viable = False
            provisioned_note = (
                'Provisioned cluster is not recommended for this workload. '
                f'With only {monthly_slot_hours:.1f} slot-hours/month, a 24/7 cluster would be idle >99% of the time. '
                'Serverless pay-per-query is significantly more cost-effective.'
            )

        best_redshift = 'serverless' if (svls_3yr < prov_3yr or not provisioned_viable) else 'provisioned'
        best_redshift_3yr = svls_3yr if best_redshift == 'serverless' else prov_3yr
        savings = bq_3yr - best_redshift_3yr
        savings_pct = (savings / bq_3yr * 100) if bq_3yr > 0 else 0

        return {
            'aws_region': aws_region,
            'region_label': region_pricing['label'],
            'bigquery_costs': bq_costs,
            'provisioned_costs': provisioned_costs,
            'serverless_costs': serverless_costs,
            'migration_costs': migration_costs,
            'comparison': {
                'bq_3yr_tco': round(bq_3yr, 2),
                'provisioned_3yr_tco': round(prov_3yr, 2),
                'serverless_3yr_tco': round(svls_3yr, 2),
                'provisioned_ri1yr_3yr_tco': round(provisioned_costs['ri_1yr_annual'] * 3 + migration_costs['total'], 2),
                'provisioned_ri3yr_3yr_tco': round(provisioned_costs['ri_3yr_annual'] * 3 + migration_costs['total'], 2),
                'best_option': best_redshift,
                'savings_amount': round(savings, 2),
                'savings_pct': round(savings_pct, 1),
                'provisioned_viable': provisioned_viable,
                'provisioned_note': provisioned_note,
            },
            'workload_summary': {
                'query_time_span_days': round(query_time_span_days, 1),
                'monthly_slot_hours': round(monthly_slot_hours, 2),
                'monthly_tb_scanned': round(monthly_tb_scanned, 4),
                'estimated_rpu_hours_monthly': round(rpu_hours_monthly, 1),
                'total_queries': total_queries,
                'workload_type': self._classify_workload(monthly_slot_hours, total_queries, query_time_span_days),
                'avg_wall_clock_seconds': workload_metrics.get('avg_wall_clock_seconds', 0),
                'active_hours_per_day': workload_metrics.get('active_hours_per_day', 0),
                'estimated_base_rpu': workload_metrics.get('estimated_base_rpu', 8),
                'max_concurrent_slots': workload_metrics.get('max_concurrent_slots', 0),
                'min_concurrent_slots': workload_metrics.get('min_concurrent_slots', 0),
                'avg_concurrent_slots': workload_metrics.get('avg_concurrent_slots', 0),
                'median_concurrent_slots': workload_metrics.get('median_concurrent_slots', 0),
                'estimated_peak_slots': workload_metrics.get('estimated_peak_slots', 0),
            },
            'recommendation': self._generate_recommendation(
                bq_costs, provisioned_costs, serverless_costs,
                monthly_slot_hours, rpu_hours_monthly, total_queries,
                query_time_span_days, total_size_gb, provisioned_viable
            ),
            'cost_notes': self._generate_cost_notes(
                bq_costs, provisioned_costs, serverless_costs,
                migration_costs, provisioned_config, region_pricing,
                aws_region, query_time_span_days, monthly_slot_hours
            ),
        }

    def get_available_regions(self) -> List[Dict]:
        """Return list of available AWS regions with labels."""
        return [
            {'value': k, 'label': v['label']}
            for k, v in REDSHIFT_PRICING.items()
        ]

    def _calculate_bq_costs(
        self, size_gb: float, monthly_tb_scanned: float,
        total_queries: int, monthly_slot_hours: float,
        query_time_span_days: float
    ) -> Dict:
        """
        Calculate current BigQuery costs.

        Two pricing models shown:
        1. On-Demand: $6.25/TB scanned (extrapolated to monthly)
        2. Editions (slot-based): monthly_slot_hours * per-slot-hour rate

        We use the HIGHER of the two as the "current cost" since
        customers typically use whichever is cheaper for their workload.
        """
        # Storage cost
        storage_monthly = size_gb * BQ_STORAGE_ACTIVE_PER_GB_MONTH
        storage_annual = storage_monthly * 12

        # On-demand query cost (extrapolated monthly)
        query_on_demand_monthly = monthly_tb_scanned * BQ_QUERY_ON_DEMAND_PER_TB
        query_on_demand_annual = query_on_demand_monthly * 12

        # Slot-based cost (editions pricing)
        # If we have slot hours, calculate what it would cost under editions
        slot_based_monthly = monthly_slot_hours * BQ_EDITIONS_STANDARD_PER_SLOT_HOUR
        slot_based_annual = slot_based_monthly * 12

        # Use the higher estimate (more realistic for what customer is paying)
        query_monthly = max(query_on_demand_monthly, slot_based_monthly)
        query_annual = query_monthly * 12
        pricing_model = 'On-Demand' if query_on_demand_monthly >= slot_based_monthly else 'Editions (Standard)'

        total_monthly = storage_monthly + query_monthly
        total_annual = storage_annual + query_annual

        # Extrapolate query count to monthly
        daily_queries = total_queries / max(query_time_span_days, 1)
        monthly_queries = round(daily_queries * 30)

        return {
            'storage': {
                'data_volume_gb': round(size_gb, 2),
                'rate_per_gb_month': BQ_STORAGE_ACTIVE_PER_GB_MONTH,
                'storage_type': 'Active Storage',
                'monthly': round(storage_monthly, 2),
                'annual': round(storage_annual, 2),
            },
            'query': {
                'queries_analyzed': total_queries,
                'estimated_monthly_queries': monthly_queries,
                'monthly_tb_scanned': round(monthly_tb_scanned, 4),
                'on_demand_monthly': round(query_on_demand_monthly, 2),
                'slot_based_monthly': round(slot_based_monthly, 2),
                'monthly_slot_hours': round(monthly_slot_hours, 2),
                'pricing_model': pricing_model,
                'monthly': round(query_monthly, 2),
                'annual': round(query_annual, 2),
            },
            'monthly': round(total_monthly, 2),
            'annual': round(total_annual, 2),
        }

    def _calculate_provisioned_costs(self, config: Dict, size_gb: float, pricing: Dict) -> Dict:
        """Calculate Redshift Provisioned cluster costs (24/7 on-demand)."""
        node_type = config.get('node_type', 'ra3.xlplus')
        num_nodes = config.get('num_nodes', 2)

        hourly_per_node = pricing['provisioned'].get(node_type, 1.086)
        total_hourly = hourly_per_node * num_nodes
        compute_monthly = total_hourly * 730  # 730 hours/month

        # Managed storage cost (for ra3 nodes)
        storage_monthly = 0
        if 'ra3' in node_type:
            storage_monthly = size_gb * pricing['managed_storage_per_gb_month']

        total_monthly = compute_monthly + storage_monthly
        total_annual = total_monthly * 12

        # Also show RI pricing (1-year no upfront = ~40% discount)
        ri_1yr_monthly = compute_monthly * 0.6 + storage_monthly
        ri_1yr_annual = ri_1yr_monthly * 12
        # 3-year all upfront = ~75% discount
        ri_3yr_monthly = compute_monthly * 0.25 + storage_monthly
        ri_3yr_annual = ri_3yr_monthly * 12

        result = {
            'node_type': node_type,
            'num_nodes': num_nodes,
            'hourly_per_node': round(hourly_per_node, 3),
            'total_hourly': round(total_hourly, 3),
            'compute_monthly': round(compute_monthly, 2),
            'storage_monthly': round(storage_monthly, 2),
            'monthly': round(total_monthly, 2),
            'annual': round(total_annual, 2),
            'ri_1yr_monthly': round(ri_1yr_monthly, 2),
            'ri_1yr_annual': round(ri_1yr_annual, 2),
            'ri_3yr_monthly': round(ri_3yr_monthly, 2),
            'ri_3yr_annual': round(ri_3yr_annual, 2),
        }

        # Pass through sizing justification from recommendation engine
        if 'sizing_basis' in config:
            result['sizing_basis'] = config['sizing_basis']
        if 'sizing_rationale' in config:
            result['sizing_rationale'] = config['sizing_rationale']
        if 'vcpu_total' in config:
            result['vcpu_total'] = config['vcpu_total']
        if 'memory_gb_total' in config:
            result['memory_gb_total'] = config['memory_gb_total']

        return result

    def _calculate_serverless_costs(
        self, config: Dict, size_gb: float, pricing: Dict,
        actual_rpu_hours_monthly: float
    ) -> Dict:
        """
        Calculate Redshift Serverless costs using workload-derived RPU-hours.

        Redshift Serverless billing model:
        - Billed per RPU-hour on a per-second basis
        - 60-second minimum charge per warehouse activation
        - Base RPU is the minimum always allocated during active queries
        - Auto-scales up to max RPU based on query complexity
        - No charge when idle (no queries running)
        - Storage billed separately (same RMS rate as provisioned)
        """
        base_rpu = config.get('base_rpu', 8)
        max_rpu = config.get('max_rpu', 32)
        rpu_hour_rate = pricing['serverless_per_rpu_hour']

        # Use actual RPU-hours from workload analysis
        # This already accounts for 60s minimum billing and concurrency
        rpu_hours_month = max(actual_rpu_hours_monthly, 0)

        compute_monthly = rpu_hours_month * rpu_hour_rate

        # Storage (same RMS pricing as provisioned)
        storage_monthly = size_gb * pricing['managed_storage_per_gb_month']

        total_monthly = compute_monthly + storage_monthly
        total_annual = total_monthly * 12

        # Calculate effective utilization for display
        max_possible = base_rpu * 730
        utilization_pct = (rpu_hours_month / max_possible * 100) if max_possible > 0 else 0

        return {
            'base_rpu': base_rpu,
            'max_rpu': max_rpu,
            'est_rpu_hours_monthly': round(rpu_hours_month, 1),
            'est_utilization_pct': round(min(utilization_pct, 100), 1),
            'rpu_hour_rate': round(rpu_hour_rate, 3),
            'compute_monthly': round(compute_monthly, 2),
            'storage_monthly': round(storage_monthly, 2),
            'monthly': round(total_monthly, 2),
            'annual': round(total_annual, 2),
        }

    def _calculate_migration_costs(self, size_gb: float) -> Dict:
        """Calculate one-time data transfer costs."""
        transfer_cost = size_gb * DATA_TRANSFER_PER_GB
        return {
            'data_volume_gb': round(size_gb, 2),
            'rate_per_gb': DATA_TRANSFER_PER_GB,
            'total': round(transfer_cost, 2),
        }

    def _generate_cost_notes(
        self, bq, prov, svls, migration, prov_config, pricing,
        region, query_span_days, monthly_slot_hours
    ) -> List[str]:
        """Generate explanatory notes for the cost analysis."""
        node_type = prov_config.get('node_type', 'ra3.xlplus')
        num_nodes = prov_config.get('num_nodes', 2)
        notes = [
            f'BigQuery costs extrapolated from {query_span_days:.0f} days of captured query data to monthly estimates.',
            f'BQ query cost uses the higher of On-Demand (${BQ_QUERY_ON_DEMAND_PER_TB}/TB) or Editions (${BQ_EDITIONS_STANDARD_PER_SLOT_HOUR}/slot-hour) pricing.',
            f'BQ monthly compute: {monthly_slot_hours:.1f} slot-hours/month estimated from INFORMATION_SCHEMA.JOBS.',
            f'Redshift Provisioned shows On-Demand, 1-Year RI (40% discount), and 3-Year RI (75% discount) pricing.',
            f'Redshift Serverless RPU-hours account for 60-second minimum billing per activation, query concurrency, and a 1.5× overhead factor vs BQ slot-hours.',
            f'Redshift Serverless: {svls.get("est_rpu_hours_monthly", 0):.1f} RPU-hours/month estimated from BQ workload analysis.',
            f'Data transfer cost (${migration["total"]:.2f}) is a one-time GCP egress expense included in Redshift 3-year TCO.',
            f'Pricing for region: {region} ({pricing["label"]}).',
        ]
        if monthly_slot_hours < 10:
            notes.append(
                '⚠️ Very low BQ compute detected. Provisioned cluster would be idle >99% of the time — '
                'Serverless is strongly recommended. If the assessment captured only a subset of queries, '
                'actual costs may be higher.'
            )
        return notes

    def _classify_workload(self, monthly_slot_hours: float, total_queries: int, span_days: float) -> Dict:
        """Classify workload pattern for recommendation context."""
        daily_queries = total_queries / max(span_days, 1)
        daily_slot_hours = monthly_slot_hours / 30

        if monthly_slot_hours < 10:
            pattern = 'sporadic'
            label = 'Sporadic / Light'
            desc = 'Very low compute usage — queries run infrequently with minimal resource consumption.'
        elif monthly_slot_hours < 100:
            pattern = 'light'
            label = 'Light / Intermittent'
            desc = 'Moderate query activity with periods of inactivity. Workload is not continuous.'
        elif monthly_slot_hours < 1000:
            if daily_queries > 200:
                pattern = 'steady'
                label = 'Steady / Consistent'
                desc = 'Regular query activity throughout the day. Workload is predictable and consistent.'
            else:
                pattern = 'bursty'
                label = 'Bursty / Variable'
                desc = 'Concentrated query bursts with idle periods. Workload varies significantly.'
        else:
            pattern = 'heavy'
            label = 'Heavy / Continuous'
            desc = 'High compute usage with sustained query activity. Workload runs near-continuously.'

        return {
            'pattern': pattern,
            'label': label,
            'description': desc,
            'daily_queries': round(daily_queries, 0),
            'daily_slot_hours': round(daily_slot_hours, 2),
        }

    def _generate_recommendation(
        self, bq, prov, svls, monthly_slot_hours, rpu_hours_monthly,
        total_queries, span_days, size_gb, provisioned_viable
    ) -> Dict:
        """Generate a clear recommendation with reasoning based on workload analysis."""
        daily_queries = total_queries / max(span_days, 1)
        workload = self._classify_workload(monthly_slot_hours, total_queries, span_days)
        pattern = workload['pattern']

        # Determine recommendation
        if not provisioned_viable or pattern in ('sporadic', 'light'):
            choice = 'serverless'
            confidence = 'high'
        elif pattern == 'heavy' and size_gb > 500:
            choice = 'provisioned'
            confidence = 'high'
        elif pattern == 'steady' and monthly_slot_hours > 500:
            choice = 'provisioned'
            confidence = 'medium'
        elif svls['monthly'] < prov['monthly'] * 0.7:
            choice = 'serverless'
            confidence = 'high'
        elif prov['ri_1yr_monthly'] < svls['monthly']:
            choice = 'provisioned'
            confidence = 'medium'
        else:
            choice = 'serverless'
            confidence = 'medium'

        # Build reasoning
        reasons = []
        if choice == 'serverless':
            reasons.append(f'Serverless monthly cost ({_fmt(svls["monthly"])}) is lower than Provisioned on-demand ({_fmt(prov["monthly"])}).')
            if pattern in ('sporadic', 'light'):
                reasons.append(f'Workload is {workload["label"].lower()} — pay-per-query avoids paying for idle compute.')
            if daily_queries < 100:
                reasons.append(f'Low query frequency (~{daily_queries:.0f}/day) means a 24/7 cluster would be underutilized.')
            if monthly_slot_hours < 100:
                reasons.append(f'Only {monthly_slot_hours:.1f} slot-hours/month of compute — Serverless auto-scales to match.')
            reasons.append('No cluster management overhead. Auto-scales RPUs based on query complexity.')
            if rpu_hours_monthly > 0:
                reasons.append(f'Estimated {rpu_hours_monthly:.0f} RPU-hours/month at ${svls.get("rpu_hour_rate", 0.375)}/RPU-hr.')
        else:
            reasons.append(f'Provisioned with 1-Year RI ({_fmt(prov["ri_1yr_monthly"])}/mo) is cost-effective for this workload.')
            if pattern in ('steady', 'heavy'):
                reasons.append(f'Workload is {workload["label"].lower()} — dedicated resources provide predictable performance.')
            if monthly_slot_hours >= 500:
                reasons.append(f'High compute usage ({monthly_slot_hours:.1f} slot-hours/month) justifies dedicated cluster.')
            if size_gb >= 500:
                reasons.append(f'Large dataset ({size_gb:.1f} GB) benefits from dedicated compute and managed storage.')
            reasons.append('Reserved Instance pricing offers up to 75% savings over on-demand.')
            reasons.append('Full control over concurrency scaling and WLM queues.')

        # Cost comparison summary
        savings_vs_bq_svls = bq['annual'] - svls['annual']
        savings_vs_bq_prov_ri = bq['annual'] - prov['ri_1yr_annual']

        return {
            'choice': choice,
            'confidence': confidence,
            'title': f'{"Redshift Serverless" if choice == "serverless" else "Redshift Provisioned (RI)"} Recommended',
            'reasons': reasons,
            'annual_savings_vs_bq': round(savings_vs_bq_svls if choice == 'serverless' else savings_vs_bq_prov_ri, 2),
            'workload_pattern': workload,
        }
