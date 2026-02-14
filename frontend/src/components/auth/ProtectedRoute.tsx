import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';

export interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: string;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  requiredRole
}) => {
  const { isAuthenticated, isLoading, user } = useAuth();
  const location = useLocation();

  // Show loading state while checking authentication
  if (isLoading) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh'
      }}>
        <div>Loading...</div>
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Check role-based access
  if (requiredRole && user) {
    const hasRequiredRole = checkRoleAccess(user.role, requiredRole);
    
    if (!hasRequiredRole) {
      return <Navigate to="/dashboard" replace />;
    }
  }

  return <>{children}</>;
};

// Helper function to check role hierarchy
function checkRoleAccess(userRole: string, requiredRole: string): boolean {
  const roleHierarchy: Record<string, number> = {
    'owner': 3,
    'admin': 2,
    'member': 1
  };

  const userLevel = roleHierarchy[userRole] || 0;
  const requiredLevel = roleHierarchy[requiredRole] || 0;

  return userLevel >= requiredLevel;
}
