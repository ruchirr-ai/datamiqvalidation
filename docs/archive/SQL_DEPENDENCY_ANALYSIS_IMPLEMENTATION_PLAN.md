# SQL Dependency Analysis Implementation Plan

## Overview
Implement SQL query analysis for views and stored procedures to extract and display dependent tables, views, and functions with nested dependency support.

## Current Status
- ✅ UI changes complete: "Back to Assessments" changed to "Back"
- ✅ Sharded Tables section removed from UI
- ✅ SQL dependency parser utility created (`backend/utils/sql_dependency_parser.py`)
- ⏳ Backend integration pending
- ⏳ Frontend display pending

## Backend Implementation

### 1. SQL Dependency Parser (`backend/utils/sql_dependency_parser.py`)
**Status**: ✅ Created

Features:
- Extracts table/view references from FROM, JOIN, INTO clauses
- Extracts user-defined function calls
- Filters out BigQuery system functions
- Removes SQL comments and string literals to avoid false matches
- Supports nested dependency analysis with cycle detection
- Handles CTEs (Common Table Expressions) properly

### 2. Update BigQuery Assessment Service
**File**: `backend/services/bigquery_assessment_service.py`

**Changes Needed**:

#### In `collect_views()` method:
```python
from utils.sql_dependency_parser import sql_parser

async def collect_views(self) -> List[Dict]:
    """Collect view and materialized view information with dependencies"""
    views = []
    
    # First pass: collect all views
    all_views = {}
    for dataset in self.client.list_datasets():
        for table in self.client.list_tables(dataset.dataset_id):
            table_ref = self.client.get_table(f"{self.project_id}.{dataset.dataset_id}.{table.table_id}")
            
            if table_ref.table_type in ['VIEW', 'MATERIALIZED_VIEW']:
                view_name = f"{dataset.dataset_id}.{table.table_id}"
                view_sql = table_ref.view_query or table_ref.mview_query
                all_views[view_name] = view_sql
    
    # Second pass: analyze dependencies
    for dataset in self.client.list_datasets():
        for table in self.client.list_tables(dataset.dataset_id):
            table_ref = self.client.get_table(f"{self.project_id}.{dataset.dataset_id}.{table.table_id}")
            
            if table_ref.table_type in ['VIEW', 'MATERIALIZED_VIEW']:
                view_name = f"{dataset.dataset_id}.{table.table_id}"
                view_sql = table_ref.view_query or table_ref.mview_query
                
                # Analyze dependencies
                dependencies = sql_parser.analyze_nested_dependencies(
                    view_name,
                    view_sql,
                    all_views
                )
                
                views.append({
                    'view_name': view_name,
                    'view_type': table_ref.table_type,
                    'view_definition': view_sql,
                    'creation_time': table_ref.created,
                    'dependencies': json.dumps(dependencies)  # Store as JSON
                })
    
    return views
```

#### In `collect_routines()` method:
```python
async def collect_routines(self) -> List[Dict]:
    """Collect stored procedures and functions with dependencies"""
    routines = []
    
    # First pass: collect all routines
    all_routines = {}
    for dataset in self.client.list_datasets():
        for routine in self.client.list_routines(dataset.dataset_id):
            routine_ref = self.client.get_routine(routine.reference)
            routine_name = f"{dataset.dataset_id}.{routine.routine_id}"
            all_routines[routine_name] = routine_ref.body
    
    # Combine with views for cross-referencing
    all_objects = {**all_views, **all_routines}  # Need to pass all_views from collect_views
    
    # Second pass: analyze dependencies
    for dataset in self.client.list_datasets():
        for routine in self.client.list_routines(dataset.dataset_id):
            routine_ref = self.client.get_routine(routine.reference)
            routine_name = f"{dataset.dataset_id}.{routine.routine_id}"
            
            # Analyze dependencies
            dependencies = sql_parser.analyze_nested_dependencies(
                routine_name,
                routine_ref.body,
                all_objects
            )
            
            routines.append({
                'routine_name': routine_name,
                'routine_type': routine_ref.type_,
                'return_type': str(routine_ref.return_type) if routine_ref.return_type else None,
                'definition': routine_ref.body,
                'external_language': routine_ref.language,
                'creation_time': routine_ref.created,
                'call_frequency': 0,
                'dependencies': json.dumps(dependencies)  # Store as JSON
            })
    
    return routines
```

### 3. Update Database Model
**File**: `backend/models/assessment.py`

**Changes Needed**:
- `dependencies` field in `AssessmentView` is already JSONB, so no changes needed
- Verify `AssessmentRoutine` has a `dependencies` field (add if missing)

### 4. Create Database Migration
**File**: `backend/alembic/versions/016_add_routine_dependencies.py`

```python
"""Add dependencies field to routines if missing

Revision ID: 016_add_routine_dependencies
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # Check if column exists, add if not
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='assessment_routines' AND column_name='dependencies'
            ) THEN
                ALTER TABLE assessment_routines 
                ADD COLUMN dependencies JSONB;
            END IF;
        END $$;
    """)

def downgrade():
    op.drop_column('assessment_routines', 'dependencies')
```

## Frontend Implementation

### 1. Update Views Section
**File**: `frontend/src/pages/AssessmentReportPage.tsx`

**Changes Needed**:

