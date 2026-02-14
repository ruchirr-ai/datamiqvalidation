import React from 'react';
import { Card } from '../components/ui/Card';

export const AdministrationPage: React.FC = () => {
  return (
    <div>
      <h1>Administration</h1>
      <Card padding="lg">
        <p>Administration settings (Admin only)</p>
      </Card>
    </div>
  );
};
