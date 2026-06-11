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
  const [saveError, setSaveError] = useState<string | null>(null);

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
      } catch (error: any) {
        console.error('Failed to save:', error);
        const errorMsg = error?.message || 'Unknown error';
        setSaveError(errorMsg);
        setTimeout(() => setSaveError(null), 4000);
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

  // Stage 2: GCS to ClickHouse Import (ClickHouse target)
  const renderGCSToClickHouse = () => {
    const isExpanded = expandedStage === 2;

    return (
      <div className="migration-stage-collapsible">
        <div className="stage-header-collapsible" onClick={() => toggleStage(2)}>
          <div className="stage-header-left">
            <div className="stage-number-collapsible">2</div>
            <div className="stage-info-collapsible">
              <h3>GCS to ClickHouse Import</h3>
              <p>Configure ClickHouse import settings and HMAC credentials for GCS access</p>
            </div>
          </div>
          <button className="collapse-button" type="button">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" className={isExpanded ? 'expanded' : ''}>
              <path d="M6 8l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>

        {isExpanded && (
          <div className="stage-content-collapsible">
            <div className="form-section">
              <label className="form-label">GCS HMAC Access Key <span className="required">*</span></label>
              <Input type="text" placeholder="GOOGxxxxxxxxxxxxxxxx" value={formData.gcsHmacAccessKey || ''} onChange={(e) => updateFormData({ gcsHmacAccessKey: e.target.value })} />
              <p className="form-help">HMAC Access Key for ClickHouse to read from GCS (Cloud Storage → Settings → Interoperability)</p>
            </div>

            <div className="form-section">
              <label className="form-label">GCS HMAC Secret Key <span className="required">*</span></label>
              <Input type="password" placeholder="Enter HMAC secret key" value={formData.gcsHmacSecretKey || ''} onChange={(e) => updateFormData({ gcsHmacSecretKey: e.target.value })} />
              <p className="form-help">HMAC Secret Key associated with the access key above</p>
            </div>

            <div className="form-section">
              <label className="form-label">Target Database <span className="required">*</span></label>
              <Input type="text" placeholder="default" value={formData.clickhouseDatabase || 'default'} onChange={(e) => updateFormData({ clickhouseDatabase: e.target.value })} />
              <p className="form-help">ClickHouse database where tables will be created</p>
            </div>

            <div className="form-section">
              <label className="form-label">Table Engine</label>
              <Select value={formData.clickhouseEngine || 'MergeTree'} onChange={(value) => updateFormData({ clickhouseEngine: String(value) })} options={[
                { value: 'MergeTree', label: 'MergeTree (Default)' },
                { value: 'ReplacingMergeTree', label: 'ReplacingMergeTree (Deduplication)' },
                { value: 'SummingMergeTree', label: 'SummingMergeTree (Pre-aggregation)' },
                { value: 'AggregatingMergeTree', label: 'AggregatingMergeTree (Aggregates)' },
              ]} />
              <p className="form-help">MergeTree is recommended for most use cases</p>
            </div>

            <div className="form-section">
              <label className="form-label">ORDER BY Strategy</label>
              <Select value={formData.clickhouseOrderBy || 'auto'} onChange={(value) => updateFormData({ clickhouseOrderBy: String(value) })} options={[
                { value: 'auto', label: 'Auto-detect from BQ partitioning/clustering' },
                { value: 'tuple', label: 'tuple() — No ordering' },
                { value: 'custom', label: 'Custom (specify per table)' },
              ]} />
              <p className="form-help">ORDER BY determines data sort order on disk — affects query performance and compression</p>

              {formData.clickhouseOrderBy === 'custom' && formData.selectedTables && formData.selectedTables.length > 0 && (
                <div style={{ marginTop: '12px', border: '1px solid var(--color-divider)', borderRadius: '6px', padding: '12px' }}>
                  <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '8px' }}>Specify ORDER BY columns per table:</div>
                  {formData.selectedTables.map((t: any, idx: number) => {
                    const tableName = typeof t === 'string' ? (t.includes('.') ? t.split('.')[1] : t) : (t.table_name || t.name || '');
                    const customOrderByMap = formData.customOrderByMap || {};
                    return (
                      <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                        <span style={{ fontSize: '13px', fontWeight: 500, minWidth: '150px' }}>{tableName}</span>
                        <Input
                          type="text"
                          placeholder="e.g., customer_id, order_date"
                          value={customOrderByMap[tableName] || ''}
                          onChange={(e) => updateFormData({
                            customOrderByMap: { ...customOrderByMap, [tableName]: e.target.value }
                          })}
                        />
                      </div>
                    );
                  })}
                  <p style={{ fontSize: '11px', color: 'var(--color-text-secondary)', marginTop: '8px' }}>
                    Enter column names separated by commas. Leave empty to use tuple() (no ordering).
                  </p>
                </div>
              )}
            </div>

            <div className="info-box">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="8" cy="8" r="6" />
                <path d="M8 6v4M8 11h.01" strokeLinecap="round" />
              </svg>
              <div>
                <strong>How it works</strong>
                <p>Tables will be auto-created in ClickHouse with types mapped from BigQuery. Data is exported as Parquet to GCS, then imported using ClickHouse's s3() function with your HMAC credentials.</p>
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

  // Stage 2: GCS to S3 Transfer - Path B (AWS DataSync Agent on GCP VM)
  const renderGCSToS3_PathB = () => {
    const isExpanded = expandedStage === 2;
    const setupConfirmed = formData.datasyncSetupConfirmed || false;
    
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
              <p>Configure AWS DataSync agent on GCP VM for private data transfer</p>
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
            <p style={{ 
              fontSize: '13px', 
              color: '#424242', 
              padding: '12px 16px',
              background: '#F8F9FA',
              border: '1px solid #E0E0E0',
              borderRadius: '6px',
              marginBottom: '20px'
            }}>
              <strong>Private Network Transfer:</strong> The AWS DataSync agent runs as a GCP VM inside your VPC, giving it private access to GCS. Data transfers to S3 over an encrypted channel.
            </p>

            {/* Setup Instructions */}
            <div className="form-section" style={{ marginTop: '24px' }}>
              <h4 style={{ marginBottom: '12px', fontSize: '15px', fontWeight: 600 }}>Setup Instructions (One-Time)</h4>
              <div style={{ 
                padding: '16px', 
                background: '#F8F9FA', 
                border: '1px solid #E0E0E0',
                borderRadius: '6px',
                marginBottom: '16px'
              }}>
                <p style={{ fontSize: '13px', color: '#424242', marginBottom: '12px' }}>
                  Before proceeding, you must manually set up the DataSync agent VM.
                </p>
                <details style={{ marginTop: '8px' }}>
                  <summary style={{ cursor: 'pointer', fontWeight: 500, color: '#1976D2', fontSize: '13px' }}>
                    View step-by-step instructions
                  </summary>
                    <ol style={{ marginTop: '12px', marginLeft: '20px', fontSize: '13px', lineHeight: '1.8' }}>
                    <li style={{ marginBottom: '12px' }}>
                      <strong>Download the DataSync Agent Image from AWS Console:</strong>
                      <ul style={{ marginTop: '4px', marginLeft: '16px' }}>
                        <li>Go to <a href="https://console.aws.amazon.com/datasync/home#/agents/create" target="_blank" rel="noopener noreferrer" style={{ color: '#1976d2' }}>AWS DataSync Console → Create Agent</a></li>
                        <li>For <strong>Hypervisor</strong>, select <strong>"Kernel-based Virtual Machine (KVM)"</strong></li>
                        <li>Click the <strong>"Download the image"</strong> link — this downloads a ~700 MB ZIP file</li>
                        <li>Extract the ZIP to get the <code>.qcow2</code> file (e.g. <code>aws-datasync-2.x.x-x86_64.xfs.gpt.qcow2</code>)</li>
                      </ul>
                    </li>
                    <li style={{ marginBottom: '12px' }}>
                      <strong>Upload the qcow2 file to your GCS bucket:</strong>
                      <ul style={{ marginTop: '4px', marginLeft: '16px' }}>
                        <li><code>gsutil cp aws-datasync-*.qcow2 gs://YOUR_BUCKET/</code></li>
                      </ul>
                    </li>
                    <li style={{ marginBottom: '12px' }}>
                      <strong>Convert qcow2 to tar.gz format (required by GCP):</strong>
                      <ul style={{ marginTop: '4px', marginLeft: '16px' }}>
                        <li>Open <strong>Cloud Shell</strong> in GCP Console</li>
                        <li><code>sudo apt-get update && sudo apt-get install -y qemu-utils pigz</code></li>
                        <li><code>gsutil cp gs://YOUR_BUCKET/aws-datasync-*.qcow2 /tmp/datasync.qcow2</code></li>
                        <li><code>qemu-img convert -f qcow2 -O raw /tmp/datasync.qcow2 /tmp/disk.raw</code></li>
                        <li><code>cd /tmp && tar -cf - disk.raw | pigz &gt; datasync-agent.tar.gz</code></li>
                        <li><code>gsutil cp /tmp/datasync-agent.tar.gz gs://YOUR_BUCKET/</code></li>
                      </ul>
                    </li>
                    <li style={{ marginBottom: '12px' }}>
                      <strong>Import as a GCP Custom Image:</strong>
                      <ul style={{ marginTop: '4px', marginLeft: '16px' }}>
                        <li><code>gcloud compute images create aws-datasync-agent \<br/>&nbsp;&nbsp;--source-uri=gs://YOUR_BUCKET/datasync-agent.tar.gz \<br/>&nbsp;&nbsp;--project=YOUR_PROJECT_ID</code></li>
                      </ul>
                    </li>
                    <li style={{ marginBottom: '12px' }}>
                      <strong>Create a GCP VM from the image:</strong>
                      <ul style={{ marginTop: '4px', marginLeft: '16px' }}>
                        <li><code>gcloud compute instances create datasync-agent-vm \<br/>&nbsp;&nbsp;--zone=YOUR_ZONE \<br/>&nbsp;&nbsp;--machine-type=n1-standard-2 \<br/>&nbsp;&nbsp;--image=aws-datasync-agent \<br/>&nbsp;&nbsp;--boot-disk-size=80GB \<br/>&nbsp;&nbsp;--boot-disk-type=pd-standard \<br/>&nbsp;&nbsp;--project=YOUR_PROJECT_ID</code></li>
                      </ul>
                    </li>
                    <li style={{ marginBottom: '12px' }}>
                      <strong>Get the VM's IP address:</strong>
                      <ul style={{ marginTop: '4px', marginLeft: '16px' }}>
                        <li><code>gcloud compute instances describe datasync-agent-vm \<br/>&nbsp;&nbsp;--zone=YOUR_ZONE \<br/>&nbsp;&nbsp;--format="get(networkInterfaces[0].networkIP)"</code></li>
                        <li>Copy the internal IP (e.g. <code>10.128.0.5</code>) — you'll enter it below</li>
                      </ul>
                    </li>
                    <li style={{ marginBottom: '12px' }}>
                      <strong>Activate the agent in AWS Console (optional):</strong>
                      <ul style={{ marginTop: '4px', marginLeft: '16px' }}>
                        <li>DataMIQ handles agent activation automatically using the VM IP you provide</li>
                      </ul>
                    </li>
                  </ol>
                  <p style={{ marginTop: '12px', fontSize: '13px' }}>
                    <strong>Important:</strong> The VM must have outbound internet access to reach AWS DataSync endpoints. If it has no public IP, configure <strong>Cloud NAT</strong> on the VPC.
                  </p>
                  </details>
              </div>

              {/* Setup Confirmation Checkbox */}
              <div style={{ marginTop: '20px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={setupConfirmed}
                    onChange={(e) => updateFormData({ datasyncSetupConfirmed: e.target.checked })}
                    style={{ width: '16px', height: '16px', cursor: 'pointer', flexShrink: 0 }}
                  />
                  <span style={{ fontSize: '14px', color: '#424242' }}>
                    I have completed the DataSync agent VM setup
                  </span>
                </label>
              </div>
            </div>

            {/* VM IP Address (only show if setup confirmed) */}
            {setupConfirmed && (
              <div className="form-section" style={{ marginTop: '24px' }}>
                <h4>DataSync Agent VM</h4>
                <div className="form-section">
                  <label className="form-label required">VM Internal IP Address</label>
                  <Input
                    type="text"
                    placeholder="10.128.0.5"
                    value={formData.datasyncExistingVmIp || ''}
                    onChange={(e) => updateFormData({ datasyncExistingVmIp: e.target.value })}
                    required
                  />
                  <p className="form-help">
                    Internal IP of the GCP VM running the DataSync agent.
                    The agent must be accessible on port 80 (HTTP) for activation.
                  </p>
                </div>
              </div>
            )}

            {/* GCS HMAC Credentials (only show if setup confirmed) */}
            {setupConfirmed && (
              <div className="form-section" style={{ marginTop: '24px' }}>
                <h4>GCS HMAC Credentials</h4>
                <p className="form-help" style={{ marginBottom: '16px' }}>
                  DataSync uses HMAC keys to access GCS. Generate in Cloud Console → Storage → Settings → Interoperability.
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
                  </div>
                </div>
              </div>
            )}

            {/* AWS Credentials & S3 (only show if setup confirmed) */}
            {setupConfirmed && (
              <div className="form-section" style={{ marginTop: '24px' }}>
                <h4>AWS Credentials & S3 Destination</h4>
                <p className="form-help" style={{ marginBottom: '16px' }}>
                  AWS credentials for DataSync service and S3 access. IAM user needs DataSync and S3 permissions.
                </p>
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
                  </div>
                </div>
                <div className="form-row">
                  <div className="form-section">
                    <label className="form-label">AWS Region</label>
                    <select
                      className="select-input"
                      value={formData.awsRegion || 'us-east-1'}
                      onChange={(e) => updateFormData({ awsRegion: e.target.value })}
                    >
                      <option value="us-east-1">us-east-1 (N. Virginia)</option>
                      <option value="us-east-2">us-east-2 (Ohio)</option>
                      <option value="us-west-1">us-west-1 (N. California)</option>
                      <option value="us-west-2">us-west-2 (Oregon)</option>
                      <option value="eu-west-1">eu-west-1 (Ireland)</option>
                      <option value="eu-central-1">eu-central-1 (Frankfurt)</option>
                      <option value="ap-south-1">ap-south-1 (Mumbai)</option>
                      <option value="ap-southeast-1">ap-southeast-1 (Singapore)</option>
                      <option value="ap-southeast-2">ap-southeast-2 (Sydney)</option>
                      <option value="ap-northeast-1">ap-northeast-1 (Tokyo)</option>
                    </select>
                    <p className="form-help">AWS region for DataSync service and S3 bucket</p>
                  </div>
                  <div className="form-section">
                    <label className="form-label required">S3 Bucket Name</label>
                    <Input
                      type="text"
                      placeholder="my-s3-bucket"
                      value={formData.s3Bucket || ''}
                      onChange={(e) => updateFormData({ s3Bucket: e.target.value })}
                      required
                    />
                  </div>
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
                {/* IAM Role ARN Section with Setup Instructions */}
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
                      <rect x="3" y="3" width="14" height="14" rx="2" />
                      <path d="M7 10l2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    <h4 style={{ margin: 0, fontSize: '16px', fontWeight: 600, color: 'var(--color-text-primary)' }}>
                      DataSync S3 IAM Role
                    </h4>
                  </div>

                  <div style={{ 
                    padding: '12px 16px',
                    background: '#F8F9FA',
                    border: '1px solid #E0E0E0',
                    borderRadius: '6px',
                    marginBottom: '16px'
                  }}>
                    <p style={{ fontSize: '13px', color: '#424242', marginBottom: '8px' }}>
                      <strong>Required:</strong> DataSync needs an IAM role to access your S3 bucket.
                    </p>
                    <details style={{ marginTop: '8px' }}>
                      <summary style={{ cursor: 'pointer', fontWeight: 500, color: '#1976D2', fontSize: '13px' }}>
                        View setup instructions
                      </summary>
                        <div style={{ marginTop: '12px', fontSize: '13px', lineHeight: '1.8' }}>
                          <p style={{ fontWeight: 600, marginBottom: '8px' }}>Option A: AWS CLI (recommended)</p>
                          <ol style={{ marginLeft: '16px', marginBottom: '16px' }}>
                            <li style={{ marginBottom: '8px' }}>
                              <strong>Create a trust policy file</strong> (<code>trust-policy.json</code>):
                              <pre style={{ 
                                background: '#263238', color: '#EEFFFF', padding: '12px', borderRadius: '6px', 
                                fontSize: '12px', marginTop: '4px', overflowX: 'auto', whiteSpace: 'pre'
                              }}>{`{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "datasync.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}`}</pre>
                            </li>
                            <li style={{ marginBottom: '8px' }}>
                              <strong>Create the role:</strong>
                              <pre style={{ 
                                background: '#263238', color: '#EEFFFF', padding: '12px', borderRadius: '6px', 
                                fontSize: '12px', marginTop: '4px', overflowX: 'auto'
                              }}>aws iam create-role --role-name DataSyncS3AccessRole --assume-role-policy-document file://trust-policy.json</pre>
                            </li>
                            <li style={{ marginBottom: '8px' }}>
                              <strong>Attach S3 access policy:</strong>
                              <pre style={{ 
                                background: '#263238', color: '#EEFFFF', padding: '12px', borderRadius: '6px', 
                                fontSize: '12px', marginTop: '4px', overflowX: 'auto'
                              }}>aws iam attach-role-policy --role-name DataSyncS3AccessRole --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess</pre>
                            </li>
                            <li style={{ marginBottom: '8px' }}>
                              <strong>Get the Role ARN:</strong>
                              <pre style={{ 
                                background: '#263238', color: '#EEFFFF', padding: '12px', borderRadius: '6px', 
                                fontSize: '12px', marginTop: '4px', overflowX: 'auto'
                              }}>aws iam get-role --role-name DataSyncS3AccessRole --query "Role.Arn" --output text</pre>
                              <span style={{ color: '#888', fontSize: '12px' }}>Copy the output (e.g. <code>arn:aws:iam::123456789012:role/DataSyncS3AccessRole</code>) and paste below.</span>
                            </li>
                          </ol>

                          <p style={{ fontWeight: 600, marginBottom: '8px' }}>Option B: AWS Console (UI)</p>
                          <ol style={{ marginLeft: '16px' }}>
                            <li style={{ marginBottom: '6px' }}>
                              Go to <a href="https://console.aws.amazon.com/iam/home#/roles/create" target="_blank" rel="noopener noreferrer" style={{ color: '#1976d2' }}>IAM Console → Create Role</a>
                            </li>
                            <li style={{ marginBottom: '6px' }}>
                              Select <strong>"AWS service"</strong> as trusted entity type
                            </li>
                            <li style={{ marginBottom: '6px' }}>
                              Under <strong>"Use case"</strong>, choose <strong>"DataSync"</strong> from the dropdown (under "Use cases for other AWS services")
                            </li>
                            <li style={{ marginBottom: '6px' }}>
                              Click <strong>Next</strong>, then search for and select <strong>"AmazonS3FullAccess"</strong> policy
                            </li>
                            <li style={{ marginBottom: '6px' }}>
                              Click <strong>Next</strong>, name the role (e.g. <code>DataSyncS3AccessRole</code>), click <strong>Create role</strong>
                            </li>
                            <li style={{ marginBottom: '6px' }}>
                              Open the newly created role and copy the <strong>ARN</strong> from the summary page
                            </li>
                          </ol>

                          <div style={{ 
                            marginTop: '12px', padding: '8px 12px', background: '#E3F2FD', 
                            borderRadius: '4px', fontSize: '12px', color: '#1565C0' 
                          }}>
                            💡 <strong>Tip:</strong> For production, scope the S3 policy to your specific bucket instead of using <code>AmazonS3FullAccess</code>.
                          </div>
                        </div>
                      </details>
                  </div>

                  <label className="form-label required">DataSync S3 IAM Role ARN</label>
                  <Input
                    type="text"
                    placeholder="arn:aws:iam::123456789012:role/DataSyncS3AccessRole"
                    value={formData.datasyncS3RoleArn || ''}
                    onChange={(e) => updateFormData({ datasyncS3RoleArn: e.target.value })}
                    required
                  />
                  <p className="form-help">
                    Paste the IAM Role ARN you created above. DataSync will assume this role to read/write your S3 bucket.
                  </p>
                </div>
              </div>
            )}

            <div className="stage-footer">
              <button 
                className="btn-save-continue"
                onClick={() => handleSaveAndContinue(2)}
                type="button"
                disabled={isSaving || !setupConfirmed}
                title={!setupConfirmed ? 'Please confirm DataSync agent VM setup first' : ''}
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

            {/* Redshift IAM Role Section with Setup Instructions */}
            <div className="form-section">
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px',
                marginBottom: '16px',
                paddingBottom: '12px',
                borderBottom: '2px solid var(--color-divider)'
              }}>
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <rect x="3" y="3" width="14" height="14" rx="2" />
                  <path d="M7 10l2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                <h4 style={{ margin: 0, fontSize: '16px', fontWeight: 600, color: 'var(--color-text-primary)' }}>
                  Redshift S3 IAM Role
                </h4>
              </div>

              <div style={{ 
                padding: '12px 16px',
                background: '#F8F9FA',
                border: '1px solid #E0E0E0',
                borderRadius: '6px',
                marginBottom: '16px'
              }}>
                <p style={{ fontSize: '13px', color: '#424242', marginBottom: '8px' }}>
                  <strong>Required:</strong> Redshift needs an IAM role to read data from your S3 bucket during the COPY command.
                </p>
                <details style={{ marginTop: '8px' }}>
                  <summary style={{ cursor: 'pointer', fontWeight: 500, color: '#1976D2', fontSize: '13px' }}>
                    View setup instructions
                  </summary>
                    <div style={{ marginTop: '12px', fontSize: '13px', lineHeight: '1.8' }}>
                      <p style={{ fontWeight: 600, marginBottom: '8px' }}>Option A: AWS CLI (recommended)</p>
                      <ol style={{ marginLeft: '16px', marginBottom: '16px' }}>
                        <li style={{ marginBottom: '8px' }}>
                          <strong>Create a trust policy file</strong> (<code>redshift-trust-policy.json</code>):
                          <pre style={{ 
                            background: '#263238', color: '#EEFFFF', padding: '12px', borderRadius: '6px', 
                            fontSize: '12px', marginTop: '4px', overflowX: 'auto', whiteSpace: 'pre'
                          }}>{`{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "redshift.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}`}</pre>
                        </li>
                        <li style={{ marginBottom: '8px' }}>
                          <strong>Create the role:</strong>
                          <pre style={{ 
                            background: '#263238', color: '#EEFFFF', padding: '12px', borderRadius: '6px', 
                            fontSize: '12px', marginTop: '4px', overflowX: 'auto'
                          }}>aws iam create-role --role-name RedshiftS3AccessRole --assume-role-policy-document file://redshift-trust-policy.json</pre>
                        </li>
                        <li style={{ marginBottom: '8px' }}>
                          <strong>Attach S3 read access policy:</strong>
                          <pre style={{ 
                            background: '#263238', color: '#EEFFFF', padding: '12px', borderRadius: '6px', 
                            fontSize: '12px', marginTop: '4px', overflowX: 'auto'
                          }}>aws iam attach-role-policy --role-name RedshiftS3AccessRole --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess</pre>
                        </li>
                        <li style={{ marginBottom: '8px' }}>
                          <strong>Get the Role ARN:</strong>
                          <pre style={{ 
                            background: '#263238', color: '#EEFFFF', padding: '12px', borderRadius: '6px', 
                            fontSize: '12px', marginTop: '4px', overflowX: 'auto'
                          }}>aws iam get-role --role-name RedshiftS3AccessRole --query "Role.Arn" --output text</pre>
                          <span style={{ color: '#888', fontSize: '12px' }}>Copy the output (e.g. <code>arn:aws:iam::123456789012:role/RedshiftS3AccessRole</code>) and paste below.</span>
                        </li>
                      </ol>

                      <p style={{ fontWeight: 600, marginBottom: '8px' }}>Option B: AWS Console (UI)</p>
                      <ol style={{ marginLeft: '16px' }}>
                        <li style={{ marginBottom: '6px' }}>
                          Go to <a href="https://console.aws.amazon.com/iam/home#/roles/create" target="_blank" rel="noopener noreferrer" style={{ color: '#1976d2' }}>IAM Console → Create Role</a>
                        </li>
                        <li style={{ marginBottom: '6px' }}>
                          Select <strong>"AWS service"</strong> as trusted entity type
                        </li>
                        <li style={{ marginBottom: '6px' }}>
                          Under <strong>"Use case"</strong>, choose <strong>"Redshift - Customizable"</strong>
                        </li>
                        <li style={{ marginBottom: '6px' }}>
                          Click <strong>Next</strong>, then search for and select <strong>"AmazonS3ReadOnlyAccess"</strong> policy
                        </li>
                        <li style={{ marginBottom: '6px' }}>
                          Click <strong>Next</strong>, name the role (e.g. <code>RedshiftS3AccessRole</code>), click <strong>Create role</strong>
                        </li>
                        <li style={{ marginBottom: '6px' }}>
                          Open the newly created role and copy the <strong>ARN</strong> from the summary page
                        </li>
                      </ol>

                      <div style={{ 
                        marginTop: '12px', padding: '8px 12px', background: '#E3F2FD', 
                        borderRadius: '4px', fontSize: '12px', color: '#1565C0' 
                      }}>
                        💡 <strong>Tip:</strong> For production, scope the S3 policy to your specific bucket instead of using <code>AmazonS3ReadOnlyAccess</code>.
                      </div>
                    </div>
                  </details>
              </div>

              <label className="form-label required">Redshift IAM Role ARN</label>
              <Input
                type="text"
                placeholder="arn:aws:iam::123456789012:role/RedshiftS3AccessRole"
                value={formData.iamRoleArn || ''}
                onChange={(e) => updateFormData({ iamRoleArn: e.target.value })}
                required
              />
              <p className="form-help">
                Paste the IAM Role ARN you created above. Redshift will assume this role to read data from S3.
              </p>
            </div>

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
                  <path d="M4 4h12v12H4z" strokeLinecap="round" strokeLinejoin="round" />
                  <path d="M4 10h12M10 4v12" strokeLinecap="round" />
                </svg>
                <h4 style={{ margin: 0, fontSize: '16px', fontWeight: 600, color: 'var(--color-text-primary)' }}>
                  Load Type
                </h4>
              </div>

              <div className="radio-group">
                <label className={`radio-option ${formData.loadType === 'full' ? 'selected' : ''}`}
                  style={formData.loadType === 'full' ? { borderColor: 'var(--color-primary)', background: '#EFF6FF' } : {}}>
                  <input
                    type="radio"
                    name="loadType"
                    value="full"
                    checked={formData.loadType === 'full'}
                    onChange={() => updateFormData({ loadType: 'full', primaryKeyColumn: '', timestampColumn: '', tableLoadConfigs: {} })}
                  />
                  <div className="radio-content">
                    <span className="radio-title">Full Load</span>
                    <span className="radio-description">
                      Truncate target tables and reload all data from source. Best for initial migrations or small datasets.
                    </span>
                  </div>
                </label>

                <label className={`radio-option ${formData.loadType === 'incremental' ? 'selected' : ''}`}
                  style={formData.loadType === 'incremental' ? { borderColor: 'var(--color-primary)', background: '#EFF6FF' } : {}}>
                  <input
                    type="radio"
                    name="loadType"
                    value="incremental"
                    checked={formData.loadType === 'incremental'}
                    onChange={() => {
                      updateFormData({ loadType: 'incremental' });
                      // Initialize per-table configs for all selected tables if not already set
                      const selectedTables = (formData.selectedTables || []).map((t: string) => {
                        const parts = t.split('.');
                        return parts.length > 1 ? parts[1] : t;
                      });
                      if (selectedTables.length > 0) {
                        const existing = formData.tableLoadConfigs || {};
                        const updated = { ...existing };
                        selectedTables.forEach((tbl: string) => {
                          if (!updated[tbl]) {
                            updated[tbl] = { load_type: 'incremental', primary_key_column: '', timestamp_column: '' };
                          }
                        });
                        updateFormData({ tableLoadConfigs: updated });
                      }
                    }}
                  />
                  <div className="radio-content">
                    <span className="radio-title">Incremental Load</span>
                    <span className="radio-description">
                      Only export and load rows that changed since the last run. Requires a primary key and a timestamp column per table.
                    </span>
                  </div>
                </label>
              </div>

              {(() => {
                const selectedTables = (formData.selectedTables || []).map((t: string) => {
                  const parts = t.split('.');
                  return parts.length > 1 ? parts[1] : t;
                });
                const configs = formData.tableLoadConfigs || {};

                const updateTableConfig = (tableName: string, field: string, value: any) => {
                  const updated = { ...configs };
                  if (!updated[tableName]) {
                    updated[tableName] = { 
                      load_type: formData.loadType || 'full', 
                      primary_key_column: '', 
                      timestamp_column: '', 
                      truncate_before_load: false 
                    };
                  }
                  updated[tableName] = { ...updated[tableName], [field]: value };
                  updateFormData({ tableLoadConfigs: updated });
                };

                // Bulk operations
                const handleSelectAllTruncate = (enabled: boolean) => {
                  const updated = { ...configs };
                  selectedTables.forEach((tbl: string) => {
                    if (!updated[tbl]) {
                      updated[tbl] = { 
                        load_type: formData.loadType || 'full', 
                        primary_key_column: '', 
                        timestamp_column: '', 
                        truncate_before_load: enabled 
                      };
                    } else {
                      updated[tbl] = { ...updated[tbl], truncate_before_load: enabled };
                    }
                  });
                  updateFormData({ tableLoadConfigs: updated });
                };

                const handleSelectAllLoadType = (loadType: string) => {
                  const updated = { ...configs };
                  selectedTables.forEach((tbl: string) => {
                    if (!updated[tbl]) {
                      updated[tbl] = { 
                        load_type: loadType, 
                        primary_key_column: '', 
                        timestamp_column: '', 
                        truncate_before_load: false 
                      };
                    } else {
                      updated[tbl] = { 
                        ...updated[tbl], 
                        load_type: loadType,
                        // Clear PK and timestamp if switching to full
                        primary_key_column: loadType === 'full' ? '' : updated[tbl].primary_key_column,
                        timestamp_column: loadType === 'full' ? '' : updated[tbl].timestamp_column
                      };
                    }
                  });
                  updateFormData({ tableLoadConfigs: updated });
                };

                // Always show table format (even for single table)
                return (
                  <div style={{ marginTop: '16px' }}>
                    <p style={{ fontSize: '13px', color: '#666', marginBottom: '12px' }}>
                      Configure load settings for each table individually. {formData.loadType === 'incremental' ? 'Incremental loads only fetch changed rows based on the timestamp column.' : 'Full loads reload all data from source.'}
                    </p>
                    
                    {/* Clean Bulk Actions Bar */}
                    <div style={{
                      display: 'flex',
                      gap: '12px',
                      padding: '12px 16px',
                      background: '#F9FAFB',
                      border: '1px solid #E5E7EB',
                      borderRadius: '8px',
                      marginBottom: '16px',
                      alignItems: 'center'
                    }}>
                      <span style={{ fontSize: '12px', fontWeight: 600, color: '#6B7280', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                        Bulk Actions:
                      </span>
                      
                      <button
                        type="button"
                        onClick={() => handleSelectAllLoadType('incremental')}
                        style={{
                          padding: '6px 14px',
                          fontSize: '13px',
                          background: '#FFFFFF',
                          border: '1px solid #E5E7EB',
                          borderRadius: '6px',
                          cursor: 'pointer',
                          fontWeight: 500,
                          color: '#374151',
                          transition: 'all 0.2s',
                          boxShadow: '0 1px 2px rgba(0, 0, 0, 0.05)'
                        }}
                        onMouseOver={(e) => {
                          e.currentTarget.style.background = '#F9FAFB';
                          e.currentTarget.style.borderColor = '#3B82F6';
                          e.currentTarget.style.color = '#3B82F6';
                        }}
                        onMouseOut={(e) => {
                          e.currentTarget.style.background = '#FFFFFF';
                          e.currentTarget.style.borderColor = '#E5E7EB';
                          e.currentTarget.style.color = '#374151';
                        }}
                      >
                        Set All Incremental
                      </button>
                      
                      <button
                        type="button"
                        onClick={() => handleSelectAllLoadType('full')}
                        style={{
                          padding: '6px 14px',
                          fontSize: '13px',
                          background: '#FFFFFF',
                          border: '1px solid #E5E7EB',
                          borderRadius: '6px',
                          cursor: 'pointer',
                          fontWeight: 500,
                          color: '#374151',
                          transition: 'all 0.2s',
                          boxShadow: '0 1px 2px rgba(0, 0, 0, 0.05)'
                        }}
                        onMouseOver={(e) => {
                          e.currentTarget.style.background = '#F9FAFB';
                          e.currentTarget.style.borderColor = '#3B82F6';
                          e.currentTarget.style.color = '#3B82F6';
                        }}
                        onMouseOut={(e) => {
                          e.currentTarget.style.background = '#FFFFFF';
                          e.currentTarget.style.borderColor = '#E5E7EB';
                          e.currentTarget.style.color = '#374151';
                        }}
                      >
                        Set All Full
                      </button>
                      
                      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '12px', color: '#6B7280', fontWeight: 500 }}>Truncate All:</span>
                        <button
                          type="button"
                          onClick={() => handleSelectAllTruncate(true)}
                          style={{
                            padding: '5px 12px',
                            fontSize: '12px',
                            background: '#FFFFFF',
                            border: '1px solid #E5E7EB',
                            borderRadius: '6px',
                            cursor: 'pointer',
                            fontWeight: 500,
                            color: '#374151',
                            transition: 'all 0.2s',
                            boxShadow: '0 1px 2px rgba(0, 0, 0, 0.05)'
                          }}
                          onMouseOver={(e) => {
                            e.currentTarget.style.background = '#ECFDF5';
                            e.currentTarget.style.borderColor = '#10B981';
                            e.currentTarget.style.color = '#059669';
                          }}
                          onMouseOut={(e) => {
                            e.currentTarget.style.background = '#FFFFFF';
                            e.currentTarget.style.borderColor = '#E5E7EB';
                            e.currentTarget.style.color = '#374151';
                          }}
                        >
                          ON
                        </button>
                        <button
                          type="button"
                          onClick={() => handleSelectAllTruncate(false)}
                          style={{
                            padding: '5px 12px',
                            fontSize: '12px',
                            background: '#FFFFFF',
                            border: '1px solid #E5E7EB',
                            borderRadius: '6px',
                            cursor: 'pointer',
                            fontWeight: 500,
                            color: '#374151',
                            transition: 'all 0.2s',
                            boxShadow: '0 1px 2px rgba(0, 0, 0, 0.05)'
                          }}
                          onMouseOver={(e) => {
                            e.currentTarget.style.background = '#FEF2F2';
                            e.currentTarget.style.borderColor = '#EF4444';
                            e.currentTarget.style.color = '#DC2626';
                          }}
                          onMouseOut={(e) => {
                            e.currentTarget.style.background = '#FFFFFF';
                            e.currentTarget.style.borderColor = '#E5E7EB';
                            e.currentTarget.style.color = '#374151';
                          }}
                        >
                          OFF
                        </button>
                      </div>
                    </div>

                    <div style={{
                      border: '1px solid #E5E7EB',
                      borderRadius: '8px',
                      overflow: 'hidden',
                      background: '#fff',
                      boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)'
                    }}>
                      {/* Header */}
                      <div style={{
                        display: 'grid',
                        gridTemplateColumns: '1.3fr 130px 1.1fr 1.1fr 90px',
                        gap: '12px',
                        padding: '12px 16px',
                        background: '#F9FAFB',
                        borderBottom: '1px solid #E5E7EB',
                        fontSize: '11px',
                        fontWeight: 600,
                        color: '#6B7280',
                        textTransform: 'uppercase',
                        letterSpacing: '0.6px'
                      }}>
                        <span>TABLE</span>
                        <span>LOAD TYPE</span>
                        <span>PRIMARY KEY</span>
                        <span>TIMESTAMP COL</span>
                        <span style={{ textAlign: 'center' }}>TRUNCATE</span>
                      </div>
                      {/* Rows */}
                      {selectedTables.map((tbl: string, idx: number) => {
                        const tblConfig = configs[tbl] || { 
                          load_type: formData.loadType || 'full', 
                          primary_key_column: '', 
                          timestamp_column: '', 
                          truncate_before_load: false 
                        };
                        const isIncremental = tblConfig.load_type === 'incremental';
                        return (
                          <div key={tbl} style={{
                            display: 'grid',
                            gridTemplateColumns: '1.3fr 130px 1.1fr 1.1fr 90px',
                            gap: '12px',
                            padding: '12px 16px',
                            borderBottom: idx < selectedTables.length - 1 ? '1px solid #F3F4F6' : 'none',
                            alignItems: 'center',
                            background: '#fff',
                            transition: 'background 0.15s'
                          }}
                          onMouseEnter={(e) => e.currentTarget.style.background = '#F9FAFB'}
                          onMouseLeave={(e) => e.currentTarget.style.background = '#fff'}
                          >
                            <span style={{ 
                              fontSize: '14px', 
                              fontWeight: 500, 
                              color: '#111827', 
                              wordBreak: 'break-word'
                            }}>
                              {tbl}
                            </span>
                            
                            {/* Clean Modern Dropdown */}
                            <select
                              value={tblConfig.load_type || 'incremental'}
                              onChange={(e) => {
                                updateTableConfig(tbl, 'load_type', e.target.value);
                                if (e.target.value === 'full') {
                                  const updated = { ...configs };
                                  updated[tbl] = { 
                                    load_type: 'full', 
                                    primary_key_column: '', 
                                    timestamp_column: '', 
                                    truncate_before_load: updated[tbl]?.truncate_before_load || false 
                                  };
                                  updateFormData({ tableLoadConfigs: updated });
                                }
                              }}
                              style={{
                                padding: '8px 32px 8px 12px',
                                fontSize: '14px',
                                fontWeight: 400,
                                color: '#1F2937',
                                background: '#FFFFFF',
                                border: '1px solid #E5E7EB',
                                borderRadius: '6px',
                                cursor: 'pointer',
                                appearance: 'none',
                                backgroundImage: `url("data:image/svg+xml,%3Csvg width='12' height='8' viewBox='0 0 12 8' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 1.5L6 6.5L11 1.5' stroke='%236B7280' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E")`,
                                backgroundRepeat: 'no-repeat',
                                backgroundPosition: 'right 10px center',
                                transition: 'all 0.2s ease',
                                outline: 'none',
                                boxShadow: '0 1px 2px rgba(0, 0, 0, 0.05)'
                              }}
                              onFocus={(e) => {
                                e.currentTarget.style.borderColor = '#3B82F6';
                                e.currentTarget.style.boxShadow = '0 0 0 3px rgba(59, 130, 246, 0.1), 0 1px 2px rgba(0, 0, 0, 0.05)';
                              }}
                              onBlur={(e) => {
                                e.currentTarget.style.borderColor = '#E5E7EB';
                                e.currentTarget.style.boxShadow = '0 1px 2px rgba(0, 0, 0, 0.05)';
                              }}
                              onMouseEnter={(e) => {
                                if (document.activeElement !== e.currentTarget) {
                                  e.currentTarget.style.borderColor = '#D1D5DB';
                                }
                              }}
                              onMouseLeave={(e) => {
                                if (document.activeElement !== e.currentTarget) {
                                  e.currentTarget.style.borderColor = '#E5E7EB';
                                }
                              }}
                            >
                              <option value="incremental">Incremental</option>
                              <option value="full">Full</option>
                            </select>
                            
                            <Input
                              type="text"
                              placeholder={isIncremental ? 'id' : '—'}
                              value={tblConfig.primary_key_column || ''}
                              onChange={(e) => updateTableConfig(tbl, 'primary_key_column', e.target.value)}
                              disabled={!isIncremental}
                              style={{ 
                                padding: '8px 12px', 
                                fontSize: '14px', 
                                fontWeight: 400,
                                color: isIncremental ? '#1F2937' : '#9CA3AF',
                                background: isIncremental ? '#FFFFFF' : '#F9FAFB',
                                border: '1px solid #E5E7EB',
                                borderRadius: '6px',
                                transition: 'all 0.2s ease',
                                boxShadow: '0 1px 2px rgba(0, 0, 0, 0.05)'
                              } as any}
                            />
                            <Input
                              type="text"
                              placeholder={isIncremental ? 'updated_at' : '—'}
                              value={tblConfig.timestamp_column || ''}
                              onChange={(e) => updateTableConfig(tbl, 'timestamp_column', e.target.value)}
                              disabled={!isIncremental}
                              style={{ 
                                padding: '8px 12px', 
                                fontSize: '14px', 
                                fontWeight: 400,
                                color: isIncremental ? '#1F2937' : '#9CA3AF',
                                background: isIncremental ? '#FFFFFF' : '#F9FAFB',
                                border: '1px solid #E5E7EB',
                                borderRadius: '6px',
                                transition: 'all 0.2s ease',
                                boxShadow: '0 1px 2px rgba(0, 0, 0, 0.05)'
                              } as any}
                            />
                            <div style={{ display: 'flex', justifyContent: 'center' }}>
                              <Toggle
                                enabled={tblConfig.truncate_before_load || false}
                                onChange={(enabled) => updateTableConfig(tbl, 'truncate_before_load', enabled)}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })()}
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
        <p>{formData.targetDbType === 'clickhouse' ? 'Configure the 2-stage migration process: BigQuery → GCS → ClickHouse' : 'Configure the 3-stage migration process: BigQuery → GCS → S3 → Redshift'}</p>
      </div>

      <div className="step-content migration-details-collapsible">
        {saveError && (
          <div style={{
            padding: '10px 16px',
            marginBottom: '12px',
            borderRadius: '8px',
            background: '#fef2f2',
            border: '1px solid #fecaca',
            color: '#dc2626',
            fontSize: '14px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="8" cy="8" r="6" />
              <path d="M6 6l4 4M10 6l-4 4" strokeLinecap="round" />
            </svg>
            {saveError}
          </div>
        )}
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

            {/* Stage 2: GCS to ClickHouse (ClickHouse target) */}
            {formData.targetDbType === 'clickhouse' && renderGCSToClickHouse()}

            {/* Stage 2: GCS to S3 (Pathway-specific, non-ClickHouse targets) */}
            {formData.targetDbType !== 'clickhouse' && pathway === 'A' && renderGCSToS3_PathA()}
            {formData.targetDbType !== 'clickhouse' && pathway === 'B' && renderGCSToS3_PathB()}
            {formData.targetDbType !== 'clickhouse' && pathway === 'C' && renderGCSToS3_PathC()}
            {formData.targetDbType !== 'clickhouse' && pathway === 'D' && renderGCSToS3_PathD()}

            {/* Stage 3: S3 to Redshift (non-ClickHouse targets only) */}
            {formData.targetDbType !== 'clickhouse' && renderS3ToRedshift()}
          </>
        )}
      </div>
    </div>
  );
};
