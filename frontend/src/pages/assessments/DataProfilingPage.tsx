import React from 'react';
import './AssessmentsPage.css';

export const DataProfilingPage: React.FC = () => {
  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Data Profiling</h1>
        <p className="page-description">
          Profile your data to understand patterns, quality issues, and migration complexity
        </p>
      </div>

      <div className="page-content">
        <div className="empty-state">
          <div className="empty-state-icon">
            <svg width="64" height="64" viewBox="0 0 64 64" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="8" y="16" width="48" height="40" rx="2" />
              <path d="M16 40h8v8h-8zM28 32h8v16h-8zM40 24h8v24h-8z" fill="currentColor" opacity="0.2" />
              <path d="M16 40h8v8h-8zM28 32h8v16h-8zM40 24h8v24h-8z" />
            </svg>
          </div>
          <h2>Data Profiling</h2>
          <p>
            Analyze your data distribution, identify null values, duplicates, and data quality issues
            that may impact your migration. Get insights into data patterns and anomalies.
          </p>
          <button className="btn btn-primary">
            Start Data Profiling
          </button>
        </div>
      </div>
    </div>
  );
};
