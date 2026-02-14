# DataMIQ Design System

## Overview

This directory contains the centralized design system for DataMIQ, including design tokens, global styles, and utility classes. All components should use these tokens to ensure consistency across the application.

## Files

- **design-tokens.css** - Centralized CSS variables for colors, typography, spacing, etc.
- **global.css** - Global styles, resets, and base typography
- **design-tokens.ts** - TypeScript constants (if needed for JS/TS usage)

## Usage

### In CSS Files

Import the design tokens at the top of your CSS file:

```css
/* Component.css */
@import '../../styles/design-tokens.css';

.my-component {
  background: var(--color-bg-surface);
  color: var(--color-text-primary);
  padding: var(--spacing-6);
  border-radius: var(--radius-md);
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
}
```

### In React Components

The design tokens are automatically available through the global CSS import in `main.tsx`.

```tsx
// Component.tsx
import './Component.css';

export const Component = () => {
  return (
    <div className="my-component">
      <h2>Title</h2>
      <p>Content</p>
    </div>
  );
};
```

## Design Tokens Reference

### Colors

#### Primary Colors
- `--color-primary` - #2A6BDB (Primary blue for actions, selected text)
- `--color-primary-dark` - #1E4FA0 (Darker blue for hover states)

#### Backgrounds
- `--color-bg-primary` - #FAFAFA (Main app background)
- `--color-bg-secondary` - #F7F7F7 (Sidebar, secondary surfaces)
- `--color-bg-surface` - #FFFFFF (Cards, dropdowns, elevated surfaces)

#### Text
- `--color-text-primary` - #1F2937 (Primary text, high contrast)
- `--color-text-secondary` - #66748C (Secondary text, muted)
- `--color-text-disabled` - #9AA6B2 (Disabled text)

#### Interactive States
- `--color-selected-bg` - #D4E4FC (Selected item background)
- `--color-hover-bg` - #EFF5FF (Hover state background)
- `--color-divider` - #E5E7EB (Borders, dividers)

#### Semantic Colors
- `--color-success` - #4CAF50
- `--color-error` - #DC2626
- `--color-error-bg` - #FEE2E2 (Error hover background)
- `--color-warning` - #FFD140
- `--color-info` - #2A6BDB

### Typography

#### Font Families
- `--font-family` - Inter (all UI text)
- `--font-family-code` - Courier New (code blocks only)

#### Font Sizes
- `--font-size-xs` - 12px
- `--font-size-sm` - 13px (navigation items)
- `--font-size-base` - 14px (body text, menu items)
- `--font-size-md` - 16px (brand text, headings)
- `--font-size-lg` - 18px
- `--font-size-xl` - 20px (page titles)
- `--font-size-2xl` - 24px
- `--font-size-3xl` - 30px
- `--font-size-4xl` - 36px

#### Font Weights
- `--font-weight-normal` - 400 (regular text)
- `--font-weight-450` - 450 (child menu items, user menu)
- `--font-weight-medium` - 500 (parent menu items)
- `--font-weight-550` - 550 (selected child items)
- `--font-weight-semibold` - 600 (selected parent items, headings)
- `--font-weight-bold` - 700 (avatar initials)

### Spacing

- `--spacing-0` - 0
- `--spacing-1` - 2px
- `--spacing-2` - 4px
- `--spacing-3` - 8px
- `--spacing-4` - 12px
- `--spacing-5` - 14px
- `--spacing-6` - 16px
- `--spacing-7` - 18px
- `--spacing-8` - 20px
- `--spacing-10` - 24px
- `--spacing-12` - 32px
- `--spacing-16` - 36px
- `--spacing-20` - 40px
- `--spacing-24` - 48px

### Border Radius

- `--radius-sm` - 6px (sharper, child items)
- `--radius-md` - 8px (medium, dropdowns)
- `--radius-lg` - 12px (rounded, parent nav items)
- `--radius-full` - 50% (circular, avatars)

### Shadows

- `--shadow-sm` - 0 2px 8px rgba(0, 0, 0, 0.15) (tooltips)
- `--shadow-md` - 0 4px 16px rgba(0, 0, 0, 0.12) (dropdowns)
- `--shadow-lg` - 0 8px 24px rgba(0, 0, 0, 0.15) (modals)

### Transitions

- `--transition-fast` - 0.15s ease (hover, focus)
- `--transition-base` - 0.2s ease (standard)
- `--transition-slow` - 0.3s ease (large movements)

## Component Patterns

### Hover States

```css
.interactive-element {
  transition: all var(--transition-fast);
}

.interactive-element:hover {
  background: var(--color-hover-bg);
}
```

### Focus States

```css
.interactive-element:focus-visible {
  outline: 2px solid var(--color-focus-ring);
  outline-offset: 2px;
}
```

### Selected States

```css
.selectable.selected {
  background: var(--color-selected-bg);
  color: var(--color-primary);
  font-weight: var(--font-weight-semibold);
}
```

### Dropdown Menus

```css
.dropdown-menu {
  position: absolute;
  background: var(--color-bg-surface);
  border: 1px solid var(--color-divider);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  padding: 4px;
  animation: slideUp 0.15s ease;
}

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
```

### Menu Items

```css
.menu-item {
  display: flex;
  align-items: center;
  gap: var(--gap-menu-items);
  padding: var(--menu-item-padding);
  min-height: var(--menu-item-height);
  border-radius: var(--radius-sm);
  font-size: var(--menu-item-size);
  font-weight: var(--menu-item-weight);
  letter-spacing: var(--menu-item-spacing);
  transition: all var(--transition-fast);
}

.menu-item:hover {
  background: var(--color-hover-bg);
}
```

## Responsive Design

### Breakpoints

- Mobile: ≤767px
- Tablet: 768px - 1023px
- Laptop: ≥1024px

### Media Queries

```css
/* Mobile */
@media (max-width: 767px) {
  /* Mobile styles */
}

/* Tablet */
@media (max-width: 1023px) and (min-width: 768px) {
  /* Tablet styles */
}

/* Laptop and above */
@media (min-width: 1024px) {
  /* Desktop styles */
}
```

## Best Practices

### DO

✅ Use design tokens for all colors, spacing, typography
✅ Use semantic variable names (e.g., `--color-text-primary`)
✅ Follow the established patterns for hover, focus, selected states
✅ Use consistent spacing from the spacing scale
✅ Use Inter font for all UI text
✅ Add letter-spacing (0.5px) to uppercase text
✅ Use appropriate font weights (450, 500, 550, 600)

### DON'T

❌ Hardcode colors, spacing, or font sizes
❌ Create custom colors outside the design system
❌ Use Google Sans (use Inter instead)
❌ Use emojis (use SVG icons)
❌ Use filled icons (use outline/stroke style)
❌ Skip hover/focus states on interactive elements
❌ Use arbitrary font weights (stick to defined weights)

## Accessibility

- Always provide focus indicators (`:focus-visible`)
- Maintain color contrast ratios (WCAG AA)
- Support keyboard navigation
- Use semantic HTML
- Provide ARIA labels where needed
- Support reduced motion preferences

## Examples

See the Sidebar component (`frontend/src/components/layout/Sidebar.tsx`) for a complete implementation example using the design system.

## Updates

When updating the design system:

1. Update `design-tokens.css` with new tokens
2. Update this README with documentation
3. Update `.kiro/steering/ui-design-system.md` with guidelines
4. Test changes across all components
5. Communicate changes to the team
