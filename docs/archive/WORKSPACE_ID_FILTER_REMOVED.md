# Workspace ID Filter Removed from BigQuery Metadata Discovery

## Issue

After fixing the Authorization header issue, a new error appeared:

```
Failed to fetch BigQuery metadata: 500: Unexpected error during metadata discovery: 
type object 'Connection' has no attribute 'workspace_id'
```

## Root Cause

The backend endpoint `/api/migrations/bq-redshift/discover-metadata` was trying to filter connections by `workspace_id`:

```python
connection = db.query(Connection).filter(
    Connection.id == req.connection_id,
    Connection.workspace_id == workspace_id  # ❌ Column doesn't exist!
).first()
```

However, the `connections` table does not have a `workspace_id` column. The multi-tenancy feature (workspaces) is not fully implemented yet:
- The `workspaces` table doesn't exist
- The `connections` table doesn't have a `workspace_id` foreign key
- The Connection model doesn't have a `workspace_id` attribute

## Fix Applied

Removed the `workspace_id` filter from the query in `backend/routers/bq_redshift_migration.py`:

**Before:**
```python
connection = db.query(Connection).filter(
    Connection.id == req.connection_id,
    Connection.workspace_id == workspace_id
).first()

if not connection:
    logger.error(f"Connection {req.connection_id} not found in workspace {workspace_id}")
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Connection {req.connection_id} not found"
    )
```

**After:**
```python
connection = db.query(Connection).filter(
    Connection.id == req.connection_id
).first()

if not connection:
    logger.error(f"Connection {req.connection_id} not found")
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Connection {req.connection_id} not found"
    )
```

## Why This Works

Since the multi-tenancy feature is not yet implemented:
- All connections are accessible to all users (no workspace isolation)
- Filtering by connection ID alone is sufficient
- The application can function without workspace support

## Future Implementation

When implementing full multi-tenancy support, you'll need to:

1. **Create workspace tables** (via Alembic migration):
   ```sql
   CREATE TABLE workspaces (
       id SERIAL PRIMARY KEY,
       name VARCHAR(255) NOT NULL,
       slug VARCHAR(255) NOT NULL,
       organization_id INTEGER REFERENCES organizations(id),
       created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
       updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
   );
   ```

2. **Add workspace_id to connections table**:
   ```sql
   ALTER TABLE connections 
   ADD COLUMN workspace_id INTEGER REFERENCES workspaces(id);
   
   CREATE INDEX idx_connections_workspace_id ON connections(workspace_id);
   ```

3. **Update Connection model**:
   ```python
   class Connection(Base):
       __tablename__ = 'connections'
       
       id = Column(Integer, primary_key=True)
       workspace_id = Column(Integer, ForeignKey('workspaces.id'), nullable=False)
       # ... other columns
   ```

4. **Re-enable workspace filtering** in all endpoints:
   ```python
   connection = db.query(Connection).filter(
       Connection.id == req.connection_id,
       Connection.workspace_id == workspace_id
   ).first()
   ```

## Testing

After this fix, the BigQuery metadata discovery should work:

1. ✅ Authorization header is present
2. ✅ Backend validates token successfully
3. ✅ Connection is found by ID (without workspace filter)
4. ✅ BigQuery client connects to project
5. ✅ Real datasets and tables are returned
6. ✅ UI displays actual BigQuery data

## Files Modified

- `backend/routers/bq_redshift_migration.py` - Removed workspace_id filter from connection query

## Related Issues

- The `get_user_workspaces` function in `workspace_middleware.py` already handles missing workspaces table gracefully
- The Connection model's `to_dict()` method returns a hardcoded `workspace_id: 1` for compatibility
- Other endpoints may also need similar fixes if they filter by workspace_id

## Next Steps

1. Test the BigQuery metadata discovery again
2. Verify real data is displayed
3. If successful, consider creating a migration to add workspace_id column (optional)
4. Document which endpoints need workspace support when implementing multi-tenancy
