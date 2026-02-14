import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from '../ui';
import { ConnectionStagingStep } from './steps/ConnectionStagingStep';
import { MetadataDiscoveryStep } from './steps/MetadataDiscoveryStep';
import { StrategySelectionStep } from './steps/StrategySelectionStep';
import { ConfigurationSetupStep } from './steps/ConfigurationSetupStep';
import { SchedulingMonitoringStep } from './steps/SchedulingMonitoringStep';
import { bqRedshiftApi } from '../../services/bqRedshiftApi';
import './CreateMigrationWizard.css';

export interface MigrationFormData {
  // Step 1: Connection Configuration
  migrationName: string;
  migrationType: 'bigquery-redshift' | 'mongodb-documentdb' | null;
  sourceConnectionId: number | null;
  targetConnectionId: number | null;
  
  // Step 2: Metadata Discovery
  selectedTables: string[];
  sourceProjectId: string;
  sourceDataset: string;
  
  // Step 3: Strategy Selection
  pathway: 'A' | 'B' | 'C' | 'D' | null;
  
  // Step 4: Configuration & Setup
  // Stage 1: BigQuery to GCS (Common)
  gcsBucket?: string;
  gcsRegion?: string;
  exportFormat?: string;
  compression?: string;
  serviceAccountJson?: string;
  
  // Stage 2: GCS to S3 - Path A (GCP Storage Transfer)
  awsAccessKeyId?: string;
  awsSecretAccessKey?: string;
  overwriteFiles?: boolean;
  deleteAfterTransfer?: boolean;
  
  // Stage 2: GCS to S3 - Path B (AWS DataSync)
  datasyncSubnetId?: string;
  datasyncSecurityGroupId?: string;
  datasyncInstanceType?: string;
  gcsAccessKey?: string;
  gcsSecretKey?: string;
  
  // Stage 2: GCS to S3 - Path C (AWS DataSync)
  gcpHmacAccessKeyId?: string;
  gcpHmacSecret?: string;
  dataSyncAgentArn?: string;
  verificationMode?: string;
  bandwidthLimit?: string;
  
  // Stage 2: GCS to S3 - Path D (CLI)
  parallelism?: number;
  compressionFormat?: string;
  gcpServiceAccountPath?: string;
  resumeOnFailure?: boolean;
  verifyChecksums?: boolean;
  
  // Stage 2: S3 Configuration (All paths)
  s3Bucket?: string;
  s3Path?: string;
  s3Region?: string;
  
  // Stage 3: S3 to Redshift (Common)
  iamRoleArn?: string;
  truncateBeforeLoad?: boolean;
  
  // Step 5: Scheduling & Monitoring
  scheduleType: 'one-time' | 'recurring';
  cronExpression: string;
  emailNotifications: boolean;
  slackWebhook: string;
  logLevel: string;
  enableCheckpointing: boolean;
  retryFailedShards: boolean;
  maxRetries: number;
}

const INITIAL_FORM_DATA: MigrationFormData = {
  migrationName: '',
  migrationType: 'bigquery-redshift',
  sourceConnectionId: null,
  targetConnectionId: null,
  selectedTables: [],
  sourceProjectId: '',
  sourceDataset: '',
  pathway: null,
  
  // Stage 1: BigQuery to GCS
  gcsBucket: '',
  gcsRegion: 'us-central1',
  exportFormat: 'AVRO',
  compression: 'NONE',
  serviceAccountJson: '',
  
  // Stage 2: Path A (GCP Storage Transfer) configuration
  awsAccessKeyId: '',
  awsSecretAccessKey: '',
  overwriteFiles: false,
  deleteAfterTransfer: false,
  
  // Stage 2: S3 Configuration
  s3Bucket: '',
  s3Region: 'us-east-1',
  
  // Stage 3: S3 to Redshift
  iamRoleArn: '',
  truncateBeforeLoad: false,
  
  scheduleType: 'one-time',
  cronExpression: '0 2 * * *',
  emailNotifications: false,
  slackWebhook: '',
  logLevel: 'INFO',
  enableCheckpointing: true,
  retryFailedShards: true,
  maxRetries: 3,
};

