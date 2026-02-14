/**
 * Edit Assessment Modal
 * 
 * Allows users to edit an existing assessment:
 * 1. Update assessment name
 * 2. Change source connection
 * 3. Change target connection
 */

import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { Button, Select, Input } from '../ui';
import { listConnections, Connection } from '../../services/api';
import { updateAssessment, getAssessment } from '../../services/assessmentsApi';
import './CreateAssessmentModal.css';

interface EditAssessmentModalProps {
  isOpen: boolean;
  assessmentId: number;
  onClose: () => void;
  onSuccess: () => void;
}

export const EditAssessmentModal: React.FC<EditAssessmentModalProps> = ({
  isOpen,
  assessmentId,
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
      fetchData();
    }
  }, [isOpen, assessmentId]);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch assessment details and connections in parallel
      const [assessmentData, connectionsData] = await Promise.all([
        getAssessment(assessmentId),
        listConnections()
      ]);

      // Set form values from assessment data
      setName(assessmentData.assessment.name);
      setSourceConnectionId(assessmentData.assessment.source_connection_id);
      setTargetConnectionId(assessmentData.assessment.target_connection_id);
      setConnections(connectionsData);
    } catch (err: any) {
      console.error('Failed to fetch data:', err);
      setError('Failed to load assessment details');
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

      await updateAssessment(assessmentId, {
        name: name.trim(),
        source_connection_id: sourceConnectionId,
        target_connection_id: targetConnectionId
      });
      
      onSuccess();
      handleClose();
    } catch (err: any) {
      console.error('Failed to update assessment:', err);
      setError(err.detail || err.message || 'Failed to update assessment');
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

  const sourceConnections = connections.filter(c => c.type === 'source');
  const targetConnections = connections.filter(c => c.type === 'target');

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal-container" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Edit Assessment</h2>
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

            {loading ? (
              <div style={{ padding: '40px', textAlign: 'center' }}>
                <div className="spinner" style={{ margin: '0 auto' }}></div>
                <p style={{ marginTop: '16px', color: '#66748C' }}>Loading assessment details...</p>
              </div>
            ) : (
              <>
                <div className="form-section">
                  <p className="form-description">
                    Update the assessment details below.
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
                  {sourceConnections.length === 0 ? (
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
                  {targetConnections.length === 0 ? (
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
              </>
            )}
          </div>

          <div className="modal-footer">
            <Button type="button" variant="outline" onClick={handleClose} disabled={submitting || loading}>
              Cancel
            </Button>
            <Button 
              type="submit" 
              variant="primary" 
              disabled={submitting || loading || !name.trim() || !sourceConnectionId || !targetConnectionId}
            >
              {submitting ? 'Updating Assessment...' : 'Update Assessment'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
