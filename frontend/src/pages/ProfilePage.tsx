import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useLanguage } from '../contexts/LanguageContext';
import { useTheme } from '../contexts/ThemeContext';
import { LANGUAGES } from '../contexts/LanguageContext';
import './ProfilePage.css';

export const ProfilePage: React.FC = () => {
  const { user } = useAuth();
  const { t, language, setLanguage } = useLanguage();
  const { theme } = useTheme();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const handlePasswordChange = (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setToast({ message: t('profile.passwordMismatch'), type: 'error' });
      return;
    }
    if (newPassword.length < 6) {
      setToast({ message: t('profile.passwordTooShort'), type: 'error' });
      return;
    }
    setToast({ message: t('profile.passwordChanged'), type: 'success' });
    setCurrentPassword(''); setNewPassword(''); setConfirmPassword('');
    setTimeout(() => setToast(null), 3000);
  };

  const initials = user?.username ? user.username.slice(0, 2).toUpperCase() : 'U';

  return (
    <div className="profile-page">
      {toast && (
        <div className={`profile-toast profile-toast--${toast.type}`} onClick={() => setToast(null)}>
          {toast.message}
        </div>
      )}

      <div className="profile-header">
        <h1 className="profile-title">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
            <circle cx="10" cy="7" r="4" />
            <path d="M3 17c0-3 3-5 7-5s7 2 7 5" strokeLinecap="round" />
          </svg>
          {t('profile.title')}
        </h1>
        <p className="profile-subtitle">{t('profile.subtitle')}</p>
      </div>

      <div className="profile-content">
        {/* User Info Card */}
        <div className="profile-card">
          <div className="profile-card-header">{t('profile.userInfo')}</div>
          <div className="profile-user-section">
            <div className="profile-avatar">{initials}</div>
            <div className="profile-user-details">
              <div className="profile-field">
                <label>{t('profile.username')}</label>
                <span>{user?.username || '—'}</span>
              </div>
              <div className="profile-field">
                <label>{t('profile.role')}</label>
                <span className="profile-role-badge">{user?.role || 'member'}</span>
              </div>
              <div className="profile-field">
                <label>{t('profile.theme')}</label>
                <span>{theme === 'dark' ? t('sidebar.darkMode') : t('sidebar.lightMode')}</span>
              </div>
              <div className="profile-field">
                <label>{t('profile.language')}</label>
                <span>{LANGUAGES.find(l => l.code === language)?.label || language}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Language Preference */}
        <div className="profile-card">
          <div className="profile-card-header">{t('profile.preferences')}</div>
          <div className="profile-pref-section">
            <div className="profile-field">
              <label>{t('profile.selectLanguage')}</label>
              <select
                className="profile-select"
                value={language}
                onChange={(e) => setLanguage(e.target.value as any)}
              >
                {LANGUAGES.map(l => (
                  <option key={l.code} value={l.code}>{l.flag} {l.label} ({l.labelEn})</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Change Password */}
        <div className="profile-card">
          <div className="profile-card-header">{t('profile.changePassword')}</div>
          <form className="profile-password-form" onSubmit={handlePasswordChange}>
            <div className="profile-form-field">
              <label>{t('profile.currentPassword')}</label>
              <input type="password" value={currentPassword} onChange={e => setCurrentPassword(e.target.value)} placeholder="••••••••" />
            </div>
            <div className="profile-form-field">
              <label>{t('profile.newPassword')}</label>
              <input type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} placeholder="••••••••" />
            </div>
            <div className="profile-form-field">
              <label>{t('profile.confirmPassword')}</label>
              <input type="password" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} placeholder="••••••••" />
            </div>
            <button type="submit" className="profile-save-btn">{t('profile.updatePassword')}</button>
          </form>
        </div>
      </div>
    </div>
  );
};
