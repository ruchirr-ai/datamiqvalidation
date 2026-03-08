/**
 * Assessments API Service
 * Handles all API calls related to assessments
 */

import { api } from './api';

export interface Assessment {
  id: number;
  name: string;
  source_connection_id: number;
  target_connection_id: number;
  project_id: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
  total_datasets: number;
  total_tables: number;
  total_views: number;
  total_routines: number;
  total_ml_models: number;
  total_size_mb: number;
  created_by: string | null;
  workspace_id: number;
}

export interface AssessmentListResponse {
  assessments: Assessment[];
  total: number;
}

export interface CreateAssessmentRequest {
  name: string;
  source_connection_id: number;
  target_connection_id: number;
}

export interface UpdateAssessmentRequest {
  name?: string;
  source_connection_id?: number;
  target_connection_id?: number;
}

export interface DatasetSummary {
  dataset_name: string;
  creation_time: string | null;
  location: string | null;
  table_count: number;
  total_size_mb: number;
}

export interface AssessmentDetailResponse {
  assessment: Assessment;
  datasets: DatasetSummary[];
}

/**
 * List all assessments
 */
export const listAssessments = async (): Promise<AssessmentListResponse> => {
  return api.get<AssessmentListResponse>('/api/assessments/');
};

/**
 * Create a new assessment
 */
export const createAssessment = async (
  data: CreateAssessmentRequest
): Promise<Assessment> => {
  return api.post<Assessment>('/api/assessments/', data);
};

/**
 * Get assessment details
 */
export const getAssessment = async (
  assessmentId: number
): Promise<AssessmentDetailResponse> => {
  return api.get<AssessmentDetailResponse>(`/api/assessments/${assessmentId}`);
};

/**
 * Delete an assessment
 */
export const deleteAssessment = async (assessmentId: number): Promise<void> => {
  return api.delete(`/api/assessments/${assessmentId}`);
};

/**
 * Update an assessment
 */
export const updateAssessment = async (
  assessmentId: number,
  data: UpdateAssessmentRequest
): Promise<Assessment> => {
  return api.put<Assessment>(`/api/assessments/${assessmentId}`, data);
};

/**
 * Run/trigger an assessment
 */
export const runAssessment = async (assessmentId: number): Promise<{ message: string; assessment_id: number }> => {
  return api.post(`/api/assessments/${assessmentId}/run`);
};

/**
 * Get assessment logs
 */
export const getAssessmentLogs = async (assessmentId: number): Promise<{ logs: any[]; assessment_id: number }> => {
  return api.get(`/api/assessments/${assessmentId}/logs`);
};

// Full Report Types
export interface AssessmentReportTable {
  id: number;
  project_id: string;
  dataset_name: string;
  table_name: string;
  table_type: string;
  creation_time: string | null;
  row_count: number;
  size_mb: number;
  partitioning_columns: string[];
  clustering_columns: string[];
  has_column_security: boolean;
  has_row_security: boolean;
  is_sharded: boolean;
  update_frequency: string;
}

export interface AssessmentReportColumn {
  table_id: number;
  column_name: string;
  data_type: string;
  is_nullable: boolean;
  ordinal_position: number;
  is_partitioning_column: boolean;
  clustering_ordinal_position: number | null;
  policy_tags: string[];
  max_length: number | null;
}

export interface AssessmentReportView {
  view_name: string;
  view_type: string;
  view_definition: string;
  creation_time: string | null;
  dependencies: string[];
}

export interface AssessmentReportRoutine {
  routine_name: string;
  routine_type: string;
  return_type: string | null;
  definition: string;
  external_language: string | null;
  creation_time: string | null;
  call_frequency: number;
}

export interface AssessmentReportMLModel {
  model_name: string;
  model_type: string;
  dataset_name: string;
  creation_time: string | null;
  last_modified_time: string | null;
}

export interface AssessmentReportQueryStat {
  job_id: string;
  execution_time: string | null;
  query_text: string | null;
  bytes_scanned: number;
  slot_milliseconds: number;
  cache_hit: boolean;
  referenced_tables: string[];
  user_email: string;
}

export interface AssessmentReportSecurity {
  security_type: string;
  table_name: string;
  policy_name: string;
  filter_predicate: string;
  grantees: string[];
}

export interface AssessmentReportShardedTable {
  shard_group: string;
  table_prefix: string;
  shard_count: number;
  total_size_mb: number;
  date_range_start: string | null;
  date_range_end: string | null;
  shard_tables: string[];
}

