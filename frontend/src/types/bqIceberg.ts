/**
 * Types for BigQuery to Iceberg migration feature
 */

// --- Structure Report Types ---

export interface ColumnMapping {
  name: string;
  source_bq_type: string;
  iceberg_type: string;
  nullable: boolean;
  warnings: string[];
}

export interface PartitionSpec {
  column: string;
  transform: 'day' | 'hour' | 'month' | 'year' | 'identity' | 'bucket' | 'truncate';
  rationale?: string;
}

export interface SortOrderColumn {
  column: string;
  direction: 'asc' | 'desc';
  null_order?: 'nulls_first' | 'nulls_last';
}

export interface TableProperties {
  [key: string]: string;
}

export interface TableStructure {
  table_name: string;
  iceberg_table_name: string;
  columns: ColumnMapping[];
  partition_spec: PartitionSpec[];
  sort_order: SortOrderColumn[];
  properties: TableProperties;
  estimated_row_count: number;
  estimated_data_size_bytes: number;
  is_custom: boolean;
}

export interface PrerequisiteItem {
  id: string;
  label: string;
  description: string;
  category: 'iam' | 's3' | 'glue' | 'athena' | 's3_tables' | 'network';
  required: boolean;
}

export interface Warning {
  severity: 'info' | 'warning' | 'error';
  table_name?: string;
  message: string;
  recommendation?: string;
}

export interface StructureReport {
  migration_id: number;
  tables: TableStructure[];
  prerequisites: PrerequisiteItem[];
  warnings: Warning[];
  dataset_to_db_mapping: Record<string, string>;
  s3_tables_namespace?: string;
  generated_at: string;
}

// --- Custom Structure Types ---

export interface CustomColumnDef {
  name: string;
  iceberg_type: string;
  nullable: boolean;
}

export interface CustomPartitionSpec {
  column: string;
  transform: string;
}

export interface CustomSortOrder {
  column: string;
  direction: 'asc' | 'desc';
}

export interface CustomStructureDefinition {
  table_name: string;
  columns: CustomColumnDef[];
  partition_spec: CustomPartitionSpec[];
  sort_order: CustomSortOrder[];
  properties: TableProperties;
}

export interface CustomStructureValidation {
  valid: boolean;
  warnings: string[];
  errors: string[];
}

// --- Cost Analysis Types ---

export interface SetupCosts {
  s3_storage_initial: number;
  glue_api_calls: number;
  data_transfer: number;
  total: number;
}

export interface RecurringCosts {
  s3_storage_monthly: number;
  glue_catalog_monthly: number;
  athena_queries_monthly: number;
  s3_tables_monthly?: number;
  total_monthly: number;
}

export interface CostProjection {
  month_3: number;
  month_6: number;
  month_12: number;
}

export interface TCOComparison {
  bigquery_monthly: number;
  iceberg_monthly: number;
  savings_monthly: number;
  savings_percentage: number;
}

export interface CostAnalysisReport {
  migration_id: number;
  destination_type: 'iceberg_s3' | 'iceberg_s3_tables';
  data_size_bytes: number;
  table_count: number;
  setup_costs: SetupCosts;
  recurring_costs: RecurringCosts;
  projections_optimistic: CostProjection;
  projections_conservative: CostProjection;
  tco_comparison?: TCOComparison;
  growth_rate_monthly: number;
  compression_ratio_optimistic: number;
  compression_ratio_conservative: number;
  generated_at: string;
}

// --- Maintenance & Compaction Config Types ---

export type CompactionStrategy = 'binpack' | 'sort' | 'z-order';

export interface MaintenanceConfig {
  target_file_size_mb: number;
  min_snapshots_to_keep: number;
  max_snapshot_age_hours: number;
}

export interface CompactionConfig {
  strategy: CompactionStrategy;
  sort_columns: string[];
  recommended_strategy?: CompactionStrategy;
  recommended_sort_columns?: string[];
}

export interface LakeFormationPrerequisite {
  description: string;
  arn_or_permission: string;
  action_type: string;
}

// --- Override Types ---

export interface StructureOverrides {
  partition_overrides?: Record<string, PartitionSpec[]>;
  sort_order_overrides?: Record<string, SortOrderColumn[]>;
  excluded_tables?: string[];
  custom_properties?: Record<string, TableProperties>;
  dataset_to_db_mapping?: Record<string, string>;
  s3_tables_namespace?: string;
}

// --- API Response Types ---

export interface ApproveStructureRequest {
  overrides?: StructureOverrides;
  dataset_to_db_mapping?: Record<string, string>;
  s3_tables_namespace?: string;
}

export interface ApproveStructureResponse {
  message: string;
  migration_id: number;
  status: string;
}

export interface RecalculateCostRequest {
  growth_rate_monthly: number;
}

// --- Iceberg Type Options ---

export const ICEBERG_TYPES = [
  'string',
  'binary',
  'boolean',
  'int',
  'long',
  'float',
  'double',
  'decimal',
  'date',
  'time',
  'timestamp',
  'timestamptz',
  'uuid',
  'fixed',
  'struct',
  'list',
  'map',
] as const;

export const PARTITION_TRANSFORMS = [
  'identity',
  'day',
  'hour',
  'month',
  'year',
  'bucket',
  'truncate',
] as const;
