import React, { useState, useMemo } from 'react';
import { Input, Select } from '../../ui';
import './StepStyles.css';
import './SchedulingMonitoringStep.css';

interface SchedulingMonitoringStepProps {
  formData: any;
  updateFormData: (updates: any) => void;
}

const CRON_PRESETS = [
  { value: '0 0 * * *', label: 'Daily at midnight' },
  { value: '0 2 * * *', label: 'Daily at 2 AM' },
  { value: '0 6 * * *', label: 'Daily at 6 AM' },
  { value: '0 0 * * 1-5', label: 'Weekdays at midnight' },
  { value: '0 0 * * 0', label: 'Weekly on Sunday' },
  { value: '0 0 1 * *', label: 'Monthly on 1st' },
  { value: 'custom', label: 'Custom CRON expression' },
];

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];
const DAY_NAMES = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

const HOURS = Array.from({ length: 24 }, (_, i) => ({
  value: i,
  label: i === 0 ? '12 AM' : i < 12 ? `${i} AM` : i === 12 ? '12 PM' : `${i - 12} PM`,
}));
const MINUTES = Array.from({ length: 60 }, (_, i) => ({
  value: i,
  label: i.toString().padStart(2, '0'),
}));

/* ─── Custom Calendar ─── */
const CustomCalendar: React.FC<{
  selectedDate: Date | null;
  onSelect: (d: Date) => void;
  selectedHour: number;
  selectedMinute: number;
  onHourChange: (h: number) => void;
  onMinuteChange: (m: number) => void;
}> = ({ selectedDate, onSelect, selectedHour, selectedMinute, onHourChange, onMinuteChange }) => {
  const today = useMemo(() => {
    const d = new Date(); d.setHours(0, 0, 0, 0); return d;
  }, []);
  const [viewDate, setViewDate] = useState(() => selectedDate ?? new Date());

  const year = viewDate.getFullYear();
  const month = viewDate.getMonth();

  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const daysInPrevMonth = new Date(year, month, 0).getDate();

  const prevMonth = () => setViewDate(new Date(year, month - 1, 1));
  const nextMonth = () => setViewDate(new Date(year, month + 1, 1));

  const isSameDay = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();

  const cells: { day: number; inMonth: boolean; date: Date }[] = [];
  for (let i = firstDay - 1; i >= 0; i--) {
    const d = daysInPrevMonth - i;
    cells.push({ day: d, inMonth: false, date: new Date(year, month - 1, d) });
  }
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push({ day: d, inMonth: true, date: new Date(year, month, d) });
  }
  const remaining = 7 - (cells.length % 7);
  if (remaining < 7) {
    for (let d = 1; d <= remaining; d++) {
      cells.push({ day: d, inMonth: false, date: new Date(year, month + 1, d) });
    }
  }

  return (
    <div className="cal">
      {/* Header */}
      <div className="cal-header">
        <button type="button" className="cal-nav" onClick={prevMonth} aria-label="Previous month">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 3L5 8l5 5"/></svg>
        </button>
        <span className="cal-title">{MONTH_NAMES[month]} {year}</span>
        <button type="button" className="cal-nav" onClick={nextMonth} aria-label="Next month">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 3l5 5-5 5"/></svg>
        </button>
      </div>

      {/* Day names */}
      <div className="cal-grid cal-day-names">
        {DAY_NAMES.map((d) => <div key={d} className="cal-cell cal-day-name">{d}</div>)}
      </div>

      {/* Day cells */}
      <div className="cal-grid">
        {cells.map((c, i) => {
          const isPast = c.date < today;
          const isToday = isSameDay(c.date, today);
          const isSelected = selectedDate ? isSameDay(c.date, selectedDate) : false;
          return (
            <button
              key={i}
              type="button"
              disabled={isPast || !c.inMonth}
              className={[
                'cal-cell cal-day',
                !c.inMonth && 'cal-outside',
                isPast && c.inMonth && 'cal-past',
                isToday && 'cal-today',
                isSelected && 'cal-selected',
              ].filter(Boolean).join(' ')}
              onClick={() => { if (!isPast && c.inMonth) onSelect(c.date); }}
            >
              {c.day}
            </button>
          );
        })}
      </div>

      {/* Time picker */}
      <div className="cal-time">
        <div className="cal-time-group">
          <label className="cal-time-label">Hour</label>
          <select
            className="cal-time-select"
            value={selectedHour}
            onChange={(e) => onHourChange(Number(e.target.value))}
          >
            {HOURS.map((h) => <option key={h.value} value={h.value}>{h.label}</option>)}
          </select>
        </div>
        <span className="cal-time-sep">:</span>
        <div className="cal-time-group">
          <label className="cal-time-label">Min</label>
          <select
            className="cal-time-select"
            value={selectedMinute}
            onChange={(e) => onMinuteChange(Number(e.target.value))}
          >
            {MINUTES.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
        </div>
      </div>
    </div>
  );
};

