# Run Migration Options for Completed Migrations - Fixed

## Issue
When a migration has status "Success" (completed), the "Run Migration" option was not showing in the dropdown menu. Users could not re-run completed migrations.

## Root Cause
The condition for showing "Run Migration" option only included:
- `paused`
- `failed`
- `cancelled`

But did NOT include `completed` status.

## Solution
Updated the condition in `MigrationsPage.tsx` to include `completed` status:

### Before
```typescript
{(migration.status === 'paused' || migration.status === 'failed' || migration.status === 'cancelled') && (
  <button className="dropdown-menu-item" onClick={() => { ... }}>
    Run Migration
  </button>
)}
```

### After
```typescript
{(migration.status === 'paused' || migration.status === 'failed' || migration.status === 'cancelled' || migration.status === 'completed') && (
  <button className="dropdown-menu-item" onClick={() => { ... }}>
    Run Migration
  </button>
)}
```

## Behavior

### For Completed Migrations
When clicking "Run Migration" on a completed migration, users will see a modal with two options:

#### 1. **Resume**
- **Icon**: Play button
- **Title**: Resume
- **Description**: "Continue from where it left off. Preserves existing progress and checkpoints."
- **Action**: Calls `handleResumeMigration()`
- **Use Case**: If you want to continue from the last checkpoint (useful if migration was manually stopped or partially completed)

#### 2. **Restart**
- **Icon**: Circular arrows (refresh)
- **Title**: Restart
- **Description**: "Start fresh from the beginning. Resets migration to pending status."
- **Action**: Calls `handleRestartMigration()`
- **Use Case**: If you want to run the entire migration again from scratch

### User Flow
```
1. User clicks "..." menu on completed migration
   ↓
2. Dropdown shows "Run Migration" option
   ↓
3. User clicks "Run Migration"
   ↓
4. Modal appears with two choices:
   - Resume (continue from checkpoint)
   - Restart (start fresh)
   ↓
5. User selects option
   ↓
6. Migration starts with selected mode
```

## Status-Based Menu Options

### Pending
- ✅ Run Migration (direct, no modal)
- ✅ View Logs
- ✅ Edit Migration
- ✅ Delete Migration

### Running
- ✅ Cancel Migration
- ✅ View Logs
- ✅ Edit Migration
- ✅ Delete Migration

### Paused / Failed / Cancelled / **Completed**
- ✅ Run Migration (shows Resume/Restart modal)
- ✅ View Logs
- ✅ Edit Migration
- ✅ Delete Migration

## Files Modified

1. **frontend/src/pages/MigrationsPage.tsx**
   - Added `migration.status === 'completed'` to the condition
   - Line ~517: Updated conditional rendering

## Testing

### Test Scenario 1: Completed Migration
1. Navigate to Migrations page
2. Find a migration with "Success" badge
3. Click the "..." menu button
4. **Expected**: "Run Migration" option appears
5. Click "Run Migration"
6. **Expected**: Modal appears with Resume and Restart options

### Test Scenario 2: Resume Completed Migration
1. Click "Run Migration" on completed migration
2. Select "Resume"
3. **Expected**: Migration resumes from last checkpoint
4. **Expected**: Status changes to "Running"

### Test Scenario 3: Restart Completed Migration
1. Click "Run Migration" on completed migration
2. Select "Restart"
3. **Expected**: Confirmation dialog appears
4. Confirm restart
5. **Expected**: Migration resets to "Pending" status
6. **Expected**: Can run migration from beginning

## Backend API Endpoints

The frontend calls these endpoints:

### Resume Migration
```
POST /api/migrations/bq-redshift/{id}/resume
```
- Continues migration from last checkpoint
- Preserves progress data
- Updates status to "running"

### Restart Migration
```
POST /api/migrations/bq-redshift/{id}/restart
```
- Resets migration to "pending" status
- Clears progress data
- Clears checkpoint data
- Ready to run from beginning

## UI Components

### Run Options Modal
Located in `MigrationsPage.tsx` (lines ~795-865):

```typescript
{showRunOptions && selectedMigrationForRun && (
  <div className="modal-overlay">
    <div className="modal-dialog">
      <div className="modal-header">
        <h3>Run Migration</h3>
      </div>
      <div className="modal-body">
        {/* Resume Button */}
        <button className="run-option-button" onClick={handleResumeMigration}>
          <div className="run-option-icon">Play Icon</div>
          <div className="run-option-content">
            <div className="run-option-title">Resume</div>
            <div className="run-option-description">Continue from where it left off...</div>
          </div>
        </button>
        
        {/* Restart Button */}
        <button className="run-option-button" onClick={handleRestartMigration}>
          <div className="run-option-icon">Refresh Icon</div>
          <div className="run-option-content">
            <div className="run-option-title">Restart</div>
            <div className="run-option-description">Start fresh from the beginning...</div>
          </div>
        </button>
      </div>
    </div>
  </div>
)}
```

## Use Cases

### Use Case 1: Re-run Successful Migration
**Scenario**: A migration completed successfully, but you want to run it again with updated data.

**Steps**:
1. Click "Run Migration" on completed migration
2. Choose "Restart" to start fresh
3. Migration runs from beginning with current data

### Use Case 2: Complete Partial Migration
**Scenario**: A migration was manually stopped before completion but shows as "completed" for some tables.

**Steps**:
1. Click "Run Migration" on completed migration
2. Choose "Resume" to continue from checkpoint
3. Migration completes remaining tables

### Use Case 3: Incremental Data Sync
**Scenario**: You want to sync new data that was added since last migration.

**Steps**:
1. Click "Run Migration" on completed migration
2. Choose "Resume" to sync only new/changed data
3. Migration uses delta sync (for Path B/C)

## Benefits

1. **Flexibility**: Users can choose to resume or restart based on their needs
2. **Data Safety**: Resume option preserves existing progress
3. **Fresh Start**: Restart option allows complete re-run
4. **Clear UI**: Modal clearly explains each option
5. **Consistent UX**: Same modal for all non-running statuses

## Next Steps

1. ✅ Frontend updated to show option for completed migrations
2. ⚠️ Test with actual completed migration
3. ⚠️ Verify backend endpoints handle completed status correctly
4. ⚠️ Add confirmation dialog for restart (already exists)
5. ⚠️ Consider adding "Run Again" quick action button on success badge

## Servers Status

- **Backend**: Running on http://localhost:8000
- **Frontend**: Running on http://localhost:3000

Both servers are running. Refresh the frontend to see the changes.

## Conclusion

Completed migrations now show the "Run Migration" option with Resume and Restart choices, providing users with flexibility to either continue from where they left off or start fresh from the beginning.
