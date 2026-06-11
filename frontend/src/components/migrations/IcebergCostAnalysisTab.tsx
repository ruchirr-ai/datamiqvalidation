/**
 * Cost Analysis Tab for Iceberg migrations
 * Displays setup costs, recurring costs, projections, and TCO comparison.
 * Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Button, Card, Alert } from '../ui';
import { bqIcebergApi } from '../../services/bqIcebergApi';
import type { CostAnalysisReport, TCOComparison } from '../../types/bqIceberg';
import './IcebergCostAnalysisTab.css';

interface IcebergCostAnalysisTabProps {
  migrationId: number;
}

const formatCurrency = (amount: number): string => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
};

const formatBytes = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
};

export const IcebergCostAnalysisTab: React.FC<IcebergCostAnalysisTabProps> = ({
  migrationId,
}) => {
  const [report, setReport] = useState<CostAnalysisReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [growthRate, setGrowthRate] = useState(5); // percentage
  const [recalculating, setRecalculating] = useState(false);

  const fetchCostAnalysis = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await bqIcebergApi.getCostAnalysis(migrationId);
      setReport(data);
      setGrowthRate(Math.round(data.growth_rate_monthly * 100));
    } catch (err: any) {
      setError(err.message || 'Failed to load cost analysis');
    } finally {
      setLoading(false);
    }
  }, [migrationId]);

  useEffect(() => {
    fetchCostAnalysis();
  }, [fetchCostAnalysis]);

  const handleGrowthRateChange = async (newRate: number) => {
    setGrowthRate(newRate);
    setRecalculating(true);
    try {
      const data = await bqIcebergApi.recalculateCost(migrationId, {
        growth_rate_monthly: newRate / 100,
      });
      setReport(data);
    } catch (err: any) {
      setError(err.message || 'Failed to recalculate costs');
    } finally {
      setRecalculating(false);
    }
  };

  if (loading) {
    return (
      <div className="cost-analysis-tab">
        <div className="cost-analysis-tab__loading">Loading cost analysis...</div>
      </div>
    );
  }

  if (error && !report) {
    return (
      <div className="cost-analysis-tab">
        <Alert variant="error">{error}</Alert>
      </div>
    );
  }

  if (!report) return null;

  return (
    <div className="cost-analysis-tab">
      <div className="cost-analysis-tab__header">
        <h2 className="cost-analysis-tab__title">Cost Analysis</h2>
        <p className="cost-analysis-tab__subtitle">
          Estimated costs for migrating {report.table_count} tables ({formatBytes(report.data_size_bytes)}) to{' '}
          {report.destination_type === 'iceberg_s3' ? 'Apache Iceberg on S3' : 'AWS S3 Tables'}
        </p>
      </div>

      {error && (
        <Alert variant="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Setup Costs */}
      <Card className="cost-analysis-tab__section">
        <h3 className="cost-analysis-tab__section-title">One-Time Setup Costs</h3>
        <div className="cost-analysis-tab__cost-grid">
          <div className="cost-analysis-tab__cost-item">
            <span className="cost-analysis-tab__cost-label">S3 Storage (Initial)</span>
            <span className="cost-analysis-tab__cost-value">
              {formatCurrency(report.setup_costs.s3_storage_initial)}
            </span>
          </div>
          <div className="cost-analysis-tab__cost-item">
            <span className="cost-analysis-tab__cost-label">Glue API Calls</span>
            <span className="cost-analysis-tab__cost-value">
              {formatCurrency(report.setup_costs.glue_api_calls)}
            </span>
          </div>
          <div className="cost-analysis-tab__cost-item">
            <span className="cost-analysis-tab__cost-label">Data Transfer</span>
            <span className="cost-analysis-tab__cost-value">
              {formatCurrency(report.setup_costs.data_transfer)}
            </span>
          </div>
          <div className="cost-analysis-tab__cost-item cost-analysis-tab__cost-item--total">
            <span className="cost-analysis-tab__cost-label">Total Setup</span>
            <span className="cost-analysis-tab__cost-value">
              {formatCurrency(report.setup_costs.total)}
            </span>
          </div>
        </div>
      </Card>

      {/* Recurring Costs */}
      <Card className="cost-analysis-tab__section">
        <h3 className="cost-analysis-tab__section-title">Recurring Monthly Costs</h3>
        <div className="cost-analysis-tab__cost-grid">
          <div className="cost-analysis-tab__cost-item">
            <span className="cost-analysis-tab__cost-label">S3 Storage</span>
            <span className="cost-analysis-tab__cost-value">
              {formatCurrency(report.recurring_costs.s3_storage_monthly)}
            </span>
          </div>
          <div className="cost-analysis-tab__cost-item">
            <span className="cost-analysis-tab__cost-label">Glue Data Catalog</span>
            <span className="cost-analysis-tab__cost-value">
              {formatCurrency(report.recurring_costs.glue_catalog_monthly)}
            </span>
          </div>
          <div className="cost-analysis-tab__cost-item">
            <span className="cost-analysis-tab__cost-label">Athena Queries</span>
            <span className="cost-analysis-tab__cost-value">
              {formatCurrency(report.recurring_costs.athena_queries_monthly)}
            </span>
          </div>
          {report.recurring_costs.s3_tables_monthly !== undefined && (
            <div className="cost-analysis-tab__cost-item">
              <span className="cost-analysis-tab__cost-label">S3 Tables Premium</span>
              <span className="cost-analysis-tab__cost-value">
                {formatCurrency(report.recurring_costs.s3_tables_monthly)}
              </span>
            </div>
          )}
          <div className="cost-analysis-tab__cost-item cost-analysis-tab__cost-item--total">
            <span className="cost-analysis-tab__cost-label">Total Monthly</span>
            <span className="cost-analysis-tab__cost-value">
              {formatCurrency(report.recurring_costs.total_monthly)}
            </span>
          </div>
        </div>
      </Card>

      {/* Growth Rate Slider */}
      <Card className="cost-analysis-tab__section">
        <h3 className="cost-analysis-tab__section-title">Growth Rate Adjustment</h3>
        <p className="cost-analysis-tab__section-desc">
          Adjust the monthly data growth rate to see how it affects cost projections.
        </p>
        <div className="cost-analysis-tab__slider-container">
          <input
            type="range"
            min="0"
            max="30"
            step="1"
            value={growthRate}
            onChange={(e) => handleGrowthRateChange(Number(e.target.value))}
            className="cost-analysis-tab__slider"
            aria-label="Monthly growth rate percentage"
          />
          <span className="cost-analysis-tab__slider-value">
            {growthRate}% / month
            {recalculating && <span className="cost-analysis-tab__recalculating"> (recalculating...)</span>}
          </span>
        </div>
      </Card>

      {/* Projections */}
      <Card className="cost-analysis-tab__section">
        <h3 className="cost-analysis-tab__section-title">Cost Projections</h3>
        <p className="cost-analysis-tab__section-desc">
          Based on compression ratios of {report.compression_ratio_optimistic}:1 (optimistic) and{' '}
          {report.compression_ratio_conservative}:1 (conservative).
        </p>
        <div className="cost-analysis-tab__projections">
          <table className="cost-analysis-tab__projections-table">
            <thead>
              <tr>
                <th>Horizon</th>
                <th>Optimistic</th>
                <th>Conservative</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>3 Months</td>
                <td className="cost-analysis-tab__projection-optimistic">
                  {formatCurrency(report.projections_optimistic.month_3)}
                </td>
                <td className="cost-analysis-tab__projection-conservative">
                  {formatCurrency(report.projections_conservative.month_3)}
                </td>
              </tr>
              <tr>
                <td>6 Months</td>
                <td className="cost-analysis-tab__projection-optimistic">
                  {formatCurrency(report.projections_optimistic.month_6)}
                </td>
                <td className="cost-analysis-tab__projection-conservative">
                  {formatCurrency(report.projections_conservative.month_6)}
                </td>
              </tr>
              <tr>
                <td>12 Months</td>
                <td className="cost-analysis-tab__projection-optimistic">
                  {formatCurrency(report.projections_optimistic.month_12)}
                </td>
                <td className="cost-analysis-tab__projection-conservative">
                  {formatCurrency(report.projections_conservative.month_12)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </Card>

      {/* TCO Comparison */}
      {report.tco_comparison && (
        <Card className="cost-analysis-tab__section">
          <h3 className="cost-analysis-tab__section-title">TCO Comparison: BigQuery vs Iceberg</h3>
          <TCOComparisonDisplay comparison={report.tco_comparison} />
        </Card>
      )}
    </div>
  );
};

