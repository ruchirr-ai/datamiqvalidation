# Implementation Plan: Database Field Configuration UI

## Overview

This implementation plan focuses on building the UI components for the database field configuration system. The plan follows a component-first approach: UI components → page layout → integration with Create Connection modal → API integration (mocked initially).

## Tasks

- [x] 1. Create TypeScript types and interfaces
  - [x] 1.1 Create field configuration types
    - Define `FieldConfiguration` interface
    - Define `ValidationRules` interface
    - Define `DatabaseType` type
    - Define API response types
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_

- [x] 2. Create default field configurations
  - [x] 2.1 Create default field configuration constants
    - Define MongoDB default fields
    - Define DocumentDB default fields
    - Define PostgreSQL default fields
    - Define MySQL default fields
    - Define Oracle default fields
    - Define SQL Server default fields
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

- [x] 3. Create Toggle Switch component
  - [x] 3.1 Implement Toggle component (`src/components/ui/Toggle.tsx`)
    - Support enabled/disabled states
    - Support onChange callback
    - Apply design tokens for styling
    - Add accessibility support (keyboard, screen reader)
    - _Requirements: 1.4_

- [x] 4. Create Database Type List component
  - [x] 4.1 Implement DatabaseTypeList component
    - Display list of database types with icons
    - Support selection state
    - Handle click events
    - Apply design tokens for styling
    - _Requirements: 1.2, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

- [x] 5. Create Field Configuration Item component
  - [x] 5.1 Implement FieldConfigItem component
    - Display field name, type, and properties
    - Include toggle switch for enabled status
    - Include edit and remove buttons
    - Apply design tokens for styling
    - _Requirements: 1.3, 1.4, 1.6, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_

- [x] 6. Create Add/Edit Field Modal component
  - [x] 6.1 Implement FieldConfigModal component
    - Support add and edit modes
    - Include form fields for all field properties
    - Implement form validation
    - Handle save and cancel actions
    - Apply design tokens for styling
    - _Requirements: 1.5, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 8.1, 8.2, 8.3_

- [x] 7. Create Field Configuration API service
  - [x] 7.1 Create fieldConfigApi service (`src/services/fieldConfigApi.ts`)
    - Implement `getFieldConfigs(databaseType)` method
    - Implement `createFieldConfig(databaseType, field)` method
    - Implement `updateFieldConfig(fieldId, field)` method
    - Implement `deleteFieldConfig(fieldId)` method
    - Implement `toggleFieldEnabled(fieldId, enabled)` method
    - Use mock data initially
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 8. Create Database Field Configuration Page
  - [x] 8.1 Implement DatabaseFieldConfigPage component
    - Create two-column layout (sidebar + main pane)
    - Integrate DatabaseTypeList in left sidebar
    - Display field configuration list in right pane
    - Handle database type selection
    - Handle field toggle, edit, remove actions
    - Show add field button
    - Implement loading and error states
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.7, 2.8_
  
  - [x] 8.2 Add responsive design for mobile and tablet
    - Implement collapsible sidebar for mobile
    - Use dropdown for database type selection on mobile
    - Stack field items vertically
    - _Requirements: 1.1, 1.2, 1.3_

- [x] 9. Add route for Database Field Configuration Page
  - [x] 9.1 Add route to React Router
    - Add `/admin/data-connections/sources` route
    - Protect route with admin role requirement
    - Update navigation to include link
    - _Requirements: 1.1_

- [x] 10. Create Dynamic Field component
  - [x] 10.1 Implement DynamicField component
    - Render different input types based on field configuration
    - Support text, number, password, select, checkbox types
    - Apply validation rules from configuration
    - Display help text and error messages
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [x] 11. Enhance Create Connection Modal
  - [x] 11.1 Update CreateConnectionModal component
    - Fetch field configuration when database type changes
    - Dynamically render fields based on configuration
    - Filter to show only enabled fields
    - Order fields by displayOrder property
    - Apply validation rules from configuration
    - Pre-populate default values
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [x] 12. Add empty states and loading states
  - [x] 12.1 Create EmptyState component
    - Display when no fields are configured
    - Show "Add Your First Field" button
    - _Requirements: 1.3_
  
  - [x] 12.2 Create LoadingState component
    - Display while fetching field configurations
    - Show loading spinner
    - _Requirements: 1.3_

