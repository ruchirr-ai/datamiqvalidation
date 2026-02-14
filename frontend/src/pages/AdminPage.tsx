import React, { useState } from 'react';
import { Users } from 'lucide-react';
import { FaAws } from 'react-icons/fa';
import { MdOutlineDatasetLinked } from 'react-icons/md';
import { DatabaseFieldConfigPage } from './DatabaseFieldConfigPage';
import './AdminPage.css';

type AdminSection = 'sources' | 'targets' | 'aws-accounts' | 'users';

export const AdminPage: React.FC = () => {
  const [activeSection, setActiveSection] = useState<AdminSection>('sources');
  const [isDataConnectionsExpanded, setIsDataConnectionsExpanded] = useState(true);

  const renderContent = () => {
    switch (activeSection) {
      case 'sources':
        return <DatabaseFieldConfigPage />;
      case 'targets':
        return (
          <div className="admin-content">
            <div className="admin-content-header">
              <h1>Targets</h1>
            </div>
            <div className="admin-content-body">
              {/* Targets content will go here */}
              <p>Target database connections management</p>
            </div>
          </div>
        );
      case 'aws-accounts':
        return (
          <div className="admin-content">
            <div className="admin-content-header">
              <h1>AWS Accounts</h1>
            </div>
            <div className="admin-content-body">
              {/* AWS Accounts content will go here */}
              <p>AWS Accounts management interface</p>
            </div>
          </div>
        );
      case 'users':
        return (
          <div className="admin-content">
            <div className="admin-content-header">
              <h1>Users</h1>
            </div>
            <div className="admin-content-body">
              {/* Users content will go here */}
              <p>Users management interface</p>
            </div>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className="admin-page">
      {/* Secondary Left Pane */}
      <div className="admin-sidebar">
        <nav className="admin-sidebar-nav">
          <div className="admin-nav-group">
            <button
              className="admin-nav-group-label"
              onClick={() => setIsDataConnectionsExpanded(!isDataConnectionsExpanded)}
            >
              <MdOutlineDatasetLinked size={17} className="admin-nav-icon" />
              <span>Data Connections</span>
            </button>
            
            {isDataConnectionsExpanded && (
              <div className="admin-nav-submenu">
                <button
                  className={`admin-nav-item submenu-item ${activeSection === 'sources' ? 'active' : ''}`}
                  onClick={() => setActiveSection('sources')}
                >
                  <span>Sources</span>
                </button>
                <button
                  className={`admin-nav-item submenu-item ${activeSection === 'targets' ? 'active' : ''}`}
                  onClick={() => setActiveSection('targets')}
                >
                  <span>Targets</span>
                </button>
              </div>
            )}
          </div>
          
          <button
            className={`admin-nav-item ${activeSection === 'aws-accounts' ? 'active' : ''}`}
            onClick={() => setActiveSection('aws-accounts')}
          >
            <FaAws size={17} className="admin-nav-icon" />
            <span>AWS Accounts</span>
          </button>
          <button
            className={`admin-nav-item ${activeSection === 'users' ? 'active' : ''}`}
            onClick={() => setActiveSection('users')}
          >
            <Users size={17} className="admin-nav-icon" />
            <span>Users</span>
          </button>
        </nav>
      </div>

      {/* Right Content Area */}
      <div className="admin-main">
        {renderContent()}
      </div>
    </div>
  );
};
