import React from 'react';
import './Card.css';

export interface CardProps {
  children: React.ReactNode;
  padding?: 'none' | 'sm' | 'md' | 'lg';
  shadow?: 'none' | 'sm' | 'md' | 'lg';
  className?: string;
  onClick?: () => void;
  style?: React.CSSProperties;
}

export const Card: React.FC<CardProps> = ({
  children,
  padding = 'md',
  shadow = 'base',
  className = '',
  onClick,
  style
}) => {
  const classes = [
    'card',
    `card--padding-${padding}`,
    `card--shadow-${shadow}`,
    className
  ].filter(Boolean).join(' ');

  return (
    <div 
      className={classes} 
      onClick={onClick} 
      style={style}
    >
      {children}
    </div>
  );
};
