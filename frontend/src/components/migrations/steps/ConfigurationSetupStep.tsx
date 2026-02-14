import React, { useState } from 'react';
import { Input, Select, Toggle } from '../../ui';
import './StepStyles.css';
import './ConfigurationSetupStep.css';

interface ConfigurationSetupStepProps {
  formData: any;
  updateFormData: (updates: any) => void;
  isEditMode?: boolean;
  onSave?: () => Promise<void>;
}

const GCS_REGIONS = [
  // Americas - Single Regions
  { value: 'northamerica-northeast1', label: 'northamerica-northeast1 (Montréal) - Single Region', category: 'Americas' },
  { value: 'northamerica-northeast2', label: 'northamerica-northeast2 (Toronto) - Single Region', category: 'Americas' },
  { value: 'us-central1', label: 'us-central1 (Iowa) - Single Region', category: 'Americas' },
  { value: 'us-east1', label: 'us-east1 (South Carolina) - Single Region', category: 'Americas' },
  { value: 'us-east4', label: 'us-east4 (Northern Virginia) - Single Region', category: 'Americas' },
  { value: 'us-east5', label: 'us-east5 (Columbus) - Single Region', category: 'Americas' },
  { value: 'us-south1', label: 'us-south1 (Dallas) - Single Region', category: 'Americas' },
  { value: 'us-west1', label: 'us-west1 (Oregon) - Single Region', category: 'Americas' },
  { value: 'us-west2', label: 'us-west2 (Los Angeles) - Single Region', category: 'Americas' },
  { value: 'us-west3', label: 'us-west3 (Salt Lake City) - Single Region', category: 'Americas' },
  { value: 'us-west4', label: 'us-west4 (Las Vegas) - Single Region', category: 'Americas' },
  { value: 'southamerica-east1', label: 'southamerica-east1 (São Paulo) - Single Region', category: 'Americas' },
  { value: 'southamerica-west1', label: 'southamerica-west1 (Santiago) - Single Region', category: 'Americas' },
  
  // Europe - Single Regions
  { value: 'europe-central2', label: 'europe-central2 (Warsaw) - Single Region', category: 'Europe' },
  { value: 'europe-north1', label: 'europe-north1 (Finland) - Single Region', category: 'Europe' },
  { value: 'europe-southwest1', label: 'europe-southwest1 (Madrid) - Single Region', category: 'Europe' },
  { value: 'europe-west1', label: 'europe-west1 (Belgium) - Single Region', category: 'Europe' },
  { value: 'europe-west2', label: 'europe-west2 (London) - Single Region', category: 'Europe' },
  { value: 'europe-west3', label: 'europe-west3 (Frankfurt) - Single Region', category: 'Europe' },
  { value: 'europe-west4', label: 'europe-west4 (Netherlands) - Single Region', category: 'Europe' },
  { value: 'europe-west6', label: 'europe-west6 (Zürich) - Single Region', category: 'Europe' },
  { value: 'europe-west8', label: 'europe-west8 (Milan) - Single Region', category: 'Europe' },
  { value: 'europe-west9', label: 'europe-west9 (Paris) - Single Region', category: 'Europe' },
  { value: 'europe-west12', label: 'europe-west12 (Turin) - Single Region', category: 'Europe' },
  
  // Asia Pacific - Single Regions
  { value: 'asia-east1', label: 'asia-east1 (Taiwan) - Single Region', category: 'Asia Pacific' },
  { value: 'asia-east2', label: 'asia-east2 (Hong Kong) - Single Region', category: 'Asia Pacific' },
  { value: 'asia-northeast1', label: 'asia-northeast1 (Tokyo) - Single Region', category: 'Asia Pacific' },
  { value: 'asia-northeast2', label: 'asia-northeast2 (Osaka) - Single Region', category: 'Asia Pacific' },
  { value: 'asia-northeast3', label: 'asia-northeast3 (Seoul) - Single Region', category: 'Asia Pacific' },
  { value: 'asia-south1', label: 'asia-south1 (Mumbai) - Single Region', category: 'Asia Pacific' },
  { value: 'asia-south2', label: 'asia-south2 (Delhi) - Single Region', category: 'Asia Pacific' },
  { value: 'asia-southeast1', label: 'asia-southeast1 (Singapore) - Single Region', category: 'Asia Pacific' },
  { value: 'asia-southeast2', label: 'asia-southeast2 (Jakarta) - Single Region', category: 'Asia Pacific' },
  { value: 'australia-southeast1', label: 'australia-southeast1 (Sydney) - Single Region', category: 'Asia Pacific' },
  { value: 'australia-southeast2', label: 'australia-southeast2 (Melbourne) - Single Region', category: 'Asia Pacific' },
  
  // Middle East & Africa - Single Regions
  { value: 'me-central1', label: 'me-central1 (Doha) - Single Region', category: 'Middle East' },
  { value: 'me-west1', label: 'me-west1 (Tel Aviv) - Single Region', category: 'Middle East' },
  { value: 'africa-south1', label: 'africa-south1 (Johannesburg) - Single Region', category: 'Africa' },
  
  // Dual Regions
  { value: 'NAM4', label: 'NAM4 (Iowa + South Carolina) - Dual Region', category: 'Dual Regions' },
  { value: 'EUR4', label: 'EUR4 (Netherlands + Finland) - Dual Region', category: 'Dual Regions' },
  { value: 'ASIA1', label: 'ASIA1 (Tokyo + Osaka) - Dual Region', category: 'Dual Regions' },
  
  // Multi-Regions
  { value: 'US', label: 'US (United States) - Multi-Region', category: 'Multi-Regions' },
  { value: 'EU', label: 'EU (European Union) - Multi-Region', category: 'Multi-Regions' },
  { value: 'ASIA', label: 'ASIA (Asia) - Multi-Region', category: 'Multi-Regions' },
];

