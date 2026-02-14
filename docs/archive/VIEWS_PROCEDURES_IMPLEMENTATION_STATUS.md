# Views & Stored Procedures Table Implementation Status

## Current Status: READY TO IMPLEMENT

### Completed
- ✅ SQL Dependency Parser exists and is complete (`backend/utils/sql_dependency_parser.py`)
- ✅ Implementation plan documented (`VIEWS_PROCEDURES_TABLE_DEPENDENCIES_PLAN.md`)
- ✅ Database models have necessary fields (AssessmentView, AssessmentRoutine)

### To Implement

#### 1. Backend Integration
**File**: `backend/services/bigquery_assessment_service.py`

**Changes Needed**:
- Import SQLDependencyParser
- Update `collect_views()` to parse dependencies
- Update `collect_routines()` to parse dependencies
- Add helper methods to resolve dependencies

#### 2. Frontend Implementation
**File**: `frontend/src/pages/AssessmentReportPage.tsx`

**Changes Needed**:
- Replace ViewsSection with table format
- Replace RoutinesSection (procedures/functions) with table format
- Add expandable rows for dependency details
- Add CSS styles for new table format

#### 3. Database Migration (Optional)
If we need to add new fields to store parsed dependencies:
- Create migration to add dependency fields
- Run migration on database

## Implementation Priority
**HIGH** - This is the main remaining task from the user's requirements.

## Next Steps
1. Update backend service to parse dependencies
2. Update frontend to display as tables
3. Test with existing assessment data
4. Verify dependencies are captured correctly

## Notes
- The SQL dependency parser is already complete and functional
- No database schema changes needed (fields already exist)
- Focus on integrating parser into assessment collection
- Frontend changes are straightforward table conversions
