import React from 'react';
import { Input, Select, Toggle } from '../../ui';
import './StepStyles.css';
import './SchedulingMonitoringStep.css';

interface SchedulingMonitoringStepProps {
  formData: any;
  updateFormData: (updates: any) => void;
}

const LOG_LEVELS = [
  { value: 'DEBUG', label: 'DEBUG - Detailed diagnostic information' },
  { value: 'INFO', label: 'INFO - General informational messages' },
  { value: 'WARNING', label: 'WARNING - Warning messages' },
  { value: 'ERROR', label: 'ERROR - Error messages only' },
];

const CRON_PRESETS = [
  { value: '0 0 * * *', label: 'Daily at midnight' },
  { value: '0 2 * * *', label: 'Daily at 2 AM' },
  { value: '0 0 * * 0', label: 'Weekly on Sunday' },
  { value: '0 0 1 * *', label: 'Monthly on 1st' },
  { value: 'custom', label: 'Custom CRON expression' },
];

export const SchedulingMonitoringStep: React.FC<SchedulingMonitoringStepProps> = ({
  formData,
  updateFormData,
}) => {
  const [cronPreset, setCronPreset] = React.useState('0 0 * * *');
  const [showCustomCron, setShowCustomCron] = React.useState(false);

  const handleCronPresetChange = (value: string | number) => {
    const stringValue = String(value);
    setCronPreset(stringValue);
    if (stringValue === 'custom') {
      setShowCustomCron(true);
    } else {
      setShowCustomCron(false);
      updateFormData({ cronExpression: stringValue });
    }
  };

  const getNextRunTime = (cronExpr: string): string => {
    // Placeholder - would use a CRON parser library
    if (!cronExpr) return 'Not scheduled';
    return 'Next run: Tomorrow at 12:00 AM';
  };

  return (
    <div className="step-container">
      <div className="step-header">
        <h2>Schedule & Monitor</h2>
        <p>Configure when to run the migration and how to monitor its progress</p>
      </div>

      <div className="step-content">
        {/* Placeholder Warning */}
        <div className="info-box" style={{ background: '#FFF4E6', borderColor: '#FFB020', marginBottom: '24px' }}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#FFB020" strokeWidth="2">
            <circle cx="8" cy="8" r="6" />
            <path d="M8 6v4M8 11h.01" strokeLinecap="round" />
          </svg>
          <div>
            <strong>Scheduling Coming Soon</strong>
            <p>
              Automated scheduling is currently under development. For now, migrations can be started manually 
              from the migrations list using the "Run Migration" action. The form below is a placeholder for 
              future scheduling functionality.
            </p>
          </div>
        </div>

        {/* Scheduling Section */}
        <div className="config-section">
          <h3>Scheduling</h3>
          
          <div className="form-section">
            <label className="form-label">Schedule Type</label>
            <div className="radio-group">
              <label className="radio-option">
                <input
                  type="radio"
                  name="scheduleType"
                  value="one-time"
                  checked={formData.scheduleType === 'one-time'}
                  onChange={(e) => updateFormData({ scheduleType: e.target.value })}
                />
                <div className="radio-content">
                  <span className="radio-title">Run Now</span>
                  <span className="radio-description">Execute migration immediately after creation</span>
                </div>
              </label>

              <label className="radio-option">
                <input
                  type="radio"
                  name="scheduleType"
                  value="recurring"
                  checked={formData.scheduleType === 'recurring'}
                  onChange={(e) => updateFormData({ scheduleType: e.target.value })}
                />
                <div className="radio-content">
                  <span className="radio-title">Scheduled</span>
                  <span className="radio-description">Schedule migration to run at specific times</span>
                </div>
              </label>
            </div>
          </div>

          {formData.scheduleType === 'recurring' && (
            <>
              <div className="form-section">
                <label className="form-label">
                  Schedule <span className="required">*</span>
                </label>
                <Select
                  value={cronPreset}
                  onChange={handleCronPresetChange}
                  options={CRON_PRESETS}
                />
              </div>

              {showCustomCron && (
                <div className="form-section">
                  <label className="form-label">
                    Custom CRON Expression <span className="required">*</span>
                  </label>
                  <Input
                    type="text"
                    placeholder="0 0 * * *"
                    value={formData.cronExpression}
                    onChange={(e) => updateFormData({ cronExpression: e.target.value })}
                  />
                  <p className="form-help">
                    Format: minute hour day month weekday (e.g., "0 2 * * *" for daily at 2 AM)
                  </p>
                </div>
              )}

              <div className="next-run-info">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="8" cy="8" r="6" />
                  <path d="M8 4v4l2 2" strokeLinecap="round" />
                </svg>
                <span>{getNextRunTime(formData.cronExpression)}</span>
              </div>
            </>
          )}
        </div>

        {/* Notifications Section */}
        <div className="config-section">
          <h3>Notifications</h3>
          
          <div className="toggle-option">
            <div className="toggle-content">
              <span className="toggle-title">Email Notifications</span>
              <span className="toggle-description">
                Receive email alerts for migration status updates
              </span>
            </div>
            <Toggle
              enabled={formData.emailNotifications}
              onChange={(enabled) => updateFormData({ emailNotifications: enabled })}
            />
          </div>

          <div className="form-section">
            <label className="form-label">Slack Webhook URL (Optional)</label>
            <Input
              type="text"
              placeholder="https://hooks.slack.com/services/..."
              value={formData.slackWebhook}
              onChange={(e) => updateFormData({ slackWebhook: e.target.value })}
            />
            <p className="form-help">
              Send migration updates to a Slack channel
            </p>
          </div>
        </div>

        {/* Monitoring Configuration */}
        <div className="config-section">
          <h3>Monitoring & Logging</h3>
          
          <div className="form-section">
            <label className="form-label">Log Level</label>
            <Select
              value={formData.logLevel}
              onChange={(value) => updateFormData({ logLevel: String(value) })}
              options={LOG_LEVELS}
            />
            <p className="form-help">
              Higher log levels provide more detailed information but may impact performance
            </p>
          </div>
        </div>

        {/* Error Handling Section */}
        <div className="config-section">
          <h3>Error Handling & Recovery</h3>
          
          <div className="toggle-option">
            <div className="toggle-content">
              <span className="toggle-title">Enable Checkpointing</span>
              <span className="toggle-description">
                Save progress at each stage to enable resumption after failures
              </span>
            </div>
            <Toggle
              enabled={formData.enableCheckpointing}
              onChange={(enabled) => updateFormData({ enableCheckpointing: enabled })}
            />
          </div>

          <div className="toggle-option">
            <div className="toggle-content">
              <span className="toggle-title">Retry Failed Shards</span>
              <span className="toggle-description">
                Automatically retry failed data shards with exponential backoff
              </span>
            </div>
            <Toggle
              enabled={formData.retryFailedShards}
              onChange={(enabled) => updateFormData({ retryFailedShards: enabled })}
            />
          </div>

          {formData.retryFailedShards && (
            <div className="form-section">
              <label className="form-label">Maximum Retries</label>
              <Input
                type="number"
                min="1"
                max="10"
                value={formData.maxRetries}
                onChange={(e) => updateFormData({ maxRetries: parseInt(e.target.value) })}
              />
              <p className="form-help">
                Number of times to retry a failed shard before marking it as permanently failed
              </p>
            </div>
          )}
        </div>

        {/* Summary */}
        <div className="success-box">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M13 4L6 11l-3-3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <div>
            <strong>Ready to create migration!</strong>
            <p>
              Review your configuration and click "Create Migration" to proceed. You can monitor
              the migration progress from the Migrations page.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
