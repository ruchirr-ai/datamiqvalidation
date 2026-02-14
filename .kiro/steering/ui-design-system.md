---
inclusion: fileMatch
fileMatchPattern: '**/*.{tsx,jsx,css,scss}'
---

# UI Design System

## Overview
A centralized design system ensures consistency, maintainability, and faster development. All UI components must be created in the component library and reused across the application.

## Component Library Structure

### Location
`frontend/src/components/ui/`

### Core Components
Create these reusable components in the UI bundle:

#### Buttons
- `Button.tsx` - Primary, secondary, tertiary variants
- `IconButton.tsx` - Button with icon only
- `ButtonGroup.tsx` - Group of related buttons

#### Forms
- `Input.tsx` - Text input with validation
- `Select.tsx` - Dropdown select
- `Checkbox.tsx` - Checkbox input
- `Radio.tsx` - Radio button
- `TextArea.tsx` - Multi-line text input
- `Form.tsx` - Form wrapper with validation
- `FormField.tsx` - Form field with label and error

#### Navigation
- `Link.tsx` - Styled link component
- `Breadcrumb.tsx` - Breadcrumb navigation
- `Tabs.tsx` - Tab navigation
- `Sidebar.tsx` - Sidebar navigation

#### Layout
- `Card.tsx` - Card container
- `Container.tsx` - Page container
- `Grid.tsx` - Grid layout
- `Stack.tsx` - Vertical/horizontal stack
- `Divider.tsx` - Visual divider

#### Feedback
- `Alert.tsx` - Alert messages
- `Toast.tsx` - Toast notifications
- `Modal.tsx` - Modal dialog
- `ProgressBar.tsx` - Progress indicator
- `Spinner.tsx` - Loading spinner
- `Badge.tsx` - Status badge

#### Data Display
- `Table.tsx` - Data table
- `List.tsx` - List component
- `EmptyState.tsx` - Empty state placeholder
- `Stat.tsx` - Statistic display

## Color System

### Core Colors (Based on Sidebar Implementation)
```css
/* Primary Brand Colors */
--color-primary: #2A6BDB;           /* Primary Blue - actions, selected text */
--color-primary-dark: #1E4FA0;      /* Darker Blue - gradients, hover states */

/* Backgrounds */
--color-bg-primary: #FAFAFA;        /* Main app background */
--color-bg-secondary: #F7F7F7;      /* Sidebar, secondary surfaces */
--color-bg-surface: #FFFFFF;        /* Cards, dropdowns, elevated surfaces */

/* Text Colors */
--color-text-primary: #1F2937;      /* Primary text - high contrast */
--color-text-secondary: #66748C;    /* Secondary text - muted */
--color-text-disabled: #9AA6B2;     /* Disabled text */

/* Interactive States */
--color-selected-bg: #D4E4FC;       /* Selected item background */
--color-hover-bg: #EFF5FF;          /* Hover state background */
--color-divider: #E5E7EB;           /* Borders, dividers */

/* Semantic Colors */
--color-success: #4CAF50;           /* Success states */
--color-error: #DC2626;             /* Error states, destructive actions */
--color-error-bg: #FEE2E2;          /* Error background (hover) */
--color-warning: #FFD140;           /* Warning states */
--color-info: #2A6BDB;              /* Info states */

/* Focus & Accessibility */
--color-focus-ring: rgba(42, 107, 219, 0.3);  /* Focus outline */
```

### Grey Scale (Extended)
```css
--color-grey-50: #FAFAFA;
--color-grey-100: #F7F7F7;
--color-grey-200: #EFF5FF;
--color-grey-300: #E5E7EB;
--color-grey-400: #D4E4FC;
--color-grey-500: #9AA6B2;
--color-grey-600: #66748C;
--color-grey-700: #1F2937;
--color-grey-800: #424242;
--color-grey-900: #212121;
```

### Usage Guidelines

