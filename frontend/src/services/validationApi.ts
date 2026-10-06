/**
 * Validation API Service
 * Handles all API calls related to post-migration data validation
 */

import { api } from './api';

// ---------------------------------------------------------------------------
// Request types
// ---------------------------------------------------------------------------

export interface TableValidationConfig {
  table_name: string;
  // Existing checks
  ddl_check: boolean;
  row_count_check: boolean;
  data_match_check: boolean;
  // New checks
  null_check?: boolean;
  null_column?: string;
  duplicate_check?: boolean;
  duplicate_match_key?: string;
  sum_check?: boolean;
  sum_column?: string;
  average_check?: boolean;
  average_column?: string;
  specific_row_check?: boolean;
  specific_row_match_key?: string;
  specific_row_start?: number;
  specific_row_end?: number;
  // Sampling
  sampling_mode?: 'all' | 'random';
  sample_limit?: number;
  batch_size?: number;
}

export interface CreateValidationRunRequest {
  migration_id: number;
  source_connection_id?: number;
  target_connection_id?: number;
  tables?: string[];
  table_configs?: TableValidationConfig[];
  bedrock_model?: string;
  batch_size?: number;
  type_mapping_overrides?: Record<string, string>;
  run_name?: string;
}

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

export interface ValidationRun {
  id: number;
  workspace_id: number;
  migration_id: number;
  source_connection_id: number;
  target_connection_id: number;
  status: string;
  progress_percentage: number;
  tables_total: number;
  tables_passed: number;
  tables_failed: number;
  tables_error: number;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  run_name: string | null;
  table_results?: ValidationTableResult[] | null;
}

export interface PaginatedValidationRunsResponse {
  runs: ValidationRun[];
  total: number;
  page: number;
  page_size: number;
}

export interface ValidationTableResult {
  id: number;
  run_id: number;
  table_name: string;
  dataset_name: string | null;
  ddl_status: string | null;
  row_count_status: string | null;
  data_match_status: string | null;
  // New check statuses
  null_status?: string | null;
  duplicate_status?: string | null;
  sum_status?: string | null;
  average_status?: string | null;
  specific_row_status?: string | null;
  null_result?: Record<string, unknown> | null;
  status: string;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
}

export interface ValidationTableDetail extends ValidationTableResult {
  ddl_comparison_result: Record<string, unknown> | null;
  row_count_result: Record<string, unknown> | null;
  data_match_result: Record<string, unknown> | null;
  // New check detailed results
  duplicate_result?: Record<string, unknown> | null;
  sum_result?: Record<string, unknown> | null;
  average_result?: Record<string, unknown> | null;
  specific_row_result?: Record<string, unknown> | null;
  ai_analysis: Record<string, unknown> | null;
}

export interface ValidationReport {
  run_id: number;
  migration_id: number;
  source_connection_name: string;
  target_connection_name: string;
  overall_status: string;
  total_tables: number;
  tables_passed: number;
  tables_failed: number;
  tables_error: number;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  run_name: string | null;
  tables: ValidationTableDetail[];
}

// ---------------------------------------------------------------------------
// API methods
// ---------------------------------------------------------------------------

/**
 * Create and start a validation run
 */
export const createValidationRun = async (
  data: CreateValidationRunRequest
): Promise<ValidationRun> => {
  return api.post<ValidationRun>('/api/validations/', data);
};

/**
 * List validation runs with pagination and optional filters
 */
export const listValidationRuns = async (
  page: number = 1,
  pageSize: number = 20,
  migrationId?: number,
  statusFilter?: string,
  includeTableResults?: boolean
): Promise<PaginatedValidationRunsResponse> => {
  const params = new URLSearchParams();
  params.set('page', String(page));
  params.set('page_size', String(pageSize));
  if (migrationId) params.set('migration_id', String(migrationId));
  if (statusFilter) params.set('status_filter', statusFilter);
  if (includeTableResults) params.set('include_table_results', 'true');
  return api.get<PaginatedValidationRunsResponse>(`/api/validations/?${params.toString()}`);
};

/**
 * Get a single validation run by ID
 */
export const getValidationRun = async (runId: number): Promise<ValidationRun> => {
  return api.get<ValidationRun>(`/api/validations/${runId}`);
};

/**
 * Get table results for a validation run
 */
export const getValidationTableResults = async (
  runId: number
): Promise<ValidationTableResult[]> => {
  return api.get<ValidationTableResult[]>(`/api/validations/${runId}/tables`);
};

/**
 * Get detailed table result with JSONB fields
 */
export const getValidationTableDetail = async (
  runId: number,
  tableName: string
): Promise<ValidationTableDetail> => {
  return api.get<ValidationTableDetail>(
    `/api/validations/${runId}/tables/${encodeURIComponent(tableName)}`
  );
};

/**
 * Get the full validation report for a run
 */
export const getValidationReport = async (
  runId: number
): Promise<ValidationReport> => {
  return api.get<ValidationReport>(`/api/validations/${runId}/report`);
};

