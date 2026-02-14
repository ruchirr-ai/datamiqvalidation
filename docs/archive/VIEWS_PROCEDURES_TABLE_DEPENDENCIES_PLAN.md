# Views & Stored Procedures - Table Format with Dependencies

## Overview
Convert Views and Stored Procedures sections from card layout to table format (similar to Tables section) and add comprehensive dependency analysis showing all dependent tables, views, functions, and nested stored procedures.

## Requirements

### Display Format
**Table Columns**:
1. Name
2. Created By (if available)
3. Created Time
4. Type (View/Materialized View or Procedure/Function)
5. Dependencies Count
6. Actions (View Details button)

### Dependency Analysis
When clicking on a view or stored procedure, show:
- **Tables**: All referenced tables
- **Views**: All referenced views (including nested)
- **Functions**: All referenced user-defined functions
- **Stored Procedures**: Any stored procedures called within
- **Dependency Tree**: Visual hierarchy of dependencies

### Features
- Parse SQL definitions to extract ALL dependencies
- Handle nested queries and subqueries
- Detect circular dependencies
- Show dependency depth/levels
- Expandable rows to show dependencies inline

## Implementation Steps

### Backend Changes

#### 1. Integrate SQL Dependency Parser
**File**: `backend/services/bigquery_assessment_service.py`

**Updates Needed**:
```python
from utils.sql_dependency_parser import SQLDependencyParser

async def collect_views(self):
    # Existing view collection code
    # Add dependency parsing
    parser = SQLDependencyParser()
    
    for view in views:
        dependencies = parser.parse_dependencies(view['view_definition'])
        view['dependencies'] = dependencies
        
        # Cross-reference with known tables/views
        view['dependent_tables'] = self._resolve_table_dependencies(dependencies['tables'])
        view['dependent_views'] = self._resolve_view_dependencies(dependencies['tables'])
        view['dependent_functions'] = dependencies['functions']
```

#### 2. Add Dependency Resolution Methods
```python
def _resolve_table_dependencies(self, table_refs: List[str]) -> List[str]:
    """Cross-reference table references with actual tables"""
    # Match against collected tables
    pass

def _resolve_view_dependencies(self, table_refs: List[str]) -> List[str]:
    """Cross-reference table references with actual views"""
    # Match against collected views
    pass
```

#### 3. Update Stored Procedures Collection
**File**: `backend/services/bigquery_assessment_service.py`

```python
async def collect_routines(self):
    # Existing routine collection
    # Add dependency parsing for stored procedures
    parser = SQLDependencyParser()
    
    for routine in routines:
        if routine['routine_definition']:
            dependencies = parser.parse_dependencies(routine['routine_definition'])
            routine['dependencies'] = dependencies
            
            # Detect stored procedure calls
            routine['calls_procedures'] = self._extract_procedure_calls(routine['routine_definition'])
```

#### 4. Enhance SQL Dependency Parser
**File**: `backend/utils/sql_dependency_parser.py`

**Add Methods**:
```python
def extract_procedure_calls(self, sql: str) -> List[str]:
    """Extract CALL statements for stored procedures"""
    pattern = r'CALL\s+`?([a-zA-Z0-9_.-]+)`?'
    matches = re.findall(pattern, sql, re.IGNORECASE)
    return matches

def build_dependency_tree(self, dependencies: Dict, all_objects: Dict) -> Dict:
    """Build hierarchical dependency tree"""
    # Recursive function to build tree
    pass
```

#### 5. Update Database Models
**File**: `backend/models/assessment.py`

