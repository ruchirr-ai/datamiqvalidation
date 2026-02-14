# Migrations List Fix - Workspace ID Filtering Removed

## Issue

Created migrations were not appearing in the Migrations List section on the BQ Redshift Migrations page.

## Root Cause

The `/api/migrations/bq-redshift/list` endpoint was filtering migrations by `workspace_id`:

```python
migrations = repo.get_migrations_by_workspace(
    workspace_id,
    status=status_filter,
    limit=limit,
    offset=offset
)
```

However, the `bq_redshift_migrations` table doesn't have a `workspace_id` column yet, causing the query to fail or return no results.

## Fix Applied

Updated the list endpoint in `backend/routers/bq_redshift_migration.py` to query all migrations without workspace filtering:

**Before:**
```python
repo = BQRedshiftMigrationRepository(db)
migrations = repo.get_migrations_by_workspace(
    workspace_id,
    status=status_filter,
    limit=limit,
    offset=offset
)

return [
    MigrationResponse(
        id=m.id,
        workspace_id=m.workspace_id,  # ❌ Column doesn't exist
        migration_name=m.migration_name,
        ...
    )
    for m in migrations
]
```

**After:**
```python
# Get all migrations (workspace filtering not implemented yet)
query = db.query(MigrationBQRedshift)

if status_filter:
    query = query.filter(MigrationBQRedshift.status == status_filter)

migrations = query.order_by(MigrationBQRedshift.created_at.desc()).limit(limit).offset(offset).all()

return [
    MigrationResponse(
        id=m.id,
        workspace_id=1,  # ✅ Hardcoded until workspace support is added
        migration_name=m.migration_name,
        ...
    )
    for m in migrations
]
```

## Changes Made

1. **Removed workspace filtering** from the query
2. **Added direct SQLAlchemy query** to fetch all migrations
3. **Hardcoded workspace_id to 1** in the response (for compatibility)
4. **Added MigrationBQRedshift import** to the router

## Testing

1. Create a new migration via the wizard
2. Navigate to the Migrations page
3. Verify the migration appears in the list
4. Test status filters (All, Pending, Running, Completed, Failed)
5. Verify all migrations are displayed correctly

## GCS Region Selection

The GCS region selection is already implemented in `ConfigurationSetupStep.tsx`:

```typescript
const GCS_REGIONS = [
  { value: 'us-central1', label: 'us-central1 (Iowa)' },
  { value: 'us-east1', label: 'us-east1 (South Carolina)' },
  { value: 'us-west1', label: 'us-west1 (Oregon)' },
  { value: 'europe-west1', label: 'europe-west1 (Belgium)' },
  { value: 'asia-east1', label: 'asia-east1 (Taiwan)' },
];
```

Users can select the appropriate GCS region based on their bucket location in Step 1 of the Configuration Setup.

## Future Implementation

When implementing full multi-tenancy support:

1. **Add workspace_id column** to `bq_redshift_migrations` table:
   ```sql
   ALTER TABLE bq_redshift_migrations 
   ADD COLUMN workspace_id INTEGER REFERENCES workspaces(id);
   
   CREATE INDEX idx_bq_redshift_migrations_workspace_id 
   ON bq_redshift_migrations(workspace_id);
   ```

2. **Re-enable workspace filtering** in the list endpoint:
   ```python
   query = db.query(MigrationBQRedshift).filter(
       MigrationBQRedshift.workspace_id == workspace_id
   )
   ```

3. **Update create endpoint** to set workspace_id:
   ```python
   migration_data = {
       'workspace_id': workspace_id,
       'migration_name': req.migration_name,
       ...
   }
   ```

## Files Modified

- `backend/routers/bq_redshift_migration.py` - Fixed list endpoint and added import

## Related Files

- `backend/repositories/bq_redshift_migration_repository.py` - Repository with workspace filtering method (not used currently)
- `backend/models/bq_redshift_migration.py` - Migration model (no workspace_id column)
- `frontend/src/pages/migrations/BQRedshiftMigrationsPage.tsx` - Migrations list UI (working correctly)

## Success Criteria

✅ Created migrations appear in the list immediately  
✅ Status filters work correctly  
✅ All migrations are visible to all users (no workspace isolation yet)  
✅ GCS region selection is available in configuration step  
✅ No errors in backend logs  