/* ─── Main Component ─── */
export const SchedulingMonitoringStep: React.FC<SchedulingMonitoringStepProps> = ({
  formData,
  updateFormData,
}) => {
  const [cronPreset, setCronPreset] = useState('0 0 * * *');
  const [showCustomCron, setShowCustomCron] = useState(false);

  // Parse existing scheduledDateTime into parts
  const parsedDate = useMemo(() => {
    if (!formData.scheduledDateTime) return null;
    const d = new Date(formData.scheduledDateTime);
    return isNaN(d.getTime()) ? null : d;
  }, [formData.scheduledDateTime]);

  const [selectedHour, setSelectedHour] = useState(() => parsedDate?.getHours() ?? 9);
  const [selectedMinute, setSelectedMinute] = useState(() => {
    if (!parsedDate) return 0;
    return parsedDate.getMinutes();
  });

  const buildISOString = (date: Date, hour: number, minute: number) => {
    const d = new Date(date);
    d.setHours(hour, minute, 0, 0);
    // Format as YYYY-MM-DDTHH:mm
    const pad = (n: number) => n.toString().padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(hour)}:${pad(minute)}`;
  };

  const handleDateSelect = (date: Date) => {
    updateFormData({ scheduledDateTime: buildISOString(date, selectedHour, selectedMinute) });
  };

  const handleHourChange = (h: number) => {
    setSelectedHour(h);
    if (parsedDate) updateFormData({ scheduledDateTime: buildISOString(parsedDate, h, selectedMinute) });
  };

  const handleMinuteChange = (m: number) => {
    setSelectedMinute(m);
    if (parsedDate) updateFormData({ scheduledDateTime: buildISOString(parsedDate, selectedHour, m) });
  };

  const handleCronPresetChange = (value: string | number) => {
    const v = String(value);
    setCronPreset(v);
    if (v === 'custom') { setShowCustomCron(true); }
    else { setShowCustomCron(false); updateFormData({ cronExpression: v }); }
  };

  const getNextRunTime = (c: string): string => {
    if (!c) return 'Not scheduled';
    const map: Record<string, string> = {
      '0 0 * * *': 'Next run: Tomorrow at 12:00 AM',
      '0 2 * * *': 'Next run: Tomorrow at 2:00 AM',
      '0 6 * * *': 'Next run: Tomorrow at 6:00 AM',
      '0 0 * * 1-5': 'Next run: Next weekday at 12:00 AM',
      '0 0 * * 0': 'Next run: Sunday at 12:00 AM',
      '0 0 1 * *': 'Next run: 1st of next month at 12:00 AM',
    };
    return map[c] || `Scheduled: ${c}`;
  };

  const formatScheduledDate = (dateStr: string): string => {
    if (!dateStr) return '';
    try {
      return new Date(dateStr).toLocaleString(undefined, {
        weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
      });
    } catch { return dateStr; }
  };

  return (
    <div className="step-container">
      <div className="step-header">
        <h2>Schedule & Run</h2>
        <p>Choose when to execute the migration and review your configuration</p>
      </div>

      <div className="step-content">
        {/* Execution Mode */}
        <div className="config-section">
          <h3>Execution Mode</h3>
          <div className="form-section">
            <label className="form-label">When should this migration run?</label>
            <div className="radio-group">
              {([
                { key: 'run-now', title: 'Run Now', desc: 'Execute the migration immediately after creation.', color: '#10B981', bg: '#ECFDF5' },
                { key: 'one-time', title: 'Schedule Once', desc: 'Pick a specific date and time to run the migration once.', color: 'var(--color-primary)', bg: '#EFF6FF' },
                { key: 'recurring', title: 'Recurring Schedule', desc: 'Run the migration on a recurring schedule using a CRON expression.', color: 'var(--color-primary)', bg: '#EFF6FF' },
                { key: 'save-only', title: 'Save Only', desc: 'Save the configuration without running. Start it later from the Migrations page.', color: 'var(--color-primary)', bg: '#EFF6FF' },
              ] as const).map((opt) => (
                <label
                  key={opt.key}
                  className={`radio-option ${formData.scheduleType === opt.key ? 'selected' : ''}`}
                  style={formData.scheduleType === opt.key ? { borderColor: opt.color, background: opt.bg } : {}}
                >
                  <input
                    type="radio"
                    name="scheduleType"
                    value={opt.key}
                    checked={formData.scheduleType === opt.key}
                    onChange={() => updateFormData({
                      scheduleType: opt.key,
                      runImmediately: opt.key === 'run-now',
                    })}
                  />
                  <div className="radio-content">
                    <span className="radio-title">{opt.title}</span>
                    <span className="radio-description">{opt.desc}</span>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* One-Time Schedule: Custom Calendar */}
          {formData.scheduleType === 'one-time' && (
            <div className="schedule-picker-section">
              <label className="form-label">
                Select Date & Time <span className="required">*</span>
              </label>
              <CustomCalendar
                selectedDate={parsedDate}
                onSelect={handleDateSelect}
                selectedHour={selectedHour}
                selectedMinute={selectedMinute}
                onHourChange={handleHourChange}
                onMinuteChange={handleMinuteChange}
              />
              {formData.scheduledDateTime && (
                <div className="next-run-info">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <rect x="2" y="3" width="12" height="11" rx="1.5" />
                    <path d="M2 6.5h12" />
                    <path d="M5 1.5v3M11 1.5v3" strokeLinecap="round" />
                  </svg>
                  <span>Scheduled for: {formatScheduledDate(formData.scheduledDateTime)}</span>
                </div>
              )}
            </div>
          )}

          {/* Recurring Schedule: CRON */}
          {formData.scheduleType === 'recurring' && (
            <div className="schedule-picker-section">
              <div className="form-section">
                <label className="form-label">Schedule <span className="required">*</span></label>
                <Select value={cronPreset} onChange={handleCronPresetChange} options={CRON_PRESETS} />
              </div>
              {showCustomCron && (
                <div className="form-section">
                  <label className="form-label">Custom CRON Expression <span className="required">*</span></label>
                  <Input
                    type="text"
                    placeholder="0 0 * * *"
                    value={formData.cronExpression}
                    onChange={(e) => updateFormData({ cronExpression: e.target.value })}
                  />
                  <p className="form-help">Format: minute hour day month weekday (e.g., "0 2 * * *" for daily at 2 AM)</p>
                </div>
              )}
              <div className="next-run-info">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <circle cx="8" cy="8" r="6" />
                  <path d="M8 4.5v3.5l2.5 1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                <span>{getNextRunTime(formData.cronExpression)}</span>
              </div>
            </div>
          )}
        </div>

        {/* Migration Summary */}
        <div className="config-section">
          <h3>Migration Summary</h3>
          <div className="summary-grid">
            {[
              ['Migration Name', formData.migrationName || '—'],
              ['Pathway', formData.pathway === 'B' ? 'Path B — AWS DataSync' : formData.pathway ? `Path ${formData.pathway}` : '—'],
              ['Tables', `${formData.selectedTables?.length || 0} selected`],
              ['Load Type', formData.loadType === 'incremental' ? 'Incremental' : 'Full Load'],
              ['Export Format', formData.exportFormat || 'AVRO'],
              ['Execution', formData.scheduleType === 'run-now' ? 'Immediate' : formData.scheduleType === 'one-time' ? (formatScheduledDate(formData.scheduledDateTime) || 'Date not set') : formData.scheduleType === 'recurring' ? (formData.cronExpression || 'Not configured') : 'Manual'],
            ].map(([label, value], i) => (
              <div className="summary-row" key={i}>
                <span className="summary-label">{label}</span>
                <span className="summary-value" style={label === 'Execution' && formData.scheduleType === 'run-now' ? { color: '#10B981' } : {}}>{value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Ready message */}
        <div className="success-box">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M13 4L6 11l-3-3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <div>
            <strong>
              {formData.scheduleType === 'run-now' ? 'Ready to create and run!'
                : formData.scheduleType === 'one-time' ? 'Ready to schedule!'
                : 'Ready to create migration!'}
            </strong>
            <p>
              {formData.scheduleType === 'run-now'
                ? 'Click "Create & Run" to save the configuration and start the migration immediately.'
                : formData.scheduleType === 'one-time'
                ? 'Click "Schedule Migration" to save and schedule. The migration will run at the selected date and time.'
                : 'Click "Create Migration" to save the configuration. You can start it later from the Migrations page.'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
