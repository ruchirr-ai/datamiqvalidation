/**
 * Field Configuration Types
 * 
 * Types and interfaces for the database field configuration system.
 */

export type FieldType = 'text' | 'number' | 'password' | 'select' | 'checkbox';

export type DatabaseType = 'mongodb' | 'documentdb' | 'postgresql' | 'mysql' | 'oracle' | 'sqlserver' | 'bigquery' | 'redshift' | 'sybase' | 'db2';

export interface ValidationRules {
  minLength?: number;
  maxLength?: number;
  min?: number;
  max?: number;
  pattern?: string;
}

export interface FieldConfiguration {
  id: string;
  name: string;
  label: string;
  type: FieldType;
  enabled: boolean;
  required: boolean;
  placeholder?: string;
  defaultValue?: string;
  validation?: ValidationRules;
  helpText?: string;
  displayOrder: number;
  databaseType?: DatabaseType;
}

export interface DatabaseTypeInfo {
  id: DatabaseType;
  name: string;
  icon: string;
}

export interface FieldConfigFormData {
  name: string;
  label: string;
  type: FieldType;
  required: boolean;
  placeholder?: string;
  defaultValue?: string;
  helpText?: string;
  displayOrder: number;
  validation?: ValidationRules;
}

export interface FieldConfigAPIResponse {
  fields: FieldConfiguration[];
  databaseType: DatabaseType;
}

export interface FieldConfigCreateRequest {
  databaseType: DatabaseType;
  field: Omit<FieldConfiguration, 'id'>;
}

export interface FieldConfigUpdateRequest {
  fieldId: string;
  field: Partial<FieldConfiguration>;
}

export interface FieldConfigToggleRequest {
  fieldId: string;
  enabled: boolean;
}