// --- TCO Comparison Sub-component ---
interface TCOComparisonDisplayProps {
  comparison: TCOComparison;
}

const TCOComparisonDisplay: React.FC<TCOComparisonDisplayProps> = ({ comparison }) => {
  const isSaving = comparison.savings_monthly > 0;

  return (
    <div className="tco-comparison">
      <div className="tco-comparison__grid">
        <div className="tco-comparison__item">
          <span className="tco-comparison__label">BigQuery (Current)</span>
          <span className="tco-comparison__value">{formatCurrency(comparison.bigquery_monthly)}/mo</span>
        </div>
        <div className="tco-comparison__item">
          <span className="tco-comparison__label">Iceberg (Projected)</span>
          <span className="tco-comparison__value">{formatCurrency(comparison.iceberg_monthly)}/mo</span>
        </div>
        <div className={`tco-comparison__item tco-comparison__item--${isSaving ? 'savings' : 'increase'}`}>
          <span className="tco-comparison__label">
            {isSaving ? 'Monthly Savings' : 'Additional Cost'}
          </span>
          <span className="tco-comparison__value">
            {isSaving ? '-' : '+'}{formatCurrency(Math.abs(comparison.savings_monthly))}/mo
            <span className="tco-comparison__percentage">
              ({Math.abs(comparison.savings_percentage).toFixed(1)}%)
            </span>
          </span>
        </div>
      </div>
    </div>
  );
};
