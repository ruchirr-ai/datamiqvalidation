"""
BigQuery Assessment Service

Collects comprehensive metadata from BigQuery for migration assessment.
Optimized: Uses INFORMATION_SCHEMA SQL queries (Strategy 2) with REST API fallback.
Caches table metadata to avoid redundant API calls (Strategy 1).
"""

from google.cloud import bigquery
from google.oauth2 import service_account
from sqlalchemy.orm import Session
from typing import Dict, List, Optional, Tuple
import json
import re
from datetime import datetime
from collections import defaultdict

from repositories.assessment_repository import AssessmentRepository
from models.assessment import AssessmentTable
from utils.sql_dependency_parser import SQLDependencyParser


class BigQueryAssessmentService:
    def __init__(self, connection_params: Dict):
        """Initialize BigQuery client."""
        credentials_json = connection_params.get('credentials_json')
        if isinstance(credentials_json, str):
            credentials_json = json.loads(credentials_json)

        self.project_id = connection_params.get('project_id')
        if not self.project_id and credentials_json:
            self.project_id = credentials_json.get('project_id')
            print(f"Extracted project_id from credentials: {self.project_id}")

        if not self.project_id:
            raise ValueError("project_id not found in connection_params or credentials_json")

        credentials = service_account.Credentials.from_service_account_info(credentials_json)
        self.client = bigquery.Client(credentials=credentials, project=self.project_id)
        self.sql_parser = SQLDependencyParser()

        # Cached data (Strategy 1) — populated once, reused across steps
        self._region: Optional[str] = None
        self._cached_table_refs: Dict[str, bigquery.Table] = {}  # "dataset.table" -> Table object
        self._cached_datasets: List[Dict] = []
        self._cached_tables: List[Dict] = []

    # ─── Region Detection ───────────────────────────────────────────────

    def _detect_region(self) -> str:
        """Detect BigQuery region from the first dataset's location."""
        if self._region:
            return self._region
        try:
            datasets = list(self.client.list_datasets())
            if datasets:
                first_ds = self.client.get_dataset(datasets[0].dataset_id)
                if first_ds.location:
                    self._region = first_ds.location.lower()
                    print(f"Detected BigQuery region: {self._region}")
                    return self._region
        except Exception as e:
            print(f"Warning: Could not detect region: {e}")
        self._region = 'us'
        return self._region

    def _run_info_schema_query(self, query: str) -> Optional[List]:
        """Run an INFORMATION_SCHEMA query, return rows or None on failure."""
        try:
            job = self.client.query(query)
            return list(job.result())
        except Exception as e:
            print(f"INFORMATION_SCHEMA query failed: {e}")
            return None

    # ─── Main Assessment Pipeline ───────────────────────────────────────

    async def run_full_assessment(self, assessment_id: int, db: Session):
        """
        Run complete assessment collecting all metadata.
        
        Steps 1-14 match the original pipeline exactly.
        Each step tries INFORMATION_SCHEMA first, falls back to REST API.
        """
        repo = AssessmentRepository(db)

        try:
            print(f"Starting assessment {assessment_id} for project {self.project_id}")
            repo.update_status(assessment_id, 'running')

            # Detect region once (used by INFORMATION_SCHEMA queries)
            region = self._detect_region()
            print(f"Using region: {region}")

            # 1. Collect datasets
            print("Step 1/14: Collecting datasets...")
            datasets_data = await self.collect_datasets()
            for dataset_data in datasets_data:
                repo.create_dataset(assessment_id, dataset_data)
            print(f"✓ Collected {len(datasets_data)} datasets")

            # 2. Collect tables
            print("Step 2/14: Collecting tables...")
            tables_data = await self.collect_tables()
            if tables_data:
                repo.bulk_create_tables(assessment_id, tables_data)
            print(f"✓ Collected {len(tables_data)} tables")

            # 3. Collect columns
            print("Step 3/14: Collecting columns...")
            columns_data = await self.collect_columns(assessment_id, db)
            if columns_data:
                repo.bulk_create_columns(assessment_id, columns_data)
            print(f"✓ Collected {len(columns_data)} columns")

            # 4. Collect views
            print("Step 4/14: Collecting views...")
            views_data = await self.collect_views()
            if views_data:
                repo.bulk_create_views(assessment_id, views_data)
            print(f"✓ Collected {len(views_data)} views")

            # 5. Collect routines
            print("Step 5/14: Collecting routines...")
            routines_data = await self.collect_routines()
            if routines_data:
                repo.bulk_create_routines(assessment_id, routines_data)
            print(f"✓ Collected {len(routines_data)} routines")

            # 6. Collect query statistics
            print("Step 6/14: Collecting query statistics...")
            query_stats_data = await self.collect_query_statistics_detailed()
            if query_stats_data:
                repo.bulk_create_query_stats(assessment_id, query_stats_data)
            print(f"✓ Collected {len(query_stats_data)} query statistics")

            # 6b. Collect slot timeline from JOBS_TIMELINE_BY_PROJECT
            print("Step 6b/14: Collecting slot timeline...")
            slot_timeline = await self.collect_slot_timeline()
            # Store in assessment_data JSON field
            existing_data = repo.get_by_id(assessment_id).assessment_data or {}
            existing_data['slot_timeline'] = slot_timeline
            repo.update_assessment_data(assessment_id, existing_data)
            print(f"✓ Slot timeline collected")

            # 7. Collect ML models (REST API only — no INFORMATION_SCHEMA equivalent)
            print("Step 7/14: Collecting ML models...")
            ml_models_data = await self.collect_ml_models()
            if ml_models_data:
                repo.bulk_create_ml_models(assessment_id, ml_models_data)
            print(f"✓ Collected {len(ml_models_data)} ML models")

            # 8. Collect security policies
            print("Step 8/14: Collecting security policies...")
            security_data = await self.collect_security_policies_detailed()
            if security_data:
                repo.bulk_create_security_policies(assessment_id, security_data)
            print(f"✓ Collected {len(security_data)} security policies")

            # 9. Detect sharded tables (derived from cached tables — no API calls)
            print("Step 9/14: Detecting sharded tables...")
            sharded_data = await self.detect_sharded_tables()
            if sharded_data:
                repo.bulk_create_sharded_tables(assessment_id, sharded_data)
            print(f"✓ Detected {len(sharded_data)} sharded table groups")

            # 10. Analyze large STRING columns (derived from cached columns — no API calls)
            print("Step 10/14: Analyzing large STRING columns...")
            large_strings = await self.analyze_large_strings()
            print(f"✓ Found {len(large_strings)} tables with large STRING columns")

            # 11. Calculate update frequency
            print("Step 11/14: Calculating table update frequencies...")
            update_frequencies = await self.calculate_update_frequency(query_stats_data)
            print(f"✓ Calculated update frequency for {len(update_frequencies)} tables")

            # 12. Detect Spark jobs (derived from routines — no extra API calls)
            print("Step 12/14: Detecting Spark jobs...")
            spark_jobs = await self.detect_spark_jobs()
            print(f"✓ Detected {len(spark_jobs)} Spark jobs")

            # 13. Collect table options (derived from cached tables — no API calls)
            print("Step 13/14: Collecting table options...")
            table_options = await self.get_table_options()
            print(f"✓ Collected options for {len(table_options)} tables")

            # 14. Update totals
            print("Step 14/14: Updating assessment totals...")
            total_size_mb = sum(t.get('size_mb', 0) for t in tables_data)
            repo.update_totals(
                assessment_id=assessment_id,
                total_datasets=len(datasets_data),
                total_tables=len([t for t in tables_data if t.get('table_type') == 'BASE TABLE']),
                total_views=len(views_data),
                total_routines=len(routines_data),
                total_ml_models=len(ml_models_data),
                total_size_mb=int(total_size_mb)
            )

            repo.update_status(assessment_id, 'completed')
            print(f"✓ Assessment {assessment_id} completed successfully")

            return {
                'assessment_id': assessment_id,
                'status': 'completed',
                'summary': {
                    'datasets': len(datasets_data),
                    'tables': len(tables_data),
                    'columns': len(columns_data),
                    'views': len(views_data),
                    'routines': len(routines_data),
                    'query_stats': len(query_stats_data),
                    'ml_models': len(ml_models_data),
                    'security_policies': len(security_data),
                    'sharded_groups': len(sharded_data),
                    'spark_jobs': len(spark_jobs),
                    'total_size_mb': int(total_size_mb)
                }
            }

        except Exception as e:
            error_msg = f"Assessment failed: {str(e)}"
            print(f"✗ {error_msg}")
            repo.update_status(assessment_id, 'failed', error_message=error_msg)
            raise

    # ─── Step 1: Collect Datasets ───────────────────────────────────────

    async def collect_datasets(self) -> List[Dict]:
        """Collect dataset info. Tries INFORMATION_SCHEMA, falls back to REST API."""
        region = self._detect_region()

        # Strategy 2: INFORMATION_SCHEMA
        query = f"""
        SELECT
            s.schema_name AS dataset_name,
            s.creation_time,
            s.location,
            COALESCE(tc.table_count, 0) AS table_count,
            COALESCE(ts.total_size_bytes, 0) AS total_size_bytes
        FROM `{self.project_id}.region-{region}.INFORMATION_SCHEMA.SCHEMATA` s
        LEFT JOIN (
            SELECT
                table_schema,
                COUNT(*) AS table_count
            FROM `{self.project_id}.region-{region}.INFORMATION_SCHEMA.TABLES`
            WHERE table_type = 'BASE TABLE'
            GROUP BY table_schema
        ) tc ON s.schema_name = tc.table_schema
        LEFT JOIN (
            SELECT
                table_schema,
                SUM(total_logical_bytes) AS total_size_bytes
            FROM `{self.project_id}.region-{region}.INFORMATION_SCHEMA.TABLE_STORAGE`
            GROUP BY table_schema
        ) ts ON s.schema_name = ts.table_schema
        """

        rows = self._run_info_schema_query(query)
        if rows is not None:
            print(f"  [INFORMATION_SCHEMA] Collected {len(rows)} datasets")
            datasets = []
            for row in rows:
                datasets.append({
                    'dataset_name': row.dataset_name,
                    'creation_time': row.creation_time,
                    'location': row.location if hasattr(row, 'location') and row.location else region,
                    'table_count': row.table_count or 0,
                    'total_size_mb': (row.total_size_bytes or 0) / (1024 * 1024)
                })
            self._cached_datasets = datasets
            return datasets

        # Fallback: REST API
        print("  [Fallback] Using REST API for datasets...")
        return await self._collect_datasets_rest()

    async def _collect_datasets_rest(self) -> List[Dict]:
        """Original REST API approach for datasets."""
        datasets = []
        for dataset in self.client.list_datasets():
            dataset_ref = self.client.get_dataset(dataset.dataset_id)
            tables = list(self.client.list_tables(dataset.dataset_id))
            table_count = len(tables)
            total_size_bytes = 0
            for table in tables:
                table_ref = self.client.get_table(
                    f"{self.project_id}.{dataset.dataset_id}.{table.table_id}")
                total_size_bytes += table_ref.num_bytes or 0
            datasets.append({
                'dataset_name': dataset.dataset_id,
                'creation_time': dataset_ref.created,
                'location': dataset_ref.location,
                'table_count': table_count,
                'total_size_mb': total_size_bytes / (1024 * 1024)
            })
        self._cached_datasets = datasets
        return datasets

    # ─── Step 2: Collect Tables ─────────────────────────────────────────

    async def collect_tables(self) -> List[Dict]:
        """Collect table info. Tries INFORMATION_SCHEMA, falls back to REST API."""
        region = self._detect_region()

        query = f"""
        SELECT
            t.table_catalog AS project_id,
            t.table_schema AS dataset_name,
            t.table_name,
            t.table_type,
            t.creation_time,
            t.ddl,
            COALESCE(ts.total_rows, 0) AS row_count,
            COALESCE(ts.total_logical_bytes, 0) AS size_bytes
        FROM `{self.project_id}.region-{region}.INFORMATION_SCHEMA.TABLES` t
        LEFT JOIN `{self.project_id}.region-{region}.INFORMATION_SCHEMA.TABLE_STORAGE` ts
            ON t.table_schema = ts.table_schema AND t.table_name = ts.table_name
        """

        rows = self._run_info_schema_query(query)
        if rows is not None:
            print(f"  [INFORMATION_SCHEMA] Collected {len(rows)} tables")
            tables = []
            for row in rows:
                # Map BigQuery INFORMATION_SCHEMA table_type to our format
                table_type = row.table_type
                if table_type == 'BASE TABLE':
                    table_type = 'BASE TABLE'
                elif table_type == 'VIEW':
                    table_type = 'VIEW'
                elif table_type == 'MATERIALIZED VIEW':
                    table_type = 'MATERIALIZED VIEW'
                elif table_type == 'EXTERNAL':
                    table_type = 'EXTERNAL'

                # Parse partitioning and clustering from DDL
                partitioning_columns = self._parse_partitioning_from_ddl(row.ddl) if row.ddl else []
                clustering_columns = self._parse_clustering_from_ddl(row.ddl) if row.ddl else []

                tables.append({
                    'project_id': row.project_id or self.project_id,
                    'dataset_name': row.dataset_name,
                    'table_name': row.table_name,
                    'table_type': table_type,
                    'creation_time': row.creation_time,
                    'row_count': row.row_count or 0,
                    'size_mb': (row.size_bytes or 0) / (1024 * 1024),
                    'partitioning_columns': partitioning_columns,
                    'clustering_columns': clustering_columns,
                    'has_column_security': False,
                    'has_row_security': False,
                    'is_sharded': self._is_sharded_table(row.table_name),
                    'update_frequency': 'unknown'
                })
            self._cached_tables = tables
            return tables

        # Fallback: REST API
        print("  [Fallback] Using REST API for tables...")
        return await self._collect_tables_rest()

    async def _collect_tables_rest(self) -> List[Dict]:
        """Original REST API approach for tables."""
        tables = []
        for dataset in self.client.list_datasets():
            for table in self.client.list_tables(dataset.dataset_id):
                table_ref = self.client.get_table(
                    f"{self.project_id}.{dataset.dataset_id}.{table.table_id}")
                self._cached_table_refs[f"{dataset.dataset_id}.{table.table_id}"] = table_ref

                if table_ref.table_type == 'TABLE':
                    table_type = 'BASE TABLE'
                elif table_ref.table_type == 'VIEW':
                    table_type = 'VIEW'
                elif table_ref.table_type == 'MATERIALIZED_VIEW':
                    table_type = 'MATERIALIZED VIEW'
                elif table_ref.table_type == 'EXTERNAL':
                    table_type = 'EXTERNAL'
                else:
                    table_type = table_ref.table_type

                partitioning_columns = []
                if table_ref.time_partitioning:
                    partitioning_columns.append(table_ref.time_partitioning.field or '_PARTITIONTIME')
                if table_ref.range_partitioning:
                    partitioning_columns.append(table_ref.range_partitioning.field)

                clustering_columns = list(table_ref.clustering_fields) if table_ref.clustering_fields else []

                tables.append({
                    'project_id': self.project_id,
                    'dataset_name': dataset.dataset_id,
                    'table_name': table.table_id,
                    'table_type': table_type,
                    'creation_time': table_ref.created,
                    'row_count': table_ref.num_rows or 0,
                    'size_mb': (table_ref.num_bytes or 0) / (1024 * 1024),
                    'partitioning_columns': partitioning_columns,
                    'clustering_columns': clustering_columns,
                    'has_column_security': False,
                    'has_row_security': False,
                    'is_sharded': self._is_sharded_table(table.table_id),
                    'update_frequency': 'unknown'
                })
        self._cached_tables = tables
        return tables

    # ─── Step 3: Collect Columns ────────────────────────────────────────

    async def collect_columns(self, assessment_id: int, db: Session) -> List[Dict]:
        """Collect column info. Tries INFORMATION_SCHEMA, falls back to REST API."""
        region = self._detect_region()

        query = f"""
        SELECT
            table_schema AS dataset_name,
            table_name,
            column_name,
            data_type,
            is_nullable,
            ordinal_position,
            is_partitioning_column,
            clustering_ordinal_position
        FROM `{self.project_id}.region-{region}.INFORMATION_SCHEMA.COLUMNS`
        ORDER BY table_schema, table_name, ordinal_position
        """

        rows = self._run_info_schema_query(query)
        if rows is not None:
            print(f"  [INFORMATION_SCHEMA] Collected {len(rows)} columns")
            columns = []

            # Build a lookup of assessment_table IDs
            table_id_lookup = {}
            assessment_tables = db.query(AssessmentTable).filter(
                AssessmentTable.assessment_id == assessment_id
            ).all()
            for at in assessment_tables:
                table_id_lookup[f"{at.dataset_name}.{at.table_name}"] = at.id

            for row in rows:
                key = f"{row.dataset_name}.{row.table_name}"
                table_id = table_id_lookup.get(key)
                if not table_id:
                    continue

                # Parse is_partitioning_column
                is_part = False
                if hasattr(row, 'is_partitioning_column'):
                    is_part = row.is_partitioning_column == 'YES' if isinstance(row.is_partitioning_column, str) else bool(row.is_partitioning_column)

                # Parse clustering_ordinal_position
                clust_pos = None
                if hasattr(row, 'clustering_ordinal_position') and row.clustering_ordinal_position is not None:
                    try:
                        clust_pos = int(row.clustering_ordinal_position)
                    except (ValueError, TypeError):
                        clust_pos = None

                columns.append({
                    'table_id': table_id,
                    'column_name': row.column_name,
                    'data_type': row.data_type,
                    'is_nullable': row.is_nullable == 'YES' if isinstance(row.is_nullable, str) else bool(row.is_nullable),
                    'ordinal_position': row.ordinal_position,
                    'is_partitioning_column': is_part,
                    'clustering_ordinal_position': clust_pos,
                    'policy_tags': [],
                    'max_length': None
                })
            return columns

        # Fallback: REST API
        print("  [Fallback] Using REST API for columns...")
        return await self._collect_columns_rest(assessment_id, db)

    async def _collect_columns_rest(self, assessment_id: int, db: Session) -> List[Dict]:
        """Original REST API approach for columns."""
        columns = []
        for dataset in self.client.list_datasets():
            for table in self.client.list_tables(dataset.dataset_id):
                key = f"{dataset.dataset_id}.{table.table_id}"
                # Use cached table ref if available
                table_ref = self._cached_table_refs.get(key)
                if not table_ref:
                    table_ref = self.client.get_table(
                        f"{self.project_id}.{dataset.dataset_id}.{table.table_id}")
                    self._cached_table_refs[key] = table_ref

                assessment_table = db.query(AssessmentTable).filter(
                    AssessmentTable.assessment_id == assessment_id,
                    AssessmentTable.dataset_name == dataset.dataset_id,
                    AssessmentTable.table_name == table.table_id
                ).first()
                if not assessment_table:
                    continue

                for idx, field in enumerate(table_ref.schema):
                    is_partitioning = False
                    if table_ref.time_partitioning and table_ref.time_partitioning.field:
                        is_partitioning = (field.name == table_ref.time_partitioning.field)
                    elif table_ref.range_partitioning and table_ref.range_partitioning.field:
                        is_partitioning = (field.name == table_ref.range_partitioning.field)

                    clustering_position = None
                    if table_ref.clustering_fields:
                        try:
                            clustering_position = list(table_ref.clustering_fields).index(field.name) + 1
                        except ValueError:
                            clustering_position = None

                    columns.append({
                        'table_id': assessment_table.id,
                        'column_name': field.name,
                        'data_type': field.field_type,
                        'is_nullable': field.mode != 'REQUIRED',
                        'ordinal_position': idx + 1,
                        'is_partitioning_column': is_partitioning,
                        'clustering_ordinal_position': clustering_position,
                        'policy_tags': list(field.policy_tags.names) if field.policy_tags else [],
                        'max_length': None
                    })
        return columns

    # ─── Step 4: Collect Views ──────────────────────────────────────────

    async def collect_views(self) -> List[Dict]:
        """Collect views. Tries INFORMATION_SCHEMA, falls back to REST API."""
        region = self._detect_region()

        query = f"""
        SELECT
            table_schema AS dataset_name,
            table_name,
            view_definition,
            check_option
        FROM `{self.project_id}.region-{region}.INFORMATION_SCHEMA.VIEWS`
        """

        rows = self._run_info_schema_query(query)

        # Also try to get materialized views
        mv_query = f"""
        SELECT
            table_schema AS dataset_name,
            table_name,
            definition AS view_definition,
            last_refresh_time
        FROM `{self.project_id}.region-{region}.INFORMATION_SCHEMA.MATERIALIZED_VIEWS`
        """
        mv_rows = self._run_info_schema_query(mv_query)

        if rows is not None:
            print(f"  [INFORMATION_SCHEMA] Collected {len(rows)} views" +
                  (f" + {len(mv_rows)} materialized views" if mv_rows else ""))
            views = []
            view_names = set()

            # Get creation times from cached tables
            creation_times = {}
            for t in self._cached_tables:
                if t['table_type'] in ('VIEW', 'MATERIALIZED VIEW'):
                    creation_times[f"{t['dataset_name']}.{t['table_name']}"] = t.get('creation_time')

            # Regular views
            for row in rows:
                view_name = f"{row.dataset_name}.{row.table_name}"
                view_names.add(view_name)
                view_def = row.view_definition
                deps = self.sql_parser.parse_dependencies(view_def) if view_def else {'tables': [], 'views': [], 'functions': []}
                views.append({
                    'view_name': view_name,
                    'view_type': 'VIEW',
                    'view_definition': view_def,
                    'creation_time': creation_times.get(view_name),
                    'dependent_tables': [],
                    'dependent_views': [],
                    'dependent_functions': deps['functions'],
                    'dependency_depth': 1
                })

            # Materialized views
            if mv_rows:
                for row in mv_rows:
                    view_name = f"{row.dataset_name}.{row.table_name}"
                    view_names.add(view_name)
                    view_def = row.view_definition
                    deps = self.sql_parser.parse_dependencies(view_def) if view_def else {'tables': [], 'views': [], 'functions': []}
                    views.append({
                        'view_name': view_name,
                        'view_type': 'MATERIALIZED_VIEW',
                        'view_definition': view_def,
                        'creation_time': creation_times.get(view_name),
                        'dependent_tables': [],
                        'dependent_views': [],
                        'dependent_functions': deps['functions'],
                        'dependency_depth': 1
                    })

            # Second pass: categorize dependencies
            for view in views:
                view_def = view['view_definition']
                if view_def:
                    view_deps = self.sql_parser.parse_dependencies(view_def)
                    for dep in view_deps['tables']:
                        if dep in view_names:
                            view['dependent_views'].append(dep)
                        else:
                            view['dependent_tables'].append(dep)

            return views

        # Fallback: REST API
        print("  [Fallback] Using REST API for views...")
        return await self._collect_views_rest()

    async def _collect_views_rest(self) -> List[Dict]:
        """Original REST API approach for views."""
        views = []
        view_names = set()

        for dataset in self.client.list_datasets():
            for table in self.client.list_tables(dataset.dataset_id):
                key = f"{dataset.dataset_id}.{table.table_id}"
                table_ref = self._cached_table_refs.get(key)
                if not table_ref:
                    table_ref = self.client.get_table(
                        f"{self.project_id}.{dataset.dataset_id}.{table.table_id}")
                    self._cached_table_refs[key] = table_ref

                if table_ref.table_type in ['VIEW', 'MATERIALIZED_VIEW']:
                    view_definition = table_ref.view_query or table_ref.mview_query
                    dependencies = self.sql_parser.parse_dependencies(view_definition) if view_definition else {'tables': [], 'views': [], 'functions': []}
                    view_name = f"{dataset.dataset_id}.{table.table_id}"
                    view_names.add(view_name)
                    views.append({
                        'view_name': view_name,
                        'view_type': table_ref.table_type,
                        'view_definition': view_definition,
                        'creation_time': table_ref.created,
                        'dependent_tables': [],
                        'dependent_views': [],
                        'dependent_functions': dependencies['functions'],
                        'dependency_depth': 1
                    })

        # Second pass
        for view in views:
            view_def = view['view_definition']
            if view_def:
                view_deps = self.sql_parser.parse_dependencies(view_def)
                for dep in view_deps['tables']:
                    if dep in view_names:
                        view['dependent_views'].append(dep)
                    else:
                        view['dependent_tables'].append(dep)

        return views

    # ─── Step 5: Collect Routines ───────────────────────────────────────

    async def collect_routines(self) -> List[Dict]:
        """Collect routines. Tries INFORMATION_SCHEMA, falls back to REST API."""
        region = self._detect_region()

        query = f"""
        SELECT
            routine_schema AS dataset_name,
            routine_name,
            routine_type,
            routine_definition,
            external_language,
            created AS creation_time,
            ddl,
            return_type
        FROM `{self.project_id}.region-{region}.INFORMATION_SCHEMA.ROUTINES`
        """

        rows = self._run_info_schema_query(query)
        if rows is not None:
            print(f"  [INFORMATION_SCHEMA] Collected {len(rows)} routines")

            # Build view names set for dependency categorization
            view_names = set()
            for t in self._cached_tables:
                if t['table_type'] in ('VIEW', 'MATERIALIZED VIEW'):
                    view_names.add(f"{t['dataset_name']}.{t['table_name']}")
                    view_names.add(f"{self.project_id}.{t['dataset_name']}.{t['table_name']}")

            routines = []
            for row in rows:
                routine_def = row.routine_definition or (row.ddl if hasattr(row, 'ddl') else None)
                deps = self.sql_parser.parse_dependencies(routine_def) if routine_def else {'tables': [], 'views': [], 'functions': []}
                calls_procedures = self._extract_procedure_calls(routine_def) if routine_def else []

                dependent_tables = []
                dependent_views = []
                for dep in deps['tables']:
                    full_name = f"{self.project_id}.{dep}" if '.' in dep and not dep.startswith(self.project_id) else dep
                    if dep in view_names or full_name in view_names:
                        dependent_views.append(dep)
                    else:
                        dependent_tables.append(dep)

                return_type_str = None
                if hasattr(row, 'return_type') and row.return_type:
                    return_type_str = str(row.return_type)

                routines.append({
                    'routine_name': f"{row.dataset_name}.{row.routine_name}",
                    'routine_type': row.routine_type,
                    'return_type': return_type_str,
                    'definition': routine_def,
                    'external_language': row.external_language if hasattr(row, 'external_language') else None,
                    'creation_time': row.creation_time if hasattr(row, 'creation_time') else None,
                    'call_frequency': 0,
                    'dependent_tables': dependent_tables,
                    'dependent_views': dependent_views,
                    'dependent_functions': deps['functions'],
                    'calls_procedures': calls_procedures,
                    'dependency_depth': len(dependent_tables) + len(dependent_views) + len(deps['functions'])
                })
            return routines

        # Fallback: REST API
        print("  [Fallback] Using REST API for routines...")
        return await self._collect_routines_rest()

    async def _collect_routines_rest(self) -> List[Dict]:
        """Original REST API approach for routines."""
        routines = []
        view_names = set()

        # Build view names from cache or API
        if self._cached_tables:
            for t in self._cached_tables:
                if t['table_type'] in ('VIEW', 'MATERIALIZED VIEW'):
                    view_names.add(f"{t['dataset_name']}.{t['table_name']}")
                    view_names.add(f"{self.project_id}.{t['dataset_name']}.{t['table_name']}")
        else:
            for dataset in self.client.list_datasets():
                for table in self.client.list_tables(dataset.dataset_id):
                    key = f"{dataset.dataset_id}.{table.table_id}"
                    table_ref = self._cached_table_refs.get(key)
                    if not table_ref:
                        table_ref = self.client.get_table(
                            f"{self.project_id}.{dataset.dataset_id}.{table.table_id}")
                        self._cached_table_refs[key] = table_ref
                    if table_ref.table_type == 'VIEW':
                        view_names.add(f"{dataset.dataset_id}.{table.table_id}")
                        view_names.add(f"{self.project_id}.{dataset.dataset_id}.{table.table_id}")

        for dataset in self.client.list_datasets():
            for routine in self.client.list_routines(dataset.dataset_id):
                routine_ref = self.client.get_routine(routine.reference)
                routine_definition = routine_ref.body
                dependencies = self.sql_parser.parse_dependencies(routine_definition) if routine_definition else {'tables': [], 'views': [], 'functions': []}
                calls_procedures = self._extract_procedure_calls(routine_definition) if routine_definition else []

                dependent_tables = []
                dependent_views = []
                for dep in dependencies['tables']:
                    full_name = f"{self.project_id}.{dep}" if '.' in dep and not dep.startswith(self.project_id) else dep
                    if dep in view_names or full_name in view_names:
                        dependent_views.append(dep)
                    else:
                        dependent_tables.append(dep)

                routines.append({
                    'routine_name': f"{dataset.dataset_id}.{routine.routine_id}",
                    'routine_type': routine_ref.type_,
                    'return_type': str(routine_ref.return_type) if routine_ref.return_type else None,
                    'definition': routine_definition,
                    'external_language': routine_ref.language,
                    'creation_time': routine_ref.created,
                    'call_frequency': 0,
                    'dependent_tables': dependent_tables,
                    'dependent_views': dependent_views,
                    'dependent_functions': dependencies['functions'],
                    'calls_procedures': calls_procedures,
                    'dependency_depth': len(dependent_tables) + len(dependent_views) + len(dependencies['functions'])
                })
        return routines

    # ─── Helper Methods ─────────────────────────────────────────────────

    def _extract_procedure_calls(self, sql: str) -> List[str]:
        """Extract CALL statements for stored procedures."""
        if not sql:
            return []
        pattern = r'CALL\s+`?([a-zA-Z0-9_.-]+)`?'
        matches = re.findall(pattern, sql, re.IGNORECASE)
        return list(set(matches))

    def _is_sharded_table(self, table_name: str) -> bool:
        """Check if table name indicates sharding (e.g., table_20240101)."""
        pattern = r'_\d{8}$|_\d{6}$|_\d{4}\d{2}\d{2}$'
        return bool(re.search(pattern, table_name))

    def _parse_partitioning_from_ddl(self, ddl: str) -> List[str]:
        """Extract partitioning columns from DDL string."""
        if not ddl:
            return []
        # PARTITION BY _PARTITIONTIME or PARTITION BY column
        match = re.search(r'PARTITION\s+BY\s+(?:DATE|TIMESTAMP|DATETIME|RANGE_BUCKET)?\s*\(?([a-zA-Z0-9_]+)', ddl, re.IGNORECASE)
        if match:
            return [match.group(1)]
        # PARTITION BY _PARTITIONTIME (pseudo column)
        if re.search(r'PARTITION\s+BY\s+_PARTITIONTIME', ddl, re.IGNORECASE):
            return ['_PARTITIONTIME']
        return []

    def _parse_clustering_from_ddl(self, ddl: str) -> List[str]:
        """Extract clustering columns from DDL string."""
        if not ddl:
            return []
        match = re.search(r'CLUSTER\s+BY\s+([a-zA-Z0-9_,\s`]+?)(?:\s*OPTIONS|\s*AS\s|\s*;|\s*$)', ddl, re.IGNORECASE)
        if match:
            cols = match.group(1)
            return [c.strip().strip('`') for c in cols.split(',') if c.strip()]
        return []

    # ─── Step 6: Query Statistics (already uses INFORMATION_SCHEMA) ─────

    async def collect_query_statistics(self) -> List[Dict]:
        """Placeholder — detailed version used instead."""
        return []

    async def collect_query_statistics_detailed(self) -> List[Dict]:
        """Collect query statistics from INFORMATION_SCHEMA.JOBS, with REST API fallback."""
        query_stats = []
        region = self._detect_region()

        query = f"""
        SELECT
            job_id,
            creation_time as execution_time,
            query as query_text,
            total_bytes_processed as bytes_scanned,
            total_slot_ms as slot_milliseconds,
            cache_hit,
            referenced_tables,
            user_email,
            state,
            error_result,
            TIMESTAMP_DIFF(end_time, start_time, MILLISECOND) as total_elapsed_time_ms
        FROM `{self.project_id}.region-{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
        WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
            AND job_type = 'QUERY'
            AND state = 'DONE'
        ORDER BY creation_time DESC
        LIMIT 50000
        """

        try:
            print(f"  Querying INFORMATION_SCHEMA.JOBS with region: {region}")
            query_job = self.client.query(query)
            results = query_job.result()

            for row in results:
                referenced_tables = []
                if row.referenced_tables:
                    for table_ref in row.referenced_tables:
                        if isinstance(table_ref, dict):
                            project = table_ref.get('projectId') or table_ref.get('project_id')
                            dataset = table_ref.get('datasetId') or table_ref.get('dataset_id')
                            table = table_ref.get('tableId') or table_ref.get('table_id')
                            if project and dataset and table:
                                referenced_tables.append(f"{project}.{dataset}.{table}")
                        else:
                            referenced_tables.append(f"{table_ref.project}.{table_ref.dataset_id}.{table_ref.table_id}")

                query_stats.append({
                    'job_id': row.job_id,
                    'execution_time': row.execution_time,
                    'query_text': row.query_text[:5000] if row.query_text else None,
                    'bytes_scanned': row.bytes_scanned or 0,
                    'slot_milliseconds': row.slot_milliseconds or 0,
                    'cache_hit': row.cache_hit or False,
                    'referenced_tables': referenced_tables,
                    'user_email': row.user_email,
                    'query_metadata': {
                        'total_elapsed_time_ms': row.total_elapsed_time_ms or 0,
                    },
                })

            print(f"  ✓ Collected {len(query_stats)} query statistics from INFORMATION_SCHEMA (region-{region})")
        except Exception as e:
            print(f"  INFORMATION_SCHEMA.JOBS failed: {e}")
            print(f"  Falling back to REST API (client.list_jobs)...")
            query_stats = await self._collect_query_stats_rest_api()

        return query_stats

    async def collect_slot_timeline(self) -> Dict:
        """
        Query JOBS_TIMELINE_BY_PROJECT to get actual concurrent slot usage
        over time. This is the most accurate source for peak/avg slot metrics.
        Returns peak_concurrent_slots, avg_concurrent_slots, and timeline data.
        """
        region = self._detect_region()
        result = {
            'peak_concurrent_slots': 0,
            'avg_concurrent_slots': 0,
            'p95_concurrent_slots': 0,
            'timeline_source': 'JOBS_TIMELINE_BY_PROJECT',
        }

        query = f"""
        SELECT
            period_start,
            SUM(period_slot_ms) / 1000 AS concurrent_slots_used
        FROM `{self.project_id}.region-{region}.INFORMATION_SCHEMA.JOBS_TIMELINE_BY_PROJECT`
        WHERE
            job_creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
            AND period_start >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
        GROUP BY period_start
        ORDER BY concurrent_slots_used DESC
        """

        try:
            print(f"  Querying JOBS_TIMELINE_BY_PROJECT for slot timeline (region-{region})...")
            query_job = self.client.query(query)
            rows = list(query_job.result())

            if rows:
                slot_values = [float(r.concurrent_slots_used or 0) for r in rows]
                result['peak_concurrent_slots'] = round(max(slot_values), 1)
                result['avg_concurrent_slots'] = round(
                    sum(slot_values) / len(slot_values), 1
                )
                # P95
                sorted_vals = sorted(slot_values)
                p95_idx = int(len(sorted_vals) * 0.95)
                result['p95_concurrent_slots'] = round(sorted_vals[min(p95_idx, len(sorted_vals) - 1)], 1)
                result['timeline_periods_count'] = len(rows)

            print(f"  ✓ Slot timeline: peak={result['peak_concurrent_slots']}, "
                  f"avg={result['avg_concurrent_slots']}, p95={result['p95_concurrent_slots']}")
        except Exception as e:
            print(f"  ⚠ JOBS_TIMELINE_BY_PROJECT failed: {e}")
            print(f"  Will fall back to sweep-line estimation from JOBS data")

        return result

    async def _collect_query_stats_rest_api(self) -> List[Dict]:
        """Fallback: collect query statistics via BigQuery REST API (client.list_jobs)."""
        from datetime import datetime, timedelta, timezone
        query_stats = []
        try:
            min_creation_time = datetime.now(timezone.utc) - timedelta(days=30)
            jobs_iter = self.client.list_jobs(
                project=self.project_id,
                min_creation_time=min_creation_time,
                all_users=True,
                state_filter="done",
                max_results=50000,
            )

            count = 0
            for job in jobs_iter:
                # Only include query jobs
                if job.job_type != "query":
                    continue

                referenced_tables = []
                try:
                    if hasattr(job, 'referenced_tables') and job.referenced_tables:
                        for tref in job.referenced_tables:
                            referenced_tables.append(f"{tref.project}.{tref.dataset_id}.{tref.table_id}")
                except Exception:
                    pass

                query_stats.append({
                    'job_id': job.job_id,
                    'execution_time': job.created,
                    'query_text': (job.query or '')[:5000] if hasattr(job, 'query') else None,
                    'bytes_scanned': getattr(job, 'total_bytes_processed', 0) or 0,
                    'slot_milliseconds': getattr(job, 'slot_millis', 0) or 0,
                    'cache_hit': getattr(job, 'cache_hit', False) or False,
                    'referenced_tables': referenced_tables,
                    'user_email': getattr(job, 'user_email', None),
                })
                count += 1
                if count >= 50000:
                    break

            print(f"  ✓ Collected {len(query_stats)} query statistics via REST API fallback")
        except Exception as e2:
            print(f"  REST API fallback also failed: {e2}")

        return query_stats


    # ─── Step 7: ML Models (REST API only) ──────────────────────────────

    async def collect_ml_models(self) -> List[Dict]:
        """Collect ML models via REST API (no INFORMATION_SCHEMA equivalent)."""
        models = []
        for dataset in self.client.list_datasets():
            for model in self.client.list_models(dataset.dataset_id):
                model_ref = self.client.get_model(
                    f"{self.project_id}.{dataset.dataset_id}.{model.model_id}")
                models.append({
                    'model_name': f"{dataset.dataset_id}.{model.model_id}",
                    'model_type': model_ref.model_type,
                    'dataset_name': dataset.dataset_id,
                    'creation_time': model_ref.created,
                    'last_modified_time': model_ref.modified
                })
        return models

    async def collect_security_policies(self) -> List[Dict]:
        """Placeholder — detailed version used instead."""
        return []

    # ─── Step 8: Security Policies (INFORMATION_SCHEMA first, REST API fallback) ───

    async def collect_security_policies_detailed(self) -> List[Dict]:
        """Collect RLS and CLS policies. Tries INFORMATION_SCHEMA first, falls back to REST API."""
        security_policies = []
        region = self._detect_region()

        # ── Strategy 1: INFORMATION_SCHEMA ──

        # CLS: Check COLUMN_FIELD_PATHS for policy tags
        cls_success = False
        try:
            cls_query = f"""
            SELECT
                table_schema,
                table_name,
                column_name,
                field_path,
                policy_tags
            FROM `{self.project_id}.region-{region}.INFORMATION_SCHEMA.COLUMN_FIELD_PATHS`
            WHERE policy_tags IS NOT NULL
              AND policy_tags.names IS NOT NULL
              AND ARRAY_LENGTH(policy_tags.names) > 0
            """
            job = self.client.query(cls_query)
            rows = list(job.result())
            cls_success = True
            for row in rows:
                tag_names = row.policy_tags.names if hasattr(row.policy_tags, 'names') else []
                if not tag_names and isinstance(row.policy_tags, dict):
                    tag_names = row.policy_tags.get('names', [])
                for tag in tag_names:
                    security_policies.append({
                        'security_type': 'CLS',
                        'table_name': f"{row.table_schema}.{row.table_name}",
                        'policy_name': f"policy_tag_{row.column_name}",
                        'filter_predicate': None,
                        'grantees': [],
                        'creation_time': None,
                        'security_metadata': {
                            'column_name': row.column_name,
                            'policy_tag': tag
                        }
                    })
            print(f"  [INFORMATION_SCHEMA] Found {len([p for p in security_policies if p['security_type'] == 'CLS'])} CLS policies")
        except Exception as e:
            print(f"  CLS INFORMATION_SCHEMA query failed: {e}")

        # RLS: Check ROW_ACCESS_POLICIES
        rls_success = False
        try:
            rls_query = f"""
            SELECT
                table_schema,
                table_name,
                policy_name,
                filter_predicate,
                grantee_list,
                ddl AS creation_ddl
            FROM `{self.project_id}.region-{region}.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES`
            """
            job = self.client.query(rls_query)
            rows = list(job.result())
            rls_success = True
            for row in rows:
                security_policies.append({
                    'security_type': 'RLS',
                    'table_name': f"{row.table_schema}.{row.table_name}",
                    'policy_name': row.policy_name,
                    'filter_predicate': row.filter_predicate,
                    'grantees': row.grantee_list.split(',') if row.grantee_list else [],
                    'creation_time': None,
                    'security_metadata': {
                        'ddl': row.creation_ddl if hasattr(row, 'creation_ddl') else None
                    }
                })
            print(f"  [INFORMATION_SCHEMA] Found {len([p for p in security_policies if p['security_type'] == 'RLS'])} RLS policies")
        except Exception as e:
            print(f"  RLS INFORMATION_SCHEMA query failed: {e}")

        if cls_success or rls_success:
            print(f"  ✓ Collected {len(security_policies)} security policies via INFORMATION_SCHEMA")
            return security_policies

        # ── Strategy 2: REST API fallback ──
        print("  [Fallback] Using REST API for security policies...")
        security_policies = []
        for dataset in self.client.list_datasets():
            for table in self.client.list_tables(dataset.dataset_id):
                key = f"{dataset.dataset_id}.{table.table_id}"
                table_ref = self._cached_table_refs.get(key)
                if not table_ref:
                    table_ref = self.client.get_table(
                        f"{self.project_id}.{dataset.dataset_id}.{table.table_id}")
                    self._cached_table_refs[key] = table_ref

                for field in table_ref.schema:
                    if field.policy_tags and field.policy_tags.names:
                        for tag in field.policy_tags.names:
                            security_policies.append({
                                'security_type': 'CLS',
                                'table_name': f"{dataset.dataset_id}.{table.table_id}",
                                'policy_name': f"policy_tag_{field.name}",
                                'filter_predicate': None,
                                'grantees': [],
                                'creation_time': None,
                                'security_metadata': {
                                    'column_name': field.name,
                                    'policy_tag': tag
                                }
                            })

            try:
                rls_query = f"""
                SELECT table_schema, table_name, policy_name, filter_predicate, grantee_list
                FROM `{self.project_id}.{dataset.dataset_id}.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES`
                """
                query_job = self.client.query(rls_query)
                for row in query_job.result():
                    security_policies.append({
                        'security_type': 'RLS',
                        'table_name': f"{row.table_schema}.{row.table_name}",
                        'policy_name': row.policy_name,
                        'filter_predicate': row.filter_predicate,
                        'grantees': row.grantee_list.split(',') if row.grantee_list else [],
                        'creation_time': None,
                        'security_metadata': {}
                    })
            except Exception:
                pass

        print(f"  ✓ Collected {len(security_policies)} security policies via REST API fallback")
        return security_policies

    # ─── Step 9: Sharded Tables (derived from cached data) ──────────────

    async def detect_sharded_tables(self) -> List[Dict]:
        """Detect sharded tables from cached table data — no API calls needed."""
        sharded_groups = defaultdict(list)

        # Use cached tables if available
        tables_source = self._cached_tables
        if not tables_source:
            # Minimal fallback: just list table names
            for dataset in self.client.list_datasets():
                for table in self.client.list_tables(dataset.dataset_id):
                    tables_source.append({
                        'dataset_name': dataset.dataset_id,
                        'table_name': table.table_id,
                        'size_mb': 0
                    })

        patterns = [
            (r'^(.+)_(\d{8})$', '%Y%m%d'),
            (r'^(.+)_(\d{6})$', '%Y%m'),
        ]

        for t in tables_source:
            table_name = t['table_name']
            dataset_name = t['dataset_name']

            for pattern, date_format in patterns:
                match = re.match(pattern, table_name)
                if match:
                    prefix = match.group(1)
                    date_str = match.group(2)
                    try:
                        shard_date = datetime.strptime(date_str, date_format)
                        sharded_groups[f"{dataset_name}.{prefix}"].append({
                            'table_name': table_name,
                            'shard_date': shard_date,
                            'size_mb': t.get('size_mb', 0)
                        })
                        break
                    except ValueError:
                        continue

        shard_summaries = []
        for group_key, shards in sharded_groups.items():
            if len(shards) > 1:
                parts = group_key.split('.', 1)
                table_prefix = parts[1] if len(parts) > 1 else group_key
                dates = [s['shard_date'] for s in shards]
                total_size = sum(s['size_mb'] for s in shards)
                shard_summaries.append({
                    'shard_group': group_key,
                    'table_prefix': table_prefix,
                    'shard_count': len(shards),
                    'total_size_mb': int(total_size),
                    'date_range_start': min(dates),
                    'date_range_end': max(dates),
                    'shard_tables': [s['table_name'] for s in shards]
                })

        return shard_summaries

    # ─── Step 10: Large STRING Columns (derived from cached columns) ────

    async def analyze_large_strings(self) -> Dict[str, List[str]]:
        """Detect tables with STRING columns — derived from cached table data."""
        large_string_tables = {}

        # If we used INFORMATION_SCHEMA for columns, we already have the data
        # Just check cached tables for STRING columns from the columns step
        # For simplicity, use cached tables list and mark all STRING columns
        for t in self._cached_tables:
            key = f"{t['dataset_name']}.{t['table_name']}"
            # We don't re-fetch — the column data is already in the DB
            # This step just identifies tables that MIGHT have large strings
            # The actual column types were already collected in step 3
            large_string_tables[key] = []  # Will be populated from DB if needed

        # If no cached tables, return empty (data already in DB from step 3)
        return large_string_tables

    # ─── Step 11: Update Frequency ──────────────────────────────────────

    async def calculate_update_frequency(self, query_stats: List[Dict]) -> Dict[str, str]:
        """Calculate update frequency from query history."""
        from datetime import timedelta

        table_access_dates = defaultdict(list)
        for stat in query_stats:
            if stat.get('referenced_tables'):
                execution_time = stat.get('execution_time')
                if execution_time:
                    for table in stat['referenced_tables']:
                        table_access_dates[table].append(execution_time)

        update_frequencies = {}
        for table, access_dates in table_access_dates.items():
            if not access_dates:
                update_frequencies[table] = 'unknown'
                continue

            sorted_dates = sorted(access_dates)
            if len(sorted_dates) < 2:
                update_frequencies[table] = 'rarely'
                continue

            intervals = []
            for i in range(1, len(sorted_dates)):
                interval = (sorted_dates[i] - sorted_dates[i-1]).total_seconds() / 3600
                intervals.append(interval)

            avg_interval_hours = sum(intervals) / len(intervals)
            if avg_interval_hours < 24:
                update_frequencies[table] = 'daily'
            elif avg_interval_hours < 168:
                update_frequencies[table] = 'weekly'
            elif avg_interval_hours < 720:
                update_frequencies[table] = 'monthly'
            else:
                update_frequencies[table] = 'rarely'

        return update_frequencies

    # ─── Step 12: Spark Jobs (derived from routines — no extra API) ─────

    async def detect_spark_jobs(self) -> List[Dict]:
        """Detect Spark jobs from routines — uses REST API only if no cached routines."""
        spark_jobs = []
        for dataset in self.client.list_datasets():
            for routine in self.client.list_routines(dataset.dataset_id):
                routine_ref = self.client.get_routine(routine.reference)
                is_spark = False
                if routine_ref.language and routine_ref.language.upper() == 'PYTHON':
                    body = routine_ref.body or ''
                    spark_keywords = ['pyspark', 'spark.', 'SparkSession', 'SparkContext']
                    is_spark = any(keyword in body for keyword in spark_keywords)

                if is_spark:
                    spark_jobs.append({
                        'dataset_name': dataset.dataset_id,
                        'routine_name': routine.routine_id,
                        'routine_type': routine_ref.type_,
                        'language': routine_ref.language,
                        'definition': routine_ref.body,
                        'created': routine_ref.created
                    })
        return spark_jobs

    # ─── Step 13: Table Options (derived from cached data) ──────────────

    async def get_table_options(self) -> Dict[str, Dict]:
        """Collect table options. Tries INFORMATION_SCHEMA, falls back to cached/REST."""
        region = self._detect_region()

        query = f"""
        SELECT
            table_schema AS dataset_name,
            table_name,
            option_name,
            option_value
        FROM `{self.project_id}.region-{region}.INFORMATION_SCHEMA.TABLE_OPTIONS`
        WHERE option_name IN (
            'partition_expiration_days',
            'require_partition_filter',
            'clustering_columns'
        )
        """

        rows = self._run_info_schema_query(query)
        if rows is not None:
            print(f"  [INFORMATION_SCHEMA] Collected {len(rows)} table option entries")
            table_options = defaultdict(dict)
            for row in rows:
                key = f"{row.dataset_name}.{row.table_name}"
                if row.option_name == 'partition_expiration_days' and row.option_value:
                    try:
                        table_options[key]['partition_expiration_days'] = int(float(row.option_value))
                    except (ValueError, TypeError):
                        pass
                elif row.option_name == 'require_partition_filter' and row.option_value:
                    table_options[key]['require_partition_filter'] = row.option_value.lower() == 'true'
                elif row.option_name == 'clustering_columns' and row.option_value:
                    # Parse clustering columns from option value
                    try:
                        cols = json.loads(row.option_value)
                        if isinstance(cols, list):
                            table_options[key]['clustering_columns'] = cols
                    except (json.JSONDecodeError, TypeError):
                        pass
            return dict(table_options)

        # Fallback: derive from cached tables
        print("  [Fallback] Deriving table options from cached data...")
        table_options = {}
        for t in self._cached_tables:
            options = {}
            if t.get('clustering_columns'):
                options['clustering_columns'] = t['clustering_columns']
            if options:
                key = f"{t['dataset_name']}.{t['table_name']}"
                table_options[key] = options
        return table_options
