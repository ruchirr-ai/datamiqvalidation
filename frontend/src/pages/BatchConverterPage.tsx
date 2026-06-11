/**
 * Batch Converter Page
 *
 * Wizard-style multi-step flow for batch code conversion of discovered
 * database assets tied to a migration project. Steps:
 *   1. Asset Selection — grouped by Asset_Type with checkboxes
 *   2. Configuration — source/target connections, Bedrock model, etc.
 *   3. Review & Confirm — summary before submission
 *   4. Progress — live progress bar, polling, error details
 *   5. Summary  — final stats, export (.sql, S3), deploy to target DB
 *
 * Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 2.5, 2.7
 */

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { Card, Button, Toggle, Badge, Alert } from '../components/ui';
import {
  listBedrockModels,
  listPromptTemplates,
  createBatchConversion,
  getBatchStatus,
  listBatchJobs,
  exportBatchSql,
  exportBatchToS3,
  deployBatch,
  fetchAssessmentAssets,
  BedrockModel,
  PromptTemplate,
  AssetSelection,
  ConversionBatch,
  ConversionJob,
  DeployResult,
} from '../services/conversionApi';
import { listAssessments, Assessment } from '../services/assessmentsApi';
import { listConnections, Connection } from '../services/api';
import { AssetSelector, assetKey } from '../components/conversion/AssetSelector';
import { BatchHistoryTable } from '../components/conversion/BatchHistoryTable';
import { BatchPreviewWindow } from '../components/conversion/BatchPreviewWindow';
import './BatchConverterPage.css';
import { useLanguage } from '../contexts/LanguageContext';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Restricted source dialect options (Req 3.3) */
const SOURCE_DIALECT_OPTIONS = ['BigQuery', 'SQL Server', 'Redshift', 'Sybase', 'IBM Db2'];

/** Restricted target dialect options (Req 3.4) */
const TARGET_DIALECT_OPTIONS = ['Redshift', 'SQL Server', 'BigQuery', 'ClickHouse'];

/** Asset type options with Query first/default (Req 5.1, 5.2) */
const ASSET_TYPE_OPTIONS = [
  { value: 'QUERY', label: 'Query' },
  { value: 'TABLE_DDL', label: 'Table DDL' },
  { value: 'STORED_PROCEDURE', label: 'Stored Procedure' },
  { value: 'FUNCTION', label: 'Function' },
  { value: 'VIEW', label: 'View' },
  { value: 'MATERIALIZED_VIEW', label: 'Materialized View' },
];

