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
  ddl_check: boolean;
  row_count_check: boolean;
  data_match_check: boolean;
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
  statusFilter?: string
): Promise<PaginatedValidationRunsResponse> => {
  const params = new URLSearchParams();
  params.set('page', String(page));
  params.set('page_size', String(pageSize));
  if (migrationId) params.set('migration_id', String(migrationId));
  if (statusFilter) params.set('status_filter', statusFilter);
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
