import React, { useState } from 'react';
import { Sidebar } from './Sidebar';
import './MainLayout.css';

interface NavigationItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  path: string;
  requiredRole?: string;
}

interface User {
  username: string;
  role: string;
  avatar?: string;
}

interface MainLayoutProps {
  children: React.ReactNode;
  navigationItems: NavigationItem[];
  currentPath: string;
  user?: User;
  onNavigate: (path: string) => void;
  onLogout: () => void;
}

export const MainLayout: React.FC<MainLayoutProps> = ({
  children,
  navigationItems,
  currentPath,
  user,
  onNavigate,
  onLogout
}) => {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  return (
    <div className="main-layout">
      <Sidebar
        isCollapsed={isSidebarCollapsed}
        onToggle={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
        currentPath={currentPath}
        onNavigate={onNavigate}
        onLogout={onLogout}
        user={user || { username: 'Guest', role: 'user' }}
      />

      <div className={`main-content ${isSidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
        <main className="page-content">
          {children}
        </main>
      </div>
    </div>
  );
};
