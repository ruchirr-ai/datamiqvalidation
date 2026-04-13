/**
 * Create Assessment Modal
 * 
 * Allows users to:
 * 1. Enter assessment name
 * 2. Select source connection
 * 3. Start assessment to collect source metadata
 */

import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { Button, Select, Input } from '../ui';
import { listConnections, Connection } from '../../services/api';
import { createAssessment } from '../../services/assessmentsApi';
import './CreateAssessmentModal.css';

interface CreateAssessmentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  mode?: 'assess' | 'analyze';
}

export const CreateAssessmentModal: React.FC<CreateAssessmentModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  mode = 'assess',
}) => {
  const [name, setName] = useState('');
  const [sourceConnectionId, setSourceConnectionId] = useState<number | null>(null);
  const [targetDb, setTargetDb] = useState<string>('redshift');
  const [connections, setConnections] = useState<Connection[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (isOpen) fetchConnections();
  }, [isOpen]);

  const fetchConnections = async () => {
    try {
      setLoading(true);
      const data = await listConnections();
      setConnections(data);
    } catch (err: any) {
      setError('Failed to load connections');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) { setError('Please enter an assessment name'); return; }
    if (!sourceConnectionId) { setError('Please select a source connection'); return; }

    try {
      setSubmitting(true);
      setError(null);
      await createAssessment({ name: name.trim(), source_connection_id: sourceConnectionId });
      onSuccess();
      handleClose();
    } catch (err: any) {
      setError(err.detail || err.message || 'Failed to create assessment');
    } finally {
      setSubmitting(false);
    }
  };

  const handleClose = () => {
    setName('');
    setSourceConnectionId(null);
    setTargetDb('redshift');
    setError(null);
    onClose();
  };

  if (!isOpen) return null;

  const sourceConnections = connections.filter(c => c.type === 'source');

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal-container" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{mode === 'analyze' ? 'Create New Analysis' : 'Create New Assessment'}</h2>
          <button className="modal-close-btn" onClick={handleClose} aria-label="Close">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {error && (
              <div className="error-message">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="8" cy="8" r="6" />
                  <path d="M8 5v3M8 11h.01" strokeLinecap="round" />
                </svg>
                {error}
              </div>
            )}

            <div className="form-section">
              <p className="form-description">
                {mode === 'analyze'
                  ? 'Create a new analysis to assess your source database and generate TCO comparison, migration recommendations, and Redshift sizing.'
                  : 'Create a new assessment to analyze your source database metadata — tables, views, routines, and more.'}
              </p>
            </div>

            <div className="form-group">
              <label htmlFor="assessment-name">Assessment Name <span className="required">*</span></label>
              <p className="field-hint">A descriptive name for this assessment</p>
              <Input id="assessment-name" type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g., Production DB Assessment" disabled={submitting} />
            </div>

            <div className="form-group">
              <label htmlFor="source-connection">Source Connection <span className="required">*</span></label>
              <p className="field-hint">Source database to analyze</p>
              {loading ? (
                <div className="loading-select">Loading connections...</div>
              ) : sourceConnections.length === 0 ? (
                <div className="no-connections-message">
                  <p>No source connections found.</p>
                  <p className="hint">Please create a source connection first.</p>
                </div>
              ) : (
                <Select
                  value={sourceConnectionId || ''}
                  onChange={(value) => setSourceConnectionId(Number(value))}
                  options={[
                    { value: '', label: 'Select source connection' },
                    ...sourceConnections.map(conn => ({ value: conn.id, label: `${conn.name} (${conn.database})` }))
                  ]}
                />
              )}
            </div>

            <div className="info-box">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="8" cy="8" r="6" />
                <path d="M8 7v4M8 5h.01" strokeLinecap="round" />
              </svg>
              <div>
                <strong>{mode === 'analyze' ? 'Assessment + Analysis will include:' : 'Assessment will analyze:'}</strong>
                <ul>
                  <li>Datasets, tables, views, routines, ML models</li>
                  <li>Data types and schema structure</li>
                  <li>Query patterns and usage insights</li>
                  <li>Security policies and indexes</li>
                  {mode === 'analyze' && <li>TCO comparison and migration recommendations</li>}
                </ul>
              </div>
            </div>

            {mode === 'analyze' && (
              <div className="form-group">
                <label htmlFor="target-db">Target Database <span className="required">*</span></label>
                <p className="field-hint">Destination database for analysis</p>
                <Select
                  value={targetDb}
                  onChange={(value) => setTargetDb(String(value))}
                  options={[
                    { value: 'redshift', label: 'Amazon Redshift' },
                  ]}
                />
              </div>
            )}
          </div>

          <div className="modal-footer">
            <Button type="button" variant="outline" onClick={handleClose} disabled={submitting}>Cancel</Button>
            <Button type="submit" variant="primary" disabled={submitting || !name.trim() || !sourceConnectionId}>
              {submitting ? 'Creating...' : 'Create Assessment'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
