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
        # 1 RPU = 16 GiB memory ≈ 2 BQ slots. So RPU needed = avg_slots / 2.
        # Valid RPU values: 4, 8, 16, 24, 32, ..., 1024 (4 is minimum, then multiples of 8).
        rpus_from_avg = max(1, math.ceil(estimated_avg_concurrent_slots / 2))
        if rpus_from_avg <= 4:
            estimated_base_rpu = 4
        else:
            estimated_base_rpu = math.floor(rpus_from_avg / 8) * 8

        # Step 4: Calculate monthly RPU-hours
        # active_hours_per_day = total_slot_hours / (time_span_days × 24)
        # RPU-hours/month = base_rpu × active_hours_per_day × 30
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
        - Mapping: 1 BQ slot ≈ 1 GiB memory equivalent.

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
            # High variance workload - size for avg (1 BQ slot ≈ 1 GiB), concurrency scaling handles peaks
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
            ('ra3.xlplus', 32, 1.086, 32),
            ('ra3.4xlarge', 96, 3.26, 32),
            ('ra3.16xlarge', 384, 13.04, 128),
        ]
        
        best_option = None
        best_cost = float('inf')
        
        for node_type, mem_per_node, hourly_cost, max_nodes in ra3_options:
            # Minimum nodes: ra3.xlplus supports single-node clusters, others need 2
            min_nodes = 1 if node_type == 'ra3.xlplus' else 2
            
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
                f"High variance workload (peak is {peak_to_avg_ratio:.1f}× avg) — "
                f"base cluster sized for sustained load with concurrency scaling for bursts"
            )
        else:
            rationale_parts.append(
                f"Steady workload — cluster sized to handle {int(total_memory_gib * 0.7)}-{total_memory_gib} concurrent slots"
            )
        
        rationale_parts.extend([
            f"Selected {node_type} ({specs['memory_gb']} GiB/node) × {num_nodes} nodes "
            f"= {total_memory_gib} GiB total RAM",
            f"Total slices: {specs['slices_per_node'] * num_nodes} "
            f"({specs['slices_per_node']} slices/node × {num_nodes} nodes)",
        ])
        
        if use_concurrency_scaling:
            rationale_parts.append(
                f"Concurrency scaling enabled: peak ({peak_slots:.0f} slots) is "
                f"{peak_to_base_ratio}× base capacity — burst traffic handled automatically"
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

        Mapping: 1 BQ slot ≈ 1 GiB memory, 1 RPU ≈ 2 BQ slots.
        Base RPU = floor(avg_slots / 2) rounded down to nearest 8.
        Max RPU = based on peak_slots for auto-scaling headroom.
        """
        # Base RPU from avg slots (not peak) — same logic as _analyze_workload
        # 1 RPU ≈ 2 BQ slots → avg_slots / 2 = RPUs needed
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
    #  Table Access Profiling (data-driven hot/warm/cold)
    # ------------------------------------------------------------------ #
    def _build_table_access_profile(self, tables: List[Dict], query_stats: List[Dict]) -> Dict:
        """Build per-table access profile from actual query stats."""
        from datetime import datetime
        table_access = {}
        for q in query_stats:
            meta = q.get('query_metadata', {}) or {}
            exec_count = meta.get('execution_count', 1) or 1
            slot_ms = q.get('slot_milliseconds', 0) or 0
            bytes_scanned = q.get('bytes_scanned', 0) or 0
            query_text = (q.get('query_text') or '').upper()
            exec_time = q.get('execution_time')
            is_write = any(kw in query_text for kw in ['INSERT', 'UPDATE', 'DELETE', 'MERGE', 'CREATE TABLE', 'TRUNCATE'])
            for ref in (q.get('referenced_tables') or []):
                # Store under multiple keys for matching (full path + short name + dataset.table)
                keys_to_store = [ref]
                parts = ref.split('.')
                if len(parts) >= 2:
                    keys_to_store.append(parts[-1])
                    keys_to_store.append(f"{parts[-2]}.{parts[-1]}")
                for key in keys_to_store:
                    if key not in table_access:
                        table_access[key] = {'query_count': 0, 'exec_count': 0, 'total_bytes': 0, 'total_slot_ms': 0, 'last_access': None, 'write_count': 0, 'read_count': 0, 'large_scans': 0}
                    ta = table_access[key]
                    ta['query_count'] += 1
                    ta['exec_count'] += exec_count
                    ta['total_bytes'] += bytes_scanned
                    ta['total_slot_ms'] += slot_ms
                    if is_write: ta['write_count'] += 1
                    else: ta['read_count'] += 1
                    if bytes_scanned > 1e9: ta['large_scans'] += 1
                    if exec_time:
                        try:
                            et = datetime.fromisoformat(exec_time) if isinstance(exec_time, str) else exec_time
                            if ta['last_access'] is None or et > ta['last_access']: ta['last_access'] = et
                        except Exception: pass

        hot, warm, cold = [], [], []
        hot_gb = warm_gb = cold_gb = 0
        write_heavy = []
        large_scan_tables = []
        now = datetime.utcnow()

        # If no table-level references found, use heuristic based on table size and total query volume
        has_references = any(v.get('exec_count', 0) > 0 for v in table_access.values())

        for t in tables:
            tname = t.get('table_name', '')
            full_name = f"{t.get('dataset_name', '')}.{tname}" if t.get('dataset_name') else tname
            access = table_access.get(tname) or table_access.get(full_name) or {}
            size_mb = t.get('size_mb', 0)
            ec = access.get('exec_count', 0)
            la = access.get('last_access')

            if has_references:
                # Data-driven classification from actual query references
                if ec >= 10 or (la and (now - la).days <= 7):
                    hot.append(tname); hot_gb += size_mb / 1024
                elif ec >= 1 or (la and (now - la).days <= 30):
                    warm.append(tname); warm_gb += size_mb / 1024
                else:
                    cold.append(tname); cold_gb += size_mb / 1024
            else:
                # Heuristic: when referenced_tables is empty, classify by update_frequency and size
                update_freq = (t.get('update_frequency') or '').lower()
                row_count = t.get('row_count', 0)
                if update_freq in ('daily', 'hourly', 'streaming') or row_count > 100000:
                    hot.append(tname); hot_gb += size_mb / 1024
                elif row_count > 1000 or size_mb > 10:
                    warm.append(tname); warm_gb += size_mb / 1024
                else:
                    cold.append(tname); cold_gb += size_mb / 1024

            if access.get('write_count', 0) > access.get('read_count', 0): write_heavy.append(tname)
            if access.get('large_scans', 0) > 0: large_scan_tables.append(tname)

        total_t = max(len(tables), 1)
        return {
            'table_access': table_access, 'hot_tables': hot, 'warm_tables': warm, 'cold_tables': cold,
            'hot_size_gb': hot_gb, 'warm_size_gb': warm_gb, 'cold_size_gb': cold_gb,
            'hot_pct': round(len(hot) / total_t * 100, 1), 'warm_pct': round(len(warm) / total_t * 100, 1), 'cold_pct': round(len(cold) / total_t * 100, 1),
            'write_heavy_tables': write_heavy, 'large_scan_tables': large_scan_tables,
        }

    # ------------------------------------------------------------------ #
    #  Workload Categorization
    # ------------------------------------------------------------------ #
    def _categorize_workloads(self, query_stats: List[Dict], tables: List[Dict], query_classification: Dict) -> List[Dict]:
        """Identify and categorize workloads from actual assessment data."""
        workloads = []
        total_queries = query_classification.get('total_queries', 0) or 1
        bi_pct = query_classification.get('bi_pct', 0)
        adhoc_pct = query_classification.get('adhoc_pct', 0)

        # Build table access profile for data-driven classification
        self._table_profile = self._build_table_access_profile(tables, query_stats)
        tp = self._table_profile

        # Deep analysis from actual query stats
        batch_indicators = 0
        heavy_transform_indicators = 0
        high_concurrency_count = 0

        for q in query_stats:
            meta = q.get('query_metadata', {}) or {}
            slot_ms = q.get('slot_milliseconds', 0) or 0
            bytes_scanned = q.get('bytes_scanned', 0) or 0
            exec_count = meta.get('execution_count', 1) or 1
            query_text = (q.get('query_text') or '').upper()

            if slot_ms > 60000 or bytes_scanned > 1e10:
                batch_indicators += 1
            if slot_ms < 5000 and exec_count > 10:
                high_concurrency_count += 1
            if any(kw in query_text for kw in ['CREATE TABLE', 'INSERT INTO', 'MERGE', 'CREATE VIEW', 'CTAS', 'CREATE OR REPLACE']):
                heavy_transform_indicators += 1

        if bi_pct > 15:
            workloads.append({
                'id': 'bi_dashboards', 'name': 'BI / Dashboard Workloads',
                'description': f'High-frequency queries from BI tools and dashboards. {high_concurrency_count} queries show high-concurrency patterns. {len(tp["hot_tables"])} hot tables identified.',
                'percentage': bi_pct, 'query_count': query_classification.get('bi_count', 0),
                'characteristics': ['High concurrency', 'Low latency required', 'Predictable query patterns', 'Repeated aggregations'],
                'priority': 'high'
            })

        if adhoc_pct > 15:
            workloads.append({
                'id': 'adhoc_analytical', 'name': 'Ad-hoc Analytical Queries',
                'description': f'Exploratory queries with varying complexity. {len(tp["large_scan_tables"])} tables have queries scanning >1GB.',
                'percentage': adhoc_pct, 'query_count': query_classification.get('adhoc_count', 0),
                'characteristics': ['Variable complexity', 'Unpredictable patterns', 'Full table scans common', 'Schema exploration'],
                'priority': 'medium'
            })

        if batch_indicators > max(total_queries * 0.05, 3):
            workloads.append({
                'id': 'batch_processing', 'name': 'Batch Processing Pipelines',
                'description': f'{batch_indicators} queries with >60s CPU time or >10GB scans detected. {len(tp["write_heavy_tables"])} write-heavy tables identified.',
                'percentage': round(batch_indicators / total_queries * 100, 1), 'query_count': batch_indicators,
                'characteristics': ['High data volume', 'Scheduled execution', 'Long-running queries', 'Write-heavy operations'],
                'priority': 'medium'
            })

        if heavy_transform_indicators > 3:
            workloads.append({
                'id': 'heavy_transforms', 'name': 'Heavy Data Transformations',
                'description': f'{heavy_transform_indicators} DDL/DML transformation operations detected (CREATE TABLE, INSERT, MERGE).',
                'percentage': round(heavy_transform_indicators / total_queries * 100, 1), 'query_count': heavy_transform_indicators,
                'characteristics': ['Complex joins', 'Multi-step pipelines', 'Data modeling', 'Schema transformations'],
                'priority': 'medium'
            })

        if len(tp['cold_tables']) > 0:
            workloads.append({
                'id': 'archival', 'name': 'Archival / Rarely Accessed Data',
                'description': f'{len(tp["cold_tables"])} tables ({tp["cold_size_gb"]:.1f} GB) with no query activity in the assessment period.',
                'percentage': tp['cold_pct'], 'query_count': 0,
                'characteristics': ['No recent queries', 'Large data volume', 'Compliance/retention needs', 'Infrequent access'],
                'table_count': len(tp['cold_tables']), 'size_gb': round(tp['cold_size_gb'], 2),
                'priority': 'low'
            })

        return workloads

    # ------------------------------------------------------------------ #
    #  Architecture Patterns
    # ------------------------------------------------------------------ #
    def _define_architecture_patterns(self, total_size_gb: float, workloads: List[Dict], query_classification: Dict) -> List[Dict]:
        """Define architecture patterns with data-driven suitability scores."""
        bi_pct = query_classification.get('bi_pct', 0)
        adhoc_pct = query_classification.get('adhoc_pct', 0)
        has_batch = any(w['id'] == 'batch_processing' for w in workloads)
        has_archive = any(w['id'] == 'archival' for w in workloads)
        has_transforms = any(w['id'] == 'heavy_transforms' for w in workloads)

        # Use table profile for data-driven scoring
        tp = getattr(self, '_table_profile', {})
        hot_pct = tp.get('hot_pct', 50)
        warm_pct = tp.get('warm_pct', 25)
        cold_pct = tp.get('cold_pct', 25)
        hot_size_gb = tp.get('hot_size_gb', total_size_gb * 0.5)
        cold_size_gb = tp.get('cold_size_gb', 0)
        write_heavy_count = len(tp.get('write_heavy_tables', []))

        patterns = []

        # Architecture A: Redshift-Centric
        a_score = 30
        if bi_pct > 60: a_score += 25
        elif bi_pct > 40: a_score += 15
        if hot_pct > 70: a_score += 20  # Most tables are hot — all belong in Redshift
        if total_size_gb < 500: a_score += 10
        if cold_pct < 10: a_score += 10  # Very little cold data
        if write_heavy_count > 0: a_score += 5  # Write-heavy tables need Redshift
        patterns.append({
            'id': 'redshift_centric',
            'name': 'Architecture A: Redshift-Centric (Full Warehouse)',
            'short_name': 'Redshift-Centric',
            'description': f'All {total_size_gb:.0f} GB loaded into Amazon Redshift. Best suited when most tables ({hot_pct}% hot) need low-latency access and BI workloads dominate ({bi_pct}% BI queries).',
            'suitability_score': min(a_score, 100),
            'best_for': ['High-frequency BI / dashboard workloads', 'Low-latency query requirements', 'Moderate data volumes (< 500 GB)'],
            'components': ['Amazon Redshift (Provisioned or Serverless)', 'Redshift Materialized Views', 'Redshift WLM for workload management'],
            'data_placement': {'hot': 'All data in Redshift tables', 'warm': 'N/A', 'cold': 'N/A'},
            'strengths': ['Lowest query latency', 'Simplest architecture', 'Best BI tool integration', 'Consistent performance'],
            'limitations': ['Higher storage costs at scale', 'All data must be loaded', 'Less flexible for ad-hoc exploration', 'Storage scales with compute'],
            'cost_profile': 'Higher compute cost, predictable pricing',
            'suitable_workloads': ['bi_dashboards']
        })

        # Architecture B: Redshift + Spectrum
        b_score = 35
        if adhoc_pct > 30: b_score += 15
        if warm_pct > 20: b_score += 15  # Significant warm data benefits from Spectrum
        if has_archive: b_score += 10
        if total_size_gb > 100: b_score += 10
        if bi_pct > 30 and adhoc_pct > 20: b_score += 10  # Mixed workload sweet spot
        if hot_pct > 30 and cold_pct > 20: b_score += 10  # Clear hot/cold split
        patterns.append({
            'id': 'redshift_spectrum',
            'name': 'Architecture B: Redshift + Spectrum (Hybrid Query Layer)',
            'short_name': 'Redshift + Spectrum',
            'description': f'Hot tables ({hot_pct}% of data) in Redshift for performance, warm/cold tables ({warm_pct + cold_pct}%) queried from S3 via Spectrum. Ideal for mixed workloads ({bi_pct}% BI, {adhoc_pct}% ad-hoc).',
            'suitability_score': min(b_score, 100),
            'best_for': ['Mixed BI and ad-hoc workloads', 'Large datasets with varying access patterns', 'Cost optimization for infrequently accessed data'],
            'components': ['Amazon Redshift', 'Redshift Spectrum', 'Amazon S3', 'AWS Glue Data Catalog'],
            'data_placement': {'hot': 'Frequently queried tables in Redshift', 'warm': 'Less frequent data in S3 via Spectrum', 'cold': 'Archived data in S3 (Parquet)'},
            'strengths': ['Balance of performance and cost', 'Query S3 data without loading', 'Unified SQL interface', 'Flexible data tiering'],
            'limitations': ['Spectrum queries slower than native Redshift', 'Requires data format optimization (Parquet)', 'More complex data management', 'S3 data not cached'],
            'cost_profile': 'Moderate — reduced storage costs, pay-per-query for S3 data',
            'suitable_workloads': ['bi_dashboards', 'adhoc_analytical', 'archival']
        })

        # Architecture C: Lakehouse
        c_score = 30
        if total_size_gb > 500: c_score += 20
        elif total_size_gb > 100: c_score += 10
        if cold_pct > 30: c_score += 15  # Significant cold data benefits from Iceberg
        if has_archive: c_score += 10
        if adhoc_pct > 40: c_score += 10
        if has_batch: c_score += 10
        if warm_pct > 30: c_score += 10  # Warm data fits Iceberg well
        patterns.append({
            'id': 'lakehouse',
            'name': 'Architecture C: Lakehouse (Redshift + S3 + Iceberg)',
            'short_name': 'Lakehouse',
            'description': f'Active tables in Redshift, {cold_pct}% of tables classified as cold{" (" + str(round(cold_size_gb, 1)) + " GB)" if cold_size_gb > 0.1 else ""} stored in S3 as Apache Iceberg tables. Supports schema evolution and time travel with {total_size_gb:.0f} GB total data.',
            'suitability_score': min(c_score, 100),
            'best_for': ['Large-scale datasets (500+ GB)', 'Schema evolution requirements', 'Mixed hot/cold data access patterns', 'Time travel and audit needs'],
            'components': ['Amazon Redshift', 'Amazon S3 (Apache Iceberg)', 'AWS Glue Data Catalog', 'AWS Lake Formation'],
            'data_placement': {'hot': 'Active tables in Redshift', 'warm': 'Recent historical data in S3 Iceberg tables', 'cold': 'Archived data in S3 Iceberg (compressed)'},
            'strengths': ['Schema evolution support', 'Time travel capabilities', 'Cost-effective at scale', 'Single copy of data possible', 'ACID transactions on S3'],
            'limitations': ['More complex setup', 'Iceberg table management overhead', 'Query performance varies by data location', 'Requires catalog management'],
            'cost_profile': 'Lower storage costs, moderate compute, Iceberg management overhead',
            'suitable_workloads': ['bi_dashboards', 'adhoc_analytical', 'archival', 'batch_processing']
        })

        # Architecture D: S3-Centric
        d_score = 25
        if adhoc_pct > 60: d_score += 20
        if total_size_gb > 1000: d_score += 20
        elif total_size_gb > 500: d_score += 10
        if cold_pct > 50: d_score += 20  # Majority cold data — S3 is ideal
        if has_archive: d_score += 10
        if hot_pct < 20: d_score += 10  # Very few hot tables — no need for full Redshift
        patterns.append({
            'id': 's3_centric',
            'name': 'Architecture D: S3-Centric (Data Lake First)',
            'short_name': 'S3 Data Lake',
            'description': f'All {total_size_gb:.0f} GB stored in S3 (Parquet/Iceberg). Two modes: D1 — query via Athena/Glue/EMR without Redshift, D2 — use Redshift as query engine over S3 tables. Best when ad-hoc queries dominate ({adhoc_pct}%) and {cold_pct}% of tables are cold.',
            'suitability_score': min(d_score, 100),
            'best_for': ['Very large datasets (1+ TB)', 'Cost-sensitive workloads', 'Flexible schema evolution', 'Multi-engine analytics'],
            'components': ['Amazon S3 (Parquet / Iceberg)', 'Amazon Athena', 'AWS Glue Data Catalog / Lake Formation', 'Amazon Redshift (optional query engine)'],
            'sub_patterns': [
                {
                    'id': 'd1_standalone',
                    'name': 'D1: S3 Tables as Standalone Analytics Layer',
                    'description': 'Data queried using Athena, Glue, or EMR directly. No Redshift required.',
                    'best_for': ['Large-scale datasets', 'Cost-sensitive workloads', 'Flexible schema evolution'],
                    'query_engines': ['Amazon Athena', 'AWS Glue', 'Amazon EMR']
                },
                {
                    'id': 'd2_with_redshift',
                    'name': 'D2: S3 Tables + Redshift (Integrated Query Layer)',
                    'description': 'Data in S3 Iceberg tables, Redshift used as query engine via Glue Data Catalog. No data ingestion needed.',
                    'best_for': ['Unified analytics across lake and warehouse', 'Reduced data movement', 'Single copy of data'],
                    'integration': 'Redshift connects to AWS Glue Data Catalog to query Iceberg tables directly',
                    'benefits': ['No data duplication', 'Reduced data movement', 'Schema evolution support', 'Time travel support']
                }
            ],
            'data_placement': {'hot': 'S3 Iceberg tables (frequently queried)', 'warm': 'S3 Parquet (periodic access)', 'cold': 'S3 Glacier (archival)'},
            'strengths': ['Lowest storage cost', 'Maximum flexibility', 'Multi-engine support', 'No vendor lock-in', 'Single copy of data'],
            'limitations': ['Higher query latency than native Redshift', 'Requires data format optimization', 'More complex orchestration', 'Athena costs per query'],
            'cost_profile': 'Lowest storage, pay-per-query compute, most cost-effective at scale',
            'suitable_workloads': ['adhoc_analytical', 'archival', 'batch_processing']
        })

        # Architecture E: Processing-Heavy
        e_score = 20
        if has_transforms: e_score += 25
        if has_batch: e_score += 20
        if write_heavy_count > len(tp.get('hot_tables', [])) * 0.3: e_score += 15  # Many write-heavy tables
        if total_size_gb > 500: e_score += 10
        patterns.append({
            'id': 'processing_heavy',
            'name': 'Architecture E: Processing-Heavy (EMR / Glue Driven)',
            'short_name': 'EMR / Glue Processing',
            'description': f'Transformation-focused architecture. {len(tp.get("write_heavy_tables", []))} write-heavy tables and batch processing workloads handled by AWS Glue (serverless ETL) or Amazon EMR (Spark). Output stored in Redshift or S3.',
            'suitability_score': min(e_score, 100),
            'best_for': ['Complex data transformations', 'Large-scale Spark workloads', 'Multi-step ETL pipelines', 'ML feature engineering'],
            'components': ['AWS Glue (serverless ETL)', 'Amazon EMR (Spark)', 'Amazon S3', 'Amazon Redshift or Athena (downstream)'],
            'data_placement': {'hot': 'Processing output in Redshift or S3', 'warm': 'Intermediate data in S3', 'cold': 'Raw/source data in S3'},
            'compute_recommendations': [
                {'engine': 'AWS Glue', 'use_case': 'Lightweight/serverless ETL, schema discovery, data cataloging', 'scale': 'Small to medium'},
                {'engine': 'Amazon EMR', 'use_case': 'Heavy Spark transformations, ML pipelines, complex joins', 'scale': 'Medium to large'}
            ],
            'strengths': ['Best for complex transformations', 'Scalable processing', 'Serverless option (Glue)', 'Spark ecosystem support'],
            'limitations': ['Not optimized for interactive queries', 'EMR cluster management', 'Higher complexity', 'Requires orchestration (Step Functions)'],
            'cost_profile': 'Variable — depends on processing volume and frequency',
            'suitable_workloads': ['batch_processing', 'heavy_transforms']
        })

        # Sort by suitability score
        patterns.sort(key=lambda p: p['suitability_score'], reverse=True)
        return patterns

    # ------------------------------------------------------------------ #
    #  Workload-to-Architecture Mapping
    # ------------------------------------------------------------------ #
    def _map_workloads_to_architectures(self, workloads: List[Dict], patterns: List[Dict]) -> List[Dict]:
        """Map each workload to the most suitable architecture with justification."""
        mappings = []
        for w in workloads:
            wid = w['id']
            best_pattern = None
            best_score = 0
            alternatives = []

            for p in patterns:
                if wid in p.get('suitable_workloads', []):
                    score = p['suitability_score']
                    # Boost score for specific matches
                    if wid == 'bi_dashboards' and p['id'] == 'redshift_centric': score += 20
                    if wid == 'adhoc_analytical' and p['id'] in ('redshift_spectrum', 's3_centric'): score += 15
                    if wid == 'batch_processing' and p['id'] == 'processing_heavy': score += 20
                    if wid == 'heavy_transforms' and p['id'] == 'processing_heavy': score += 25
                    if wid == 'archival' and p['id'] in ('s3_centric', 'lakehouse'): score += 20

                    if score > best_score:
                        if best_pattern:
                            alternatives.append({'name': best_pattern['short_name'], 'reason': 'Lower suitability score'})
                        best_pattern = p
                        best_score = score
                    else:
                        alternatives.append({'name': p['short_name'], 'reason': 'Lower suitability score'})

            if best_pattern:
                mappings.append({
                    'workload': w['name'],
                    'workload_id': wid,
                    'recommended_architecture': best_pattern['short_name'],
                    'architecture_id': best_pattern['id'],
                    'suitability_score': best_score,
                    'justification': self._get_mapping_justification(wid, best_pattern['id'], w),
                    'trade_offs': best_pattern.get('limitations', [])[:2],
                    'alternatives_not_selected': alternatives[:2]
                })

        return mappings

    def _get_mapping_justification(self, workload_id: str, arch_id: str, workload: Dict) -> str:
        """Generate justification for a workload-architecture mapping."""
        justifications = {
            ('bi_dashboards', 'redshift_centric'): f"With {workload.get('percentage', 0)}% BI queries requiring consistent low-latency responses, Redshift's columnar storage and result caching provide optimal dashboard performance.",
            ('bi_dashboards', 'redshift_spectrum'): f"BI workloads ({workload.get('percentage', 0)}%) benefit from Redshift's native performance for hot data, while Spectrum handles overflow queries on historical data.",
            ('adhoc_analytical', 'redshift_spectrum'): f"Ad-hoc queries ({workload.get('percentage', 0)}%) with unpredictable patterns benefit from Spectrum's ability to query S3 data without pre-loading, reducing storage costs.",
            ('adhoc_analytical', 's3_centric'): f"High ad-hoc query volume ({workload.get('percentage', 0)}%) with variable patterns is best served by S3 + Athena for cost-effective, schema-flexible exploration.",
            ('batch_processing', 'processing_heavy'): f"Batch processing workloads ({workload.get('query_count', 0)} queries) with large data volumes are best handled by EMR/Glue for scalable, cost-effective processing.",
            ('heavy_transforms', 'processing_heavy'): f"Complex transformations ({workload.get('query_count', 0)} operations) require Spark-level processing power available through EMR or serverless Glue jobs.",
            ('archival', 's3_centric'): f"Archival data ({workload.get('size_gb', 0):.1f} GB across {workload.get('table_count', 0)} tables) with no recent queries should reside in S3 for minimal cost with on-demand access via Athena.",
            ('archival', 'lakehouse'): f"Archival data benefits from Iceberg's time travel and schema evolution while maintaining low S3 storage costs.",
        }
        return justifications.get((workload_id, arch_id), f"This architecture provides the best balance of performance and cost for {workload.get('name', 'this workload')}.")

    # ------------------------------------------------------------------ #
    #  Architecture Recommendation (Main Entry Point)
    # ------------------------------------------------------------------ #
    def _recommend_architecture(self, query_classification: Dict, total_size_gb: float, tables: List[Dict] = None, query_stats: List[Dict] = None) -> Dict:
        """Generate comprehensive workload-based multi-architecture recommendations."""
        tables = tables or []
        query_stats = query_stats or []

        # 1. Categorize workloads
        workloads = self._categorize_workloads(query_stats, tables, query_classification)

        # 2. Define architecture patterns with suitability scores
        patterns = self._define_architecture_patterns(total_size_gb, workloads, query_classification)

        # 3. Map workloads to architectures
        workload_mappings = self._map_workloads_to_architectures(workloads, patterns)

        # 4. Determine primary recommendation
        if patterns:
            primary = patterns[0]
            # Check if a combination is better
            unique_archs = set(m['architecture_id'] for m in workload_mappings)
            if len(unique_archs) > 1:
                recommendation_type = 'combination'
                arch_names = list(set(m['recommended_architecture'] for m in workload_mappings))
                workload_names = [m['workload'] for m in workload_mappings]
                recommendation_summary = f"A combination of {' and '.join(arch_names)} is recommended to serve the identified workload categories: {', '.join(workload_names)}."
            else:
                recommendation_type = 'single'
                recommendation_summary = f"{primary['short_name']} is recommended as the dominant architecture, scoring {primary['suitability_score']}% suitability for the identified workload profile."
        else:
            primary = None
            recommendation_type = 'single'
            recommendation_summary = 'Insufficient data to generate architecture recommendations.'

        # 5. Data placement strategy
        data_placement = {
            'hot': {'description': 'Frequently queried data (daily access)', 'recommendation': 'Amazon Redshift tables', 'criteria': ['Query frequency > 10/day', 'Latency < 1s required', 'Active dashboards']},
            'warm': {'description': 'Periodically accessed data (weekly/monthly)', 'recommendation': 'S3 via Redshift Spectrum or Iceberg tables', 'criteria': ['Query frequency 1-10/week', 'Moderate latency acceptable', 'Historical analysis']},
            'cold': {'description': 'Rarely accessed / archival data', 'recommendation': 'S3 (Parquet/Iceberg) or S3 Glacier', 'criteria': ['No recent queries', 'Compliance/retention only', 'Cost optimization priority']}
        }

        # 6. Backward-compatible strategies (for existing frontend)
        strategies = []
        for p in patterns[:3]:
            strategies.append({
                'title': p['name'],
                'points': p['best_for'] + [f"Suitability Score: {p['suitability_score']}%"]
            })

        # 7. Generate plain-English insights summary from actual assessment data
        tp = getattr(self, '_table_profile', {})
        total_tables = len(tables)
        total_queries = query_classification.get('total_queries', 0)
        bi_pct = query_classification.get('bi_pct', 0)
        adhoc_pct = query_classification.get('adhoc_pct', 0)
        read_pct = query_classification.get('read_pct', 0)
        write_pct = query_classification.get('write_pct', 0)
        cache_ratio = query_classification.get('cache_hit_ratio', 0)
        hot_count = len(tp.get('hot_tables', []))
        warm_count = len(tp.get('warm_tables', []))
        cold_count = len(tp.get('cold_tables', []))

        insights = []
        # Data volume insight
        if total_size_gb > 1000:
            insights.append(f"The dataset is large at {total_size_gb:.1f} GB across {total_tables} tables, which favors architectures with tiered storage (S3 + Redshift) to optimize costs.")
        elif total_size_gb > 100:
            insights.append(f"The dataset is {total_size_gb:.1f} GB across {total_tables} tables — a moderate size that works well with most architecture patterns.")
        else:
            insights.append(f"The dataset is compact at {total_size_gb:.1f} GB across {total_tables} tables, making a Redshift-centric approach straightforward and cost-effective.")

        # Query pattern insight
        if total_queries > 0:
            if bi_pct > 60:
                insights.append(f"The workload is heavily BI-driven ({bi_pct}% scheduled/repeated queries), indicating a need for consistent low-latency performance — Redshift excels here.")
            elif adhoc_pct > 60:
                insights.append(f"The workload is predominantly ad-hoc ({adhoc_pct}% exploratory queries), suggesting flexible, pay-per-query options like Athena or Redshift Spectrum would be cost-effective.")
            else:
                insights.append(f"A mixed workload is observed — {bi_pct}% BI/scheduled and {adhoc_pct}% ad-hoc queries — which benefits from a hybrid architecture combining Redshift with S3-based querying.")

        # Read/write insight
        if write_pct > 30:
            insights.append(f"A notable {write_pct}% of queries are write operations (INSERT, UPDATE, MERGE), indicating active data transformation pipelines that may benefit from dedicated ETL processing (Glue/EMR).")
        elif read_pct > 90:
            insights.append(f"The workload is read-heavy ({read_pct}% reads), which is ideal for columnar storage and caching optimizations in Redshift.")

        # Table access pattern insight
        if total_tables > 0 and (hot_count + warm_count + cold_count) > 0:
            if cold_count > total_tables * 0.4:
                insights.append(f"Over {cold_count} tables ({tp.get('cold_pct', 0)}%) show no recent query activity — these are strong candidates for S3 cold storage, significantly reducing costs.")
            if hot_count > 0 and cold_count > 0:
                insights.append(f"The data has a clear access pattern: {hot_count} hot tables (frequently queried), {warm_count} warm tables, and {cold_count} cold tables — a tiered storage strategy would optimize both performance and cost.")
            elif hot_count > total_tables * 0.7:
                insights.append(f"Most tables ({hot_count}/{total_tables}) are actively queried, supporting a Redshift-centric approach where all data stays in the warehouse.")

        # Cache insight
        if cache_ratio > 50:
            insights.append(f"A {cache_ratio}% cache hit ratio indicates many repeated queries — Redshift's result caching will provide significant performance gains for these patterns.")
        elif cache_ratio < 20 and total_queries > 100:
            insights.append(f"A low cache hit ratio ({cache_ratio}%) suggests diverse query patterns with few repeats — Redshift Spectrum or Athena may be more cost-effective for handling varied queries.")

        return {
            'strategies': strategies,
            'workloads': workloads,
            'architecture_patterns': patterns,
            'workload_mappings': workload_mappings,
            'data_placement': data_placement,
            'insights_summary': insights,
            'recommendation': {
                'type': recommendation_type,
                'summary': recommendation_summary,
                'primary_architecture': primary['short_name'] if primary else None,
                'primary_architecture_id': primary['id'] if primary else None,
            },
            'total_size_gb': round(total_size_gb, 2)
        }
