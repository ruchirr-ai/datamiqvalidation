import React from 'react';
import './AssessmentsPage.css';

export const AssessmentReportsPage: React.FC = () => {
  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Assessment Reports</h1>
        <p className="page-description">
          View and manage comprehensive assessment reports for your migration projects
        </p>
      </div>

      <div className="page-content">
        <div className="empty-state">
          <div className="empty-state-icon">
            <svg width="64" height="64" viewBox="0 0 64 64" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="12" y="8" width="40" height="48" rx="2" />
              <path d="M20 20h24M20 28h24M20 36h16" strokeLinecap="round" />
              <circle cx="44" cy="44" r="8" />
              <path d="M40 44l3 3 5-6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <h2>Assessment Reports</h2>
          <p>
            No assessment reports available yet. Run a schema analysis or compatibility check
            to generate detailed reports about your migration readiness.
          </p>
          <button className="btn btn-primary">
            Generate Report
          </button>
        </div>
      </div>
    </div>
  );
};
