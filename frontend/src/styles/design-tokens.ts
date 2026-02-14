/**
 * Design Tokens
 * Centralized design system values for DataMIQ
 */

export const colors = {
  // Primary Brand Colors
  blue1: '#003087',
  blue2: '#0070E0',
  blue3: '#001C64',
  gold: '#FFD140',
  slate: '#001435',
  offWhite: '#FAF8F5',
  white: '#FFFFFF',
  
  // Grayscale
  black: '#000000',
  gray900: '#1A1A1A',
  gray800: '#2D2D2D',
  gray700: '#404040',
  gray600: '#666666',
  gray500: '#808080',
  gray400: '#999999',
  gray300: '#CCCCCC',
  gray200: '#E5E5E5',
  gray100: '#F5F5F5',
  
  // Semantic Colors
  success: '#10B981',
  warning: '#F59E0B',
  error: '#EF4444',
  info: '#3B82F6',
  
  // UI States
  hover: '#0070E0',
  active: '#001C64',
  disabled: '#CCCCCC',
  focus: '#0070E0',
} as const;

export const spacing = {
  xs: '4px',
  sm: '8px',
  md: '12px',
  base: '16px',
  lg: '24px',
  xl: '32px',
  '2xl': '48px',
  '3xl': '64px',
  '4xl': '96px',
} as const;

export const typography = {
  fontFamily: {
    sans: '"Google Sans Flex", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    mono: '"Google Sans Code", "Courier New", monospace',
  },
  fontSize: {
    xs: '12px',
    sm: '14px',
    base: '16px',
    lg: '18px',
    xl: '20px',
    '2xl': '24px',
    '3xl': '30px',
    '4xl': '36px',
    '5xl': '48px',
  },
  fontWeight: {
    light: 300,
    normal: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
  },
  lineHeight: {
    tight: 1.25,
    normal: 1.5,
    relaxed: 1.75,
  },
} as const;

export const borderRadius = {
  none: '0',
  sm: '4px',
  base: '6px',
  md: '8px',
  lg: '12px',
  xl: '16px',
  full: '9999px',
} as const;

export const shadows = {
  none: 'none',
  sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
  base: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
  md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
  lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
  xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
  '2xl': '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
  inner: 'inset 0 2px 4px 0 rgba(0, 0, 0, 0.06)',
} as const;

export const breakpoints = {
  mobile: '320px',
  tablet: '768px',
  laptop: '1024px',
  desktop: '1280px',
  wide: '1536px',
} as const;

export const zIndex = {
  base: 0,
  dropdown: 1000,
  sticky: 1020,
  fixed: 1030,
  modalBackdrop: 1040,
  modal: 1050,
  popover: 1060,
  tooltip: 1070,
} as const;

export const transitions = {
  fast: '150ms ease-in-out',
  base: '200ms ease-in-out',
  slow: '300ms ease-in-out',
} as const;

// Export all tokens as a single object
export const tokens = {
  colors,
  spacing,
  typography,
  borderRadius,
  shadows,
  breakpoints,
  zIndex,
  transitions,
} as const;

export default tokens;
