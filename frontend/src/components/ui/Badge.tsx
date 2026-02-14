import React from 'react';
import './Badge.css';

export interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info';
  size?: 'sm' | 'md';
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'default',
  size = 'md',
  className = ''
}) => {
  const classes = [
    'badge',
    `badge--${variant}`,
    `badge--${size}`,
    className
  ].filter(Boolean).join(' ');

  return <span className={classes}>{children}</span>;
};
