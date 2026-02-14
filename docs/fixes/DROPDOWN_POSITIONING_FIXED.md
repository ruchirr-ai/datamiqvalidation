# Dropdown Menu Positioning Fixed

## Issue
Dropdown menus in both Connections and Migrations pages were being cut off for bottom rows. The menu items were not fully visible when clicking the three-dot menu button on the last few rows of the table.

## Root Cause
The dropdown was using `position: absolute` which was being clipped by the table container. The positioning logic was also using string values ('top'/'bottom') instead of calculating actual pixel positions.

## Solution

### 1. Changed Position Strategy
- **Before**: `position: absolute` with `top`/`bottom` relative to parent
- **After**: `position: fixed` with calculated pixel positions relative to viewport

### 2. Dynamic Position Calculation
Instead of just determining if menu should open upward or downward, we now calculate exact pixel positions:

```typescript
const position = {
  right: window.innerWidth - rect.right,
  ...(shouldOpenUpward 
    ? { bottom: windowHeight - rect.top + 4 }
    : { top: rect.bottom + 4 }
  )
};
```

### 3. Updated State Management
- **Before**: `menuPosition: 'bottom' | 'top'`
- **After**: `menuPosition: { top?: number; bottom?: number; right: number }`

### 4. Applied Inline Styles
The dropdown now receives calculated positions as inline styles:

```tsx
<div 
  className={`connection-dropdown-menu ${menuPosition.bottom ? 'open-upward' : ''}`}
  style={{
    top: menuPosition.top ? `${menuPosition.top}px` : 'auto',
    bottom: menuPosition.bottom ? `${menuPosition.bottom}px` : 'auto',
    right: `${menuPosition.right}px`
  }}
>
```

## Files Modified

### ConnectionsPage
1. **frontend/src/pages/ConnectionsPage.tsx**
   - Updated `menuPosition` state type
   - Added position calculation logic in button onClick
   - Applied inline styles to dropdown

2. **frontend/src/pages/ConnectionsPage.css**
   - Changed `.connection-dropdown-menu` from `position: absolute` to `position: fixed`
   - Removed static `top`, `bottom`, `right` properties (now set via inline styles)

### MigrationsPage
1. **frontend/src/pages/MigrationsPage.tsx**
   - Updated `menuPosition` state type
   - Added position calculation logic in button onClick
   - Applied inline styles to dropdown

2. **frontend/src/pages/MigrationsPage.css**
   - Changed `.migration-dropdown-menu` from `position: absolute` to `position: fixed`
   - Removed static `top`, `bottom`, `right` properties (now set via inline styles)

## Benefits

1. **No Clipping**: Dropdown is never clipped by table container overflow
2. **Accurate Positioning**: Menu appears exactly where it should relative to the button
3. **Works for All Rows**: Top, middle, and bottom rows all display the menu correctly
4. **Responsive**: Automatically adjusts based on available space
5. **High Z-Index**: Menu appears above all other elements (z-index: 10000)

## Testing

Test the dropdown menu on:
- ✅ First row (top of table)
- ✅ Middle rows
- ✅ Last row (bottom of table)
- ✅ Second-to-last row
- ✅ With different window heights
- ✅ With scrolled table

All menu items should be fully visible and clickable in all scenarios.

## Technical Details

### Menu Height
Set to 180px as approximate height for calculation. This accounts for:
- 3 menu items × ~38px each = ~114px
- 1 divider = ~9px
- Padding = 8px (4px top + 4px bottom)
- Buffer = ~49px for safety

### Z-Index Strategy
- Dropdown menu: 10000
- Ensures menu appears above:
  - Table rows
  - Pagination controls
  - Other UI elements

### Animation
Maintained smooth slide animations:
- Downward opening: `slideUp` animation (0.15s)
- Upward opening: `slideDown` animation (0.15s)

## Status
✅ **COMPLETE** - Dropdown positioning now works correctly for all rows in both Connections and Migrations pages.
