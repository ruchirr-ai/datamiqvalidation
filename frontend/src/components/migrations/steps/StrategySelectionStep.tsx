import React from 'react';
import './StepStyles.css';
import './StrategySelectionStep.css';

interface StrategySelectionStepProps {
  formData: any;
  updateFormData: (updates: any) => void;
  isEditMode?: boolean;
}

interface PathwayOption {
  id: 'A' | 'B' | 'C';
  name: string;
  tag: string;
  tagColor: string;
  description: string;
  flow: string;
  pros: string[];
  cons: string[];
  bestFor: string;
}

const PATHWAYS: PathwayOption[] = [
  {
    id: 'A',
    name: 'AWS Native (SCT)',
    tag: 'Schema Conversion',
    tagColor: 'primary',
    description: 'Automated schema conversion and data migration using AWS Schema Conversion Tool',
    flow: 'BigQuery → AWS SCT → Redshift',
    pros: [
      'Automated schema conversion and assessment',
      'Built-in data extraction agents',
      'Migration complexity analysis',
      'Optimization recommendations',
    ],
    cons: [
      'Requires AWS SCT installation and setup',
      'May need manual schema adjustments',
    ],
    bestFor: 'Complex schema migrations requiring automated conversion and assessment',
  },
  {
    id: 'B',
    name: 'AWS DataSync',
    tag: 'Recommended for Large Scale',
    tagColor: 'success',
    description: 'Managed cross-cloud transfer using AWS DataSync',
    flow: 'BigQuery → GCS → AWS DataSync → S3 → Redshift',
    pros: [
      'Managed data transfer service',
      'No agent required for GCS to S3',
      'Automatic encryption and validation',
      'CloudWatch monitoring and logging',
    ],
    cons: [
      'Requires HMAC key setup for GCS',
      'Additional AWS DataSync costs',
    ],
    bestFor: 'Large-scale migrations (TB to PB) with managed service preference',
  },
  {
    id: 'C',
    name: 'CLI/Legacy',
    tag: 'Maximum Control',
    tagColor: 'default',
    description: 'Command-line tools for maximum control and flexibility',
    flow: 'BigQuery → GCS → gsutil/aws cli → S3 → Redshift',
    pros: [
      'Maximum control and flexibility',
      'No additional AWS services required',
      'Compatible with legacy systems',
      'Cost-effective approach',
    ],
    cons: [
      'Manual orchestration required',
      'Requires CLI tools installation',
      'More maintenance overhead',
    ],
    bestFor: 'Small-scale migrations or custom orchestration requirements',
  },
];

const CLICKHOUSE_PATHWAYS: PathwayOption[] = [
  {
    id: 'A',
    name: 'GCS Export + s3Cluster',
    tag: 'Recommended',
    tagColor: 'success',
    description: 'Export BigQuery tables to GCS as Parquet, then import into ClickHouse using the s3() table function',
    flow: 'BigQuery → GCS (Parquet) → ClickHouse s3()',
    pros: [
      'Simple and reliable — no middleware needed',
      'Parallel import via s3Cluster for multi-node',
      'Parquet preserves column types',
      'Free GCS export (up to 50TB/day)',
    ],
    cons: [
      'Requires GCS HMAC keys for ClickHouse access',
      'Intermediate storage in GCS',
    ],
    bestFor: 'All migration sizes — recommended default approach',
  },
  {
    id: 'B',
    name: 'AWS Glue ETL',
    tag: 'Coming Soon',
    tagColor: 'default',
    description: 'Use AWS Glue to read from BigQuery and write to ClickHouse via JDBC',
    flow: 'BigQuery → AWS Glue (ETL) → ClickHouse',
    pros: [
      'Managed ETL service',
      'Built-in transformations',
      'Good for complex data reshaping',
    ],
    cons: [
      'Requires ClickHouse on AWS',
      'JDBC overhead — slower than file-based',
      'Additional Glue costs',
    ],
    bestFor: 'When ClickHouse is on AWS and transformations are needed',
  },
];

