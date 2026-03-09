/**
 * API service for BigQuery to Redshift migrations
 */

const API_BASE = '/api/migrations/bq-redshift';

export interface Migration {
  id: number;
  migration_name: string;
  pathway: 'A' | 'B' | 'C' | 'D';
  status: string;
  current_stage: string | null;
  source?: {
    connection_id?: number;
    project_id?: string;
    dataset?: string;
    tables?: string[];
  };
  target?: {
    connection_id?: number;
    cluster?: string;
    database?: string;
    schema?: string;
  };
  storage?: {
    gcs_bucket?: string;
    gcs_path?: string;
    s3_bucket?: string;
    s3_path?: string;
    export_format?: string;
    compression?: string;
  };
  schedule?: {
    type?: string;
    cron_expression?: string;
    next_run_time?: string | null;
  };
  state?: {
    status?: string;
    current_stage?: string | null;
  };
  metrics?: {
    total_rows_source?: number | null;
    total_rows_target?: number | null;
    total_bytes_transferred?: number | null;
    start_time?: string | null;
    end_time?: string | null;
    duration_seconds?: number | null;
    last_run_at?: string | null;
  };
  // Flat fields for list view compatibility
  source_connection_name?: string;
  target_connection_name?: string;
  // Path B: DataSync fields
  datasync_existing_vm_ip?: string;
  datasync_s3_role_arn?: string;
  gcs_access_key?: string;
  aws_region?: string;
  created_at: string;
  updated_at: string;
  start_time: string | null;
  end_time: string | null;
  last_run_at: string | null;
  duration_seconds: number | null;
}

export interface CreateMigrationRequest {
  migration_name: string;
  pathway: 'A' | 'B' | 'C' | 'D';
  source_project_id: string;
  source_dataset: string;
  source_tables: string[];
  target_cluster: string;
  target_database: string;
  target_schema: string;
  gcs_bucket: string;
  gcs_path: string;
  s3_bucket: string;
  s3_path: string;
  schedule_cron?: string;
}

export interface MigrationStatus {
  migration_id: number;
  status: string;
  current_stage: string;
  pathway: string;
  progress: {
    total_shards: number;
    completed_shards: number;
    failed_shards: number;
    percentage: number;
  };
  start_time: string | null;
  end_time: string | null;
  duration_seconds: number | null;
  metrics: {
    total_rows_source: number | null;
    total_rows_target: number | null;
    total_bytes_transferred: number | null;
  };
}

export interface MigrationLog {
  id: number;
  migration_id: number;
  timestamp: string;
  log_level: string;
  stage: string;
  message: string;
  error_code: string | null;
}

export interface BigQueryDataset {
  dataset_id: string;
  location: string;
  created: string;
  modified: string;
  table_count?: number;
}

export interface BigQueryTable {
  table_id: string;
  dataset_id?: string;
  type?: string;
  table_type?: string;
  num_rows: number;
  num_bytes?: number;
  size_bytes?: number;
  created: string;
  modified: string;
  description?: string;
}

export interface BigQueryMetadataResponse {
  connection_id: number;
  project_id: string;
  datasets?: BigQueryDataset[];
  tables?: Record<string, BigQueryTable[]>;  // dataset_id -> tables
}

const getAuthHeaders = () => {
  // Try both possible token keys for compatibility
  const token = localStorage.getItem('auth_token') || localStorage.getItem('access_token');
  return {
    'Content-Type': 'application/json',
    ...(token && { 'Authorization': `Bearer ${token}` })
  };
};

