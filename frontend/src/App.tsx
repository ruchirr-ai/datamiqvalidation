import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ProtectedRoute } from './components/auth/ProtectedRoute';
import { MainLayout } from './components/layout/MainLayout';
import { ChatAgent } from './components/ChatAgent/ChatAgent';
import { LoginScreen } from './pages/LoginScreen';
import { DashboardPage } from './pages/DashboardPage';
import { ConnectionsPage } from './pages/ConnectionsPage';
import { MigrationsPage } from './pages/MigrationsPage';
import { JobsPage } from './pages/JobsPage';
import { AdministrationPage } from './pages/AdministrationPage';
import { AdminPage } from './pages/AdminPage';
import { DatabaseFieldConfigPage } from './pages/DatabaseFieldConfigPage';
import { AssessmentsPage } from './pages/AssessmentsPage';
import { AssessmentReportPage } from './pages/AssessmentReportPage';
import { SchemaAnalysisPage } from './pages/assessments/SchemaAnalysisPage';
import { CompatibilityCheckPage } from './pages/assessments/CompatibilityCheckPage';
import { AssessmentReportsPage } from './pages/assessments/AssessmentReportsPage';
import { DataProfilingPage } from './pages/assessments/DataProfilingPage';
import { BQRedshiftMigrationsPage } from './pages/migrations/BQRedshiftMigrationsPage';
import { CreateMigrationWizard } from './components/migrations/CreateMigrationWizard';
import { PathwayATestPage } from './pages/PathwayATestPage';
import { BQExportTestPage } from './pages/BQExportTestPage';
import './styles/global.css';

// Navigation items configuration
const navigationItems = [
  {
    id: 'dashboard',
    label: 'Dashboard',
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M3 4H9V10H3V4Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M11 4H17V7H11V4Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M11 9H17V16H11V9Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M3 12H9V16H3V12Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
    path: '/dashboard',
    requiredRole: 'member'
  },
  {
    id: 'connections',
    label: 'Connections',
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M4 7H16M4 13H16M7 3V17M13 3V17" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      </svg>
    ),
    path: '/connections',
    requiredRole: 'member'
  },
  {
    id: 'migrations',
    label: 'Migrations',
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M4 10H16M16 10L12 6M16 10L12 14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
    path: '/migrations',
    requiredRole: 'member'
  },
  {
    id: 'jobs',
    label: 'Jobs',
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M10 4V10L14 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        <circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="2"/>
      </svg>
    ),
    path: '/jobs',
    requiredRole: 'member'
  },
  {
    id: 'administration',
    label: 'Administration',
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M10 2L3 7V13C3 16.3137 6.13401 19 10 19C13.866 19 17 16.3137 17 13V7L10 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
    path: '/administration',
    requiredRole: 'admin'
  },
  {
    id: 'admin',
    label: 'Admin',
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
        <path d="M10 11C12.2091 11 14 9.20914 14 7C14 4.79086 12.2091 3 10 3C7.79086 3 6 4.79086 6 7C6 9.20914 7.79086 11 10 11Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M3 17C3 14.2386 5.68629 12 9 12H11C14.3137 12 17 14.2386 17 17" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
    path: '/admin',
    requiredRole: 'admin'
  }
];

// App content with routing
const AppContent: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();

  const handleNavigate = (path: string) => {
    navigate(path);
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  // Determine current page context for ChatAgent
  const getCurrentPageContext = () => {
    const path = location.pathname;
    if (path.includes('/assessments')) return 'assessments';
    if (path.includes('/connections')) return 'connections';
    if (path.includes('/migrations')) return 'migrations';
    if (path.includes('/jobs')) return 'jobs';
    if (path.includes('/dashboard')) return 'dashboard';
    return 'dashboard';
  };

  return (
    <>
      <Routes>
        <Route path="/login" element={<LoginScreen />} />
        
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <MainLayout
                navigationItems={navigationItems}
                currentPath={location.pathname}
                user={user ? {
                  username: user.username,
                  role: user.role,
                  avatar: undefined
                } : undefined}
                onNavigate={handleNavigate}
                onLogout={handleLogout}
              >
                <Routes>
                  <Route path="/" element={<Navigate to="/dashboard" replace />} />
                  <Route path="/dashboard" element={<DashboardPage />} />
                  <Route path="/connections" element={<ConnectionsPage />} />
                  <Route path="/assessments" element={<AssessmentsPage />} />
                  <Route path="/assessments/:assessmentId/report" element={<AssessmentReportPage />} />
                  <Route path="/assessments/schema-analysis" element={<SchemaAnalysisPage />} />
                  <Route path="/assessments/compatibility" element={<CompatibilityCheckPage />} />
                  <Route path="/assessments/reports" element={<AssessmentReportsPage />} />
                  <Route path="/assessments/data-profiling" element={<DataProfilingPage />} />
                  <Route path="/migrations" element={<MigrationsPage />} />
                  <Route path="/migrations/bq-redshift" element={<BQRedshiftMigrationsPage />} />
                  <Route path="/migrations/create" element={<CreateMigrationWizard />} />
                  <Route path="/migrations/pathway-a-test" element={<PathwayATestPage />} />
                  <Route path="/migrations/bq-export-test" element={<BQExportTestPage />} />
                  <Route path="/jobs" element={<JobsPage />} />
                  <Route
                    path="/administration"
                    element={
                      <ProtectedRoute requiredRole="admin">
                        <AdministrationPage />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/admin"
                    element={
                      <ProtectedRoute requiredRole="admin">
                        <AdminPage />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/admin/data-connections/sources"
                    element={
                      <ProtectedRoute requiredRole="admin">
                        <DatabaseFieldConfigPage />
                      </ProtectedRoute>
                    }
                  />
                </Routes>
              </MainLayout>
            </ProtectedRoute>
          }
        />
      </Routes>

      {/* ChatAgent - Show on all authenticated pages except login */}
      {user && location.pathname !== '/login' && (
        <ChatAgent 
          currentPage={getCurrentPageContext()}
          hasAssessments={true}
        />
      )}
    </>
  );
};

// Main App component
const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </BrowserRouter>
  );
};

export default App;