export const StrategySelectionStep: React.FC<StrategySelectionStepProps> = ({
  formData,
  updateFormData,
  isEditMode = false,
}) => {
  const getEstimatedStats = () => {
    // Calculate based on selected tables
    const tableCount = formData.selectedTables.length;
    // Placeholder calculations - would be based on actual metadata
    const estimatedVolume = tableCount * 50; // GB
    const estimatedDuration = Math.ceil(estimatedVolume / 10); // hours
    
    return {
      tableCount,
      estimatedVolume,
      estimatedDuration,
    };
  };

  const getRecommendedPathway = (volumeGB: number): 'A' | 'B' | 'C' => {
    if (volumeGB > 1000) return 'B';  // 1TB+ - AWS DataSync
    if (volumeGB > 100) return 'A';   // 100GB+ - AWS DMS
    return 'C';                        // < 100GB - CLI
  };

  const stats = getEstimatedStats();
  const pathways = formData.targetDbType === 'clickhouse' ? CLICKHOUSE_PATHWAYS : PATHWAYS;

  return (
    <div className="step-container">
      <div className="step-header">
        <h2>Select Migration Strategy</h2>
        <p>Choose the best pathway for your migration based on data volume and requirements</p>
      </div>

      <div className="step-content">
        {/* Read-only notice for edit mode */}
        {isEditMode && (
          <div className="info-box" style={{ marginBottom: '16px' }}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="8" cy="8" r="6" />
              <path d="M8 6v4M8 11h.01" strokeLinecap="round" />
            </svg>
            <div>
              <strong>Migration Strategy (Read-Only)</strong>
              <p>The migration pathway cannot be changed after creation. The selected strategy is displayed below.</p>
            </div>
          </div>
        )}

        {/* Pathway Options */}
        <div className="pathway-grid">
          {pathways.map(pathway => {
            const isSelected = formData.pathway === pathway.id;

            return (
              <div
                key={pathway.id}
                className={`pathway-card ${isSelected ? 'selected' : ''} ${isEditMode ? 'disabled' : ''}`}
                onClick={() => !isEditMode && updateFormData({ pathway: pathway.id })}
                style={{ cursor: isEditMode ? 'not-allowed' : 'pointer', opacity: isEditMode && !isSelected ? 0.6 : 1 }}
              >
                <div className="pathway-header">
                  <div className="pathway-radio">
                    <input
                      type="radio"
                      name="pathway"
                      checked={isSelected}
                      onChange={() => !isEditMode && updateFormData({ pathway: pathway.id })}
                      disabled={isEditMode}
                    />
                  </div>
                  <div className="pathway-info">
                    <div className="pathway-title">
                      <span className="pathway-id">Path {pathway.id}</span>
                      <span className="pathway-name">{pathway.name}</span>
                    </div>
                    <div className={`pathway-tag tag-${pathway.tagColor}`}>
                      {pathway.tag}
                    </div>
                  </div>
                </div>

                <div className="pathway-flow">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M2 8h12M10 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <span>{pathway.flow}</span>
                </div>

                <div className="pathway-details">
                  <div className="detail-section">
                    <h4>Considerations</h4>
                    <ul>
                      {pathway.cons.map((con, idx) => (
                        <li key={idx}>
                          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                            <circle cx="8" cy="8" r="6" />
                            <path d="M8 5v3M8 11h.01" strokeLinecap="round" />
                          </svg>
                          {con}
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className="best-for">
                    <strong>Best for:</strong> {pathway.bestFor}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="info-box">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="8" cy="8" r="6" />
            <path d="M8 6v4M8 11h.01" strokeLinecap="round" />
          </svg>
          <div>
            <strong>Need help choosing?</strong>
            <p>
              The recommended pathway is based on your data volume and migration requirements.
              All pathways support checkpointing and resumption for reliability.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
