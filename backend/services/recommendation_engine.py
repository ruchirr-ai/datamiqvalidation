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

    # Redshift node types with specs (official AWS docs, updated 2025)
    # slices_per_node: determines query parallelism within a node
    NODE_TYPES = {
        'dc2.large': {
            'vcpu': 2, 'memory_gb': 15, 'storage_gb': 160,
            'slices_per_node': 2,
            'storage_type': 'SSD', 'max_nodes': 32,
            'use_case': 'Small datasets (<160 GB) with fast SSD storage',
        },
        'dc2.8xlarge': {
            'vcpu': 32, 'memory_gb': 244, 'storage_gb': 2560,
            'slices_per_node': 16,
            'storage_type': 'SSD', 'max_nodes': 128,
            'use_case': 'Large datasets needing fast local SSD',
        },
        'ra3.xlplus': {
            'vcpu': 4, 'memory_gb': 32, 'storage_gb': 32000,
            'slices_per_node': 2,
            'storage_type': 'Managed Storage', 'max_nodes': 32,
            'use_case': 'Most workloads — separates compute and storage',
        },
        'ra3.4xlarge': {
            'vcpu': 12, 'memory_gb': 96, 'storage_gb': 128000,
            'slices_per_node': 4,
            'storage_type': 'Managed Storage', 'max_nodes': 32,
            'use_case': 'Large workloads needing more compute',
        },
        'ra3.16xlarge': {
            'vcpu': 48, 'memory_gb': 384, 'storage_gb': 128000,
            'slices_per_node': 16,
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

        avg_slot_ms = total_slot_ms / query_count if query_count else 0

        # --- Compute per-query concurrent slot utilisation early ---
        # so we can use actual data for peak estimation instead of heuristics.
        per_query_slots = []
        for q in query_stats:
            q_slot_ms = q.get('slot_milliseconds', 0)
            if q_slot_ms <= 0:
                continue
            # Try to get actual runtime from query_metadata first
            q_runtime_ms = q.get('total_elapsed_time_ms') or q.get('runtime_ms', 0)
            if not q_runtime_ms:
                meta = q.get('query_metadata') or {}
                if isinstance(meta, dict):
                    q_runtime_ms = meta.get('total_elapsed_time_ms', 0)
            if q_runtime_ms and q_runtime_ms > 0:
                slots_used = q_slot_ms / q_runtime_ms
            else:
                slots_used = q_slot_ms / 30000  # assume 30s
            per_query_slots.append(max(1, slots_used))

        # Estimate average concurrent slots per query
        if per_query_slots:
            estimated_avg_concurrent_slots = sum(per_query_slots) / len(per_query_slots)
        else:
            estimated_avg_concurrent_slots = max(1, min(avg_slot_ms / 30000, 2000))

        # Peak slot utilization using sweep-line algorithm for true overlap.
        # For each query, compute [start, end) interval and its concurrent slots.
        # The maximum running total = true peak slots at any point in time.
        from datetime import timedelta as _td
        events = []
        for q in query_stats:
            q_slot_ms = q.get('slot_milliseconds', 0)
            if q_slot_ms <= 0:
                continue
            et = q.get('execution_time')
            if et:
                if isinstance(et, str):
                    try:
                        et = datetime.fromisoformat(et.replace('Z', '+00:00'))
                    except Exception:
                        et = None
                if et:
                    q_runtime_ms = q.get('total_elapsed_time_ms') or q.get('runtime_ms', 0)
                    if not q_runtime_ms:
                        meta = q.get('query_metadata') or {}
                        if isinstance(meta, dict):
                            q_runtime_ms = meta.get('total_elapsed_time_ms', 0)
                    if q_runtime_ms and q_runtime_ms > 0:
                        q_slots = max(1, q_slot_ms / q_runtime_ms)
                        q_duration_ms = q_runtime_ms
                    else:
                        q_slots = max(1, q_slot_ms / 30000)
                        q_duration_ms = 30000
                    end_t = et + _td(milliseconds=q_duration_ms)
                    events.append((et, q_slots))
                    events.append((end_t, -q_slots))

        if events:
            events.sort(key=lambda e: (e[0], e[1]))
            running_slots = 0.0
            estimated_peak_slots = 0.0
            for _, delta in events:
                running_slots += delta
                if running_slots > estimated_peak_slots:
                    estimated_peak_slots = running_slots
        elif per_query_slots:
            estimated_peak_slots = max(per_query_slots)
        else:
            estimated_peak_slots = max(1, slot_values[0] / 30000) if slot_values else 1

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
        # Base RPU should handle the average concurrent slot usage.
        # Peak slots are handled by auto-scaling (up to max_rpu).
        # Use avg concurrent slots converted to RPUs (slots / 2).
        rpus_from_avg = max(8, math.ceil(estimated_avg_concurrent_slots / 2))
        # Round up to valid RPU values: 8, 16, 32, 48, 64, ...
        valid_rpus = [8, 16, 32, 48, 64, 96, 128, 192, 256, 512]
        estimated_base_rpu = 8
        for rpu in valid_rpus:
            if rpu >= rpus_from_avg:
                estimated_base_rpu = rpu
                break
        else:
            estimated_base_rpu = valid_rpus[-1]

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

        # --- Per-query concurrent slot stats (already computed above) ---
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

        Mapping methodology (BQ Slots → Redshift RA3):
        - 1 BQ slot = 1 GiB memory equivalent
        - Peak BQ slots determines the memory footprint needed
        - RA3 node selection based on memory:
            ra3.xlplus:   32 GiB/node → up to ~500 slots (16 nodes)
            ra3.4xlarge:  96 GiB/node → up to ~1,800 slots (19 nodes)
            ra3.16xlarge: 384 GiB/node → up to ~5,000 slots (13 nodes)

        Node specs (official AWS docs):
          ra3.xlplus:   4 vCPU, 32 GiB RAM, 2 slices/node, 2-32 nodes
          ra3.4xlarge:  12 vCPU, 96 GiB RAM, 4 slices/node, 2-32 nodes
          ra3.16xlarge: 48 vCPU, 384 GiB RAM, 16 slices/node, 2-128 nodes
        """
        # Memory needed = peak BQ slots × 1 GiB per slot
        memory_needed_gib = max(32, math.ceil(peak_slots))

        # Try each RA3 node type, prefer the smallest that keeps node count reasonable
        # ra3.xlplus (32 GiB/node): use for up to ~500 slots (16 nodes)
        # ra3.4xlarge (96 GiB/node): use for ~600-1,800 slots
        # ra3.16xlarge (384 GiB/node): use for ~2,000+ slots
        ra3_options = [
            ('ra3.xlplus', 32, 16),    # (type, mem_per_node, max_preferred_nodes)
            ('ra3.4xlarge', 96, 19),
            ('ra3.16xlarge', 384, 13),
        ]

        node_type = 'ra3.xlplus'
        num_nodes = 2

        for nt, mem_per_node, max_pref in ra3_options:
            nodes = max(2, math.ceil(memory_needed_gib / mem_per_node))
            if nodes <= max_pref:
                node_type = nt
                num_nodes = nodes
                break
        else:
            # Fallback: use ra3.16xlarge with as many nodes as needed
            node_type = 'ra3.16xlarge'
            num_nodes = max(2, math.ceil(memory_needed_gib / 384))

        specs = self.NODE_TYPES[node_type]
        num_nodes = min(num_nodes, specs['max_nodes'])

        # Build rationale
        rationale_parts = [
            f"Peak BQ slots: {peak_slots:.0f} → {memory_needed_gib} GiB memory needed "
            f"(1 GiB per BQ slot)",
            f"Selected {node_type} ({specs['memory_gb']} GiB/node) × {num_nodes} nodes "
            f"= {specs['memory_gb'] * num_nodes} GiB total RAM",
            f"Total slices: {specs['slices_per_node'] * num_nodes} "
            f"({specs['slices_per_node']} slices/node × {num_nodes} nodes)",
        ]

        return {
            'node_type': node_type,
            'num_nodes': num_nodes,
            'storage_type': specs['storage_type'],
            'vcpu_total': specs['vcpu'] * num_nodes,
            'memory_gb_total': specs['memory_gb'] * num_nodes,
            'use_case': specs['use_case'],
            'sizing_basis': {
                'peak_slots': round(peak_slots, 1),
                'memory_needed_gib': memory_needed_gib,
                'monthly_slot_hours': round(monthly_slot_hours, 1),
                'slices_per_node': specs['slices_per_node'],
                'nodes_for_compute': num_nodes,
                'nodes_for_storage': 2,
                'nodes_for_peak': num_nodes,
                'sizing_driver': 'memory',
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

        Mapping: 1 BQ slot = 1 GiB memory, 1 RPU = 16 GiB memory.
        So RPU needed = ceil(peak_slots / 16), rounded up to nearest 8.

        Base RPU: minimum RPUs always available.
        Max RPU: upper limit for auto-scaling (up to 1024).
        """
        # Peak BQ slots → memory → RPU
        # 1 BQ slot = 1 GiB, 1 RPU = 16 GiB
        memory_needed_gib = max(16, math.ceil(peak_slots))
        raw_rpu = math.ceil(memory_needed_gib / 16)
        # Round up to nearest 8 (valid RPU increments)
        base_rpu = max(8, math.ceil(raw_rpu / 8) * 8)

        # Max RPU: allow headroom for burst (2x base, min 32)
        max_rpu = max(base_rpu * 2, 32)
        max_rpu = min(max_rpu, 1024)
        max_rpu = math.ceil(max_rpu / 8) * 8

        # Actual RPU-hours from workload analysis
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
