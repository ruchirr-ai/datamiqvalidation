# Design Document: Database Field Configuration UI

## Overview

The Database Field Configuration UI provides administrators with an interface to configure which fields appear when users create database connections. The system allows customization per database type, enabling dynamic forms that adapt to different database systems (MongoDB, DocumentDB, PostgreSQL, MySQL, Oracle, SQL Server).

This design focuses on the **frontend UI implementation only**, creating the admin configuration interface and integrating it with the existing Create Connection modal.

## Architecture

### High-Level UI Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Admin Page (React)                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Data Connections Section                 │   │
│  │  ┌────────────────┐  ┌──────────────────────────┐   │   │
│  │  │  Left Sidebar  │  │   Right Main Pane        │   │   │
│  │  │                │  │                          │   │   │
│  │  │  - MongoDB     │  │  Field Configuration     │   │   │
│  │  │  - DocumentDB  │  │  ┌────────────────────┐ │   │   │
│  │  │  - PostgreSQL  │  │  │ Field 1 [Toggle]   │ │   │   │
│  │  │  - MySQL       │  │  │ Field 2 [Toggle]   │ │   │   │
│  │  │  - Oracle      │  │  │ Field 3 [Toggle]   │ │   │   │
│  │  │  - SQL Server  │  │  │ [+ Add Field]      │ │   │   │
│  │  │                │  │  └────────────────────┘ │   │   │
│  │  └────────────────┘  └──────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Create Connection Modal (Enhanced)              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Database Type: [PostgreSQL ▼]                       │   │
│  │  ┌────────────────────────────────────────────────┐ │   │
│  │  │  Dynamic Fields (based on configuration)       │ │   │
│  │  │  - Host [enabled field]                        │ │   │
│  │  │  - Port [enabled field]                        │ │   │
│  │  │  - Database [enabled field]                    │ │   │
│  │  │  - Username [enabled field]                    │ │   │
│  │  │  - Password [enabled field]                    │ │   │
│  │  │  - SSL Mode [enabled field]                    │ │   │
│  │  └────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## UI Components

### 1. Database Field Configuration Page

**Location**: Admin → Data Connections → Sources

**Component Structure**:
```
DatabaseFieldConfigPage
├── PageHeader
│   └── Title: "Database Connection Field Configuration"
├── ContentLayout (Two-column)
│   ├── LeftSidebar
│   │   ├── DatabaseTypeList
│   │   │   ├── DatabaseTypeItem (MongoDB) [selected by default]
│   │   │   ├── DatabaseTypeItem (DocumentDB)
│   │   │   ├── DatabaseTypeItem (PostgreSQL)
│   │   │   ├── DatabaseTypeItem (MySQL)
│   │   │   ├── DatabaseTypeItem (Oracle)
│   │   │   └── DatabaseTypeItem (SQL Server)
│   └── RightMainPane
│       ├── FieldConfigurationHeader
│       │   ├── DatabaseTypeName
│       │   └── AddFieldButton
│       └── FieldConfigurationList
│           ├── FieldConfigItem (for each field)
│           │   ├── FieldInfo
│           │   │   ├── FieldName
│           │   │   ├── FieldType
│           │   │   └── FieldProperties
│           │   ├── ToggleSwitch (enabled/disabled)
│           │   ├── EditButton
│           │   └── RemoveButton
│           └── EmptyState (when no fields)
```

### 2. Field Configuration Item Component

**Props**:
```typescript
interface FieldConfigItemProps {
  field: FieldConfiguration;
  onToggle: (fieldId: string, enabled: boolean) => void;
  onEdit: (fieldId: string) => void;
  onRemove: (fieldId: string) => void;
}

interface FieldConfiguration {
  id: string;
  name: string;
  label: string;
  type: 'text' | 'number' | 'password' | 'select' | 'checkbox';
  enabled: boolean;
  required: boolean;
  placeholder?: string;
  defaultValue?: string;
  validation?: ValidationRules;
  helpText?: string;
  displayOrder: number;
}

interface ValidationRules {
  minLength?: number;
  maxLength?: number;
  min?: number;
  max?: number;
  pattern?: string;
}
```

**Visual Design**:
```
┌────────────────────────────────────────────────────────────┐
│  Host                                          [Toggle ON]  │
│  Type: Text | Required: Yes | Order: 1                     │
│  Placeholder: "localhost"                                  │
│  [Edit] [Remove]                                           │
└────────────────────────────────────────────────────────────┘
```

### 3. Add/Edit Field Modal