**Primary Actions & Selected States**: Use `--color-primary` (#2A6BDB)
**Hover States**: Use `--color-hover-bg` (#EFF5FF) for backgrounds
**Selected Items**: Use `--color-selected-bg` (#D4E4FC) for backgrounds, `--color-primary` for text
**Primary Text**: Use `--color-text-primary` (#1F2937) for high contrast
**Secondary Text**: Use `--color-text-secondary` (#66748C) for muted text
**Backgrounds**: Use `--color-bg-primary` (#FAFAFA) for main, `--color-bg-secondary` (#F7F7F7) for sidebars
**Surfaces**: Use `--color-bg-surface` (#FFFFFF) for cards, modals, dropdowns
**Borders & Dividers**: Use `--color-divider` (#E5E7EB)
**Destructive Actions**: Use `--color-error` (#DC2626) with `--color-error-bg` (#FEE2E2) on hover

## Typography

### Font Family
Use Inter font family for all typography (NOT Google Sans):

```css
--font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
--font-family-code: 'Courier New', monospace;
```

**Import in HTML/CSS**:
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;450;500;550;600;700&display=swap" rel="stylesheet">
```

**Usage**:
- **Inter**: Use for ALL UI text, headings, body, buttons, labels, navigation
- **Monospace**: Use ONLY for code blocks and technical data

### Font Sizes (Based on Sidebar Implementation)
```css
--font-size-xs: 0.75rem;     /* 12px */
--font-size-sm: 0.8125rem;   /* 13px - navigation items, small text */
--font-size-base: 0.875rem;  /* 14px - body text, user menu items */
--font-size-md: 1rem;        /* 16px - brand text, headings */
--font-size-lg: 1.125rem;    /* 18px */
--font-size-xl: 1.25rem;     /* 20px - page titles */
--font-size-2xl: 1.5rem;     /* 24px */
--font-size-3xl: 1.875rem;   /* 30px */
--font-size-4xl: 2.25rem;    /* 36px */
```

### Font Weights (Precise Values)
```css
--font-weight-normal: 400;      /* Regular text */
--font-weight-450: 450;         /* Child menu items, user menu items */
--font-weight-medium: 500;      /* Parent menu items */
--font-weight-550: 550;         /* Selected child menu items */
--font-weight-semibold: 600;    /* Selected parent items, brand text, account name */
--font-weight-bold: 700;        /* Avatar initials */
```

### Typography Scale (Component-Specific)
```css
/* Navigation */
--nav-font-size: 13px;
--nav-font-weight: 500;              /* Parent items */
--nav-font-weight-child: 450;        /* Child items */
--nav-font-weight-selected: 600;     /* Selected parent */
--nav-font-weight-selected-child: 550; /* Selected child */

/* Brand */
--brand-font-size: 16px;
--brand-font-weight: 600;

/* Account Block */
--account-name-size: 14px;
--account-name-weight: 600;
--account-name-spacing: 0.5px;       /* Letter spacing for uppercase */
--account-role-size: 13px;
--account-role-weight: 450;

/* User Menu */
--menu-item-size: 14px;
--menu-item-weight: 450;
--menu-item-spacing: -0.01em;        /* Slight tightening */
```

### Text Formatting Rules
- **Uppercase Text**: Always add `letter-spacing: 0.5px` for readability (e.g., username)
- **Title Case**: First letter uppercase, rest lowercase (e.g., role names)
- **Line Height**: Use `1.2` for compact text, `1.3-1.4` for body text

## Spacing

### Spacing Scale (Based on Sidebar Implementation)
```css
--spacing-0: 0;
--spacing-1: 0.125rem;   /* 2px - fine adjustments */
--spacing-2: 0.25rem;    /* 4px - gap adjustments */
--spacing-3: 0.5rem;     /* 8px - small gaps */
--spacing-4: 0.75rem;    /* 12px - icon-label gap, group spacing */
--spacing-5: 0.875rem;   /* 14px - pill padding */
--spacing-6: 1rem;       /* 16px - standard padding */
--spacing-7: 1.125rem;   /* 18px - sidebar padding-x, footer margin */
--spacing-8: 1.25rem;    /* 20px - sidebar padding-top */
--spacing-10: 1.5rem;    /* 24px - page content padding */
--spacing-12: 2rem;      /* 32px - icon container, large spacing */
--spacing-16: 2.25rem;   /* 36px - avatar size */
--spacing-20: 2.5rem;    /* 40px */
--spacing-24: 3rem;      /* 48px */
```

### Component-Specific Spacing
```css
/* Sidebar */
--sidebar-width: 260px;
--sidebar-collapsed-width: 72px;
--sidebar-padding-x: 18px;
--sidebar-padding-top: 20px;

/* Navigation */
--nav-row-height: 44px;
--nav-child-height: 38px;
--nav-item-spacing: 2px;           /* Between items */
--icon-size: 17px;
--icon-container-width: 32px;
--gap-icon-label: 12px;

/* Border Radius */
--radius-sm: 6px;                  /* Sharper - child items, buttons */
--radius-md: 8px;                  /* Medium - dropdowns, cards */
--radius-lg: 12px;                 /* Rounded - parent nav items (pills) */
--radius-full: 50%;                /* Circular - avatars */

/* Shadows */
--shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.15);      /* Tooltips, small elevations */
--shadow-md: 0 4px 16px rgba(0, 0, 0, 0.12);     /* Dropdowns, modals */
--shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.15);     /* Large modals */

/* Transitions */
--transition-fast: 0.15s ease;     /* Hover, focus states */
--transition-base: 0.2s ease;      /* Standard transitions */
--transition-slow: 0.3s ease;      /* Large movements */
```

## Responsive Breakpoints

```css
--breakpoint-mobile: 320px;
--breakpoint-mobile-max: 767px;
--breakpoint-tablet: 768px;
--breakpoint-tablet-max: 1023px;
--breakpoint-laptop: 1024px;
--breakpoint-desktop: 1440px;
```

### Media Queries (Based on Sidebar Implementation)
```css
/* Mobile (320px - 767px) */
@media (max-width: 767px) {
  /* Collapsed sidebar, flyout menus, tooltips */
}

/* Tablet (768px - 1023px) */
@media (max-width: 1023px) and (min-width: 768px) {
  /* Full sidebar, adjusted font sizes */
}

/* Laptop and above (1024px+) */
@media (min-width: 1024px) {
  /* Full desktop experience */
}

/* Small mobile (320px - 480px) */
@media (max-width: 480px) {
  /* Reduced sizes for very small screens */
}

/* Landscape mobile */
@media (max-height: 600px) and (orientation: landscape) {
  /* Compact vertical spacing */
}
```

### Responsive Patterns

#### Sidebar Behavior
- **Desktop (1024px+)**: Full width (260px), expandable/collapsible
- **Tablet (768px-1023px)**: Full width (260px), always visible
- **Mobile (≤767px)**: Collapsed (72px), flyout menus on click

#### Flyout Menus (Mobile)
- Position: Fixed, to the right of sidebar
- Only one flyout open at a time
- Close previous when opening new
- Positioned dynamically based on trigger element

#### Typography Scaling
- **Desktop**: Standard sizes
- **Tablet**: Slightly reduced (13px → 14px for nav)
- **Mobile**: Maintain readability, use tooltips for labels

## Icons

### Icon Library
Use inline SVG icons with outline/stroke style (as implemented in Sidebar):

**Approach**: Create inline SVG icons directly in components
- Consistent stroke width: 1.5px - 2px
- ViewBox: 20x20 or 16x16
- Fill: none
- Stroke: currentColor (inherits text color)

**Alternative Libraries** (if needed):
- **Lucide React** (preferred): `lucide-react`
- **Heroicons**: `@heroicons/react`
- **Feather Icons**: `react-icons/fi`

### Icon Guidelines
- **DO NOT use emojis**
- **Use ONLY outline/stroke style icons** (no filled icons)
- **Sizes**: 16px (small), 17px (navigation), 20px (standard), 24px (large)
- **Stroke width**: 1.5px (standard), 2px (bold)
- **Color**: Use `currentColor` to inherit from parent
- **Accessibility**: Always include `aria-hidden="true"` on decorative icons

### Icon Examples (From Sidebar)
```tsx
// Dashboard icon (20x20, stroke 1.5px)
<svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
  <rect x="3" y="3" width="6" height="6" rx="1" />
  <rect x="11" y="3" width="6" height="6" rx="1" />
  <rect x="3" y="11" width="6" height="6" rx="1" />
  <rect x="11" y="11" width="6" height="6" rx="1" />
</svg>

// Chevron icon (16x16, stroke 2px)
<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
  <path d="M6 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
</svg>

// External link icon (12x12, stroke 1.5px)
<svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
  <path d="M9 3L3 9M9 3v4M9 3H5" strokeLinecap="round" strokeLinejoin="round" />
</svg>
```

### Icon Usage in Components
```tsx
// Icon wrapper for consistent sizing
<span className="icon" aria-hidden="true">
  <svg>...</svg>
</span>

// CSS for icon wrapper
.icon {
  width: var(--icon-size);
  height: var(--icon-size);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: inherit;
}
```

## Interaction Patterns (Based on Sidebar Implementation)

### Hover States
```css
/* Standard hover - light background */
.interactive-element:hover {
  background: var(--color-hover-bg);
  transition: all var(--transition-fast);
}

/* Full-width hover (no border-radius) */
.full-width-hover:hover {
  background: var(--color-hover-bg);
  border-radius: 0;
}

/* Destructive hover */
.destructive:hover {
  background: var(--color-error-bg);
}
```

### Focus States
```css
/* Standard focus ring */
.interactive-element:focus-visible {
  outline: 2px solid var(--color-focus-ring);
  outline-offset: 2px;
}

/* Inset focus ring */
.inset-focus:focus-visible {
  outline: 2px solid var(--color-focus-ring);
  outline-offset: -2px;
}
```

### Selected States
```css
/* Selected item */
.selectable.selected {
  background: var(--color-selected-bg);
  color: var(--color-primary);
  font-weight: var(--font-weight-semibold);
}

/* Selected with pseudo-element background */
.child-item.selected::before {
  content: '';
  position: absolute;
  left: 20px;
  right: 0;
  top: 4px;
  bottom: 4px;
  border-radius: var(--radius-sm);
  background: var(--color-selected-bg);
  z-index: -1;
}
```

### Dropdown/Menu Patterns
```css
/* Dropdown container */
.dropdown-menu {
  position: absolute;
  background: var(--color-bg-surface);
  border: 1px solid var(--color-divider);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  padding: 4px;
  animation: slideUp 0.15s ease;
}

/* Slide up animation */
@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Menu item */
.menu-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 9px 12px;
  min-height: 38px;
  border-radius: var(--radius-sm);
  font-size: var(--menu-item-size);
  font-weight: var(--menu-item-weight);
  letter-spacing: var(--menu-item-spacing);
  transition: all var(--transition-fast);
}

/* Menu divider */
.menu-divider {
  height: 1px;
  background: var(--color-divider);
  margin: 4px 0;
}
```

### Keyboard Navigation
- Support Enter and Space keys for activation
- Provide clear focus indicators
- Support Tab navigation
- Support Escape to close menus/modals

```tsx
const handleKeyDown = (e: React.KeyboardEvent, action: () => void) => {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault();
    action();
  }
};
```

### Click Outside to Close
```tsx
React.useEffect(() => {
  const handleClickOutside = (event: MouseEvent) => {
    const target = event.target as HTMLElement;
    if (isOpen && !target.closest('.menu-container')) {
      setIsOpen(false);
    }
  };

  document.addEventListener('mousedown', handleClickOutside);
  return () => document.removeEventListener('mousedown', handleClickOutside);
}, [isOpen]);
```

## Component Usage Rules

### DO
- Import components from `@/components/ui`
- Use design tokens (CSS variables) for colors and spacing
- Follow responsive design patterns
- Maintain consistent spacing and alignment
- Use semantic HTML elements

### DON'T
- Create inline styles for common patterns
- Recreate existing components
- Use arbitrary colors outside the palette
- Use emojis instead of icons
- Hardcode spacing or colors

## Example Component Structure

```tsx
// frontend/src/components/ui/Button.tsx
import React from 'react';
import './Button.css';

interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'tertiary';
  size?: 'sm' | 'md' | 'lg';
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  children,
  onClick,
  disabled = false,
}) => {
  return (
    <button
      className={`btn btn-${variant} btn-${size}`}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
};
```

## Accessibility Requirements

- Use semantic HTML
- Provide proper ARIA labels
- Ensure keyboard navigation
- Maintain color contrast ratios (WCAG AA)
- Support screen readers
- Provide focus indicators
- Use proper heading hierarchy
