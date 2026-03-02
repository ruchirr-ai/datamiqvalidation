/**
 * API Client
 * Centralized API client with authentication and error handling
 */

const getApiBaseUrl = () => {
  if (import.meta.env.VITE_API_URL !== undefined && import.meta.env.VITE_API_URL !== '') {
    return import.meta.env.VITE_API_URL;
  }
  // In production (served via nginx), use relative URLs (empty base)
  // In dev (localhost:3000/5173), point to backend on port 8000
  const hostname = window.location.hostname;
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return 'http://localhost:8000';
  }
  return '';  // nginx proxies /api/ to backend
};

const API_BASE_URL = getApiBaseUrl();

export interface ApiError {
  message: string;
  status: number;
  detail?: string;
}

class ApiClient {
  private baseURL: string;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }

  private getAuthToken(): string | null {
    return localStorage.getItem('auth_token');
  }

  private getHeaders(customHeaders?: HeadersInit): HeadersInit {
    const token = this.getAuthToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...customHeaders as Record<string, string>
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    return headers;
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      const error: ApiError = {
        message: response.statusText,
        status: response.status
      };

      try {
        const errorData = await response.json();
        error.detail = errorData.detail || errorData.error || errorData.message;
      } catch {
        // Response body is not JSON
      }

      // Handle 401 Unauthorized - token expired or invalid
      if (response.status === 401) {
        // Clear token and redirect to login
        localStorage.removeItem('auth_token');
        window.location.href = '/login';
      }

      throw error;
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    return response.json();
  }

  async get<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      method: 'GET',
      headers: this.getHeaders(options?.headers),
      ...options
    });

    return this.handleResponse<T>(response);
  }

  async post<T>(endpoint: string, data?: any, options?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      method: 'POST',
      headers: this.getHeaders(options?.headers),
      body: data ? JSON.stringify(data) : undefined,
      ...options
    });

    return this.handleResponse<T>(response);
  }

  async put<T>(endpoint: string, data?: any, options?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      method: 'PUT',
      headers: this.getHeaders(options?.headers),
      body: data ? JSON.stringify(data) : undefined,
      ...options
    });

    return this.handleResponse<T>(response);
  }

  async patch<T>(endpoint: string, data?: any, options?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      method: 'PATCH',
      headers: this.getHeaders(options?.headers),
      body: data ? JSON.stringify(data) : undefined,
      ...options
    });

    return this.handleResponse<T>(response);
  }

  async delete<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      method: 'DELETE',
      headers: this.getHeaders(options?.headers),
      ...options
    });

    return this.handleResponse<T>(response);
  }
}

// Export singleton instance
export const apiClient = new ApiClient(API_BASE_URL);

// Export convenience methods
export const api = {
  get: <T>(endpoint: string, options?: RequestInit) => apiClient.get<T>(endpoint, options),
  post: <T>(endpoint: string, data?: any, options?: RequestInit) => apiClient.post<T>(endpoint, data, options),
  put: <T>(endpoint: string, data?: any, options?: RequestInit) => apiClient.put<T>(endpoint, data, options),
  patch: <T>(endpoint: string, data?: any, options?: RequestInit) => apiClient.patch<T>(endpoint, data, options),
  delete: <T>(endpoint: string, options?: RequestInit) => apiClient.delete<T>(endpoint, options)
};

// Connection Testing API
export interface TestConnectionRequest {
  database: string;
  connection_params: Record<string, any>;
}

export interface TestConnectionResponse {
  success: boolean;
  message: string;
  details?: Record<string, any>;
}

export const testConnection = async (
  database: string,
  connectionParams: Record<string, any>
): Promise<TestConnectionResponse> => {
  return api.post<TestConnectionResponse>('/api/connections/test', {
    database,
    connection_params: connectionParams
  });
};

// Connection CRUD API
export interface Connection {
  id: number;
  name: string;
  type: string;
  database: string;
  connection_params: Record<string, any>;
  connection_string?: string;
  created_by: string;
  status: string;
  last_tested_at: string | null;
  created_at: string;
  updated_at: string;
  is_active?: boolean;
  workspace_id?: number;
}

export interface CreateConnectionRequest {
  name: string;
  type: string;
  database: string;
  connection_params: Record<string, any>;
  created_by?: string;
}

export const createConnection = async (
  data: CreateConnectionRequest
): Promise<{ success: boolean; message: string; connection: Connection }> => {
  return api.post('/api/connections/', data);
};

export const listConnections = async (): Promise<Connection[]> => {
  return api.get<Connection[]>('/api/connections/');
};

export const deleteConnection = async (connectionId: number): Promise<void> => {
  return api.delete(`/api/connections/${connectionId}`);
};

export const updateConnectionStatus = async (
  connectionId: number,
  status: string,
  lastTestedAt: string
): Promise<Connection> => {
  return api.put<Connection>(`/api/connections/${connectionId}/status`, {
    status,
    last_tested_at: lastTestedAt
  });
};