**Component**: `FieldConfigModal`

**Props**:
```typescript
interface FieldConfigModalProps {
  isOpen: boolean;
  mode: 'add' | 'edit';
  field?: FieldConfiguration;
  databaseType: string;
  onSave: (field: FieldConfiguration) => void;
  onCancel: () => void;
}
```

**Form Fields**:
- Field Name (text input)
- Field Label (text input)
- Field Type (select: text, number, password, select, checkbox)
- Required (checkbox)
- Placeholder (text input)
- Default Value (text input)
- Help Text (textarea)
- Display Order (number input)
- Validation Rules (expandable section)
  - Min Length (number input)
  - Max Length (number input)
  - Pattern (text input for regex)

**Visual Design**:
```
┌─────────────────────────────────────────────────────────┐
│  Add Field Configuration                          [X]    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Field Name *                                            │
│  [_____________________________________________]         │
│                                                          │
│  Field Label *                                           │
│  [_____________________________________________]         │
│                                                          │
│  Field Type *                                            │
│  [Text ▼]                                                │
│                                                          │
│  [✓] Required Field                                      │
│                                                          │
│  Placeholder                                             │
│  [_____________________________________________]         │
│                                                          │
│  Default Value                                           │
│  [_____________________________________________]         │
│                                                          │
│  Help Text                                               │
│  [_____________________________________________]         │
│  [_____________________________________________]         │
│                                                          │
│  Display Order *                                         │
│  [___]                                                   │
│                                                          │
│  ▼ Validation Rules                                      │
│    Min Length: [___]  Max Length: [___]                 │
│    Pattern (regex): [_____________________________]     │
│                                                          │
├─────────────────────────────────────────────────────────┤
│                              [Cancel]  [Save]            │
└─────────────────────────────────────────────────────────┘
```

### 4. Enhanced Create Connection Modal

**Component**: `CreateConnectionModal` (existing, to be enhanced)

**Changes Required**:
1. Fetch field configuration when database type is selected
2. Dynamically render form fields based on configuration
3. Apply validation rules from configuration
4. Show/hide fields based on enabled status
5. Order fields by displayOrder property

**Dynamic Field Rendering**:
```typescript
interface DynamicFieldProps {
  config: FieldConfiguration;
  value: any;
  onChange: (value: any) => void;
  error?: string;
}

// Render different input types based on config.type
const DynamicField: React.FC<DynamicFieldProps> = ({ config, value, onChange, error }) => {
  switch (config.type) {
    case 'text':
      return <Input type="text" {...config} value={value} onChange={onChange} error={error} />;
    case 'password':
      return <Input type="password" {...config} value={value} onChange={onChange} error={error} />;
    case 'number':
      return <Input type="number" {...config} value={value} onChange={onChange} error={error} />;
    case 'select':
      return <Select {...config} value={value} onChange={onChange} error={error} />;
    case 'checkbox':
      return <Checkbox {...config} checked={value} onChange={onChange} />;
    default:
      return null;
  }
};
```

### 5. Database Type List Component

**Component**: `DatabaseTypeList`

**Props**:
```typescript
interface DatabaseTypeListProps {
  selectedType: string;
  onSelect: (type: string) => void;
}

const DATABASE_TYPES = [
  { id: 'mongodb', name: 'MongoDB', icon: '🍃' },
  { id: 'documentdb', name: 'DocumentDB', icon: '📄' },
  { id: 'postgresql', name: 'PostgreSQL', icon: '🐘' },
  { id: 'mysql', name: 'MySQL', icon: '🐬' },
  { id: 'oracle', name: 'Oracle', icon: '🔴' },
  { id: 'sqlserver', name: 'SQL Server', icon: '🔷' },
];
```

**Visual Design**:
```
┌──────────────────────┐
│  Database Types      │
├──────────────────────┤
│ ▶ 🍃 MongoDB        │ ← Selected (highlighted)
│   📄 DocumentDB      │
│   🐘 PostgreSQL      │
│   🐬 MySQL           │
│   🔴 Oracle          │
│   🔷 SQL Server      │
└──────────────────────┘
```

## Data Flow

### 1. Loading Field Configuration

```
User navigates to Admin → Data Connections → Sources
    ↓
Component mounts, selects MongoDB by default
    ↓
Fetch field configuration for MongoDB
    ↓
Display fields in right pane with toggle states
```

### 2. Switching Database Types

```
User clicks on PostgreSQL in left sidebar
    ↓
Update selected database type state
    ↓
Fetch field configuration for PostgreSQL
    ↓
Display PostgreSQL fields in right pane
```

