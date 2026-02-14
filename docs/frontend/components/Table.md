# Table Component

## Overview
A reusable table component with consistent styling across the application. Based on the Data Connections table design.

## Import
```tsx
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui';
```

## Basic Usage

```tsx
<Table>
  <TableHeader>
    <TableRow>
      <TableHead>Name</TableHead>
      <TableHead>Type</TableHead>
      <TableHead>Status</TableHead>
    </TableRow>
  </TableHeader>
  <TableBody>
    <TableRow>
      <TableCell>Item 1</TableCell>
      <TableCell>Source</TableCell>
      <TableCell>Active</TableCell>
    </TableRow>
    <TableRow>
      <TableCell>Item 2</TableCell>
      <TableCell>Target</TableCell>
      <TableCell>Inactive</TableCell>
    </TableRow>
  </TableBody>
</Table>
```

## Components

### Table
Main container for the table.

**Props:**
- `children` (ReactNode, required): Table content
- `className` (string, optional): Additional CSS classes

### TableHeader
Table header section (`<thead>`).

**Props:**
- `children` (ReactNode, required): Header rows

### TableBody
Table body section (`<tbody>`).

**Props:**
- `children` (ReactNode, required): Body rows

### TableRow
Table row (`<tr>`).

**Props:**
- `children` (ReactNode, required): Row cells
- `onClick` (function, optional): Click handler for row
- `className` (string, optional): Additional CSS classes

### TableHead
Table header cell (`<th>`).

**Props:**
- `children` (ReactNode, required): Cell content
- `className` (string, optional): Additional CSS classes

### TableCell
Table data cell (`<td>`).

**Props:**
- `children` (ReactNode, required): Cell content
- `className` (string, optional): Additional CSS classes

## Styling

### Default Styles
- White background with 8px border radius
- Header: 12.5px font, 600 weight, uppercase, #6B7280 color
- Rows: 13px font, 450 weight, #D1D5DB borders
- Hover: #EFF5FF background (same as left nav)
- Last row: border visible
- Padding: 12px vertical for header, 8px for rows
- First column: 24px left padding

### Utility Classes

#### table-cell-with-icon
Display cell content with an icon.

```tsx
<TableCell>
  <div className="table-cell-with-icon">
    <Cable className="table-cell-icon" />
    <span className="table-cell-name">Connection Name</span>
  </div>
</TableCell>
```

#### table-cell-with-avatar
Display cell content with an avatar.

```tsx
<TableCell>
  <div className="table-cell-with-avatar">
    <Avatar name="John Doe" size="sm" />
    <span>John Doe</span>
  </div>
</TableCell>
```

#### table-cell-timestamp
Style for timestamp cells.

```tsx
<TableCell className="table-cell-timestamp">
  2026-01-26 10:30 AM
</TableCell>
```

#### table-badge
Badge styling for table cells.

```tsx
<TableCell>
  <span className="table-badge">Active</span>
</TableCell>
```

#### table-action-btn
Action button for table rows (e.g., menu button).

```tsx
<TableCell>
  <button className="table-action-btn">
    <MoreVertical size={16} />
  </button>
</TableCell>
```

## Complete Example

```tsx
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell, Avatar, Badge } from '@/components/ui';
import { Cable, MoreVertical } from 'lucide-react';

const ConnectionsTable = () => {
  const connections = [
    { id: 1, name: 'Production DB', createdBy: 'john.doe', status: 'connected' },
    { id: 2, name: 'Staging DB', createdBy: 'jane.smith', status: 'disconnected' }
  ];

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>NAME</TableHead>
          <TableHead>CREATED BY</TableHead>
          <TableHead>STATUS</TableHead>
          <TableHead></TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {connections.map((conn) => (
          <TableRow key={conn.id}>
            <TableCell>
              <div className="table-cell-with-icon">
                <Cable className="table-cell-icon" />
                <span className="table-cell-name">{conn.name}</span>
              </div>
            </TableCell>
            <TableCell>
              <div className="table-cell-with-avatar">
                <Avatar name={conn.createdBy} size="sm" />
                <span>{conn.createdBy}</span>
              </div>
            </TableCell>
            <TableCell>
              <Badge variant={conn.status === 'connected' ? 'success' : 'error'}>
                {conn.status}
              </Badge>
            </TableCell>
            <TableCell>
              <button className="table-action-btn">
                <MoreVertical size={16} />
              </button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
};
```

## Design Specifications

### Typography
- **Title**: 20px, 600 weight, with icon
- **Count**: 16px, 600 weight, 20px gap below title
- **Header**: 12.5px font, 600 weight, uppercase
- **Rows**: 13px font, 450 weight

### Colors
- **Header text**: #6B7280
- **Row text**: #1F2937
- **Icon/Name**: #000000
- **Borders**: #D1D5DB
- **Hover background**: #EFF5FF

### Spacing
- **Header padding**: 12px vertical, 20px horizontal
- **Row padding**: 8px vertical, 20px horizontal
- **First column**: 24px left padding
- **Icon gap**: 10px
- **Avatar gap**: 8px

### Borders
- **Border radius**: 8px for container
- **Row borders**: 1px solid #D1D5DB
- **Last row**: border visible

## Responsive Behavior
On screens smaller than 768px:
- Table container becomes horizontally scrollable
- Table maintains minimum width of 800px

## Accessibility
- Uses semantic HTML table elements
- Supports keyboard navigation
- Row click handlers for interactive tables
- Proper ARIA labels should be added for action buttons