**Add Fields** (if not already present):
```python
class AssessmentView(Base):
    # Existing fields...
    dependent_tables = Column(ARRAY(Text), nullable=True)
    dependent_views = Column(ARRAY(Text), nullable=True)
    dependent_functions = Column(ARRAY(Text), nullable=True)
    dependency_depth = Column(Integer, nullable=True)

class AssessmentRoutine(Base):
    # Existing fields...
    dependent_tables = Column(ARRAY(Text), nullable=True)
    dependent_views = Column(ARRAY(Text), nullable=True)
    dependent_functions = Column(ARRAY(Text), nullable=True)
    calls_procedures = Column(ARRAY(Text), nullable=True)
    dependency_depth = Column(Integer, nullable=True)
```

### Frontend Changes

#### 1. Convert Views Section to Table Format
**File**: `frontend/src/pages/AssessmentReportPage.tsx`

**Replace ViewsSection Component**:
```typescript
const ViewsSection: React.FC<any> = ({ views, formatDate }) => {
  const [expandedView, setExpandedView] = useState<number | null>(null);
  
  return (
    <div className="section-content">
      <h2 className="section-heading">Views ({views.length})</h2>
      
      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Created Time</th>
              <th>Dependencies</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {views.map((view, index) => (
              <>
                <tr key={index}>
                  <td className="font-medium">{view.view_name}</td>
                  <td>
                    <Badge variant={view.view_type === 'MATERIALIZED_VIEW' ? 'info' : 'default'}>
                      {view.view_type}
                    </Badge>
                  </td>
                  <td>{formatDate(view.creation_time)}</td>
                  <td>
                    {view.dependencies ? (
                      <div className="dependencies-summary">
                        {view.dependent_tables?.length > 0 && (
                          <Badge variant="default">
                            {view.dependent_tables.length} Tables
                          </Badge>
                        )}
                        {view.dependent_views?.length > 0 && (
                          <Badge variant="info">
                            {view.dependent_views.length} Views
                          </Badge>
                        )}
                      </div>
                    ) : (
                      <span className="text-muted">None</span>
                    )}
                  </td>
                  <td>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setExpandedView(expandedView === index ? null : index)}
                    >
                      {expandedView === index ? 'Hide' : 'Show'} Details
                    </Button>
                  </td>
                </tr>
                
                {expandedView === index && (
                  <tr className="expanded-row">
                    <td colSpan={5}>
                      <ViewDependencyDetails view={view} />
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
```

#### 2. Create Dependency Details Component
```typescript
const ViewDependencyDetails: React.FC<{ view: any }> = ({ view }) => {
  return (
    <div className="dependency-details">
      <div className="dependency-section">
        <h4>SQL Definition</h4>
        <pre className="sql-code"><code>{view.view_definition}</code></pre>
      </div>
      
      {view.dependencies && (
        <div className="dependency-section">
          <h4>Dependencies</h4>
          
          {view.dependent_tables && view.dependent_tables.length > 0 && (
            <div className="dependency-group">
              <h5><Database size={16} /> Tables ({view.dependent_tables.length})</h5>
              <div className="dependency-list">
                {view.dependent_tables.map((table, idx) => (
                  <Badge key={idx} variant="default">{table}</Badge>
                ))}
              </div>
            </div>
          )}
          
          {view.dependent_views && view.dependent_views.length > 0 && (
            <div className="dependency-group">
              <h5><Eye size={16} /> Views ({view.dependent_views.length})</h5>
              <div className="dependency-list">
                {view.dependent_views.map((v, idx) => (
                  <Badge key={idx} variant="info">{v}</Badge>
                ))}
              </div>
            </div>
          )}
          
          {view.dependent_functions && view.dependent_functions.length > 0 && (
            <div className="dependency-group">
              <h5><Code size={16} /> Functions ({view.dependent_functions.length})</h5>
              <div className="dependency-list">
                {view.dependent_functions.map((func, idx) => (
                  <Badge key={idx} variant="warning">{func}</Badge>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
```

#### 3. Convert Stored Procedures Section
Similar table format with additional "Calls Procedures" column and dependency details.

#### 4. Add CSS Styles
**File**: `frontend/src/pages/AssessmentReportPage.css`

