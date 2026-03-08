/**
 * API service for Copy History
 */

const API_BASE = '/api/copy-history';

export interface CopyRecord {
  id: number;
  migration_id: number;
  migration_name: string;
  schema_name: string;
  table_name: string;
  copy_command: string;
  source_uri: string | null;
  file_format: string | null;
  compression: string | null;
  iam_role_arn: string | null;
  status: 'running' | 'completed' | 'failed';
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  rows_loaded: number;
  bytes_loaded: number;
  error_message: string | null;
  error_details: any;
  created_at: string;
}

export interface CopyHistoryResponse {
  total: number;
  records: CopyRecord[];
}

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token') || localStorage.getItem('access_token');
  return {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
  };
};

export const copyHistoryApi = {
  async list(params?: {
    status_filter?: string;
    migration_id?: number;
    search?: string;
    limit?: number;
    offset?: number;
  }): Promise<CopyHistoryResponse> {
    const searchParams = new URLSearchParams();
    if (params?.status_filter && params.status_filter !== 'all') searchParams.set('status_filter', params.status_filter);
    if (params?.migration_id) searchParams.set('migration_id', params.migration_id.toString());
    if (params?.search) searchParams.set('search', params.search);
    if (params?.limit) searchParams.set('limit', params.limit.toString());
    if (params?.offset) searchParams.set('offset', params.offset.toString());

    const qs = searchParams.toString();
    const response = await fetch(`${API_BASE}/list${qs ? `?${qs}` : ''}`, {
      headers: getAuthHeaders(),
    });
    if (!response.ok) throw new Error('Failed to fetch copy history');
    return response.json();
  },

  async get(id: number): Promise<CopyRecord> {
    const response = await fetch(`${API_BASE}/${id}`, {
      headers: getAuthHeaders(),
    });
    if (!response.ok) throw new Error('Failed to fetch copy record');
    return response.json();
  },
};
