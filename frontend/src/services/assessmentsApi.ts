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
  dataset_metadata?: Record<string, any>;
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
  table_metadata?: Record<string, any>;
  partition_function?: string | null;
  partition_scheme?: string | null;
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
    source_db_type?: string;
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
  indexes: AssessmentReportIndex[];
}

export interface AssessmentReportIndex {
  id: number;
  table_id: number | null;
  schema_name: string;
  table_name: string;
  object_type: string;
  index_name: string;
  index_type: string;
  is_unique: boolean;
  is_primary_key: boolean;
  is_clustered: boolean;
  key_columns: string;
  included_columns: string | null;
  filter_definition: string | null;
  size_mb: number;
  row_count: number;
  index_metadata: Record<string, any>;
}

/**
 * Get comprehensive assessment report (full — used for PDF download)
 */
export const getAssessmentReport = async (assessmentId: number): Promise<AssessmentFullReport> => {
  return api.get(`/api/assessments/${assessmentId}/report`);
};

// ---- Lazy-load per-section endpoints ----

export interface ReportSummary {
  assessment: AssessmentFullReport['assessment'] & {
    trigger_count?: number;
    schemas_count?: number;
    security_items_count?: number;
  };
  datasets: DatasetSummary[];
  security_policies_preview?: any[];
}

