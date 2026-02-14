import React from 'react';
import './AssessmentsPage.css';

export const SchemaAnalysisPage: React.FC = () => {
  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Schema Analysis</h1>
        <p className="page-description">
          Analyze source database schemas to identify tables, columns, data types, and relationships
        </p>
      </div>

      <div className="page-content">
        <div className="empty-state">
          <div className="empty-state-icon">
            <svg width="64" height="64" viewBox="0 0 64 64" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="8" y="8" width="48" height="48" rx="4" />
              <path d="M8 20h48M20 8v48" />
              <circle cx="32" cy="36" r="8" />
            </svg>
          </div>
          <h2>Schema Analysis</h2>
          <p>
            Start by selecting a source connection to analyze its database schema.
            We'll identify all tables, columns, indexes, constraints, and relationships.
          </p>
          <button className="btn btn-primary">
            Start Schema Analysis
          </button>
        </div>
      </div>
    </div>
  );
};
