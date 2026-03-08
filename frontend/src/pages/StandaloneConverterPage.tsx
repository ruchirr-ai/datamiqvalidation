/**
 * Quick Convert Page (formerly Standalone Converter)
 *
 * Provides an ad-hoc SQL/code conversion interface powered by AWS Bedrock LLM
 * with optional sqlGLOT pre-processing. Users can paste source code, configure
 * conversion parameters, and view side-by-side results.
 *
 * Requirements: 2.1, 2.3, 3.1, 3.2, 3.6, 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 6.1, 7.1, 8.1, 8.2, 8.3, 8.6
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Card, Button, Alert, Toggle } from '../components/ui';
import { CodePane } from '../components/conversion/CodePane';
import { ConversionHistoryTable } from '../components/conversion/ConversionHistoryTable';
import {
  createStandaloneConversion,
  listBedrockModels,
  listPromptTemplates,
  BedrockModel,
  PromptTemplate,
  ConversionJob,
  StandaloneConversionRequest,
} from '../services/conversionApi';
import './StandaloneConverterPage.css';

/** Restricted source dialect options (Req 3.1) */
const SOURCE_DIALECT_OPTIONS = ['BigQuery', 'SQL Server', 'Redshift'];

/** Restricted target dialect options (Req 3.2) */
const TARGET_DIALECT_OPTIONS = ['Redshift', 'SQL Server', 'BigQuery'];

/** Asset type options with QUERY first/default (Req 5.1, 5.2) */
const ASSET_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: 'QUERY', label: 'Query' },
  { value: 'TABLE_DDL', label: 'Table DDL' },
  { value: 'STORED_PROCEDURE', label: 'Stored Procedure' },
  { value: 'FUNCTION', label: 'Function' },
  { value: 'VIEW', label: 'View' },
  { value: 'MATERIALIZED_VIEW', label: 'Materialized View' },
];

/** Accepted file extensions for local file upload (Req 8.2) */
const ACCEPTED_FILE_EXTENSIONS = ['.txt', '.sql', '.csv', '.json', '.xml'];
const ACCEPTED_FILE_TYPES = ACCEPTED_FILE_EXTENSIONS.join(',');
const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024; // 5 MB