export const CreateMigrationWizard: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [currentStep, setCurrentStep] = useState(1);
  const [formData, setFormData] = useState<MigrationFormData>(INITIAL_FORM_DATA);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isEditMode, setIsEditMode] = useState(false);
  const [editMigrationId, setEditMigrationId] = useState<number | null>(null);
  const [isLoadingMigration, setIsLoadingMigration] = useState(false);
  const [isOriginalEditMode, setIsOriginalEditMode] = useState(false); // Track if user came from edit URL

  const totalSteps = 5;

  // Load migration data if in edit mode
  useEffect(() => {
    const editId = searchParams.get('edit');
    if (editId) {
      setIsEditMode(true);
      setIsOriginalEditMode(true); // User came from edit URL
      setEditMigrationId(parseInt(editId));
      loadMigrationData(parseInt(editId));
    } else {
      // Reset to create mode if no edit parameter
      setIsEditMode(false);
      setIsOriginalEditMode(false);
      setEditMigrationId(null);
      setFormData(INITIAL_FORM_DATA);
      setCurrentStep(1);
    }
  }, [searchParams]);

  const loadMigrationData = async (migrationId: number) => {
    setIsLoadingMigration(true);
    try {
      console.log('Loading migration data for edit:', migrationId);
      const migration = await bqRedshiftApi.getMigration(migrationId);
      
      console.log('Migration data received:', migration);
      
      // Extract data from nested objects
      const sourceConnectionId = migration.source?.connection_id || null;
      const targetConnectionId = migration.target?.connection_id || null;
      const sourceProjectId = migration.source?.project_id || '';
      const sourceDataset = migration.source?.dataset || '';
      const sourceTables = migration.source?.tables || [];
      
      const gcsBucket = migration.storage?.gcs_bucket || '';
      const s3Bucket = migration.storage?.s3_bucket || '';
      const s3Path = migration.storage?.s3_path || '';
      const exportFormat = migration.storage?.export_format || 'AVRO';
      const compression = migration.storage?.compression || 'NONE';
      
      const scheduleType = migration.schedule?.type || 'one-time';
      const cronExpression = migration.schedule?.cron_expression || '0 2 * * *';
      
      // Convert table names to full format (dataset.table)
      // API returns: ['customers', 'orders']
      // UI expects: ['analytics.customers', 'analytics.orders']
      const selectedTablesWithDataset = sourceTables.map((tableName: string) => {
        // If already in dataset.table format, keep it
        if (tableName.includes('.')) {
          return tableName;
        }
        // Otherwise, prepend the dataset
        return `${sourceDataset}.${tableName}`;
      });
      
      console.log('Extracted data:', {
        sourceConnectionId,
        targetConnectionId,
        sourceProjectId,
        sourceDataset,
        sourceTables,
        selectedTablesWithDataset,
        pathway: migration.pathway
      });
      
      // Map API response to form data
      // Note: Connection IDs are read-only in edit mode
      setFormData({
        migrationName: migration.migration_name || '',
        migrationType: 'bigquery-redshift',
        sourceConnectionId: sourceConnectionId,
        targetConnectionId: targetConnectionId,
        selectedTables: selectedTablesWithDataset,
        sourceProjectId: sourceProjectId,
        sourceDataset: sourceDataset,
        pathway: migration.pathway as 'A' | 'B' | 'C' | 'D' || null,
        
        // Stage 1: BigQuery to GCS
        gcsBucket: gcsBucket,
        gcsRegion: 'us-central1', // Not stored in DB, use default
        exportFormat: exportFormat,
        compression: compression,
        serviceAccountJson: '', // Don't load sensitive data
        
        // Stage 2: S3 Configuration
        s3Bucket: s3Bucket,
        s3Path: s3Path,
        s3Region: 'us-east-1', // Not stored in DB, use default
        
        // AWS credentials - don't load for security
        awsAccessKeyId: '',
        awsSecretAccessKey: '',
        overwriteFiles: false, // Don't load for security
        deleteAfterTransfer: false, // Don't load for security
        
        // Stage 3: S3 to Redshift
        iamRoleArn: '',
        truncateBeforeLoad: false,
        
        // Scheduling
        scheduleType: scheduleType as 'one-time' | 'recurring',
        cronExpression: cronExpression,
        emailNotifications: false,
        slackWebhook: '',
        logLevel: 'INFO',
        enableCheckpointing: true,
        retryFailedShards: true,
        maxRetries: 3,
      });
      
      console.log('Migration data loaded successfully');
    } catch (error: any) {
      console.error('Failed to load migration data:', error);
      setError(`Failed to load migration: ${error.message}`);
    } finally {
      setIsLoadingMigration(false);
    }
  };

  const updateFormData = (updates: Partial<MigrationFormData>) => {
    setFormData(prev => ({ ...prev, ...updates }));
  };

  const validateStep = (): boolean => {
    setError(null);
    
    // DISABLED FOR UI TESTING - Allow free navigation
    return true;
  };

  const handleNext = () => {
    if (validateStep()) {
      setCurrentStep(prev => Math.min(prev + 1, totalSteps));
    }
  };

  const handleBack = () => {
    setError(null);
    setCurrentStep(prev => Math.max(prev - 1, 1));
  };

  const handleSubmit = async () => {
    if (!validateStep()) {
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await performSave();
      
      // Navigate back to migrations page
      navigate('/migrations');
    } catch (err: any) {
      console.error(`Failed to ${isEditMode ? 'update' : 'create'} migration:`, err);
      setError(err.message || `Failed to ${isEditMode ? 'update' : 'create'} migration`);
      alert(`Failed to ${isEditMode ? 'update' : 'create'} migration: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const performSave = async (): Promise<void> => {
    console.log('Saving migration with data:', formData);
    
    // Minimal validation - only check truly required fields
    if (!formData.migrationName) {
      throw new Error('Migration name is required');
    }
    if (!formData.pathway) {
      throw new Error('Migration pathway is required');
    }
    if (!formData.sourceConnectionId) {
      throw new Error('Source connection is required');
    }
    if (!formData.targetConnectionId) {
      throw new Error('Target connection is required');
    }
    
    // Extract table names without dataset prefix (only if tables are selected)
    let tableNames: string[] = [];
    if (formData.selectedTables && formData.selectedTables.length > 0 && formData.sourceDataset) {
      // selectedTables format: ['dataset.table1', 'dataset.table2']
      // Filter to only include tables from the selected dataset
      const tablesFromSelectedDataset = formData.selectedTables.filter(fullTableName => {
        const [dataset] = fullTableName.split('.');
        return dataset === formData.sourceDataset;
      });
      
      if (tablesFromSelectedDataset.length < formData.selectedTables.length) {
        const skippedCount = formData.selectedTables.length - tablesFromSelectedDataset.length;
        console.warn(`Skipping ${skippedCount} tables from other datasets. Only migrating tables from "${formData.sourceDataset}"`);
      }
      
      // Extract just the table names (without dataset prefix)
      tableNames = tablesFromSelectedDataset.map(fullTableName => {
        const parts = fullTableName.split('.');
        return parts.length > 1 ? parts[1] : fullTableName;
      });
      
      console.log('Selected tables (with dataset):', formData.selectedTables);
      console.log('Tables from selected dataset:', tablesFromSelectedDataset);
      console.log('Table names (without dataset):', tableNames);
    }
    
    // Prepare API request
    const migrationData = {
      migration_name: formData.migrationName,
      pathway: formData.pathway,
      source_connection_id: formData.sourceConnectionId,
      source_project_id: formData.sourceProjectId || '',
      source_dataset: formData.sourceDataset || '',
      source_tables: tableNames.length > 0 ? tableNames : [],
      target_connection_id: formData.targetConnectionId,
      target_cluster: 'redshift-cluster', // TODO: Get from connection
      target_database: 'target_db', // TODO: Get from connection
      target_schema: 'public',
      gcs_bucket: formData.gcsBucket || '',
      gcs_path: '/staging',
      s3_bucket: formData.s3Bucket || '',
      s3_path: formData.s3Path || '/staging',
      export_format: formData.exportFormat || 'AVRO',
      compression: formData.compression || 'NONE',
      // AWS credentials for GCS → S3 transfer (Path A & C)
      aws_access_key_id: formData.awsAccessKeyId || '',
      aws_secret_access_key: formData.awsSecretAccessKey || '',
      overwrite_existing_files: formData.overwriteFiles || false,
      delete_source_after_transfer: formData.deleteAfterTransfer || false,
      // AWS DataSync configuration (Path B)
      datasync_subnet_id: formData.datasyncSubnetId || '',
      datasync_security_group_id: formData.datasyncSecurityGroupId || '',
      datasync_instance_type: formData.datasyncInstanceType || 'm5.xlarge',
      gcs_access_key: formData.gcsAccessKey || '',
      gcs_secret_key: formData.gcsSecretKey || '',
      // IAM role for Redshift S3 access (Path C)
      iam_role_arn: formData.iamRoleArn || '',
      schedule_type: formData.scheduleType || 'one-time',
      cron_expression: formData.scheduleType === 'recurring' ? formData.cronExpression : undefined
    };
    
    console.log('Calling API with:', migrationData);
    
    // Call API to create or update migration
    try {
      if (isEditMode && editMigrationId) {
        console.log('Updating migration:', editMigrationId);
        const result = await bqRedshiftApi.updateMigration(editMigrationId, migrationData);
        console.log('Migration updated successfully:', result);
        return result;
      } else {
        console.log('Creating new migration');
        const result = await bqRedshiftApi.createMigration(migrationData);
        console.log('Migration created successfully:', result);
        
        // IMPORTANT: Switch to edit mode after first creation
        // This prevents creating multiple migrations on subsequent "Save & Continue" clicks
        if (result.id) {
          console.log('Switching to edit mode with migration ID:', result.id);
          setIsEditMode(true);
          setEditMigrationId(result.id);
        }
        
        return result;
      }
    } catch (error: any) {
      console.error('API Error:', error);
      console.error('Error message:', error.message);
      console.error('Error response:', error.response);
      throw error;
    }
  };

  const handleCancel = () => {
    if (window.confirm('Are you sure you want to cancel? All progress will be lost.')) {
      navigate('/migrations');
    }
  };

  const renderStep = () => {
    const isMongoDocumentDB = formData.migrationType === 'mongodb-documentdb';

    switch (currentStep) {
      case 1:
        return (
          <ConnectionStagingStep
            formData={formData}
            updateFormData={updateFormData}
            isEditMode={isEditMode}
          />
        );
      case 2:
        // For MongoDB to DocumentDB, skip metadata discovery (different workflow)
        if (isMongoDocumentDB) {
          return (
            <div className="step-container">
              <div className="step-header">
                <h2>MongoDB Collection Selection</h2>
                <p>Select collections to migrate from MongoDB to DocumentDB</p>
              </div>
              <div className="step-content">
                <div className="info-box">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="8" cy="8" r="6" />
                    <path d="M8 6v4M8 11h.01" strokeLinecap="round" />
                  </svg>
                  <div>
                    <strong>MongoDB to DocumentDB Migration</strong>
                    <p>
                      Collection selection and migration configuration for MongoDB to DocumentDB 
                      will be implemented in the next phase.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          );
        }
        return (
          <MetadataDiscoveryStep
            formData={formData}
            updateFormData={updateFormData}
            isEditMode={isEditMode}
          />
        );
      case 3:
        // For MongoDB to DocumentDB, skip strategy selection (different workflow)
        if (isMongoDocumentDB) {
          return (
            <div className="step-container">
              <div className="step-header">
                <h2>Migration Strategy</h2>
                <p>Configure MongoDB to DocumentDB migration strategy</p>
              </div>
              <div className="step-content">
                <div className="info-box">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="8" cy="8" r="6" />
                    <path d="M8 6v4M8 11h.01" strokeLinecap="round" />
                  </svg>
                  <div>
                    <strong>MongoDB to DocumentDB Migration Strategy</strong>
                    <p>
                      Migration strategy configuration for MongoDB to DocumentDB 
                      will be implemented in the next phase.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          );
        }
        return (
          <StrategySelectionStep
            formData={formData}
            updateFormData={updateFormData}
            isEditMode={isEditMode}
          />
        );
      case 4:
        // For MongoDB to DocumentDB, skip configuration (different workflow)
        if (isMongoDocumentDB) {
          return (
            <div className="step-container">
              <div className="step-header">
                <h2>Migration Configuration</h2>
                <p>Configure MongoDB to DocumentDB migration parameters</p>
              </div>
              <div className="step-content">
                <div className="info-box">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="8" cy="8" r="6" />
                    <path d="M8 6v4M8 11h.01" strokeLinecap="round" />
                  </svg>
                  <div>
                    <strong>MongoDB to DocumentDB Configuration</strong>
                    <p>
                      Migration configuration for MongoDB to DocumentDB 
                      will be implemented in the next phase.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          );
        }
        return (
          <ConfigurationSetupStep
            formData={formData}
            updateFormData={updateFormData}
            isEditMode={isEditMode}
            onSave={performSave}
          />
        );
      case 5:
        return (
          <SchedulingMonitoringStep
            formData={formData}
            updateFormData={updateFormData}
          />
        );
      default:
        return null;
    }
  };

  return (
    <div className="create-migration-wizard">
      {/* Header */}
      <div className="wizard-header">
        <h1>{isEditMode ? 'Edit Migration' : 'Setup Data Migration'}</h1>
        <p>{isEditMode ? 'Update your migration configuration' : 'Configure your data migration in 5 simple steps'}</p>
      </div>

      {/* Progress Indicator */}
      <div className="wizard-progress">
        {[1, 2, 3, 4, 5].map(step => (
          <div
            key={step}
            className={`progress-step ${currentStep === step ? 'active' : ''} ${
              currentStep > step ? 'completed' : ''
            }`}
            onClick={() => setCurrentStep(step)}
            style={{ cursor: 'pointer' }}
            title={`Click to go to step ${step}`}
          >
            <div className="step-number">{step}</div>
            <div className="step-label">
              {step === 1 && 'Connections'}
              {step === 2 && 'Select Tables'}
              {step === 3 && 'Strategy'}
              {step === 4 && 'Configuration'}
              {step === 5 && 'Schedule'}
            </div>
          </div>
        ))}
      </div>

      {/* Error Message */}
      {error && (
        <div className="wizard-error">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="8" cy="8" r="6" />
            <path d="M8 5v3M8 11h.01" strokeLinecap="round" />
          </svg>
          {error}
        </div>
      )}

      {/* Loading State */}
      {isLoadingMigration && (
        <div className="wizard-loading">
          <div className="spinner"></div>
          <p>Loading migration data...</p>
        </div>
      )}

      {/* Step Content */}
      <div className="wizard-content">
        {!isLoadingMigration && renderStep()}
      </div>

      {/* Navigation Buttons */}
      <div className="wizard-footer">
        <div className="footer-left">
          <Button variant="outline" onClick={handleCancel}>
            Cancel
          </Button>
        </div>
        <div className="footer-right">
          {currentStep > 1 && (
            <Button variant="outline" onClick={handleBack}>
              Back
            </Button>
          )}
          {currentStep < totalSteps ? (
            <Button variant="primary" onClick={handleNext}>
              Next
            </Button>
          ) : (
            <Button
              variant="primary"
              onClick={handleSubmit}
              disabled={isSubmitting}
            >
              {isSubmitting 
                ? (isOriginalEditMode ? 'Updating...' : 'Creating...') 
                : (isOriginalEditMode ? 'Update Migration' : 'Create Migration')
              }
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};
