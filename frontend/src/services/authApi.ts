/**
 * Authentication API
 * API methods for authentication operations
 */

import { api } from './api';

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: {
    id: number;
    username: string;
    role: string;
    organization_id?: number;
  };
}

export interface UserInfoResponse {
  user: {
    id: number;
    username: string;
    role: string;
    organization_id?: number;
  };
  workspaces: Array<{
    id: number;
    name: string;
    slug: string;
    role: string;
  }>;
}

export interface RefreshTokenResponse {
  access_token: string;
  token_type: string;
}

export const authApi = {
  /**
   * Login with username and password
   */
  login: async (username: string, password: string): Promise<LoginResponse> => {
    return api.post<LoginResponse>('/api/auth/login', {
      username,
      password
    });
  },

  /**
   * Logout current user
   */
  logout: async (): Promise<void> => {
    return api.post<void>('/api/auth/logout');
  },

  /**
   * Get current user information
   */
  getCurrentUser: async (): Promise<UserInfoResponse> => {
    return api.get<UserInfoResponse>('/api/auth/me');
  },

  /**
   * Refresh authentication token
   */
  refreshToken: async (): Promise<RefreshTokenResponse> => {
    return api.post<RefreshTokenResponse>('/api/auth/refresh');
  }
};
