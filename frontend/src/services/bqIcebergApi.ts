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
   * List existing Glue databases for a region
   */
  async listGlueDatabases(region: string = 'us-east-1'): Promise<{ name: string; description: string }[]> {
    const response = await fetch(`${API_BASE}/glue-databases?region=${encodeURIComponent(region)}`, {
      headers: getAuthHeaders(),
    });
    const data = await handleResponse<any>(response);
    return data.databases || [];
  },

  /**
  async getStructureReport(migrationId: number): Promise<StructureReport> {
    const response = await fetch(`${API_BASE}/${migrationId}/structure-report`, {
      headers: getAuthHeaders(),
    });
    const data = await handleResponse<any>(response);
    // API wraps the report — unwrap it
    const report = data.structure_report ?? data;

    // prerequisites can be a dict from backend — normalize to array
    let prerequisites: any[] = [];
    if (Array.isArray(report.prerequisites)) {
      prerequisites = report.prerequisites;
    } else if (report.prerequisites && typeof report.prerequisites === 'object') {
      // Convert dict like {iam_permissions: [...], glue_database: "..."} to flat list
      prerequisites = Object.entries(report.prerequisites).flatMap(([key, val]) => {
        if (key === 'lake_formation' && Array.isArray(val)) {
          return val.map((item: any) => ({
            id: `lake_formation-${item.action_type || Math.random()}`,
            label: item.description,
            description: item.arn_or_permission || '',
            category: 'lake_formation',
            arn_or_permission: item.arn_or_permission,
          }));
        }
        if (Array.isArray(val)) {
          return val.map((v: string) => ({ id: `${key}-${v}`, label: v, description: key.replace(/_/g, ' '), category: key }));
        }
        return [{ id: key, label: String(val), description: key.replace(/_/g, ' '), category: key }];
      });
    }

    // Normalize each table to match frontend TypeScript types
    const normalizedTables = (report.tables || []).map((t: any) => {
      const normalized = {
        iceberg_table_name: t.iceberg_table_name ?? t.proposed_name ?? t.source_table ?? '',
        source_table: t.source_table ?? '',
        is_custom: t.is_custom ?? false,
        estimated_row_count: t.estimated_row_count ?? t.estimated_rows ?? 0,
        estimated_data_size_bytes: t.estimated_data_size_bytes ?? Math.round((t.estimated_size_mb ?? 0) * 1024 * 1024),
        partition_spec: Array.isArray(t.partition_spec) ? t.partition_spec : [],
        sort_order: Array.isArray(t.sort_order) ? t.sort_order : [],
        properties: t.properties ?? t.table_properties ?? {},
        compaction_config: t.compaction_config ?? null,
        columns: (t.columns || []).map((c: any) => ({
          name: c.name ?? '',
          source_bq_type: c.source_bq_type ?? c.bq_type ?? c.data_type ?? '',
          iceberg_type: c.iceberg_type ?? '',
          nullable: c.nullable ?? c.mode !== 'REQUIRED',
          warnings: Array.isArray(c.warnings) ? c.warnings : [],
        })),
      };
      return { ...t, ...normalized };
    });

    return {
      ...report,
      tables: normalizedTables,
      warnings: report.warnings ?? [],
      prerequisites,
      dataset_to_db_mapping: report.dataset_to_db_mapping ?? {},
    } as StructureReport;
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
