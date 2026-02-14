# Create Migration Mode Fix

## Issue
When clicking "Create" to create a new migration, the wizard was showing "Edit Migration" instead of "Setup Data Migration".

## Root Cause
The `CreateMigrationWizard` component checks for an `edit` parameter in the URL to determine if it's in edit mode. However, when navigating from edit mode back to create mode, the component wasn't properly resetting its state if the `edit` parameter was removed from the URL.

The browser might cache the previous URL state or the component state wasn't being reset when the URL changed from `/migrations/create?edit=123` to `/migrations/create`.

## Solution
Enhanced the `useEffect` hook that monitors the `searchParams` to explicitly reset to create mode when there's no `edit` parameter:

### Before
```typescript
useEffect(() => {
  const editId = searchParams.get('edit');
  if (editId) {
    setIsEditMode(true);
    setEditMigrationId(parseInt(editId));
    loadMigrationData(parseInt(editId));
  }
}, [searchParams]);
```

### After
```typescript
useEffect(() => {
  const editId = searchParams.get('edit');
  if (editId) {
    setIsEditMode(true);
    setEditMigrationId(parseInt(editId));
    loadMigrationData(parseInt(editId));
  } else {
    // Reset to create mode if no edit parameter
    setIsEditMode(false);
    setEditMigrationId(null);
    setFormData(INITIAL_FORM_DATA);
    setCurrentStep(1);
  }
}, [searchParams]);
```

## What Changed

### File Modified
- `frontend/src/components/migrations/CreateMigrationWizard.tsx`

### Changes Made
1. Added `else` block to the `useEffect` hook
2. Explicitly set `isEditMode` to `false` when no edit parameter
3. Reset `editMigrationId` to `null`
4. Reset `formData` to `INITIAL_FORM_DATA`
5. Reset `currentStep` to `1`

## How It Works

### Create Mode (No edit parameter)
1. User clicks "+ New" → "Create" from migrations page
2. Navigates to `/migrations/create` (no query parameters)
3. `useEffect` detects no `edit` parameter
4. Sets `isEditMode = false`
5. Resets all form data to initial state
6. Shows "Setup Data Migration" title
7. Shows "Create Migration" button

### Edit Mode (With edit parameter)
1. User clicks "Edit Migration" from dropdown menu
2. Navigates to `/migrations/create?edit=123`
3. `useEffect` detects `edit=123` parameter
4. Sets `isEditMode = true`
5. Loads existing migration data
6. Shows "Edit Migration" title
7. Shows "Update Migration" button

## Testing

### Test Create Mode
1. Navigate to http://localhost:3000/migrations
2. Click "+ New" → "Create"
3. **Expected**: 
   - Title shows "Setup Data Migration"
   - Form is empty/default values
   - Button shows "Create Migration"

### Test Edit Mode
1. Navigate to http://localhost:3000/migrations
2. Click three-dot menu on any migration
3. Click "Edit Migration"
4. **Expected**:
   - Title shows "Edit Migration"
   - Form is pre-filled with migration data
   - Button shows "Update Migration"

### Test Mode Switching
1. Start in edit mode (edit a migration)
2. Click browser back button or navigate to migrations page
3. Click "+ New" → "Create"
4. **Expected**:
   - Mode properly switches to create
   - Form is reset to empty/default
   - Title shows "Setup Data Migration"

## UI Indicators

The wizard shows different text based on mode:

### Create Mode
- **Title**: "Setup Data Migration"
- **Subtitle**: "Configure your data migration in 5 simple steps"
- **Submit Button**: "Create Migration"
- **Loading State**: "Creating..."

### Edit Mode
- **Title**: "Edit Migration"
- **Subtitle**: "Update your migration configuration"
- **Submit Button**: "Update Migration"
- **Loading State**: "Updating..."

## Additional Notes

### Read-Only Fields in Edit Mode
Some fields are read-only when editing:
- Source Connection (cannot change)
- Target Connection (cannot change)
- Migration Type (cannot change)

### Sensitive Data in Edit Mode
For security, sensitive data is not loaded in edit mode:
- AWS Secret Access Key
- Service Account JSON
- Passwords

Users must re-enter these values if they want to update them.

## Verification

After the fix, verify:
1. ✅ Create mode shows correct title
2. ✅ Create mode has empty form
3. ✅ Edit mode shows correct title
4. ✅ Edit mode loads existing data
5. ✅ Switching between modes works correctly
6. ✅ Browser back/forward buttons work correctly

## Related Files

- `frontend/src/components/migrations/CreateMigrationWizard.tsx` - Main wizard component
- `frontend/src/pages/MigrationsPage.tsx` - Navigation to create/edit
- All step components inherit the `isEditMode` prop

## Conclusion

The fix ensures that the wizard properly resets to create mode when navigating without an edit parameter, preventing the "stuck in edit mode" issue.