const EXPORT_FORMATS = [
  { value: 'PARQUET', label: 'Parquet (Recommended)' },
  { value: 'AVRO', label: 'Avro' },
  { value: 'CSV', label: 'CSV' },
  { value: 'JSON', label: 'JSON (Newline-delimited)' },
];

const COMPRESSION_OPTIONS: Record<string, { value: string; label: string }[]> = {
  'CSV': [
    { value: 'NONE', label: 'None' },
    { value: 'GZIP', label: 'GZIP' }
  ],
  'JSON': [
    { value: 'NONE', label: 'None' },
    { value: 'GZIP', label: 'GZIP' }
  ],
  'AVRO': [
    { value: 'NONE', label: 'None' },
    { value: 'DEFLATE', label: 'Deflate' },
    { value: 'SNAPPY', label: 'Snappy' }
  ],
  'PARQUET': [
    { value: 'NONE', label: 'None' },
    { value: 'GZIP', label: 'GZIP' },
    { value: 'SNAPPY', label: 'Snappy' },
    { value: 'ZSTD', label: 'ZSTD' }
  ]
};

export const ConfigurationSetupStep: React.FC<ConfigurationSetupStepProps> = ({
  formData,
  updateFormData,
  isEditMode = false,
  onSave,
}) => {
  const pathway = formData.pathway;
  const [expandedStage, setExpandedStage] = useState<number>(1);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const toggleStage = (stageNumber: number) => {
    setExpandedStage(expandedStage === stageNumber ? 0 : stageNumber);
  };

  const handleSaveAndContinue = async (currentStage: number) => {
    // Save data in both create and edit modes (like stages 1 and 2)
    if (onSave) {
      setIsSaving(true);
      setSaveSuccess(false);
      try {
        await onSave();
        setSaveSuccess(true);
        // Show success message briefly
        setTimeout(() => setSaveSuccess(false), 2000);
        // Collapse current stage and expand next
        if (currentStage < 3) {
          setExpandedStage(currentStage + 1);
        }
      } catch (error) {
        console.error('Failed to save:', error);
        alert('Failed to save changes. Please try again.');
      } finally {
        setIsSaving(false);
      }
    } else {
      // Fallback: just toggle UI if no save function provided
      if (currentStage < 3) {
        setExpandedStage(currentStage + 1);
      }
    }
  };

  // Stage 1: BigQuery to GCS Export (Common for all paths)
  const renderBigQueryToGCS = () => {
    const isExpanded = expandedStage === 1;
    
    return (
      <div className="migration-stage-collapsible">
        <div 
          className="stage-header-collapsible" 
          onClick={() => toggleStage(1)}
        >
          <div className="stage-header-left">
            <div className="stage-number-collapsible">1</div>
            <div className="stage-info-collapsible">
              <h3>BigQuery to GCS Export</h3>
              <p>Configure BigQuery export settings to Google Cloud Storage</p>
            </div>
          </div>
          <button className="collapse-button" type="button">
            <svg 
              width="20" 
              height="20" 
              viewBox="0 0 20 20" 
              fill="none" 
              stroke="currentColor" 
              strokeWidth="2"
              className={isExpanded ? 'expanded' : ''}
            >
              <path d="M6 8l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>

        {isExpanded && (
          <div className="stage-content-collapsible">
            <div className="form-section">
              <label className="form-label">
                GCS Staging Bucket <span className="required">*</span>
              </label>
              <Input
                type="text"
                placeholder="gs://my-staging-bucket"
                value={formData.gcsBucket || ''}
                onChange={(e) => updateFormData({ gcsBucket: e.target.value })}
              />
              <p className="form-help">
                Google Cloud Storage bucket for BigQuery export data
              </p>
            </div>

            <div className="form-row">
              <div className="form-section">
                <label className="form-label">
                  GCS Region <span className="required">*</span>
                </label>
                <select
                  className="select-input"
                  value={formData.gcsRegion || 'us-central1'}
                  onChange={(e) => updateFormData({ gcsRegion: e.target.value })}
                >
                  <optgroup label="🌎 Americas - Single Regions">
                    {GCS_REGIONS.filter(r => r.category === 'Americas').map(region => (
                      <option key={region.value} value={region.value}>{region.label}</option>
                    ))}
                  </optgroup>
                  <optgroup label="🌍 Europe - Single Regions">
                    {GCS_REGIONS.filter(r => r.category === 'Europe').map(region => (
                      <option key={region.value} value={region.value}>{region.label}</option>
                    ))}
                  </optgroup>
                  <optgroup label="🌏 Asia Pacific - Single Regions">
                    {GCS_REGIONS.filter(r => r.category === 'Asia Pacific').map(region => (
                      <option key={region.value} value={region.value}>{region.label}</option>
                    ))}
                  </optgroup>
                  <optgroup label="🌐 Middle East & Africa">
                    {GCS_REGIONS.filter(r => r.category === 'Middle East' || r.category === 'Africa').map(region => (
                      <option key={region.value} value={region.value}>{region.label}</option>
                    ))}
                  </optgroup>
                  <optgroup label="🔗 Dual Regions (High Availability)">
                    {GCS_REGIONS.filter(r => r.category === 'Dual Regions').map(region => (
                      <option key={region.value} value={region.value}>{region.label}</option>
                    ))}
                  </optgroup>
                  <optgroup label="🌐 Multi-Regions (Geo-Redundant)">
                    {GCS_REGIONS.filter(r => r.category === 'Multi-Regions').map(region => (
                      <option key={region.value} value={region.value}>{region.label}</option>
                    ))}
                  </optgroup>
                </select>
                <p className="form-help">
                  Choose based on your GCS bucket location. Multi-regions provide geo-redundancy.
                </p>
              </div>

              <div className="form-section">
                <label className="form-label">
                  Export Format <span className="required">*</span>
                </label>
                <Select
                  value={formData.exportFormat || 'PARQUET'}
                  onChange={(value) => {
                    const format = String(value);
                    updateFormData({ 
                      exportFormat: format,
                      compression: 'NONE' // Reset compression when format changes
                    });
                  }}
                  options={EXPORT_FORMATS}
                />
              </div>
            </div>

            <div className="form-section">
              <label className="form-label">
                Compression <span className="required">*</span>
              </label>
              <Select
                value={formData.compression || 'NONE'}
                onChange={(value) => updateFormData({ compression: String(value) })}
                options={COMPRESSION_OPTIONS[formData.exportFormat || 'PARQUET'] || COMPRESSION_OPTIONS['PARQUET']}
              />
              <p className="form-help">
                {formData.compression === 'NONE' ? 'No compression (faster export, larger files)' :
                 formData.compression === 'GZIP' ? 'Good compression ratio, slower export' :
                 formData.compression === 'SNAPPY' ? 'Fast compression, moderate file size' :
                 formData.compression === 'DEFLATE' ? 'Balanced compression and speed' :
                 formData.compression === 'ZSTD' ? 'Excellent compression, good speed' :
                 'Select compression method for export'}
              </p>
            </div>

            <div className="form-section">
              <label className="form-label">
                GCP Service Account JSON <span className="required">*</span>
              </label>
              <textarea
                className="textarea-input"
                placeholder='{"type": "service_account", "project_id": "...", ...}'
                rows={4}
                value={formData.serviceAccountJson || ''}
                onChange={(e) => updateFormData({ serviceAccountJson: e.target.value })}
              />
              <p className="form-help">
                Service account with BigQuery and GCS permissions
              </p>
            </div>

            <div className="stage-footer">
              <button 
                className="btn-save-continue"
                onClick={() => handleSaveAndContinue(1)}
                type="button"
                disabled={isSaving}
              >
                {isSaving ? 'Saving...' : saveSuccess ? '✓ Saved' : 'Save & Continue'}
              </button>
            </div>
          </div>
        )}
      </div>
    );
  };

  // Stage 2: GCS to S3 Transfer - Path A (GCP Storage Transfer Service)
  const renderGCSToS3_PathA = () => {
    const isExpanded = expandedStage === 2;
    
    return (
      <div className="migration-stage-collapsible">
        <div 
          className="stage-header-collapsible" 
          onClick={() => toggleStage(2)}
        >
          <div className="stage-header-left">
            <div className="stage-number-collapsible">2</div>
            <div className="stage-info-collapsible">
              <h3>
                GCS → S3 Transfer
                <span className="pathway-badge">Path A</span>
              </h3>
              <p>Configure GCP Storage Transfer Service for data transfer</p>
            </div>
          </div>
          <button className="collapse-button" type="button">
            <svg 
              width="20" 
              height="20" 
              viewBox="0 0 20 20" 
              fill="none" 
              stroke="currentColor" 
              strokeWidth="2"
              className={isExpanded ? 'expanded' : ''}
            >
              <path d="M6 8l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>

        {isExpanded && (
          <div className="stage-content-collapsible">
            <div className="info-box" style={{ background: '#E8F4FD', borderColor: '#2A6BDB' }}>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#2A6BDB" strokeWidth="2">
                <circle cx="8" cy="8" r="6" />
                <path d="M8 6v4M8 11h.01" strokeLinecap="round" />
              </svg>
              <div>
                <strong>GCP Storage Transfer Service</strong>
                <p>
                  Uses Google's native Storage Transfer Service to push data directly from GCS to S3.
                  Requires AWS credentials for the transfer service to write to your S3 bucket.
                </p>
              </div>
            </div>

            <div className="form-section">
              <label className="form-label">
                S3 Bucket <span className="required">*</span>
              </label>
              <Input
                type="text"
                placeholder="my-s3-bucket"
                value={formData.s3Bucket || ''}
                onChange={(e) => updateFormData({ s3Bucket: e.target.value })}
              />
              <p className="form-help">
                AWS S3 bucket for storing transferred data (without s3:// prefix)
              </p>
            </div>

            <div className="form-section">
              <label className="form-label">
                S3 Path <span className="required">*</span>
              </label>
              <Input
                type="text"
                placeholder="migrations/bq-to-redshift"
                value={formData.s3Path || ''}
                onChange={(e) => updateFormData({ s3Path: e.target.value })}
              />
              <p className="form-help">
                Path within S3 bucket (without leading slash)
              </p>
            </div>

            <div className="form-section">
              <label className="form-label">
                AWS Access Key ID <span className="required">*</span>
              </label>
              <Input
                type="text"
                placeholder="AKIAIOSFODNN7EXAMPLE"
                value={formData.awsAccessKeyId || ''}
                onChange={(e) => updateFormData({ awsAccessKeyId: e.target.value })}
              />
              <p className="form-help">
                AWS credentials for Storage Transfer Service to write to S3
              </p>
            </div>

            <div className="form-section">
              <label className="form-label">
                AWS Secret Access Key <span className="required">*</span>
              </label>
              <Input
                type="password"
                placeholder="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
                value={formData.awsSecretAccessKey || ''}
                onChange={(e) => updateFormData({ awsSecretAccessKey: e.target.value })}
              />
              <p className="form-help">
                Keep this secure - will be encrypted in database
              </p>
            </div>

            {/* Transfer Options Section */}
            <div className="form-section" style={{ marginTop: '24px' }}>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px',
                marginBottom: '16px',
                paddingBottom: '12px',
                borderBottom: '2px solid var(--color-divider)'
              }}>
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M10 3v14M3 10h14" strokeLinecap="round" strokeLinejoin="round" />
                  <circle cx="10" cy="10" r="7" />
                </svg>
                <h4 style={{ 
                  margin: 0, 
                  fontSize: '16px', 
                  fontWeight: 600,
                  color: 'var(--color-text-primary)'
                }}>
                  Transfer Options
                </h4>
              </div>

              <div className="toggle-option">
                <div className="toggle-content">
                  <span className="toggle-title">Overwrite Existing Files</span>
                  <span className="toggle-description">
                    Overwrite files in S3 if they already exist
                  </span>
                </div>
                <Toggle
                  enabled={formData.overwriteFiles || false}
                  onChange={(enabled) => updateFormData({ overwriteFiles: enabled })}
                />
              </div>

              <div className="toggle-option">
                <div className="toggle-content">
                  <span className="toggle-title">Delete Source After Transfer</span>
                  <span className="toggle-description">
                    Delete files from GCS after successful transfer to S3
                  </span>
                </div>
                <Toggle
                  enabled={formData.deleteAfterTransfer || false}
                  onChange={(enabled) => updateFormData({ deleteAfterTransfer: enabled })}
                />
              </div>
            </div>

            <div className="stage-footer">
              <button 
                className="btn-save-continue"
                onClick={() => handleSaveAndContinue(2)}
                type="button"
                disabled={isSaving}
              >
                {isSaving ? 'Saving...' : saveSuccess ? '✓ Saved' : 'Save & Continue'}
              </button>
            </div>
          </div>
        )}
      </div>
    );
  };

  // Stage 2: GCS to S3 Transfer - Path B (AWS DataSync)
  const renderGCSToS3_PathB = () => {
    const isExpanded = expandedStage === 2;
    
    return (
      <div className="migration-stage-collapsible">
        <div 
          className="stage-header-collapsible" 
          onClick={() => toggleStage(2)}
        >
          <div className="stage-header-left">
            <div className="stage-number-collapsible">2</div>
            <div className="stage-info-collapsible">
              <h3>
                GCS → S3 Transfer
                <span className="pathway-badge">Path B</span>
              </h3>
              <p>Configure AWS DataSync for automated data transfer</p>
            </div>
          </div>
          <button className="collapse-button" type="button">
            <svg 
              width="20" 
              height="20" 
              viewBox="0 0 20 20" 
              fill="none" 
              stroke="currentColor" 
              strokeWidth="2"
              className={isExpanded ? 'expanded' : ''}
            >
              <path d="M6 8l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>

        {isExpanded && (
          <div className="stage-content-collapsible">
            <div className="info-box" style={{ background: '#FFF4E6', borderColor: '#FFD140' }}>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#FF9800" strokeWidth="2">
                <circle cx="8" cy="8" r="6" />
                <path d="M8 6v4M8 11h.01" strokeLinecap="round" />
              </svg>
              <div>
                <strong>AWS DataSync</strong>
                <p>
                  Automated data transfer using AWS DataSync agent. Deploys an EC2 agent in your VPC
                  to securely transfer data from GCS to S3 with automatic retry and delta sync capabilities.
                </p>
              </div>
            </div>

            <div className="form-section">
              <h4>AWS Infrastructure Configuration</h4>
              
              <div className="form-row">
                <div className="form-section">
                  <label className="form-label required">VPC Subnet ID</label>
                  <Input
                    type="text"
                    placeholder="subnet-0123456789abcdef0"
                    value={formData.datasyncSubnetId || ''}
                    onChange={(e) => updateFormData({ datasyncSubnetId: e.target.value })}
                    required
                  />
                  <p className="form-help">Private subnet for DataSync agent deployment</p>
                </div>

                <div className="form-section">
                  <label className="form-label required">Security Group ID</label>
                  <Input
                    type="text"
                    placeholder="sg-0123456789abcdef0"
                    value={formData.datasyncSecurityGroupId || ''}
                    onChange={(e) => updateFormData({ datasyncSecurityGroupId: e.target.value })}
                    required
                  />
                  <p className="form-help">Security group for DataSync agent (allow HTTPS outbound)</p>
                </div>
              </div>

              <div className="form-section">
                <label className="form-label">EC2 Instance Type</label>
                <Select
                  value={formData.datasyncInstanceType || 'm5.xlarge'}
                  onChange={(value) => updateFormData({ datasyncInstanceType: String(value) })}
                  options={[
                    { value: 'm5.large', label: 'm5.large (2 vCPU, 8 GB RAM)' },
                    { value: 'm5.xlarge', label: 'm5.xlarge (4 vCPU, 16 GB RAM) - Recommended' },
                    { value: 'm5.2xlarge', label: 'm5.2xlarge (8 vCPU, 32 GB RAM)' },
                    { value: 'm5.4xlarge', label: 'm5.4xlarge (16 vCPU, 64 GB RAM)' },
                  ]}
                />
                <p className="form-help">Instance type for DataSync agent (larger for better performance)</p>
              </div>
            </div>

            <div className="form-section" style={{ marginTop: '24px' }}>
              <h4>GCS HMAC Credentials</h4>
              <p className="form-help" style={{ marginBottom: '16px' }}>
                DataSync requires HMAC keys to access GCS. Generate these in Google Cloud Console → Storage → Settings → Interoperability.
              </p>
              
              <div className="form-row">
                <div className="form-section">
                  <label className="form-label required">GCS HMAC Access Key</label>
                  <Input
                    type="text"
                    placeholder="GOOG1E..."
                    value={formData.gcsAccessKey || ''}
                    onChange={(e) => updateFormData({ gcsAccessKey: e.target.value })}
                    required
                  />
                  <p className="form-help">GCS HMAC access key ID</p>
                </div>

                <div className="form-section">
                  <label className="form-label required">GCS HMAC Secret Key</label>
                  <Input
                    type="password"
                    placeholder="••••••••••••••••••••"
                    value={formData.gcsSecretKey || ''}
                    onChange={(e) => updateFormData({ gcsSecretKey: e.target.value })}
                    required
                  />
                  <p className="form-help">GCS HMAC secret key (encrypted and stored securely)</p>
                </div>
              </div>
            </div>

            <div className="form-section" style={{ marginTop: '24px' }}>
              <h4>S3 Destination</h4>
              
              <div className="form-row">
                <div className="form-section">
                  <label className="form-label required">S3 Bucket Name</label>
                  <Input
                    type="text"
                    placeholder="my-s3-bucket"
                    value={formData.s3Bucket || ''}
                    onChange={(e) => updateFormData({ s3Bucket: e.target.value })}
                    required
                  />
                  <p className="form-help">Target S3 bucket for data transfer</p>
                </div>

                <div className="form-section">
                  <label className="form-label required">S3 Path</label>
                  <Input
                    type="text"
                    placeholder="migrations/bq-to-redshift"
                    value={formData.s3Path || ''}
                    onChange={(e) => updateFormData({ s3Path: e.target.value })}
                    required
                  />
                  <p className="form-help">Path within S3 bucket</p>
                </div>
              </div>
            </div>

            <div className="stage-footer">
              <button 
                className="btn-save-continue"
                onClick={() => handleSaveAndContinue(2)}
                type="button"
                disabled={isSaving}
              >
                {isSaving ? 'Saving...' : saveSuccess ? '✓ Saved' : 'Save & Continue'}
              </button>
            </div>
          </div>
        )}
      </div>
    );
  };

  // Stage 2: GCS to S3 Transfer - Path C (Direct Transfer)
  const renderGCSToS3_PathC = () => {
    const isExpanded = expandedStage === 2;
    
    return (
      <div className="migration-stage-collapsible">
        <div 
          className="stage-header-collapsible" 
          onClick={() => toggleStage(2)}
        >
          <div className="stage-header-left">
            <div className="stage-number-collapsible">2</div>
            <div className="stage-info-collapsible">
              <h3>
                GCS to S3 Transfer
                <span className="pathway-badge">Path C</span>
              </h3>
              <p>Configure direct transfer from GCS to S3</p>
            </div>
          </div>
          <button className="collapse-button" type="button">
            <svg 
              width="20" 
              height="20" 
              viewBox="0 0 20 20" 
              fill="none" 
              stroke="currentColor" 
              strokeWidth="2"
              className={isExpanded ? 'expanded' : ''}
            >
              <path d="M6 8l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>

        {isExpanded && (
          <div className="stage-content-collapsible">
            <div className="form-section">
              <h4>S3 Configuration</h4>
              
              <div className="form-row">
                <div className="form-section">
                  <label className="form-label required">S3 Bucket Name</label>
                  <Input
                    type="text"
                    placeholder="my-s3-bucket"
                    value={formData.s3Bucket || ''}
                    onChange={(e) => updateFormData({ s3Bucket: e.target.value })}
                    required
                  />
                  <p className="form-help">Target S3 bucket for data transfer</p>
                </div>

                <div className="form-section">
                  <label className="form-label required">S3 Path</label>
                  <Input
                    type="text"
                    placeholder="migrations/bq-to-redshift"
                    value={formData.s3Path || ''}
                    onChange={(e) => updateFormData({ s3Path: e.target.value })}
                    required
                  />
                  <p className="form-help">Path within S3 bucket</p>
                </div>
              </div>

              <div className="form-row">
                <div className="form-section">
                  <label className="form-label required">AWS Access Key ID</label>
                  <Input
                    type="text"
                    placeholder="AKIAIOSFODNN7EXAMPLE"
                    value={formData.awsAccessKeyId || ''}
                    onChange={(e) => updateFormData({ awsAccessKeyId: e.target.value })}
                    required
                  />
                  <p className="form-help">AWS IAM access key with S3 write permissions</p>
                </div>

                <div className="form-section">
                  <label className="form-label required">AWS Secret Access Key</label>
                  <Input
                    type="password"
                    placeholder="••••••••••••••••••••"
                    value={formData.awsSecretAccessKey || ''}
                    onChange={(e) => updateFormData({ awsSecretAccessKey: e.target.value })}
                    required
                  />
                  <p className="form-help">AWS secret key (encrypted and stored securely)</p>
                </div>
              </div>
            </div>

            {/* Transfer Options Section */}
            <div className="form-section" style={{ marginTop: '24px' }}>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px',
                marginBottom: '16px',
                paddingBottom: '12px',
                borderBottom: '2px solid var(--color-divider)'
              }}>
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M10 3v14M3 10h14" strokeLinecap="round" strokeLinejoin="round" />
                  <circle cx="10" cy="10" r="7" />
                </svg>
                <h4 style={{ 
                  margin: 0, 
                  fontSize: '16px', 
                  fontWeight: 600,
                  color: 'var(--color-text-primary)'
                }}>
                  Transfer Options
                </h4>
              </div>

              <div className="toggle-option">
                <div className="toggle-content">
                  <span className="toggle-title">Overwrite Existing Files</span>
                  <span className="toggle-description">
                    Overwrite files in S3 if they already exist
                  </span>
                </div>
                <Toggle
                  enabled={formData.overwriteFiles || false}
                  onChange={(enabled) => updateFormData({ overwriteFiles: enabled })}
                />
              </div>

              <div className="toggle-option">
                <div className="toggle-content">
                  <span className="toggle-title">Delete Source After Transfer</span>
                  <span className="toggle-description">
                    Delete files from GCS after successful transfer to S3
                  </span>
                </div>
                <Toggle
                  enabled={formData.deleteAfterTransfer || false}
                  onChange={(enabled) => updateFormData({ deleteAfterTransfer: enabled })}
                />
              </div>
            </div>

            <div className="stage-footer">
              <button 
                className="btn-save-continue"
                onClick={() => handleSaveAndContinue(2)}
                type="button"
                disabled={isSaving}
              >
                {isSaving ? 'Saving...' : saveSuccess ? '✓ Saved' : 'Save & Continue'}
              </button>
            </div>
          </div>
        )}
      </div>
    );
  };

  // Stage 2: GCS to S3 Transfer - Path D (CLI Orchestration)
  const renderGCSToS3_PathD = () => {
    const isExpanded = expandedStage === 2;
    
    return (
      <div className="migration-stage-collapsible">
        <div 
          className="stage-header-collapsible" 
          onClick={() => toggleStage(2)}
        >
          <div className="stage-header-left">
            <div className="stage-number-collapsible">2</div>
            <div className="stage-info-collapsible">
              <h3>
                GCS to S3 Transfer
                <span className="pathway-badge">Path D</span>
              </h3>
              <p>Configure CLI-based orchestration for small-scale migrations</p>
            </div>
          </div>
          <button className="collapse-button" type="button">
            <svg 
              width="20" 
              height="20" 
              viewBox="0 0 20 20" 
              fill="none" 
              stroke="currentColor" 
              strokeWidth="2"
              className={isExpanded ? 'expanded' : ''}
            >
              <path d="M6 8l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>

        {isExpanded && (
          <div className="stage-content-collapsible">
            <div className="info-box">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="8" cy="8" r="6" />
                <path d="M8 6v4M8 11h.01" strokeLinecap="round" />
              </svg>
              <div>
                <strong>CLI Orchestration</strong>
                <p>
                  Command-line based approach using gsutil and AWS CLI for small-scale migrations
                  and legacy systems. Provides maximum control and flexibility.
                </p>
              </div>
            </div>

            <div className="form-section">
              <h4>Transfer Options</h4>
              <div className="form-row">
                <div className="form-section">
                  <label className="form-label">Parallelism</label>
                  <Input
                    type="number"
                    min="1"
                    max="100"
                    value={formData.parallelism || 10}
                    onChange={(e) => updateFormData({ parallelism: parseInt(e.target.value) })}
                  />
                  <p className="form-help">Number of parallel transfer threads</p>
                </div>

                <div className="form-section">
                  <label className="form-label">Compression Format</label>
                  <Select
                    value={formData.compressionFormat || 'gzip'}
                    onChange={(value) => updateFormData({ compressionFormat: String(value) })}
                    options={[
                      { value: 'none', label: 'None' },
                      { value: 'gzip', label: 'GZIP' },
                      { value: 'bzip2', label: 'BZIP2' },
                      { value: 'lz4', label: 'LZ4' },
                    ]}
                  />
                </div>
              </div>
            </div>

            <div className="toggle-option">
              <div className="toggle-content">
                <span className="toggle-title">Resume on Failure</span>
                <span className="toggle-description">
                  Resume transfer from last checkpoint if interrupted
                </span>
              </div>
              <Toggle
                enabled={formData.resumeOnFailure || true}
                onChange={(enabled) => updateFormData({ resumeOnFailure: enabled })}
              />
            </div>

            <div className="toggle-option">
              <div className="toggle-content">
                <span className="toggle-title">Verify Checksums</span>
                <span className="toggle-description">
                  Verify file integrity using MD5 checksums after transfer
                </span>
              </div>
              <Toggle
                enabled={formData.verifyChecksums || true}
                onChange={(enabled) => updateFormData({ verifyChecksums: enabled })}
              />
            </div>

            <div className="stage-footer">
              <button 
                className="btn-save-continue"
                onClick={() => handleSaveAndContinue(2)}
                type="button"
                disabled={isSaving}
              >
                {isSaving ? 'Saving...' : saveSuccess ? '✓ Saved' : 'Save & Continue'}
              </button>
            </div>
          </div>
        )}
      </div>
    );
  };

  // Stage 3: S3 to Redshift Load (Common for all paths)
  const renderS3ToRedshift = () => {
    const isExpanded = expandedStage === 3;
    
    return (
      <div className="migration-stage-collapsible">
        <div 
          className="stage-header-collapsible" 
          onClick={() => toggleStage(3)}
        >
          <div className="stage-header-left">
            <div className="stage-number-collapsible">3</div>
            <div className="stage-info-collapsible">
              <h3>S3 to Redshift Load</h3>
              <p>Configure Redshift COPY command parameters</p>
            </div>
          </div>
          <button className="collapse-button" type="button">
            <svg 
              width="20" 
              height="20" 
              viewBox="0 0 20 20" 
              fill="none" 
              stroke="currentColor" 
              strokeWidth="2"
              className={isExpanded ? 'expanded' : ''}
            >
              <path d="M6 8l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>

        {isExpanded && (
          <div className="stage-content-collapsible">
            <div className="info-box">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="8" cy="8" r="6" />
                <path d="M8 6v4M8 11h.01" strokeLinecap="round" />
              </svg>
              <div>
                <strong>Using Target Connection</strong>
                <p>
                  The Redshift connection selected in Step 1 will be used for loading data. 
                  COPY command will be automatically generated based on the export format from Stage 1.
                </p>
              </div>
            </div>

            <div className="form-section">
              <label className="form-label required">IAM Role ARN</label>
              <Input
                type="text"
                placeholder="arn:aws:iam::123456789012:role/RedshiftS3Role"
                value={formData.iamRoleArn || ''}
                onChange={(e) => updateFormData({ iamRoleArn: e.target.value })}
                required
              />
              <p className="form-help">
                IAM role that Redshift will use to access S3. Must have s3:GetObject and s3:ListBucket permissions.
              </p>
            </div>

            <div className="toggle-option">
              <div className="toggle-content">
                <span className="toggle-title">Truncate Before Load</span>
                <span className="toggle-description">
                  Truncate target tables before loading data
                </span>
              </div>
              <Toggle
                enabled={formData.truncateBeforeLoad || false}
                onChange={(enabled) => updateFormData({ truncateBeforeLoad: enabled })}
              />
            </div>

            <div className="stage-footer">
              <button 
                className="btn-save-continue"
                onClick={() => handleSaveAndContinue(3)}
                type="button"
                disabled={isSaving}
              >
                {isSaving ? 'Saving...' : saveSuccess ? '✓ Saved' : 'Save & Continue'}
              </button>
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="step-container">
      <div className="step-header">
        <h2>Migration Details</h2>
        <p>Configure the 3-stage migration process: BigQuery → GCS → S3 → Redshift</p>
      </div>

      <div className="step-content migration-details-collapsible">
        {!pathway && (
          <div className="warning-box">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M8 1l7 12H1L8 1z" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M8 6v3M8 11h.01" strokeLinecap="round" />
            </svg>
            <div>
              <strong>No pathway selected</strong>
              <p>Please go back and select a migration pathway first.</p>
            </div>
          </div>
        )}

        {pathway && (
          <>
            {/* Stage 1: BigQuery to GCS (Common) */}
            {renderBigQueryToGCS()}

            {/* Stage 2: GCS to S3 (Pathway-specific) */}
            {pathway === 'A' && renderGCSToS3_PathA()}
            {pathway === 'B' && renderGCSToS3_PathB()}
            {pathway === 'C' && renderGCSToS3_PathC()}
            {pathway === 'D' && renderGCSToS3_PathD()}

            {/* Stage 3: S3 to Redshift (Common) */}
            {renderS3ToRedshift()}
          </>
        )}
      </div>
    </div>
  );
};
