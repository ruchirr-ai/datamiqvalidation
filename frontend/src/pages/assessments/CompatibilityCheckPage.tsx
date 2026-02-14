import React from 'react';
import './AssessmentsPage.css';

export const CompatibilityCheckPage: React.FC = () => {
  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Compatibility Check</h1>
        <p className="page-description">
          Check compatibility between source and target databases to identify potential migration issues
        </p>
      </div>

      <div className="page-content">
        <div className="empty-state">
          <div className="empty-state-icon">
            <svg width="64" height="64" viewBox="0 0 64 64" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="20" cy="32" r="12" />
              <circle cx="44" cy="32" r="12" />
              <path d="M32 32h0" strokeWidth="4" strokeLinecap="round" />
              <path d="M26 26l12 12M26 38l12-12" strokeLinecap="round" />
            </svg>
          </div>
          <h2>Compatibility Check</h2>
          <p>
            Compare source and target database types to identify compatibility issues,
            data type mappings, and feature differences that may affect your migration.
          </p>
          <button className="btn btn-primary">
            Run Compatibility Check
          </button>
        </div>
      </div>
    </div>
  );
};