export const StandaloneConverterPage: React.FC = () => {
  // --- Form state ---
  const [sourceDialect, setSourceDialect] = useState(SOURCE_DIALECT_OPTIONS[0]);
  const [targetDialect, setTargetDialect] = useState(TARGET_DIALECT_OPTIONS[0]);
  const [assetType, setAssetType] = useState('QUERY');
  const [assetName, setAssetName] = useState('Untitled Conversion');
  const [awsRegion, setAwsRegion] = useState('us-east-1');
  const [bedrockModel, setBedrockModel] = useState('');
  const [promptTemplatePath, setPromptTemplatePath] = useState('');
  const [customTemplatePath, setCustomTemplatePath] = useState('');
  const [showCustomInput, setShowCustomInput] = useState(false);
  const [maxRetries, setMaxRetries] = useState(3);
  const [useSqlglot, setUseSqlglot] = useState(false);
  const [sourceCode, setSourceCode] = useState('');

  // --- File upload state (Req 8.1, 8.2, 8.3, 8.6) ---
  const [uploadedFile, setUploadedFile] = useState<{ name: string; content: string } | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // --- UI state ---
  const [models, setModels] = useState<BedrockModel[]>([]);
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [converting, setConverting] = useState(false);
  const [result, setResult] = useState<ConversionJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [historyRefreshToken, setHistoryRefreshToken] = useState(0);
  const [showTooltip, setShowTooltip] = useState(false);

  // --- Load prompt templates on mount ---
  useEffect(() => {
    const fetchTemplates = async () => {
      try {
        setTemplatesLoading(true);
        const data = await listPromptTemplates();
        setTemplates(data);
        if (data.length > 0 && !promptTemplatePath) {
          setPromptTemplatePath(data[0].path);
        }
      } catch (err) {
        console.error('Failed to load templates:', err);
        setTemplates([]);
      } finally {
        setTemplatesLoading(false);
      }
    };
    fetchTemplates();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // --- Load Bedrock models when region changes ---
  const fetchModels = useCallback(async (region: string) => {
    if (!region.trim()) return;
    try {
      setModelsLoading(true);
      const data = await listBedrockModels(region);
      setModels(data);
      if (data.length > 0 && !bedrockModel) {
        setBedrockModel(data[0].model_id);
      }
    } catch {
      setModels([]);
    } finally {
      setModelsLoading(false);
    }
  }, [bedrockModel]);

  useEffect(() => {
    fetchModels(awsRegion);
  }, [awsRegion]); // eslint-disable-line react-hooks/exhaustive-deps

  // --- File upload handler (Req 8.2, 8.3) ---
  const handleFileUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setFileError(null);
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate extension
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ACCEPTED_FILE_EXTENSIONS.includes(ext)) {
      setFileError(`Invalid file type. Accepted: ${ACCEPTED_FILE_EXTENSIONS.join(', ')}`);
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    // Validate size
    if (file.size > MAX_FILE_SIZE_BYTES) {
      setFileError('File exceeds maximum size of 5 MB.');
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      setUploadedFile({ name: file.name, content });
    };
    reader.onerror = () => {
      setFileError('Failed to read file.');
    };
    reader.readAsText(file);

    // Reset input so the same file can be re-selected
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, []);

  const handleRemoveFile = useCallback(() => {
    setUploadedFile(null);
    setFileError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, []);

  // --- Conversion handler ---
  const handleConvert = useCallback(async () => {
    const effectiveTemplate = showCustomInput ? customTemplatePath : promptTemplatePath;
    if (!sourceCode.trim()) {
      setError('Please enter source code to convert.');
      return;
    }
    if (!bedrockModel) {
      setError('Please select a Bedrock model.');
      return;
    }
    if (!effectiveTemplate.trim()) {
      setError('Please select or provide a Prompt Template path.');
      return;
    }

    setError(null);
    setConverting(true);
    setResult(null);

    try {
      const request: StandaloneConversionRequest = {
        source_code: sourceCode,
        source_dialect: sourceDialect,
        target_dialect: targetDialect,
        asset_type: assetType,
        asset_name: assetName,
        aws_region: awsRegion,
        bedrock_model: bedrockModel,
        prompt_template_path: effectiveTemplate,
        max_retries: maxRetries,
        use_sqlglot: useSqlglot,
      };

      // Include file content as additional_context (Req 8.3)
      if (uploadedFile) {
        request.additional_context = uploadedFile.content;
      }

      const job = await createStandaloneConversion(request);
      setResult(job);
      setHistoryRefreshToken((t) => t + 1);
    } catch (err: any) {
      const msg =
        err?.detail || err?.message || 'Conversion failed. Please try again.';
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setConverting(false);
    }
  }, [
    sourceCode,
    sourceDialect,
    targetDialect,
    assetType,
    assetName,
    awsRegion,
    bedrockModel,
    promptTemplatePath,
    customTemplatePath,
    maxRetries,
    useSqlglot,
    showCustomInput,
    uploadedFile,
  ]);

  // --- Export .sql handler ---
  const handleExportSql = useCallback(() => {
    if (!result?.target_code) return;
    const blob = new Blob([result.target_code], { type: 'application/sql' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `converted_${targetDialect}.sql`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }, [result, targetDialect]);

  // --- History row click handler ---
  const handleSelectHistoryJob = useCallback(
    (job: ConversionJob) => {
      setResult(job);
      setSourceCode(job.source_code);
      setSourceDialect(job.source_dialect);
      setTargetDialect(job.target_dialect);
      setAssetType(job.asset_type);
    },
    []
  );

  const effectiveTemplatePath = showCustomInput ? customTemplatePath : promptTemplatePath;
  const canConvert =
    sourceCode.trim().length > 0 &&
    bedrockModel.length > 0 &&
    effectiveTemplatePath.trim().length > 0;

  return (
    <div className="standalone-converter-page">
      {/* Page header (Req 6.1, 7.1) */}
      <div className="converter-header">
        <h1 className="converter-title">
          <svg
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            aria-hidden="true"
          >
            <path
              d="M3 10h4l2-6 2 12 2-6h4"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          Code Converter
        </h1>
        <p className="converter-subtitle">
          Convert SQL and database code between dialects
        </p>
      </div>

      {/* Configuration form */}
      <Card className="converter-config-card">
        <div className="config-form">
          {/* Row 1: Dialects + Asset Type */}
          <div className="config-row">
            <div className="config-field">
              <label className="config-label" htmlFor="source-dialect">
                Source Dialect
              </label>
              <select
                id="source-dialect"
                className="config-select"
                value={sourceDialect}
                onChange={(e) => setSourceDialect(e.target.value)}
              >
                {SOURCE_DIALECT_OPTIONS.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </div>

            <div className="config-field">
              <label className="config-label" htmlFor="target-dialect">
                Target Dialect
              </label>
              <select
                id="target-dialect"
                className="config-select"
                value={targetDialect}
                onChange={(e) => setTargetDialect(e.target.value)}
              >
                {TARGET_DIALECT_OPTIONS.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </div>

            <div className="config-field">
              <label className="config-label" htmlFor="asset-type">
                Asset Type
              </label>
              <select
                id="asset-type"
                className="config-select"
                value={assetType}
                onChange={(e) => setAssetType(e.target.value)}
              >
                {ASSET_TYPE_OPTIONS.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Row 2: Asset Name + Region + Model */}
          <div className="config-row">
            <div className="config-field">
              <label className="config-label" htmlFor="asset-name">
                Asset Name
              </label>
              <input
                id="asset-name"
                className="config-input"
                type="text"
                value={assetName}
                onChange={(e) => setAssetName(e.target.value)}
                placeholder="Untitled Conversion"
              />
            </div>

            <div className="config-field">
              <label className="config-label" htmlFor="aws-region">
                AWS Region
              </label>
              <input
                id="aws-region"
                className="config-input"
                type="text"
                value={awsRegion}
                onChange={(e) => setAwsRegion(e.target.value)}
                placeholder="us-east-1"
              />
            </div>

            <div className="config-field">
              <label className="config-label" htmlFor="bedrock-model">
                Bedrock Model
              </label>
              <select
                id="bedrock-model"
                className="config-select"
                value={bedrockModel}
                onChange={(e) => setBedrockModel(e.target.value)}
                disabled={modelsLoading}
              >
                {modelsLoading ? (
                  <option value="">Loading models…</option>
                ) : models.length === 0 ? (
                  <option value="">No models available</option>
                ) : (
                  models.map((m) => (
                    <option key={m.model_id} value={m.model_id}>
                      {m.model_name} ({m.provider || 'unknown'})
                    </option>
                  ))
                )}
              </select>
            </div>
          </div>

          {/* Row 3: Template + Local Files */}
          <div className="config-row config-row--two-col">
            <div className="config-field">
              <label className="config-label" htmlFor="template-path">
                Prompt Template
              </label>
              <select
                id="template-path"
                className="config-select"
                value={showCustomInput ? 'custom' : promptTemplatePath}
                onChange={(e) => {
                  const val = e.target.value;
                  if (val === 'custom') {
                    setShowCustomInput(true);
                  } else {
                    setShowCustomInput(false);
                    setPromptTemplatePath(val);
                    setCustomTemplatePath('');
                  }
                }}
                disabled={templatesLoading}
              >
                {templatesLoading ? (
                  <option value="">Loading templates…</option>
                ) : templates.length === 0 ? (
                  <option value="">No templates available</option>
                ) : (
                  <>
                    {templates.map((t) => (
                      <option key={t.path} value={t.path}>
                        {t.name}
                      </option>
                    ))}
                    <option value="custom">Custom S3 Path...</option>
                  </>
                )}
              </select>
              {showCustomInput && (
                <input
                  className="config-input config-input--custom"
                  type="text"
                  value={customTemplatePath}
                  onChange={(e) => setCustomTemplatePath(e.target.value)}
                  placeholder="s3://bucket/path/template.txt or prompts/template.txt"
                  style={{ marginTop: '8px' }}
                />
              )}
            </div>

            <div className="config-field">
              <label className="config-label" htmlFor="local-file-upload">
                Local Files
              </label>
              {uploadedFile ? (
                <div className="file-upload-display">
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 16 16"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    aria-hidden="true"
                  >
                    <path
                      d="M9 1H4a1 1 0 00-1 1v12a1 1 0 001 1h8a1 1 0 001-1V5L9 1z"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                    <path d="M9 1v4h4" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <span className="file-upload-name" title={uploadedFile.name}>
                    {uploadedFile.name}
                  </span>
                  <button
                    type="button"
                    className="file-upload-remove"
                    onClick={handleRemoveFile}
                    aria-label="Remove uploaded file"
                  >
                    Remove
                  </button>
                </div>
              ) : (
                <div className="file-upload-control">
                  <input
                    ref={fileInputRef}
                    id="local-file-upload"
                    type="file"
                    accept={ACCEPTED_FILE_TYPES}
                    onChange={handleFileUpload}
                    className="file-upload-input"
                    aria-label="Upload a local file for additional context"
                  />
                  <label htmlFor="local-file-upload" className="file-upload-button">
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 16 16"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      aria-hidden="true"
                    >
                      <path
                        d="M8 12V4m0 0L5 7m3-3l3 3"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                      <path
                        d="M2 11v2a1 1 0 001 1h10a1 1 0 001-1v-2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                    Choose File
                  </label>
                  <span className="file-upload-hint">.txt, .sql, .csv, .json, .xml — max 5 MB</span>
                </div>
              )}
              {fileError && <span className="file-upload-error">{fileError}</span>}
            </div>
          </div>

          {/* Row 4: Max Retries + SQLGlot toggle */}
          <div className="config-row config-row--bottom">
            <div className="config-field config-field--small">
              <label className="config-label" htmlFor="max-retries">
                Max Retries
              </label>
              <input
                id="max-retries"
                className="config-input"
                type="number"
                min={0}
                max={10}
                value={maxRetries}
                onChange={(e) =>
                  setMaxRetries(Math.max(0, Math.min(10, Number(e.target.value))))
                }
              />
            </div>

            <div className="config-field config-field--toggle">
              <div className="sqlglot-toggle-wrapper">
                <Toggle
                  enabled={useSqlglot}
                  onChange={setUseSqlglot}
                  label="SQLGlot Pre-processing"
                  ariaLabel="Enable SQLGlot pre-processing"
                />
                <span
                  className="sqlglot-info-icon"
                  role="button"
                  tabIndex={0}
                  aria-label="SQLGlot information"
                  onMouseEnter={() => setShowTooltip(true)}
                  onMouseLeave={() => setShowTooltip(false)}
                  onFocus={() => setShowTooltip(true)}
                  onBlur={() => setShowTooltip(false)}
                >
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 14 14"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    aria-hidden="true"
                  >
                    <circle cx="7" cy="7" r="6" />
                    <path d="M7 9.5V7M7 4.5h.01" strokeLinecap="round" />
                  </svg>
                  {showTooltip && (
                    <span className="sqlglot-tooltip" role="tooltip">
                      SQLGlot pre-processes your SQL using rule-based transpilation before sending it to the AI model, improving accuracy for standard SQL patterns.
                    </span>
                  )}
                </span>
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* Error display */}
      {error && (
        <Alert variant="error" title="Conversion Error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Loading indicator */}
      {converting && (
        <div className="converter-loading">
          <div className="converter-spinner" />
          <span>Converting your code…</span>
        </div>
      )}

      {/* Side-by-side code panes */}
      <div className="converter-panes">
        {/* Source code input (left) */}
        <div className="converter-pane converter-pane--source">
          <div className="pane-header">
            <span className="pane-title">Source Code</span>
            <span className="pane-dialect">{sourceDialect}</span>
          </div>
          <textarea
            className="source-textarea"
            value={sourceCode}
            onChange={(e) => setSourceCode(e.target.value)}
            placeholder="Paste your SQL or database code here…"
            spellCheck={false}
            aria-label="Source code input"
          />
          {/* Convert button below source pane (Req 4.1) */}
          <div className="source-pane-actions">
            <Button
              variant="primary"
              onClick={handleConvert}
              loading={converting}
              disabled={!canConvert || converting}
            >
              {converting ? 'Converting…' : 'Convert'}
            </Button>
          </div>
        </div>

        {/* Converted code output (right) */}
        <div className="converter-pane converter-pane--target">
          <div className="pane-header">
            <span className="pane-title">Converted Code</span>
            <span className="pane-dialect">{targetDialect}</span>
            {result?.target_code && (
              <div className="pane-actions">
                <button
                  className="pane-action-btn"
                  onClick={handleExportSql}
                  title="Export as .sql"
                  aria-label="Export converted code as .sql file"
                  type="button"
                >
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 16 16"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    aria-hidden="true"
                  >
                    <path
                      d="M8 2v8m0 0l-3-3m3 3l3-3M3 12h10"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                  Export .sql
                </button>
              </div>
            )}
          </div>
          <CodePane
            code={result?.target_code || ''}
            title=""
            language={targetDialect}
            showLineNumbers
            maxHeight="400px"
          />
        </div>
      </div>

      {/* Result metadata */}
      {result && (
        <div className="converter-result-meta">
          <span className="meta-item">
            Status:{' '}
            <strong className={`status-${result.status}`}>{result.status}</strong>
          </span>
          {result.use_sqlglot && (
            <span className="meta-item">
              SQLGlot:{' '}
              <strong>
                {result.sqlglot_success ? 'Success' : 'Fallback to raw'}
              </strong>
            </span>
          )}
          <span className="meta-item">
            Retries: <strong>{result.retry_count}</strong>
          </span>
        </div>
      )}

      {/* Conversion history */}
      <Card className="converter-history-card">
        <ConversionHistoryTable
          onSelectJob={handleSelectHistoryJob}
          selectedJobId={result?.id ?? null}
          refreshToken={historyRefreshToken}
        />
      </Card>
    </div>
  );
};
