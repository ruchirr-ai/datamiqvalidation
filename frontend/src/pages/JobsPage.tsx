import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { useLanguage } from '../contexts/LanguageContext';
import './JobsPage.css';

interface JobDetail {
  [key: string]: any;
}

interface Job {
  id: string;
  resource_id: number;
  type: 'assessment' | 'migration';
  name: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  details: JobDetail;
  progress: number;
}

interface JobsSummary {
  total: number;
  running: number;
  completed: number;
  failed: number;
  pending: number;
}

type FilterTab = 'all' | 'running' | 'completed' | 'failed' | 'pending';

export const JobsPage: React.FC = () => {
  const navigate = useNavigate();
  const { t } = useLanguage();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [summary, setSummary] = useState<JobsSummary>({ total: 0, running: 0, completed: 0, failed: 0, pending: 0 });
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState<FilterTab>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const fetchJobs = async () => {
    try {
      setLoading(true);
      const data = await api.get<{ jobs: Job[]; summary: JobsSummary }>('/api/jobs/');
      setJobs(data.jobs);
      setSummary(data.summary);
    } catch (err) {
      // silently fail
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchJobs(); }, []);

  // Auto-refresh every 10s if there are running jobs
  useEffect(() => {
    if (summary.running > 0) {
      const interval = setInterval(fetchJobs, 10000);
      return () => clearInterval(interval);
    }
  }, [summary.running]);

  const filteredJobs = jobs.filter(j => {
    if (activeFilter !== 'all') {
      if (activeFilter === 'pending' && !['pending', 'queued', 'ready'].includes(j.status)) return false;
      if (activeFilter === 'running' && j.status !== 'running') return false;
      if (activeFilter === 'completed' && j.status !== 'completed') return false;
      if (activeFilter === 'failed' && j.status !== 'failed') return false;
    }
    if (searchQuery) {
      return j.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
             j.type.toLowerCase().includes(searchQuery.toLowerCase());
    }
    return true;
  });

  const formatTime = (iso: string | null) => {
    if (!iso) return '—';
    const d = new Date(iso);
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'Just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    if (days < 7) return `${days}d ago`;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const getDuration = (start: string | null, end: string | null) => {
    if (!start) return '—';
    const s = new Date(start).getTime();
    const e = end ? new Date(end).getTime() : Date.now();
    const sec = Math.floor((e - s) / 1000);
    if (sec < 60) return `${sec}s`;
    if (sec < 3600) return `${Math.floor(sec / 60)}m ${sec % 60}s`;
    return `${Math.floor(sec / 3600)}h ${Math.floor((sec % 3600) / 60)}m`;
  };

  const handleJobClick = (job: Job) => {
    if (job.type === 'assessment') {
      if (job.status === 'completed') navigate(`/assessments/${job.resource_id}/report`);
      else navigate('/assessments');
    } else {
      navigate('/migrations');
    }
  };

  return (
    <div className="jobs-page">
      <div className="jobs-header">
        <div className="jobs-title-row">
          <h1 className="jobs-title">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="10" cy="10" r="7" />
              <path d="M10 6v4l3 2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {t('jobs.title')}
          </h1>
          <button className="jobs-refresh-btn" onClick={fetchJobs} title="Refresh">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M2 8a6 6 0 0111.5-2.5M14 8a6 6 0 01-11.5 2.5" strokeLinecap="round" />
              <path d="M14 2v4h-4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>

        {/* Summary cards */}
        <div className="jobs-summary">
          {[
            { label: t('jobs.all'), value: summary.total, color: '#374151' },
            { label: t('jobs.running'), value: summary.running, color: '#2563EB' },
            { label: t('jobs.completed'), value: summary.completed, color: '#059669' },
            { label: t('jobs.failed'), value: summary.failed, color: '#DC2626' },
            { label: t('jobs.pending'), value: summary.pending, color: '#6B7280' },
          ].map(s => (
            <div key={s.label} className="jobs-summary-card">
              <span className="jobs-summary-value" style={{ color: s.color }}>{s.value}</span>
              <span className="jobs-summary-label">{s.label}</span>
            </div>
          ))}
        </div>

        {/* Filter tabs + search */}
        <div className="jobs-controls">
          <div className="jobs-filter-tabs">
            {([
              { id: 'all' as FilterTab, label: t('jobs.all') },
              { id: 'running' as FilterTab, label: t('jobs.running') },
              { id: 'completed' as FilterTab, label: t('jobs.completed') },
              { id: 'failed' as FilterTab, label: t('jobs.failed') },
              { id: 'pending' as FilterTab, label: t('jobs.pending') },
            ]).map(tab => (
              <button key={tab.id}
                className={`jobs-filter-tab ${activeFilter === tab.id ? 'active' : ''}`}
                onClick={() => setActiveFilter(tab.id)}>
                {tab.label}
              </button>
            ))}
          </div>
          <div className="jobs-search">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="#9CA3AF" strokeWidth="2">
              <circle cx="7" cy="7" r="5" /><path d="M11 11l3 3" strokeLinecap="round" />
            </svg>
            <input type="text" placeholder={t('jobs.search')} value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)} />
          </div>
        </div>
      </div>

      {/* Jobs table */}
      <div className="jobs-table-container">
        {loading ? (
          <div className="jobs-loading"><span className="jobs-spinner" /> {t('jobs.loading')}</div>
        ) : filteredJobs.length === 0 ? (
          <div className="jobs-empty">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="#D1D5DB" strokeWidth="1.5">
              <circle cx="24" cy="24" r="18" />
              <path d="M24 14v10l7 4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <p>{t('jobs.noJobs')}{activeFilter !== 'all' ? ` (${activeFilter})` : ''}</p>
          </div>
        ) : (
          <table className="jobs-table">
            <thead>
              <tr>
                <th>{t('jobs.name')}</th>
                <th>{t('jobs.type')}</th>
                <th>{t('jobs.status')}</th>
                <th>{t('jobs.progress')}</th>
                <th>{t('jobs.startedAt')}</th>
                <th>{t('jobs.duration')}</th>
                <th>{t('connections.details')}</th>
              </tr>
            </thead>
            <tbody>
              {filteredJobs.map(job => (
                <tr key={job.id} className="jobs-row" onClick={() => handleJobClick(job)}>
                  <td className="jobs-td-name">{job.name}</td>
                  <td>
                    <span className={`jobs-type-badge ${job.type}`}>
                      {job.type === 'assessment' ? (
                        <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <path d="M8 2L3 5v3c0 3 2 5 5 5.5 3-.5 5-2.5 5-5.5V5l-5-3z" />
                        </svg>
                      ) : (
                        <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <path d="M2 8h12M11 5l3 3-3 3" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      )}
                      {job.type === 'assessment' ? t('dashboard.assessments') : t('dashboard.migrations')}
                    </span>
                  </td>
                  <td><span className={`jobs-status ${job.status}`}>{job.status}</span></td>
                  <td>
                    <div className="jobs-progress">
                      <div className="jobs-progress-track">
                        <div className={`jobs-progress-fill ${job.status}`} style={{ width: `${job.progress}%` }} />
                      </div>
                      <span className="jobs-progress-text">{job.progress}%</span>
                    </div>
                  </td>
                  <td className="jobs-td-time">{formatTime(job.started_at)}</td>
                  <td className="jobs-td-time">{getDuration(job.started_at, job.completed_at)}</td>
                  <td className="jobs-td-details">
                    {job.type === 'assessment' ? (
                      <span>{job.details.tables} tables, {job.details.size_mb} MB</span>
                    ) : (
                      <span>{job.details.source || '—'} → {job.details.target || '—'}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
