import React from 'react';

interface Db2IconProps {
  size?: number;
  className?: string;
}

/** IBM Db2 logo icon — blue "Db2" text style */
export const Db2Icon: React.FC<Db2IconProps> = ({ size = 16, className }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
  >
    <rect width="24" height="24" rx="4" fill="#054ADA" />
    <text
      x="12"
      y="16.5"
      textAnchor="middle"
      fontFamily="Arial, Helvetica, sans-serif"
      fontWeight="700"
      fontSize="11"
      fill="white"
    >
      Db2
    </text>
  </svg>
);
