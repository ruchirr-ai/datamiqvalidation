import React, { useState } from 'react';
import { Cable, Sun, Moon, Globe } from 'lucide-react';
import { Logo } from '../ui/Logo';
import { useTheme } from '../../contexts/ThemeContext';
import { useLanguage, LANGUAGES } from '../../contexts/LanguageContext';
import './Sidebar.css';

interface NavItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  path: string;
  children?: NavItem[];
}

interface SidebarProps {
  isCollapsed: boolean;
  onToggle: () => void;
  currentPath: string;
  onNavigate: (path: string) => void;
  onLogout: () => void;
  user: {
    username: string;
    role: string;
    avatar?: string;
  };
}

export const Sidebar: React.FC<SidebarProps> = ({
  isCollapsed,
  onToggle,
  currentPath,
  onNavigate,
  onLogout,
  user
}) => {
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set(['monitoring']));
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const [isLangMenuOpen, setIsLangMenuOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [menuPositions, setMenuPositions] = useState<Record<string, number>>({});
  const { theme, toggleTheme } = useTheme();
  const { language, setLanguage, t } = useLanguage();

  // Detect mobile screen size
  React.useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth <= 767);
    };
    
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);
  
  // Calculate menu positions for expanded items
  const updateMenuPosition = (itemId: string, element: HTMLButtonElement | null) => {
    if (element && isMobile) {
      const rect = element.getBoundingClientRect();
      const newPosition = rect.top;
      
      // Only update if position has changed significantly (more than 1px)
      setMenuPositions(prev => {
        if (Math.abs((prev[itemId] || 0) - newPosition) > 1) {
          return { ...prev, [itemId]: newPosition };
        }
        return prev;
      });
    }
  };

  const toggleGroup = (groupId: string) => {
    setExpandedGroups(prev => {
      const newSet = new Set(prev);
      
      // On mobile, only allow one expanded group at a time
      if (isMobile) {
        if (newSet.has(groupId)) {
          newSet.delete(groupId);
        } else {
          newSet.clear(); // Close all other groups
          newSet.add(groupId);
        }
      } else {
        // On desktop, allow multiple expanded groups
        if (newSet.has(groupId)) {
          newSet.delete(groupId);
        } else {
          newSet.add(groupId);
        }
      }
      
      return newSet;
    });
  };

  const currentLang = LANGUAGES.find(l => l.code === language);

  const navigationItems: NavItem[] = [
    {
      id: 'dashboard',
      label: t('nav.dashboard'),
      icon: (
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
          <rect x="3" y="3" width="6" height="6" rx="1" />
          <rect x="11" y="3" width="6" height="6" rx="1" />
          <rect x="3" y="11" width="6" height="6" rx="1" />
          <rect x="11" y="11" width="6" height="6" rx="1" />
        </svg>
      ),
      path: '/dashboard'
    },
    {
      id: 'workspaces',
      label: t('nav.workspaces'),
      icon: (
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M3 7h14M3 7l2-4h10l2 4M3 7v9a2 2 0 002 2h10a2 2 0 002-2V7" />
        </svg>
      ),
      path: '/workspaces'
    },
    {
      id: 'connections',
      label: t('nav.connections'),
      icon: <Cable size={20} strokeWidth={1.5} />,
      path: '/connections'
    },
    {
      id: 'assessments',
      label: t('nav.assessments'),
      icon: (
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M9 2L3 6v4c0 4.5 3 7.5 6 8 3-.5 6-3.5 6-8V6l-6-4z" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M7 10l2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ),
      path: '/assessments',
      children: [
        { id: 'assess-1', label: t('nav.schemaAnalysis'), icon: null, path: '/assessments/schema-analysis' },
        { id: 'assess-2', label: t('nav.compatibilityCheck'), icon: null, path: '/assessments/compatibility' },
        { id: 'assess-3', label: t('nav.assessmentReports'), icon: null, path: '/assessments/reports' }
      ]
    },
    {
      id: 'migrations',
      label: t('nav.migrations'),
      icon: (
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M3 10h14M14 6l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ),
      path: '/migrations'
    },
    {
      id: 'jobs',
      label: t('nav.jobs'),
      icon: (
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
          <circle cx="10" cy="10" r="7" />
          <path d="M10 6v4l3 2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ),
      path: '/jobs',
      children: [
        { id: 'job-1', label: t('nav.running'), icon: null, path: '/jobs/running' },
        { id: 'job-2', label: t('nav.queued'), icon: null, path: '/jobs/queued' },
        { id: 'job-3', label: t('nav.history'), icon: null, path: '/jobs/history' }
      ]
    },
    {
      id: 'converter',
      label: t('nav.converter'),
      icon: (
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M7 5L3 10l4 5" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M13 5l4 5-4 5" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M11 3L9 17" strokeLinecap="round" />
        </svg>
      ),
      path: '/converter',
      children: [
        { id: 'conv-1', label: t('nav.quickConvert'), icon: null, path: '/converter' },
        { id: 'conv-2', label: t('nav.batch'), icon: null, path: '/converter/batch' }
      ]
    },
    {
      id: 'validations',
      label: t('nav.validations'),
      icon: (
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
          <rect x="3" y="2" width="14" height="16" rx="2" />
          <path d="M7 7l2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M7 13h6" strokeLinecap="round" />
        </svg>
      ),
      path: '/validations'
    },
    {
      id: 'monitoring',
      label: t('nav.monitoring'),
      icon: (
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M3 12l3-3 4 4 7-7" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M17 6v4h-4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ),
      path: '/monitoring',
      children: [
        { id: 'mon-1', label: t('nav.queryHistory'), icon: null, path: '/monitoring/query-history' },
        { id: 'mon-2', label: t('nav.copyHistory'), icon: null, path: '/monitoring/copy-history' },
        { id: 'mon-3', label: t('nav.taskHistory'), icon: null, path: '/monitoring/task-history' },
        { id: 'mon-4', label: t('nav.dynamicTables'), icon: null, path: '/monitoring/dynamic-tables' },
        { id: 'mon-5', label: t('nav.governance'), icon: null, path: '/monitoring/governance' }
      ]
    },
    {
      id: 'admin',
      label: t('nav.admin'),
      icon: (
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M10 2L3 6v4c0 4.5 3 7.5 7 8 4-.5 7-3.5 7-8V6l-7-4z" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ),
      path: '/admin'
    }
  ];

  const handleKeyDown = (e: React.KeyboardEvent, action: () => void) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      action();
    }
  };

  const renderNavItem = (item: NavItem, isChild: boolean = false) => {
    const isExpanded = expandedGroups.has(item.id);
    const hasChildren = item.children && item.children.length > 0;
    const isSelected = currentPath === item.path;
    
    // On mobile, always show children when expanded, regardless of isCollapsed prop
    const shouldShowChildren = hasChildren && isExpanded && (isMobile || !isCollapsed);

    return (
      <div key={item.id} className="nav-item-wrapper">
        <button
          ref={(el) => {
            if (!isChild && hasChildren && isExpanded) {
              updateMenuPosition(item.id, el);
            }
          }}
          className={`nav-item ${isSelected ? 'selected' : ''} ${isChild ? 'child' : ''}`}
          onClick={() => {
            if (hasChildren) {
              // For parent items with children, navigate to parent path AND toggle submenu
              onNavigate(item.path);
              toggleGroup(item.id);
            } else {
              onNavigate(item.path);
            }
          }}
          onKeyDown={(e) => handleKeyDown(e, () => {
            if (hasChildren) {
              onNavigate(item.path);
              toggleGroup(item.id);
            } else {
              onNavigate(item.path);
            }
          })}
          aria-label={item.label}
          aria-expanded={hasChildren ? isExpanded : undefined}
          aria-current={isSelected ? 'page' : undefined}
        >
          {!isChild && item.icon && (
            <span className="nav-icon" aria-hidden="true">
              {item.icon}
            </span>
          )}
          <span className="nav-label">{item.label}</span>
        </button>
        {shouldShowChildren && (
          <div 
            className="nav-children" 
            role="group"
            style={isMobile ? { top: `${menuPositions[item.id] || 0}px` } : undefined}
          >
            {item.children!.map(child => renderNavItem(child, true))}
          </div>
        )}
      </div>
    );
  };

  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  const handleUserMenuClick = () => {
    setIsUserMenuOpen(!isUserMenuOpen);
  };

  const handleMenuItemClick = (action: string) => {
    setIsUserMenuOpen(false);
    
    switch (action) {
      case 'profile':
        onNavigate('/profile');
        break;
      case 'support':
        onNavigate('/support');
        break;
      case 'documentation':
        window.open('/docs', '_blank');
        break;
      case 'privacy':
        window.open('https://datamiq.com/privacy', '_blank');
        break;
      case 'signout':
        onLogout();
        break;
    }
  };

  // Close menus when clicking outside
  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (isUserMenuOpen && !target.closest('.account-block') && !target.closest('.user-menu')) {
        setIsUserMenuOpen(false);
      }
      if (isLangMenuOpen && !target.closest('.sidebar-language-selector')) {
        setIsLangMenuOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isUserMenuOpen, isLangMenuOpen]);

  return (
    <aside className={`sidebar ${isCollapsed ? 'collapsed' : ''}`} role="navigation" aria-label="Main navigation">
      {/* Brand Header */}
      <div className="sidebar-header">
        <Logo size={28} showText={!isCollapsed && !isMobile} animate={!isCollapsed && !isMobile} />
        <button
          className="collapse-toggle"
          onClick={onToggle}
          aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-expanded={!isCollapsed}
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
            <path d={isCollapsed ? "M6 4l4 4-4 4" : "M10 4L6 8l4 4"} strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>

      {/* Navigation List */}
      <nav className="sidebar-nav" aria-label="Primary navigation">
        {navigationItems.map(item => renderNavItem(item))}
      </nav>

      {/* Sidebar Bottom Section */}
      <div className="sidebar-bottom">
        {/* Theme Toggle */}
        <div className="sidebar-theme-toggle">
          <button
            className="theme-toggle-btn"
            onClick={toggleTheme}
            aria-label={theme === 'light' ? t('sidebar.darkMode') : t('sidebar.lightMode')}
            title={theme === 'light' ? t('sidebar.darkMode') : t('sidebar.lightMode')}
          >
            {theme === 'light' ? (
              <Moon size={18} strokeWidth={1.5} />
            ) : (
              <Sun size={18} strokeWidth={1.5} />
            )}
            {!isCollapsed && (
              <span className="theme-toggle-label">
                {theme === 'light' ? t('sidebar.darkMode') : t('sidebar.lightMode')}
              </span>
            )}
          </button>
        </div>

        {/* Language Selector */}
        <div className="sidebar-language-selector">
          <button
            className="language-toggle-btn"
            onClick={() => setIsLangMenuOpen(!isLangMenuOpen)}
            aria-label={t('sidebar.language')}
            title={t('sidebar.language')}
          >
            <Globe size={18} strokeWidth={1.5} />
            {!isCollapsed && (
              <span className="language-toggle-label">
                {currentLang?.flag} {currentLang?.label}
              </span>
            )}
          </button>
          {isLangMenuOpen && (
            <div className="language-menu" role="menu">
              {LANGUAGES.map((lang) => (
                <button
                  key={lang.code}
                  className={`language-menu-item ${language === lang.code ? 'active' : ''}`}
                  onClick={() => {
                    setLanguage(lang.code);
                    setIsLangMenuOpen(false);
                  }}
                  role="menuitem"
                >
                  <span className="language-flag">{lang.flag}</span>
                  <span className="language-name">{lang.label}</span>
                  {language === lang.code && (
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M3 7l3 3 5-5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Account Block */}
      <div className="sidebar-footer">
        <button
          className="account-block"
          onClick={handleUserMenuClick}
          onKeyDown={(e) => handleKeyDown(e, handleUserMenuClick)}
          aria-label="User menu"
          aria-expanded={isUserMenuOpen}
          aria-haspopup="true"
        >
          <div className="account-avatar" aria-hidden="true">
            {user.avatar ? (
              <img src={user.avatar} alt="" />
            ) : (
              <span>{getInitials(user.username)}</span>
            )}
          </div>
          {!isCollapsed && (
            <>
              <div className="account-info">
                <div className="account-name">{user.username.toUpperCase()}</div>
                <div className="account-role">{user.role.charAt(0).toUpperCase() + user.role.slice(1).toLowerCase()}</div>
              </div>
              <svg
                className={`account-chevron ${isUserMenuOpen ? 'open' : ''}`}
                width="16"
                height="16"
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                aria-hidden="true"
              >
                <path d="M4 6l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </>
          )}
        </button>

        {/* User Menu Dropdown */}
        {isUserMenuOpen && (
          <div className="user-menu" role="menu">
            <button
              className="user-menu-item"
              onClick={() => handleMenuItemClick('profile')}
              role="menuitem"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                <circle cx="8" cy="5" r="2.5" />
                <path d="M3 14c0-2.5 2-4 5-4s5 1.5 5 4" strokeLinecap="round" />
              </svg>
              <span>{t('sidebar.myProfile')}</span>
            </button>

            <button
              className="user-menu-item"
              onClick={() => handleMenuItemClick('support')}
              role="menuitem"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                <circle cx="8" cy="8" r="6" />
                <path d="M8 12v.5M8 6a2 2 0 011.5 3.5L8 11" strokeLinecap="round" />
              </svg>
              <span>{t('sidebar.support')}</span>
            </button>

            <button
              className="user-menu-item"
              onClick={() => handleMenuItemClick('documentation')}
              role="menuitem"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M4 2h8a1 1 0 011 1v10a1 1 0 01-1 1H4a1 1 0 01-1-1V3a1 1 0 011-1z" />
                <path d="M6 6h4M6 9h4" strokeLinecap="round" />
              </svg>
              <span>{t('sidebar.documentation')}</span>
              <svg className="external-icon" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M9 3L3 9M9 3v4M9 3H5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>

            <div className="user-menu-divider" />

            <button
              className="user-menu-item"
              onClick={() => handleMenuItemClick('privacy')}
              role="menuitem"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M8 2L3 5v3c0 3 2 5 5 5.5 3-.5 5-2.5 5-5.5V5l-5-3z" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <span>{t('sidebar.privacyNotice')}</span>
              <svg className="external-icon" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M9 3L3 9M9 3v4M9 3H5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>

            <div className="user-menu-divider" />

            <button
              className="user-menu-item signout"
              onClick={() => handleMenuItemClick('signout')}
              role="menuitem"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M10 2h3a1 1 0 011 1v10a1 1 0 01-1 1h-3M6 11l4-3-4-3M10 8H2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <span>{t('sidebar.signOut')}</span>
            </button>
          </div>
        )}
      </div>
    </aside>
  );
};
