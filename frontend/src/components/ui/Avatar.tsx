import React from 'react';
import './Avatar.css';

export interface AvatarProps {
  src?: string;
  alt?: string;
  name?: string;
  initials?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
}

export const Avatar: React.FC<AvatarProps> = ({
  src,
  alt = '',
  name,
  initials,
  size = 'md',
  className = ''
}) => {
  const classes = [
    'avatar',
    `avatar--${size}`,
    className
  ].filter(Boolean).join(' ');

  const getInitials = () => {
    if (initials) return initials.charAt(0).toUpperCase();
    if (name) return name.charAt(0).toUpperCase();
    if (alt) return alt.charAt(0).toUpperCase();
    return '?';
  };

  return (
    <div className={classes}>
      {src ? (
        <img src={src} alt={alt || name || 'Avatar'} className="avatar__image" />
      ) : (
        <span className="avatar__initials">{getInitials()}</span>
      )}
    </div>
  );
};
