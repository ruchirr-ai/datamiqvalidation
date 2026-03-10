import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';

interface WorkspaceInfo {
  id: number;
  name: string;
  slug: string;
}

interface WorkspaceContextType {
  workspaces: WorkspaceInfo[];
  selectedWorkspaceId: number | null; // null means "All Workspaces"
  selectedWorkspaceName: string;
  setSelectedWorkspaceId: (id: number | null) => void;
  refreshWorkspaces: () => Promise<void>;
}

const WorkspaceContext = createContext<WorkspaceContextType>({
  workspaces: [],
  selectedWorkspaceId: null,
  selectedWorkspaceName: 'All Workspaces',
  setSelectedWorkspaceId: () => {},
  refreshWorkspaces: async () => {},
});

export const useWorkspace = () => useContext(WorkspaceContext);

export const WorkspaceProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [workspaces, setWorkspaces] = useState<WorkspaceInfo[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceIdState] = useState<number | null>(() => {
    try {
      const saved = localStorage.getItem('datamiq_selected_workspace');
      return saved ? JSON.parse(saved) : null;
    } catch { return null; }
  });

  const fetchWorkspaces = useCallback(async () => {
    // Only fetch if user is authenticated
    const token = localStorage.getItem('auth_token');
    if (!token) return;
    try {
      const data = await api.get<any[]>('/api/workspaces/');
      setWorkspaces(data.map(w => ({ id: w.id, name: w.name, slug: w.slug })));
    } catch (err) {
      // silently fail
    }
  }, []);

  useEffect(() => { fetchWorkspaces(); }, [fetchWorkspaces]);

  const setSelectedWorkspaceId = (id: number | null) => {
    setSelectedWorkspaceIdState(id);
    localStorage.setItem('datamiq_selected_workspace', JSON.stringify(id));
  };

  const selectedWorkspaceName = selectedWorkspaceId
    ? workspaces.find(w => w.id === selectedWorkspaceId)?.name || 'Workspace'
    : 'All Workspaces';

  return (
    <WorkspaceContext.Provider value={{
      workspaces,
      selectedWorkspaceId,
      selectedWorkspaceName,
      setSelectedWorkspaceId,
      refreshWorkspaces: fetchWorkspaces,
    }}>
      {children}
    </WorkspaceContext.Provider>
  );
};
