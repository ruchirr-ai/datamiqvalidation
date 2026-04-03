"""
SQL Server Assessment Service

Collects comprehensive metadata from SQL Server for migration assessment to Redshift.

Collects:
- Databases and schemas
- Tables (with partitioning, compression, indexes)
- Columns (with data types, constraints, computed columns)
- Views (regular and indexed views)
- Stored Procedures
- Functions (scalar, table-valued, inline)
- Triggers
- Indexes (clustered, non-clustered, filtered, columnstore)
- Constraints (PK, FK, unique, check, default)
- Statistics
- Security (users, roles, permissions, RLS)
- SQL Server specific features (filegroups, partitions, etc.)
"""

import pyodbc
from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional
import json
from datetime import datetime
import re

from repositories.assessment_repository import AssessmentRepository
from models.assessment import AssessmentDataset


class SQLServerAssessmentService:
    def __init__(self, connection_params: Dict):
        """
        Initialize SQL Server connection
        
        Args:
            connection_params: Dictionary containing:
                - host: SQL Server host
                - port: SQL Server port (default 1433)
                - database_name: Database name
                - instance_name: Instance name (optional, e.g., SQLEXPRESS)
                - username: SQL Server username
                - password: SQL Server password
                - driver: ODBC driver (default: ODBC Driver 17 for SQL Server)
                - windows_auth: Use Windows Authentication (optional)
        """
        self.host = connection_params.get('host', 'localhost')
        self.port = connection_params.get('port', 1433)
        self.database = connection_params.get('database_name', 'master')
        self.instance_name = connection_params.get('instance_name', '')
        self.username = connection_params.get('username')
        self.password = connection_params.get('password')
        self.driver = connection_params.get('driver', 'ODBC Driver 17 for SQL Server')
        # Handle windows_auth as string "true"/"false" or boolean
        windows_auth_value = connection_params.get('windows_auth', False)
        if isinstance(windows_auth_value, str):
            self.windows_auth = windows_auth_value.lower() in ('true', '1', 'yes')
        else:
            self.windows_auth = bool(windows_auth_value)
        
        # Build connection string
        self.connection_string = self._build_connection_string()
        self.connection = None
    
    def _build_connection_string(self) -> str:
        """Build SQL Server connection string"""
        # Handle instance name format (e.g., localhost\SQLEXPRESS)
        if self.instance_name:
            server = f"{self.host}\\{self.instance_name}"
        else:
            server = f"{self.host},{self.port}"
        
        if self.windows_auth:
            conn_str = f"DRIVER={{{self.driver}}};SERVER={server};DATABASE={self.database};Trusted_Connection=yes;"
        else:
            conn_str = f"DRIVER={{{self.driver}}};SERVER={server};DATABASE={self.database};UID={self.username};PWD={self.password};"
        
        return conn_str
    
    def connect(self):
        """Establish connection to SQL Server with timeout"""
        if not self.connection:
            try:
                print(f"[SQL Server] Connecting to {self.host}\\{self.instance_name if self.instance_name else self.host}:{self.port}")
                print(f"[SQL Server] Connection string: {self.connection_string[:100]}...")
                
                # Set a connection timeout (30 seconds)
                self.connection = pyodbc.connect(self.connection_string, timeout=30)
                
                print(f"[SQL Server] Successfully connected to SQL Server")
            except Exception as e:
                print(f"[SQL Server] Connection failed: {e}")
                raise
        return self.connection
    
    def close(self):
        """Close SQL Server connection"""
        if self.connection:
            self.connection.close()
            self.connection = None

    
    async def run_full_assessment(self, assessment_id: int, db: Session):
        """
        Run complete SQL Server assessment
        
        Collects:
        1. Database information
        2. Schemas
        3. Tables (with row counts, sizes, partitioning)
        4. Columns (with data types, nullability, defaults)
        5. Views
        6. Stored Procedures
        7. Functions
        8. Triggers
        9. Indexes
        10. Constraints
        11. Security policies
        12. Statistics and usage patterns
        """
        repo = AssessmentRepository(db)
        
        try:
            print(f"[SQL Server Assessment] Starting assessment {assessment_id} for database {self.database}", flush=True)
            print(f"[SQL Server Assessment] Connection params: host={self.host}, instance={self.instance_name}, database={self.database}", flush=True)
            
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message=f'Starting SQL Server assessment for database {self.database}',
                stage='initialization'
            )
            db.commit()
            
            repo.update_status(assessment_id, 'running')
            db.commit()
            
            # Connect to SQL Server
            print("[SQL Server Assessment] Step 1: Connecting to SQL Server...", flush=True)
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message='Connecting to SQL Server...',
                stage='connection'
            )
            db.commit()
            
            self.connect()
            
            print("[SQL Server Assessment] ✓ Connected successfully", flush=True)
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message='Successfully connected to SQL Server',
                stage='connection'
            )
            db.commit()
            
            # 1. Collect database information
            print("[SQL Server Assessment] Step 2: Collecting database information...", flush=True)
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message='Collecting database information...',
                stage='metadata_collection'
            )
            db.commit()
            
            database_data = await self.collect_database_info()
            repo.create_dataset(assessment_id, database_data)
            db.commit()
            
            print(f"[SQL Server Assessment] ✓ Collected database info: {database_data.get('dataset_name')}", flush=True)
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message=f'Collected database info: {database_data.get("dataset_name")}',
                stage='metadata_collection'
            )
            db.commit()
            
            # 2. Collect tables
            print("[SQL Server Assessment] Step 3: Collecting tables...", flush=True)
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message='Collecting tables...',
                stage='metadata_collection'
            )
            db.commit()
            
            tables_data = await self.collect_tables()
            if tables_data:
                repo.bulk_create_tables(assessment_id, tables_data)
                db.commit()
                
                # Update dataset table_count with actual count of BASE TABLEs
                base_table_count = len([t for t in tables_data if t.get('table_type') == 'BASE TABLE'])
                dataset = db.query(AssessmentDataset).filter(
                    AssessmentDataset.assessment_id == assessment_id
                ).first()
                if dataset:
                    dataset.table_count = base_table_count
                    db.commit()
            
            print(f"[SQL Server Assessment] ✓ Collected {len(tables_data)} tables", flush=True)
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message=f'Collected {len(tables_data)} tables',
                stage='metadata_collection'
            )
            db.commit()
            
            # 3. Collect columns
            print("[SQL Server Assessment] Step 4: Collecting columns...", flush=True)
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message='Collecting columns...',
                stage='metadata_collection'
            )
            db.commit()
            
            columns_data = await self.collect_columns(assessment_id, db)
            if columns_data:
                repo.bulk_create_columns(assessment_id, columns_data)
                db.commit()
            
            print(f"[SQL Server Assessment] ✓ Collected {len(columns_data)} columns", flush=True)
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message=f'Collected {len(columns_data)} columns',
                stage='metadata_collection'
            )
            db.commit()
            
            # 4. Collect views
            print("[SQL Server Assessment] Step 5: Collecting views...", flush=True)
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message='Collecting views...',
                stage='metadata_collection'
            )
            db.commit()
            
            views_data = await self.collect_views()
            if views_data:
                # Enrich views with dependencies
                views_data = await self.enrich_views_with_dependencies(views_data)
                repo.bulk_create_views(assessment_id, views_data)
                db.commit()
            
            print(f"[SQL Server Assessment] ✓ Collected {len(views_data)} views", flush=True)
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message=f'Collected {len(views_data)} views',
                stage='metadata_collection'
            )
            db.commit()
            
            # 5. Collect stored procedures
            print("[SQL Server Assessment] Step 6: Collecting stored procedures...", flush=True)
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message='Collecting stored procedures...',
                stage='metadata_collection'
            )
            db.commit()
            
            # Collect execution stats once for all routines (procedures, functions, triggers)
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message='About to collect routine execution statistics from Query Store...',
                stage='metadata_collection'
            )
            db.commit()
            print("[SQL Server Assessment] Collecting routine execution statistics from Query Store...", flush=True)
            execution_stats = await self.collect_routine_execution_stats()
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message=f'Collected execution stats for {len(execution_stats)} routines',
                stage='metadata_collection'
            )
            db.commit()
            
            procedures_data = await self.collect_procedures()
            if procedures_data:
                # Merge execution stats into procedures
                for proc in procedures_data:
                    proc_name = proc['routine_name']
                    if proc_name in execution_stats:
                        proc['routine_metadata'].update(execution_stats[proc_name])
                        proc['call_frequency'] = execution_stats[proc_name]['total_executions']
                
                # Enrich with dependencies and usage stats
                procedures_data = await self.enrich_routines_with_dependencies_and_usage(procedures_data)
                repo.bulk_create_routines(assessment_id, procedures_data, clear_existing=True)  # Clear on first call
                db.commit()
            
            print(f"[SQL Server Assessment] ✓ Collected {len(procedures_data)} stored procedures", flush=True)
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message=f'Collected {len(procedures_data)} stored procedures',
                stage='metadata_collection'
            )
            db.commit()
            
            # 6. Collect functions
            print("[SQL Server Assessment] Step 7: Collecting functions...", flush=True)
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message='Collecting functions...',
                stage='metadata_collection'
            )
            db.commit()
            
            functions_data = await self.collect_functions()
            if functions_data:
                # Merge execution stats into functions
                for func in functions_data:
                    func_name = func['routine_name']
                    if func_name in execution_stats:
                        func['routine_metadata'].update(execution_stats[func_name])
                        func['call_frequency'] = execution_stats[func_name]['total_executions']
                
                # Enrich with dependencies and usage stats
                functions_data = await self.enrich_routines_with_dependencies_and_usage(functions_data)
                repo.bulk_create_routines(assessment_id, functions_data, clear_existing=False)  # Don't clear
                db.commit()
            
            print(f"[SQL Server Assessment] ✓ Collected {len(functions_data)} functions", flush=True)
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message=f'Collected {len(functions_data)} functions',
                stage='metadata_collection'
            )
            db.commit()
            
            # 7. Collect triggers (table and database level)
            print("[SQL Server Assessment] Step 8: Collecting triggers...", flush=True)
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message='Collecting triggers...',
                stage='metadata_collection'
            )
            db.commit()
            
            triggers_data = await self.collect_triggers()
            if triggers_data:
                # Merge execution stats into triggers
                for trigger in triggers_data:
                    trigger_name = trigger['routine_name']
                    if trigger_name in execution_stats:
                        trigger['routine_metadata'].update(execution_stats[trigger_name])
                        trigger['call_frequency'] = execution_stats[trigger_name]['total_executions']
                
                repo.bulk_create_routines(assessment_id, triggers_data, clear_existing=False)  # Don't clear
                db.commit()
            
            print(f"[SQL Server Assessment] ✓ Collected {len(triggers_data)} triggers", flush=True)
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message=f'Collected {len(triggers_data)} triggers',
                stage='metadata_collection'
            )
            db.commit()
            
            # 8. Collect indexes
            print("[SQL Server Assessment] Step 9: Collecting indexes...", flush=True)
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message='Collecting indexes...',
                stage='metadata_collection'
            )
            db.commit()
            
            indexes_data = await self.collect_indexes()
            if indexes_data:
                # Map table_name to table_id from stored assessment tables
                stored_tables = repo.get_tables(assessment_id)
                table_id_map = {}
                for t in stored_tables:
                    key = f"{t.dataset_name}.{t.table_name}"
                    table_id_map[key] = t.id
                
                for idx in indexes_data:
                    key = f"{idx.get('schema_name', 'dbo')}.{idx.get('table_name', '')}"
                    idx['table_id'] = table_id_map.get(key)
                
                repo.bulk_create_indexes(assessment_id, indexes_data)
                db.commit()
            
            print(f"[SQL Server Assessment] ✓ Collected {len(indexes_data)} indexes", flush=True)
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message=f'Collected {len(indexes_data)} indexes',
                stage='metadata_collection',
                log_metadata={'index_count': len(indexes_data)}
            )
            db.commit()
            
            # 9. Collect constraints
            print("[SQL Server Assessment] Step 10: Collecting constraints...", flush=True)
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message='Collecting constraints...',
                stage='metadata_collection'
            )
            db.commit()
            
            constraints_data = await self.collect_constraints()
            
            print(f"[SQL Server Assessment] ✓ Collected {len(constraints_data)} constraints", flush=True)
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message=f'Collected {len(constraints_data)} constraints',
                stage='metadata_collection',
                log_metadata={'constraint_count': len(constraints_data)}
            )
            db.commit()
            
            # 10. Collect security metadata
            print("[SQL Server Assessment] Step 10: Collecting security metadata...", flush=True)
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message='Collecting security metadata...',
                stage='metadata_collection'
            )
            db.commit()
            
            security_data = await self.collect_security_metadata()
            if security_data:
                repo.bulk_create_security_policies(assessment_id, security_data)
                db.commit()
            
            print(f"[SQL Server Assessment] ✓ Collected {len(security_data)} security policies", flush=True)
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message=f'Collected {len(security_data)} security policies',
                stage='metadata_collection'
            )
            db.commit()

            # 11. Collect query statistics from DMVs
            print("[SQL Server Assessment] Step 12: Collecting query statistics...", flush=True)
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message='Collecting query statistics from DMVs...',
                stage='metadata_collection'
            )
            db.commit()
            
            query_stats_data = await self.collect_query_stats(repo, assessment_id, db)
            if query_stats_data:
                repo.create_log(
                    assessment_id=assessment_id,
                    log_level='INFO',
                    message=f'Storing {len(query_stats_data)} query statistics in database...',
                    stage='metadata_collection'
                )
                db.commit()
                
                print(f"[SQL Server Assessment] Storing {len(query_stats_data)} query stats in database...", flush=True)
                repo.bulk_create_query_stats(assessment_id, query_stats_data)
                db.commit()
                
                print(f"[SQL Server Assessment] ✓ Stored {len(query_stats_data)} query statistics", flush=True)
            
            print(f"[SQL Server Assessment] ✓ Collected {len(query_stats_data) if query_stats_data else 0} query statistics", flush=True)
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message=f'Collected {len(query_stats_data) if query_stats_data else 0} query statistics',
                stage='metadata_collection'
            )
            db.commit()
            
            # 12a. Collect additional SQL Server metadata (Agent Jobs, Certificates, Encryption, etc.)
            print("[SQL Server Assessment] Step 12a: Collecting additional SQL Server metadata...", flush=True)
            additional_metadata = {}
            
            try:
                additional_metadata['agent_jobs'] = await self.collect_agent_jobs()
                print(f"[SQL Server Assessment] ✓ Collected {len(additional_metadata['agent_jobs'])} SQL Agent jobs", flush=True)
            except Exception as e:
                print(f"[SQL Server Assessment] Warning: Could not collect Agent jobs: {e}", flush=True)
                additional_metadata['agent_jobs'] = []
            
            try:
                additional_metadata['certificates'] = await self.collect_certificates()
                print(f"[SQL Server Assessment] ✓ Collected {len(additional_metadata['certificates'])} certificates", flush=True)
            except Exception as e:
                print(f"[SQL Server Assessment] Warning: Could not collect certificates: {e}", flush=True)
                additional_metadata['certificates'] = []
            
            try:
                additional_metadata['encryption'] = await self.collect_encryption()
                print(f"[SQL Server Assessment] ✓ Collected encryption info", flush=True)
            except Exception as e:
                print(f"[SQL Server Assessment] Warning: Could not collect encryption: {e}", flush=True)
                additional_metadata['encryption'] = {}
            
            try:
                additional_metadata['assemblies'] = await self.collect_assemblies()
                print(f"[SQL Server Assessment] ✓ Collected {len(additional_metadata['assemblies'])} CLR assemblies", flush=True)
            except Exception as e:
                print(f"[SQL Server Assessment] Warning: Could not collect assemblies: {e}", flush=True)
                additional_metadata['assemblies'] = []
            
            try:
                additional_metadata['policies'] = await self.collect_policies()
                print(f"[SQL Server Assessment] ✓ Collected {len(additional_metadata['policies'])} policies", flush=True)
            except Exception as e:
                print(f"[SQL Server Assessment] Warning: Could not collect policies: {e}", flush=True)
                additional_metadata['policies'] = []
            
            try:
                additional_metadata['replication'] = await self.collect_replication()
                print(f"[SQL Server Assessment] ✓ Collected replication info", flush=True)
            except Exception as e:
                print(f"[SQL Server Assessment] Warning: Could not collect replication: {e}", flush=True)
                additional_metadata['replication'] = {}
            
            try:
                additional_metadata['computed_columns'] = await self.collect_computed_columns()
                print(f"[SQL Server Assessment] ✓ Collected {len(additional_metadata['computed_columns'])} computed columns", flush=True)
            except Exception as e:
                print(f"[SQL Server Assessment] Warning: Could not collect computed columns: {e}", flush=True)
                additional_metadata['computed_columns'] = []
            
            try:
                additional_metadata['user_defined_types'] = await self.collect_user_defined_types()
                print(f"[SQL Server Assessment] ✓ Collected {len(additional_metadata['user_defined_types'])} user-defined types", flush=True)
            except Exception as e:
                print(f"[SQL Server Assessment] Warning: Could not collect UDTs: {e}", flush=True)
                additional_metadata['user_defined_types'] = []
            
            # Store additional metadata in the dataset record
            dataset = repo.get_datasets(assessment_id)
            if dataset:
                ds = dataset[0]
                existing_meta = dict(ds.dataset_metadata or {})
                existing_meta['additional_metadata'] = additional_metadata
                ds.dataset_metadata = existing_meta
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(ds, 'dataset_metadata')
                db.add(ds)
                db.commit()
                print(f"[SQL Server Assessment] ✓ Stored additional metadata in dataset record", flush=True)
            
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message=f'Collected additional metadata: {len(additional_metadata.get("agent_jobs", []))} jobs, {len(additional_metadata.get("certificates", []))} certs, {len(additional_metadata.get("assemblies", []))} assemblies, {len(additional_metadata.get("user_defined_types", []))} UDTs',
                stage='metadata_collection'
            )
            db.commit()
            
            # 12. Update assessment totals
            print("[SQL Server Assessment] Step 13: Updating assessment totals...", flush=True)
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message='Updating assessment totals...',
                stage='finalization'
            )
            db.commit()
            
            assessment = repo.get_by_id(assessment_id)
            total_size_mb = sum(t.get('size_mb', 0) for t in tables_data)
            total_routines = len(procedures_data) + len(functions_data) + len(triggers_data)
            
            repo.update_totals(
                assessment_id=assessment_id,
                total_datasets=1,  # SQL Server has one database
                total_tables=len([t for t in tables_data if t.get('table_type') == 'BASE TABLE']),
                total_views=len(views_data),
                total_routines=total_routines,
                total_size_mb=total_size_mb
            )
            db.commit()
            
            # Mark as completed
            repo.update_status(assessment_id, 'completed')
            db.commit()
            
            print(f"[SQL Server Assessment] ✓ Assessment {assessment_id} completed successfully", flush=True)
            repo.create_log(
                assessment_id=assessment_id,
                log_level='INFO',
                message=f'Assessment completed successfully. Tables: {len(tables_data)}, Views: {len(views_data)}, Routines: {total_routines}, Query Stats: {len(query_stats_data)}, Size: {total_size_mb:.2f} MB',
                stage='completion'
            )
            db.commit()
            
        except Exception as e:
            error_msg = str(e)
            print(f"[SQL Server Assessment] ERROR: {error_msg}", flush=True)
            import traceback
            stack = traceback.format_exc()
            print(f"[SQL Server Assessment] Stack trace: {stack}", flush=True)
            
            repo.create_log(
                assessment_id=assessment_id,
                log_level='ERROR',
                message=f'Assessment failed: {error_msg}',
                stage='error',
                stack_trace=stack
            )
            db.commit()
            
            repo.update_status(assessment_id, 'failed', error_message=error_msg)
            db.commit()
            raise
        finally:
            self.close()

    
    async def collect_database_info(self) -> Dict:
        """Collect database-level information"""
        cursor = self.connection.cursor()
        
        # Completely avoid DATABASEPROPERTYEX and SQL_VARIANT types
        # Use only sys catalog views which return proper data types
        query = """
        SELECT 
            DB_NAME() AS database_name,
            CAST(SERVERPROPERTY('Collation') AS VARCHAR(255)) AS collation,
            d.state_desc AS status,
            d.recovery_model_desc AS recovery_model,
            CAST(SERVERPROPERTY('ProductVersion') AS VARCHAR(50)) AS version,
            CONVERT(VARCHAR(50), d.create_date, 120) AS create_date,
            d.compatibility_level AS compatibility_level,
            CAST(SERVERPROPERTY('Edition') AS VARCHAR(255)) AS edition,
            CAST(SERVERPROPERTY('ProductLevel') AS VARCHAR(50)) AS product_level,
            CAST(SERVERPROPERTY('MachineName') AS VARCHAR(255)) AS machine_name,
            CAST(SERVERPROPERTY('ServerName') AS VARCHAR(255)) AS server_name,
            CAST(SERVERPROPERTY('InstanceName') AS VARCHAR(255)) AS instance_name_prop,
            CAST(SERVERPROPERTY('IsClustered') AS INT) AS is_clustered,
            CAST(SERVERPROPERTY('IsHadrEnabled') AS INT) AS is_hadr_enabled,
            CAST(COALESCE(SERVERPROPERTY('HadrManagerStatus'), 0) AS INT) AS hadr_manager_status
        FROM sys.databases d
        WHERE d.name = DB_NAME()
        """
        
        cursor.execute(query)
        row = cursor.fetchone()
        
        if not row:
            return {}
        
        # Get file sizes in a separate query to avoid any type issues
        size_query = """
        SELECT 
            SUM(CASE WHEN type = 0 THEN CAST(size AS BIGINT) ELSE 0 END) * 8.0 / 1024 AS data_size_mb,
            SUM(CASE WHEN type = 1 THEN CAST(size AS BIGINT) ELSE 0 END) * 8.0 / 1024 AS log_size_mb
        FROM sys.database_files
        """
        
        cursor.execute(size_query)
        size_row = cursor.fetchone()
        
        # Convert Decimal to float for JSON serialization
        data_size_mb = float(size_row.data_size_mb) if size_row and size_row.data_size_mb else 0.0
        log_size_mb = float(size_row.log_size_mb) if size_row and size_row.log_size_mb else 0.0
        
        # Determine instance role (Primary, Secondary, Standalone)
        instance_role = 'Standalone'
        try:
            if row.is_hadr_enabled:
                role_query = """
                SELECT role_desc 
                FROM sys.dm_hadr_availability_replica_states rs
                INNER JOIN sys.availability_replicas r ON rs.replica_id = r.replica_id
                WHERE rs.is_local = 1
                """
                cursor.execute(role_query)
                role_row = cursor.fetchone()
                if role_row:
                    instance_role = role_row.role_desc  # PRIMARY or SECONDARY
            elif row.is_clustered:
                instance_role = 'Clustered'
        except Exception:
            instance_role = 'Standalone'
        
        return {
            'dataset_name': row.database_name,
            'location': f"{self.host}\\{self.instance_name}" if self.instance_name else self.host,
            'creation_time': row.create_date,
            'table_count': 0,  # Will be updated later
            'total_size_mb': data_size_mb + log_size_mb,
            'dataset_metadata': {
                'collation': row.collation,
                'status': row.status,
                'recovery_model': row.recovery_model,
                'compatibility_level': row.compatibility_level,
                'data_size_mb': data_size_mb,
                'log_size_mb': log_size_mb,
                'version': row.version,
                'edition': row.edition,
                'product_level': row.product_level,
                'machine_name': row.machine_name,
                'server_name': row.server_name,
                'instance_name': row.instance_name_prop or 'Default',
                'instance_role': instance_role
            }
        }

    
    async def collect_tables(self) -> List[Dict]:
        """Collect table information including row counts, sizes, and metadata"""
        cursor = self.connection.cursor()
        
        query = """
        SELECT 
            s.name AS schema_name,
            t.name AS table_name,
            t.type_desc AS table_type,
            t.create_date,
            t.modify_date,
            SUM(p.rows) AS row_count,
            SUM(a.total_pages) * 8.0 / 1024 AS size_mb,
            SUM(a.used_pages) * 8.0 / 1024 AS used_size_mb,
            SUM(a.data_pages) * 8.0 / 1024 AS data_size_mb,
            -- Partitioning info
            ps.name AS partition_scheme,
            pf.name AS partition_function,
            -- Compression info
            MAX(p.data_compression_desc) AS compression_type,
            -- Temporal table info
            t.temporal_type_desc,
            -- Memory optimized
            t.is_memory_optimized,
            -- External table
            t.is_external
        FROM sys.tables t
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        INNER JOIN sys.indexes i ON t.object_id = i.object_id
        INNER JOIN sys.partitions p ON i.object_id = p.object_id AND i.index_id = p.index_id
        INNER JOIN sys.allocation_units a ON p.partition_id = a.container_id
        LEFT JOIN sys.partition_schemes ps ON i.data_space_id = ps.data_space_id
        LEFT JOIN sys.partition_functions pf ON ps.function_id = pf.function_id
        WHERE t.is_ms_shipped = 0
            AND i.index_id <= 1  -- Clustered index or heap only
        GROUP BY 
            s.name, t.name, t.type_desc, t.create_date, t.modify_date,
            ps.name, pf.name, t.temporal_type_desc,
            t.is_memory_optimized, t.is_external
        ORDER BY s.name, t.name
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        tables = []
        for row in rows:
            # Convert Decimal to float for JSON serialization
            size_mb = float(row.size_mb) if row.size_mb else 0.0
            used_size_mb = float(row.used_size_mb) if row.used_size_mb else 0.0
            data_size_mb = float(row.data_size_mb) if row.data_size_mb else 0.0
            
            table_data = {
                'project_id': self.database,
                'dataset_name': row.schema_name,
                'table_name': row.table_name,
                'table_type': 'BASE TABLE' if row.table_type == 'USER_TABLE' else row.table_type,
                'creation_time': row.create_date,
                'row_count': row.row_count or 0,
                'size_mb': size_mb,
                'partitioning_columns': [row.partition_function] if row.partition_function else [],
                'clustering_columns': [],
                'has_column_security': False,  # Will check separately
                'has_row_security': False,  # Will check separately
                'is_sharded': False,
                'table_metadata': {
                    'schema_name': row.schema_name,
                    'modify_date': row.modify_date.isoformat() if row.modify_date else None,
                    'used_size_mb': used_size_mb,
                    'data_size_mb': data_size_mb,
                    'partition_scheme': row.partition_scheme,
                    'partition_function': row.partition_function,
                    'compression_type': row.compression_type,
                    'temporal_type': row.temporal_type_desc,
                    'is_memory_optimized': row.is_memory_optimized,
                    'is_external': row.is_external
                }
            }
            tables.append(table_data)
        
        return tables

    
    async def collect_columns(self, assessment_id: int, db: Session) -> List[Dict]:
        """Collect column information for all tables"""
        cursor = self.connection.cursor()
        repo = AssessmentRepository(db)
        
        # Check if is_masked and is_encrypted columns exist in sys.columns
        check_columns_query = """
        SELECT 
            CASE WHEN EXISTS (
                SELECT 1 FROM sys.columns 
                WHERE object_id = OBJECT_ID('sys.columns') 
                AND name = 'is_masked'
            ) THEN 1 ELSE 0 END AS has_is_masked,
            CASE WHEN EXISTS (
                SELECT 1 FROM sys.columns 
                WHERE object_id = OBJECT_ID('sys.columns') 
                AND name = 'is_encrypted'
            ) THEN 1 ELSE 0 END AS has_is_encrypted
        """
        
        cursor.execute(check_columns_query)
        column_check = cursor.fetchone()
        has_is_masked = column_check.has_is_masked if column_check else False
        has_is_encrypted = column_check.has_is_encrypted if column_check else False
        
        # Build query dynamically based on available columns
        encryption_columns = []
        if has_is_masked:
            encryption_columns.append("c.is_masked")
        if has_is_encrypted:
            encryption_columns.append("c.is_encrypted")
        
        encryption_select = ", " + ", ".join(encryption_columns) if encryption_columns else ""
        
        # Get all tables from assessment
        tables = repo.get_tables(assessment_id)
        
        columns = []
        for table in tables:
            # Access the JSONB metadata field correctly
            schema_name = table.table_metadata.get('schema_name', 'dbo') if table.table_metadata else 'dbo'
            table_name = table.table_name
            
            query = f"""
            SELECT 
                c.name AS column_name,
                t.name AS data_type,
                c.max_length,
                c.precision,
                c.scale,
                c.is_nullable,
                c.column_id AS ordinal_position,
                c.is_identity,
                c.is_computed,
                cc.definition AS computed_definition,
                dc.definition AS default_definition,
                -- Check if part of primary key
                CASE WHEN pk.column_id IS NOT NULL THEN 1 ELSE 0 END AS is_primary_key,
                -- Check if part of foreign key
                CASE WHEN fk.parent_column_id IS NOT NULL THEN 1 ELSE 0 END AS is_foreign_key,
                -- Check if part of unique constraint
                CASE WHEN uq.column_id IS NOT NULL THEN 1 ELSE 0 END AS is_unique,
                -- User-defined type detection
                t.is_user_defined AS is_user_defined_type,
                CASE WHEN t.is_user_defined = 1 THEN t.name ELSE NULL END AS udt_name,
                CASE WHEN t.is_user_defined = 1 THEN st.name ELSE NULL END AS base_type_name
                {encryption_select}
            FROM sys.columns c
            INNER JOIN sys.types t ON c.user_type_id = t.user_type_id
            LEFT JOIN sys.types st ON t.system_type_id = st.system_type_id AND st.is_user_defined = 0 AND st.user_type_id = st.system_type_id
            LEFT JOIN sys.computed_columns cc ON c.object_id = cc.object_id AND c.column_id = cc.column_id
            LEFT JOIN sys.default_constraints dc ON c.default_object_id = dc.object_id
            LEFT JOIN (
                SELECT ic.object_id, ic.column_id
                FROM sys.index_columns ic
                INNER JOIN sys.indexes i ON ic.object_id = i.object_id AND ic.index_id = i.index_id
                WHERE i.is_primary_key = 1
            ) pk ON c.object_id = pk.object_id AND c.column_id = pk.column_id
            LEFT JOIN sys.foreign_key_columns fk ON c.object_id = fk.parent_object_id AND c.column_id = fk.parent_column_id
            LEFT JOIN (
                SELECT ic.object_id, ic.column_id
                FROM sys.index_columns ic
                INNER JOIN sys.indexes i ON ic.object_id = i.object_id AND ic.index_id = i.index_id
                WHERE i.is_unique_constraint = 1
            ) uq ON c.object_id = uq.object_id AND c.column_id = uq.column_id
            WHERE c.object_id = OBJECT_ID(?)
            ORDER BY c.column_id
            """
            
            cursor.execute(query, f"{schema_name}.{table_name}")
            rows = cursor.fetchall()
            
            for row in rows:
                # Build full data type string
                data_type = row.data_type
                if data_type in ('varchar', 'nvarchar', 'char', 'nchar', 'binary', 'varbinary'):
                    if row.max_length == -1:
                        data_type += '(MAX)'
                    else:
                        length = row.max_length if data_type in ('varchar', 'char', 'binary', 'varbinary') else row.max_length // 2
                        data_type += f'({length})'
                elif data_type in ('decimal', 'numeric'):
                    data_type += f'({row.precision},{row.scale})'
                
                # Build column metadata dynamically
                column_metadata = {
                    'precision': row.precision,
                    'scale': row.scale,
                    'is_identity': row.is_identity,
                    'is_computed': row.is_computed,
                    'computed_definition': row.computed_definition,
                    'default_definition': row.default_definition,
                    'is_primary_key': row.is_primary_key,
                    'is_foreign_key': row.is_foreign_key,
                    'is_unique': row.is_unique,
                    'is_user_defined_type': bool(row.is_user_defined_type),
                    'udt_name': row.udt_name,
                    'base_type_name': row.base_type_name
                }
                
                # Add encryption columns if they exist
                if has_is_masked:
                    column_metadata['is_masked'] = getattr(row, 'is_masked', False)
                if has_is_encrypted:
                    column_metadata['is_encrypted'] = getattr(row, 'is_encrypted', False)
                
                column_data = {
                    'table_id': table.id,
                    'column_name': row.column_name,
                    'data_type': data_type,
                    'is_nullable': row.is_nullable,
                    'ordinal_position': row.ordinal_position,
                    'is_partitioning_column': False,
                    'clustering_ordinal_position': None,
                    'policy_tags': [],
                    'max_length': row.max_length,
                    'column_metadata': column_metadata
                }
                columns.append(column_data)
        
        return columns

    
    async def collect_views(self) -> List[Dict]:
        """Collect view information"""
        cursor = self.connection.cursor()
        
        query = """
        SELECT 
            s.name AS schema_name,
            v.name AS view_name,
            v.create_date,
            v.modify_date,
            m.definition AS view_definition,
            -- Check if indexed view
            CASE WHEN EXISTS (
                SELECT 1 FROM sys.indexes i 
                WHERE i.object_id = v.object_id AND i.type > 0
            ) THEN 'INDEXED_VIEW' ELSE 'VIEW' END AS view_type,
            -- Check if schema bound
            OBJECTPROPERTY(v.object_id, 'IsSchemaBound') AS is_schema_bound
        FROM sys.views v
        INNER JOIN sys.schemas s ON v.schema_id = s.schema_id
        LEFT JOIN sys.sql_modules m ON v.object_id = m.object_id
        WHERE v.is_ms_shipped = 0
        ORDER BY s.name, v.name
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        views = []
        for row in rows:
            view_data = {
                'view_name': row.view_name,
                'view_type': row.view_type,
                'view_definition': row.view_definition,
                'creation_time': row.create_date,
                'dependencies': [],
                'dependent_tables': [],
                'dependent_views': [],
                'dependent_functions': [],
                'dependency_depth': 0,
                'view_metadata': {
                    'schema_name': row.schema_name,
                    'modify_date': row.modify_date.isoformat() if row.modify_date else None,
                    'is_schema_bound': row.is_schema_bound
                }
            }
            views.append(view_data)
        
        return views

    
    async def collect_procedures(self) -> List[Dict]:
        """Collect stored procedure information"""
        cursor = self.connection.cursor()
        
        # Check if is_encrypted column exists in sys.sql_modules
        check_encrypted_query = """
        SELECT COUNT(*) as col_count
        FROM sys.columns
        WHERE object_id = OBJECT_ID('sys.sql_modules')
        AND name = 'is_encrypted'
        """
        cursor.execute(check_encrypted_query)
        has_is_encrypted = cursor.fetchone().col_count > 0
        
        # Build query dynamically based on column availability
        encrypted_column = "m.is_encrypted" if has_is_encrypted else "CAST(0 AS BIT) AS is_encrypted"
        
        query = f"""
        SELECT 
            s.name AS schema_name,
            p.name AS procedure_name,
            p.create_date,
            p.modify_date,
            m.definition AS procedure_definition,
            -- Check if CLR procedure
            CASE WHEN p.type = 'PC' THEN 'CLR' ELSE 'SQL' END AS procedure_type,
            -- Check if encrypted
            {encrypted_column},
            -- Check if recompile
            OBJECTPROPERTY(p.object_id, 'ExecIsQuotedIdentOn') AS quoted_identifier,
            OBJECTPROPERTY(p.object_id, 'ExecIsAnsiNullsOn') AS ansi_nulls
        FROM sys.procedures p
        INNER JOIN sys.schemas s ON p.schema_id = s.schema_id
        LEFT JOIN sys.sql_modules m ON p.object_id = m.object_id
        WHERE p.is_ms_shipped = 0
        ORDER BY s.name, p.name
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        procedures = []
        for row in rows:
            procedure_data = {
                'routine_name': row.procedure_name,
                'routine_type': 'PROCEDURE',
                'return_type': None,
                'definition': row.procedure_definition if not row.is_encrypted else '[ENCRYPTED]',
                'external_language': 'CLR' if row.procedure_type == 'CLR' else None,
                'creation_time': row.create_date,
                'call_frequency': 0,
                'dependent_tables': [],
                'dependent_views': [],
                'dependent_functions': [],
                'calls_procedures': [],
                'dependency_depth': 0,
                'routine_metadata': {
                    'schema_name': row.schema_name,
                    'modify_date': row.modify_date.isoformat() if row.modify_date else None,
                    'procedure_type': row.procedure_type,
                    'is_encrypted': row.is_encrypted,
                    'quoted_identifier': row.quoted_identifier,
                    'ansi_nulls': row.ansi_nulls
                }
            }
            procedures.append(procedure_data)
        
        return procedures

    
    async def collect_functions(self) -> List[Dict]:
        """Collect function information (scalar, table-valued, inline)"""
        cursor = self.connection.cursor()
        
        # Check if is_encrypted column exists in sys.sql_modules
        check_encrypted_query = """
        SELECT COUNT(*) as col_count
        FROM sys.columns
        WHERE object_id = OBJECT_ID('sys.sql_modules')
        AND name = 'is_encrypted'
        """
        cursor.execute(check_encrypted_query)
        has_is_encrypted = cursor.fetchone().col_count > 0
        
        # Build query dynamically based on column availability
        encrypted_column = "m.is_encrypted" if has_is_encrypted else "CAST(0 AS BIT) AS is_encrypted"
        
        query = f"""
        SELECT 
            s.name AS schema_name,
            o.name AS function_name,
            o.create_date,
            o.modify_date,
            m.definition AS function_definition,
            CASE o.type
                WHEN 'FN' THEN 'SCALAR'
                WHEN 'IF' THEN 'INLINE_TABLE_VALUED'
                WHEN 'TF' THEN 'TABLE_VALUED'
                WHEN 'FS' THEN 'CLR_SCALAR'
                WHEN 'FT' THEN 'CLR_TABLE_VALUED'
                ELSE 'UNKNOWN'
            END AS function_type,
            -- Return type for scalar functions
            TYPE_NAME(r.user_type_id) AS return_type,
            -- Check if encrypted
            {encrypted_column},
            -- Check if schema bound
            OBJECTPROPERTY(o.object_id, 'IsSchemaBound') AS is_schema_bound
        FROM sys.objects o
        INNER JOIN sys.schemas s ON o.schema_id = s.schema_id
        LEFT JOIN sys.sql_modules m ON o.object_id = m.object_id
        LEFT JOIN sys.parameters r ON o.object_id = r.object_id AND r.parameter_id = 0
        WHERE o.type IN ('FN', 'IF', 'TF', 'FS', 'FT')
            AND o.is_ms_shipped = 0
        ORDER BY s.name, o.name
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        functions = []
        for row in rows:
            function_data = {
                'routine_name': row.function_name,
                'routine_type': 'FUNCTION',
                'return_type': row.return_type,
                'definition': row.function_definition if not row.is_encrypted else '[ENCRYPTED]',
                'external_language': 'CLR' if 'CLR' in row.function_type else None,
                'creation_time': row.create_date,
                'call_frequency': 0,
                'dependent_tables': [],
                'dependent_views': [],
                'dependent_functions': [],
                'calls_procedures': [],
                'dependency_depth': 0,
                'routine_metadata': {
                    'schema_name': row.schema_name,
                    'modify_date': row.modify_date.isoformat() if row.modify_date else None,
                    'function_type': row.function_type,
                    'is_encrypted': row.is_encrypted,
                    'is_schema_bound': row.is_schema_bound
                }
            }
            functions.append(function_data)
        
        return functions

    
    async def collect_triggers(self) -> List[Dict]:
        """
        Collect trigger information (DML and DDL triggers)
        
        Collects:
        - Table triggers (AFTER/INSTEAD OF INSERT/UPDATE/DELETE)
        - Database triggers (DDL events)
        - Server triggers (server-level events)
        """
        cursor = self.connection.cursor()
        
        # Check if is_encrypted column exists in sys.sql_modules
        check_encrypted_query = """
        SELECT COUNT(*) as col_count
        FROM sys.columns
        WHERE object_id = OBJECT_ID('sys.sql_modules')
        AND name = 'is_encrypted'
        """
        cursor.execute(check_encrypted_query)
        has_is_encrypted = cursor.fetchone().col_count > 0
        
        # Build query dynamically based on column availability
        encrypted_column = "m.is_encrypted" if has_is_encrypted else "CAST(0 AS BIT) AS is_encrypted"
        
        # Collect DML triggers (table triggers)
        dml_query = f"""
        SELECT 
            s.name AS schema_name,
            tr.name AS trigger_name,
            tr.create_date,
            tr.modify_date,
            m.definition AS trigger_definition,
            OBJECT_NAME(tr.parent_id) AS table_name,
            -- Trigger type
            CASE 
                WHEN tr.is_instead_of_trigger = 1 THEN 'INSTEAD OF'
                ELSE 'AFTER'
            END AS trigger_type,
            -- Events
            STUFF((
                SELECT ', ' + te.type_desc
                FROM sys.trigger_events te
                WHERE te.object_id = tr.object_id
                FOR XML PATH(''), TYPE
            ).value('.', 'NVARCHAR(MAX)'), 1, 2, '') AS trigger_events,
            -- Disabled status
            tr.is_disabled,
            -- Not for replication
            tr.is_not_for_replication,
            -- Encrypted
            {encrypted_column}
        FROM sys.triggers tr
        INNER JOIN sys.objects o ON tr.parent_id = o.object_id
        INNER JOIN sys.schemas s ON o.schema_id = s.schema_id
        LEFT JOIN sys.sql_modules m ON tr.object_id = m.object_id
        WHERE tr.parent_class = 1  -- Object or column triggers
            AND o.is_ms_shipped = 0
        ORDER BY s.name, OBJECT_NAME(tr.parent_id), tr.name
        """
        
        cursor.execute(dml_query)
        dml_rows = cursor.fetchall()
        
        triggers = []
        
        # Process DML triggers
        for row in dml_rows:
            trigger_data = {
                'routine_name': row.trigger_name,
                'routine_type': 'TRIGGER',
                'return_type': None,
                'definition': row.trigger_definition if not row.is_encrypted else '[ENCRYPTED]',
                'external_language': None,
                'creation_time': row.create_date,
                'call_frequency': 0,
                'dependent_tables': [row.table_name] if row.table_name else [],
                'dependent_views': [],
                'dependent_functions': [],
                'calls_procedures': [],
                'dependency_depth': 0,
                'routine_metadata': {
                    'schema_name': row.schema_name,
                    'modify_date': row.modify_date.isoformat() if row.modify_date else None,
                    'trigger_type': row.trigger_type,
                    'trigger_events': row.trigger_events,
                    'table_name': row.table_name,
                    'is_disabled': row.is_disabled,
                    'is_not_for_replication': row.is_not_for_replication,
                    'is_encrypted': row.is_encrypted,
                    'trigger_level': 'TABLE'
                }
            }
            triggers.append(trigger_data)
        
        # Collect DDL triggers (database-level)
        ddl_query = f"""
        SELECT 
            tr.name AS trigger_name,
            tr.create_date,
            tr.modify_date,
            m.definition AS trigger_definition,
            -- Trigger type
            'DDL' AS trigger_type,
            -- Events
            STUFF((
                SELECT ', ' + te.type_desc
                FROM sys.trigger_events te
                WHERE te.object_id = tr.object_id
                FOR XML PATH(''), TYPE
            ).value('.', 'NVARCHAR(MAX)'), 1, 2, '') AS trigger_events,
            -- Disabled status
            tr.is_disabled,
            -- Encrypted
            {encrypted_column},
            -- Parent type
            tr.parent_class_desc
        FROM sys.triggers tr
        LEFT JOIN sys.sql_modules m ON tr.object_id = m.object_id
        WHERE tr.parent_class = 0  -- Database triggers
        ORDER BY tr.name
        """
        
        cursor.execute(ddl_query)
        ddl_rows = cursor.fetchall()
        
        # Process DDL triggers
        for row in ddl_rows:
            trigger_data = {
                'routine_name': row.trigger_name,
                'routine_type': 'TRIGGER',
                'return_type': None,
                'definition': row.trigger_definition if not row.is_encrypted else '[ENCRYPTED]',
                'external_language': None,
                'creation_time': row.create_date,
                'call_frequency': 0,
                'dependent_tables': [],
                'dependent_views': [],
                'dependent_functions': [],
                'calls_procedures': [],
                'dependency_depth': 0,
                'routine_metadata': {
                    'schema_name': 'DATABASE',
                    'modify_date': row.modify_date.isoformat() if row.modify_date else None,
                    'trigger_type': row.trigger_type,
                    'trigger_events': row.trigger_events,
                    'table_name': None,
                    'is_disabled': row.is_disabled,
                    'is_encrypted': row.is_encrypted,
                    'trigger_level': 'DATABASE',
                    'parent_class': row.parent_class_desc
                }
            }
            triggers.append(trigger_data)
        
        return triggers

    
    async def collect_routine_execution_stats(self) -> Dict[str, Dict]:
        """
        Collect execution statistics for stored procedures, functions, and triggers from Query Store
        Returns a dictionary keyed by object name with execution stats
        
        Uses direct Query Store queries that join on object_id for accurate matching
        """
        cursor = self.connection.cursor()
        
        # Check if Query Store is enabled
        check_query = """
        SELECT actual_state, actual_state_desc
        FROM sys.database_query_store_options
        """
        try:
            cursor.execute(check_query)
            result = cursor.fetchone()
            if not result or result.actual_state != 2:  # 2 = READ_WRITE
                print("[SQL Server Assessment] Query Store not enabled, skipping execution stats", flush=True)
                return {}
        except Exception as e:
            print(f"[SQL Server Assessment] Query Store check failed: {e}, skipping execution stats", flush=True)
            return {}
        
        stats_dict = {}
        
        print("[SQL Server Assessment] Collecting execution stats for stored procedures...", flush=True)
        
        # Query for Stored Procedures - Convert datetimeoffset to datetime to avoid ODBC type -155 error
        proc_query = """
        SELECT
            o.name AS routine_name,
            SUM(rs.count_executions) AS total_executions,
            SUM(CASE
                WHEN CAST(rsi.start_time AS datetime) >= CAST(GETDATE() AS DATE)
                THEN rs.count_executions
                ELSE 0
            END) AS executions_today,
            SUM(CASE
                WHEN CAST(rsi.start_time AS datetime) >= DATEADD(day,-7,GETDATE())
                THEN rs.count_executions
                ELSE 0
            END) AS executions_last_7_days,
            SUM(CASE
                WHEN CAST(rsi.start_time AS datetime) >= DATEADD(day,-30,GETDATE())
                THEN rs.count_executions
                ELSE 0
            END) AS executions_last_30_days,
            AVG(rs.avg_duration)/1000 AS avg_duration_ms,
            CAST(MAX(rsi.end_time) AS datetime) AS last_execution_time
        FROM sys.query_store_runtime_stats rs
        JOIN sys.query_store_runtime_stats_interval rsi
            ON rs.runtime_stats_interval_id = rsi.runtime_stats_interval_id
        JOIN sys.query_store_plan p
            ON rs.plan_id = p.plan_id
        JOIN sys.query_store_query q
            ON p.query_id = q.query_id
        JOIN sys.objects o
            ON q.object_id = o.object_id
        WHERE
            o.type = 'P'
            AND CAST(rsi.start_time AS datetime) >= DATEADD(day,-30,GETDATE())
        GROUP BY o.name
        HAVING SUM(rs.count_executions) > 0
        ORDER BY executions_last_30_days DESC
        """
        
        try:
            cursor.execute(proc_query)
            rows = cursor.fetchall()
            print(f"[SQL Server Assessment] Found {len(rows)} stored procedures with execution stats", flush=True)
            
            for row in rows:
                stats_dict[row.routine_name] = {
                    'total_executions': int(row.total_executions) if row.total_executions else 0,
                    'executions_today': int(row.executions_today) if row.executions_today else 0,
                    'executions_last_7_days': int(row.executions_last_7_days) if row.executions_last_7_days else 0,
                    'executions_last_30_days': int(row.executions_last_30_days) if row.executions_last_30_days else 0,
                    'avg_duration_ms': float(row.avg_duration_ms) if row.avg_duration_ms else 0.0,
                    'last_execution_time': row.last_execution_time.isoformat() if row.last_execution_time else None
                }
        except Exception as e:
            print(f"[SQL Server Assessment] Error collecting procedure stats: {e}", flush=True)
            import traceback
            traceback.print_exc()
        
        print("[SQL Server Assessment] Collecting execution stats for functions...", flush=True)
        
        # Query for Functions - Convert datetimeoffset to datetime to avoid ODBC type -155 error
        func_query = """
        SELECT
            o.name AS routine_name,
            SUM(rs.count_executions) AS total_executions,
            SUM(CASE
                WHEN CAST(rsi.start_time AS datetime) >= CAST(GETDATE() AS DATE)
                THEN rs.count_executions
                ELSE 0
            END) AS executions_today,
            SUM(CASE
                WHEN CAST(rsi.start_time AS datetime) >= DATEADD(day,-7,GETDATE())
                THEN rs.count_executions
                ELSE 0
            END) AS executions_last_7_days,
            SUM(CASE
                WHEN CAST(rsi.start_time AS datetime) >= DATEADD(day,-30,GETDATE())
                THEN rs.count_executions
                ELSE 0
            END) AS executions_last_30_days,
            AVG(rs.avg_duration)/1000 AS avg_duration_ms,
            CAST(MAX(rsi.end_time) AS datetime) AS last_execution_time
        FROM sys.query_store_runtime_stats rs
        JOIN sys.query_store_runtime_stats_interval rsi
            ON rs.runtime_stats_interval_id = rsi.runtime_stats_interval_id
        JOIN sys.query_store_plan p
            ON rs.plan_id = p.plan_id
        JOIN sys.query_store_query q
            ON p.query_id = q.query_id
        JOIN sys.objects o
            ON q.object_id = o.object_id
        WHERE
            o.type IN ('FN','TF','IF')
            AND CAST(rsi.start_time AS datetime) >= DATEADD(day,-30,GETDATE())
        GROUP BY o.name
        HAVING SUM(rs.count_executions) > 0
        ORDER BY executions_last_30_days DESC
        """
        
        try:
            cursor.execute(func_query)
            rows = cursor.fetchall()
            print(f"[SQL Server Assessment] Found {len(rows)} functions with execution stats", flush=True)
            
            for row in rows:
                stats_dict[row.routine_name] = {
                    'total_executions': int(row.total_executions) if row.total_executions else 0,
                    'executions_today': int(row.executions_today) if row.executions_today else 0,
                    'executions_last_7_days': int(row.executions_last_7_days) if row.executions_last_7_days else 0,
                    'executions_last_30_days': int(row.executions_last_30_days) if row.executions_last_30_days else 0,
                    'avg_duration_ms': float(row.avg_duration_ms) if row.avg_duration_ms else 0.0,
                    'last_execution_time': row.last_execution_time.isoformat() if row.last_execution_time else None
                }
        except Exception as e:
            print(f"[SQL Server Assessment] Error collecting function stats: {e}", flush=True)
        
        print("[SQL Server Assessment] Collecting execution stats for triggers...", flush=True)
        
        # Query for Triggers - Convert datetimeoffset to datetime to avoid ODBC type -155 error
        trigger_query = """
        SELECT
            o.name AS routine_name,
            SUM(rs.count_executions) AS total_executions,
            SUM(CASE
                WHEN CAST(rsi.start_time AS datetime) >= CAST(GETDATE() AS DATE)
                THEN rs.count_executions
                ELSE 0
            END) AS executions_today,
            SUM(CASE
                WHEN rsi.start_time >= DATEADD(day,-7,GETDATE())
                THEN rs.count_executions
                ELSE 0
            END) AS executions_last_7_days,
            SUM(CASE
                WHEN CAST(rsi.start_time AS datetime) >= DATEADD(day,-30,GETDATE())
                THEN rs.count_executions
                ELSE 0
            END) AS executions_last_30_days,
            AVG(rs.avg_duration)/1000 AS avg_duration_ms,
            CAST(MAX(rsi.end_time) AS datetime) AS last_execution_time
        FROM sys.query_store_runtime_stats rs
        JOIN sys.query_store_runtime_stats_interval rsi
            ON rs.runtime_stats_interval_id = rsi.runtime_stats_interval_id
        JOIN sys.query_store_plan p
            ON rs.plan_id = p.plan_id
        JOIN sys.query_store_query q
            ON p.query_id = q.query_id
        JOIN sys.objects o
            ON q.object_id = o.object_id
        WHERE
            o.type = 'TR'
            AND CAST(rsi.start_time AS datetime) >= DATEADD(day,-30,GETDATE())
        GROUP BY o.name
        HAVING SUM(rs.count_executions) > 0
        ORDER BY executions_last_30_days DESC
        """
        
        try:
            cursor.execute(trigger_query)
            rows = cursor.fetchall()
            print(f"[SQL Server Assessment] Found {len(rows)} triggers with execution stats", flush=True)
            
            for row in rows:
                stats_dict[row.routine_name] = {
                    'total_executions': int(row.total_executions) if row.total_executions else 0,
                    'executions_today': int(row.executions_today) if row.executions_today else 0,
                    'executions_last_7_days': int(row.executions_last_7_days) if row.executions_last_7_days else 0,
                    'executions_last_30_days': int(row.executions_last_30_days) if row.executions_last_30_days else 0,
                    'avg_duration_ms': float(row.avg_duration_ms) if row.avg_duration_ms else 0.0,
                    'last_execution_time': row.last_execution_time.isoformat() if row.last_execution_time else None
                }
        except Exception as e:
            print(f"[SQL Server Assessment] Error collecting trigger stats: {e}", flush=True)
        
        print(f"[SQL Server Assessment] Total execution stats collected for {len(stats_dict)} routines", flush=True)
        return stats_dict

    
    async def collect_routine_dependencies(self, routine_name: str, schema_name: str = 'dbo') -> Dict:
        """
        Collect dependencies for a specific stored procedure or function
        
        Returns:
        - Tables referenced
        - Views referenced
        - Functions called
        - Stored procedures called
        """
        cursor = self.connection.cursor()
        
        query = """
        SELECT 
            OBJECT_SCHEMA_NAME(referenced_id) AS referenced_schema,
            OBJECT_NAME(referenced_id) AS referenced_object,
            o.type_desc AS referenced_type,
            dep.referenced_entity_name,
            dep.is_caller_dependent,
            dep.is_ambiguous
        FROM sys.sql_expression_dependencies dep
        LEFT JOIN sys.objects o ON dep.referenced_id = o.object_id
        WHERE referencing_id = OBJECT_ID(?)
        ORDER BY referenced_type, referenced_object
        """
        
        try:
            cursor.execute(query, f"{schema_name}.{routine_name}")
            rows = cursor.fetchall()
            
            dependencies = {
                'tables': [],
                'views': [],
                'functions': [],
                'procedures': [],
                'other': []
            }
            
            for row in rows:
                ref_name = row.referenced_object or row.referenced_entity_name
                if not ref_name:
                    continue
                    
                ref_type = row.referenced_type
                
                if ref_type in ('USER_TABLE', 'INTERNAL_TABLE'):
                    dependencies['tables'].append(ref_name)
                elif ref_type == 'VIEW':
                    dependencies['views'].append(ref_name)
                elif ref_type in ('SQL_SCALAR_FUNCTION', 'SQL_TABLE_VALUED_FUNCTION', 'SQL_INLINE_TABLE_VALUED_FUNCTION'):
                    dependencies['functions'].append(ref_name)
                elif ref_type == 'SQL_STORED_PROCEDURE':
                    dependencies['procedures'].append(ref_name)
                else:
                    dependencies['other'].append(ref_name)
            
            return dependencies
            
        except Exception as e:
            print(f"[SQL Server Assessment] Warning: Could not collect dependencies for {routine_name}: {e}", flush=True)
            return {
                'tables': [],
                'views': [],
                'functions': [],
                'procedures': [],
                'other': []
            }
    
    
    async def collect_routine_usage_stats(self, routine_name: str, schema_name: str = 'dbo') -> Dict:
        """
        Collect usage statistics for a stored procedure or function from Query Store
        
        Query Store provides persistent statistics that survive SQL Server restarts,
        unlike DMVs which are volatile and cleared on restart.
        
        Returns:
        - Execution count
        - Last execution time
        - Average execution time
        - Total CPU time
        - Calls per day (estimated)
        """
        print(f"\n[DEBUG] collect_routine_usage_stats called for: {schema_name}.{routine_name}", flush=True)
        
        cursor = self.connection.cursor()
        
        # Pre-concatenate the full object name for OBJECT_ID
        # This avoids parameter binding issues with string concatenation
        full_object_name = f"{schema_name}.{routine_name}"
        
        print(f"[DEBUG] Full object name: {full_object_name}", flush=True)
        
        # First, get the object_id
        object_id_query = "SELECT OBJECT_ID(?)"
        cursor.execute(object_id_query, full_object_name)
        object_id_row = cursor.fetchone()
        object_id = object_id_row[0] if object_id_row else None
        
        print(f"[DEBUG] Object ID: {object_id}", flush=True)
        
        if not object_id:
            print(f"[DEBUG] Object ID is NULL - routine not found in database", flush=True)
            return {
                'execution_count': 0,
                'last_execution_time': None,
                'creation_time': None,
                'total_cpu_time_sec': 0,
                'total_elapsed_time_sec': 0,
                'avg_cpu_time_sec': 0,
                'avg_elapsed_time_sec': 0,
                'total_logical_reads': 0,
                'total_physical_reads': 0,
                'calls_per_day': 0,
                'cache_hit_ratio': 0,
                'permission_error': False
            }
        
        # Use Query Store for persistent statistics
        query = """
        SELECT 
            SUM(rs.count_executions) AS execution_count,
            MAX(rs.last_execution_time) AS last_execution_time,
            MIN(rs.first_execution_time) AS creation_time,
            SUM(rs.avg_cpu_time * rs.count_executions) / 1000000.0 AS total_cpu_time_sec,
            SUM(rs.avg_duration * rs.count_executions) / 1000000.0 AS total_elapsed_time_sec,
            AVG(rs.avg_cpu_time) / 1000000.0 AS avg_cpu_time_sec,
            AVG(rs.avg_duration) / 1000000.0 AS avg_elapsed_time_sec,
            SUM(rs.avg_logical_io_reads * rs.count_executions) AS total_logical_reads,
            SUM(rs.avg_physical_io_reads * rs.count_executions) AS total_physical_reads
        FROM sys.query_store_query q
        JOIN sys.query_store_plan p ON q.query_id = p.query_id
        JOIN sys.query_store_runtime_stats rs ON p.plan_id = rs.plan_id
        WHERE q.object_id = ?
            AND q.object_id IS NOT NULL
        GROUP BY q.object_id
        """
        
        print(f"[DEBUG] Executing Query Store query with object_id: {object_id}", flush=True)
        
        try:
            cursor.execute(query, object_id)
            row = cursor.fetchone()
            
            print(f"[DEBUG] Query executed. Row returned: {row is not None}", flush=True)
            
            if row:
                print(f"[DEBUG] Row data - execution_count: {row.execution_count}, last_execution: {row.last_execution_time}", flush=True)
                
                # Calculate calls per day
                if row.creation_time and row.last_execution_time:
                    days_active = (row.last_execution_time - row.creation_time).total_seconds() / 86400
                    if days_active > 0:
                        calls_per_day = row.execution_count / days_active
                    else:
                        calls_per_day = row.execution_count
                else:
                    calls_per_day = 0
                
                result = {
                    'execution_count': row.execution_count,
                    'last_execution_time': row.last_execution_time.isoformat() if row.last_execution_time else None,
                    'creation_time': row.creation_time.isoformat() if row.creation_time else None,
                    'total_cpu_time_sec': float(row.total_cpu_time_sec),
                    'total_elapsed_time_sec': float(row.total_elapsed_time_sec),
                    'avg_cpu_time_sec': float(row.avg_cpu_time_sec),
                    'avg_elapsed_time_sec': float(row.avg_elapsed_time_sec),
                    'total_logical_reads': row.total_logical_reads,
                    'total_physical_reads': row.total_physical_reads,
                    'calls_per_day': round(calls_per_day, 2),
                    'cache_hit_ratio': round((1 - (row.total_physical_reads / max(row.total_logical_reads, 1))) * 100, 2),
                    'permission_error': False
                }
                print(f"[DEBUG] Returning result with execution_count: {result['execution_count']}", flush=True)
                return result
            else:
                print(f"[DEBUG] No row returned from Query Store - routine has not been executed or not tracked", flush=True)
                return {
                    'execution_count': 0,
                    'last_execution_time': None,
                    'creation_time': None,
                    'total_cpu_time_sec': 0,
                    'total_elapsed_time_sec': 0,
                    'avg_cpu_time_sec': 0,
                    'avg_elapsed_time_sec': 0,
                    'total_logical_reads': 0,
                    'total_physical_reads': 0,
                    'calls_per_day': 0,
                    'cache_hit_ratio': 0,
                    'permission_error': False
                }
                
        except Exception as e:
            print(f"[DEBUG] Exception in collect_routine_usage_stats: {type(e).__name__}: {e}", flush=True)
            error_msg = str(e).lower()
            is_permission_error = 'permission' in error_msg or 'denied' in error_msg
            
            if is_permission_error:
                print(f"[SQL Server Assessment] Permission Error: Cannot access Query Store for usage stats. SQL user needs VIEW SERVER STATE permission.", flush=True)
                # Store permission error flag for first occurrence
                if not hasattr(self, '_dmv_permission_error_logged'):
                    self._dmv_permission_error_logged = True
                    print(f"[SQL Server Assessment] To enable usage statistics, grant permission: GRANT VIEW SERVER STATE TO [your_sql_user]", flush=True)
            else:
                print(f"[SQL Server Assessment] Warning: Could not collect usage stats for {routine_name}: {e}", flush=True)
            
            return {
                'execution_count': 0,
                'last_execution_time': None,
                'creation_time': None,
                'total_cpu_time_sec': 0,
                'total_elapsed_time_sec': 0,
                'avg_cpu_time_sec': 0,
                'avg_elapsed_time_sec': 0,
                'total_logical_reads': 0,
                'total_physical_reads': 0,
                'calls_per_day': 0,
                'cache_hit_ratio': 0,
                'permission_error': is_permission_error
            }
    
    
    async def enrich_views_with_dependencies(self, views: List[Dict]) -> List[Dict]:
        """
        Enrich view data with dependencies using sys.sql_expression_dependencies
        """
        print(f"\n[SQL Server Assessment] Enriching {len(views)} views with dependencies...", flush=True)
        
        for view in views:
            view_name = view['view_name']
            schema_name = view.get('view_metadata', {}).get('schema_name', 'dbo')
            
            try:
                dependencies = await self.collect_routine_dependencies(view_name, schema_name)
                view['dependent_tables'] = dependencies.get('tables', [])
                view['dependent_views'] = dependencies.get('views', [])
                view['dependent_functions'] = dependencies.get('functions', [])
                
                total_deps = len(view['dependent_tables']) + len(view['dependent_views']) + len(view['dependent_functions'])
                view['dependency_depth'] = 1 if total_deps > 0 else 0
                
                print(f"[SQL Server Assessment]   View {schema_name}.{view_name}: {total_deps} dependencies", flush=True)
            except Exception as e:
                print(f"[SQL Server Assessment] Warning: Could not collect dependencies for view {view_name}: {e}", flush=True)
        
        return views
    
    
    async def enrich_routines_with_dependencies_and_usage(self, routines: List[Dict]) -> List[Dict]:
        """
        Enrich routine data with dependencies and usage statistics
        """
        print(f"\n[DEBUG] enrich_routines_with_dependencies_and_usage called with {len(routines)} routines", flush=True)
        enriched_routines = []
        
        for routine in routines:
            routine_name = routine['routine_name']
            schema_name = routine.get('routine_metadata', {}).get('schema_name', 'dbo')
            
            print(f"[DEBUG] Processing routine: {schema_name}.{routine_name}", flush=True)
            
            # Collect dependencies
            dependencies = await self.collect_routine_dependencies(routine_name, schema_name)
            print(f"[DEBUG] Dependencies collected: {len(dependencies.get('tables', []))} tables, {len(dependencies.get('procedures', []))} procedures", flush=True)
            
            # Collect usage statistics
            usage_stats = await self.collect_routine_usage_stats(routine_name, schema_name)
            print(f"[DEBUG] Usage stats collected: execution_count={usage_stats.get('execution_count', 0)}", flush=True)
            
            # Enrich routine data
            routine['dependent_tables'] = dependencies['tables']
            routine['dependent_views'] = dependencies['views']
            routine['dependent_functions'] = dependencies['functions']
            routine['calls_procedures'] = dependencies['procedures']
            routine['call_frequency'] = usage_stats['execution_count']
            
            # Add usage stats to metadata
            if 'routine_metadata' not in routine:
                routine['routine_metadata'] = {}
            
            routine['routine_metadata']['usage_stats'] = usage_stats
            routine['routine_metadata']['dependencies'] = dependencies
            
            enriched_routines.append(routine)
        
        return enriched_routines
    
    
    async def collect_indexes(self) -> List[Dict]:
        """
        Collect index information for both tables and views
        
        Collects:
        - Clustered indexes
        - Non-clustered indexes
        - Unique indexes
        - Filtered indexes
        - Columnstore indexes
        - Full-text indexes
        - Spatial indexes
        - XML indexes
        - Indexed view indexes
        """
        cursor = self.connection.cursor()
        
        # Collect indexes on tables
        table_index_query = """
        SELECT 
            s.name AS schema_name,
            t.name AS table_name,
            'TABLE' AS object_type,
            i.name AS index_name,
            i.type_desc AS index_type,
            i.is_unique,
            i.is_primary_key,
            i.is_unique_constraint,
            i.fill_factor,
            i.is_padded,
            i.is_disabled,
            i.allow_row_locks,
            i.allow_page_locks,
            i.has_filter,
            i.filter_definition,
            -- Compression
            MAX(p.data_compression_desc) AS compression_type,
            -- Index columns
            STUFF((
                SELECT ', ' + c.name + CASE WHEN ic.is_descending_key = 1 THEN ' DESC' ELSE ' ASC' END
                FROM sys.index_columns ic
                INNER JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
                WHERE ic.object_id = i.object_id AND ic.index_id = i.index_id AND ic.is_included_column = 0
                ORDER BY ic.key_ordinal
                FOR XML PATH(''), TYPE
            ).value('.', 'NVARCHAR(MAX)'), 1, 2, '') AS key_columns,
            -- Included columns
            STUFF((
                SELECT ', ' + c.name
                FROM sys.index_columns ic
                INNER JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
                WHERE ic.object_id = i.object_id AND ic.index_id = i.index_id AND ic.is_included_column = 1
                ORDER BY ic.index_column_id
                FOR XML PATH(''), TYPE
            ).value('.', 'NVARCHAR(MAX)'), 1, 2, '') AS included_columns,
            -- Size
            SUM(ps.used_page_count) * 8.0 / 1024 AS size_mb
        FROM sys.indexes i
        INNER JOIN sys.tables t ON i.object_id = t.object_id
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        LEFT JOIN sys.partitions p ON i.object_id = p.object_id AND i.index_id = p.index_id
        LEFT JOIN sys.dm_db_partition_stats ps ON i.object_id = ps.object_id AND i.index_id = ps.index_id
        WHERE t.is_ms_shipped = 0
            AND i.type > 0  -- Exclude heaps
        GROUP BY 
            s.name, t.name, i.name, i.type_desc, i.is_unique, i.is_primary_key,
            i.is_unique_constraint, i.fill_factor, i.is_padded, i.is_disabled,
            i.allow_row_locks, i.allow_page_locks, i.has_filter, i.filter_definition,
            i.object_id, i.index_id
        ORDER BY s.name, t.name, i.name
        """
        
        cursor.execute(table_index_query)
        rows = cursor.fetchall()
        
        indexes = []
        for row in rows:
            size_mb = float(row.size_mb) if row.size_mb else 0.0
            
            index_data = {
                'schema_name': row.schema_name,
                'table_name': row.table_name,
                'object_type': 'TABLE',
                'index_name': row.index_name,
                'index_type': row.index_type,
                'is_unique': bool(row.is_unique),
                'is_primary_key': bool(row.is_primary_key),
                'is_clustered': row.index_type == 'CLUSTERED',
                'key_columns': row.key_columns,
                'included_columns': row.included_columns,
                'filter_definition': row.filter_definition,
                'size_mb': size_mb,
                'row_count': 0,
                'index_metadata': {
                    'is_unique_constraint': bool(row.is_unique_constraint),
                    'compression_type': row.compression_type,
                    'fill_factor': row.fill_factor,
                    'is_disabled': bool(row.is_disabled),
                    'is_padded': bool(row.is_padded),
                    'allow_row_locks': bool(row.allow_row_locks),
                    'allow_page_locks': bool(row.allow_page_locks),
                    'has_filter': bool(row.has_filter)
                }
            }
            indexes.append(index_data)
        
        # Collect indexes on views (indexed/materialized views)
        view_index_query = """
        SELECT 
            s.name AS schema_name,
            v.name AS view_name,
            i.name AS index_name,
            i.type_desc AS index_type,
            i.is_unique,
            i.is_padded,
            i.is_disabled,
            i.allow_row_locks,
            i.allow_page_locks,
            i.has_filter,
            i.filter_definition,
            MAX(p.data_compression_desc) AS compression_type,
            STUFF((
                SELECT ', ' + c.name + CASE WHEN ic.is_descending_key = 1 THEN ' DESC' ELSE ' ASC' END
                FROM sys.index_columns ic
                INNER JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
                WHERE ic.object_id = i.object_id AND ic.index_id = i.index_id AND ic.is_included_column = 0
                ORDER BY ic.key_ordinal
                FOR XML PATH(''), TYPE
            ).value('.', 'NVARCHAR(MAX)'), 1, 2, '') AS key_columns,
            STUFF((
                SELECT ', ' + c.name
                FROM sys.index_columns ic
                INNER JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
                WHERE ic.object_id = i.object_id AND ic.index_id = i.index_id AND ic.is_included_column = 1
                ORDER BY ic.index_column_id
                FOR XML PATH(''), TYPE
            ).value('.', 'NVARCHAR(MAX)'), 1, 2, '') AS included_columns,
            SUM(ps.used_page_count) * 8.0 / 1024 AS size_mb
        FROM sys.indexes i
        INNER JOIN sys.views v ON i.object_id = v.object_id
        INNER JOIN sys.schemas s ON v.schema_id = s.schema_id
        LEFT JOIN sys.partitions p ON i.object_id = p.object_id AND i.index_id = p.index_id
        LEFT JOIN sys.dm_db_partition_stats ps ON i.object_id = ps.object_id AND i.index_id = ps.index_id
        WHERE v.is_ms_shipped = 0
            AND i.type > 0
        GROUP BY 
            s.name, v.name, i.name, i.type_desc, i.is_unique,
            i.is_padded, i.is_disabled,
            i.allow_row_locks, i.allow_page_locks, i.has_filter, i.filter_definition,
            i.object_id, i.index_id
        ORDER BY s.name, v.name, i.name
        """
        
        try:
            cursor.execute(view_index_query)
            view_rows = cursor.fetchall()
            
            for row in view_rows:
                size_mb = float(row.size_mb) if row.size_mb else 0.0
                
                index_data = {
                    'schema_name': row.schema_name,
                    'table_name': row.view_name,  # Store view name in table_name field
                    'object_type': 'VIEW',
                    'index_name': row.index_name,
                    'index_type': row.index_type,
                    'is_unique': bool(row.is_unique),
                    'is_primary_key': False,
                    'is_clustered': row.index_type == 'CLUSTERED',
                    'key_columns': row.key_columns,
                    'included_columns': row.included_columns,
                    'filter_definition': row.filter_definition,
                    'size_mb': size_mb,
                    'row_count': 0,
                    'index_metadata': {
                        'object_type': 'VIEW',
                        'compression_type': row.compression_type,
                        'is_disabled': bool(row.is_disabled),
                        'is_padded': bool(row.is_padded),
                        'allow_row_locks': bool(row.allow_row_locks),
                        'allow_page_locks': bool(row.allow_page_locks),
                        'has_filter': bool(row.has_filter)
                    }
                }
                indexes.append(index_data)
            
            print(f"[SQL Server Assessment] Collected {len(view_rows)} view indexes", flush=True)
        except Exception as e:
            print(f"[SQL Server Assessment] Warning: Could not collect view indexes: {e}", flush=True)
        
        return indexes
    
    async def collect_constraints(self) -> List[Dict]:
        """
        Collect constraint information
        
        Collects:
        - Primary Key constraints
        - Foreign Key constraints
        - Unique constraints
        - Check constraints
        - Default constraints
        """
        cursor = self.connection.cursor()
        
        query = """
        SELECT 
            s.name AS schema_name,
            t.name AS table_name,
            c.name AS constraint_name,
            c.type_desc AS constraint_type,
            -- For FK constraints
            OBJECT_SCHEMA_NAME(fk.referenced_object_id) AS referenced_schema,
            OBJECT_NAME(fk.referenced_object_id) AS referenced_table,
            fk.delete_referential_action_desc AS delete_action,
            fk.update_referential_action_desc AS update_action,
            fk.is_disabled AS fk_is_disabled,
            fk.is_not_trusted AS fk_is_not_trusted,
            -- For check constraints
            cc.definition AS check_definition,
            cc.is_disabled AS check_is_disabled,
            cc.is_not_trusted AS check_is_not_trusted,
            -- For default constraints
            dc.definition AS default_definition,
            -- Columns involved
            STUFF((
                SELECT ', ' + col.name
                FROM sys.index_columns ic
                INNER JOIN sys.columns col ON ic.object_id = col.object_id AND ic.column_id = col.column_id
                INNER JOIN sys.indexes i ON ic.object_id = i.object_id AND ic.index_id = i.index_id
                WHERE i.object_id = c.parent_object_id 
                    AND ((c.type = 'PK' AND i.is_primary_key = 1) OR (c.type = 'UQ' AND i.is_unique_constraint = 1))
                ORDER BY ic.key_ordinal
                FOR XML PATH(''), TYPE
            ).value('.', 'NVARCHAR(MAX)'), 1, 2, '') AS constraint_columns,
            -- For FK, get column mappings
            STUFF((
                SELECT ', ' + COL_NAME(fkc.parent_object_id, fkc.parent_column_id) + ' -> ' + 
                       COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id)
                FROM sys.foreign_key_columns fkc
                WHERE fkc.constraint_object_id = c.object_id
                ORDER BY fkc.constraint_column_id
                FOR XML PATH(''), TYPE
            ).value('.', 'NVARCHAR(MAX)'), 1, 2, '') AS fk_column_mapping
        FROM sys.objects c
        INNER JOIN sys.tables t ON c.parent_object_id = t.object_id
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        LEFT JOIN sys.foreign_keys fk ON c.object_id = fk.object_id
        LEFT JOIN sys.check_constraints cc ON c.object_id = cc.object_id
        LEFT JOIN sys.default_constraints dc ON c.object_id = dc.object_id
        WHERE c.type IN ('PK', 'F', 'UQ', 'C', 'D')
            AND t.is_ms_shipped = 0
        ORDER BY s.name, t.name, c.type_desc, c.name
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        constraints = []
        for row in rows:
            constraint_data = {
                'schema_name': row.schema_name,
                'table_name': row.table_name,
                'constraint_name': row.constraint_name,
                'constraint_type': row.constraint_type,
                'constraint_columns': row.constraint_columns,
                'definition': row.check_definition or row.default_definition,
                'referenced_schema': row.referenced_schema,
                'referenced_table': row.referenced_table,
                'fk_column_mapping': row.fk_column_mapping,
                'metadata': {
                    'delete_action': row.delete_action,
                    'update_action': row.update_action,
                    'is_disabled': row.fk_is_disabled or row.check_is_disabled,
                    'is_not_trusted': row.fk_is_not_trusted or row.check_is_not_trusted
                }
            }
            constraints.append(constraint_data)
        
        return constraints

    
    async def collect_query_stats(self, repo=None, assessment_id=None, db=None) -> List[Dict]:
        """
        Collect SQL Server query execution statistics from Query Store
        
        Query Store provides:
        - Persistent query performance data (survives restarts)
        - Historical execution data with timestamps
        - True time-based filtering capabilities
        - Individual query execution tracking
        
        Falls back to DMV if Query Store is not enabled.
        """
        cursor = self.connection.cursor()
        
        # Set query timeout to 10 seconds to prevent hanging
        cursor.execute("SET LOCK_TIMEOUT 10000")  # 10 seconds
        
        # First, check if Query Store is enabled
        try:
            # Check current database
            cursor.execute("SELECT DB_NAME() AS current_db")
            current_db = cursor.fetchone()
            current_db_name = current_db.current_db if current_db else 'Unknown'
            
            if repo and assessment_id:
                repo.create_log(
                    assessment_id=assessment_id,
                    log_level='INFO',
                    message=f'Checking Query Store status on database: {current_db_name}',
                    stage='metadata_collection'
                )
                db.commit()
            
            cursor.execute("""
                SELECT 
                    actual_state_desc,
                    readonly_reason,
                    actual_state
                FROM sys.database_query_store_options
            """)
            qs_status = cursor.fetchone()
            
            if qs_status:
                status_msg = f"Query Store status: state={qs_status.actual_state}, desc='{qs_status.actual_state_desc}'"
                if repo and assessment_id:
                    repo.create_log(
                        assessment_id=assessment_id,
                        log_level='INFO',
                        message=status_msg,
                        stage='metadata_collection'
                    )
                    db.commit()
            
            # Check if Query Store is enabled (state 2 = READ_WRITE, state 3 = READ_ONLY)
            if qs_status and qs_status.actual_state in (2, 3):
                if repo and assessment_id:
                    repo.create_log(
                        assessment_id=assessment_id,
                        log_level='INFO',
                        message=f'Query Store is enabled ({qs_status.actual_state_desc}), using Query Store for query insights',
                        stage='metadata_collection'
                    )
                    db.commit()
                return await self._collect_from_query_store(cursor, repo, assessment_id, db)
            else:
                status_desc = qs_status.actual_state_desc if qs_status else 'None'
                if repo and assessment_id:
                    repo.create_log(
                        assessment_id=assessment_id,
                        log_level='WARNING',
                        message=f'Query Store is not enabled (status: {status_desc}), falling back to DMV',
                        stage='metadata_collection'
                    )
                    db.commit()
                return await self._collect_from_dmv(cursor, repo, assessment_id, db)
                
        except Exception as e:
            error_msg = f"Could not check Query Store status: {e}, falling back to DMV"
            if repo and assessment_id:
                repo.create_log(
                    assessment_id=assessment_id,
                    log_level='ERROR',
                    message=error_msg,
                    stage='metadata_collection'
                )
                db.commit()
            return await self._collect_from_dmv(cursor, repo, assessment_id, db)
    
    async def _collect_from_query_store(self, cursor, repo=None, assessment_id=None, db=None) -> List[Dict]:
        """
        Collect query statistics from Query Store
        
        Query Store provides historical data with actual execution timestamps,
        enabling true time-based filtering in the UI.
        
        Converts datetimeoffset to datetime to avoid ODBC type -155 errors.
        Collects ALL queries from the past 30 days (no TOP limit) for comprehensive production analysis.
        """
        # Query Store query - ALL queries from past 30 days for complete production insights
        query = """
        SELECT
            qsq.query_id,
            CONVERT(VARCHAR(100), qsq.query_hash) AS query_hash,
            qst.query_sql_text,
            CONVERT(INT, SUM(qrs.count_executions)) AS execution_count,
            CONVERT(DECIMAL(18,6), AVG(CONVERT(DECIMAL(18,6), qrs.avg_duration)) / 1000000.0) AS avg_elapsed_time_sec,
            CONVERT(DECIMAL(18,6), MAX(CONVERT(DECIMAL(18,6), qrs.max_duration)) / 1000000.0) AS max_elapsed_time_sec,
            CONVERT(DECIMAL(18,6), AVG(CONVERT(DECIMAL(18,6), qrs.avg_cpu_time)) / 1000000.0) AS avg_cpu_time_sec,
            CONVERT(DECIMAL(18,2), AVG(CONVERT(DECIMAL(18,2), qrs.avg_logical_io_reads))) AS avg_logical_reads,
            CONVERT(DECIMAL(18,2), AVG(CONVERT(DECIMAL(18,2), qrs.avg_physical_io_reads))) AS avg_physical_reads,
            CONVERT(DATETIME, MAX(qrsi.end_time)) AS execution_time,
            CONVERT(DATETIME, MIN(qrsi.start_time)) AS interval_start_time,
            qsq.object_id,
            OBJECT_NAME(qsq.object_id) AS object_name
        FROM sys.query_store_query qsq
        INNER JOIN sys.query_store_query_text qst 
            ON qsq.query_text_id = qst.query_text_id
        INNER JOIN sys.query_store_plan qsp 
            ON qsq.query_id = qsp.query_id
        INNER JOIN sys.query_store_runtime_stats qrs 
            ON qsp.plan_id = qrs.plan_id
        INNER JOIN sys.query_store_runtime_stats_interval qrsi 
            ON qrs.runtime_stats_interval_id = qrsi.runtime_stats_interval_id
        WHERE qst.query_sql_text NOT LIKE '%sys.query_store%'
            AND qst.query_sql_text NOT LIKE '%sys.database_query_store_options%'
            AND qrsi.end_time >= DATEADD(day, -30, GETUTCDATE())
        GROUP BY 
            qsq.query_id,
            qsq.query_hash,
            qst.query_sql_text,
            qsq.object_id
        HAVING SUM(qrs.count_executions) > 0
        ORDER BY AVG(qrs.avg_duration) DESC
        """
        
        try:
            if repo and assessment_id:
                repo.create_log(
                    assessment_id=assessment_id,
                    log_level='INFO',
                    message='Executing Query Store query...',
                    stage='metadata_collection'
                )
                db.commit()
            
            print(f"[SQL Server Assessment] Executing Query Store collection...", flush=True)
            
            # Set query timeout to 30 seconds
            cursor.execute("SET QUERY_GOVERNOR_COST_LIMIT 0")
            cursor.execute("SET LOCK_TIMEOUT 30000")  # 30 seconds
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            if repo and assessment_id:
                repo.create_log(
                    assessment_id=assessment_id,
                    log_level='INFO',
                    message=f'Retrieved {len(rows)} rows from Query Store',
                    stage='metadata_collection'
                )
                db.commit()
            
            print(f"[SQL Server Assessment] Retrieved {len(rows)} query stats from Query Store", flush=True)
            
            if repo and assessment_id:
                repo.create_log(
                    assessment_id=assessment_id,
                    log_level='INFO',
                    message=f'Processing {len(rows)} query statistics...',
                    stage='metadata_collection'
                )
                db.commit()
            
            # Helper function to clean strings for PostgreSQL
            def clean_string(value):
                """Remove NULL bytes and handle encoding issues"""
                if value is None:
                    return None
                if isinstance(value, bytes):
                    value = value.decode('utf-8', errors='ignore')
                if isinstance(value, str):
                    # Remove NULL bytes that PostgreSQL can't handle
                    value = value.replace('\x00', '')
                    # Also remove other problematic characters
                    value = value.replace('\r\n', '\n').replace('\r', '\n')
                return value
            
            def clean_dict_strings(data):
                """Recursively clean all string values in a dictionary"""
                if isinstance(data, dict):
                    return {k: clean_dict_strings(v) for k, v in data.items()}
                elif isinstance(data, list):
                    return [clean_dict_strings(item) for item in data]
                elif isinstance(data, str):
                    return clean_string(data)
                else:
                    return data
            
            query_stats = []
            for idx, row in enumerate(rows):
                if idx % 50 == 0:  # Log progress every 50 rows
                    print(f"[SQL Server Assessment] Processing row {idx}/{len(rows)}", flush=True)
                
                # Clean all string fields
                query_text = clean_string(row.query_sql_text)
                query_hash = clean_string(row.query_hash)
                object_name = clean_string(row.object_name) if row.object_name else None
                
                # Generate unique job_id - also clean it
                job_id = clean_string(f"sqlserver_qs_{row.query_id}_{query_hash}_{idx}")
                
                stat_data = {
                    'job_id': job_id,
                    'execution_time': row.execution_time,
                    'query_text': query_text[:5000] if query_text and len(query_text) > 5000 else query_text,
                    'bytes_scanned': int(row.avg_logical_reads * 8192),
                    'slot_milliseconds': int(row.avg_cpu_time_sec * 1000),
                    'cache_hit': row.avg_physical_reads == 0,
                    'referenced_tables': [],
                    'user_email': self.username or 'SQL Server User',
                    'query_metadata': {
                        'query_id': row.query_id,
                        'query_hash': query_hash,
                        'object_name': object_name,
                        'execution_count': row.execution_count,
                        'execution_time': row.execution_time.isoformat() if row.execution_time else None,
                        'avg_cpu_time_sec': float(row.avg_cpu_time_sec),
                        'avg_elapsed_time_sec': float(row.avg_elapsed_time_sec),
                        'max_elapsed_time_sec': float(row.max_elapsed_time_sec),
                        'avg_logical_reads': float(row.avg_logical_reads),
                        'avg_physical_reads': float(row.avg_physical_reads),
                        'data_source': 'query_store'
                    }
                }
                
                # Deep clean all string values in the entire stat_data dictionary
                stat_data = clean_dict_strings(stat_data)
                query_stats.append(stat_data)
            
            if repo and assessment_id:
                repo.create_log(
                    assessment_id=assessment_id,
                    log_level='INFO',
                    message=f'Successfully processed {len(query_stats)} query statistics from Query Store',
                    stage='metadata_collection'
                )
                db.commit()
            
            print(f"[SQL Server Assessment] Successfully processed {len(query_stats)} query stats from Query Store", flush=True)
            return query_stats
            
        except Exception as e:
            error_msg = f"Error collecting from Query Store: {e}, falling back to DMV"
            if repo and assessment_id:
                repo.create_log(
                    assessment_id=assessment_id,
                    log_level='ERROR',
                    message=error_msg,
                    stage='metadata_collection'
                )
                db.commit()
            return await self._collect_from_dmv(cursor, repo, assessment_id, db)
    
    async def _collect_from_dmv(self, cursor, repo=None, assessment_id=None, db=None) -> List[Dict]:
        """
        Fallback: Collect query statistics from DMV when Query Store is not available
        
        DMV provides cumulative statistics but lacks historical time-based data.
        """
        query = """
        SELECT
            -- Query identification
            qs.sql_handle,
            qs.plan_handle,
            SUBSTRING(
                qt.text,
                (qs.statement_start_offset/2) + 1,
                ((CASE qs.statement_end_offset
                    WHEN -1 THEN DATALENGTH(qt.text)
                    ELSE qs.statement_end_offset
                END - qs.statement_start_offset)/2) + 1
            ) AS query_text,
            
            -- Execution statistics
            qs.execution_count,
            qs.total_worker_time / 1000000.0 AS total_cpu_time_sec,
            qs.total_elapsed_time / 1000000.0 AS total_elapsed_time_sec,
            qs.total_logical_reads,
            qs.total_physical_reads,
            qs.total_logical_writes,
            
            -- Average statistics
            (qs.total_worker_time / qs.execution_count) / 1000000.0 AS avg_cpu_time_sec,
            (qs.total_elapsed_time / qs.execution_count) / 1000000.0 AS avg_elapsed_time_sec,
            qs.total_logical_reads / qs.execution_count AS avg_logical_reads,
            qs.total_physical_reads / qs.execution_count AS avg_physical_reads,
            
            -- Min/Max statistics
            qs.min_worker_time / 1000000.0 AS min_cpu_time_sec,
            qs.max_worker_time / 1000000.0 AS max_cpu_time_sec,
            qs.min_elapsed_time / 1000000.0 AS min_elapsed_time_sec,
            qs.max_elapsed_time / 1000000.0 AS max_elapsed_time_sec,
            
            -- Timing
            qs.creation_time,
            qs.last_execution_time
            
        FROM sys.dm_exec_query_stats qs
        CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) qt
        WHERE qt.text NOT LIKE '%sys.dm_exec_query_stats%'
            AND qt.text NOT LIKE '%sys.tables%'
            AND qt.text NOT LIKE '%sys.columns%'
            AND qt.text NOT LIKE '%sys.indexes%'
            AND qt.text NOT LIKE '%sys.objects%'
            AND qt.text NOT LIKE '%INFORMATION_SCHEMA%'
            AND qt.text NOT LIKE '%sys.dm_db_partition_stats%'
            AND qt.text NOT LIKE '%sys.sql_modules%'
            AND qt.text NOT LIKE '%sys.triggers%'
            AND qs.execution_count > 0
        ORDER BY qs.total_elapsed_time DESC
        """
        
        try:
            print(f"[SQL Server Assessment] Executing DMV query stats collection...", flush=True)
            cursor.execute(query)
            rows = cursor.fetchall()
            print(f"[SQL Server Assessment] Retrieved {len(rows)} query stats from DMV", flush=True)
            
            # Helper function to clean strings for PostgreSQL
            def clean_string(value):
                """Remove NULL bytes and handle encoding issues"""
                if value is None:
                    return None
                if isinstance(value, bytes):
                    value = value.decode('utf-8', errors='ignore')
                if isinstance(value, str):
                    # Remove NULL bytes that PostgreSQL can't handle
                    value = value.replace('\x00', '')
                    # Also remove other problematic characters
                    value = value.replace('\r\n', '\n').replace('\r', '\n')
                return value
            
            def clean_dict_strings(data):
                """Recursively clean all string values in a dictionary"""
                if isinstance(data, dict):
                    return {k: clean_dict_strings(v) for k, v in data.items()}
                elif isinstance(data, list):
                    return [clean_dict_strings(item) for item in data]
                elif isinstance(data, str):
                    return clean_string(data)
                else:
                    return data
            
            query_stats = []
            for row in rows:
                query_text = clean_string(row.query_text)
                
                stat_data = {
                    'job_id': clean_string(f"sqlserver_dmv_{hash(str(row.sql_handle))}"),
                    'execution_time': row.last_execution_time,
                    'query_text': query_text[:5000] if query_text and len(query_text) > 5000 else query_text,
                    'bytes_scanned': int(row.total_logical_reads * 8192),
                    'slot_milliseconds': int(row.total_cpu_time_sec * 1000),
                    'cache_hit': row.total_physical_reads == 0,
                    'referenced_tables': [],
                    'user_email': self.username or 'SQL Server User',
                    'query_metadata': {
                        'execution_count': row.execution_count,
                        'total_cpu_time_sec': float(row.total_cpu_time_sec),
                        'total_elapsed_time_sec': float(row.total_elapsed_time_sec),
                        'total_logical_reads': row.total_logical_reads,
                        'total_physical_reads': row.total_physical_reads,
                        'total_logical_writes': row.total_logical_writes,
                        'avg_cpu_time_sec': float(row.avg_cpu_time_sec),
                        'avg_elapsed_time_sec': float(row.avg_elapsed_time_sec),
                        'avg_logical_reads': float(row.avg_logical_reads),
                        'avg_physical_reads': float(row.avg_physical_reads),
                        'min_cpu_time_sec': float(row.min_cpu_time_sec),
                        'max_cpu_time_sec': float(row.max_cpu_time_sec),
                        'min_elapsed_time_sec': float(row.min_elapsed_time_sec),
                        'max_elapsed_time_sec': float(row.max_elapsed_time_sec),
                        'creation_time': row.creation_time.isoformat() if row.creation_time else None,
                        'query_plan': None,
                        'data_source': 'dmv'
                    }
                }
                
                # Deep clean all string values in the entire stat_data dictionary
                stat_data = clean_dict_strings(stat_data)
                query_stats.append(stat_data)
            
            print(f"[SQL Server Assessment] Successfully processed {len(query_stats)} query stats from DMV", flush=True)
            return query_stats
            
        except Exception as e:
            print(f"[SQL Server Assessment] Warning: Could not collect query stats from DMV: {e}", flush=True)
            return []

    async def collect_security_metadata(self) -> List[Dict]:
        """
        Collect comprehensive SQL Server security metadata including:
        - Database users and authentication types
        - Server logins and security policies
        - Database roles and memberships
        - Object permissions (tables, views, procedures)
        - Schema ownership
        - Security policies (RLS, CLS)
        - Encryption information
        """
        security_policies = []
        cursor = self.connection.cursor()

        # 1. Collect Database Users
        try:
            print("[SQL Server Assessment] Collecting database users...", flush=True)
            users_query = """
            SELECT 
                dp.name AS user_name,
                dp.type_desc AS user_type,
                dp.authentication_type_desc AS authentication_type,
                dp.default_schema_name,
                STUFF((
                    SELECT ', ' + r2.name
                    FROM sys.database_role_members rm2
                    JOIN sys.database_principals r2 ON rm2.role_principal_id = r2.principal_id
                    WHERE rm2.member_principal_id = dp.principal_id
                    FOR XML PATH(''), TYPE
                ).value('.', 'NVARCHAR(MAX)'), 1, 2, '') AS roles,
                dp.create_date,
                dp.modify_date AS last_login,
                0 AS is_disabled,
                0 AS is_locked,
                CASE WHEN dp.authentication_type = 1 THEN 'Windows Authentication' 
                     ELSE 'SQL Server Authentication' END AS password_policy
            FROM sys.database_principals dp
            WHERE dp.type IN ('S', 'U', 'G')
                AND dp.name NOT IN ('dbo', 'guest', 'INFORMATION_SCHEMA', 'sys')
            ORDER BY dp.name
            """

            cursor.execute(users_query)
            users_rows = cursor.fetchall()
            print(f"[SQL Server Assessment] Found {len(users_rows)} database users", flush=True)

            for row in users_rows:
                security_policies.append({
                    'security_type': 'USER',
                    'table_name': None,
                    'policy_name': row.user_name,
                    'filter_predicate': None,
                    'grantees': [row.user_name],
                    'creation_time': row.create_date,
                    'security_metadata': {
                        'user_name': row.user_name,
                        'user_type': row.user_type,
                        'authentication_type': row.authentication_type,
                        'default_schema': row.default_schema_name or 'dbo',
                        'roles': row.roles or 'None',
                        'create_date': row.create_date.isoformat() if row.create_date else None,
                        'last_login': row.last_login.isoformat() if row.last_login else None,
                        'is_disabled': bool(row.is_disabled),
                        'is_locked': bool(row.is_locked),
                        'password_policy': row.password_policy
                    }
                })
        except Exception as e:
            print(f"[SQL Server Assessment] Error collecting database users: {e}", flush=True)
            
        # 2. Collect Server Logins
        try:
            print("[SQL Server Assessment] Collecting server logins...", flush=True)
            logins_query = """
            SELECT 
                sp.name AS login_name,
                sp.type_desc AS login_type,
                sp.is_disabled,
                ISNULL(sl.is_policy_checked, 0) AS password_policy_enforced,
                ISNULL(sl.is_expiration_checked, 0) AS password_expiration_enforced,
                0 AS failed_login_attempts,
                sp.create_date,
                STUFF((
                    SELECT ', ' + r2.name
                    FROM sys.server_role_members srm2
                    JOIN sys.server_principals r2 ON srm2.role_principal_id = r2.principal_id AND r2.type = 'R'
                    WHERE srm2.member_principal_id = sp.principal_id
                    FOR XML PATH(''), TYPE
                ).value('.', 'NVARCHAR(MAX)'), 1, 2, '') AS server_roles
            FROM sys.server_principals sp
            LEFT JOIN sys.sql_logins sl ON sp.principal_id = sl.principal_id
            WHERE sp.type IN ('S', 'U', 'G')
                AND sp.name NOT LIKE '##%'
                AND sp.name NOT LIKE 'NT %'
            ORDER BY sp.name
            """

            cursor.execute(logins_query)
            logins_rows = cursor.fetchall()
            print(f"[SQL Server Assessment] Found {len(logins_rows)} server logins", flush=True)

            for row in logins_rows:
                server_roles = row.server_roles.split(', ') if row.server_roles else []
                security_policies.append({
                    'security_type': 'LOGIN',
                    'table_name': None,
                    'policy_name': row.login_name,
                    'filter_predicate': None,
                    'grantees': [row.login_name],
                    'creation_time': row.create_date,
                    'security_metadata': {
                        'login_name': row.login_name,
                        'login_type': row.login_type,
                        'is_disabled': bool(row.is_disabled),
                        'is_locked': False,
                        'password_policy_enforced': bool(row.password_policy_enforced),
                        'password_expiration_enforced': bool(row.password_expiration_enforced),
                        'failed_login_attempts': row.failed_login_attempts,
                        'last_successful_login': None,
                        'server_roles': server_roles
                    }
                })
        except Exception as e:
            print(f"[SQL Server Assessment] Error collecting server logins: {e}", flush=True)
            
        # 3. Collect Database Roles
        try:
            print("[SQL Server Assessment] Collecting database roles...", flush=True)
            roles_query = """
            SELECT 
                dp.name AS role_name,
                CASE WHEN dp.is_fixed_role = 1 THEN 'Fixed Role' ELSE 'User Defined' END AS role_category,
                dp.is_fixed_role,
                COUNT(rm.member_principal_id) AS members_count,
                NULL AS description
            FROM sys.database_principals dp
            LEFT JOIN sys.database_role_members rm ON dp.principal_id = rm.role_principal_id
            WHERE dp.type = 'R'
                AND dp.name NOT IN ('public')
            GROUP BY dp.name, dp.is_fixed_role
            ORDER BY dp.name
            """

            cursor.execute(roles_query)
            roles_rows = cursor.fetchall()
            print(f"[SQL Server Assessment] Found {len(roles_rows)} database roles", flush=True)

            for row in roles_rows:
                security_policies.append({
                    'security_type': 'ROLE',
                    'table_name': None,
                    'policy_name': row.role_name,
                    'filter_predicate': None,
                    'grantees': [row.role_name],
                    'creation_time': None,
                    'security_metadata': {
                        'role_name': row.role_name,
                        'role_category': row.role_category,
                        'is_fixed_role': bool(row.is_fixed_role),
                        'members_count': row.members_count,
                        'description': row.description
                    }
                })
        except Exception as e:
            print(f"[SQL Server Assessment] Error collecting database roles: {e}", flush=True)
            
        # 4. Collect Object Permissions
        try:
            print("[SQL Server Assessment] Collecting object permissions...", flush=True)
            permissions_query = """
            SELECT 
                s.name AS schema_name,
                o.name AS object_name,
                o.type_desc AS object_type,
                pr.name AS user_or_role,
                p.permission_name,
                p.state_desc AS permission_state,
                grantor.name AS grantor,
                CASE WHEN p.state = 'W' THEN 1 ELSE 0 END AS is_grantable
            FROM sys.database_permissions p
            LEFT JOIN sys.objects o ON p.major_id = o.object_id
            LEFT JOIN sys.schemas s ON o.schema_id = s.schema_id
            LEFT JOIN sys.database_principals pr ON p.grantee_principal_id = pr.principal_id
            LEFT JOIN sys.database_principals grantor ON p.grantor_principal_id = grantor.principal_id
            WHERE p.major_id > 0
                AND o.name IS NOT NULL
                AND pr.name IS NOT NULL
            ORDER BY s.name, o.name, pr.name, p.permission_name
            """

            cursor.execute(permissions_query)
            permissions_rows = cursor.fetchall()
            print(f"[SQL Server Assessment] Found {len(permissions_rows)} object permissions", flush=True)

            for row in permissions_rows:
                security_policies.append({
                    'security_type': 'PERMISSION',
                    'table_name': f"{row.schema_name}.{row.object_name}",
                    'policy_name': f"{row.user_or_role}_{row.permission_name}",
                    'filter_predicate': None,
                    'grantees': [row.user_or_role],
                    'creation_time': None,
                    'security_metadata': {
                        'schema_name': row.schema_name,
                        'object_name': row.object_name,
                        'object_type': row.object_type,
                        'user_or_role': row.user_or_role,
                        'permission_name': row.permission_name,
                        'permission_state': row.permission_state,
                        'grantor': row.grantor,
                        'is_grantable': bool(row.is_grantable)
                    }
                })
        except Exception as e:
            print(f"[SQL Server Assessment] Error collecting object permissions: {e}", flush=True)
            
        # 5. Collect Schema Ownership
        try:
            print("[SQL Server Assessment] Collecting schema ownership...", flush=True)
            schemas_query = """
            SELECT 
                s.name AS schema_name,
                pr.name AS owner_name,
                pr.type_desc AS owner_type,
                NULL AS created_date
            FROM sys.schemas s
            LEFT JOIN sys.database_principals pr ON s.principal_id = pr.principal_id
            WHERE s.name NOT IN ('guest', 'INFORMATION_SCHEMA', 'sys')
            ORDER BY s.name
            """

            cursor.execute(schemas_query)
            schemas_rows = cursor.fetchall()
            print(f"[SQL Server Assessment] Found {len(schemas_rows)} schemas", flush=True)

            for row in schemas_rows:
                security_policies.append({
                    'security_type': 'SCHEMA',
                    'table_name': None,
                    'policy_name': row.schema_name,
                    'filter_predicate': None,
                    'grantees': [row.owner_name] if row.owner_name else [],
                    'creation_time': None,
                    'security_metadata': {
                        'schema_name': row.schema_name,
                        'owner_name': row.owner_name or 'dbo',
                        'owner_type': row.owner_type or 'SQL_USER',
                        'created_date': row.created_date
                    }
                })
        except Exception as e:
            print(f"[SQL Server Assessment] Error collecting schema ownership: {e}", flush=True)
            
        # 6. Collect Security Policies (Row-Level Security)
        try:
            print("[SQL Server Assessment] Collecting security policies...", flush=True)
            policies_query = """
            SELECT 
                sp.name AS policy_name,
                'SECURITY' AS policy_type,
                s.name AS table_schema,
                t.name AS table_name,
                pred.predicate_definition AS filter_predicate,
                sp.is_enabled,
                sp.create_date,
                pred.predicate_type_desc
            FROM sys.security_policies sp
            LEFT JOIN sys.security_predicates pred ON sp.object_id = pred.object_id
            LEFT JOIN sys.tables t ON pred.target_object_id = t.object_id
            LEFT JOIN sys.schemas s ON t.schema_id = s.schema_id
            ORDER BY sp.name
            """

            cursor.execute(policies_query)
            policies_rows = cursor.fetchall()
            print(f"[SQL Server Assessment] Found {len(policies_rows)} security policies", flush=True)

            for row in policies_rows:
                security_policies.append({
                    'security_type': 'SECURITY_POLICY',
                    'table_name': f"{row.table_schema}.{row.table_name}" if row.table_schema and row.table_name else None,
                    'policy_name': row.policy_name,
                    'filter_predicate': row.filter_predicate,
                    'grantees': [],
                    'creation_time': row.create_date,
                    'security_metadata': {
                        'policy_name': row.policy_name,
                        'policy_type': row.predicate_type_desc or row.policy_type,
                        'table_schema': row.table_schema,
                        'table_name': row.table_name,
                        'filter_predicate': row.filter_predicate,
                        'is_enabled': bool(row.is_enabled),
                        'created_date': row.create_date.isoformat() if row.create_date else None
                    }
                })
        except Exception as e:
            print(f"[SQL Server Assessment] Note: Security policies not available (requires SQL Server 2016+): {e}", flush=True)
            
        # 7. Collect Encryption Information
        try:
            print("[SQL Server Assessment] Collecting encryption information...", flush=True)
            encryption_query = """
            SELECT 
                'DATABASE_ENCRYPTION' AS encryption_type,
                dmk.name AS key_name,
                dmk.algorithm_desc AS algorithm,
                dmk.key_length,
                COUNT(c.column_id) AS encrypted_objects_count,
                dmk.create_date
            FROM sys.symmetric_keys dmk
            LEFT JOIN sys.column_encryption_keys cek ON dmk.symmetric_key_id = cek.column_encryption_key_id
            LEFT JOIN sys.column_encryption_key_values cekv ON cek.column_encryption_key_id = cekv.column_encryption_key_id
            LEFT JOIN sys.columns c ON c.encryption_type IS NOT NULL
            WHERE dmk.name != '##MS_ServiceMasterKey##'
            GROUP BY dmk.name, dmk.algorithm_desc, dmk.key_length, dmk.create_date

            UNION ALL

            SELECT 
                'TRANSPARENT_DATA_ENCRYPTION' AS encryption_type,
                'TDE_Certificate' AS key_name,
                'AES' AS algorithm,
                256 AS key_length,
                1 AS encrypted_objects_count,
                NULL AS create_date
            FROM sys.dm_database_encryption_keys dek
            WHERE dek.encryption_state = 3
            """

            cursor.execute(encryption_query)
            encryption_rows = cursor.fetchall()
            print(f"[SQL Server Assessment] Found {len(encryption_rows)} encryption entries", flush=True)

            for row in encryption_rows:
                security_policies.append({
                    'security_type': 'ENCRYPTION',
                    'table_name': None,
                    'policy_name': row.key_name,
                    'filter_predicate': None,
                    'grantees': [],
                    'creation_time': row.create_date,
                    'security_metadata': {
                        'encryption_type': row.encryption_type,
                        'key_name': row.key_name,
                        'algorithm': row.algorithm,
                        'key_length': row.key_length,
                        'encrypted_objects_count': row.encrypted_objects_count,
                        'created_date': row.create_date.isoformat() if row.create_date else None
                    }
                })
        except Exception as e:
            print(f"[SQL Server Assessment] Note: Encryption information not available: {e}", flush=True)

        # 8. Collect Linked Servers
        try:
            print("[SQL Server Assessment] Collecting linked servers...", flush=True)
            linked_servers_query = """
            SELECT 
                s.name AS server_name,
                s.product,
                s.provider AS provider_name,
                s.data_source,
                s.catalog AS default_catalog,
                s.is_linked,
                s.is_remote_login_enabled,
                s.is_rpc_out_enabled,
                s.is_data_access_enabled,
                s.modify_date,
                STUFF((
                    SELECT ', ' + ll.remote_name
                    FROM sys.linked_logins ll
                    WHERE ll.server_id = s.server_id AND ll.remote_name IS NOT NULL
                    FOR XML PATH(''), TYPE
                ).value('.', 'NVARCHAR(MAX)'), 1, 2, '') AS mapped_logins
            FROM sys.servers s
            WHERE s.is_linked = 1
            ORDER BY s.name
            """

            cursor.execute(linked_servers_query)
            linked_rows = cursor.fetchall()
            print(f"[SQL Server Assessment] Found {len(linked_rows)} linked servers", flush=True)

            for row in linked_rows:
                security_policies.append({
                    'security_type': 'LINKED_SERVER',
                    'table_name': None,
                    'policy_name': row.server_name,
                    'filter_predicate': None,
                    'grantees': [],
                    'creation_time': row.modify_date,
                    'security_metadata': {
                        'server_name': row.server_name,
                        'product': row.product or '',
                        'provider_name': row.provider_name or '',
                        'data_source': row.data_source or '',
                        'default_catalog': row.default_catalog or '',
                        'is_remote_login_enabled': bool(row.is_remote_login_enabled),
                        'is_rpc_out_enabled': bool(row.is_rpc_out_enabled),
                        'is_data_access_enabled': bool(row.is_data_access_enabled),
                        'mapped_logins': row.mapped_logins or '',
                        'modified_date': row.modify_date.isoformat() if row.modify_date else None
                    }
                })
        except Exception as e:
            print(f"[SQL Server Assessment] Note: Linked servers not available: {e}", flush=True)

        print(f"[SQL Server Assessment] ✓ Collected {len(security_policies)} total security policies", flush=True)
        return security_policies











    async def collect_agent_jobs(self) -> List[Dict]:
        """Collect SQL Agent jobs from msdb"""
        cursor = self.connection.cursor()
        jobs = []
        query = """
        SELECT j.name AS job_name, j.enabled, j.description, j.date_created, j.date_modified,
               (SELECT COUNT(*) FROM msdb.dbo.sysjobsteps js WHERE js.job_id = j.job_id) AS step_count
        FROM msdb.dbo.sysjobs j
        ORDER BY j.name
        """
        try:
            cursor.execute(query)
            for row in cursor.fetchall():
                steps = []
                step_query = """
                SELECT step_name, subsystem, command, database_name, retry_attempts, retry_interval
                FROM msdb.dbo.sysjobsteps WHERE job_id = (SELECT job_id FROM msdb.dbo.sysjobs WHERE name = ?)
                ORDER BY step_id
                """
                cursor.execute(step_query, row.job_name)
                for s in cursor.fetchall():
                    steps.append({
                        'step_name': s.step_name, 'subsystem': s.subsystem,
                        'command': s.command, 'database_name': s.database_name,
                        'retry_attempts': s.retry_attempts, 'retry_interval': s.retry_interval
                    })
                jobs.append({
                    'job_name': row.job_name, 'enabled': bool(row.enabled),
                    'description': row.description or '',
                    'date_created': row.date_created.isoformat() if row.date_created else None,
                    'date_modified': row.date_modified.isoformat() if row.date_modified else None,
                    'step_count': row.step_count, 'steps': steps
                })
        except Exception as e:
            print(f"[SQL Server Assessment] Agent jobs query failed: {e}", flush=True)
        return jobs

    async def collect_certificates(self) -> List[Dict]:
        """Collect database certificates"""
        cursor = self.connection.cursor()
        certs = []
        query = """
        SELECT name, certificate_id, pvt_key_encryption_type_desc,
               subject, start_date, expiry_date, issuer_name
        FROM sys.certificates WHERE name NOT LIKE '##%'
        """
        try:
            cursor.execute(query)
            for row in cursor.fetchall():
                certs.append({
                    'name': row.name, 'certificate_id': row.certificate_id,
                    'encryption_type': row.pvt_key_encryption_type_desc,
                    'subject': row.subject, 'issuer': row.issuer_name,
                    'start_date': row.start_date.isoformat() if row.start_date else None,
                    'expiry_date': row.expiry_date.isoformat() if row.expiry_date else None
                })
        except Exception as e:
            print(f"[SQL Server Assessment] Certificates query failed: {e}", flush=True)
        return certs

    async def collect_encryption(self) -> Dict:
        """Collect encryption keys and TDE status"""
        cursor = self.connection.cursor()
        result = {'symmetric_keys': [], 'asymmetric_keys': [], 'tde_enabled': False}
        try:
            cursor.execute("SELECT name, algorithm_desc, key_length FROM sys.symmetric_keys WHERE name NOT LIKE '##%'")
            for row in cursor.fetchall():
                result['symmetric_keys'].append({'name': row.name, 'algorithm': row.algorithm_desc, 'key_length': row.key_length})
        except Exception as e:
            print(f"[SQL Server Assessment] Symmetric keys query failed: {e}", flush=True)
        try:
            cursor.execute("SELECT name, algorithm_desc, key_length FROM sys.asymmetric_keys")
            for row in cursor.fetchall():
                result['asymmetric_keys'].append({'name': row.name, 'algorithm': row.algorithm_desc, 'key_length': row.key_length})
        except Exception as e:
            print(f"[SQL Server Assessment] Asymmetric keys query failed: {e}", flush=True)
        try:
            cursor.execute("SELECT db.name, dek.encryption_state FROM sys.dm_database_encryption_keys dek JOIN sys.databases db ON dek.database_id = db.database_id")
            tde_rows = cursor.fetchall()
            result['tde_enabled'] = len(tde_rows) > 0
            result['tde_databases'] = [{'database': r.name, 'state': r.encryption_state} for r in tde_rows]
        except Exception as e:
            result['tde_databases'] = []
        return result

    async def collect_assemblies(self) -> List[Dict]:
        """Collect CLR assemblies"""
        cursor = self.connection.cursor()
        assemblies = []
        try:
            cursor.execute("SELECT name, permission_set_desc, create_date, is_user_defined FROM sys.assemblies WHERE is_user_defined = 1")
            for row in cursor.fetchall():
                assemblies.append({
                    'name': row.name, 'permission_set': row.permission_set_desc,
                    'create_date': row.create_date.isoformat() if row.create_date else None
                })
        except Exception as e:
            print(f"[SQL Server Assessment] Assemblies query failed: {e}", flush=True)
        return assemblies

    async def collect_policies(self) -> List[Dict]:
        """Collect Policy-Based Management policies from msdb"""
        cursor = self.connection.cursor()
        policies = []
        try:
            cursor.execute("SELECT name, is_enabled, execution_mode FROM msdb.dbo.syspolicy_policies")
            for row in cursor.fetchall():
                policies.append({'name': row.name, 'is_enabled': bool(row.is_enabled), 'execution_mode': row.execution_mode})
        except Exception as e:
            print(f"[SQL Server Assessment] Policies query failed: {e}", flush=True)
        return policies

    async def collect_replication(self) -> Dict:
        """Collect replication status"""
        cursor = self.connection.cursor()
        result = {'is_published': False, 'is_subscribed': False, 'is_merge_published': False, 'publications': []}
        try:
            cursor.execute("SELECT name, is_published, is_subscribed, is_merge_published FROM sys.databases WHERE name = DB_NAME()")
            row = cursor.fetchone()
            if row:
                result['is_published'] = bool(row.is_published)
                result['is_subscribed'] = bool(row.is_subscribed)
                result['is_merge_published'] = bool(row.is_merge_published)
        except Exception as e:
            print(f"[SQL Server Assessment] Replication query failed: {e}", flush=True)
        return result

    async def collect_computed_columns(self) -> List[Dict]:
        """Collect all computed columns across tables"""
        cursor = self.connection.cursor()
        computed = []
        try:
            cursor.execute("""
                SELECT s.name AS schema_name, t.name AS table_name, c.name AS column_name,
                       c.definition, c.is_persisted
                FROM sys.computed_columns c
                JOIN sys.tables t ON c.object_id = t.object_id
                JOIN sys.schemas s ON t.schema_id = s.schema_id
                ORDER BY s.name, t.name, c.name
            """)
            for row in cursor.fetchall():
                computed.append({
                    'schema_name': row.schema_name, 'table_name': row.table_name,
                    'column_name': row.column_name, 'definition': row.definition,
                    'is_persisted': bool(row.is_persisted)
                })
        except Exception as e:
            print(f"[SQL Server Assessment] Computed columns query failed: {e}", flush=True)
        return computed

    async def collect_user_defined_types(self) -> List[Dict]:
        """Collect user-defined types (alias types and table types)"""
        cursor = self.connection.cursor()
        udts = []
        try:
            cursor.execute("""
                SELECT t.name AS type_name, st.name AS base_type, t.max_length,
                       t.precision, t.scale, t.is_nullable, t.is_table_type
                FROM sys.types t
                LEFT JOIN sys.types st ON t.system_type_id = st.system_type_id
                    AND st.is_user_defined = 0 AND st.user_type_id = st.system_type_id
                WHERE t.is_user_defined = 1
                ORDER BY t.name
            """)
            for row in cursor.fetchall():
                udts.append({
                    'type_name': row.type_name, 'base_type': row.base_type,
                    'max_length': row.max_length, 'precision': row.precision,
                    'scale': row.scale, 'is_nullable': bool(row.is_nullable),
                    'is_table_type': bool(row.is_table_type)
                })
        except Exception as e:
            print(f"[SQL Server Assessment] UDT query failed: {e}", flush=True)
        return udts