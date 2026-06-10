"""
ClickHouse Migration Service

Handles the BigQuery → GCS → ClickHouse migration pipeline.
Stages per table:
  1. Schema Creation (CREATE TABLE in ClickHouse)
  2. Export (EXPORT DATA from BigQuery to GCS as Parquet)
  3. Import (INSERT INTO ... SELECT FROM s3() in ClickHouse)
  4. Verify (Row count comparison)
"""

import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


# BigQuery to ClickHouse type mapping
BQ_TO_CLICKHOUSE_TYPES = {
    'STRING': 'String',
    'BYTES': 'String',
    'INT64': 'Int64',
    'INTEGER': 'Int64',
    'INT': 'Int32',
    'SMALLINT': 'Int16',
    'TINYINT': 'Int8',
    'FLOAT64': 'Float64',
    'FLOAT': 'Float32',
    'NUMERIC': 'Decimal(38, 10)',
    'BIGNUMERIC': 'Decimal(76, 38)',
    'DECIMAL': 'Decimal(38, 10)',
    'BOOL': 'UInt8',
    'BOOLEAN': 'UInt8',
    'DATE': 'Date32',
    'DATETIME': 'DateTime64(6)',
    'TIMESTAMP': 'DateTime64(6)',
    'TIME': 'String',
    'GEOGRAPHY': 'String',
    'JSON': 'String',
}


def map_bq_type_to_clickhouse(bq_type: str, is_nullable: bool = True) -> str:
    """Map a BigQuery data type to ClickHouse equivalent."""
    base_type = bq_type.upper().split('(')[0].strip()

    # Handle ARRAY types
    if base_type == 'ARRAY' or bq_type.upper().startswith('ARRAY<'):
        inner = bq_type.upper().replace('ARRAY<', '').rstrip('>')
        inner_ch = BQ_TO_CLICKHOUSE_TYPES.get(inner.strip(), 'String')
        return f'Array({inner_ch})'

    # Handle STRUCT/RECORD
    if base_type in ('STRUCT', 'RECORD'):
        return 'String'  # Flatten to JSON string

    ch_type = BQ_TO_CLICKHOUSE_TYPES.get(base_type, 'String')

    if is_nullable and base_type not in ('ARRAY', 'STRUCT', 'RECORD'):
        return f'Nullable({ch_type})'

    return ch_type


def generate_create_table_ddl(
    table_name: str,
    columns: List[Dict],
    database: str = 'default',
    engine: str = 'MergeTree',
    order_by: str = 'tuple()',
    partition_by: Optional[str] = None,
) -> str:
    """Generate ClickHouse CREATE TABLE DDL from BigQuery column metadata."""
    col_defs = []
    for col in columns:
        col_name = col.get('column_name', col.get('name', 'unknown'))
        data_type = col.get('data_type', 'STRING')
        is_nullable = col.get('is_nullable', True)
        ch_type = map_bq_type_to_clickhouse(data_type, is_nullable)
        # Escape column names with backticks
        col_defs.append(f'    `{col_name}` {ch_type}')

    columns_sql = ',\n'.join(col_defs)
    partition_clause = f'\nPARTITION BY {partition_by}' if partition_by else ''

    ddl = f"""CREATE TABLE IF NOT EXISTS `{database}`.`{table_name}`
(
{columns_sql}
)
ENGINE = {engine}
ORDER BY {order_by}{partition_clause}
SETTINGS allow_nullable_key = 1"""

    return ddl


