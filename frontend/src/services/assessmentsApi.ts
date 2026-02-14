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
