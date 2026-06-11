/**
 * API service for BigQuery to Iceberg migrations
 */
import type {
  StructureReport,
  CostAnalysisReport,
  ApproveStructureRequest,
  ApproveStructureResponse,
  RecalculateCostRequest,
  CustomStructureDefinition,
  CustomStructureValidation,
} from '../types/bqIceberg';

const API_BASE = '/api/migrations/bq-iceberg';

const getAuthHeaders = (): Record<string, string> => {
  const token = localStorage.getItem('auth_token') || localStorage.getItem('access_token');
  return {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
  };
};

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const err = await response.json();
      detail = err.detail || err.message || detail;
    } catch {
      // non-JSON body
    }
    throw new Error(detail);
  }
  return response.json();
}

export const bqIcebergApi = {
  /**
   * Get structure report for a migration
   */
  async getStructureReport(migrationId: number): Promise<StructureReport> {
    const response = await fetch(`${API_BASE}/${migrationId}/structure-report`, {
      headers: getAuthHeaders(),
    });
    return handleResponse<StructureReport>(response);
  },

  /**
   * Approve structure and proceed to load stage
   */
  async approveStructure(
    migrationId: number,
    data: ApproveStructureRequest
  ): Promise<ApproveStructureResponse> {
    const response = await fetch(`${API_BASE}/${migrationId}/approve-structure`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<ApproveStructureResponse>(response);
  },

  /**
   * Request changes to the structure
   */
  async requestChanges(
    migrationId: number,
    data: ApproveStructureRequest
  ): Promise<{ message: string }> {
    const response = await fetch(`${API_BASE}/${migrationId}/request-changes`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<{ message: string }>(response);
  },

  /**
   * Define custom structure for a table
   */
  async defineCustomStructure(
    migrationId: number,
    customDef: CustomStructureDefinition
  ): Promise<CustomStructureValidation> {
    const response = await fetch(`${API_BASE}/${migrationId}/custom-structure`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(customDef),
    });
    return handleResponse<CustomStructureValidation>(response);
  },

  /**
   * Get cost analysis report
   */
  async getCostAnalysis(migrationId: number): Promise<CostAnalysisReport> {
    const response = await fetch(`${API_BASE}/${migrationId}/cost-analysis`, {
      headers: getAuthHeaders(),
    });
    return handleResponse<CostAnalysisReport>(response);
  },

  /**
   * Recalculate cost analysis with new growth rate
   */
  async recalculateCost(
    migrationId: number,
    data: RecalculateCostRequest
  ): Promise<CostAnalysisReport> {
    const response = await fetch(`${API_BASE}/${migrationId}/cost-analysis/recalculate`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<CostAnalysisReport>(response);
  },

  /**
   * Download structure report as markdown
   */
  async downloadReport(migrationId: number): Promise<Blob> {
    const response = await fetch(`${API_BASE}/${migrationId}/download-report`, {
      headers: getAuthHeaders(),
    });
    if (!response.ok) {
      throw new Error('Failed to download report');
    }
    return response.blob();
  },
};