export const bqRedshiftApi = {
  /**
   * List all migrations
   */
  async listMigrations(statusFilter?: string): Promise<Migration[]> {
    const params = statusFilter ? `?status_filter=${statusFilter}` : '';
    const response = await fetch(`${API_BASE}/list${params}`, {
      headers: getAuthHeaders()
    });
    
    if (!response.ok) {
      throw new Error('Failed to fetch migrations');
    }
    
    return response.json();
  },

  /**
   * Get migration by ID
   */
  async getMigration(id: number): Promise<Migration> {
    const response = await fetch(`${API_BASE}/${id}`, {
      method: 'GET',
      headers: getAuthHeaders()
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to get migration');
    }
    
    return response.json();
  },

  /**
   * Create new migration
   */
  async createMigration(data: CreateMigrationRequest): Promise<Migration> {
    const response = await fetch(`${API_BASE}/create`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(data)
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to create migration');
    }
    
    return response.json();
  },

  /**
   * Update existing migration
   */
  async updateMigration(id: number, data: Partial<CreateMigrationRequest>): Promise<Migration> {
    const response = await fetch(`${API_BASE}/${id}/update`, {
      method: 'PUT',
      headers: getAuthHeaders(),
      body: JSON.stringify(data)
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to update migration');
    }
    
    return response.json();
  },

  /**
   * Start migration
   */
  async startMigration(id: number): Promise<{ message: string }> {
    const response = await fetch(`${API_BASE}/${id}/start`, {
      method: 'POST',
      headers: getAuthHeaders()
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to start migration');
    }
    
    return response.json();
  },

  /**
   * Pause migration
   */
  async pauseMigration(id: number): Promise<{ message: string }> {
    const response = await fetch(`${API_BASE}/${id}/pause`, {
      method: 'POST',
      headers: getAuthHeaders()
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to pause migration');
    }
    
    return response.json();
  },

  /**
   * Resume migration
   */
  async resumeMigration(id: number): Promise<{ message: string }> {
    const response = await fetch(`${API_BASE}/${id}/resume`, {
      method: 'POST',
      headers: getAuthHeaders()
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to resume migration');
    }
    
    return response.json();
  },

  /**
   * Cancel migration
   */
  async cancelMigration(id: number): Promise<{ message: string }> {
    const response = await fetch(`${API_BASE}/${id}/cancel`, {
      method: 'POST',
      headers: getAuthHeaders()
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to cancel migration');
    }
    
    return response.json();
  },

  /**
   * Restart migration (reset to pending status)
   */
  async restartMigration(id: number): Promise<{ message: string }> {
    const response = await fetch(`${API_BASE}/${id}/restart`, {
      method: 'POST',
      headers: getAuthHeaders()
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to restart migration');
    }
    
    return response.json();
  },

  /**
   * Get migration status
   */
  async getStatus(id: number): Promise<MigrationStatus> {
    const response = await fetch(`${API_BASE}/${id}/status`, {
      headers: getAuthHeaders()
    });
    
    if (!response.ok) {
      throw new Error('Failed to fetch migration status');
    }
    
    return response.json();
  },

  /**
   * Get migration logs
   */
  async getLogs(id: number, limit?: number): Promise<MigrationLog[]> {
    const params = limit ? `?limit=${limit}` : '';
    const response = await fetch(`${API_BASE}/${id}/logs${params}`, {
      headers: getAuthHeaders()
    });
    
    if (!response.ok) {
      throw new Error('Failed to fetch migration logs');
    }
    
    return response.json();
  },

  /**
   * Get migration logs (alias for compatibility)
   */
  async getMigrationLogs(id: number, limit?: number): Promise<any> {
    const params = limit ? `?limit=${limit}` : '';
    const response = await fetch(`${API_BASE}/${id}/logs${params}`, {
      headers: getAuthHeaders()
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to fetch migration logs');
    }
    
    return response.json();
  },

  /**
   * Delete migration
   */
  async deleteMigration(id: number): Promise<{ message: string }> {
    const response = await fetch(`${API_BASE}/${id}`, {
      method: 'DELETE',
      headers: getAuthHeaders()
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to delete migration');
    }
    
    return response.json();
  },

  /**
   * Discover BigQuery metadata (datasets and tables)
   */
  async discoverMetadata(
    connectionId: number,
    projectId?: string,
    dataset?: string
  ): Promise<BigQueryMetadataResponse> {
    console.log('Calling discover-metadata API:', { connectionId, projectId, dataset });
    
    // Try both possible token keys for compatibility
    const token = localStorage.getItem('auth_token') || localStorage.getItem('access_token');
    console.log('Auth token:', token ? 'Present' : 'Missing');
    console.log('Token keys checked:', {
      auth_token: !!localStorage.getItem('auth_token'),
      access_token: !!localStorage.getItem('access_token')
    });
    
    if (!token) {
      console.error('No access token found in localStorage');
      throw new Error('Authentication required. Please log in.');
    }

    const requestBody = {
      connection_id: connectionId,
      project_id: projectId || undefined,
      dataset: dataset || undefined
    };
    
    console.log('Request body:', requestBody);
    console.log('Request headers:', getAuthHeaders());

    const response = await fetch(`${API_BASE}/discover-metadata`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(requestBody)
    });
    
    console.log('API Response status:', response.status, response.statusText);
    
    if (!response.ok) {
      if (response.status === 401) {
        console.error('401 Unauthorized - Token may be invalid or expired');
        throw new Error('Authentication failed. Please log out and log back in.');
      }
      
      let errorDetail = 'Failed to discover metadata';
      try {
        const error = await response.json();
        console.error('Error response:', error);
        errorDetail = error.detail || errorDetail;
      } catch (e) {
        console.error('Could not parse error response');
      }
      
      throw new Error(`${response.status}: ${errorDetail}`);
    }
    
    const data = await response.json();
    console.log('API Response data:', data);
    return data;
  }
};

// Export convenience function
export const discoverBigQueryMetadata = bqRedshiftApi.discoverMetadata;
