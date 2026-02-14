---
inclusion: fileMatch
fileMatchPattern: '**/*.{tsx,jsx,css,scss}'
---

# UI Design Inspiration

## Snowflake UI Reference

### Design Philosophy
The UI should be inspired by Snowflake's clean, minimal, and professional interface:
- Clean and spacious layouts
- Minimal visual clutter
- Professional and enterprise-grade appearance
- Clear information hierarchy
- Subtle use of color
- Outline-based icons

### Key Characteristics

#### Layout
- **Sidebar Navigation**: Left sidebar with collapsible sections
- **Content Area**: Large, clean content area with ample white space
- **Header**: Minimal top header with user actions and context
- **Cards**: Use cards for grouping related content
- **Tables**: Clean, readable tables with subtle borders

#### Visual Style
- **Minimal Borders**: Use subtle borders (1px, light grey)
- **White Space**: Generous padding and margins
- **Shadows**: Subtle shadows for depth (avoid heavy shadows)
- **Rounded Corners**: Small border radius (4px - 8px)
- **Clean Typography**: Clear, readable text with good hierarchy

#### Colors
- **Backgrounds**: Primarily white and off-white
- **Accents**: Use blue sparingly for primary actions
- **Text**: Dark slate/black for primary text, grey for secondary
- **Borders**: Light grey (#E0E0E0, #EEEEEE)
- **Hover States**: Subtle background changes

#### Icons
- **Style**: Outline-based, minimal, small
- **Size**: 16px - 24px
- **Stroke**: Thin to medium stroke width (1.5px - 2px)
- **Color**: Match text color or use subtle grey
- **Usage**: Use icons to enhance, not decorate

#### Navigation
- **Sidebar**: Collapsible sections with icons and labels
- **Active State**: Subtle background highlight for active items
- **Hover State**: Light background change on hover
- **Hierarchy**: Clear visual hierarchy with indentation

#### Data Display
- **Tables**: Clean rows with subtle hover effects
- **Status Indicators**: Small badges or colored text
- **Metrics**: Large, clear numbers with labels
- **Progress**: Subtle progress bars
- **Code**: Monospace font with light background

#### Interactive Elements
- **Buttons**: Clear, minimal buttons with subtle shadows
- **Forms**: Clean inputs with clear labels
- **Dropdowns**: Simple, functional dropdowns
- **Modals**: Centered modals with subtle backdrop
- **Tooltips**: Small, informative tooltips

### Component Examples

#### Sidebar Navigation
```tsx
<nav className="sidebar">
  <div className="sidebar-section">
    <div className="sidebar-item active">
      <Database size={20} />
      <span>Projects</span>
    </div>
    <div className="sidebar-item">
      <Settings size={20} />
      <span>Settings</span>
    </div>
  </div>
</nav>
```

#### Data Table
```tsx
<table className="data-table">
  <thead>
    <tr>
      <th>Name</th>
      <th>Status</th>
      <th>Progress</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Migration 1</td>
      <td><Badge variant="success">Complete</Badge></td>
      <td>100%</td>
    </tr>
  </tbody>
</table>
```

#### Card Layout
```tsx
<div className="card">
  <div className="card-header">
    <h3>Database Connections</h3>
  </div>
  <div className="card-content">
    {/* Content */}
  </div>
</div>
```

### CSS Guidelines

#### Spacing
- Use consistent spacing scale (4px, 8px, 12px, 16px, 24px, 32px)
- Generous padding inside cards and containers
- Clear separation between sections

#### Borders
- Use 1px borders with light grey colors
- Avoid heavy borders
- Use borders to separate, not decorate

#### Shadows
- Subtle shadows for elevation
- Avoid heavy drop shadows
- Use shadows sparingly

```css
/* Subtle shadow for cards */
box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);

/* Hover shadow */
box-shadow: 0 2px 6px rgba(0, 0, 0, 0.12);
```

#### Hover States
- Subtle background color changes
- Smooth transitions (200ms)
- Clear visual feedback

```css
.sidebar-item:hover {
  background-color: var(--color-grey-100);
  transition: background-color 200ms ease;
}
```

### Avoid
- Heavy shadows
- Bright, saturated colors
- Filled/solid icons
- Excessive animations
- Visual clutter
- Decorative elements
- Emojis
- Gradients (use sparingly)
- Complex patterns

### Embrace
- Clean, minimal design
- Ample white space
- Subtle interactions
- Clear hierarchy
- Professional appearance
- Functional design
- Outline icons
- Consistent spacing
