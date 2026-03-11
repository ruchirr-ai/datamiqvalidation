"""
Recommendation Engine for BigQuery to Redshift Migration

Analyzes BigQuery assessment data and generates:
1. Redshift configuration recommendations (Provisioned vs Serverless)
2. Distribution key and sort key recommendations per table
3. Query classification (Ad-hoc vs BI)
4. Architecture recommendations

Key BQ → Redshift mappings:
- BQ slots → Redshift vCPUs/RPUs (1 BQ slot ≈ 0.5 vCPU equivalent)
- BQ bytes_scanned → Redshift data scan patterns (affects sort key choices)
- BQ partitioning → Redshift sort keys
- BQ clustering → Redshift sort keys (compound)
- BQ slot_milliseconds → Redshift compute hours (for serverless RPU estimation)
"""

import logging
import math
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """
    Generates intelligent Redshift migration recommendations based on
    BigQuery assessment metadata including tables, columns, queries,
    and usage patterns.
    """

    # Redshift node types with specs
    NODE_TYPES = {
        'dc2.large': {
            'vcpu': 2, 'memory_gb': 15, 'storage_gb': 160,
            'storage_type': 'SSD', 'max_nodes': 32,
            'use_case': 'Small datasets (<160 GB) with fast SSD storage',
        },
        'dc2.8xlarge': {
            'vcpu': 32, 'memory_gb': 244, 'storage_gb': 2560,
            'storage_type': 'SSD', 'max_nodes': 128,
            'use_case': 'Large datasets needing fast local SSD',
        },
        'ra3.xlplus': {
            'vcpu': 4, 'memory_gb': 32, 'storage_gb': 32000,
            'storage_type': 'Managed Storage', 'max_nodes': 32,
            'use_case': 'Most workloads — separates compute and storage',
        },
        'ra3.4xlarge': {
            'vcpu': 12, 'memory_gb': 96, 'storage_gb': 128000,
            'storage_type': 'Managed Storage', 'max_nodes': 32,
            'use_case': 'Large workloads needing more compute',
        },
        'ra3.16xlarge': {
            'vcpu': 48, 'memory_gb': 384, 'storage_gb': 128000,
            'storage_type': 'Managed Storage', 'max_nodes': 128,
            'use_case': 'Very large enterprise workloads',
        },
    }

    def generate_recommendations(
        self,
        assessment: Dict,
        tables: List[Dict],
        columns: List[Dict],
        query_stats: List[Dict],
        datasets: List[Dict],
    ) -> Dict[str, Any]:
        """Generate all recommendations from assessment data."""
        total_size_gb = assessment.get('total_size_mb', 0) / 1024
        total_rows = sum(t.get('row_count', 0) for t in tables)
        total_tables = len(tables)

        # Compute workload metrics from BQ query stats
        workload = self._analyze_workload(query_stats)

        # 1. Query classification
        query_classification = self._classify_queries(query_stats)

        # 2. Redshift configuration recommendation
        config_recommendation = self._recommend_redshift_config(
            total_size_gb, total_rows, total_tables,
            query_stats, query_classification, workload
        )

        # 3. Distribution & sort key recommendations
        dist_sort_recommendations = self._recommend_dist_sort_keys(
            tables, columns, query_stats
        )

        # 4. Architecture recommendation
        architecture = self._recommend_architecture(query_classification, total_size_gb)

        return {
            'query_classification': query_classification,
            'config_recommendation': config_recommendation,
            'dist_sort_keys': dist_sort_recommendations,
            'architecture': architecture,
            'workload_metrics': workload,
        }

    # ------------------------------------------------------------------ #
    #  Workload Analysis (BQ → Redshift mapping)
    # ------------------------------------------------------------------ #
    def _analyze_workload(self, query_stats: List[Dict]) -> Dict:
        """
        Analyze BQ workload to derive Redshift-equivalent compute needs.

        BQ slot_milliseconds = total_slots_used × duration_ms for a query.
        This is CPU-time, NOT wall-clock time.

        Redshift Serverless bills: RPUs_allocated × wall_clock_seconds,
        with a 60-second minimum per warehouse activation.

        Conversion approach:
        1. Estimate per-query wall-clock duration from slot_ms and concurrency
        2. Apply 60-second minimum billing per activation window
        3. Convert BQ slots to RPUs (1 RPU ≈ 2 vCPUs ≈ 2 BQ slots)
        4. Account for query concurrency (overlapping queries share activation)
        """
        if not query_stats:
            return {
                'total_slot_ms': 0,
                'total_slot_hours': 0,
                'avg_slot_ms_per_query': 0,
                'total_bytes_scanned': 0,
                'total_tb_scanned': 0,
                'avg_bytes_per_query': 0,
                'query_count': 0,
                'estimated_daily_slot_hours': 0,
                'estimated_monthly_slot_hours': 0,
                'estimated_rpu_hours_monthly': 0,
                'estimated_peak_slots': 0,
                'query_time_span_days': 30,
            }

        total_slot_ms = sum(q.get('slot_milliseconds', 0) for q in query_stats)
        total_bytes = sum(q.get('bytes_scanned', 0) for q in query_stats)
        query_count = len(query_stats)

        total_slot_hours = total_slot_ms / (1000 * 3600)  # ms → hours
        total_tb_scanned = total_bytes / (1024 ** 4) if total_bytes else 0

        # Determine time span of captured queries
        exec_times = []
        for q in query_stats:
            et = q.get('execution_time')
            if et:
                if isinstance(et, str):
                    try:
                        et = datetime.fromisoformat(et.replace('Z', '+00:00'))
                    except Exception:
                        continue
                exec_times.append(et)

        if len(exec_times) >= 2:
            time_span = (max(exec_times) - min(exec_times)).total_seconds() / 86400
            time_span_days = max(time_span, 1)
        else:
            time_span_days = 30

        # Extrapolate to monthly
        daily_slot_hours = total_slot_hours / time_span_days
        monthly_slot_hours = daily_slot_hours * 30

        # --- Estimate per-query concurrency and wall-clock duration ---
        # BQ slot_ms = concurrent_slots × wall_clock_ms
        # We estimate avg concurrent slots per query, then derive wall-clock.
        slot_values = sorted(
            [q.get('slot_milliseconds', 0) for q in query_stats], reverse=True
        )

        # Estimate average concurrent slots per query.
        # For BQ on-demand, typical concurrency is 50-500 slots per query.
        # We use a heuristic: avg_slot_ms / assumed_avg_duration_ms
        # Conservative: assume avg query takes ~30 seconds wall-clock
        avg_slot_ms = total_slot_ms / query_count if query_count else 0
        # Estimate concurrent slots: slot_ms / 30000ms (30s assumed avg duration)
        # Clamp between 1 and 2000 (BQ on-demand max)
        estimated_avg_concurrent_slots = max(1, min(avg_slot_ms / 30000, 2000))

        # Peak concurrency: top 5% of queries
        top_5pct_count = max(1, int(len(slot_values) * 0.05))
        peak_slot_ms = sum(slot_values[:top_5pct_count]) / top_5pct_count if slot_values else 0
        estimated_peak_slots = max(1, peak_slot_ms / 30000)

        # --- Redshift Serverless RPU-hour estimation ---
        # Step 1: Estimate wall-clock seconds per query
        # wall_clock_ms = slot_ms / concurrent_slots
        avg_wall_clock_s = (avg_slot_ms / max(estimated_avg_concurrent_slots, 1)) / 1000

        # Step 2: Apply 60-second minimum billing per activation
        # Redshift bills min 60s per warehouse activation, not per query.
        # If queries overlap or arrive within 60s of each other, they share
        # the activation window. We estimate activation count from query spacing.
        daily_queries = query_count / max(time_span_days, 1)
        monthly_queries = daily_queries * 30

        # Estimate how many 60-second activation windows per day.
        # If queries are spread evenly: activations = daily_queries if gap > 60s,
        # else queries cluster into fewer windows.
        # Heuristic: assume queries arrive in bursts. Active hours per day ≈
        # min(daily_queries × max(wall_clock, 60) / 3600, 24)
        billed_seconds_per_query = max(avg_wall_clock_s, 60)  # 60s minimum
        # But overlapping queries share the window, so apply concurrency factor
        # Estimate: if N queries run per hour, and each takes T seconds,
        # concurrent queries = N × T / 3600. Activation windows = N / max(concurrent, 1)
        queries_per_hour = daily_queries / 24 if daily_queries > 0 else 0
        concurrent_queries = max(1, queries_per_hour * billed_seconds_per_query / 3600)
        # Effective activations per hour = queries_per_hour / concurrent_queries
        activations_per_hour = queries_per_hour / concurrent_queries
        # Each activation lasts at least 60s, or longer if queries take longer
        activation_duration_s = max(60, avg_wall_clock_s * concurrent_queries)
        # Total billed seconds per hour
        billed_seconds_per_hour = activations_per_hour * activation_duration_s
        # Cap at 3600 (can't bill more than 1 hour per hour)
        billed_seconds_per_hour = min(billed_seconds_per_hour, 3600)

        # Step 3: Convert BQ slots to RPUs for sizing
        # 1 RPU = 16 GB RAM + ~2 vCPUs. BQ slot ≈ 1 vCPU.
        # But Redshift allocates RPUs at base_rpu minimum (e.g., 32).
        # The RPU count during a query depends on complexity.
        # For estimation: RPUs needed ≈ max(base_rpu, peak_slots / 2)
        # We use a moderate estimate: the base RPU that would be configured.
        if monthly_slot_hours < 100:
            estimated_base_rpu = 8
        elif monthly_slot_hours < 500:
            estimated_base_rpu = 16
        elif monthly_slot_hours < 2000:
            estimated_base_rpu = 32
        else:
            estimated_base_rpu = 64

        # Step 4: Calculate monthly RPU-hours
        # RPU-hours = (billed_seconds_per_hour / 3600) × RPUs × active_hours_per_day × 30
        # Active hours per day: estimate from query distribution
        if daily_queries <= 0:
            active_hours_per_day = 0
        elif daily_queries < 10:
            active_hours_per_day = 1  # Sporadic
        elif daily_queries < 100:
            active_hours_per_day = min(daily_queries * billed_seconds_per_query / 3600, 8)
        else:
            active_hours_per_day = min(daily_queries * billed_seconds_per_query / 3600, 16)
        # Cap: can't exceed 24 hours
        active_hours_per_day = min(active_hours_per_day, 24)

        # RPU-hours/month = base_rpu × active_hours_per_day × 30
        # This represents the minimum billing (base RPU always allocated during active time)
        estimated_rpu_hours_monthly = estimated_base_rpu * active_hours_per_day * 30

        # Cross-check: RPU-hours should be at least proportional to BQ slot-hours
        # but accounting for the RPU/slot ratio and Redshift's different execution model.
        # Redshift typically needs 1.5-3x the wall-clock time of BQ for equivalent queries
        # (BQ has more aggressive parallelism with 100s-1000s of slots).
        # Minimum: slot_hours / slots_per_rpu × overhead_factor
        slot_based_rpu_hours = (monthly_slot_hours / 2) * 1.5  # 1.5x overhead
        estimated_rpu_hours_monthly = max(estimated_rpu_hours_monthly, slot_based_rpu_hours)

        # --- Per-query concurrent slot utilisation ---
        per_query_slots = []
        for q in query_stats:
            q_slot_ms = q.get('slot_milliseconds', 0)
            if q_slot_ms <= 0:
                continue
            q_runtime_ms = q.get('total_elapsed_time_ms') or q.get('runtime_ms', 0)
            if q_runtime_ms and q_runtime_ms > 0:
                slots_used = q_slot_ms / q_runtime_ms
            else:
                slots_used = q_slot_ms / 30000  # assume 30s
            per_query_slots.append(max(1, slots_used))

        if per_query_slots:
            max_concurrent_slots = round(max(per_query_slots), 1)
            min_concurrent_slots = round(min(per_query_slots), 1)
            avg_concurrent_slots = round(sum(per_query_slots) / len(per_query_slots), 1)
            sorted_slots = sorted(per_query_slots)
            median_concurrent_slots = round(sorted_slots[len(sorted_slots) // 2], 1)
        else:
            max_concurrent_slots = round(estimated_peak_slots, 1)
            min_concurrent_slots = 1.0
            avg_concurrent_slots = round(estimated_avg_concurrent_slots, 1)
            median_concurrent_slots = avg_concurrent_slots

        return {
            'total_slot_ms': total_slot_ms,
            'total_slot_hours': round(total_slot_hours, 2),
            'avg_slot_ms_per_query': round(avg_slot_ms, 0),
            'total_bytes_scanned': total_bytes,
            'total_tb_scanned': round(total_tb_scanned, 4),
            'avg_bytes_per_query': round(total_bytes / query_count, 0) if query_count else 0,
            'query_count': query_count,
            'estimated_daily_slot_hours': round(daily_slot_hours, 2),
            'estimated_monthly_slot_hours': round(monthly_slot_hours, 2),
            'estimated_rpu_hours_monthly': round(estimated_rpu_hours_monthly, 2),
            'estimated_peak_slots': round(estimated_peak_slots, 1),
            'query_time_span_days': round(time_span_days, 1),
            'avg_wall_clock_seconds': round(avg_wall_clock_s, 1),
            'estimated_base_rpu': estimated_base_rpu,
            'active_hours_per_day': round(active_hours_per_day, 1),
            'max_concurrent_slots': max_concurrent_slots,
            'min_concurrent_slots': min_concurrent_slots,
            'avg_concurrent_slots': avg_concurrent_slots,
            'median_concurrent_slots': median_concurrent_slots,
        }

    # ------------------------------------------------------------------ #
    #  Query Classification
    # ------------------------------------------------------------------ #
    def _classify_queries(self, query_stats: List[Dict]) -> Dict:
        """
        Classify queries as Ad-hoc vs BI/Scheduled.
        """
        total = len(query_stats)
        if total == 0:
            return {
                'total_queries': 0,
                'adhoc_count': 0, 'adhoc_pct': 0,
                'bi_count': 0, 'bi_pct': 0,
            }

        bi_keywords = [
            'dashboard', 'report', 'scheduled', 'looker', 'tableau',
            'metabase', 'datastudio', 'superset', 'grafana', 'powerbi',
        ]

        # Track query fingerprints for repetition detection
        query_fingerprints: Dict[str, int] = {}
        bi_flags = [False] * total

        for idx, q in enumerate(query_stats):
            text = (q.get('query_text') or '').lower()
            user = (q.get('user_email') or '').lower()

            fp = ''.join(text.split())[:100]
            query_fingerprints[fp] = query_fingerprints.get(fp, 0) + 1

            if any(kw in text for kw in bi_keywords):
                bi_flags[idx] = True
            if any(sa in user for sa in ['service', 'bot', 'scheduler', 'airflow', 'looker']):
                bi_flags[idx] = True

        # Repeated queries (>3 times) are likely BI
        repeated_fps = {fp for fp, cnt in query_fingerprints.items() if cnt >= 3}
        for idx, q in enumerate(query_stats):
            text = (q.get('query_text') or '').lower()
            fp = ''.join(text.split())[:100]
            if fp in repeated_fps:
                bi_flags[idx] = True

        bi_count = sum(bi_flags)
        adhoc_count = total - bi_count

        return {
            'total_queries': total,
            'adhoc_count': adhoc_count,
            'adhoc_pct': round(adhoc_count / total * 100, 1) if total else 0,
            'bi_count': bi_count,
            'bi_pct': round(bi_count / total * 100, 1) if total else 0,
        }

    # ------------------------------------------------------------------ #
    #  Redshift Configuration
    # ------------------------------------------------------------------ #
    def _recommend_redshift_config(
        self,
        total_size_gb: float,
        total_rows: int,
        total_tables: int,
        query_stats: List[Dict],
        query_classification: Dict,
        workload: Dict,
    ) -> Dict:
        """
        Recommend Redshift configuration using actual BQ workload metrics.
        """
        total_queries = query_classification.get('total_queries', 0)
        bi_pct = query_classification.get('bi_pct', 0)
        adhoc_pct = query_classification.get('adhoc_pct', 50)

        monthly_slot_hours = workload.get('estimated_monthly_slot_hours', 0)
        rpu_hours_monthly = workload.get('estimated_rpu_hours_monthly', 0)
        peak_slots = workload.get('estimated_peak_slots', 1)

        # --- Provisioned Cluster Recommendation ---
        provisioned = self._recommend_provisioned(
            total_size_gb, total_queries, monthly_slot_hours, peak_slots
        )

        # --- Serverless Recommendation ---
        serverless = self._recommend_serverless(
            total_size_gb, total_queries, monthly_slot_hours,
            rpu_hours_monthly, peak_slots
        )

        # --- Decision: Which is recommended? ---
        serverless_score = 0
        provisioned_score = 0

        # Data size factor
        if total_size_gb < 100:
            serverless_score += 3
        elif total_size_gb < 500:
            serverless_score += 2
            provisioned_score += 1
        else:
            provisioned_score += 3

        # Query pattern factor
        if adhoc_pct > 70:
            serverless_score += 3
        elif adhoc_pct > 40:
            serverless_score += 1
            provisioned_score += 1
        else:
            provisioned_score += 3

        # Compute intensity factor (based on actual slot hours)
        if monthly_slot_hours < 50:
            serverless_score += 3  # Light workload → serverless wins
        elif monthly_slot_hours < 500:
            serverless_score += 1
            provisioned_score += 1
        else:
            provisioned_score += 3  # Heavy workload → provisioned wins

        # Query volume factor
        daily_queries = total_queries / max(workload.get('query_time_span_days', 30), 1)
        if daily_queries < 50:
            serverless_score += 2
        elif daily_queries < 500:
            serverless_score += 1
            provisioned_score += 1
        else:
            provisioned_score += 2

        recommended = 'serverless' if serverless_score >= provisioned_score else 'provisioned'

        # Build reasoning
        reasons = []
        if recommended == 'serverless':
            if monthly_slot_hours < 50:
                reasons.append(f'Low compute usage ({monthly_slot_hours:.1f} slot-hours/month) — pay-per-use is more efficient')
            elif total_size_gb < 100:
                reasons.append(f'Small dataset ({total_size_gb:.2f} GB) — no need for dedicated cluster')
            if adhoc_pct > 50:
                reasons.append(f'{adhoc_pct}% ad-hoc queries — variable workload benefits from auto-scaling')
            if daily_queries < 50:
                reasons.append(f'Low query frequency (~{daily_queries:.0f}/day) — avoid paying for idle cluster')
            reasons.append('Serverless auto-scales RPUs based on workload complexity')
            reasons.append('No cluster management overhead')
        else:
            if monthly_slot_hours >= 500:
                reasons.append(f'High compute usage ({monthly_slot_hours:.1f} slot-hours/month) — dedicated resources are cost-effective')
            if total_size_gb >= 500:
                reasons.append(f'Large dataset ({total_size_gb:.2f} GB) — benefits from dedicated compute')
            if bi_pct > 50:
                reasons.append(f'{bi_pct}% BI/scheduled queries — consistent performance needed')
            reasons.append('Predictable costs with Reserved Instance pricing (up to 75% savings)')
            reasons.append('Full control over concurrency scaling and WLM queues')

        return {
            'recommended': recommended,
            'reasons': reasons,
            'provisioned': provisioned,
            'serverless': serverless,
            'decision_scores': {
                'serverless_score': serverless_score,
                'provisioned_score': provisioned_score,
            },
            'key_stats': {
                'total_data_volume_gb': round(total_size_gb, 2),
                'total_rows': total_rows,
                'total_tables': total_tables,
                'total_queries_analyzed': total_queries,
                'monthly_slot_hours': round(monthly_slot_hours, 2),
                'estimated_daily_queries': round(daily_queries, 1),
            },
        }

    def _recommend_provisioned(
        self, size_gb: float, query_count: int,
        monthly_slot_hours: float, peak_slots: float
    ) -> Dict:
        """
        Recommend provisioned cluster configuration.

        Node selection prioritises COMPUTE needs over raw data size.
        ra3 nodes use managed storage, so data volume only matters for
        dc2 (local SSD).  For ra3, we pick the smallest node type whose
        per-node vCPU count can serve the workload with a reasonable
        number of nodes (≤ 6 preferred, ≤ 32 hard max).

        Mapping: 1 BQ slot ≈ 0.5 Redshift vCPU (Redshift vCPUs are
        hyper-threaded Xeon cores, roughly 2× a BQ slot in throughput).
        """
        # --- Compute needs ---
        monthly_vcpu_hours = monthly_slot_hours * 0.5
        avg_vcpus_needed = monthly_vcpu_hours / 730 if monthly_vcpu_hours > 0 else 0
        peak_vcpus = peak_slots * 0.5

        # --- Determine the driving factor for node selection ---
        # For dc2: local SSD limits matter.  For ra3: only compute matters.
        # We try the smallest ra3 first and only up-size if we'd need too
        # many nodes (> 6 is expensive and adds coordination overhead).

        sizing_driver = 'compute'  # default

        if size_gb < 50 and avg_vcpus_needed < 2:
            node_type = 'dc2.large'
            min_nodes = 1
            sizing_driver = 'data_volume'
        elif size_gb < 160 and avg_vcpus_needed < 4:
            node_type = 'dc2.large'
            min_nodes = 2
            sizing_driver = 'data_volume'
        else:
            # ra3 territory — pick based on compute, NOT data size
            # (ra3 uses managed storage, data volume doesn't constrain node type)
            # Try ra3.xlplus first (4 vCPU / node)
            nodes_xlplus = max(2, math.ceil(avg_vcpus_needed / 4))
            peak_nodes_xlplus = max(2, math.ceil(peak_vcpus / 4))
            needed_xlplus = max(nodes_xlplus, peak_nodes_xlplus)

            # Try ra3.4xlarge (12 vCPU / node)
            nodes_4xl = max(2, math.ceil(avg_vcpus_needed / 12))
            peak_nodes_4xl = max(2, math.ceil(peak_vcpus / 12))
            needed_4xl = max(nodes_4xl, peak_nodes_4xl)

            # Try ra3.16xlarge (48 vCPU / node)
            nodes_16xl = max(2, math.ceil(avg_vcpus_needed / 48))
            peak_nodes_16xl = max(2, math.ceil(peak_vcpus / 48))
            needed_16xl = max(nodes_16xl, peak_nodes_16xl)

            # Pick the smallest node type that keeps node count ≤ 6
            # (fewer large nodes = less coordination overhead, but
            #  more small nodes = cheaper per-vCPU)
            if needed_xlplus <= 6:
                node_type = 'ra3.xlplus'
                min_nodes = 2
            elif needed_4xl <= 6:
                node_type = 'ra3.4xlarge'
                min_nodes = 2
            elif needed_16xl <= 6:
                node_type = 'ra3.16xlarge'
                min_nodes = 2
            else:
                # Very large workload — use ra3.16xlarge with many nodes
                node_type = 'ra3.16xlarge'
                min_nodes = 2

            # If peak concurrency drives the choice, note it
            if peak_vcpus > avg_vcpus_needed * 2:
                sizing_driver = 'peak_concurrency'

        specs = self.NODE_TYPES[node_type]
        vcpus_per_node = specs['vcpu']

        # Calculate nodes needed for compute
        nodes_for_compute = max(min_nodes, math.ceil(avg_vcpus_needed / vcpus_per_node))

        # Calculate nodes needed for storage (dc2 only)
        if 'dc2' in node_type:
            storage_per_node = specs['storage_gb']
            compressed_size = size_gb / 3  # ~3x compression
            nodes_for_storage = max(min_nodes, math.ceil(compressed_size / storage_per_node))
            if nodes_for_storage > nodes_for_compute:
                sizing_driver = 'data_volume'
        else:
            nodes_for_storage = min_nodes

        # Peak concurrency adjustment
        nodes_for_peak = max(min_nodes, math.ceil(peak_vcpus / vcpus_per_node))
        if nodes_for_peak > nodes_for_compute and nodes_for_peak > nodes_for_storage:
            sizing_driver = 'peak_concurrency'

        num_nodes = min(
            max(nodes_for_compute, nodes_for_storage, nodes_for_peak),
            specs['max_nodes']
        )

        # Build human-readable sizing rationale
        rationale_parts = []
        rationale_parts.append(
            f"Avg vCPUs needed: {avg_vcpus_needed:.1f} "
            f"(from {monthly_slot_hours:.0f} BQ slot-hrs/mo × 0.5 vCPU/slot ÷ 730 hrs)"
        )
        rationale_parts.append(
            f"Peak concurrent slots: {peak_slots:.0f} → {peak_vcpus:.0f} Redshift vCPUs"
        )
        rationale_parts.append(
            f"Selected {node_type} ({vcpus_per_node} vCPU/node) × {num_nodes} nodes "
            f"= {vcpus_per_node * num_nodes} total vCPUs"
        )
        if sizing_driver == 'peak_concurrency':
            rationale_parts.append(
                f"Node count driven by peak concurrency ({nodes_for_peak} nodes needed)"
            )
        elif sizing_driver == 'data_volume':
            rationale_parts.append(
                f"Node count driven by data volume ({size_gb:.1f} GB, ~{size_gb/3:.0f} GB compressed)"
            )
        else:
            rationale_parts.append(
                f"Node count driven by average compute needs ({nodes_for_compute} nodes needed)"
            )

        return {
            'node_type': node_type,
            'num_nodes': num_nodes,
            'storage_type': specs['storage_type'],
            'vcpu_total': specs['vcpu'] * num_nodes,
            'memory_gb_total': specs['memory_gb'] * num_nodes,
            'use_case': specs['use_case'],
            'sizing_basis': {
                'avg_vcpus_needed': round(avg_vcpus_needed, 2),
                'peak_vcpus': round(peak_vcpus, 1),
                'peak_slots': round(peak_slots, 1),
                'monthly_slot_hours': round(monthly_slot_hours, 1),
                'vcpus_per_node': vcpus_per_node,
                'nodes_for_compute': nodes_for_compute,
                'nodes_for_storage': nodes_for_storage,
                'nodes_for_peak': nodes_for_peak,
                'sizing_driver': sizing_driver,
            },
            'sizing_rationale': rationale_parts,
        }


    def _recommend_serverless(
        self, size_gb: float, query_count: int,
        monthly_slot_hours: float, rpu_hours_monthly: float,
        peak_slots: float
    ) -> Dict:
        """
        Recommend serverless configuration using actual BQ workload data.

        RPU sizing:
        - Base RPU: minimum RPUs always available (affects cold-start latency)
          AWS minimum is 4 RPU (since June 2025).
        - Max RPU: upper limit for auto-scaling (up to 1024)

        BQ slots → RPU conversion:
        - 1 RPU = 16 GB memory + ~2 vCPUs
        - 1 BQ slot ≈ 1 vCPU
        - So 1 RPU ≈ 2 BQ slots in vCPU terms
        - But Redshift bills wall-clock × RPUs, not CPU-time
        """
        # Peak BQ slots → peak RPU needed
        peak_rpu = max(4, math.ceil(peak_slots / 2 / 4) * 4)

        # Base RPU sizing based on workload intensity
        if monthly_slot_hours < 100:
            base_rpu = 8
        elif monthly_slot_hours < 500:
            base_rpu = max(8, min(peak_rpu, 16))
        elif monthly_slot_hours < 2000:
            base_rpu = max(16, min(peak_rpu, 32))
        else:
            base_rpu = max(32, min(peak_rpu, 64))

        # Max RPU: allow headroom for burst
        if monthly_slot_hours < 10:
            max_rpu = 16
        elif monthly_slot_hours < 100:
            max_rpu = 32
        else:
            max_rpu = max(base_rpu * 4, peak_rpu * 2, 64)
            max_rpu = min(max_rpu, 1024)
        max_rpu = math.ceil(max_rpu / 4) * 4

        # Actual RPU-hours from workload analysis (already accounts for
        # 60s minimum billing, concurrency, and overhead)
        actual_rpu_hours = rpu_hours_monthly

        max_possible_rpu_hours = base_rpu * 730
        utilization_pct = (actual_rpu_hours / max_possible_rpu_hours * 100) if max_possible_rpu_hours > 0 else 0
        utilization_pct = min(utilization_pct, 100)

        return {
            'base_rpu': base_rpu,
            'max_rpu': max_rpu,
            'est_rpu_hours_monthly': round(actual_rpu_hours, 1),
            'est_utilization_pct': round(utilization_pct, 1),
        }

    # ------------------------------------------------------------------ #
    #  Distribution & Sort Key Recommendations
    # ------------------------------------------------------------------ #
    def _recommend_dist_sort_keys(
        self,
        tables: List[Dict],
        columns: List[Dict],
        query_stats: List[Dict],
    ) -> List[Dict]:
        """
        Recommend DISTKEY and SORTKEY for each table.
        """
        cols_by_table: Dict[int, List[Dict]] = {}
        for c in columns:
            tid = c.get('table_id')
            if tid not in cols_by_table:
                cols_by_table[tid] = []
            cols_by_table[tid].append(c)

        column_usage = self._analyze_column_usage(query_stats)

        recommendations = []
        for table in tables:
            if table.get('table_type', '').upper() == 'VIEW':
                continue

            table_id = table.get('id')
            table_name = table.get('table_name', '')
            dataset = table.get('dataset_name', '')
            full_name = f"{dataset}.{table_name}"
            table_cols = cols_by_table.get(table_id, [])
            row_count = table.get('row_count', 0)
            partitioning = table.get('partitioning_columns', [])
            clustering = table.get('clustering_columns', [])

            distkey = self._pick_distkey(table_name, table_cols, column_usage, row_count)
            sortkey = self._pick_sortkey(table_name, table_cols, column_usage, partitioning, clustering)

            reasoning = []
            if distkey['key'] and distkey['key'] != 'EVEN':
                if distkey['key'] in (clustering or []):
                    reasoning.append(f"BQ clustering column '{distkey['key']}' maps well to DISTKEY")
                else:
                    reasoning.append(f"Column '{distkey['key']}' has high cardinality for even distribution")
            else:
                if row_count < 1_000_000:
                    reasoning.append(f"EVEN distribution — table has {row_count:,} rows (< 1M)")
                else:
                    reasoning.append("EVEN distribution — no clear DISTKEY candidate found")

            if sortkey['keys']:
                for sk in sortkey['keys']:
                    if sk in (partitioning or []):
                        reasoning.append(f"BQ partition column '{sk}' → ideal SORTKEY (range scans)")
                    elif sk in (clustering or []):
                        reasoning.append(f"BQ clustering column '{sk}' → SORTKEY (filter optimization)")
            else:
                reasoning.append("AUTO sortkey — Redshift will auto-optimize based on query patterns")

            recommendations.append({
                'table_name': full_name,
                'distkey': distkey['key'] or 'EVEN',
                'sortkey': ', '.join(sortkey['keys']) if sortkey['keys'] else 'AUTO',
                'reasoning': reasoning,
            })

        return recommendations

    def _pick_distkey(self, table_name: str, cols: List[Dict], usage: Dict, row_count: int) -> Dict:
        """Pick best distribution key for a table."""
        if row_count < 1_000_000:
            return {'key': 'EVEN', 'style': 'EVEN'}

        id_candidates = []
        for c in cols:
            name = c.get('column_name', '').lower()
            dtype = c.get('data_type', '').upper()
            if any(kw in name for kw in ['_id', 'id', '_key', 'key']) and dtype in ('INT64', 'INTEGER', 'STRING', 'BIGINT'):
                id_candidates.append(c)

        join_cols = usage.get('join_columns', {}).get(table_name.lower(), [])
        if join_cols:
            return {'key': join_cols[0], 'style': 'KEY'}

        if id_candidates:
            return {'key': id_candidates[0]['column_name'], 'style': 'KEY'}

        return {'key': 'EVEN', 'style': 'EVEN'}

    def _pick_sortkey(self, table_name: str, cols: List[Dict], usage: Dict, partitioning: List, clustering: List) -> Dict:
        """Pick best sort key(s) for a table."""
        keys = []

        if partitioning:
            keys.extend(partitioning)

        if clustering:
            for ck in clustering:
                if ck not in keys:
                    keys.append(ck)

        if keys:
            return {'keys': keys[:4], 'type': 'COMPOUND'}

        for c in cols:
            dtype = c.get('data_type', '').upper()
            name = c.get('column_name', '').lower()
            if dtype in ('TIMESTAMP', 'DATETIME', 'DATE') and any(kw in name for kw in ['created', 'updated', 'date', 'time', 'at']):
                keys.append(c['column_name'])
                break

        if keys:
            return {'keys': keys, 'type': 'COMPOUND'}

        return {'keys': [], 'type': 'AUTO'}

    def _analyze_column_usage(self, query_stats: List[Dict]) -> Dict:
        """Analyze query patterns to find frequently used columns."""
        join_columns: Dict[str, List[str]] = {}

        for q in query_stats:
            text = (q.get('query_text') or '').lower()
            if ' join ' in text and ' on ' in text:
                parts = text.split(' on ')
                for part in parts[1:]:
                    tokens = part.split('=')
                    for token in tokens:
                        token = token.strip().split()[0] if token.strip() else ''
                        if '.' in token:
                            tbl, col = token.rsplit('.', 1)
                            tbl = tbl.split('.')[-1]
                            if tbl not in join_columns:
                                join_columns[tbl] = []
                            if col not in join_columns[tbl]:
                                join_columns[tbl].append(col)

        return {'join_columns': join_columns}

    # ------------------------------------------------------------------ #
    #  Architecture Recommendation
    # ------------------------------------------------------------------ #
    def _recommend_architecture(self, query_classification: Dict, total_size_gb: float) -> Dict:
        """Recommend data storage and query architecture."""
        adhoc_pct = query_classification.get('adhoc_pct', 50)
        bi_pct = query_classification.get('bi_pct', 50)

        strategies = []

        if adhoc_pct > 70:
            strategies.append({
                'title': 'Data Storage & Query Strategy',
                'points': [
                    f'{adhoc_pct}% Ad-hoc queries — Load data to Amazon S3 and use Amazon Athena for exploratory analysis. Cost-effective querying without a running cluster.',
                    'Use AWS Glue Data Catalog for a unified metadata layer accessible by both Athena and Redshift.',
                    'Implement data partitioning in S3 to optimize Athena query performance and reduce costs.',
                ],
            })
        elif bi_pct > 70:
            strategies.append({
                'title': 'Data Storage & Query Strategy',
                'points': [
                    f'{bi_pct}% BI/Scheduled queries — Load all frequently queried data into Redshift for consistent, low-latency performance.',
                    'Use Redshift materialized views for complex aggregations used by BI tools.',
                    'Implement Redshift workload management (WLM) to prioritize BI queries.',
                ],
            })
        else:
            strategies.append({
                'title': 'Data Storage & Query Strategy',
                'points': [
                    'Mixed workload — Use Redshift for BI workloads and Redshift Spectrum for ad-hoc queries on S3 data.',
                    'Store hot/frequently accessed data in Redshift tables, archive cold data to S3.',
                    'Use Redshift Spectrum to query S3 data directly without loading.',
                ],
            })

        return {'strategies': strategies}