```css
/* Expanded Row Styles */
.expanded-row {
  background: var(--color-bg-primary);
}

.expanded-row td {
  padding: 0 !important;
}

.dependency-details {
  padding: var(--spacing-6);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-6);
}

.dependency-section {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-4);
}

.dependency-section h4 {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin: 0;
}

.dependency-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
}

.dependency-group h5 {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-secondary);
  margin: 0;
}

.dependency-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-2);
}

.dependencies-summary {
  display: flex;
  gap: var(--spacing-2);
  flex-wrap: wrap;
}

.sql-code {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-divider);
  border-radius: var(--radius-sm);
  padding: var(--spacing-4);
  overflow-x: auto;
  margin: 0;
  max-height: 300px;
  overflow-y: auto;
}

.sql-code code {
  font-family: var(--font-family-code);
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}
```

## Database Migration

### Create Migration for New Fields
**File**: `backend/alembic/versions/016_add_dependency_fields.py`

```python
"""Add dependency fields to views and routines

Revision ID: 016_add_dependency_fields
"""

def upgrade():
    # Add dependency fields to assessment_views
    op.add_column('assessment_views', 
        sa.Column('dependent_tables', postgresql.ARRAY(sa.Text()), nullable=True))
    op.add_column('assessment_views', 
        sa.Column('dependent_views', postgresql.ARRAY(sa.Text()), nullable=True))
    op.add_column('assessment_views', 
        sa.Column('dependent_functions', postgresql.ARRAY(sa.Text()), nullable=True))
    op.add_column('assessment_views', 
        sa.Column('dependency_depth', sa.Integer(), nullable=True))
    
    # Add dependency fields to assessment_routines
    op.add_column('assessment_routines', 
        sa.Column('dependent_tables', postgresql.ARRAY(sa.Text()), nullable=True))
    op.add_column('assessment_routines', 
        sa.Column('dependent_views', postgresql.ARRAY(sa.Text()), nullable=True))
    op.add_column('assessment_routines', 
        sa.Column('dependent_functions', postgresql.ARRAY(sa.Text()), nullable=True))
    op.add_column('assessment_routines', 
        sa.Column('calls_procedures', postgresql.ARRAY(sa.Text()), nullable=True))
    op.add_column('assessment_routines', 
        sa.Column('dependency_depth', sa.Integer(), nullable=True))

def downgrade():
    # Remove columns
    pass
```

## Testing Plan

### Backend Tests
1. Test SQL dependency parser with various SQL patterns
2. Test nested query parsing
3. Test circular dependency detection
4. Test stored procedure call extraction

### Frontend Tests
1. Test table rendering with dependencies
2. Test expand/collapse functionality
3. Test dependency badge display
4. Test responsive design

### Integration Tests
1. Run full assessment with dependency analysis
2. Verify all dependencies are captured
3. Test with complex nested views
4. Test with stored procedures calling other procedures

## Benefits

### User Experience
- **Cleaner Layout**: Table format is more scannable than cards
- **Better Information Density**: More data visible at once
- **Dependency Visibility**: Clear understanding of object relationships
- **Impact Analysis**: Know what will be affected by changes

### Technical
- **Comprehensive Analysis**: Captures all dependencies including nested
- **Reusable Parser**: SQL dependency parser can be used elsewhere
- **Migration Planning**: Helps plan migration order based on dependencies
- **Risk Assessment**: Identify complex dependencies early

## Timeline Estimate
- Backend Integration: 4-6 hours
- Frontend Implementation: 3-4 hours
- Testing & Refinement: 2-3 hours
- **Total**: 9-13 hours

## Priority
**HIGH** - This significantly improves the assessment report's value for migration planning.

## Next Steps
1. Create database migration for new fields
2. Integrate SQL dependency parser into backend
3. Update frontend Views section
4. Update frontend Stored Procedures section
5. Add comprehensive tests
6. Document dependency analysis capabilities