Add a dependency tree component:
```typescript
const DependencyTree: React.FC<{ dependencies: any[], level?: number }> = ({ dependencies, level = 0 }) => {
  if (!dependencies || dependencies.length === 0) return null;
  
  return (
    <ul className="dependency-tree" style={{ marginLeft: `${level * 20}px` }}>
      {dependencies.map((dep: any, idx: number) => (
        <li key={idx} className="dependency-item">
          <span className={`dependency-type-${dep.type}`}>
            {dep.type === 'table' && <TableIcon size={14} />}
            {dep.type === 'view' && <Eye size={14} />}
            {dep.type === 'function' && <Code size={14} />}
            {dep.name}
          </span>
          {dep.dependencies && dep.dependencies.length > 0 && (
            <DependencyTree dependencies={dep.dependencies} level={level + 1} />
          )}
        </li>
      ))}
    </ul>
  );
};
```

Update ViewsSection to show dependencies:
```typescript
const ViewsSection: React.FC<any> = ({ views, formatDate }) => {
  const [expandedView, setExpandedView] = useState<number | null>(null);
  
  return (
    <div className="section-content">
      <h2 className="section-heading">Views ({views.length})</h2>
      {views.length === 0 ? (
        <div className="empty-state">
          <Eye size={48} />
          <p>No views found</p>
        </div>
      ) : (
        <div className="views-list">
          {views.map((view: any, index: number) => {
            const isExpanded = expandedView === index;
            const dependencies = view.dependencies ? JSON.parse(view.dependencies) : [];
            
            return (
              <div key={index} className="view-item">
                <div className="view-header">
                  <div className="view-info">
                    <h4 className="view-name">{view.view_name}</h4>
                    <div className="view-meta">
                      <Badge variant={view.view_type === 'VIEW' ? 'info' : 'warning'}>
                        {view.view_type}
                      </Badge>
                      <span className="text-sm text-muted">
                        Created: {formatDate(view.creation_time)}
                      </span>
                      {dependencies.length > 0 && (
                        <Badge variant="default">{dependencies.length} dependencies</Badge>
                      )}
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setExpandedView(isExpanded ? null : index)}
                  >
                    {isExpanded ? 'Hide' : 'Show'} Details
                  </Button>
                </div>
                
                {isExpanded && (
                  <div className="view-details">
                    {dependencies.length > 0 && (
                      <div className="dependencies-section">
                        <h5>Dependencies:</h5>
                        <DependencyTree dependencies={dependencies} />
                      </div>
                    )}
                    <div className="view-definition">
                      <h5>Definition:</h5>
                      <pre><code>{view.view_definition}</code></pre>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
```

### 2. Update Stored Procedures Section
Similar changes to show dependencies in stored procedures.

### 3. Add CSS Styles
**File**: `frontend/src/pages/AssessmentReportPage.css`

```css
.dependency-tree {
  list-style: none;
  padding-left: 0;
  margin: 8px 0;
}

.dependency-item {
  padding: 4px 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.dependency-type-table {
  color: var(--color-primary);
  display: flex;
  align-items: center;
  gap: 4px;
}

.dependency-type-view {
  color: var(--color-info);
  display: flex;
  align-items: center;
  gap: 4px;
}

.dependency-type-function {
  color: var(--color-warning);
  display: flex;
  align-items: center;
  gap: 4px;
}

.view-details, .routine-details {
  margin-top: 16px;
  padding: 16px;
  background: var(--color-bg-secondary);
  border-radius: var(--radius-md);
}

.dependencies-section {
  margin-bottom: 16px;
}

.dependencies-section h5 {
  margin-bottom: 8px;
  font-weight: var(--font-weight-semibold);
}

.view-definition pre {
  background: var(--color-bg-surface);
  padding: 12px;
  border-radius: var(--radius-sm);
  overflow-x: auto;
  font-size: var(--font-size-sm);
}
```

## Testing Plan

### 1. Unit Tests for SQL Parser
**File**: `backend/tests/test_sql_dependency_parser.py`

Test cases:
- Simple SELECT with FROM clause
- Multiple JOINs
- Nested subqueries
- CTEs (WITH clause)
- Function calls
- Circular dependencies
- Complex nested views

### 2. Integration Tests
- Test view collection with dependencies
- Test routine collection with dependencies
- Test nested dependency resolution
- Test with real BigQuery data

### 3. UI Testing
- Verify dependency tree displays correctly
- Test expand/collapse functionality
- Test with various nesting levels
- Verify icons and styling

## Implementation Steps

1. ✅ Create SQL dependency parser utility
2. ⏳ Update BigQuery assessment service to use parser
3. ⏳ Create/update database migration if needed
4. ⏳ Update frontend to display dependency trees
5. ⏳ Add CSS styling for dependency visualization
6. ⏳ Test with sample data
7. ⏳ Run full assessment to verify
8. ⏳ Document the feature

## Benefits

- **Migration Planning**: Understand object dependencies before migration
- **Impact Analysis**: See what will be affected by changes
- **Complexity Assessment**: Identify highly coupled objects
- **Documentation**: Auto-generated dependency documentation
- **Risk Assessment**: Identify circular dependencies and complex chains

## Notes

- The parser handles BigQuery SQL syntax
- System functions are filtered out to show only user-defined dependencies
- Circular dependencies are detected and prevented
- Nesting level is limited to 10 to prevent infinite recursion
- Dependencies are stored as JSONB for flexibility and querying