- [x] 13. Add error handling and notifications
  - [x] 13.1 Implement error handling
    - Display error messages for API failures
    - Show retry button on errors
    - Handle validation errors in forms
    - _Requirements: 1.4, 1.5, 1.6_
  
  - [x] 13.2 Add success notifications
    - Show success message after field creation
    - Show success message after field update
    - Show success message after field deletion
    - Show success message after toggle
    - _Requirements: 1.4, 1.5, 1.6_

- [x] 14. Add confirmation dialogs
  - [x] 14.1 Create ConfirmDialog component
    - Display confirmation before field deletion
    - Support custom messages
    - Handle confirm and cancel actions
    - _Requirements: 1.6_

- [x] 15. Add accessibility features
  - [x] 15.1 Implement keyboard navigation
    - Tab through database types
    - Enter to select database type
    - Tab through field items
    - Space to toggle field enabled status
    - Enter to edit field
    - Delete key to remove field (with confirmation)
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 1.6_
  
  - [x] 15.2 Add ARIA labels and screen reader support
    - Add proper ARIA labels for all interactive elements
    - Announce state changes
    - Announce loading states
    - Announce success/error messages
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 1.6_

- [x] 16. Style components with design tokens
  - [x] 16.1 Create CSS modules for components
    - Style DatabaseTypeList component
    - Style FieldConfigItem component
    - Style FieldConfigModal component
    - Style DatabaseFieldConfigPage component
    - Apply responsive design
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

- [ ] 17. Test components
  - [ ]* 17.1 Write unit tests for Toggle component
    - Test toggle state changes
    - Test onChange callback
    - Test keyboard interaction
    - _Requirements: 1.4_
  
  - [ ]* 17.2 Write unit tests for DatabaseTypeList component
    - Test database type rendering
    - Test selection state
    - Test click handling
    - _Requirements: 1.2, 2.1-2.8_
  
  - [ ]* 17.3 Write unit tests for FieldConfigItem component
    - Test field display
    - Test toggle functionality
    - Test edit and remove buttons
    - _Requirements: 1.3, 1.4, 1.6_
  
  - [ ]* 17.4 Write unit tests for FieldConfigModal component
    - Test form rendering in add mode
    - Test form rendering in edit mode
    - Test form validation
    - Test save and cancel actions
    - _Requirements: 1.5, 3.1-3.8_
  
  - [ ]* 17.5 Write unit tests for DatabaseFieldConfigPage component
    - Test page layout
    - Test database type selection
    - Test field list rendering
    - Test add, edit, remove actions
    - _Requirements: 1.1-1.6_
  
  - [ ]* 17.6 Write unit tests for DynamicField component
    - Test rendering different field types
    - Test validation
    - Test error display
    - _Requirements: 4.1-4.6_
  
  - [ ]* 17.7 Write unit tests for enhanced CreateConnectionModal
    - Test dynamic field rendering
    - Test field filtering by enabled status
    - Test field ordering
    - Test validation
    - _Requirements: 4.1-4.6_

- [ ] 18. Integration testing
  - [ ]* 18.1 Test complete field configuration flow
    - Test adding a new field
    - Test editing a field
    - Test removing a field
    - Test toggling field enabled status
    - Test switching database types
    - _Requirements: 1.1-1.6, 2.1-2.8_
  
  - [ ]* 18.2 Test dynamic connection form integration
    - Test field configuration affects connection form
    - Test enabled/disabled fields
    - Test field ordering
    - Test validation rules
    - _Requirements: 4.1-4.6_

- [ ] 19. Documentation
  - [ ] 19.1 Document DatabaseFieldConfigPage component
    - Document component props and usage
    - Document state management
    - Document API integration
    - _Requirements: Documentation standards_
  
  - [ ] 19.2 Document field configuration API
    - Document API endpoints
    - Document request/response formats
    - Document error handling
    - _Requirements: Documentation standards, 10.1-10.8_
  
  - [ ] 19.3 Document DynamicField component
    - Document component props and usage
    - Document field types
    - Document validation
    - _Requirements: Documentation standards_

- [x] 20. Final checkpoint - Ensure UI implementation is complete
  - Verify all components render correctly
  - Verify responsive design works
  - Verify accessibility features work
  - Verify integration with Create Connection modal
  - Test with different database types
  - Ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional testing tasks
- Each task references specific requirements for traceability
- UI implementation uses React + TypeScript
- Styling uses CSS modules with design tokens
- API integration uses mock data initially, to be replaced with real API calls later
- All components follow accessibility best practices
- Responsive design supports desktop, tablet, and mobile
- Focus on minimal, clean UI following existing design system

