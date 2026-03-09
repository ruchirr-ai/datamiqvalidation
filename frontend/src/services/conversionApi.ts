/**
 * Conversion API Service
 * Handles all API calls related to code conversion (standalone and batch)
 */

import { api } from './api';

// ---------------------------------------------------------------------------
// Request types
// ---------------------------------------------------------------------------

export interface StandaloneConversionRequest {
  source_code: string;
  source_dialect: string;
  target_dialect: string;
  asset_type: string;
  asset_name?: string;
  aws_region: string;
  bedrock_model: string;
  prompt_template_path: string;
  max_retries?: number;
  use_sqlglot?: boolean;
  additional_context?: string;
}

export interface AssetSelection {
  asset_type: string;
  asset_name: string;
  source_code: string;
}

export interface BatchConversionRequest {
  migration_project_id: number;
  source_connection_id: number;
  target_connection_id: number;
  batch_name?: string;
  assets: AssetSelection[];
  source_dialect: string;
  target_dialect: string;
  aws_region: string;
  bedrock_model: string;
  prompt_template_path: string;
  max_retries?: number;
  use_sqlglot?: boolean;
}

export interface S3ExportRequest {
  s3_path: string;
  region: string;
}

export interface DeployRequest {
  target_connection_id: number;
}

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

export interface ConversionJob {
  id: number;
  workspace_id: number;
  batch_id: number | null;
  source_code: string;
  target_code: string | null;
  source_dialect: string;
  target_dialect: string;
  asset_type: string;
  asset_name: string | null;
  bedrock_model: string;
  aws_region: string;
  status: string;
  error_message: string | null;
  use_sqlglot: boolean;
  sqlglot_success: boolean | null;
  retry_count: number;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface PaginatedJobsResponse {
  jobs: ConversionJob[];
  total: number;
  page: number;
  page_size: number;
}

export interface ConversionBatch {
  id: number;
  workspace_id: number;
  batch_name: string | null;
  migration_project_id: number | null;
  source_connection_id: number;
  target_connection_id: number;
  status: string;
  total_assets: number;
  completed_assets: number;
  failed_assets: number;
  bedrock_model: string;
  aws_region: string;
  use_sqlglot: boolean;
  max_retries: number;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface BedrockModel {
  model_id: string;
  model_name: string;
  provider: string | null;
}

export interface ConversionLog {
  id: number;
  job_id: number;
  timestamp: string;
  log_level: string;
  step_name: string;
  message: string;
  duration_ms: number | null;
}

export interface DeployResult {
  success: boolean;
  deployed_assets: string[];
  failed_asset: string | null;
  error_message: string | null;
}

// ---------------------------------------------------------------------------
// Standalone conversion
// ---------------------------------------------------------------------------

/**
 * Create a standalone (single-snippet) code conversion
 */
export const createStandaloneConversion = async (
  data: StandaloneConversionRequest
): Promise<ConversionJob> => {
  return api.post<ConversionJob>('/api/conversions/standalone', data);
};

// ---------------------------------------------------------------------------
// Job listing / retrieval / deletion
// ---------------------------------------------------------------------------

/**
 * List conversion jobs with pagination and optional filters
 */
export const listJobs = async (
  page: number = 1,
  pageSize: number = 20,
  statusFilter?: string,
  assetType?: string,
  sourceDialect?: string,
  standaloneOnly?: boolean
): Promise<PaginatedJobsResponse> => {
  const params = new URLSearchParams();
  params.set('page', String(page));
  params.set('page_size', String(pageSize));
  if (statusFilter) params.set('status_filter', statusFilter);
  if (assetType) params.set('asset_type', assetType);
  if (sourceDialect) params.set('source_dialect', sourceDialect);
  if (standaloneOnly) params.set('standalone_only', 'true');
  return api.get<PaginatedJobsResponse>(`/api/conversions/jobs?${params.toString()}`);
};

/**
 * Get a single conversion job by ID
 */
export const getJob = async (jobId: number): Promise<ConversionJob> => {
  return api.get<ConversionJob>(`/api/conversions/jobs/${jobId}`);
};

/**
 * Delete a conversion job
 */
export const deleteJob = async (jobId: number): Promise<{ message: string }> => {
  return api.delete<{ message: string }>(`/api/conversions/jobs/${jobId}`);
};

/**
 * Retrieve conversion logs for a specific job
 */
export const getJobLogs = async (jobId: number): Promise<ConversionLog[]> => {
  return api.get<ConversionLog[]>(`/api/conversions/jobs/${jobId}/logs`);
};

/**
 * Bulk delete multiple conversion jobs by IDs
 */
export const bulkDeleteJobs = async (jobIds: number[]): Promise<{ message: string }> => {
  return api.delete<{ message: string }>('/api/conversions/jobs/bulk', {
    body: JSON.stringify({ job_ids: jobIds }),
  });
};

// ---------------------------------------------------------------------------
// Batch conversion
// ---------------------------------------------------------------------------

/**
 * Create a batch conversion for multiple assets
 */
export const createBatchConversion = async (
  data: BatchConversionRequest
): Promise<ConversionBatch> => {
  return api.post<ConversionBatch>('/api/conversions/batch', data);
};

/**
 * Get batch conversion status and progress
 */
export const getBatchStatus = async (batchId: number): Promise<ConversionBatch> => {
  return api.get<ConversionBatch>(`/api/conversions/batch/${batchId}`);
};

/**
 * List all conversion jobs within a batch
 */
export const listBatchJobs = async (batchId: number): Promise<ConversionJob[]> => {
  return api.get<ConversionJob[]>(`/api/conversions/batch/${batchId}/jobs`);
};

/**
 * List all conversion batches for the current workspace with pagination
 */
export const listBatches = async (
  page: number,
  pageSize: number
): Promise<{ batches: ConversionBatch[]; total: number }> => {
  const params = new URLSearchParams();
  params.set('page', String(page));
  params.set('page_size', String(pageSize));
  return api.get<{ batches: ConversionBatch[]; total: number }>(
    `/api/conversions/batches?${params.toString()}`
  );
};

/**
 * Delete a conversion batch and its associated jobs
 */
export const deleteBatch = async (batchId: number): Promise<{ message: string }> => {
  return api.delete<{ message: string }>(`/api/conversions/batches/${batchId}`);
};

/**
 * Export batch conversion results as a .sql file download
 */
export const exportBatchSql = async (batchId: number): Promise<void> => {
  const token = localStorage.getItem('auth_token');

  const response = await fetch(`/api/conversions/batch/${batchId}/export/sql`, {
    method: 'POST',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw {
      message: response.statusText,
      status: response.status,
      detail: errorData.detail || errorData.error || errorData.message,
    };
  }

  const disposition = response.headers.get('Content-Disposition');
  const filenameMatch = disposition?.match(/filename="?([^"]+)"?/);
  const filename = filenameMatch ? filenameMatch[1] : `batch_${batchId}_converted.sql`;

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

/**
 * Export batch conversion results to S3
 */
export const exportBatchToS3 = async (
  batchId: number,
  data: S3ExportRequest
): Promise<{ message: string }> => {
  return api.post<{ message: string }>(`/api/conversions/batch/${batchId}/export/s3`, data);
};

/**
 * Deploy converted assets to the target database
 */
export const deployBatch = async (
  batchId: number,
  data: DeployRequest
): Promise<DeployResult> => {
  return api.post<DeployResult>(`/api/conversions/batch/${batchId}/deploy`, data);
};

// ---------------------------------------------------------------------------
// Bedrock models
// ---------------------------------------------------------------------------

/**
 * List available Bedrock models for a given AWS region
 */
export const listBedrockModels = async (region: string): Promise<BedrockModel[]> => {
  return api.get<BedrockModel[]>(`/api/conversions/models?region=${encodeURIComponent(region)}`);
};

// ---------------------------------------------------------------------------
// Prompt templates
// ---------------------------------------------------------------------------

export interface PromptTemplate {
  path: string;
  name: string;
  description: string;
  source_dialect: string;
  target_dialect: string;
}

/**
 * List available local prompt templates
 */
export const listPromptTemplates = async (): Promise<PromptTemplate[]> => {
  return api.get<PromptTemplate[]>('/api/conversions/templates');
};


// ---------------------------------------------------------------------------
// Assessment assets (for batch converter)
// ---------------------------------------------------------------------------

export interface AssessmentAssetsResponse {
  assessment_id: number;
  assessment_name: string;
  total: number;
  assets: AssetSelection[];
}

/**
 * Fetch convertible assets (tables, views, routines) from a completed assessment
 */
export const fetchAssessmentAssets = async (
  assessmentId: number
): Promise<AssessmentAssetsResponse> => {
  return api.get<AssessmentAssetsResponse>(`/api/assessments/${assessmentId}/assets`);
};