/**
 * Delete a validation run and all associated table results
 */
export const deleteValidationRun = async (
  runId: number
): Promise<void> => {
  return api.delete<void>(`/api/validations/${runId}`);
};

// ---------------------------------------------------------------------------
// Migration info for form auto-fill
// ---------------------------------------------------------------------------

export interface MigrationInfo {
  migration_id: number;
  migration_name: string;
  source_connection_id: number | null;
  target_connection_id: number | null;
  source_connection_name: string | null;
  target_connection_name: string | null;
  tables: string[];
  table_row_counts: Record<string, number | null> | null;
}

/**
 * Get migration info for auto-filling the validation form
 */
export const getMigrationInfo = async (
  migrationId: number
): Promise<MigrationInfo> => {
  return api.get<MigrationInfo>(`/api/validations/migration/${migrationId}/info`);
};

// ---------------------------------------------------------------------------
// Bedrock models for validation
// ---------------------------------------------------------------------------

export interface BedrockModel {
  model_id: string;
  model_name: string;
  provider: string;
}

/**
 * List available Bedrock models for AI analysis
 */
export const listValidationBedrockModels = async (
  region: string = 'us-east-1'
): Promise<BedrockModel[]> => {
  return api.get<BedrockModel[]>(`/api/validations/bedrock-models?region=${encodeURIComponent(region)}`);
};

// ---------------------------------------------------------------------------
// Migration table columns (for column-based validation checks)
// ---------------------------------------------------------------------------

export interface MigrationColumn {
  column_name: string;
  data_type: string;
  is_nullable: boolean;
  ordinal_position: number;
}

export interface MigrationTableColumns {
  migration_id: number;
  table_name: string;
  source_columns: MigrationColumn[];
  target_columns: MigrationColumn[];
}

/**
 * Get source and target columns for a migration table.
 * Used to populate column pickers for NULL/SUM/AVERAGE/duplicate/specific-row checks.
 */
export const getMigrationTableColumns = async (
  migrationId: number,
  tableName: string
): Promise<MigrationTableColumns> => {
  return api.get<MigrationTableColumns>(
    `/api/validations/migration/${migrationId}/tables/${encodeURIComponent(tableName)}/columns`
  );
};

// ---------------------------------------------------------------------------
// Direct validation test (connection-to-connection, no migration)
// ---------------------------------------------------------------------------

export interface DirectValidationRequest {
  source_connection_id: number;
  target_connection_id: number;
  source_schema: string;
  target_schema: string;
  table_name: string;
  row_count?: boolean;
  ddl_check?: boolean;
  null_check?: boolean;
  null_column?: string;
  duplicate_check?: boolean;
  duplicate_match_key?: string;
  sum_check?: boolean;
  sum_column?: string;
  average_check?: boolean;
  average_column?: string;
  specific_row_check?: boolean;
  specific_row_match_key?: string;
  specific_row_start?: number;
  specific_row_end?: number;
}

export interface DirectValidationCheckResult {
  status: string;
  source_value?: number | null;
  target_value?: number | null;
  difference?: number | null;
  error_message?: string | null;
}

export interface DirectValidationResponse {
  overall_status: string;
  source_engine: string;
  target_engine: string;
  source_connection: string;
  target_connection: string;
  table_name: string;
  checks: Record<string, DirectValidationCheckResult>;
}

/**
 * Run a direct validation test between two connections (no migration required).
 */
export const runDirectValidationTest = async (
  data: DirectValidationRequest
): Promise<DirectValidationResponse> => {
  return api.post<DirectValidationResponse>('/api/validations/direct-test', data);
};

// ---------------------------------------------------------------------------
// Connection table/column discovery (for the Quick Test picker)
// ---------------------------------------------------------------------------

export interface DiscoveredTable {
  schema: string;
  table: string;
}

export interface ConnectionTablesResponse {
  connection_id: number;
  connection_name: string;
  engine: string;
  tables: DiscoveredTable[];
}

/**
 * List all user tables (schema + table) for a connection.
 */
export const getConnectionTables = async (
  connectionId: number
): Promise<ConnectionTablesResponse> => {
  return api.get<ConnectionTablesResponse>(
    `/api/validations/connections/${connectionId}/tables`
  );
};

export interface DiscoveredColumn {
  column_name: string;
  data_type: string;
}

export interface ConnectionColumnsResponse {
  connection_id: number;
  engine: string;
  schema: string;
  table: string;
  columns: DiscoveredColumn[];
}

/**
 * List columns for a table on a connection (for check column pickers).
 */
export const getConnectionColumns = async (
  connectionId: number,
  schema: string,
  table: string
): Promise<ConnectionColumnsResponse> => {
  const params = new URLSearchParams({ schema, table });
  return api.get<ConnectionColumnsResponse>(
    `/api/validations/connections/${connectionId}/columns?${params.toString()}`
  );
};