export interface AssessmentFullReport {
  assessment: {
    id: number;
    name: string;
    project_id: string;
    status: string;
    started_at: string | null;
    completed_at: string | null;
    total_datasets: number;
    total_tables: number;
    total_views: number;
    total_routines: number;
    total_ml_models: number;
    total_size_mb: number;
  };
  datasets: DatasetSummary[];
  tables: AssessmentReportTable[];
  columns: AssessmentReportColumn[];
  views: AssessmentReportView[];
  routines: AssessmentReportRoutine[];
  ml_models: AssessmentReportMLModel[];
  query_stats: AssessmentReportQueryStat[];
  security_policies: AssessmentReportSecurity[];
  sharded_tables: AssessmentReportShardedTable[];
}

/**
 * Get comprehensive assessment report
 */
export const getAssessmentReport = async (assessmentId: number): Promise<AssessmentFullReport> => {
  return api.get(`/api/assessments/${assessmentId}/report`);
};


// ---- Recommendations Types ----

export interface QueryClassification {
  total_queries: number;
  adhoc_count: number;
  adhoc_pct: number;
  bi_count: number;
  bi_pct: number;
}

export interface ProvisionedConfig {
  node_type: string;
  num_nodes: number;
  storage_type: string;
  vcpu_total: number;
  memory_gb_total: number;
  use_case: string;
}

export interface ServerlessConfig {
  base_rpu: number;
  max_rpu: number;
  est_rpu_hours_monthly: number;
  est_utilization_pct: number;
}

export interface ConfigRecommendation {
  recommended: 'provisioned' | 'serverless';
  reasons: string[];
  provisioned: ProvisionedConfig;
  serverless: ServerlessConfig;
  key_stats: {
    total_data_volume_gb: number;
    total_rows: number;
    total_tables: number;
    total_queries_analyzed: number;
  };
}

export interface DistSortKeyRecommendation {
  table_name: string;
  distkey: string;
  sortkey: string;
  reasoning: string[];
}

export interface ArchitectureStrategy {
  title: string;
  points: string[];
}

export interface RecommendationsData {
  query_classification: QueryClassification;
  config_recommendation: ConfigRecommendation;
  dist_sort_keys: DistSortKeyRecommendation[];
  architecture: {
    strategies: ArchitectureStrategy[];
  };
}

// ---- TCO Types ----

export interface TCOCostBreakdown {
  monthly: number;
  annual: number;
}

export interface BQCosts extends TCOCostBreakdown {
  storage: {
    data_volume_gb: number;
    rate_per_gb_month: number;
    storage_type: string;
    monthly: number;
    annual: number;
  };
  query: {
    queries_analyzed: number;
    tb_scanned: number;
    rate_per_tb: number;
    pricing_model: string;
    monthly: number;
    annual: number;
  };
}

export interface ProvisionedCosts extends TCOCostBreakdown {
  node_type: string;
  num_nodes: number;
  hourly_per_node: number;
  total_hourly: number;
  compute_monthly: number;
  storage_monthly: number;
  ri_1yr_monthly: number;
  ri_1yr_annual: number;
  ri_3yr_monthly: number;
  ri_3yr_annual: number;
}

export interface ServerlessCosts extends TCOCostBreakdown {
  base_rpu: number;
  max_rpu: number;
  est_rpu_hours_monthly: number;
  est_utilization_pct: number;
  rpu_hour_rate: number;
  compute_monthly: number;
  storage_monthly: number;
}

export interface TCOComparison {
  bq_3yr_tco: number;
  provisioned_3yr_tco: number;
  serverless_3yr_tco: number;
  best_option: string;
  savings_amount: number;
  savings_pct: number;
}

export interface TCOData {
  aws_region: string;
  region_label: string;
  bigquery_costs: BQCosts;
  provisioned_costs: ProvisionedCosts;
  serverless_costs: ServerlessCosts;
  migration_costs: {
    data_volume_gb: number;
    rate_per_gb: number;
    total: number;
  };
  comparison: TCOComparison;
  cost_notes: string[];
}

export interface AWSRegion {
  value: string;
  label: string;
}

/**
 * Get recommendations for an assessment
 */
export const getAssessmentRecommendations = async (assessmentId: number): Promise<RecommendationsData> => {
  return api.get(`/api/assessments/${assessmentId}/recommendations`);
};

/**
 * Get TCO analysis for an assessment
 */
export const getAssessmentTCO = async (assessmentId: number, region: string = 'us-east-1'): Promise<TCOData> => {
  return api.get(`/api/assessments/${assessmentId}/tco?region=${region}`);
};

/**
 * Get available AWS regions for TCO analysis
 */
export const getTCORegions = async (): Promise<{ regions: AWSRegion[] }> => {
  return api.get('/api/assessments/tco/regions');
};
