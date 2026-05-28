/**
 * ClickHouse Migration API Service
 * Handles API calls for BigQuery → GCS → ClickHouse migrations
 */

import { api } from './api';

export interface ClickHouseMigrationRequest {
  name: string;
  source_connection_id: number;
  target_connection_id: number;
  selected_tables: Array<{
    table_name: string;
    dataset_name: string;
    columns: Array<{ column_name: string; data_type: string; is_nullable: boolean }>;
    row_count: number;
    partitioning_columns?: string[];
    clustering_columns?: string[];
  }>;
  config: {
    gcsBucket: string;
    gcsPathPrefix: string;
    gcsRegion: string;
    gcsHmacAccessKey: string;
    gcsHmacSecretKey: string;
    clickhouseDatabase: string;
    clickhouseEngine: string;
    clickhouseOrderBy: string;
    exportFormat: string;
    compression: string;
  };
}

export interface MigrationStatus {
  migration_id: string;
  name: string;
  status: string;
  total_tables: number;
  completed_tables: number;
  failed_tables: number;
  current_table: string | null;
  current_stage: string | null;
  started_at: string | null;
  completed_at: string | null;
  table_results: Array<{
    table_name: string;
    status: string;
    last_stage: string;
    timestamp: string;
  }>;
}

export interface MigrationLog {
  table_name: string;
  stage: string;
  status: string;
  message: string;
  rows_processed: number;
  duration_seconds: number;
  error_detail: string | null;
  timestamp: string;
}

export const clickhouseMigrationApi = {
  /**
   * Start a new ClickHouse migration
   */
  startMigration: async (data: ClickHouseMigrationRequest): Promise<{ migration_id: string; status: string; message: string }> => {
    return api.post('/api/migrations/clickhouse/start', data);
  },

  /**
   * Get migration status
   */
  getStatus: async (migrationId: string): Promise<MigrationStatus> => {
    return api.get(`/api/migrations/clickhouse/${migrationId}/status`);
  },

  /**
   * Get migration logs
   */
  getLogs: async (migrationId: string): Promise<{ migration_id: string; logs: MigrationLog[] }> => {
    return api.get(`/api/migrations/clickhouse/${migrationId}/logs`);
  },

  /**
   * Retry failed tables
   */
  retryFailed: async (migrationId: string): Promise<{ message: string }> => {
    return api.post(`/api/migrations/clickhouse/${migrationId}/retry`, {});
  },

  /**
   * List all ClickHouse migrations
   */
  listMigrations: async (): Promise<{ migrations: MigrationStatus[] }> => {
    return api.get('/api/migrations/clickhouse/list');
  },
};
