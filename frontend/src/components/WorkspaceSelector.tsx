import React from 'react';
import { Select } from './ui';
import { useWorkspace } from '../contexts/WorkspaceContext';

export const WorkspaceSelector: React.FC = () => {
  const { workspaces, selectedWorkspaceId, setSelectedWorkspaceId } = useWorkspace();

  const options = [
    { value: 0, label: 'All Workspaces' },
    ...workspaces.map(ws => ({ value: ws.id, label: ws.name })),
  ];

  return (
    <Select
      value={selectedWorkspaceId ?? 0}
      onChange={(val) => setSelectedWorkspaceId(val === 0 ? null : Number(val))}
      options={options}
    />
  );
};
