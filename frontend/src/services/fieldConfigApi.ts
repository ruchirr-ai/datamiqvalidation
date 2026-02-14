/**
 * Field Configuration API Service
 * 
 * Handles API calls for field configuration management.
 */

import { FieldConfiguration, DatabaseType } from '../types/fieldConfig';
import { api } from './api';

export const fieldConfigApi = {
  /**
   * Get all field configurations for a database type
   */
  async getFieldConfigs(databaseType: DatabaseType): Promise<FieldConfiguration[]> {
    try {
      const response = await api.get<FieldConfiguration[]>(`/api/field-configs/${databaseType}`);
      return response;
    } catch (error: any) {
      // If no configs exist in DB, return empty array (will use defaults from constants)
      if (error.status === 404 || (error.detail && error.detail.includes('not found'))) {
        return [];
      }
      throw error;
    }
  },

  /**
   * Create a new field configuration
   */
  async createFieldConfig(
    databaseType: DatabaseType,
    field: Omit<FieldConfiguration, 'id'>
  ): Promise<FieldConfiguration> {
    const response = await api.post<FieldConfiguration>(
      `/api/field-configs/${databaseType}`,
      {
        name: field.name,
        label: field.label,
        type: field.type,
        enabled: field.enabled ?? true,
        required: field.required ?? false,
        default_value: field.defaultValue,
        placeholder: field.placeholder,
        help_text: field.helpText,
        display_order: field.displayOrder ?? 0,
        validation: field.validation,
        options: field.options,
      }
    );
    return response;
  },

  /**
   * Update an existing field configuration
   */
  async updateFieldConfig(
    fieldId: string,
    updates: Partial<FieldConfiguration>
  ): Promise<FieldConfiguration> {
    // Build request body with only defined values
    const requestBody: any = {};
    
    if (updates.name !== undefined) requestBody.name = updates.name;
    if (updates.label !== undefined) requestBody.label = updates.label;
    if (updates.type !== undefined) requestBody.type = updates.type;
    if (updates.enabled !== undefined) requestBody.enabled = updates.enabled;
    if (updates.required !== undefined) requestBody.required = updates.required;
    if (updates.defaultValue !== undefined) requestBody.default_value = updates.defaultValue;
    if (updates.placeholder !== undefined) requestBody.placeholder = updates.placeholder;
    if (updates.helpText !== undefined) requestBody.help_text = updates.helpText;
    if (updates.displayOrder !== undefined) requestBody.display_order = updates.displayOrder;
    if (updates.validation !== undefined) requestBody.validation = updates.validation;
    if (updates.options !== undefined) requestBody.options = updates.options;
    
    const response = await api.put<FieldConfiguration>(
      `/api/field-configs/${fieldId}`,
      requestBody
    );
    return response;
  },

  /**
   * Delete a field configuration
   */
  async deleteFieldConfig(fieldId: string): Promise<void> {
    await api.delete(`/api/field-configs/${fieldId}`);
  },

  /**
   * Toggle field enabled status
   */
  async toggleFieldEnabled(fieldId: string, enabled: boolean): Promise<FieldConfiguration> {
    return this.updateFieldConfig(fieldId, { enabled });
  },

  /**
   * Seed default configurations for a database type
   */
  async seedDefaultConfigs(databaseType: DatabaseType): Promise<{ success: boolean; count: number }> {
    const response = await api.post<{ success: boolean; count: number }>(
      `/api/field-configs/${databaseType}/seed`
    );
    return response;
  },
};