def generate_import_sql(
    table_name: str,
    columns: List[Dict],
    gcs_bucket: str,
    gcs_path_prefix: str,
    hmac_access_key: str,
    hmac_secret_key: str,
    database: str = 'default',
    export_format: str = 'PARQUET',
) -> str:
    """Generate ClickHouse INSERT INTO ... SELECT FROM s3() statement."""
    col_names = []
    col_selects = []
    for col in columns:
        col_name = col.get('column_name', col.get('name', 'unknown'))
        col_names.append(f'`{col_name}`')
        # Use ifNull for nullable columns to provide defaults
        data_type = col.get('data_type', 'STRING').upper()
        if data_type in ('INT64', 'INTEGER', 'FLOAT64', 'NUMERIC', 'BIGNUMERIC'):
            col_selects.append(f'ifNull(`{col_name}`, 0)')
        elif data_type in ('BOOL', 'BOOLEAN'):
            col_selects.append(f'ifNull(`{col_name}`, 0)')
        elif data_type in ('DATE', 'DATETIME', 'TIMESTAMP'):
            col_selects.append(f'`{col_name}`')
        else:
            col_selects.append(f"ifNull(`{col_name}`, '')")

    # Determine file extension and ClickHouse format name based on export format
    format_map = {
        'PARQUET': ('parquet', 'Parquet'),
        'AVRO': ('avro', 'Avro'),
        'CSV': ('csv', 'CSV'),
        'JSON': ('json', 'JSONEachRow'),
    }
    file_ext, ch_format = format_map.get(export_format.upper(), ('parquet', 'Parquet'))

    # BigQuery exports files as 000000000000.parquet, 000000000001.parquet, etc.
    gcs_url = f'https://storage.googleapis.com/{gcs_bucket}/{gcs_path_prefix}/{table_name}/*.{file_ext}'

    sql = f"""INSERT INTO `{database}`.`{table_name}`
SELECT
    {', '.join(col_selects)}
FROM s3(
    '{gcs_url}',
    '{hmac_access_key}',
    '{hmac_secret_key}',
    '{ch_format}'
)"""

    return sql


def generate_export_sql(
    project_id: str,
    dataset_name: str,
    table_name: str,
    gcs_bucket: str,
    gcs_path_prefix: str,
    export_format: str = 'PARQUET',
    compression: str = 'SNAPPY',
) -> str:
    """Generate BigQuery EXPORT DATA SQL statement."""
    # Map format to file extension
    ext_map = {'PARQUET': 'parquet', 'AVRO': 'avro', 'CSV': 'csv', 'JSON': 'json'}
    file_ext = ext_map.get(export_format.upper(), 'parquet')
    gcs_uri = f'gs://{gcs_bucket}/{gcs_path_prefix}/{table_name}/*.{file_ext}'

    sql = f"""EXPORT DATA OPTIONS (
    uri = '{gcs_uri}',
    format = '{export_format}',
    overwrite = true,
    compression = '{compression}'
) AS (
    SELECT * FROM `{project_id}.{dataset_name}.{table_name}`
)"""

    return sql


