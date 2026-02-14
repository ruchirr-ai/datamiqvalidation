/**
 * Create Assessment Modal
 * 
 * Allows users to:
 * 1. Select source connection (BigQuery)
 * 2. Select target connection (Redshift)
 * 3. Start assessment to collect metadata and analyze migration compatibility
 * 
 * Displays results:
 * - Datasets (Databases)
 * - Dataset name, Creation time, Location/Region, Table count, Total size
 * - Migration compatibility analysis
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
}

export const CreateAssessmentModal: React.FC<CreateAssessmentModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [name, setName] = useState('');
  const [sourceConnectionId, setSourceConnectionId] = useState<number | null>(null);
  const [targetConnectionId, setTargetConnectionId] = useState<number | null>(null);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      fetchConnections();
    }
  }, [isOpen]);

  const fetchConnections = async () => {
    try {
      setLoading(true);
      const data = await listConnections();
      setConnections(data);
    } catch (err: any) {
      console.error('Failed to fetch connections:', err);
      setError('Failed to load connections');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!name.trim()) {
      setError('Please enter an assessment name');
      return;
    }

    if (!sourceConnectionId) {
      setError('Please select a source connection');
      return;
    }

    if (!targetConnectionId) {
      setError('Please select a target connection');
      return;
    }

    try {
      setSubmitting(true);
      setError(null);

      await createAssessment({
        name: name.trim(),
        source_connection_id: sourceConnectionId,
        target_connection_id: targetConnectionId
      });
      
      onSuccess();
      handleClose();
    } catch (err: any) {
      console.error('Failed to create assessment:', err);
      setError(err.detail || err.message || 'Failed to create assessment');
    } finally {
      setSubmitting(false);
    }
  };

  const handleClose = () => {
    setName('');
    setSourceConnectionId(null);
    setTargetConnectionId(null);
    setError(null);
    onClose();
  };

  if (!isOpen) return null;

  // Allow any source and target connections (not restricted to BigQuery/Redshift)
  const sourceConnections = connections.filter(c => c.type === 'source');
  const targetConnections = connections.filter(c => c.type === 'target');

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal-container" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Create New Assessment</h2>
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
                Create a new assessment to analyze migration compatibility and collect metadata information.
              </p>
            </div>

            <div className="form-group">
              <label htmlFor="assessment-name">
                Assessment Name <span className="required">*</span>
              </label>
              <p className="field-hint">A descriptive name for this assessment</p>
              <Input
                id="assessment-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Production DB Migration Assessment"
                disabled={submitting}
              />
            </div>

            <div className="form-group">
              <label htmlFor="source-connection">
                Source Connection <span className="required">*</span>
              </label>
              <p className="field-hint">Source database connection to assess</p>
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
                    ...sourceConnections.map(conn => ({
                      value: conn.id,
                      label: conn.name
                    }))
                  ]}
                />
              )}
            </div>

            <div className="form-group">
              <label htmlFor="target-connection">
                Target Connection <span className="required">*</span>
              </label>
              <p className="field-hint">Target database connection for migration</p>
              {loading ? (
                <div className="loading-select">Loading connections...</div>
              ) : targetConnections.length === 0 ? (
                <div className="no-connections-message">
                  <p>No target connections found.</p>
                  <p className="hint">Please create a target connection first.</p>
                </div>
              ) : (
                <Select
                  value={targetConnectionId || ''}
                  onChange={(value) => setTargetConnectionId(Number(value))}
                  options={[
                    { value: '', label: 'Select target connection' },
                    ...targetConnections.map(conn => ({
                      value: conn.id,
                      label: conn.name
                    }))
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
                <strong>Assessment will analyze:</strong>
                <ul>
                  <li>Source metadata - datasets, tables, views, routines, ML models</li>
                  <li>Data types and schema compatibility</li>
                  <li>Migration complexity and potential issues</li>
                  <li>Estimated migration time and resources</li>
                </ul>
              </div>
            </div>
          </div>

          <div className="modal-footer">
            <Button type="button" variant="outline" onClick={handleClose} disabled={submitting}>
              Cancel
            </Button>
            <Button 
              type="submit" 
              variant="primary" 
              disabled={submitting || !name.trim() || !sourceConnectionId || !targetConnectionId}
            >
              {submitting ? 'Creating Assessment...' : 'Create Assessment'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
