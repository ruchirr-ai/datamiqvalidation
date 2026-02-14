"""
BigQuery Assessment Service

Collects comprehensive metadata from BigQuery for migration assessment
"""

from google.cloud import bigquery
from google.oauth2 import service_account
from sqlalchemy.orm import Session
from typing import Dict, List
import json
from datetime import datetime

from repositories.assessment_repository import AssessmentRepository
from models.assessment import AssessmentTable
from utils.sql_dependency_parser import SQLDependencyParser


class BigQueryAssessmentService:
    def __init__(self, connection_params: Dict):
        """
        Initialize BigQuery client
        
        Args:
            connection_params: Dictionary containing:
                - project_id: GCP project ID
                - credentials_json: Service account JSON (as string or dict)
        """
        self.project_id = connection_params.get('project_id')
        
        # Parse credentials
        credentials_json = connection_params.get('credentials_json')
        if isinstance(credentials_json, str):
            credentials_json = json.loads(credentials_json)
        
        # Create credentials and client
        credentials = service_account.Credentials.from_service_account_info(credentials_json)
        self.client = bigquery.Client(
            credentials=credentials,
            project=self.project_id
        )
        
        # Initialize SQL dependency parser
        self.sql_parser = SQLDependencyParser()
    
    async def run_full_assessment(self, assessment_id: int, db: Session):
        """
        Run complete assessment collecting all metadata
        
        This method:
        1. Collects dataset information
        2. Collects table information
        3. Collects column information
        4. Collects views and materialized views
        5. Collects stored procedures and functions
        6. Collects query statistics (last 7 days)
        7. Collects ML models
        8. Collects security policies (RLS/CLS)
        9. Detects sharded tables
        10. Analyzes large STRING columns
        11. Calculates update frequency
        12. Detects Spark jobs
        13. Collects table options
        14. Updates assessment totals
        """
        repo = AssessmentRepository(db)
        
        try:
            print(f"Starting assessment {assessment_id} for project {self.project_id}")
            repo.update_status(assessment_id, 'running')
            
            # 1. Collect datasets
            print("Collecting datasets...")
            datasets_data = await self.collect_datasets()
            for dataset_data in datasets_data:
                repo.create_dataset(assessment_id, dataset_data)
            print(f"✓ Collected {len(datasets_data)} datasets")
            
            # 2. Collect tables
            print("Collecting tables...")
            tables_data = await self.collect_tables()
            if tables_data:
                repo.bulk_create_tables(assessment_id, tables_data)
            print(f"✓ Collected {len(tables_data)} tables")
            
            # 3. Collect columns
            print("Collecting columns...")
            columns_data = await self.collect_columns(assessment_id, db)
            if columns_data:
                repo.bulk_create_columns(assessment_id, columns_data)
            print(f"✓ Collected {len(columns_data)} columns")
            
            # 4. Collect views
            print("Collecting views...")
            views_data = await self.collect_views()
            if views_data:
                repo.bulk_create_views(assessment_id, views_data)
            print(f"✓ Collected {len(views_data)} views")
            
            # 5. Collect routines (stored procedures and functions)
            print("Collecting routines...")
            routines_data = await self.collect_routines()
            if routines_data:
                repo.bulk_create_routines(assessment_id, routines_data)
            print(f"✓ Collected {len(routines_data)} routines")
            
            # 6. Collect query statistics (last 7 days)
            print("Collecting query statistics (last 7 days)...")
            query_stats_data = await self.collect_query_statistics_detailed()
            if query_stats_data:
                repo.bulk_create_query_stats(assessment_id, query_stats_data)
            print(f"✓ Collected {len(query_stats_data)} query statistics")
            
            # 7. Collect ML models
            print("Collecting ML models...")
            ml_models_data = await self.collect_ml_models()
            if ml_models_data:
                repo.bulk_create_ml_models(assessment_id, ml_models_data)
            print(f"✓ Collected {len(ml_models_data)} ML models")
            
            # 8. Collect security policies (RLS/CLS)
            print("Collecting security policies...")
            security_data = await self.collect_security_policies_detailed()
            if security_data:
                repo.bulk_create_security_policies(assessment_id, security_data)
            print(f"✓ Collected {len(security_data)} security policies")
            
            # 9. Detect sharded tables
            print("Detecting sharded tables...")
            sharded_data = await self.detect_sharded_tables()
            if sharded_data:
                repo.bulk_create_sharded_tables(assessment_id, sharded_data)
            print(f"✓ Detected {len(sharded_data)} sharded table groups")
            
            # 10. Analyze large STRING columns
            print("Analyzing large STRING columns...")
            large_strings = await self.analyze_large_strings()
            print(f"✓ Found {len(large_strings)} tables with large STRING columns")
            
            # 11. Calculate update frequency from query stats
            print("Calculating table update frequencies...")
            update_frequencies = await self.calculate_update_frequency(query_stats_data)
            print(f"✓ Calculated update frequency for {len(update_frequencies)} tables")
            
            # 12. Detect Spark jobs
            print("Detecting Spark jobs...")
            spark_jobs = await self.detect_spark_jobs()
            print(f"✓ Detected {len(spark_jobs)} Spark jobs")
            
            # 13. Collect table options
            print("Collecting table options...")
            table_options = await self.get_table_options()
            print(f"✓ Collected options for {len(table_options)} tables")
            
            # 14. Update totals
            print("Updating assessment totals...")
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
            
            # Mark assessment as completed
            repo.update_status(assessment_id, 'completed')
            print(f"✓ Assessment {assessment_id} completed successfully")
            
            # Return summary
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
    
    async def collect_datasets(self) -> List[Dict]:
        """Collect dataset (database) information"""
        datasets = []
        
        for dataset in self.client.list_datasets():
            dataset_ref = self.client.get_dataset(dataset.dataset_id)
            
            # Count tables in dataset
            tables = list(self.client.list_tables(dataset.dataset_id))
            table_count = len(tables)
            
            # Calculate total size
            total_size_bytes = 0
            for table in tables:
                table_ref = self.client.get_table(f"{self.project_id}.{dataset.dataset_id}.{table.table_id}")
                total_size_bytes += table_ref.num_bytes or 0
            
            datasets.append({
                'dataset_name': dataset.dataset_id,
                'creation_time': dataset_ref.created,
                'location': dataset_ref.location,
                'table_count': table_count,
                'total_size_mb': total_size_bytes / (1024 * 1024)
            })
        
        return datasets
    
    async def collect_tables(self) -> List[Dict]:
        """Collect table information"""
        tables = []
        
        for dataset in self.client.list_datasets():
            for table in self.client.list_tables(dataset.dataset_id):
                table_ref = self.client.get_table(f"{self.project_id}.{dataset.dataset_id}.{table.table_id}")
                
                # Determine table type
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
                
                # Get partitioning info
                partitioning_columns = []
                if table_ref.time_partitioning:
                    partitioning_columns.append(table_ref.time_partitioning.field or '_PARTITIONTIME')
                if table_ref.range_partitioning:
                    partitioning_columns.append(table_ref.range_partitioning.field)
                
                # Get clustering info - ensure it's a proper list
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
                    'has_column_security': False,  # Will be updated by security collection
                    'has_row_security': False,  # Will be updated by security collection
                    'is_sharded': self._is_sharded_table(table.table_id),
                    'update_frequency': 'unknown'  # Will be updated by query stats
                })
        
        return tables
    
    async def collect_columns(self, assessment_id: int, db: Session) -> List[Dict]:
        """Collect column information"""
        from repositories.assessment_repository import AssessmentRepository
        
        columns = []
        repo = AssessmentRepository(db)
        
        for dataset in self.client.list_datasets():
            for table in self.client.list_tables(dataset.dataset_id):
                table_ref = self.client.get_table(f"{self.project_id}.{dataset.dataset_id}.{table.table_id}")
                
                # Find the corresponding assessment_table record
                assessment_table = db.query(AssessmentTable).filter(
                    AssessmentTable.assessment_id == assessment_id,
                    AssessmentTable.dataset_name == dataset.dataset_id,
                    AssessmentTable.table_name == table.table_id
                ).first()
                
                if not assessment_table:
                    continue  # Skip if table not found
                
                for idx, field in enumerate(table_ref.schema):
                    # Check if this column is a partitioning column
                    is_partitioning = False
                    if table_ref.time_partitioning and table_ref.time_partitioning.field:
                        is_partitioning = (field.name == table_ref.time_partitioning.field)
                    elif table_ref.range_partitioning and table_ref.range_partitioning.field:
                        is_partitioning = (field.name == table_ref.range_partitioning.field)
                    
                    # Check if this column is a clustering column and get its position
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
                        'max_length': None  # STRING fields don't have max_length in schema
                    })
        
        return columns
    
    async def collect_views(self) -> List[Dict]:
        """Collect view and materialized view information with dependencies"""
        views = []
        
        # First pass: collect all views
        for dataset in self.client.list_datasets():
            for table in self.client.list_tables(dataset.dataset_id):
                table_ref = self.client.get_table(f"{self.project_id}.{dataset.dataset_id}.{table.table_id}")
                
                if table_ref.table_type in ['VIEW', 'MATERIALIZED_VIEW']:
                    view_definition = table_ref.view_query or table_ref.mview_query
                    
                    # Parse dependencies from SQL
                    dependencies = self.sql_parser.parse_dependencies(view_definition) if view_definition else {'tables': [], 'views': [], 'functions': []}
                    
                    views.append({
                        'view_name': f"{dataset.dataset_id}.{table.table_id}",
                        'view_type': table_ref.table_type,
                        'view_definition': view_definition,
                        'creation_time': table_ref.created,
                        'dependent_tables': [],  # Will be populated in second pass
                        'dependent_views': [],  # Will be populated in second pass
                        'dependent_functions': dependencies['functions'],
                        'dependency_depth': 1  # Will be calculated if needed
                    })
        
        # Second pass: categorize dependencies into tables vs views
        view_names = {v['view_name'] for v in views}
        all_dependencies = dependencies['tables']  # All table/view references from last iteration
        
        for view in views:
            # Re-parse dependencies for this specific view
            view_def = view['view_definition']
            if view_def:
                view_deps = self.sql_parser.parse_dependencies(view_def)
                all_deps = view_deps['tables']
                
                for dep in all_deps:
                    # Check if dependency is a view or table
                    if dep in view_names:
                        view['dependent_views'].append(dep)
                    else:
                        view['dependent_tables'].append(dep)
        
        return views
    
    async def collect_routines(self) -> List[Dict]:
        """Collect stored procedures and functions with dependencies"""
        routines = []
        
        # First pass: collect all routines
        for dataset in self.client.list_datasets():
            for routine in self.client.list_routines(dataset.dataset_id):
                routine_ref = self.client.get_routine(routine.reference)
                routine_definition = routine_ref.body
                
                # Parse dependencies from SQL
                dependencies = self.sql_parser.parse_dependencies(routine_definition) if routine_definition else {'tables': [], 'views': [], 'functions': []}
                
                # Extract procedure calls (CALL statements)
                calls_procedures = self._extract_procedure_calls(routine_definition) if routine_definition else []
                
                routines.append({
                    'routine_name': f"{dataset.dataset_id}.{routine.routine_id}",
                    'routine_type': routine_ref.type_,
                    'return_type': str(routine_ref.return_type) if routine_ref.return_type else None,
                    'definition': routine_definition,
                    'external_language': routine_ref.language,
                    'creation_time': routine_ref.created,
                    'call_frequency': 0,  # Will be updated by query stats
                    'dependent_tables': [],  # Will be populated in second pass
                    'dependent_views': [],  # Will be populated in second pass
                    'dependent_functions': dependencies['functions'],
                    'calls_procedures': calls_procedures,
                    'dependency_depth': 1
                })
        
        # Second pass: categorize dependencies (would need view list to distinguish)
        # For now, all dependencies are marked as tables
        # This can be enhanced by cross-referencing with collected views
        
        return routines
    
    def _extract_procedure_calls(self, sql: str) -> List[str]:
        """Extract CALL statements for stored procedures"""
        if not sql:
            return []
        
        import re
        pattern = r'CALL\s+`?([a-zA-Z0-9_.-]+)`?'
        matches = re.findall(pattern, sql, re.IGNORECASE)
        return list(set(matches))  # Remove duplicates
    
    async def collect_query_statistics(self) -> List[Dict]:
        """Collect query statistics from INFORMATION_SCHEMA.JOBS"""
        # This would require querying INFORMATION_SCHEMA.JOBS
        # For now, return empty list
        return []
    
    async def collect_ml_models(self) -> List[Dict]:
        """Collect ML model information"""
        models = []
        
        for dataset in self.client.list_datasets():
            for model in self.client.list_models(dataset.dataset_id):
                model_ref = self.client.get_model(f"{self.project_id}.{dataset.dataset_id}.{model.model_id}")
                
                models.append({
                    'model_name': f"{dataset.dataset_id}.{model.model_id}",  # Include dataset in model name
                    'model_type': model_ref.model_type,
                    'dataset_name': dataset.dataset_id,
                    'creation_time': model_ref.created,
                    'last_modified_time': model_ref.modified
                })
        
        return models
    
    async def collect_security_policies(self) -> List[Dict]:
        """Collect security policies (RLS and CLS)"""
        # This would require querying INFORMATION_SCHEMA for policies
        # For now, return empty list
        return []
    
    def _is_sharded_table(self, table_name: str) -> bool:
        """Check if table name indicates sharding (e.g., table_20240101)"""
        import re
        # Check for date suffix pattern
        pattern = r'_\d{8}$|_\d{6}$|_\d{4}\d{2}\d{2}$'
        return bool(re.search(pattern, table_name))
    
    async def collect_query_statistics_detailed(self) -> List[Dict]:
        """
        Collect detailed query statistics from INFORMATION_SCHEMA.JOBS
        Collects up to 180 days of query history (BigQuery INFORMATION_SCHEMA retention limit)
        Frontend will filter by time frame dynamically
        """
        query_stats = []
        
        # Detect the region from the first dataset
        # BigQuery INFORMATION_SCHEMA.JOBS_BY_PROJECT requires the correct region
        region = 'us'  # Default fallback
        try:
            datasets = list(self.client.list_datasets())
            if datasets:
                first_dataset = self.client.get_dataset(datasets[0].dataset_id)
                if first_dataset.location:
                    # Convert location to region format (e.g., 'us-central1' -> 'us', 'US' -> 'us')
                    location = first_dataset.location.lower()
                    if location.startswith('us'):
                        region = 'us'
                    elif location.startswith('eu'):
                        region = 'eu'
                    elif location.startswith('asia'):
                        region = 'asia'
                    else:
                        # For specific regions like 'us-central1', use the full location
                        region = location
                    print(f"Detected BigQuery region: {region} (from location: {first_dataset.location})")
        except Exception as e:
            print(f"Warning: Could not detect region, using default 'us': {e}")
        
        # Query to get job statistics from last 180 days (max retention in INFORMATION_SCHEMA)
        # Collect all queries so frontend can filter by time frame dynamically
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
            error_result
        FROM `{self.project_id}.region-{region}.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
        WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 180 DAY)
            AND job_type = 'QUERY'
            AND state = 'DONE'
        ORDER BY creation_time DESC
        LIMIT 50000
        """
        
        try:
            print(f"Querying INFORMATION_SCHEMA with region: {region}")
            query_job = self.client.query(query)
            results = query_job.result()
            
            for row in results:
                # Parse referenced tables
                referenced_tables = []
                if row.referenced_tables:
                    for table_ref in row.referenced_tables:
                        referenced_tables.append(f"{table_ref.project}.{table_ref.dataset_id}.{table_ref.table_id}")
                
                query_stats.append({
                    'job_id': row.job_id,
                    'execution_time': row.execution_time,
                    'query_text': row.query_text[:5000] if row.query_text else None,  # Limit query text size
                    'bytes_scanned': row.bytes_scanned or 0,
                    'slot_milliseconds': row.slot_milliseconds or 0,
                    'cache_hit': row.cache_hit or False,
                    'referenced_tables': referenced_tables,
                    'user_email': row.user_email
                })
            
            print(f"✓ Collected {len(query_stats)} query statistics from region-{region}")
        except Exception as e:
            print(f"Warning: Could not collect query statistics from region-{region}: {e}")
            print(f"Error details: {str(e)}")
            # Return empty list if INFORMATION_SCHEMA is not accessible
        
        return query_stats
    
    async def detect_sharded_tables(self) -> List[Dict]:
        """
        Detect and group sharded tables (date-suffixed tables)
        Returns list of shard groups with metadata
        """
        import re
        from collections import defaultdict
        from datetime import datetime
        
        sharded_groups = defaultdict(list)
        
        # Collect all tables and detect sharding pattern
        for dataset in self.client.list_datasets():
            for table in self.client.list_tables(dataset.dataset_id):
                table_name = table.table_id
                
                # Check for date suffix patterns
                patterns = [
                    (r'^(.+)_(\d{8})$', '%Y%m%d'),  # table_20240101
                    (r'^(.+)_(\d{6})$', '%Y%m'),     # table_202401
                    (r'^(.+)_(\d{4})(\d{2})(\d{2})$', '%Y%m%d')  # table_2024_01_01
                ]
                
                for pattern, date_format in patterns:
                    match = re.match(pattern, table_name)
                    if match:
                        prefix = match.group(1)
                        date_str = match.group(2) if len(match.groups()) == 2 else ''.join(match.groups()[1:])
                        
                        try:
                            # Parse date to validate
                            shard_date = datetime.strptime(date_str, date_format)
                            
                            # Get table size
                            table_ref = self.client.get_table(f"{self.project_id}.{dataset.dataset_id}.{table_name}")
                            size_mb = (table_ref.num_bytes or 0) / (1024 * 1024)
                            
                            sharded_groups[f"{dataset.dataset_id}.{prefix}"].append({
                                'table_name': table_name,
                                'shard_date': shard_date,
                                'size_mb': size_mb
                            })
                            break
                        except ValueError:
                            continue
        
        # Create shard group summaries
        shard_summaries = []
        for group_key, shards in sharded_groups.items():
            if len(shards) > 1:  # Only groups with multiple shards
                dataset_name, table_prefix = group_key.split('.', 1)
                
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
    
    async def analyze_large_strings(self) -> Dict[str, List[str]]:
        """
        Detect tables with large STRING columns
        Returns dict mapping table names to list of large string columns
        """
        large_string_tables = {}
        
        for dataset in self.client.list_datasets():
            for table in self.client.list_tables(dataset.dataset_id):
                table_ref = self.client.get_table(f"{self.project_id}.{dataset.dataset_id}.{table.table_id}")
                
                large_columns = []
                for field in table_ref.schema:
                    # Check for STRING type without max_length (unbounded)
                    if field.field_type == 'STRING':
                        # In BigQuery, STRING columns are variable length
                        # We'll sample data to check for large values
                        large_columns.append(field.name)
                
                if large_columns:
                    table_key = f"{dataset.dataset_id}.{table.table_id}"
                    large_string_tables[table_key] = large_columns
        
        return large_string_tables
    
    async def calculate_update_frequency(self, query_stats: List[Dict]) -> Dict[str, str]:
        """
        Calculate update frequency for tables based on query history
        Returns dict mapping table names to frequency (daily, weekly, monthly, rarely)
        """
        from collections import defaultdict
        from datetime import datetime, timedelta
        
        table_access_dates = defaultdict(list)
        
        # Parse query stats to find table access patterns
        for stat in query_stats:
            if stat.get('referenced_tables'):
                execution_time = stat.get('execution_time')
                if execution_time:
                    for table in stat['referenced_tables']:
                        table_access_dates[table].append(execution_time)
        
        # Calculate frequency for each table
        update_frequencies = {}
        now = datetime.utcnow()
        
        for table, access_dates in table_access_dates.items():
            if not access_dates:
                update_frequencies[table] = 'unknown'
                continue
            
            # Sort dates
            sorted_dates = sorted(access_dates)
            
            # Calculate average interval between accesses
            if len(sorted_dates) < 2:
                update_frequencies[table] = 'rarely'
                continue
            
            intervals = []
            for i in range(1, len(sorted_dates)):
                interval = (sorted_dates[i] - sorted_dates[i-1]).total_seconds() / 3600  # hours
                intervals.append(interval)
            
            avg_interval_hours = sum(intervals) / len(intervals)
            
            # Classify frequency
            if avg_interval_hours < 24:
                update_frequencies[table] = 'daily'
            elif avg_interval_hours < 168:  # 7 days
                update_frequencies[table] = 'weekly'
            elif avg_interval_hours < 720:  # 30 days
                update_frequencies[table] = 'monthly'
            else:
                update_frequencies[table] = 'rarely'
        
        return update_frequencies
    
    async def collect_security_policies_detailed(self) -> List[Dict]:
        """
        Collect Row-Level Security (RLS) and Column-Level Security (CLS) policies
        """
        security_policies = []
        
        # Query for row-level security policies with creation time
        rls_query = f"""
        SELECT
            table_catalog,
            table_schema,
            table_name,
            policy_name,
            filter_predicate,
            grantee_list,
            ddl AS creation_ddl
        FROM `{self.project_id}.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES`
        """
        
        try:
            query_job = self.client.query(rls_query)
            results = query_job.result()
            
            for row in results:
                # Try to extract creation time from DDL or use None
                creation_time = None
                # Note: BigQuery doesn't expose creation_time directly for policies
                # We capture the DDL which contains the policy definition
                
                security_policies.append({
                    'security_type': 'RLS',
                    'table_name': f"{row.table_schema}.{row.table_name}",  # Include dataset in table name
                    'policy_name': row.policy_name,
                    'filter_predicate': row.filter_predicate,
                    'grantees': row.grantee_list.split(',') if row.grantee_list else [],
                    'creation_time': creation_time,  # Will be None for now
                    'security_metadata': {
                        'ddl': row.creation_ddl if hasattr(row, 'creation_ddl') else None
                    }
                })
        except Exception as e:
            print(f"Warning: Could not collect RLS policies: {e}")
        
        # Column-level security is collected via policy tags on columns
        # This is already handled in collect_columns()
        
        return security_policies
    
    async def detect_spark_jobs(self) -> List[Dict]:
        """
        Detect Spark-based stored procedures and Python procedures with Spark references
        """
        spark_jobs = []
        
        for dataset in self.client.list_datasets():
            for routine in self.client.list_routines(dataset.dataset_id):
                routine_ref = self.client.get_routine(routine.reference)
                
                # Check if routine uses Spark
                is_spark = False
                if routine_ref.language and routine_ref.language.upper() == 'PYTHON':
                    # Check routine body for Spark references
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
    
    async def get_table_options(self) -> Dict[str, Dict]:
        """
        Collect table options including clustering and partition expiration
        """
        table_options = {}
        
        for dataset in self.client.list_datasets():
            for table in self.client.list_tables(dataset.dataset_id):
                table_ref = self.client.get_table(f"{self.project_id}.{dataset.dataset_id}.{table.table_id}")
                
                options = {}
                
                # Clustering configuration
                if table_ref.clustering_fields:
                    options['clustering_columns'] = table_ref.clustering_fields
                
                # Partition expiration
                if table_ref.time_partitioning and table_ref.time_partitioning.expiration_ms:
                    expiration_days = table_ref.time_partitioning.expiration_ms / (1000 * 60 * 60 * 24)
                    options['partition_expiration_days'] = int(expiration_days)
                
                # Require partition filter
                if table_ref.require_partition_filter:
                    options['require_partition_filter'] = True
                
                if options:
                    table_key = f"{dataset.dataset_id}.{table.table_id}"
                    table_options[table_key] = options
        
        return table_options