const WIZARD_STEPS = [
  { number: 1, label: 'Assets' },
  { number: 2, label: 'Config' },
  { number: 3, label: 'Review' },
  { number: 4, label: 'Progress' },
  { number: 5, label: 'Summary' },
];

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface BatchConverterPageProps {
  /** Discovered assets to display for selection (passed from parent or populated later) */
  assets?: AssetSelection[];
  /** Pre-populated migration project id */
  migrationProjectId?: number;
  /** Pre-populated source connection id */
  sourceConnectionId?: number;
  /** Pre-populated target connection id */
  targetConnectionId?: number;
  /** Pre-populated source dialect */
  sourceDialect?: string;
  /** Pre-populated target dialect */
  targetDialect?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const BatchConverterPage: React.FC<BatchConverterPageProps> = ({
  assets = [],
  migrationProjectId,
  sourceConnectionId,
  targetConnectionId,
  sourceDialect: initialSourceDialect,
  targetDialect: initialTargetDialect,
}) => {
  const { t } = useLanguage();
  // --- Wizard state ---
  const [currentStep, setCurrentStep] = useState(1);

  // --- Step 1: Asset selection ---
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
  /** Editable asset name overrides keyed by assetKey */
  const [assetNameOverrides, setAssetNameOverrides] = useState<Record<string, string>>({});

  // --- Step 2: Configuration ---
  const [sourceConnId, setSourceConnId] = useState(sourceConnectionId ?? 0);
  const [targetConnId, setTargetConnId] = useState(targetConnectionId ?? 0);
  const [sourceDialect, setSourceDialect] = useState(initialSourceDialect ?? SOURCE_DIALECT_OPTIONS[0]);
  const [targetDialect, setTargetDialect] = useState(initialTargetDialect ?? TARGET_DIALECT_OPTIONS[0]);
  const [awsRegion, setAwsRegion] = useState('us-east-1');
  const [bedrockModel, setBedrockModel] = useState('');
  const [promptTemplatePath, setPromptTemplatePath] = useState('');
  const [customTemplatePath, setCustomTemplatePath] = useState('');
  const [showCustomInput, setShowCustomInput] = useState(false);
  const [maxRetries, setMaxRetries] = useState(3);
  const [useSqlglot, setUseSqlglot] = useState(false);
  const [batchName, setBatchName] = useState('');

  // --- Step 3→4: Submission ---
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // --- Step 4: Progress ---
  const [batchId, setBatchId] = useState<number | null>(null);
  const [batchStatus, setBatchStatus] = useState<ConversionBatch | null>(null);
  const [batchJobs, setBatchJobs] = useState<ConversionJob[]>([]);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // --- Step 5: Summary / Export / Deploy ---
  const [s3ExportPath, setS3ExportPath] = useState('');
  const [s3ExportRegion, setS3ExportRegion] = useState('us-east-1');
  const [s3Exporting, setS3Exporting] = useState(false);
  const [s3ExportMsg, setS3ExportMsg] = useState<string | null>(null);
  const [deploying, setDeploying] = useState(false);
  const [deployResult, setDeployResult] = useState<DeployResult | null>(null);
  const [exportingSQL, setExportingSQL] = useState(false);

  // --- Models & Templates ---
  const [models, setModels] = useState<BedrockModel[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);

  // --- Assessment-based asset loading ---
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [assessmentsLoading, setAssessmentsLoading] = useState(false);
  const [selectedAssessmentId, setSelectedAssessmentId] = useState<number | null>(null);
  const [loadedAssets, setLoadedAssets] = useState<AssetSelection[]>([]);
  const [assetsLoading, setAssetsLoading] = useState(false);
  const [assetsError, setAssetsError] = useState<string | null>(null);

  // --- Connections ---
  const [connections, setConnections] = useState<Connection[]>([]);
  const [connectionsLoading, setConnectionsLoading] = useState(false);

  // --- React Router location for nav reset (Req 12.2) ---
  const location = useLocation();
  const locationKeyRef = useRef(location.key);
  const currentStepRef = useRef(currentStep);
  currentStepRef.current = currentStep;

  useEffect(() => {
    if (location.key !== locationKeyRef.current) {
      locationKeyRef.current = location.key;
      // Clicking batch nav always resets to step 1 (unless already on step 1)
      if (currentStepRef.current >= 2) {
        setCurrentStep(1);
        setSelectedKeys(new Set());
        setAssetNameOverrides({});
        setBatchId(null);
        setBatchStatus(null);
        setBatchJobs([]);
        setSubmitting(false);
        setSubmitError(null);
        setS3ExportPath('');
        setS3ExportMsg(null);
        setDeployResult(null);
      }
    }
  }, [location.key]);

  // Merge prop-provided assets with assessment-loaded assets
  const allAssets = useMemo(
    () => (assets.length > 0 ? assets : loadedAssets),
    [assets, loadedAssets]
  );

  // --- Derived data ---
  const selectedAssets = useMemo(
    () =>
      allAssets
        .filter((a) => selectedKeys.has(assetKey(a)))
        .map((a) => {
          const key = assetKey(a);
          const overrideName = assetNameOverrides[key];
          return overrideName !== undefined ? { ...a, asset_name: overrideName } : a;
        }),
    [allAssets, selectedKeys, assetNameOverrides]
  );

  const selectedCountByType = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const a of selectedAssets) {
      counts[a.asset_type] = (counts[a.asset_type] || 0) + 1;
    }
    return counts;
  }, [selectedAssets]);

  // --- Load Bedrock models when region changes ---
  const fetchModels = useCallback(
    async (region: string) => {
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
    },
    [bedrockModel]
  );

  useEffect(() => {
    fetchModels(awsRegion);
  }, [awsRegion]); // eslint-disable-line react-hooks/exhaustive-deps

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

  // --- Auto-select matching template when source/target dialect changes ---
  useEffect(() => {
    if (templates.length === 0 || showCustomInput) return;
    const srcKey = sourceDialect.toLowerCase().replace(/\s+/g, '');
    const tgtKey = targetDialect.toLowerCase().replace(/\s+/g, '');
    const match = templates.find((t) => {
      const pathLower = t.path.toLowerCase();
      return pathLower.includes(srcKey) && pathLower.includes(tgtKey);
    });
    if (match) {
      setPromptTemplatePath(match.path);
    }
  }, [sourceDialect, targetDialect, templates, showCustomInput]);

  // --- Load completed assessments on mount ---
  useEffect(() => {
    const loadAssessments = async () => {
      setAssessmentsLoading(true);
      try {
        const data = await listAssessments();
        // Only show completed assessments
        setAssessments(data.assessments.filter((a) => a.status === 'completed'));
      } catch {
        setAssessments([]);
      } finally {
        setAssessmentsLoading(false);
      }
    };
    loadAssessments();
  }, []);

  // --- Load connections on mount ---
  useEffect(() => {
    const loadConnections = async () => {
      setConnectionsLoading(true);
      try {
        const data = await listConnections();
        setConnections(data);
      } catch {
        setConnections([]);
      } finally {
        setConnectionsLoading(false);
      }
    };
    loadConnections();
  }, []);

  // --- Load assets when assessment is selected ---
  useEffect(() => {
    if (selectedAssessmentId === null) {
      setLoadedAssets([]);
      setAssetsError(null);
      return;
    }
    const loadAssets = async () => {
      setAssetsLoading(true);
      setAssetsError(null);
      setSelectedKeys(new Set());
      try {
        const data = await fetchAssessmentAssets(selectedAssessmentId);
        setLoadedAssets(data.assets);
      } catch {
        setAssetsError('Failed to load assets from assessment');
        setLoadedAssets([]);
      } finally {
        setAssetsLoading(false);
      }
    };
    loadAssets();
  }, [selectedAssessmentId]); // eslint-disable-line react-hooks/exhaustive-deps

  // --- Sync props when they change ---
  useEffect(() => {
    if (sourceConnectionId !== undefined) setSourceConnId(sourceConnectionId);
  }, [sourceConnectionId]);

  useEffect(() => {
    if (targetConnectionId !== undefined) setTargetConnId(targetConnectionId);
  }, [targetConnectionId]);

  // --- Polling for batch progress (Step 4) ---
  useEffect(() => {
    if (batchId === null || currentStep !== 4) return;

    const poll = async () => {
      try {
        const status = await getBatchStatus(batchId);
        setBatchStatus(status);

        const jobs = await listBatchJobs(batchId);
        setBatchJobs(jobs);

        // Stop polling when batch is done
        if (
          status.status === 'completed' ||
          status.status === 'completed_with_errors' ||
          status.status === 'failed'
        ) {
          if (pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
          }
          setCurrentStep(5);
        }
      } catch {
        // Silently continue polling on transient errors
      }
    };

    // Initial fetch
    poll();

    // Poll every 3 seconds
    pollingRef.current = setInterval(poll, 3000);

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [batchId, currentStep]);

  // --- Navigation ---
  const canGoNext = (): boolean => {
    if (currentStep === 1) return selectedAssets.length > 0;
    if (currentStep === 2) {
      const effectiveTemplate = showCustomInput ? customTemplatePath : promptTemplatePath;
      return (
        sourceConnId > 0 &&
        targetConnId > 0 &&
        bedrockModel.length > 0 &&
        effectiveTemplate.trim().length > 0 &&
        awsRegion.trim().length > 0
      );
    }
    return false;
  };

  const canStartConversion = (): boolean => {
    const effectiveTemplate = showCustomInput ? customTemplatePath : promptTemplatePath;
    return (
      selectedAssets.length > 0 &&
      sourceConnId > 0 &&
      targetConnId > 0 &&
      bedrockModel.length > 0 &&
      effectiveTemplate.trim().length > 0 &&
      awsRegion.trim().length > 0
    );
  };

  const goNext = () => {
    if (currentStep < 3 && canGoNext()) {
      setCurrentStep((s) => s + 1);
    }
  };

  const goBack = () => {
    if (currentStep > 1 && currentStep <= 3) {
      setCurrentStep((s) => s - 1);
    }
  };

  // --- Start Conversion (Step 3 → Step 4) ---
  const handleStartConversion = async () => {
    if (submitting) return;
    setSubmitting(true);
    setSubmitError(null);
    const effectiveTemplate = showCustomInput ? customTemplatePath : promptTemplatePath;
    try {
      const batch = await createBatchConversion({
        migration_project_id: migrationProjectId ?? 1,
        source_connection_id: sourceConnId,
        target_connection_id: targetConnId,
        batch_name: batchName.trim() || undefined,
        assets: selectedAssets,
        source_dialect: sourceDialect,
        target_dialect: targetDialect,
        aws_region: awsRegion,
        bedrock_model: bedrockModel,
        prompt_template_path: effectiveTemplate,
        max_retries: maxRetries,
        use_sqlglot: useSqlglot,
      });
      setBatchId(batch.id);
      setBatchStatus(batch);
      setCurrentStep(4);
    } catch (err: unknown) {
      console.error('Batch conversion error:', err);
      let msg = 'Failed to start batch conversion';
      
      if (err && typeof err === 'object') {
        if ('detail' in err) {
          const detail = (err as { detail: unknown }).detail;
          // Handle Pydantic validation errors (array of error objects)
          if (Array.isArray(detail)) {
            msg = detail.map((e: any) => {
              const field = e.loc?.join('.') || 'unknown';
              const message = e.msg || 'validation error';
              return `${field}: ${message}`;
            }).join('; ');
          } else if (typeof detail === 'string') {
            msg = detail;
          } else if (detail && typeof detail === 'object') {
            msg = JSON.stringify(detail);
          }
        } else if ('message' in err) {
          msg = String((err as { message: unknown }).message);
        }
      }
      
      setSubmitError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  // --- Export / Deploy handlers (Step 5) ---
  const handleExportSql = async () => {
    if (!batchId || exportingSQL) return;
    setExportingSQL(true);
    try {
      await exportBatchSql(batchId);
    } catch {
      // download errors are shown by browser
    } finally {
      setExportingSQL(false);
    }
  };

  const handleExportS3 = async () => {
    if (!batchId || s3Exporting || !s3ExportPath.trim()) return;
    setS3Exporting(true);
    setS3ExportMsg(null);
    try {
      const res = await exportBatchToS3(batchId, {
        s3_path: s3ExportPath.trim(),
        region: s3ExportRegion,
      });
      setS3ExportMsg(res.message || 'Exported to S3 successfully');
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'detail' in err
          ? String((err as { detail: unknown }).detail)
          : 'S3 export failed';
      setS3ExportMsg(msg);
    } finally {
      setS3Exporting(false);
    }
  };

  const handleDeploy = async () => {
    if (!batchId || deploying) return;
    setDeploying(true);
    setDeployResult(null);
    try {
      const result = await deployBatch(batchId, {
        target_connection_id: targetConnId,
      });
      setDeployResult(result);
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'detail' in err
          ? String((err as { detail: unknown }).detail)
          : 'Deployment failed';
      setDeployResult({
        success: false,
        deployed_assets: [],
        failed_asset: null,
        error_message: msg,
      });
    } finally {
      setDeploying(false);
    }
  };

  /** Reset all state and return to step 1 for a new conversion */
  const handleNewConversion = () => {
    setCurrentStep(1);
    setSelectedKeys(new Set());
    setAssetNameOverrides({});
    setSourceConnId(sourceConnectionId ?? 0);
    setTargetConnId(targetConnectionId ?? 0);
    setSourceDialect(initialSourceDialect ?? SOURCE_DIALECT_OPTIONS[0]);
    setTargetDialect(initialTargetDialect ?? TARGET_DIALECT_OPTIONS[0]);
    setAwsRegion('us-east-1');
    setBedrockModel('');
    setPromptTemplatePath('');
    setCustomTemplatePath('');
    setShowCustomInput(false);
    setMaxRetries(3);
    setUseSqlglot(false);
    setBatchName('');
    setSubmitting(false);
    setSubmitError(null);
    setBatchId(null);
    setBatchStatus(null);
    setBatchJobs([]);
    setS3ExportPath('');
    setS3ExportRegion('us-east-1');
    setS3Exporting(false);
    setS3ExportMsg(null);
    setDeploying(false);
    setDeployResult(null);
    setExportingSQL(false);
    setSelectedAssessmentId(null);
    setLoadedAssets([]);
    setAssetsError(null);
  };

  // --- Render helpers ---

  const renderStepIndicator = () => (
    <div className="step-indicator" role="navigation" aria-label="Wizard steps">
      {WIZARD_STEPS.map((step, idx) => {
        const isActive = step.number === currentStep;
        const isCompleted = step.number < currentStep;
        return (
          <div className="step-item" key={step.number}>
            {idx > 0 && (
              <span
                className={`step-connector${isCompleted ? ' completed' : ''}`}
              />
            )}
            <span className="step-circle-group">
              <span
                className={`step-circle${isActive ? ' active' : ''}${isCompleted ? ' completed' : ''}`}
                aria-current={isActive ? 'step' : undefined}
              >
                {isCompleted ? (
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 14 14"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    aria-hidden="true"
                  >
                    <path
                      d="M2.5 7.5l3 3 6-6"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                ) : (
                  step.number
                )}
              </span>
              <span
                className={`step-label${isActive ? ' active' : ''}${isCompleted ? ' completed' : ''}`}
              >
                {step.label}
              </span>
            </span>
          </div>
        );
      })}
    </div>
  );

  // --- Step 1: Asset Selection ---
  const renderAssetSelection = () => (
    <div className="asset-selection-step">
      {/* Assessment picker */}
      <div className="assessment-picker">
        <label className="batch-config-label" htmlFor="assessment-select">
          Select Assessment
        </label>
        <select
          id="assessment-select"
          className="batch-config-select"
          value={selectedAssessmentId ?? ''}
          onChange={(e) => {
            const val = e.target.value;
            setSelectedAssessmentId(val ? Number(val) : null);
          }}
          disabled={assessmentsLoading}
        >
          <option value="">
            {assessmentsLoading ? 'Loading assessments…' : '— Choose a completed assessment —'}
          </option>
          {assessments.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name} — {a.total_tables} tables, {a.total_views} views, {a.total_routines} routines
            </option>
          ))}
        </select>
        {assessments.length === 0 && !assessmentsLoading && (
          <p className="assessment-picker-hint">
            No completed assessments found. Run an assessment first to discover assets.
          </p>
        )}
      </div>

      {assetsError && <Alert variant="error">{assetsError}</Alert>}

      {assetsLoading ? (
        <div className="asset-selection-empty">Loading assets…</div>
      ) : (
        <AssetSelector
          assets={allAssets}
          selectedKeys={selectedKeys}
          onSelectionChange={setSelectedKeys}
        />
      )}

      {/* Editable asset names for selected assets (Req 2.2) */}
      {selectedKeys.size > 0 && (
        <div className="asset-name-editor">
          <h4 className="asset-name-editor-title">Asset Names</h4>
          <p className="asset-name-editor-hint">
            Edit names for selected assets before conversion.
          </p>
          <div className="asset-name-editor-list">
            {allAssets
              .filter((a) => selectedKeys.has(assetKey(a)))
              .map((a) => {
                const key = assetKey(a);
                return (
                  <div className="asset-name-editor-row" key={key}>
                    <span className="asset-name-editor-type">
                      {ASSET_TYPE_OPTIONS.find((o) => o.value === a.asset_type)?.label ??
                        a.asset_type.replace(/_/g, ' ')}
                    </span>
                    <input
                      className="asset-name-editor-input"
                      type="text"
                      value={assetNameOverrides[key] ?? a.asset_name}
                      onChange={(e) =>
                        setAssetNameOverrides((prev) => ({
                          ...prev,
                          [key]: e.target.value,
                        }))
                      }
                      aria-label={`Asset name for ${a.asset_name}`}
                    />
                  </div>
                );
              })}
          </div>
        </div>
      )}
    </div>
  );

  // --- Step 2: Configuration ---
  const renderConfiguration = () => (
    <div className="batch-config-form">
      {/* Batch Name */}
      <div className="batch-config-row">
        <div className="batch-config-field" style={{ flex: 1 }}>
          <label className="batch-config-label" htmlFor="batch-name">
            Batch Name
          </label>
          <input
            id="batch-name"
            className="batch-config-input"
            type="text"
            value={batchName}
            onChange={(e) => setBatchName(e.target.value)}
            placeholder="e.g. Customer Tables Migration"
            maxLength={255}
          />
        </div>
      </div>

      {/* Row 1: Source / Target connections */}
      <div className="batch-config-row">
        <div className="batch-config-field">
          <label className="batch-config-label" htmlFor="batch-source-conn">
            {t('converter.sourceConnection')}
          </label>
          <select
            id="batch-source-conn"
            className="batch-config-select"
            value={sourceConnId || ''}
            onChange={(e) => setSourceConnId(Number(e.target.value))}
            disabled={connectionsLoading || sourceConnectionId !== undefined}
          >
            <option value="">
              {connectionsLoading ? 'Loading connections…' : '— Select source connection —'}
            </option>
            {connections.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.type})
              </option>
            ))}
          </select>
        </div>
        <div className="batch-config-field">
          <label className="batch-config-label" htmlFor="batch-target-conn">
            {t('converter.targetConnection')}
          </label>
          <select
            id="batch-target-conn"
            className="batch-config-select"
            value={targetConnId || ''}
            onChange={(e) => setTargetConnId(Number(e.target.value))}
            disabled={connectionsLoading || targetConnectionId !== undefined}
          >
            <option value="">
              {connectionsLoading ? 'Loading connections…' : '— Select target connection —'}
            </option>
            {connections.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.type})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Row 2: Dialects */}
      <div className="batch-config-row">
        <div className="batch-config-field">
          <label className="batch-config-label" htmlFor="batch-source-dialect">
            {t('converter.sourceDialect')}
          </label>
          <select
            id="batch-source-dialect"
            className="batch-config-select"
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
        <div className="batch-config-field">
          <label className="batch-config-label" htmlFor="batch-target-dialect">
            {t('converter.targetDialect')}
          </label>
          <select
            id="batch-target-dialect"
            className="batch-config-select"
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
      </div>

      {/* Row 3: Region, Model, Template */}
      <div className="batch-config-row batch-config-row--three">
        <div className="batch-config-field">
          <label className="batch-config-label" htmlFor="batch-region">
            AWS Region
          </label>
          <input
            id="batch-region"
            className="batch-config-input"
            type="text"
            value={awsRegion}
            onChange={(e) => setAwsRegion(e.target.value)}
            placeholder="us-east-1"
          />
        </div>
        <div className="batch-config-field">
          <label className="batch-config-label" htmlFor="batch-model">
            {t('converter.bedrockModel')}
          </label>
          <select
            id="batch-model"
            className="batch-config-select"
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
        <div className="batch-config-field">
          <label className="batch-config-label" htmlFor="batch-template">
            {t('converter.promptTemplate')}
          </label>
          <select
            id="batch-template"
            className="batch-config-select"
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
                <option value="custom">Custom S3 Path…</option>
              </>
            )}
          </select>
          {showCustomInput && (
            <input
              className="batch-config-input"
              type="text"
              value={customTemplatePath}
              onChange={(e) => setCustomTemplatePath(e.target.value)}
              placeholder="s3://bucket/path/template.txt or prompts/template.txt"
              style={{ marginTop: '8px' }}
            />
          )}
        </div>
      </div>

      {/* Row 4: Max Retries + sqlGLOT toggle */}
      <div className="batch-config-row batch-config-row--actions">
        <div className="batch-config-field batch-config-field--small">
          <label className="batch-config-label" htmlFor="batch-retries">
            {t('converter.maxRetries')}
          </label>
          <input
            id="batch-retries"
            className="batch-config-input"
            type="number"
            min={0}
            max={10}
            value={maxRetries}
            onChange={(e) =>
              setMaxRetries(Math.max(0, Math.min(10, Number(e.target.value))))
            }
          />
        </div>
        <div className="batch-config-field batch-config-field--toggle">
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
              <span className="sqlglot-tooltip" role="tooltip">
                SQLGlot pre-processes your SQL using rule-based transpilation before sending it to the AI model, improving accuracy for standard SQL patterns.
              </span>
            </span>
          </div>
        </div>
      </div>
    </div>
  );

  // --- Step 3: Review & Confirm ---
  const renderReview = () => {
    const sourceConnection = connections.find((c) => c.id === sourceConnId);
    const targetConnection = connections.find((c) => c.id === targetConnId);

    return (
      <div>
        {/* Selected assets summary */}
        <div className="review-section">
          <h3 className="review-section-title">
            Selected Assets ({selectedAssets.length})
          </h3>
          <div className="review-assets-grid">
            {Object.entries(selectedCountByType)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([type, count]) => (
                <div className="review-asset-type-card" key={type}>
                  <span className="review-asset-type-label">
                    {type.replace(/_/g, ' ')}
                  </span>
                  <span className="review-asset-type-count">{count}</span>
                </div>
              ))}
          </div>
        </div>

        {/* Configuration summary */}
        <div className="review-section">
          <h3 className="review-section-title">Configuration</h3>
          <div className="review-config-grid">
            {migrationProjectId !== undefined && (
              <div className="review-config-item">
                <span className="review-config-key">Migration Project</span>
                <span className="review-config-value">
                  #{migrationProjectId}
                </span>
              </div>
            )}
            <div className="review-config-item">
              <span className="review-config-key">Source Connection</span>
              <span className="review-config-value">
                {sourceConnection ? `${sourceConnection.name} (${sourceConnection.type})` : `#${sourceConnId}`}
              </span>
            </div>
            <div className="review-config-item">
              <span className="review-config-key">Target Connection</span>
              <span className="review-config-value">
                {targetConnection ? `${targetConnection.name} (${targetConnection.type})` : `#${targetConnId}`}
              </span>
            </div>
            <div className="review-config-item">
              <span className="review-config-key">Source Dialect</span>
              <span className="review-config-value">{sourceDialect}</span>
            </div>
            <div className="review-config-item">
              <span className="review-config-key">Target Dialect</span>
              <span className="review-config-value">{targetDialect}</span>
            </div>
            <div className="review-config-item">
              <span className="review-config-key">AWS Region</span>
              <span className="review-config-value">{awsRegion}</span>
            </div>
            <div className="review-config-item">
              <span className="review-config-key">Bedrock Model</span>
              <span className="review-config-value">{bedrockModel}</span>
            </div>
            <div className="review-config-item">
              <span className="review-config-key">Prompt Template</span>
              <span className="review-config-value">
                {showCustomInput 
                  ? customTemplatePath 
                  : (templates.find((t) => t.path === promptTemplatePath)?.name ?? promptTemplatePath)}
              </span>
            </div>
            <div className="review-config-item">
              <span className="review-config-key">Max Retries</span>
              <span className="review-config-value">{maxRetries}</span>
            </div>
            <div className="review-config-item">
              <span className="review-config-key">sqlGLOT</span>
              <span className="review-config-value">
                {useSqlglot ? 'Enabled' : 'Disabled'}
              </span>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // --- Step 4: Progress Monitoring ---
  const renderProgress = () => {
    const total = batchStatus?.total_assets ?? 0;
    const completed = batchStatus?.completed_assets ?? 0;
    const failed = batchStatus?.failed_assets ?? 0;
    const processed = completed + failed;
    const pct = total > 0 ? Math.round((processed / total) * 100) : 0;
    const isRunning =
      batchStatus?.status === 'pending' || batchStatus?.status === 'in_progress';

    // Find the currently in-progress job
    const currentJob = batchJobs.find((j) => j.status === 'in_progress');
    const failedJobs = batchJobs.filter((j) => j.status === 'failed');

    return (
      <div className="progress-step">
        {/* Progress bar */}
        <div className="progress-bar-container">
          <div className="progress-bar-header">
            <span className="progress-bar-label">
              {isRunning ? 'Converting assets…' : 'Conversion complete'}
            </span>
            <span className="progress-bar-pct">{pct}%</span>
          </div>
          <div className="progress-bar-track" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
            <div
              className={`progress-bar-fill${failed > 0 ? ' has-errors' : ''}`}
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>

        {/* Stats row */}
        <div className="progress-stats">
          <div className="progress-stat">
            <span className="progress-stat-value">{total}</span>
            <span className="progress-stat-label">Total</span>
          </div>
          <div className="progress-stat progress-stat--success">
            <span className="progress-stat-value">{completed}</span>
            <span className="progress-stat-label">Completed</span>
          </div>
          <div className="progress-stat progress-stat--error">
            <span className="progress-stat-value">{failed}</span>
            <span className="progress-stat-label">Failed</span>
          </div>
        </div>

        {/* Current asset */}
        {isRunning && currentJob && (
          <div className="progress-current">
            <span className="progress-current-label">Converting:</span>
            <span className="progress-current-name">
              {currentJob.asset_name ?? 'Unknown asset'}
            </span>
            <Badge variant="info" size="sm">{currentJob.asset_type.replace(/_/g, ' ')}</Badge>
          </div>
        )}

        {isRunning && !currentJob && (
          <div className="progress-current">
            <span className="progress-current-label">Waiting for next asset…</span>
          </div>
        )}

        {/* Failed job details */}
        {failedJobs.length > 0 && (
          <div className="progress-errors">
            <h4 className="progress-errors-title">
              Failed Assets ({failedJobs.length})
            </h4>
            <div className="progress-errors-list">
              {failedJobs.map((job) => (
                <div className="progress-error-item" key={job.id}>
                  <div className="progress-error-header">
                    <span className="progress-error-name">{job.asset_name ?? `Job #${job.id}`}</span>
                    <Badge variant="error" size="sm">{job.asset_type.replace(/_/g, ' ')}</Badge>
                  </div>
                  {job.error_message && (
                    <p className="progress-error-msg">{job.error_message}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  // --- Step 5: Summary ---
  const renderSummary = () => {
    const completed = batchStatus?.completed_assets ?? 0;
    const failed = batchStatus?.failed_assets ?? 0;
    const total = batchStatus?.total_assets ?? 0;
    const status = batchStatus?.status ?? 'unknown';

    const statusVariant: 'success' | 'warning' | 'error' | 'info' =
      status === 'completed'
        ? 'success'
        : status === 'completed_with_errors'
          ? 'warning'
          : status === 'failed'
            ? 'error'
            : 'info';

    return (
      <div className="summary-step">
        {/* Overall status */}
        <div className="summary-header">
          <h3 className="summary-title">Batch Conversion Complete</h3>
          <Badge variant={statusVariant}>{status.replace(/_/g, ' ')}</Badge>
        </div>

        {/* New Conversion button (Req 12.1, 12.3) */}
        {(status === 'completed' || status === 'completed_with_errors') && (
          <div className="summary-new-conversion">
            <Button variant="secondary" onClick={handleNewConversion}>
              New Conversion
            </Button>
          </div>
        )}

        {/* Stats */}
        <div className="summary-stats">
          <div className="summary-stat">
            <span className="summary-stat-value">{total}</span>
            <span className="summary-stat-label">Total Assets</span>
          </div>
          <div className="summary-stat summary-stat--success">
            <span className="summary-stat-value">{completed}</span>
            <span className="summary-stat-label">Converted</span>
          </div>
          <div className="summary-stat summary-stat--error">
            <span className="summary-stat-value">{failed}</span>
            <span className="summary-stat-label">Failed</span>
          </div>
        </div>

        {/* Export actions */}
        <div className="summary-section">
          <h4 className="summary-section-title">Export Options</h4>

          <div className="summary-actions">
            {/* Download .sql */}
            <Button
              variant="secondary"
              onClick={handleExportSql}
              disabled={exportingSQL || completed === 0}
            >
              {exportingSQL ? 'Downloading…' : 'Download .sql'}
            </Button>
          </div>

        </div>

        {/* Batch Preview Window (Req 11.1) */}
        {(status === 'completed' || status === 'completed_with_errors') && batchJobs.length > 0 && (
          <BatchPreviewWindow jobs={batchJobs} />
        )}
      </div>
    );
  };

  // --- Render current step content ---
  const renderStepContent = () => {
    switch (currentStep) {
      case 1:
        return renderAssetSelection();
      case 2:
        return renderConfiguration();
      case 3:
        return renderReview();
      case 4:
        return renderProgress();
      case 5:
        return renderSummary();
      default:
        return null;
    }
  };

  return (
    <div className="batch-converter-page">
      {/* Page header */}
      <div className="batch-header">
        <h1 className="batch-title">
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
              d="M4 4h5v5H4zM11 4h5v5h-5zM4 11h5v5H4zM11 11h5v5h-5z"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          Batch Code Converter
        </h1>
        <p className="batch-subtitle">
          {t('converter.subtitle')}
        </p>
      </div>

      {/* Step indicator */}
      <Card>{renderStepIndicator()}</Card>

      {/* Wizard content */}
      <Card className="wizard-content-card">
        {renderStepContent()}

        {/* Navigation buttons — only for steps 1-3 */}
        {currentStep <= 3 && (
          <div className="wizard-nav">
            <div className="wizard-nav-left">
              {currentStep > 1 && (
                <Button variant="secondary" onClick={goBack}>
                  Back
                </Button>
              )}
            </div>
            <div className="wizard-nav-right">
              {currentStep < 3 && (
                <Button
                  variant="primary"
                  onClick={goNext}
                  disabled={!canGoNext()}
                >
                  Next
                </Button>
              )}
              {currentStep === 3 && (
                <Button
                  variant="primary"
                  onClick={handleStartConversion}
                  disabled={submitting || !canStartConversion()}
                >
                  {submitting ? 'Starting…' : 'Start Conversion'}
                </Button>
              )}
            </div>
          </div>
        )}
        {submitError && currentStep === 3 && (
          <Alert variant="error" className="submit-error-alert" onClose={() => setSubmitError(null)}>
            {submitError}
          </Alert>
        )}
      </Card>

      {/* Batch history — visible before conversion starts */}
      {currentStep <= 3 && (
        <Card>
          <BatchHistoryTable />
        </Card>
      )}
    </div>
  );
};
