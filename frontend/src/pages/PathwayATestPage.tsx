import React, { useState, useEffect } from 'react';
import { Button, Input, Select, Card, Alert } from '../components/ui';
import { api } from '../services/api';
import './PathwayATestPage.css';

interface Connection {
  id: number;
  name: string;
  type: string;
  database: string;
}

interface TestResult {
  success: boolean;
  step: string;
  message: string;
  details: any;
  duration_seconds: number;
  timestamp: string;
}

export const PathwayATestPage: React.FC = () => {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [loading, setLoading] = useState(false);
  
  // Step 1: BigQuery to GCS
  const [step1Data, setStep1Data] = useState({
    source_connection_id: '',
    project_id: '',
    dataset: '',
    table: '',
    gcs_bucket: '',
    gcs_path: 'migrations/test'
  });
  const [step1Result, setStep1Result] = useState<TestResult | null>(null);
  
  // Step 2: GCS to S3
  const [step2Data, setStep2Data] = useState({
    gcs_bucket: '',
    gcs_path: 'migrations/test',
    s3_bucket: '',
    s3_path: 'migrations/test',
    aws_access_key_id: '',
    aws_secret_access_key: ''
  });
  const [step2Result, setStep2Result] = useState<TestResult | null>(null);
  
  // Step 3: S3 to Redshift
  const [step3Data, setStep3Data] = useState({
    target_connection_id: '',
    s3_bucket: '',
    s3_path: 'migrations/test',
    table_name: '',
    schema: 'public',
    iam_role: ''
  });
  const [step3Result, setStep3Result] = useState<TestResult | null>(null);

  useEffect(() => {
    fetchConnections();
  }, []);

  const fetchConnections = async () => {
    try {
      const data = await api.get<Connection[]>('/api/connections/list');
      setConnections(data);
    } catch (error) {
      console.error('Failed to fetch connections:', error);
    }
  };

  const testStep1 = async () => {
    setLoading(true);
    setStep1Result(null);
    
    try {
      const result = await api.post<TestResult>(
        '/api/migrations/pathway-a/test/step1-bigquery-to-gcs',
        {
          source_connection_id: parseInt(step1Data.source_connection_id),
          project_id: step1Data.project_id,
          dataset: step1Data.dataset,
          table: step1Data.table,
          gcs_bucket: step1Data.gcs_bucket,
          gcs_path: step1Data.gcs_path
        }
      );
      setStep1Result(result);
      
      // Auto-populate step 2 if successful
      if (result.success) {
        setStep2Data(prev => ({
          ...prev,
          gcs_bucket: step1Data.gcs_bucket,
          gcs_path: step1Data.gcs_path
        }));
      }
    } catch (error: any) {
      setStep1Result({
        success: false,
        step: 'bigquery_to_gcs',
        message: error.message || 'Test failed',
        details: { error: error.message },
        duration_seconds: 0,
        timestamp: new Date().toISOString()
      });
    } finally {
      setLoading(false);
    }
  };

  const testStep2 = async () => {
    setLoading(true);
    setStep2Result(null);
    
    try {
      const result = await api.post<TestResult>(
        '/api/migrations/pathway-a/test/step2-gcs-to-s3',
        step2Data
      );
      setStep2Result(result);
      
      // Auto-populate step 3 if successful
      if (result.success) {
        setStep3Data(prev => ({
          ...prev,
          s3_bucket: step2Data.s3_bucket,
          s3_path: step2Data.s3_path,
          table_name: step1Data.table
        }));
      }
    } catch (error: any) {
      setStep2Result({
        success: false,
        step: 'gcs_to_s3',
        message: error.message || 'Test failed',
        details: { error: error.message },
        duration_seconds: 0,
        timestamp: new Date().toISOString()
      });
    } finally {
      setLoading(false);
    }
  };

  const testStep3 = async () => {
    setLoading(true);
    setStep3Result(null);
    
    try {
      const result = await api.post<TestResult>(
        '/api/migrations/pathway-a/test/step3-s3-to-redshift',
        {
          target_connection_id: parseInt(step3Data.target_connection_id),
          s3_bucket: step3Data.s3_bucket,
          s3_path: step3Data.s3_path,
          table_name: step3Data.table_name,
          schema: step3Data.schema,
          iam_role: step3Data.iam_role || undefined
        }
      );
      setStep3Result(result);
    } catch (error: any) {
      setStep3Result({
        success: false,
        step: 's3_to_redshift',
        message: error.message || 'Test failed',
        details: { error: error.message },
        duration_seconds: 0,
        timestamp: new Date().toISOString()
      });
    } finally {
      setLoading(false);
    }
  };

  const bigqueryConnections = connections.filter(c => c.database.toLowerCase() === 'bigquery');
  const redshiftConnections = connections.filter(c => c.database.toLowerCase() === 'redshift');

  return (
    <div className="pathway-test-page">
      <div className="page-header">
        <h1>Pathway A Testing</h1>
        <p>Test each step of the BigQuery → GCS → S3 → Redshift migration</p>
      </div>

      <div className="test-steps">
        {/* Step 1: BigQuery to GCS */}
        <Card className="test-step-card">
          <div className="step-header">
            <div className="step-number">1</div>
            <div className="step-info">
              <h2>BigQuery to GCS Export</h2>
              <p>Export BigQuery table to Google Cloud Storage in AVRO format</p>
            </div>
          </div>

          <div className="step-form">
            <div className="form-row">
              <div className="form-field">
                <label>BigQuery Connection</label>
                <Select
                  value={step1Data.source_connection_id}
                  onChange={(e) => setStep1Data({ ...step1Data, source_connection_id: e.target.value })}
                >
                  <option value="">Select connection...</option>
                  {bigqueryConnections.map(conn => (
                    <option key={conn.id} value={conn.id}>
                      {conn.name} ({conn.database})
                    </option>
                  ))}
                </Select>
              </div>

              <div className="form-field">
                <label>Project ID</label>
                <Input
                  value={step1Data.project_id}
                  onChange={(e) => setStep1Data({ ...step1Data, project_id: e.target.value })}
                  placeholder="assessiq-484512"
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-field">
                <label>Dataset</label>
                <Input
                  value={step1Data.dataset}
                  onChange={(e) => setStep1Data({ ...step1Data, dataset: e.target.value })}
                  placeholder="sales_analytics"
                />
              </div>

              <div className="form-field">
                <label>Table</label>
                <Input
                  value={step1Data.table}
                  onChange={(e) => setStep1Data({ ...step1Data, table: e.target.value })}
                  placeholder="customers_tbl"
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-field">
                <label>GCS Bucket</label>
                <Input
                  value={step1Data.gcs_bucket}
                  onChange={(e) => setStep1Data({ ...step1Data, gcs_bucket: e.target.value })}
                  placeholder="my-migration-bucket"
                />
              </div>

              <div className="form-field">
                <label>GCS Path</label>
                <Input
                  value={step1Data.gcs_path}
                  onChange={(e) => setStep1Data({ ...step1Data, gcs_path: e.target.value })}
                  placeholder="migrations/test"
                />
              </div>
            </div>

            <Button
              onClick={testStep1}
              disabled={loading || !step1Data.source_connection_id || !step1Data.project_id || !step1Data.dataset || !step1Data.table || !step1Data.gcs_bucket}
            >
              {loading ? 'Testing...' : 'Test Step 1'}
            </Button>
          </div>

          {step1Result && (
            <TestResultDisplay result={step1Result} />
          )}
        </Card>

        {/* Step 2: GCS to S3 */}
        <Card className="test-step-card">
          <div className="step-header">
            <div className="step-number">2</div>
            <div className="step-info">
              <h2>GCS to S3 Transfer</h2>
              <p>Transfer files from GCS to S3 using Storage Transfer Service</p>
            </div>
          </div>

          <div className="step-form">
            <div className="form-row">
              <div className="form-field">
                <label>GCS Bucket</label>
                <Input
                  value={step2Data.gcs_bucket}
                  onChange={(e) => setStep2Data({ ...step2Data, gcs_bucket: e.target.value })}
                  placeholder="my-migration-bucket"
                />
              </div>

              <div className="form-field">
                <label>GCS Path</label>
                <Input
                  value={step2Data.gcs_path}
                  onChange={(e) => setStep2Data({ ...step2Data, gcs_path: e.target.value })}
                  placeholder="migrations/test"
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-field">
                <label>S3 Bucket</label>
                <Input
                  value={step2Data.s3_bucket}
                  onChange={(e) => setStep2Data({ ...step2Data, s3_bucket: e.target.value })}
                  placeholder="my-migration-bucket"
                />
              </div>

              <div className="form-field">
                <label>S3 Path</label>
                <Input
                  value={step2Data.s3_path}
                  onChange={(e) => setStep2Data({ ...step2Data, s3_path: e.target.value })}
                  placeholder="migrations/test"
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-field">
                <label>AWS Access Key ID (Optional)</label>
                <Input
                  type="password"
                  value={step2Data.aws_access_key_id}
                  onChange={(e) => setStep2Data({ ...step2Data, aws_access_key_id: e.target.value })}
                  placeholder="Leave empty to use default credentials"
                />
              </div>

              <div className="form-field">
                <label>AWS Secret Access Key (Optional)</label>
                <Input
                  type="password"
                  value={step2Data.aws_secret_access_key}
                  onChange={(e) => setStep2Data({ ...step2Data, aws_secret_access_key: e.target.value })}
                  placeholder="Leave empty to use default credentials"
                />
              </div>
            </div>

            <Button
              onClick={testStep2}
              disabled={loading || !step2Data.gcs_bucket || !step2Data.s3_bucket}
            >
              {loading ? 'Testing...' : 'Test Step 2'}
            </Button>
          </div>

          {step2Result && (
            <TestResultDisplay result={step2Result} />
          )}
        </Card>

        {/* Step 3: S3 to Redshift */}
        <Card className="test-step-card">
          <div className="step-header">
            <div className="step-number">3</div>
            <div className="step-info">
              <h2>S3 to Redshift Load</h2>
              <p>Load data from S3 to Redshift using COPY command</p>
            </div>
          </div>

          <div className="step-form">
            <div className="form-row">
              <div className="form-field">
                <label>Redshift Connection</label>
                <Select
                  value={step3Data.target_connection_id}
                  onChange={(e) => setStep3Data({ ...step3Data, target_connection_id: e.target.value })}
                >
                  <option value="">Select connection...</option>
                  {redshiftConnections.map(conn => (
                    <option key={conn.id} value={conn.id}>
                      {conn.name} ({conn.database})
                    </option>
                  ))}
                </Select>
              </div>

              <div className="form-field">
                <label>Table Name</label>
                <Input
                  value={step3Data.table_name}
                  onChange={(e) => setStep3Data({ ...step3Data, table_name: e.target.value })}
                  placeholder="customers_tbl"
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-field">
                <label>S3 Bucket</label>
                <Input
                  value={step3Data.s3_bucket}
                  onChange={(e) => setStep3Data({ ...step3Data, s3_bucket: e.target.value })}
                  placeholder="my-migration-bucket"
                />
              </div>

              <div className="form-field">
                <label>S3 Path</label>
                <Input
                  value={step3Data.s3_path}
                  onChange={(e) => setStep3Data({ ...step3Data, s3_path: e.target.value })}
                  placeholder="migrations/test"
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-field">
                <label>Schema</label>
                <Input
                  value={step3Data.schema}
                  onChange={(e) => setStep3Data({ ...step3Data, schema: e.target.value })}
                  placeholder="public"
                />
              </div>

              <div className="form-field">
                <label>IAM Role (Optional)</label>
                <Input
                  value={step3Data.iam_role}
                  onChange={(e) => setStep3Data({ ...step3Data, iam_role: e.target.value })}
                  placeholder="arn:aws:iam::123456789012:role/RedshiftCopyRole"
                />
              </div>
            </div>

            <Button
              onClick={testStep3}
              disabled={loading || !step3Data.target_connection_id || !step3Data.s3_bucket || !step3Data.table_name}
            >
              {loading ? 'Testing...' : 'Test Step 3'}
            </Button>
          </div>

          {step3Result && (
            <TestResultDisplay result={step3Result} />
          )}
        </Card>
      </div>
    </div>
  );
};

const TestResultDisplay: React.FC<{ result: TestResult }> = ({ result }) => {
  return (
    <div className="test-result">
      <Alert variant={result.success ? 'success' : 'error'}>
        <div className="result-header">
          <span className="result-status">
            {result.success ? '✓ Success' : '✗ Failed'}
          </span>
          <span className="result-duration">
            {result.duration_seconds.toFixed(2)}s
          </span>
        </div>
        <div className="result-message">{result.message}</div>
      </Alert>

      {result.details && Object.keys(result.details).length > 0 && (
        <div className="result-details">
          <h4>Details:</h4>
          <pre>{JSON.stringify(result.details, null, 2)}</pre>
        </div>
      )}
    </div>
  );
};