export interface PaginatedTablesResponse {
  tables: AssessmentReportTable[];
  columns: AssessmentReportColumn[];
  indexes: AssessmentReportIndex[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  datasets: string[];
}

export interface PaginatedViewsResponse {
  views: AssessmentReportView[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface RoutinesResponse {
  routines: AssessmentReportRoutine[];
}

export interface SecurityResponse {
  security_policies: AssessmentReportSecurity[];
  columns: AssessmentReportColumn[];
  tables: { id: number; dataset_name: string; table_name: string }[];
}

export interface MLModelsResponse {
  ml_models: AssessmentReportMLModel[];
  spark_models: AssessmentReportRoutine[];
}

export interface UserInsightsResponse {
  query_stats: AssessmentReportQueryStat[];
}

export const getReportSummary = async (assessmentId: number): Promise<ReportSummary> => {
  return api.get(`/api/assessments/${assessmentId}/report/summary`);
};

export const getReportTables = async (assessmentId: number, page: number = 1, pageSize: number = 50, dataset?: string): Promise<PaginatedTablesResponse> => {
  let url = `/api/assessments/${assessmentId}/report/tables?page=${page}&page_size=${pageSize}`;
  if (dataset && dataset !== 'all') url += `&dataset=${encodeURIComponent(dataset)}`;
  return api.get(url);
};

export const getReportViews = async (assessmentId: number, page: number = 1, pageSize: number = 50): Promise<PaginatedViewsResponse> => {
  return api.get(`/api/assessments/${assessmentId}/report/views?page=${page}&page_size=${pageSize}`);
};

export const getReportRoutines = async (assessmentId: number): Promise<RoutinesResponse> => {
  return api.get(`/api/assessments/${assessmentId}/report/routines`);
};

export const getReportSecurity = async (assessmentId: number): Promise<SecurityResponse> => {
  return api.get(`/api/assessments/${assessmentId}/report/security`);
};

export const getReportMLModels = async (assessmentId: number): Promise<MLModelsResponse> => {
  return api.get(`/api/assessments/${assessmentId}/report/ml-models`);
};

export const getReportUserInsights = async (assessmentId: number): Promise<UserInsightsResponse> => {
  return api.get(`/api/assessments/${assessmentId}/report/user-insights`);
};

export interface AdditionalMetadata {
  agent_jobs?: any[];
  certificates?: any[];
  encryption?: { symmetric_keys?: any[]; asymmetric_keys?: any[]; tde_enabled?: boolean; tde_databases?: any[] };
  assemblies?: any[];
  policies?: any[];
  replication?: { is_published?: boolean; is_subscribed?: boolean; is_merge_published?: boolean };
  computed_columns?: any[];
  user_defined_types?: any[];
}

export const getReportAdditionalMetadata = async (assessmentId: number): Promise<AdditionalMetadata> => {
  return api.get(`/api/assessments/${assessmentId}/report/additional-metadata`);
};

/** Fetch ALL tables (no pagination) for CSV export */
export const getAllReportTables = async (assessmentId: number, dataset?: string): Promise<{ tables: AssessmentReportTable[]; total: number }> => {
  let url = `/api/assessments/${assessmentId}/report/tables?export=all`;
  if (dataset && dataset !== 'all') url += `&dataset=${encodeURIComponent(dataset)}`;
  return api.get(url);
};

/** Fetch ALL views (no pagination) for CSV export */
export const getAllReportViews = async (assessmentId: number): Promise<{ views: AssessmentReportView[]; total: number }> => {
  return api.get(`/api/assessments/${assessmentId}/report/views?export=all`);
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
    estimated_monthly_queries?: number;
    monthly_tb_scanned?: number;
    tb_scanned?: number;
    on_demand_monthly?: number;
    slot_based_monthly?: number;
    monthly_slot_hours?: number;
    rate_per_tb?: number;
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
  vcpu_total?: number;
  memory_gb_total?: number;
  sizing_basis?: {
    avg_vcpus_needed?: number;
    peak_vcpus?: number;
    avg_slots?: number;
    peak_slots?: number;
    base_memory_gib?: number;
    monthly_slot_hours?: number;
    vcpus_per_node?: number;
    slices_per_node?: number;
    nodes_for_compute?: number;
    nodes_for_storage?: number;
    peak_to_base_ratio?: number;
    sizing_driver?: string;
  };
  sizing_rationale?: string[];
  concurrency_scaling?: boolean;
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
  provisioned_ri1yr_3yr_tco?: number;
  provisioned_ri3yr_3yr_tco?: number;
  serverless_3yr_tco: number;
  best_option: string;
  savings_amount: number;
  savings_pct: number;
  provisioned_viable?: boolean;
  provisioned_note?: string | null;
}

export interface WorkloadType {
  pattern: string;
  label: string;
  description: string;
  daily_queries: number;
  daily_slot_hours: number;
}

export interface TCORecommendation {
  choice: string;
  confidence: string;
  title: string;
  reasons: string[];
  annual_savings_vs_bq: number;
  workload_pattern: WorkloadType;
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
  workload_summary?: {
    query_time_span_days: number;
    monthly_slot_hours: number;
    monthly_tb_scanned: number;
    estimated_rpu_hours_monthly: number;
    total_queries: number;
    workload_type: WorkloadType;
    avg_wall_clock_seconds?: number;
    active_hours_per_day?: number;
    estimated_base_rpu?: number;
    max_concurrent_slots?: number;
    min_concurrent_slots?: number;
    avg_concurrent_slots?: number;
    median_concurrent_slots?: number;
    estimated_peak_slots?: number;
  };
  recommendation?: TCORecommendation;
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


// ---- Compatibility Check Types ----

export interface CompatibilityCheckRequest {
  assessment_id: number;
}

export interface DataTypeMapping {
  table_name: string;
  column_name: string;
  bq_type: string;
  redshift_type: string;
  compatibility: 'full' | 'partial' | 'lossy' | 'unsupported' | 'unknown';
  notes: string;
}

export interface DataTypeAnalysis {
  mappings: DataTypeMapping[];
  stats: { full: number; partial: number; lossy: number; unsupported: number; unknown: number };
  compatibility_pct: number;
  total_columns: number;
}

export interface FeatureGap {
  category: string;
  severity: 'high' | 'medium' | 'low';
  count: number;
  description: string;
  items: string[];
  recommendation: string;
}

export interface SqlSyntaxIssue {
  pattern: string;
  severity: 'high' | 'medium' | 'low';
  fix: string;
  affected_count: number;
  affected_items: string[];
}

export interface LLMInsights {
  executive_summary: string;
  effort_level: string;
  migration_approach: string;
  estimated_timeline?: string;
  team_requirements?: { role: string; reason: string }[];
  testing_strategy?: string[];
  rollback_plan?: string;
  cost_considerations?: string[];
  // Legacy fields (backward compat)
  critical_risks?: { risk: string; impact: string; mitigation: string }[];
  effort_justification?: string;
  additional_recommendations?: string[];
}

export interface CompatibilityReport {
  assessment_id: number;
  assessment_name: string;
  overall_score: number;
  score_breakdown: { overall: number; data_types: number; feature_gaps: number; sql_syntax: number };
  summary: {
    total_tables: number;
    total_columns: number;
    total_views: number;
    total_routines: number;
    total_ml_models: number;
    total_security_policies: number;
    total_sharded_tables: number;
  };
  data_type_analysis: DataTypeAnalysis;
  feature_gaps: FeatureGap[];
  sql_syntax_issues: SqlSyntaxIssue[];
  llm_insights?: LLMInsights | null;
}

/**
 * Run compatibility check on a completed assessment
 */
export const runCompatibilityCheck = async (assessmentId: number): Promise<CompatibilityReport> => {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 120000); // 2 min timeout
  try {
    return await api.post<CompatibilityReport>('/api/compatibility/check', { assessment_id: assessmentId }, { signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
};


/**
 * Save compatibility check result
 */
export const saveCompatibilityResult = async (assessmentId: number, report: CompatibilityReport): Promise<{ success: boolean }> => {
  return api.post('/api/compatibility/save', { assessment_id: assessmentId, report });
};

/**
 * Get saved compatibility check result
 */
export const getSavedCompatibility = async (assessmentId: number): Promise<{ found: boolean; report: CompatibilityReport | null }> => {
  return api.get(`/api/compatibility/saved/${assessmentId}`);
};


// ---- Schema Analysis Types ----

export interface SchemaColumn {
  name: string;
  data_type: string;
  is_nullable: boolean;
  ordinal_position: number;
  is_partitioning: boolean;
  clustering_position: number | null;
  max_length: number | null;
  policy_tags: string[];
}

export interface SchemaTable {
  id: number;
  dataset: string;
  name: string;
  full_name: string;
  type: string;
  row_count: number;
  size_mb: number;
  created_at: string | null;
  partitioning_columns: string[];
  clustering_columns: string[];
  has_column_security: boolean;
  has_row_security: boolean;
  is_sharded: boolean;
  shard_group: string | null;
  column_count: number;
  columns: SchemaColumn[];
}

export interface SchemaDataset {
  name: string;
  table_count: number;
  total_size_mb: number;
  location: string | null;
  created_at: string | null;
  tables: string[];
}

export interface SchemaView {
  name: string;
  dataset: string | null;
  type: string;
  definition: string | null;
  is_materialized: boolean;
}

export interface SchemaRoutine {
  name: string;
  type: string;
  language: string;
  definition: string | null;
}

export interface SchemaTypeDistribution {
  type: string;
  count: number;
}

export interface SchemaAnalysisData {
  assessment_id: number;
  assessment_name: string;
  status: string;
  summary: {
    datasets: number;
    tables: number;
    columns: number;
    views: number;
    routines: number;
    total_rows: number;
    total_size_mb: number;
    partitioned_tables: number;
    clustered_tables: number;
    secured_tables: number;
    sharded_tables: number;
    nullable_columns: number;
    non_nullable_columns: number;
  };
  datasets: SchemaDataset[];
  tables: SchemaTable[];
  views: SchemaView[];
  routines: SchemaRoutine[];
  type_distribution: SchemaTypeDistribution[];
}

/**
 * Get schema analysis for a completed assessment
 */
export const getSchemaAnalysis = async (assessmentId: number): Promise<SchemaAnalysisData> => {
  return api.get<SchemaAnalysisData>(`/api/schema/analysis/${assessmentId}`);
};