### 3. Toggling Field Enabled Status

```
User toggles field enabled switch
    ↓
Update field configuration (enabled = true/false)
    ↓
Save to backend API
    ↓
Update UI state
    ↓
Show success notification
```

### 4. Adding New Field

```
User clicks "+ Add Field" button
    ↓
Open FieldConfigModal in 'add' mode
    ↓
User fills form and clicks Save
    ↓
Validate form data
    ↓
Save to backend API
    ↓
Refresh field list
    ↓
Show success notification
```

### 5. Editing Field

```
User clicks Edit button on field
    ↓
Open FieldConfigModal in 'edit' mode with field data
    ↓
User modifies form and clicks Save
    ↓
Validate form data
    ↓
Update backend API
    ↓
Refresh field list
    ↓
Show success notification
```

### 6. Removing Field

```
User clicks Remove button on field
    ↓
Show confirmation dialog
    ↓
User confirms deletion
    ↓
Delete from backend API
    ↓
Remove from field list
    ↓
Show success notification
```

### 7. Dynamic Connection Form

```
User opens Create Connection modal
    ↓
Fetch field configuration for default database type
    ↓
Render enabled fields in displayOrder
    ↓
User selects different database type
    ↓
Fetch field configuration for new type
    ↓
Re-render form with new fields
    ↓
User fills form and submits
    ↓
Validate against field configuration rules
    ↓
Submit to backend
```

## State Management

### Component State Structure

```typescript
// DatabaseFieldConfigPage state
interface ConfigPageState {
  selectedDatabaseType: string;
  fields: FieldConfiguration[];
  loading: boolean;
  error: string | null;
  isModalOpen: boolean;
  modalMode: 'add' | 'edit';
  editingField: FieldConfiguration | null;
}

// CreateConnectionModal state (enhanced)
interface ConnectionModalState {
  databaseType: string;
  fieldConfigs: FieldConfiguration[];
  formValues: Record<string, any>;
  errors: Record<string, string>;
  loading: boolean;
}
```

### API Integration

```typescript
// API service methods
interface FieldConfigAPI {
  // Get all field configurations for a database type
  getFieldConfigs(databaseType: string): Promise<FieldConfiguration[]>;
  
  // Create new field configuration
  createFieldConfig(databaseType: string, field: FieldConfiguration): Promise<FieldConfiguration>;
  
  // Update existing field configuration
  updateFieldConfig(fieldId: string, field: Partial<FieldConfiguration>): Promise<FieldConfiguration>;
  
  // Delete field configuration
  deleteFieldConfig(fieldId: string): Promise<void>;
  
  // Toggle field enabled status
  toggleFieldEnabled(fieldId: string, enabled: boolean): Promise<void>;
}
```

## Styling and Design Tokens

### Layout

```css
.config-page {
  display: flex;
  height: calc(100vh - 64px); /* Full height minus header */
  background: var(--color-gray-50);
}

.left-sidebar {
  width: 280px;
  background: var(--color-white);
  border-right: 1px solid var(--color-gray-200);
  overflow-y: auto;
}

.right-main-pane {
  flex: 1;
  padding: var(--spacing-xl);
  overflow-y: auto;
}
```

### Database Type Item

```css
.database-type-item {
  display: flex;
  align-items: center;
  padding: var(--spacing-md) var(--spacing-lg);
  cursor: pointer;
  transition: background 0.2s;
}

.database-type-item:hover {
  background: var(--color-gray-100);
}

.database-type-item.selected {
  background: var(--color-blue-50);
  border-left: 3px solid var(--color-blue-600);
  font-weight: var(--font-weight-semibold);
}

.database-type-icon {
  font-size: 24px;
  margin-right: var(--spacing-md);
}
```

### Field Configuration Item

```css
.field-config-item {
  background: var(--color-white);
  border: 1px solid var(--color-gray-200);
  border-radius: var(--border-radius-md);
  padding: var(--spacing-lg);
  margin-bottom: var(--spacing-md);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.field-info {
  flex: 1;
}

.field-name {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--color-gray-900);
  margin-bottom: var(--spacing-xs);
}

.field-meta {
  font-size: var(--font-size-sm);
  color: var(--color-gray-600);
}

.field-actions {
  display: flex;
  gap: var(--spacing-md);
  align-items: center;
}
```

### Toggle Switch

