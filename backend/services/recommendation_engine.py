"""
Recommendation Engine for BigQuery to Redshift Migration

Analyzes BigQuery assessment data and generates:
1. Redshift configuration recommendations (Provisioned vs Serverless)
2. Distribution key and sort key recommendations per table
3. Query classification (Ad-hoc vs BI)
4. Architecture recommendations

Key BQ â†’ Redshift mappings:
- BQ slots â†’ Redshift vCPUs/RPUs (1 BQ slot â‰ˆ 0.5 vCPU equivalent)
- BQ bytes_scanned â†’ Redshift data scan patterns (affects sort key choices)
- BQ partitioning â†’ Redshift sort keys
- BQ clustering â†’ Redshift sort keys (compound)
- BQ slot_milliseconds â†’ Redshift compute hours (for serverless RPU estimation)
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
        'ra3.large': {
            'vcpu': 2, 'memory_gb': 16, 'storage_gb': 8000,
            'slices_per_node': 2,
            'storage_type': 'Managed Storage', 'max_nodes': 16,
            'use_case': 'Small workloads with managed storage',
        },
        'ra3.xlplus': {
            'vcpu': 4, 'memory_gb': 32, 'storage_gb': 32000,
            'slices_per_node': 2,
            'storage_type': 'Managed Storage', 'max_nodes': 32,
            'use_case': 'Most workloads â€” separates compute and storage',
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
        self._workload_cache = workload  # Cache for architecture recommendation

        # Override peak/avg slots with JOBS_TIMELINE data if available
        assessment_data = assessment.get('assessment_data') or {}
        slot_timeline = assessment_data.get('slot_timeline') or {}
        if slot_timeline.get('peak_concurrent_slots', 0) > 0:
            workload['estimated_peak_slots'] = slot_timeline['peak_concurrent_slots']
            workload['avg_concurrent_slots'] = slot_timeline.get('avg_concurrent_slots', workload.get('avg_concurrent_slots', 0))
            workload['p50_concurrent_slots'] = slot_timeline.get('p50_concurrent_slots', 0)
            workload['p90_concurrent_slots'] = slot_timeline.get('p90_concurrent_slots', 0)
            workload['p95_concurrent_slots'] = slot_timeline.get('p95_concurrent_slots', 0)
            workload['p99_concurrent_slots'] = slot_timeline.get('p99_concurrent_slots', 0)
            workload['slot_timeline_source'] = 'JOBS_TIMELINE_BY_PROJECT'

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
        architecture = self._recommend_architecture(query_classification, total_size_gb, tables, query_stats)

        return {
            'query_classification': query_classification,
            'config_recommendation': config_recommendation,
            'dist_sort_keys': dist_sort_recommendations,
            'architecture': architecture,
            'workload_metrics': workload,
        }

    # ------------------------------------------------------------------ #
    #  Workload Analysis (BQ â†’ Redshift mapping)
    # ------------------------------------------------------------------ #
    def _analyze_workload(self, query_stats: List[Dict]) -> Dict:
        """
        Analyze BQ workload to derive Redshift-equivalent compute needs.

        BQ slot_milliseconds = total_slots_used Ã— duration_ms for a query.
        This is CPU-time, NOT wall-clock time.

        Redshift Serverless bills: RPUs_allocated Ã— wall_clock_seconds,
        with a 60-second minimum per warehouse activation.

        Conversion approach:
        1. Estimate per-query wall-clock duration from slot_ms and concurrency
        2. Apply 60-second minimum billing per activation window
        3. Convert BQ slots to RPUs (1 RPU â‰ˆ 2 vCPUs â‰ˆ 2 BQ slots)
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

        total_slot_hours = total_slot_ms / (1000 * 3600)  # ms â†’ hours
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
        # BQ slot_ms = concurrent_slots Ã— wall_clock_ms
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
        # Heuristic: assume queries arrive in bursts. Active hours per day â‰ˆ
        # min(daily_queries Ã— max(wall_clock, 60) / 3600, 24)
        billed_seconds_per_query = max(avg_wall_clock_s, 60)  # 60s minimum
        # But overlapping queries share the window, so apply concurrency factor
        # Estimate: if N queries run per hour, and each takes T seconds,
        # concurrent queries = N Ã— T / 3600. Activation windows = N / max(concurrent, 1)
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
        # 1 RPU = 16 GiB memory â‰ˆ 2 BQ slots. So RPU needed = avg_slots / 2.
        # Valid RPU values: 4, 8, 16, 24, 32, ..., 1024 (4 is minimum, then multiples of 8).
        rpus_from_avg = max(1, math.ceil(estimated_avg_concurrent_slots / 2))
        if rpus_from_avg <= 4:
            estimated_base_rpu = 4
        else:
            estimated_base_rpu = math.floor(rpus_from_avg / 8) * 8

        # Step 4: Calculate monthly RPU-hours
        # active_hours_per_day = total_slot_hours / (time_span_days Ã— 24)
        # RPU-hours/month = base_rpu Ã— active_hours_per_day Ã— 30
        active_hours_per_day = total_slot_hours / (time_span_days * 24) if time_span_days > 0 else 0
        active_hours_per_day = min(active_hours_per_day, 24)

        estimated_rpu_hours_monthly = estimated_base_rpu * active_hours_per_day * 30

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
        Classify queries as Ad-hoc vs BI/Scheduled, and compute read/write split + cache hit ratio.
        """
        total = len(query_stats)
        if total == 0:
            return {
                'total_queries': 0,
                'adhoc_count': 0, 'adhoc_pct': 0,
                'bi_count': 0, 'bi_pct': 0,
                'read_count': 0, 'write_count': 0,
                'read_pct': 0, 'write_pct': 0,
                'cache_hit_ratio': 0, 'cache_hits': 0, 'select_queries': 0,
            }

        WRITE_TYPES = {'INSERT', 'UPDATE', 'DELETE', 'MERGE', 'CREATE_TABLE_AS_SELECT',
                       'CREATE_TABLE', 'DROP_TABLE', 'ALTER_TABLE', 'TRUNCATE_TABLE',
                       'CREATE_VIEW', 'DROP_VIEW', 'CREATE_FUNCTION', 'DROP_FUNCTION',
                       'CREATE_PROCEDURE', 'DROP_PROCEDURE', 'CREATE_MODEL', 'EXPORT_DATA'}

        bi_keywords = [
            'dashboard', 'report', 'scheduled', 'looker', 'tableau',
            'metabase', 'datastudio', 'superset', 'grafana', 'powerbi',
        ]

        # Track query fingerprints for repetition detection
        query_fingerprints: Dict[str, int] = {}
        bi_flags = [False] * total
        read_count = 0
        write_count = 0
        select_queries = 0
        cache_hits = 0

        for idx, q in enumerate(query_stats):
            text = (q.get('query_text') or '').lower()
            user = (q.get('user_email') or '').lower()
            meta = q.get('query_metadata') or {}
            stmt_type = (meta.get('statement_type') or '').upper() if isinstance(meta, dict) else ''

            fp = ''.join(text.split())[:100]
            query_fingerprints[fp] = query_fingerprints.get(fp, 0) + 1

            if any(kw in text for kw in bi_keywords):
                bi_flags[idx] = True
            if any(sa in user for sa in ['service', 'bot', 'scheduler', 'airflow', 'looker']):
                bi_flags[idx] = True

            # Read/write classification using statement_type
            if stmt_type and stmt_type != 'UNKNOWN':
                if stmt_type in WRITE_TYPES:
                    write_count += 1
                else:
                    read_count += 1
                if stmt_type == 'SELECT':
                    select_queries += 1
                    if q.get('cache_hit') is True:
                        cache_hits += 1
            else:
                # Fallback to regex
                if text.strip():
                    import re
                    if re.match(r'^\s*(insert|update|delete|merge|create|drop|alter|truncate)', text):
                        write_count += 1
                    else:
                        read_count += 1
                        select_queries += 1
                        if q.get('cache_hit') is True:
                            cache_hits += 1
                else:
                    read_count += 1

        # Repeated queries (>3 times) are likely BI
        repeated_fps = {fp for fp, cnt in query_fingerprints.items() if cnt >= 3}
        for idx, q in enumerate(query_stats):
            text = (q.get('query_text') or '').lower()
            fp = ''.join(text.split())[:100]
            if fp in repeated_fps:
                bi_flags[idx] = True

        bi_count = sum(bi_flags)
        adhoc_count = total - bi_count
        cache_hit_ratio = round(cache_hits / select_queries * 100, 1) if select_queries > 0 else 0

        return {
            'total_queries': total,
            'adhoc_count': adhoc_count,
            'adhoc_pct': round(adhoc_count / total * 100, 1) if total else 0,
            'bi_count': bi_count,
            'bi_pct': round(bi_count / total * 100, 1) if total else 0,
            'read_count': read_count,
            'write_count': write_count,
            'read_pct': round(read_count / total * 100, 1) if total else 0,
            'write_pct': round(write_count / total * 100, 1) if total else 0,
            'cache_hit_ratio': cache_hit_ratio,
            'cache_hits': cache_hits,
            'select_queries': select_queries,
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

        avg_slots = workload.get('avg_concurrent_slots', peak_slots)

        # --- Provisioned Cluster Recommendation ---
        provisioned = self._recommend_provisioned(
            total_size_gb, total_queries, monthly_slot_hours, peak_slots, avg_slots
        )

        # --- Serverless Recommendation ---
        serverless = self._recommend_serverless(
            total_size_gb, total_queries, monthly_slot_hours,
            rpu_hours_monthly, peak_slots, avg_slots
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
            serverless_score += 3  # Light workload â†’ serverless wins
        elif monthly_slot_hours < 500:
            serverless_score += 1
            provisioned_score += 1
        else:
            provisioned_score += 3  # Heavy workload â†’ provisioned wins

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
                reasons.append(f'Low compute usage ({monthly_slot_hours:.1f} slot-hours/month) â€” pay-per-use is more efficient')
            elif total_size_gb < 100:
                reasons.append(f'Small dataset ({total_size_gb:.2f} GB) â€” no need for dedicated cluster')
            if adhoc_pct > 50:
                reasons.append(f'{adhoc_pct}% ad-hoc queries â€” variable workload benefits from auto-scaling')
            if daily_queries < 50:
                reasons.append(f'Low query frequency (~{daily_queries:.0f}/day) â€” avoid paying for idle cluster')
            reasons.append('Serverless auto-scales RPUs based on workload complexity')
            reasons.append('No cluster management overhead')
        else:
            if monthly_slot_hours >= 500:
                reasons.append(f'High compute usage ({monthly_slot_hours:.1f} slot-hours/month) â€” dedicated resources are cost-effective')
            if total_size_gb >= 500:
                reasons.append(f'Large dataset ({total_size_gb:.2f} GB) â€” benefits from dedicated compute')
            if bi_pct > 50:
                reasons.append(f'{bi_pct}% BI/scheduled queries â€” consistent performance needed')
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
        monthly_slot_hours: float, peak_slots: float,
        avg_slots: float = 0
    ) -> Dict:
        """
        Recommend provisioned cluster configuration.

        Sizing approach:
        - Evaluate both horizontal (more small nodes) and vertical (fewer large nodes) scaling
        - Consider peak workload for sizing, not just average
        - Use concurrency scaling when peak >> base capacity
        - Optimize for cost across different node type combinations
        - Mapping: 1 BQ slot â‰ˆ 1 GiB memory equivalent.

        Node specs (official AWS docs):
          ra3.xlplus:   4 vCPU, 32 GiB RAM, 2 slices/node, 2-32 nodes
          ra3.4xlarge:  12 vCPU, 96 GiB RAM, 4 slices/node, 2-32 nodes
          ra3.16xlarge: 48 vCPU, 384 GiB RAM, 16 slices/node, 2-128 nodes
        """
        # Determine sizing strategy based on peak-to-avg ratio
        base_slots = avg_slots if avg_slots > 0 else peak_slots
        peak_to_avg_ratio = peak_slots / max(avg_slots, 1) if avg_slots > 0 else 1
        
        # If peak is much higher than avg (>3x), size for a middle ground with concurrency scaling
        # Otherwise, size closer to peak for consistent performance
        if peak_to_avg_ratio > 3:
            # High variance workload - size for avg (1 BQ slot â‰ˆ 1 GiB), concurrency scaling handles peaks
            target_memory_gib = max(32, math.ceil(avg_slots))
            use_concurrency_scaling = True
        else:
            # Steady workload - size for peak with some headroom
            target_memory_gib = max(32, math.ceil(peak_slots * 0.7))
            use_concurrency_scaling = peak_slots > (target_memory_gib * 1.3)
        
        # Ensure minimum for data volume
        # For RA3 nodes, storage is managed (decoupled from compute), so storage
        # rarely drives node count. Use actual storage capacity per node type.
        # For DC2 nodes, storage is local SSD, so it can drive node count.
        
        # Evaluate all viable node type combinations
        # Format: (node_type, memory_per_node, hourly_cost_per_node, max_recommended_nodes)
        ra3_options = [
            ('ra3.large', 16, 0.543, 16),
            ('ra3.xlplus', 32, 1.086, 32),
            ('ra3.4xlarge', 96, 3.26, 32),
            ('ra3.16xlarge', 384, 13.04, 128),
        ]
        
        best_option = None
        best_cost = float('inf')
        
        for node_type, mem_per_node, hourly_cost, max_nodes in ra3_options:
            # Minimum nodes: ra3.large and ra3.xlplus support single-node, others need 2
            min_nodes = 1 if node_type in ('ra3.large', 'ra3.xlplus') else 2
            
            # Calculate nodes needed for compute
            nodes_for_compute = max(min_nodes, math.ceil(target_memory_gib / mem_per_node))
            
            # Calculate nodes needed for storage using actual node storage capacity
            node_storage_gb = self.NODE_TYPES[node_type]['storage_gb']
            nodes_for_storage = max(min_nodes, math.ceil(size_gb / node_storage_gb)) if node_storage_gb > 0 else min_nodes
            
            nodes_needed = max(nodes_for_compute, nodes_for_storage)
            
            # Skip if exceeds max nodes for this type
            if nodes_needed > max_nodes:
                continue
            
            # Calculate monthly cost
            monthly_cost = nodes_needed * hourly_cost * 730
            total_memory = nodes_needed * mem_per_node
            specs = self.NODE_TYPES[node_type]
            total_slices = nodes_needed * specs['slices_per_node']
            
            # Prefer this option if:
            # 1. It's cheaper, OR
            # 2. Same cost but better performance (more slices for parallelism)
            if monthly_cost < best_cost or (monthly_cost == best_cost and best_option and total_slices > best_option['total_slices']):
                best_cost = monthly_cost
                best_option = {
                    'node_type': node_type,
                    'num_nodes': nodes_needed,
                    'nodes_for_compute': nodes_for_compute,
                    'nodes_for_storage': nodes_for_storage,
                    'total_memory': total_memory,
                    'total_slices': total_slices,
                    'monthly_cost': monthly_cost,
                    'specs': specs,
                }
        
        # Use best option found
        if not best_option:
            # Fallback to 16xlarge if nothing fits
            node_type = 'ra3.16xlarge'
            num_nodes = max(2, math.ceil(target_memory_gib / 384))
            specs = self.NODE_TYPES[node_type]
        else:
            node_type = best_option['node_type']
            num_nodes = best_option['num_nodes']
            specs = best_option['specs']
        
        num_nodes = min(num_nodes, specs['max_nodes'])
        total_memory_gib = specs['memory_gb'] * num_nodes
        peak_to_base_ratio = round(peak_slots / max(total_memory_gib, 1), 1)
        
        # Build rationale
        rationale_parts = [
            f"Avg BQ slots: {avg_slots:.0f}, Peak BQ slots: {peak_slots:.0f}",
        ]
        
        if peak_to_avg_ratio > 3:
            rationale_parts.append(
                f"High variance workload (peak is {peak_to_avg_ratio:.1f}Ã— avg) â€” "
                f"base cluster sized for sustained load with concurrency scaling for bursts"
            )
        else:
            rationale_parts.append(
                f"Steady workload â€” cluster sized to handle {int(total_memory_gib * 0.7)}-{total_memory_gib} concurrent slots"
            )
        
        rationale_parts.extend([
            f"Selected {node_type} ({specs['memory_gb']} GiB/node) Ã— {num_nodes} nodes "
            f"= {total_memory_gib} GiB total RAM",
            f"Total slices: {specs['slices_per_node'] * num_nodes} "
            f"({specs['slices_per_node']} slices/node Ã— {num_nodes} nodes)",
        ])
        
        if use_concurrency_scaling:
            rationale_parts.append(
                f"Concurrency scaling enabled: peak ({peak_slots:.0f} slots) is "
                f"{peak_to_base_ratio}Ã— base capacity â€” burst traffic handled automatically"
            )
        
        return {
            'node_type': node_type,
            'num_nodes': num_nodes,
            'storage_type': specs['storage_type'],
            'vcpu_total': specs['vcpu'] * num_nodes,
            'memory_gb_total': total_memory_gib,
            'use_case': specs['use_case'],
            'concurrency_scaling': use_concurrency_scaling,
            'sizing_basis': {
                'avg_slots': round(avg_slots, 1),
                'peak_slots': round(peak_slots, 1),
                'base_memory_gib': target_memory_gib,
                'monthly_slot_hours': round(monthly_slot_hours, 1),
                'slices_per_node': specs['slices_per_node'],
                'nodes_for_compute': best_option['nodes_for_compute'] if best_option else num_nodes,
                'nodes_for_storage': best_option['nodes_for_storage'] if best_option else 2,
                'peak_to_base_ratio': peak_to_base_ratio,
                'peak_to_avg_ratio': round(peak_to_avg_ratio, 1),
                'sizing_driver': 'cost_optimized_for_peak' if peak_to_avg_ratio <= 3 else 'sustained_with_bursts',
            },
            'sizing_rationale': rationale_parts,
        }



    def _recommend_serverless(
        self, size_gb: float, query_count: int,
        monthly_slot_hours: float, rpu_hours_monthly: float,
        peak_slots: float, avg_slots: float = 0
    ) -> Dict:
        """
        Recommend serverless configuration using actual BQ workload data.

        Mapping: 1 BQ slot â‰ˆ 1 GiB memory, 1 RPU â‰ˆ 2 BQ slots.
        Base RPU = floor(avg_slots / 2) rounded down to nearest 8.
        Max RPU = based on peak_slots for auto-scaling headroom.
        """
        # Base RPU from avg slots (not peak) â€” same logic as _analyze_workload
        # 1 RPU â‰ˆ 2 BQ slots â†’ avg_slots / 2 = RPUs needed
        # Valid RPU values: 4, 8, 16, 24, 32, ..., 1024 (4 is minimum, then multiples of 8).
        base_avg = avg_slots if avg_slots > 0 else peak_slots
        rpus_from_avg = max(1, math.ceil(base_avg / 2))
        if rpus_from_avg <= 4:
            base_rpu = 4
        else:
            base_rpu = math.floor(rpus_from_avg / 8) * 8

        # Max RPU from peak slots for auto-scaling headroom
        rpus_from_peak = max(1, math.ceil(peak_slots / 2))
        max_rpu = max(base_rpu, math.ceil(rpus_from_peak / 8) * 8)
        max_rpu = min(max_rpu, 1024)

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
                    reasoning.append(f"EVEN distribution â€” table has {row_count:,} rows (< 1M)")
                else:
                    reasoning.append("EVEN distribution â€” no clear DISTKEY candidate found")

            if sortkey['keys']:
                for sk in sortkey['keys']:
                    if sk in (partitioning or []):
                        reasoning.append(f"BQ partition column '{sk}' â†’ ideal SORTKEY (range scans)")
                    elif sk in (clustering or []):
                        reasoning.append(f"BQ clustering column '{sk}' â†’ SORTKEY (filter optimization)")
            else:
                reasoning.append("AUTO sortkey â€” Redshift will auto-optimize based on query patterns")

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


    # ================================================================== #
    #  ARCHITECTURE RECOMMENDATION FRAMEWORK
    #  Metadata → Metrics → Classification → Scoring → Overrides → Output
    # ================================================================== #

    def _compute_decision_metrics(self, tables: List[Dict], query_stats: List[Dict],
                                   query_classification: Dict, workload: Dict) -> Dict:
        """Compute all decision metrics from assessment data."""
        import re
        from datetime import datetime
        total_queries = query_classification.get('total_queries', 0) or 1
        bi_pct = query_classification.get('bi_pct', 0)
        adhoc_pct = query_classification.get('adhoc_pct', 0)
        write_pct = query_classification.get('write_pct', 0)
        cache_ratio = query_classification.get('cache_hit_ratio', 0)
        total_size_gb = sum(t.get('size_mb', 0) for t in tables) / 1024

        # Table access profiling
        table_access = {}
        for q in query_stats:
            meta = q.get('query_metadata', {}) or {}
            ec = meta.get('execution_count', 1) or 1
            slot_ms = q.get('slot_milliseconds', 0) or 0
            bs = q.get('bytes_scanned', 0) or 0
            qt = (q.get('query_text') or '').upper()
            et = q.get('execution_time')
            is_w = any(k in qt for k in ['INSERT','UPDATE','DELETE','MERGE','CREATE TABLE','TRUNCATE'])
            for ref in (q.get('referenced_tables') or []):
                keys = [ref]
                parts = ref.split('.')
                if len(parts) >= 2: keys += [parts[-1], f'{parts[-2]}.{parts[-1]}']
                for key in keys:
                    ta = table_access.setdefault(key, {'qc':0,'ec':0,'bytes':0,'slot':0,'writes':0,'reads':0,'scans':0})
                    ta['qc'] += 1; ta['ec'] += ec; ta['bytes'] += bs; ta['slot'] += slot_ms
                    if is_w: ta['writes'] += 1
                    else: ta['reads'] += 1
                    if bs > 1e9: ta['scans'] += 1

        # Hot/warm/cold classification
        has_refs = any(v.get('ec', 0) > 0 for v in table_access.values())
        hot, warm, cold = [], [], []
        hot_gb = warm_gb = cold_gb = 0.0
        wh_tables = []
        now = datetime.utcnow()
        for t in tables:
            tn = t.get('table_name', '')
            fn = f"{t.get('dataset_name','')}.{tn}" if t.get('dataset_name') else tn
            a = table_access.get(tn) or table_access.get(fn) or {}
            sm = t.get('size_mb', 0)
            if has_refs:
                if a.get('ec', 0) >= 10: hot.append(tn); hot_gb += sm/1024
                elif a.get('ec', 0) >= 1: warm.append(tn); warm_gb += sm/1024
                else: cold.append(tn); cold_gb += sm/1024
            else:
                rc = t.get('row_count', 0)
                if rc > 100000: hot.append(tn); hot_gb += sm/1024
                elif rc > 1000 or sm > 10: warm.append(tn); warm_gb += sm/1024
                else: cold.append(tn); cold_gb += sm/1024
            if a.get('writes', 0) > a.get('reads', 0): wh_tables.append(tn)
        tt = max(len(tables), 1)
        hot_pct = round(len(hot)/tt*100, 1)
        cold_pct = round(len(cold)/tt*100, 1)

        # Join complexity
        total_joins = 0; q_with_joins = 0; scan_heavy = 0
        for q in query_stats:
            qt = (q.get('query_text') or '').upper()
            jc = len(re.findall(r'\bJOIN\b', qt))
            total_joins += jc
            if jc > 0: q_with_joins += 1
            if (q.get('bytes_scanned', 0) or 0) > 1e9: scan_heavy += 1
        avg_joins = round(total_joins / total_queries, 1) if total_queries else 0
        # ETL detection
        etl_count = sum(1 for q in query_stats if any(k in (q.get('query_text') or '').upper() for k in ['CREATE TABLE','INSERT INTO','MERGE','CTAS','CREATE OR REPLACE']))
        etl_pct = round(etl_count / total_queries * 100, 1) if total_queries else 0
        # User distribution
        users = set(q.get('user_email','') for q in query_stats if q.get('user_email'))
        user_tables = {}
        for q in query_stats:
            u = q.get('user_email','')
            for ref in (q.get('referenced_tables') or []):
                s = ref.split('.')[-1] if '.' in ref else ref
                user_tables.setdefault(s, set()).add(u) if u else None
        shared = sum(1 for v in user_tables.values() if len(v) > 1)
        # Top table concentration
        tqc = {}
        for q in query_stats:
            for ref in (q.get('referenced_tables') or []):
                s = ref.split('.')[-1] if '.' in ref else ref
                tqc[s] = tqc.get(s, 0) + 1
        sc = sorted(tqc.values(), reverse=True)
        top10_pct = round(sum(sc[:10]) / (sum(sc) or 1) * 100, 1) if sc else 0
        # Concurrency
        peak = round(workload.get('estimated_peak_slots', 0), 1)
        avg_c = round(workload.get('avg_concurrent_slots', 0), 1)

        return {
            'bi_pct': bi_pct, 'adhoc_pct': adhoc_pct, 'write_pct': write_pct,
            'etl_pct': etl_pct, 'etl_count': etl_count, 'cache_ratio': cache_ratio,
            'total_size_gb': total_size_gb, 'total_tables': len(tables), 'total_queries': total_queries,
            'hot_pct': hot_pct, 'cold_pct': cold_pct,
            'hot_size_gb': round(hot_gb, 2), 'cold_size_gb': round(cold_gb, 2),
            'hot_count': len(hot), 'warm_count': len(warm), 'cold_count': len(cold),
            'write_heavy_count': len(wh_tables),
            'avg_joins': avg_joins, 'queries_with_joins': q_with_joins, 'scan_heavy': scan_heavy,
            'peak_concurrent': peak, 'avg_concurrent': avg_c,
            'unique_users': len(users), 'shared_tables': shared, 'top10_pct': top10_pct,
        }

    # ------------------------------------------------------------------ #
    #  Step 2: Score Architectures
    # ------------------------------------------------------------------ #
    def _score_architectures(self, m: Dict) -> List[Dict]:
        """Score each architecture using weighted metrics. m = decision metrics."""
        archs = []

        # --- 1. Redshift ---
        s = 0
        s += min(m['bi_pct'] * 0.25, 25)
        s += min(m['hot_pct'] * 0.20, 20)
        s += min(m['avg_joins'] * 5, 15)
        s += min(m['peak_concurrent'] * 0.15, 15) if m['peak_concurrent'] > 10 else 5
        s += 10 if m['total_size_gb'] < 500 else 0
        s += 5 if m['top10_pct'] > 80 else 0
        s -= 10 if m['cold_pct'] > 60 else 0
        # Provisioned vs Serverless decision
        # Provisioned: stable predictable workload, high concurrency, cost-effective at scale
        # Serverless: spiky/unpredictable, low admin overhead, auto-scaling
        prefer_provisioned = (
            m['bi_pct'] > 60 or  # Stable BI workload
            m['peak_concurrent'] > 50 or  # High concurrency
            m['total_size_gb'] > 200 or  # Large dataset
            m['total_queries'] > 5000  # High query volume
        )
        if prefer_provisioned:
            deploy_mode = 'Provisioned'
            deploy_reason = 'Stable workload pattern with predictable query volume — provisioned offers better cost efficiency and consistent performance.'
            # Use the actual provisioned recommendation engine for node config
            workload = getattr(self, '_workload_cache', {})
            prov = self._recommend_provisioned(
                m['total_size_gb'],
                m['total_queries'],
                workload.get('estimated_monthly_slot_hours', 0),
                m['peak_concurrent'],
                m['avg_concurrent']
            )
            node_config = f"{prov['node_type']} ({prov['num_nodes']}-node cluster, {prov['vcpu_total']} vCPUs, {prov['memory_gb_total']} GiB RAM)"
            # One-liner sizing explanation tied to assessment data
            nodes_for_compute = prov.get('sizing_basis', {}).get('nodes_for_compute', prov['num_nodes'])
            nodes_for_storage = prov.get('sizing_basis', {}).get('nodes_for_storage', 1)
            if nodes_for_compute > nodes_for_storage:
                config_explanation = f"Based on the assessed workload of {m['total_queries']} queries with {m['peak_concurrent']:.0f} peak concurrent slots, {prov['num_nodes']} nodes are needed to handle the compute demand ({prov['memory_gb_total']} GiB RAM, {prov['vcpu_total']} vCPUs)."
            elif nodes_for_storage > nodes_for_compute:
                config_explanation = f"With {m['total_size_gb']:.0f} GB of data identified in the assessment, {prov['num_nodes']} nodes are needed to accommodate the storage requirement ({prov['memory_gb_total']} GiB RAM, {prov['vcpu_total']} vCPUs)."
            else:
                config_explanation = f"The assessed {m['total_size_gb']:.0f} GB dataset with {m['total_queries']} queries requires {prov['num_nodes']} nodes to meet both compute and storage needs ({prov['memory_gb_total']} GiB RAM, {prov['vcpu_total']} vCPUs)."
        else:
            deploy_mode = 'Serverless'
            deploy_reason = 'Variable or unpredictable workload pattern — serverless auto-scales and eliminates cluster management overhead.'
            node_config = None
            config_explanation = None
        archs.append({
            'id': 'all_redshift', 'name': 'Redshift',
            'score': round(max(min(s, 100), 0)),
            'description': f'All {m["total_size_gb"]:.0f} GB loaded into Amazon Redshift. {m["hot_pct"]}% hot tables, {m["bi_pct"]}% BI queries, avg {m["avg_joins"]} joins/query.',
            'components': ['Amazon Redshift', 'Materialized Views', 'WLM'],
            'strengths': ['Lowest query latency', 'Best BI tool integration', 'Simplest architecture', 'Result caching'],
            'limitations': ['Higher storage cost at scale', 'All data must be loaded', 'Less flexible for ad-hoc'],
            'cost_profile': 'Higher compute, predictable pricing',
            'best_for': 'BI-heavy, high-join, high-concurrency workloads with mostly hot data',
            'deploy_mode': deploy_mode,
            'deploy_reason': deploy_reason,
            'node_config': node_config,
            'config_explanation': config_explanation,
        })

        # --- 2. Redshift + Data Sharing ---
        # HARD GATE: Only consider if 3+ distinct users AND shared tables detected
        s = 0
        if m['unique_users'] >= 3 and m['shared_tables'] > 0:
            s += 20 if m['unique_users'] > 3 else 10
            s += 20 if m['shared_tables'] > 5 else (10 if m['shared_tables'] > 0 else 0)
            s += min(m['bi_pct'] * 0.15, 15)
            s += min(m['peak_concurrent'] * 0.10, 10) if m['peak_concurrent'] > 20 else 0
            s += 10 if m['hot_pct'] > 50 else 0
            s += 5 if m['avg_joins'] > 2 else 0
        # If fewer than 3 users or no shared tables, score stays 0
        archs.append({
            'id': 'redshift_data_sharing', 'name': 'Redshift + Data Sharing',
            'score': round(max(min(s, 100), 0)),
            'description': f'{m["unique_users"]} distinct users, {m["shared_tables"]} shared tables. Workload isolation across teams with shared datasets.',
            'components': ['Amazon Redshift', 'Data Sharing', 'Separate Namespaces/Clusters'],
            'strengths': ['Workload isolation per team', 'Governance & access control', 'No data duplication', 'Independent scaling'],
            'limitations': ['Management complexity', 'Cross-cluster query overhead', 'Requires Redshift RA3'],
            'cost_profile': 'Multiple clusters/namespaces, shared storage',
            'best_for': 'Multi-team environments with shared datasets and different SLAs',
        })

        # --- 3. EMR / Glue + Open Iceberg ---
        s = 0
        s += min(m['etl_pct'] * 0.30, 30)          # ETL weight 30%
        s += min(m['write_pct'] * 0.20, 20)         # Write-heavy weight 20%
        s += 15 if m['write_heavy_count'] > 3 else (5 if m['write_heavy_count'] > 0 else 0)
        s += 10 if m['total_size_gb'] > 500 else 0
        s += 10 if m['scan_heavy'] > m['total_queries'] * 0.1 else 0
        s -= 15 if m['etl_pct'] < 10 else 0         # No ETL = not suitable
        archs.append({
            'id': 'emr_glue_iceberg', 'name': 'EMR / Glue + Open Iceberg',
            'score': round(max(min(s, 100), 0)),
            'description': f'{m["etl_pct"]}% ETL workload, {m["write_heavy_count"]} write-heavy tables. Heavy transformations via Spark/Glue with Iceberg tables.',
            'components': ['Amazon EMR (Spark)', 'AWS Glue', 'Apache Iceberg on S3', 'AWS Glue Data Catalog'],
            'strengths': ['Best for complex transformations', 'Schema evolution', 'CDC/streaming support', 'ACID on S3'],
            'limitations': ['Cluster management (EMR)', 'Higher complexity', 'Not optimized for interactive BI'],
            'cost_profile': 'Variable — depends on processing volume',
            'best_for': 'Heavy ETL, streaming/CDC pipelines, frequent schema evolution',
        })

        # --- 4. AWS Managed Iceberg (Glue + S3 Tables) ---
        s = 0
        s += min(m['etl_pct'] * 0.20, 20)
        s += 15 if m['cold_pct'] > 30 else 5
        s += 15 if m['total_size_gb'] > 100 else 5
        s += 10 if m['write_pct'] > 20 else 0
        s += 10 if m['adhoc_pct'] > 30 else 0
        s -= 10 if m['etl_pct'] < 5 and m['cold_pct'] < 20 else 0
        archs.append({
            'id': 'managed_iceberg', 'name': 'AWS Managed Iceberg (Glue + S3 Tables)',
            'score': round(max(min(s, 100), 0)),
            'description': f'{m["cold_pct"]}% cold tables, {m["total_size_gb"]:.0f} GB total. Serverless Iceberg management without EMR cluster overhead.',
            'components': ['AWS Glue', 'S3 Tables (Iceberg)', 'AWS Glue Data Catalog', 'Lake Formation'],
            'strengths': ['Serverless — no cluster management', 'Schema evolution', 'Lower ops overhead than EMR', 'ACID transactions'],
            'limitations': ['Less flexible than full EMR', 'Limited to Glue capabilities', 'Moderate query latency'],
            'cost_profile': 'Serverless pricing, lower ops cost than EMR',
            'best_for': 'Moderate ETL, serverless preference, cold data management',
        })

        # --- 5. Athena + Redshift ---
        s = 0
        s += min(m['adhoc_pct'] * 0.25, 25)        # Ad-hoc weight 25%
        s += min(m['cold_pct'] * 0.20, 20)          # Cold data weight 20%
        s += 15 if m['total_size_gb'] > 500 else 5
        s += 10 if m['scan_heavy'] < m['total_queries'] * 0.2 else 0  # Not too many large scans
        s += 10 if m['bi_pct'] > 20 else 0          # Some BI = needs Redshift too
        s -= 10 if m['peak_concurrent'] > 100 else 0  # High concurrency = Athena struggles
        s -= 10 if m['avg_joins'] > 3 else 0         # Complex joins = Athena not ideal
        archs.append({
            'id': 'athena_redshift', 'name': 'Athena + Redshift',
            'score': round(max(min(s, 100), 0)),
            'description': f'{m["adhoc_pct"]}% ad-hoc queries via Athena on S3, {m["bi_pct"]}% BI queries via Redshift. Pay-per-query for exploration.',
            'components': ['Amazon Athena', 'Amazon Redshift', 'Amazon S3 (Parquet/Iceberg)', 'AWS Glue Data Catalog'],
            'strengths': ['Pay-per-query for ad-hoc', 'No cluster for exploration', 'Cost-effective for cold data', 'Flexible'],
            'limitations': ['Athena latency higher than Redshift', 'Cost risk with large frequent scans', 'Not ideal for complex joins'],
            'cost_profile': 'Pay-per-query (Athena) + Redshift for BI',
            'best_for': 'High ad-hoc %, cost-sensitive, mixed workloads with cold data',
        })
        archs.sort(key=lambda a: a['score'], reverse=True)
        return archs

    # ------------------------------------------------------------------ #
    #  Step 3: Apply Rule-Based Overrides
    # ------------------------------------------------------------------ #
    def _apply_overrides(self, archs: List[Dict], m: Dict) -> List[Dict]:
        """Apply hard rules that override or adjust scores."""
        overrides_applied = []
        for a in archs:
            aid = a['id']
            # Performance & Latency
            if aid == 'athena_redshift' and m['peak_concurrent'] > 100:
                a['score'] = max(a['score'] - 20, 0)
                overrides_applied.append(f"Athena penalized: high concurrency ({m['peak_concurrent']} peak)")
            if aid == 'all_redshift' and m['bi_pct'] > 75:
                a['score'] = min(a['score'] + 10, 100)
                overrides_applied.append(f"Redshift boosted: BI-dominant workload ({m['bi_pct']}%)")
            # Data Access
            if aid == 'all_redshift' and m['cold_pct'] > 60:
                a['score'] = max(a['score'] - 20, 0)
                overrides_applied.append(f"Redshift penalized: majority cold data ({m['cold_pct']}%)")
            if aid == 'all_redshift' and m['hot_pct'] > 70:
                a['score'] = min(a['score'] + 15, 100)
                overrides_applied.append(f"Redshift boosted: mostly hot data ({m['hot_pct']}%)")
            if aid == 'athena_redshift' and m['cold_pct'] > 60:
                a['score'] = min(a['score'] + 15, 100)
                overrides_applied.append(f"Athena+Redshift boosted: high cold data ({m['cold_pct']}%)")
            # Workload Type
            if aid == 'athena_redshift' and m['adhoc_pct'] > 50:
                a['score'] = min(a['score'] + 10, 100)
                overrides_applied.append(f"Athena boosted: ad-hoc dominant ({m['adhoc_pct']}%)")
            if aid == 'athena_redshift' and m['adhoc_pct'] < 10:
                a['score'] = 0
                overrides_applied.append(f"Athena disqualified: no significant ad-hoc workload ({m['adhoc_pct']}%)")
            if aid in ('emr_glue_iceberg', 'managed_iceberg') and m['etl_pct'] > 40:
                a['score'] = min(a['score'] + 15, 100)
                overrides_applied.append(f"Iceberg boosted: heavy ETL ({m['etl_pct']}%)")
            if aid == 'athena_redshift' and m['write_pct'] > 30:
                a['score'] = max(a['score'] - 15, 0)
                overrides_applied.append(f"Athena penalized: write-heavy ({m['write_pct']}%)")
            # Query Complexity
            if aid == 'all_redshift' and m['avg_joins'] > 3:
                a['score'] = min(a['score'] + 10, 100)
                overrides_applied.append(f"Redshift boosted: complex joins (avg {m['avg_joins']})")
            if aid == 'athena_redshift' and m['avg_joins'] > 3:
                a['score'] = max(a['score'] - 10, 0)
                overrides_applied.append(f"Athena penalized: complex joins not ideal")
            # Organization
            if aid == 'redshift_data_sharing' and m['unique_users'] > 3 and m['shared_tables'] > 5:
                a['score'] = min(a['score'] + 15, 100)
                overrides_applied.append(f"Data Sharing boosted: {m['unique_users']} users, {m['shared_tables']} shared tables")
            # Data Volume
            if aid == 'all_redshift' and m['total_size_gb'] > 500:
                a['score'] = max(a['score'] - 10, 0)
                overrides_applied.append(f"Redshift penalized: large dataset ({m['total_size_gb']:.0f} GB)")
            if aid in ('athena_redshift', 'managed_iceberg') and m['total_size_gb'] > 500:
                a['score'] = min(a['score'] + 10, 100)
            # ETL
            if aid in ('emr_glue_iceberg', 'managed_iceberg') and m['etl_pct'] < 5:
                a['score'] = max(a['score'] - 15, 0)
                overrides_applied.append(f"Iceberg penalized: minimal ETL ({m['etl_pct']}%)")
        # Golden Rules
        for a in archs:
            if a['id'] == 'athena_redshift' and m['bi_pct'] > 70 and a['score'] > archs[0]['score']:
                a['score'] = max(a['score'] - 20, 0)
                overrides_applied.append("Golden rule: never Athena-only for enterprise BI")
            if a['id'] == 'all_redshift' and m['cold_pct'] > 70:
                a['score'] = min(a['score'], 40)
                overrides_applied.append("Golden rule: never full Redshift if majority cold")
            if a['id'] in ('emr_glue_iceberg', 'managed_iceberg') and m['etl_pct'] < 5:
                a['score'] = min(a['score'], 30)
                overrides_applied.append("Golden rule: never EMR/Iceberg without ETL workload")
            if a['id'] == 'redshift_data_sharing' and (m['unique_users'] < 3 or m['shared_tables'] == 0):
                a['score'] = 0
                overrides_applied.append(f"Golden rule: Data Sharing requires 3+ distinct user groups AND shared table access (found {m['unique_users']} users, {m['shared_tables']} shared tables)")
            if a['id'] == 'athena_redshift' and m['adhoc_pct'] < 10:
                a['score'] = 0
                overrides_applied.append(f"Golden rule: Athena requires ad-hoc workload (found {m['adhoc_pct']}%)")
            if a['id'] in ('managed_iceberg', 'emr_glue_iceberg') and m['bi_pct'] > 30:
                a['score'] = 0
                overrides_applied.append(f"Golden rule: {a['name']} cannot be standalone when BI is {m['bi_pct']}% — Redshift required")
        archs.sort(key=lambda a: a['score'], reverse=True)
        return archs, overrides_applied

    # ------------------------------------------------------------------ #
    #  Step 4: Generate Insights Summary
    # ------------------------------------------------------------------ #
    def _generate_insights(self, m: Dict) -> List[str]:
        """Generate plain-English assessment insights."""
        insights = []
        sz = m['total_size_gb']
        if sz > 1000: insights.append(f"The dataset is large at {sz:.0f} GB across {m['total_tables']} tables, favoring tiered storage to optimize costs.")
        elif sz > 100: insights.append(f"The dataset is {sz:.0f} GB across {m['total_tables']} tables — a moderate size compatible with most architectures.")
        else: insights.append(f"The dataset is compact at {sz:.0f} GB across {m['total_tables']} tables, making a Redshift-centric approach straightforward.")
        if m['bi_pct'] > 60: insights.append(f"The workload is BI-driven ({m['bi_pct']}% scheduled/repeated queries), requiring consistent low-latency performance.")
        elif m['adhoc_pct'] > 60: insights.append(f"The workload is predominantly ad-hoc ({m['adhoc_pct']}% exploratory queries), favoring pay-per-query options.")
        else: insights.append(f"A mixed workload is observed — {m['bi_pct']}% BI/scheduled and {m['adhoc_pct']}% ad-hoc — benefiting from a hybrid architecture.")
        if m['avg_joins'] > 3: insights.append(f"High join complexity detected (avg {m['avg_joins']} joins/query) — Redshift's collocation advantage is significant here.")
        if m['write_pct'] > 30: insights.append(f"Notable write activity ({m['write_pct']}% writes) indicates active transformation pipelines.")
        if m['cold_pct'] > 40: insights.append(f"{m['cold_count']} tables ({m['cold_pct']}%) show no recent query activity — candidates for S3 cold storage.")
        if m['hot_pct'] > 0 and m['cold_pct'] > 0: insights.append(f"Clear access pattern: {m['hot_count']} hot, {m['warm_count']} warm, {m['cold_count']} cold tables — tiered storage recommended.")
        if m['unique_users'] > 3: insights.append(f"{m['unique_users']} distinct users with {m['shared_tables']} shared tables — data sharing may improve governance.")
        if m['cache_ratio'] > 50: insights.append(f"A {m['cache_ratio']}% cache hit ratio indicates repeated queries — Redshift result caching will provide gains.")
        if m['etl_pct'] > 20: insights.append(f"{m['etl_pct']}% of queries are ETL/transformation operations — dedicated processing (Glue/EMR) recommended.")
        return insights

    # ------------------------------------------------------------------ #
    #  Step 5: Main Entry Point
    # ------------------------------------------------------------------ #
    def _recommend_architecture(self, query_classification: Dict, total_size_gb: float,
                                 tables: List[Dict] = None, query_stats: List[Dict] = None) -> Dict:
        """Generate architecture recommendations using the full framework."""
        tables = tables or []
        query_stats = query_stats or []
        workload = getattr(self, '_workload_cache', {})
        # 1. Compute decision metrics
        m = self._compute_decision_metrics(tables, query_stats, query_classification, workload)
        # 2. Score architectures
        archs = self._score_architectures(m)
        # 3. Apply rule-based overrides
        archs, overrides = self._apply_overrides(archs, m)
        # 4. Generate insights
        insights = self._generate_insights(m)
        # 5. Determine recommendation
        primary = archs[0] if archs else None
        # Check if combination is needed
        recommended_ids = set()
        if m['bi_pct'] > 20 and m['adhoc_pct'] > 20:
            # Mixed workload — may need combination
            bi_arch = max((a for a in archs if a['id'] in ('all_redshift','redshift_data_sharing')), key=lambda a: a['score'], default=None)
            adhoc_arch = max((a for a in archs if a['id'] in ('athena_redshift','managed_iceberg')), key=lambda a: a['score'], default=None)
            if bi_arch and adhoc_arch and bi_arch['id'] != adhoc_arch['id']:
                recommended_ids = {bi_arch['id'], adhoc_arch['id']}
        if m['etl_pct'] > 20:
            etl_arch = max((a for a in archs if a['id'] in ('emr_glue_iceberg','managed_iceberg')), key=lambda a: a['score'], default=None)
            if etl_arch: recommended_ids.add(etl_arch['id'])
        if m['unique_users'] >= 3 and m['shared_tables'] > 0:
            recommended_ids.add('redshift_data_sharing')
        if not recommended_ids and primary:
            recommended_ids = {primary['id']}
        # Build recommendation summary
        rec_names = [a['name'] for a in archs if a['id'] in recommended_ids]
        if len(rec_names) > 1:
            rec_type = 'combination'
            rec_summary = f"A combination of {' and '.join(rec_names)} is recommended based on the identified workload patterns."
        elif rec_names:
            rec_type = 'single'
            rec_summary = f"{rec_names[0]} is recommended as the primary architecture (score: {primary['score']}%)."
        else:
            rec_type = 'single'
            rec_summary = 'Insufficient data to generate recommendations.'
        # Mark recommended architectures
        for a in archs:
            a['recommended'] = a['id'] in recommended_ids
        # Backward-compatible strategies
        strategies = [{'title': a['name'], 'points': [a['best_for'], f"Score: {a['score']}%"]} for a in archs[:3]]
        return {
            'strategies': strategies,
            'architecture_patterns': archs,
            'insights_summary': insights,
            'recommendation': {
                'type': rec_type, 'summary': rec_summary,
                'primary_architecture': primary['name'] if primary else None,
                'primary_architecture_id': primary['id'] if primary else None,
            },
            'decision_metrics': {k: v for k, v in m.items() if k not in ('hot_tables','warm_tables','cold_tables','write_heavy_tables')},
            'overrides_applied': overrides,
            'total_size_gb': round(m['total_size_gb'], 2),
        }
