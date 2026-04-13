/**
 * Assessment Report Page - Thin Router
 * 
 * This file ONLY handles:
 * 1. Loading the summary on mount
 * 2. Determining if the assessment is BigQuery or SQL Server
 * 3. Rendering the appropriate sub-page
 * 
 * DO NOT add BigQuery or SQL Server specific UI code here.
 * - BigQuery UI → BigQueryReportPage.tsx
 * - SQL Server UI → SQLServerReportPage.tsx
 * - Shared utilities → reportUtils.tsx
 */

import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from '../components/ui';
import { getReportSummary, ReportSummary } from '../services/assessmentsApi';
import { BigQueryReportPage } from './BigQueryReportPage';
import { SQLServerReportPage } from './SQLServerReportPage';
import './AssessmentReportPage.css';

export const AssessmentReportPage: React.FC = () => {
  const { assessmentId } = useParams<{ assessmentId: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [summary, setSummary] = useState<ReportSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const hasFetchedRef = useRef(false);

  const id = parseInt(assessmentId!);

  // Load summary on mount
  useEffect(() => {
    if (assessmentId && !hasFetchedRef.current) {
      hasFetchedRef.current = true;
      (async () => {
        try {
          setLoading(true);
          const data = await getReportSummary(id);
          setSummary(data);
        } catch (err: any) {
          setError(err.detail || err.message || 'Failed to load assessment report');
        } finally {
          setLoading(false);
        }
      })();
    }
  }, [assessmentId]);

  // Handle download query param
  useEffect(() => {
    if (searchParams.get('download') === 'true' && summary && !loading) {
      setSearchParams({}, { replace: true });
    }
  }, [summary, loading, searchParams]);

  if (loading) {
    return (
      <div className="assessment-report-page">
        <div style={{ padding: '40px', textAlign: 'center' }}>
          <div className="spinner" style={{ margin: '0 auto' }}></div>
          <p style={{ marginTop: '16px', color: 'var(--color-text-secondary)' }}>Loading assessment report...</p>
        </div>
      </div>
    );
  }

  if (error || !summary) {
    return (
      <div className="assessment-report-page">
        <div style={{ padding: '40px', textAlign: 'center' }}>
          <p style={{ color: 'var(--color-error)', marginBottom: '16px' }}>{error || 'Assessment not found'}</p>
          <Button variant="primary" onClick={() => navigate('/assessments')}>Back</Button>
        </div>
      </div>
    );
  }

  const isSQLServer = summary.assessment.source_db_type?.toLowerCase() === 'sqlserver';
  const isAnalyzeMode = searchParams.get('mode') === 'analyze';

  if (isSQLServer) {
    return <SQLServerReportPage summary={summary} assessmentId={id} />;
  }

  return <BigQueryReportPage summary={summary} assessmentId={id} showAnalysis={isAnalyzeMode} />;
};
