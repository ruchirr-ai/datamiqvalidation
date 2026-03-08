/**
 * API service for Task History (DataSync tasks)
 */

const API_BASE = '/api/task-history';

export interface TaskRecord {
  id: number;
  migration_id: number;
  migration_name: string;
  task_arn: string | null;
  execution_arn: string | null;
  task_name: string | null;
  task_type: string;
  agent_arn: string | null;
  agent_ip: string | null;
  source_location_arn: string | null;
  source_uri: string | null;
  dest_location_arn: string | null;
  dest_uri: string | null;
  table_name: string | null;
  status: 'running' | 'completed' | 'failed' | 'agent_offline';
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  files_transferred: number;
  bytes_transferred: number;
  error_message: string | null;
  error_code: string | null;
  error_details: any;
  raw_result: any;
  created_at: string;
}

export interface TaskHistoryResponse {
  total: number;
  records: TaskRecord[];
}

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token') || localStorage.getItem('access_token');
  return {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
  };
};

export const taskHistoryApi = {
  async list(params?: {
    status_filter?: string;
    migration_id?: number;
    search?: string;
    limit?: number;
    offset?: number;
  }): Promise<TaskHistoryResponse> {
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
    if (!response.ok) throw new Error('Failed to fetch task history');
    return response.json();
  },

  async get(id: number): Promise<TaskRecord> {
    const response = await fetch(`${API_BASE}/${id}`, {
      headers: getAuthHeaders(),
    });
    if (!response.ok) throw new Error('Failed to fetch task record');
    return response.json();
  },
};
