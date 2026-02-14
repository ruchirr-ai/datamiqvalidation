import React from 'react';
import { Card } from '../components/ui/Card';

export const DashboardPage: React.FC = () => {
  return (
    <div>
      <h1>Dashboard</h1>
      <Card padding="lg">
        <p>Welcome to DataMIQ Dashboard</p>
      </Card>
    </div>
  );
};
