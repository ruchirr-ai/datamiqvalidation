# Design System Update - January 2026

## Overview

Updated the DataMIQ design system based on the actual implementation of the Sidebar component. The design system now reflects the real style preferences and patterns used in the application.

## Changes Made

### 1. Updated Steering Documentation

**File**: `.kiro/steering/ui-design-system.md`

#### Color System
- Replaced generic brand colors with actual colors from Sidebar implementation
- Primary: #2A6BDB (was #0070E0)
- Added specific background colors: #FAFAFA, #F7F7F7, #FFFFFF
- Added text colors: #1F2937 (primary), #66748C (secondary)
- Added interactive state colors: #D4E4FC (selected), #EFF5FF (hover)
- Added error colors: #DC2626 with #FEE2E2 hover background
- Updated grey scale to match actual usage

#### Typography
- Changed from Google Sans to **Inter font family**
- Added precise font weights: 400, 450, 500, 550, 600, 700
- Updated font sizes to match implementation (13px for nav, 14px for body)
- Added component-specific typography tokens
- Added text formatting rules (uppercase with 0.5px letter spacing)

#### Spacing
- Updated spacing scale based on actual Sidebar measurements
- Added component-specific spacing tokens
- Added border radius values: 6px (sharp), 8px (medium), 12px (rounded)
- Added shadow definitions
- Added transition timing values

#### Responsive Design
- Updated breakpoints with max values
- Added specific responsive patterns from Sidebar
- Documented mobile flyout behavior
- Added landscape mobile considerations

#### Icons
- Changed to inline SVG approach (as used in Sidebar)
- Documented exact stroke widths and sizes
- Provided SVG examples from Sidebar implementation
- Emphasized outline/stroke style only

#### Interaction Patterns
- Added hover state patterns
- Added focus state patterns
- Added selected state patterns
- Added dropdown/menu patterns
- Added keyboard navigation patterns
- Added click-outside-to-close pattern

### 2. Created Centralized Design Tokens

**File**: `frontend/src/styles/design-tokens.css`

Created a comprehensive CSS variables file with:
- All colors from the Sidebar implementation
- Typography tokens (fonts, sizes, weights)
- Spacing scale
- Border radius values
- Shadow definitions
- Transition timings
- Component-specific tokens (sidebar, navigation, icons, etc.)
- Utility classes for common patterns
- Accessibility support (reduced motion, high contrast)

### 3. Updated Global Styles

**File**: `frontend/src/styles/global.css`

- Imported design-tokens.css
- Changed to Inter font import
- Updated all CSS variables to use new design tokens
- Updated scrollbar styling to match Sidebar
- Simplified and cleaned up base styles

### 4. Created Design System Documentation

**File**: `frontend/src/styles/README.md`

Comprehensive documentation including:
- Overview of the design system
- Usage instructions for CSS and React
- Complete design tokens reference
- Component patterns with code examples
- Responsive design guidelines
- Best practices (DO/DON'T)
- Accessibility guidelines
- Real examples from Sidebar component

## Key Style Preferences Captured

### Colors
- **Primary**: #2A6BDB (blue for actions, selected text)
- **Backgrounds**: #FAFAFA (main), #F7F7F7 (sidebar), #FFFFFF (surfaces)
- **Text**: #1F2937 (primary), #66748C (secondary)
- **Interactive**: #D4E4FC (selected bg), #EFF5FF (hover bg)
- **Error**: #DC2626 with #FEE2E2 hover

### Typography
- **Font**: Inter (NOT Google Sans)
- **Weights**: 450 (child items), 500 (parent items), 550 (selected child), 600 (selected parent)
- **Sizes**: 13px (nav), 14px (body), 16px (brand)
- **Uppercase**: Always add 0.5px letter spacing

### Spacing
- **Sidebar**: 260px width, 72px collapsed
- **Padding**: 18px horizontal, 20px top
- **Nav items**: 44px height (parent), 38px (child)
- **Gaps**: 12px icon-label, 2px between items

### Border Radius
- **Sharp**: 6px (child items, buttons)
- **Medium**: 8px (dropdowns, cards)
- **Rounded**: 12px (parent nav items)
- **Circular**: 50% (avatars)

### Responsive
- **Mobile**: ≤767px (collapsed sidebar, flyouts)
- **Tablet**: 768px-1023px (full sidebar)
- **Laptop**: ≥1024px (full experience)

## Benefits

1. **Consistency**: All components will use the same design tokens
2. **Maintainability**: Single source of truth for styles
3. **Efficiency**: Faster development with pre-defined patterns
4. **Scalability**: Easy to update styles globally
5. **Documentation**: Clear guidelines for all developers

## Usage for Future Components

When creating new components:

1. Import design-tokens.css in your component CSS
2. Use CSS variables instead of hardcoded values
3. Follow the patterns documented in the design system
4. Reference the Sidebar component as an example
5. Check the README for specific usage guidelines

## Example

```css
/* MyComponent.css */
@import '../../styles/design-tokens.css';

.my-component {
  background: var(--color-bg-surface);
  color: var(--color-text-primary);
  padding: var(--spacing-6);
  border-radius: var(--radius-md);
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
  transition: all var(--transition-fast);
}

.my-component:hover {
  background: var(--color-hover-bg);
}

.my-component:focus-visible {
  outline: 2px solid var(--color-focus-ring);
  outline-offset: 2px;
}
```

## Next Steps

1. ✅ Design system documented
2. ✅ Centralized tokens created
3. ✅ Global styles updated
4. ⏳ Apply design tokens to existing components
5. ⏳ Create reusable UI components using design tokens
6. ⏳ Build component library in `frontend/src/components/ui/`

## Files Modified/Created

- `.kiro/steering/ui-design-system.md` (updated)
- `frontend/src/styles/design-tokens.css` (created)
- `frontend/src/styles/global.css` (updated)
- `frontend/src/styles/README.md` (created)
- `DESIGN_SYSTEM_UPDATE.md` (this file)

---

**Date**: January 26, 2026
**Based on**: Sidebar component implementation
**Status**: Complete ✅
