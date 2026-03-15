import React from 'react';
import { Card } from '../components/ui/Card';
import { useLanguage } from '../contexts/LanguageContext';

export const AdministrationPage: React.FC = () => {
  const { t } = useLanguage();
  return (
    <div>
      <h1>{t('nav.admin')}</h1>
      <Card padding="lg">
        <p>{t('admin.settingsDesc')}</p>
      </Card>
    </div>
  );
};