```css
.toggle-switch {
  position: relative;
  width: 48px;
  height: 24px;
  background: var(--color-gray-300);
  border-radius: var(--border-radius-full);
  cursor: pointer;
  transition: background 0.3s;
}

.toggle-switch.enabled {
  background: var(--color-blue-600);
}

.toggle-switch-handle {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 20px;
  height: 20px;
  background: var(--color-white);
  border-radius: 50%;
  transition: transform 0.3s;
}

.toggle-switch.enabled .toggle-switch-handle {
  transform: translateX(24px);
}
```

## Responsive Design

### Desktop (> 1024px)
- Full two-column layout
- Left sidebar: 280px fixed width
- Right pane: Flexible width
- Field items: Full details visible

### Tablet (768px - 1024px)
- Collapsible left sidebar
- Hamburger menu to toggle sidebar
- Right pane: Full width when sidebar collapsed
- Field items: Compact view

### Mobile (< 768px)
- Single column layout
- Database type selector as dropdown
- Full-width field items
- Stacked action buttons
- Modal forms: Full screen

## Accessibility

### Keyboard Navigation
- Tab through database types
- Enter to select database type
- Tab through field items
- Space to toggle field enabled status
- Enter to edit field
- Delete key to remove field (with confirmation)

### Screen Reader Support
- Proper ARIA labels for all interactive elements
- Announce state changes (field enabled/disabled)
- Announce loading states
- Announce success/error messages

### Focus Management
- Visible focus indicators
- Focus trap in modals
- Return focus after modal close
- Logical tab order

## Error Handling

### UI Error States

1. **Loading Error**
   - Display error message in right pane
   - Show retry button
   - Log error details

2. **Save Error**
   - Display error notification
   - Keep modal open with form data
   - Highlight problematic fields

3. **Delete Error**
   - Display error notification
   - Keep field in list
   - Allow retry

4. **Validation Error**
   - Inline error messages below fields
   - Prevent form submission
   - Focus first error field

### Empty States

1. **No Fields Configured**
   ```
   ┌────────────────────────────────────┐
   │                                    │
   │         📋                         │
   │                                    │
   │   No fields configured yet         │
   │                                    │
   │   [+ Add Your First Field]         │
   │                                    │
   └────────────────────────────────────┘
   ```

2. **Loading State**
   ```
   ┌────────────────────────────────────┐
   │                                    │
   │         ⏳                         │
   │                                    │
   │   Loading field configurations...  │
   │                                    │
   └────────────────────────────────────┘
   ```

## Default Field Configurations

### MongoDB Default Fields
```typescript
const MONGODB_DEFAULT_FIELDS: FieldConfiguration[] = [
  {
    id: 'host',
    name: 'host',
    label: 'Host',
    type: 'text',
    enabled: true,
    required: true,
    placeholder: 'localhost',
    displayOrder: 1,
  },
  {
    id: 'port',
    name: 'port',
    label: 'Port',
    type: 'number',
    enabled: true,
    required: true,
    defaultValue: '27017',
    displayOrder: 2,
  },
  {
    id: 'database',
    name: 'database',
    label: 'Database',
    type: 'text',
    enabled: true,
    required: true,
    displayOrder: 3,
  },
  {
    id: 'username',
    name: 'username',
    label: 'Username',
    type: 'text',
    enabled: true,
    required: false,
    displayOrder: 4,
  },
  {
    id: 'password',
    name: 'password',
    label: 'Password',
    type: 'password',
    enabled: true,
    required: false,
    displayOrder: 5,
  },
  {
    id: 'replica_set',
    name: 'replica_set',
    label: 'Replica Set',
    type: 'text',
    enabled: true,
    required: false,
    helpText: 'Name of the replica set',
    displayOrder: 6,
  },
  {
    id: 'auth_database',
    name: 'auth_database',
    label: 'Authentication Database',
    type: 'text',
    enabled: true,
    required: false,
    defaultValue: 'admin',
    displayOrder: 7,
  },
];
```

