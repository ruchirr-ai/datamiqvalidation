import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import './WorkspacesPage.css';

interface WorkspaceStats {
  connections: number;
  assessments: number;
  migrations: number;
  conversions: number;
  members: number;
}

interface Workspace {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  organization_id: number;
  role: string;
  created_at: string | null;
  is_active: boolean;
  stats: WorkspaceStats;
}

export const WorkspacesPage: React.FC = () => {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchWorkspaces = async () => {
      try {
        const data = await api.get<Workspace[]>('/api/workspaces/');
        setWorkspaces(data);
      } catch (err) {
        console.error('Failed to load workspaces:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchWorkspaces();
  }, []);

  const formatDate = (ts: string | null) => {
    if (!ts) return '—';
    return new Date(ts).toLocaleDateString('en-IN', {
      timeZone: 'Asia/Kolkata',
      year: 'numeric', month: 'short', day: 'numeric',
    });
  };

  if (loading) {
    return (
      <div className="workspaces-page">
        <div className="workspaces-loading">
          <span className="ws-spinner" />
          Loading workspaces...
        </div>
      </div>
    );
  }

  return (
    <div className="workspaces-page">
      <div className="workspaces-header">
        <h1 className="workspaces-title">
          <svg width="22" height="22" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M3 7h14M3 7l2-4h10l2 4M3 7v9a2 2 0 002 2h10a2 2 0 002-2V7" />
          </svg>
          Workspaces
        </h1>
        <p className="workspaces-subtitle">Manage your project workspaces and team access</p>
      </div>

      <div className="workspaces-grid">
        {workspaces.map((ws) => (
          <div className="workspace-card" key={ws.id}>
            <div className="workspace-card-header">
              <div className="workspace-card-info">
                <div className="workspace-icon">
                  <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M3 7h14M3 7l2-4h10l2 4M3 7v9a2 2 0 002 2h10a2 2 0 002-2V7" />
                  </svg>
                </div>
                <div>
                  <h3 className="workspace-name">{ws.name}</h3>
                  <span className="workspace-slug">/{ws.slug}</span>
                </div>
              </div>
              <span className={`workspace-role-badge ${ws.role}`}>{ws.role}</span>
            </div>

            {ws.description && (
              <p className="workspace-description">{ws.description}</p>
            )}

            <div className="workspace-stats">
              <div className="workspace-stat">
                <div className="workspace-stat-value">{ws.stats.connections}</div>
                <div className="workspace-stat-label">Connections</div>
              </div>
              <div className="workspace-stat">
                <div className="workspace-stat-value">{ws.stats.assessments}</div>
                <div className="workspace-stat-label">Assessments</div>
              </div>
              <div className="workspace-stat">
                <div className="workspace-stat-value">{ws.stats.migrations}</div>
                <div className="workspace-stat-label">Migrations</div>
              </div>
              <div className="workspace-stat">
                <div className="workspace-stat-value">{ws.stats.conversions}</div>
                <div className="workspace-stat-label">Conversions</div>
              </div>
              <div className="workspace-stat">
                <div className="workspace-stat-value">{ws.stats.members}</div>
                <div className="workspace-stat-label">Members</div>
              </div>
            </div>

            <div className="workspace-card-footer">
              <span className="workspace-created">Created {formatDate(ws.created_at)}</span>
              {ws.is_active && (
                <span className="workspace-active-badge">
                  <span className="workspace-active-dot" />
                  Active
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