class ClickHouseMigrationService:
    """
    Orchestrates the BigQuery → GCS → ClickHouse migration pipeline.
    """

    def __init__(self, bq_client, ch_client, config: Dict[str, Any]):
        """
        Args:
            bq_client: google.cloud.bigquery.Client instance
            ch_client: clickhouse_connect client instance
            config: Migration configuration dict with keys:
                - gcs_bucket: GCS bucket name
                - gcs_path_prefix: Path prefix in bucket
                - gcs_hmac_access_key: HMAC access key
                - gcs_hmac_secret_key: HMAC secret key
                - clickhouse_database: Target database
                - clickhouse_engine: Table engine (MergeTree, etc.)
                - clickhouse_order_by: ORDER BY strategy
                - export_format: PARQUET, AVRO, etc.
                - compression: SNAPPY, GZIP, etc.
        """
        self.bq_client = bq_client
        self.ch_client = ch_client
        self.config = config
        self.logs: List[Dict] = []

    def _log(self, table_name: str, stage: str, status: str, message: str,
             rows: int = 0, duration: float = 0, error_detail: str = None):
        """Add a log entry."""
        entry = {
            'table_name': table_name,
            'stage': stage,
            'status': status,
            'message': message,
            'rows_processed': rows,
            'duration_seconds': round(duration, 2),
            'error_detail': error_detail,
            'timestamp': datetime.utcnow().isoformat(),
        }
        self.logs.append(entry)
        if status == 'failed':
            logger.error(f"[{table_name}][{stage}] {message}: {error_detail}")
        else:
            logger.info(f"[{table_name}][{stage}] {message}")

    def create_table(self, table_name: str, columns: List[Dict],
                     order_by: str = 'tuple()') -> bool:
        """Stage 1: Create table in ClickHouse."""
        start = time.time()
        try:
            ddl = generate_create_table_ddl(
                table_name=table_name,
                columns=columns,
                database=self.config.get('clickhouse_database', 'default'),
                engine=self.config.get('clickhouse_engine', 'MergeTree'),
                order_by=order_by,
            )
            self.ch_client.command(ddl)
            duration = time.time() - start
            self._log(table_name, 'ddl', 'completed',
                      f'Table created in ClickHouse', duration=duration)
            return True
        except Exception as e:
            duration = time.time() - start
            self._log(table_name, 'ddl', 'failed',
                      'Failed to create table', duration=duration,
                      error_detail=str(e))
            return False

    def export_to_gcs(self, project_id: str, dataset_name: str,
                      table_name: str) -> bool:
        """Stage 2: Export BigQuery table to GCS as Parquet."""
        start = time.time()
        try:
            export_sql = generate_export_sql(
                project_id=project_id,
                dataset_name=dataset_name,
                table_name=table_name,
                gcs_bucket=self.config['gcs_bucket'],
                gcs_path_prefix=self.config.get('gcs_path_prefix', 'migrations'),
                export_format=self.config.get('export_format', 'PARQUET'),
                compression=self.config.get('compression', 'SNAPPY'),
            )
            query_job = self.bq_client.query(export_sql)
            query_job.result()  # Wait for completion

            duration = time.time() - start
            self._log(table_name, 'export', 'completed',
                      f'Exported to GCS: gs://{self.config["gcs_bucket"]}/{self.config.get("gcs_path_prefix", "migrations")}/{table_name}/',
                      duration=duration)
            return True
        except Exception as e:
            duration = time.time() - start
            self._log(table_name, 'export', 'failed',
                      'Failed to export from BigQuery', duration=duration,
                      error_detail=str(e))
            return False

    def import_from_gcs(self, table_name: str, columns: List[Dict]) -> bool:
        """Stage 3: Import data from GCS into ClickHouse using s3()."""
        start = time.time()
        try:
            database = self.config.get('clickhouse_database', 'default')

            # Truncate table before import to prevent duplicates on re-run
            self.ch_client.command(f'TRUNCATE TABLE IF EXISTS `{database}`.`{table_name}`')

            import_sql = generate_import_sql(
                table_name=table_name,
                columns=columns,
                gcs_bucket=self.config['gcs_bucket'],
                gcs_path_prefix=self.config.get('gcs_path_prefix', 'migrations'),
                hmac_access_key=self.config['gcs_hmac_access_key'],
                hmac_secret_key=self.config['gcs_hmac_secret_key'],
                database=database,
                export_format=self.config.get('export_format', 'PARQUET'),
            )
            self.ch_client.command(import_sql)

            duration = time.time() - start
            self._log(table_name, 'import', 'completed',
                      'Data imported from GCS to ClickHouse', duration=duration)
            return True
        except Exception as e:
            duration = time.time() - start
            self._log(table_name, 'import', 'failed',
                      'Failed to import into ClickHouse', duration=duration,
                      error_detail=str(e))
            return False

    def verify_row_count(self, table_name: str, expected_rows: int) -> bool:
        """Stage 4: Verify row count matches source."""
        start = time.time()
        try:
            database = self.config.get('clickhouse_database', 'default')
            result = self.ch_client.query(
                f'SELECT count() FROM `{database}`.`{table_name}`'
            )
            actual_rows = result.result_rows[0][0] if result.result_rows else 0

            duration = time.time() - start
            match = actual_rows == expected_rows
            status = 'completed' if match else 'warning'
            msg = f'Row count: {actual_rows} (expected {expected_rows})'
            if not match:
                msg += f' — MISMATCH ({actual_rows - expected_rows:+d})'

            self._log(table_name, 'verify', status, msg,
                      rows=actual_rows, duration=duration)
            return match
        except Exception as e:
            duration = time.time() - start
            self._log(table_name, 'verify', 'failed',
                      'Failed to verify row count', duration=duration,
                      error_detail=str(e))
            return False

    def migrate_table(self, project_id: str, dataset_name: str,
                      table_name: str, columns: List[Dict],
                      expected_rows: int = 0,
                      order_by: str = 'tuple()') -> Dict:
        """Run the full migration pipeline for a single table."""
        result = {
            'table_name': table_name,
            'status': 'running',
            'stages': {'ddl': 'pending', 'export': 'pending',
                       'import': 'pending', 'verify': 'pending'},
        }

        # Stage 1: Create table
        result['stages']['ddl'] = 'running'
        if not self.create_table(table_name, columns, order_by):
            result['status'] = 'failed'
            result['stages']['ddl'] = 'failed'
            return result
        result['stages']['ddl'] = 'completed'

        # Stage 2: Export to GCS
        result['stages']['export'] = 'running'
        if not self.export_to_gcs(project_id, dataset_name, table_name):
            result['status'] = 'failed'
            result['stages']['export'] = 'failed'
            return result
        result['stages']['export'] = 'completed'

        # Stage 3: Import from GCS
        result['stages']['import'] = 'running'
        if not self.import_from_gcs(table_name, columns):
            result['status'] = 'failed'
            result['stages']['import'] = 'failed'
            return result
        result['stages']['import'] = 'completed'

        # Stage 4: Verify
        result['stages']['verify'] = 'running'
        self.verify_row_count(table_name, expected_rows)
        result['stages']['verify'] = 'completed'

        result['status'] = 'completed'
        return result

    def migrate_all(self, tables: List[Dict], project_id: str,
                    dataset_name: str) -> Dict:
        """
        Run migration for all selected tables.

        Args:
            tables: List of table dicts with keys:
                - table_name, columns (list), row_count,
                  partitioning_columns, clustering_columns
            project_id: BigQuery project ID
            dataset_name: BigQuery dataset name

        Returns:
            Migration summary with per-table results and logs.
        """
        total = len(tables)
        completed = 0
        failed = 0
        results = []

        self._log('_migration_', 'start', 'started',
                  f'Starting migration of {total} tables')

        for i, table in enumerate(tables):
            table_name = table['table_name']
            columns = table.get('columns', [])
            row_count = table.get('row_count', 0)

            # Determine ORDER BY
            order_by = self._determine_order_by(table)

            self._log(table_name, 'start', 'started',
                      f'Starting table {i+1}/{total}')

            result = self.migrate_table(
                project_id=project_id,
                dataset_name=dataset_name,
                table_name=table_name,
                columns=columns,
                expected_rows=row_count,
                order_by=order_by,
            )
            results.append(result)

            if result['status'] == 'completed':
                completed += 1
            else:
                failed += 1

        self._log('_migration_', 'end', 'completed',
                  f'Migration finished: {completed}/{total} succeeded, {failed} failed')

        return {
            'total_tables': total,
            'completed': completed,
            'failed': failed,
            'results': results,
            'logs': self.logs,
        }

    def _determine_order_by(self, table: Dict) -> str:
        """Determine ORDER BY clause based on BQ table metadata."""
        strategy = self.config.get('clickhouse_order_by', 'auto')

        if strategy == 'tuple':
            return 'tuple()'

        if strategy == 'custom':
            # Use per-table custom ORDER BY from user input
            custom_map = self.config.get('custom_order_by_map', {})
            table_name = table.get('table_name', '')
            custom_value = custom_map.get(table_name, '').strip()
            if custom_value:
                cols = [f'`{c.strip()}`' for c in custom_value.split(',') if c.strip()]
                if cols:
                    return f'({", ".join(cols)})'
            return 'tuple()'

        if strategy == 'auto':
            # Use clustering columns first, then partitioning
            clustering = table.get('clustering_columns') or []
            partitioning = table.get('partitioning_columns') or []

            if clustering and isinstance(clustering, list) and len(clustering) > 0:
                cols = [f'`{c}`' for c in clustering if c]
                if cols:
                    return f'({", ".join(cols)})'

            if partitioning and isinstance(partitioning, list) and len(partitioning) > 0:
                cols = [f'`{c}`' for c in partitioning if c]
                if cols:
                    return f'({", ".join(cols)})'

        return 'tuple()'
