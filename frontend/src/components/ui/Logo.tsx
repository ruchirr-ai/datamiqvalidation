import React from 'react';
import { PaperAirplaneIcon } from '@heroicons/react/24/outline';
import './Logo.css';

interface LogoProps {
  size?: number;
  showText?: boolean;
  className?: string;
  animate?: boolean;
}

export const Logo: React.FC<LogoProps> = ({ 
  size = 32, 
  showText = true,
  className = '',
  animate = false
}) => {
  // Reduce icon size to 75% of the specified size
  const iconSize = Math.round(size * 0.75);
  
  return (
    <div className={`logo ${className}`} style={{ 
      display: 'flex', 
      alignItems: 'center',
      gap: '4px'
    }}>
      {/* Paper airplane from Heroicons - represents data migration/sending */}
      <div 
        style={{ 
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: `${size}px`,
          height: `${size}px`,
          flexShrink: 0,
          marginTop: '-7px',
          position: 'relative',
          overflow: 'visible'
        }}
      >
        <PaperAirplaneIcon 
          className={animate ? 'logo__plane--animated' : ''}
          width={iconSize}
          height={iconSize}
          strokeWidth={2}
          style={{ 
            color: 'var(--color-primary)',
            transform: 'rotate(-30deg)',
            position: 'relative',
            zIndex: 1
          }}
        />
      </div>
      {showText && (
        <span style={{ 
          fontSize: '17px',
          fontWeight: 600,
          color: 'var(--color-primary)',
          whiteSpace: 'nowrap',
          lineHeight: `${size}px`,
          display: 'flex',
          alignItems: 'center',
          fontFamily: '"Google Sans Flex", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif'
        }}>
          DataMIQ
        </span>
      )}
    </div>
  );
};