### PostgreSQL Default Fields
```typescript
const POSTGRESQL_DEFAULT_FIELDS: FieldConfiguration[] = [
  {
    id: 'host',
    name: 'host',
    label: 'Host',
    type: 'text',
    enabled: true,
    required: true,
    placeholder: 'localhost',
    displayOrder: 1,
  },
  {
    id: 'port',
    name: 'port',
    label: 'Port',
    type: 'number',
    enabled: true,
    required: true,
    defaultValue: '5432',
    displayOrder: 2,
  },
  {
    id: 'database',
    name: 'database',
    label: 'Database',
    type: 'text',
    enabled: true,
    required: true,
    displayOrder: 3,
  },
  {
    id: 'username',
    name: 'username',
    label: 'Username',
    type: 'text',
    enabled: true,
    required: true,
    displayOrder: 4,
  },
  {
    id: 'password',
    name: 'password',
    label: 'Password',
    type: 'password',
    enabled: true,
    required: true,
    displayOrder: 5,
  },
  {
    id: 'ssl_mode',
    name: 'ssl_mode',
    label: 'SSL Mode',
    type: 'select',
    enabled: true,
    required: false,
    defaultValue: 'prefer',
    helpText: 'SSL connection mode',
    displayOrder: 6,
  },
  {
    id: 'schema',
    name: 'schema',
    label: 'Schema',
    type: 'text',
    enabled: true,
    required: false,
    defaultValue: 'public',
    displayOrder: 7,
  },
];
```

### Oracle Default Fields
```typescript
const ORACLE_DEFAULT_FIELDS: FieldConfiguration[] = [
  {
    id: 'host',
    name: 'host',
    label: 'Host',
    type: 'text',
    enabled: true,
    required: true,
    placeholder: 'localhost',
    displayOrder: 1,
  },
  {
    id: 'port',
    name: 'port',
    label: 'Port',
    type: 'number',
    enabled: true,
    required: true,
    defaultValue: '1521',
    displayOrder: 2,
  },
  {
    id: 'sid',
    name: 'sid',
    label: 'SID',
    type: 'text',
    enabled: true,
    required: false,
    helpText: 'Oracle System Identifier',
    displayOrder: 3,
  },
  {
    id: 'service_name',
    name: 'service_name',
    label: 'Service Name',
    type: 'text',
    enabled: true,
    required: false,
    helpText: 'Oracle Service Name',
    displayOrder: 4,
  },
  {
    id: 'username',
    name: 'username',
    label: 'Username',
    type: 'text',
    enabled: true,
    required: true,
    displayOrder: 5,
  },
  {
    id: 'password',
    name: 'password',
    label: 'Password',
    type: 'password',
    enabled: true,
    required: true,
    displayOrder: 6,
  },
];
```

### SQL Server Default Fields
```typescript
const SQLSERVER_DEFAULT_FIELDS: FieldConfiguration[] = [
  {
    id: 'host',
    name: 'host',
    label: 'Host',
    type: 'text',
    enabled: true,
    required: true,
    placeholder: 'localhost',
    displayOrder: 1,
  },
  {
    id: 'port',
    name: 'port',
    label: 'Port',
    type: 'number',
    enabled: true,
    required: true,
    defaultValue: '1433',
    displayOrder: 2,
  },
  {
    id: 'database',
    name: 'database',
    label: 'Database',
    type: 'text',
    enabled: true,
    required: true,
    displayOrder: 3,
  },
  {
    id: 'instance_name',
    name: 'instance_name',
    label: 'Instance Name',
    type: 'text',
    enabled: true,
    required: false,
    helpText: 'SQL Server instance name',
    displayOrder: 4,
  },
  {
    id: 'username',
    name: 'username',
    label: 'Username',
    type: 'text',
    enabled: true,
    required: false,
    displayOrder: 5,
  },
  {
    id: 'password',
    name: 'password',
    label: 'Password',
    type: 'password',
    enabled: true,
    required: false,
    displayOrder: 6,
  },
  {
    id: 'windows_auth',
    name: 'windows_auth',
    label: 'Use Windows Authentication',
    type: 'checkbox',
    enabled: true,
    required: false,
    defaultValue: 'false',
    displayOrder: 7,
  },
];
```

## Implementation Notes

### Phase 1: Admin Configuration UI
1. Create DatabaseFieldConfigPage component
2. Create DatabaseTypeList component
3. Create FieldConfigItem component
4. Create FieldConfigModal component
5. Implement state management
6. Add API integration (mock for now)
7. Add styling and responsive design

### Phase 2: Dynamic Connection Form
1. Enhance CreateConnectionModal component
2. Add dynamic field rendering logic
3. Implement field validation based on configuration
4. Add field ordering logic
5. Test with different database types

### Phase 3: Integration
1. Connect to backend API endpoints
2. Add error handling
3. Add loading states
4. Add success notifications
5. Test end-to-end flow

### Testing Considerations
- Test field toggle functionality
- Test add/edit/remove field operations
- Test database type switching
- Test dynamic form rendering
- Test field validation
- Test responsive design
- Test keyboard navigation
- Test screen reader compatibility
