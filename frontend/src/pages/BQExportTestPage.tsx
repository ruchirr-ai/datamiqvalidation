import React, { useState, useEffect } from 'react';
import { Button, Select, Input } from '../components/ui';
import { api } from '../services/api';
import './PathwayATestPage.css';

interface Connection {
  id: number;
  name: string;
  database: string;
}

interface ExportFormat {
  value: string;
  label: string;
  description: string;
  compression: string[];
}

interface ExportResult {
  success: boolean;
  message: string;
  job_id?: string;
  destination_uris?: string[];
  rows_exported?: number;
  bytes_exported?: number;
  files_created?: number;
  duration_seconds?: number;
  error?: string;
}

export const BQExportTestPage: React.FC = () => {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [formats, setFormats] = useState<ExportFormat[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ExportResult | null>(null);
  
  const [formData, setFormData] = useState({
    connection_id: '',
    project_id: 'assessiq-484512',
    dataset: 'sales_analytics',
    table: 'assess_tbl',
    gcs_bucket: 'my-gcs-staging-bucket',
    gcs_path: '/exports',
    export_format: 'AVRO',
    compression: 'SNAPPY'
  });

  useEffect(() => {
    fetchConnections();
    fetchFormats();
  }, []);

  const fetchConnections = async () => {
    try {
      const token = localStorage.getItem('auth_token') || localStorage.getItem('access_token');
      const response = await fetch('/api/connections/list', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      const data = await response.json();
      const bqConnections = data.filter((c: Connection) => c.database.toLowerCase() === 'bigquery');
      setConnections(bqConnections);
      
      if (bqConnections.length > 0) {
        setFormData(prev => ({ ...prev, connection_id: bqConnections[0].id.toString() }));
      }
    } catch (error) {
      console.error('Failed to fetch connections:', error);
    }
  };

  const fetchFormats = async () => {
    try {
      const token = localStorage.getItem('auth_token') || localStorage.getItem('access_token');
      const response = await fetch('/api/bq-export-test/formats', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      const data = await response.json();
      setFormats(data.formats);
    } catch (error) {
      console.error('Failed to fetch formats:', error);
    }
  };

  const handleExport = async () => {
    setLoading(true);
    setResult(null);

    try {
      const token = localStorage.getItem('auth_token') || localStorage.getItem('access_token');
      const response = await fetch('/api/bq-export-test/export', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          connection_id: parseInt(formData.connection_id),
          project_id: formData.project_id,
          dataset: formData.dataset,
          table: formData.table,
          gcs_bucket: formData.gcs_bucket,
          gcs_path: formData.gcs_path,
          export_format: formData.export_format,
          compression: formData.compression === 'None' ? null : formData.compression
        })
      });

      const data = await response.json();
      setResult(data);
    } catch (error: any) {
      setResult({
        success: false,
        message: 'Export failed',
        error: error.message
      });
    } finally {
      setLoading(false);
    }
  };

  const formatBytes = (bytes?: number) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
  };

  const selectedFormat = formats.find(f => f.value === formData.export_format);

  return (
    <div className="pathway-test-page">
      <div className="test-header">
        <h1>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
            <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
            <line x1="12" y1="22.08" x2="12" y2="12" />
          </svg>
          BigQuery to GCS Export Test
        </h1>
        <p>Test exporting BigQuery tables to Google Cloud Storage with production data</p>
      </div>

      <div className="test-container">
        <div className="test-step">
          <div className="step-header">
            <div className="step-number">1</div>
            <div className="step-info">
              <h3>BigQuery Source Configuration</h3>
              <p>Select the BigQuery connection and table to export</p>
            </div>
          </div>

          <div className="step-content">
            <div className="form-grid">
              <div className="form-group">
                <label>BigQuery Connection *</label>
                <select
                  className="form-input"
                  value={formData.connection_id}
                  onChange={(e) => setFormData({ ...formData, connection_id: e.target.value })}
                >
                  <option value="">Select connection...</option>
                  {connections.map(conn => (
                    <option key={conn.id} value={conn.id}>
                      {conn.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Project ID *</label>
                <Input
                  type="text"
                  value={formData.project_id}
                  onChange={(e) => setFormData({ ...formData, project_id: e.target.value })}
                  placeholder="my-gcp-project"
                />
              </div>

              <div className="form-group">
                <label>Dataset *</label>
                <Input
                  type="text"
                  value={formData.dataset}
                  onChange={(e) => setFormData({ ...formData, dataset: e.target.value })}
                  placeholder="my_dataset"
                />
              </div>

              <div className="form-group">
                <label>Table *</label>
                <Input
                  type="text"
                  value={formData.table}
                  onChange={(e) => setFormData({ ...formData, table: e.target.value })}
                  placeholder="my_table"
                />
              </div>
            </div>

            <div className="info-box">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="8" cy="8" r="6" />
                <path d="M8 6v4M8 11h.01" strokeLinecap="round" />
              </svg>
              <div>
                <strong>Table Reference</strong>
                <p>Full table path: {formData.project_id}.{formData.dataset}.{formData.table}</p>
              </div>
            </div>
          </div>
        </div>

        <div className="test-step">
          <div className="step-header">
            <div className="step-number">2</div>
            <div className="step-info">
              <h3>GCS Destination Configuration</h3>
              <p>Configure where to export the data in Google Cloud Storage</p>
            </div>
          </div>

          <div className="step-content">
            <div className="form-grid">
              <div className="form-group">
                <label>GCS Bucket *</label>
                <Input
                  type="text"
                  value={formData.gcs_bucket}
                  onChange={(e) => setFormData({ ...formData, gcs_bucket: e.target.value })}
                  placeholder="my-gcs-bucket"
                />
                <p className="form-help">Bucket name without gs:// prefix</p>
              </div>

              <div className="form-group">
                <label>GCS Path</label>
                <Input
                  type="text"
                  value={formData.gcs_path}
                  onChange={(e) => setFormData({ ...formData, gcs_path: e.target.value })}
                  placeholder="/exports"
                />
                <p className="form-help">Path within the bucket (default: /exports)</p>
              </div>
            </div>

            <div className="info-box">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="8" cy="8" r="6" />
                <path d="M8 6v4M8 11h.01" strokeLinecap="round" />
              </svg>
              <div>
                <strong>Destination URI</strong>
                <p>gs://{formData.gcs_bucket}{formData.gcs_path}/{formData.table}_*.{formData.export_format.toLowerCase()}</p>
              </div>
            </div>
          </div>
        </div>

        <div className="test-step">
          <div className="step-header">
            <div className="step-number">3</div>
            <div className="step-info">
              <h3>Export Format & Compression</h3>
              <p>Choose the export format and compression method</p>
            </div>
          </div>

          <div className="step-content">
            <div className="form-grid">
              <div className="form-group">
                <label>Export Format *</label>
                <select
                  className="form-input"
                  value={formData.export_format}
                  onChange={(e) => setFormData({ ...formData, export_format: e.target.value, compression: 'None' })}
                >
                  {formats.map(format => (
                    <option key={format.value} value={format.value}>
                      {format.label}
                    </option>
                  ))}
                </select>
                {selectedFormat && (
                  <p className="form-help">{selectedFormat.description}</p>
                )}
              </div>

              <div className="form-group">
                <label>Compression</label>
                <select
                  className="form-input"
                  value={formData.compression}
                  onChange={(e) => setFormData({ ...formData, compression: e.target.value })}
                >
                  <option value="None">None</option>
                  {selectedFormat?.compression.filter(c => c !== 'None').map(comp => (
                    <option key={comp} value={comp}>{comp}</option>
                  ))}
                </select>
                <p className="form-help">
                  {formData.compression === 'None' ? 'No compression (faster export)' :
                   formData.compression === 'GZIP' ? 'Good compression ratio, slower' :
                   formData.compression === 'SNAPPY' ? 'Fast compression, larger files' :
                   formData.compression === 'DEFLATE' ? 'Balanced compression' : ''}
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="test-actions">
          <Button
            variant="primary"
            onClick={handleExport}
            disabled={loading || !formData.connection_id}
          >
            {loading ? 'Exporting...' : 'Start Export'}
          </Button>
        </div>

        {result && (
          <div className={`test-result ${result.success ? 'success' : 'error'}`}>
            <div className="result-header">
              {result.success ? (
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M9 12l2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              ) : (
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M15 9l-6 6M9 9l6 6" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
              <h3>{result.success ? 'Export Successful!' : 'Export Failed'}</h3>
            </div>

            <div className="result-content">
              <p className="result-message">{result.message}</p>

              {result.success && (
                <>
                  <div className="result-stats">
                    <div className="stat">
                      <span className="stat-label">Rows Exported</span>
                      <span className="stat-value">{result.rows_exported?.toLocaleString()}</span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">Data Size</span>
                      <span className="stat-value">{formatBytes(result.bytes_exported)}</span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">Files Created</span>
                      <span className="stat-value">~{result.files_created}</span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">Duration</span>
                      <span className="stat-value">{result.duration_seconds}s</span>
                    </div>
                  </div>

                  {result.job_id && (
                    <div className="result-detail">
                      <strong>Job ID:</strong>
                      <code>{result.job_id}</code>
                    </div>
                  )}

                  {result.destination_uris && result.destination_uris.length > 0 && (
                    <div className="result-detail">
                      <strong>Destination Files:</strong>
                      {result.destination_uris.map((uri, idx) => (
                        <code key={idx}>{uri}</code>
                      ))}
                    </div>
                  )}

                  <div className="success-box">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M13 4L6 11l-3-3" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    <div>
                      <strong>Next Steps</strong>
                      <p>Data has been exported to GCS. You can now:</p>
                      <ul>
                        <li>Verify files in GCS bucket: gs://{formData.gcs_bucket}{formData.gcs_path}/</li>
                        <li>GCS to S3 transfer available via Path C migration</li>
                        <li>S3 to Redshift load fully implemented with RedshiftLoader</li>
                      </ul>
                    </div>
                  </div>
                </>
              )}

              {result.error && (
                <div className="error-box">
                  <strong>Error Details:</strong>
                  <pre>{result.error}</pre>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
