import React, { useState } from 'react';
import { Download, X, FileText } from 'lucide-react';
import './DownloadReportModal.css';

interface Section {
  id: string;
  label: string;
  description: string;
}

interface DownloadReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  assessmentName: string;
  onDownload: (selectedSections: string[]) => void;
  downloading?: boolean;
}

const SECTIONS: Section[] = [
  { id: 'summary', label: 'Summary', description: 'Assessment overview with key metrics' },
  { id: 'datasets', label: 'Datasets', description: 'Dataset details and sizes' },
  { id: 'tables', label: 'Tables', description: 'Table schemas, row counts, partitioning' },
  { id: 'views', label: 'Views', description: 'View definitions and metadata' },
  { id: 'procedures', label: 'Stored Procedures', description: 'Stored procedure definitions' },
  { id: 'functions', label: 'Functions', description: 'Function definitions' },
  { id: 'ml-models', label: 'ML & Spark Models', description: 'ML models and Spark jobs' },
  { id: 'query-insights', label: 'Query Insights', description: 'Query patterns and statistics' },
  { id: 'user-insights', label: 'User Insights', description: 'User activity and access patterns' },
  { id: 'security', label: 'Security', description: 'Security policies (RLS/CLS)' },
  { id: 'recommendations', label: 'Recommendations', description: 'Migration recommendations' },
  { id: 'tco', label: 'TCO Analysis', description: 'Total Cost of Ownership comparison' },
];

export const DownloadReportModal: React.FC<DownloadReportModalProps> = ({
  isOpen,
  onClose,
  assessmentName,
  onDownload,
  downloading = false,
}) => {
  const [selected, setSelected] = useState<Set<string>>(new Set(SECTIONS.map(s => s.id)));

  if (!isOpen) return null;

  const toggleSection = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => setSelected(new Set(SECTIONS.map(s => s.id)));
  const deselectAll = () => setSelected(new Set());

  return (
    <div className="download-modal-overlay" onClick={onClose}>
      <div className="download-modal" onClick={e => e.stopPropagation()}>
        <div className="download-modal-header">
          <div className="download-modal-title">
            <FileText size={20} />
            <h3>Download Report</h3>
          </div>
          <button className="download-modal-close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="download-modal-subtitle">
          <span>Assessment: {assessmentName}</span>
          <span className="download-format-badge">PDF</span>
        </div>

        <div className="download-modal-body">
          <div className="section-select-header">
            <span>Select sections to include:</span>
            <div className="section-select-actions">
              <button className="link-btn" onClick={selectAll}>Select All</button>
              <span className="divider">|</span>
              <button className="link-btn" onClick={deselectAll}>Deselect All</button>
            </div>
          </div>

          <div className="section-list">
            {SECTIONS.map(section => (
              <label key={section.id} className="section-item">
                <input
                  type="checkbox"
                  checked={selected.has(section.id)}
                  onChange={() => toggleSection(section.id)}
                />
                <div className="section-item-info">
                  <span className="section-item-label">{section.label}</span>
                  <span className="section-item-desc">{section.description}</span>
                </div>
              </label>
            ))}
          </div>
        </div>

        <div className="download-modal-footer">
          <button className="btn-cancel" onClick={onClose}>Cancel</button>
          <button
            className="btn-download"
            onClick={() => onDownload(Array.from(selected))}
            disabled={selected.size === 0 || downloading}
          >
            {downloading ? (
              <>
                <span className="btn-spinner" />
                Generating PDF...
              </>
            ) : (
              <>
                <Download size={16} />
                Download PDF ({selected.size} sections)
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
