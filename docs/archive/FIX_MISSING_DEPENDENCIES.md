# Fix Missing Dependencies for Existing Assessments

## Issue
Existing assessments show "No dependencies found" because they were created before the dependency parsing feature was added.

## Root Cause
The backend dependency parsing logic was added recently. Existing assessments in the database don't have the `dependent_tables`, `dependent_views`, `dependent_functions`, and `calls_procedures` fields populated.

## Solution

You have two options:

### Option 1: Run a New Assessment (Recommended)
The easiest solution is to run a new assessment. The new assessment will automatically:
- Parse all SQL definitions
- Extract all dependencies
- Store them in the database
- Display them correctly in the UI

**Steps**:
1. Go to Assessments page
2. Click "Create Assessment"
3. Fill in the details
4. Run the assessment
5. View the report - dependencies will be shown

### Option 2: Parse Dependencies for Existing Assessments

If you want to keep your existing assessments and add dependencies to them, run this script:

```bash
# Navigate to backend directory
cd backend

# Run the dependency parsing script
python scripts/parse_existing_dependencies.py
```

**What the script does**:
1. Reads all existing views from the database
2. Parses their SQL definitions to extract dependencies
3. Categorizes dependencies into tables, views, functions
4. Updates the database with the parsed information
5. Reads all existing routines (stored procedures/functions)
6. Parses their SQL definitions
7. Extracts procedure calls (CALL statements)
8. Updates the database

**After running the script**:
1. Refresh the assessment report page in your browser
2. Click on any view or stored procedure name
3. You should now see all dependencies listed

## What Gets Parsed

### For Views
- **Tables**: All table references in FROM, JOIN clauses
- **Views**: All view references (nested views)
- **Functions**: All user-defined function calls
- **Excludes**: CTEs (WITH clauses), system functions

### For Stored Procedures/Functions
- **Tables**: All table references
- **Views**: All view references
- **Functions**: All function calls
- **Procedures**: All CALL statements to other procedures
- **Excludes**: CTEs, system functions

## Verification

After running the script or creating a new assessment:

1. **Open Assessment Report**
2. **Go to Views tab**
3. **Click on a view name** (should be blue and underlined)
4. **Check expanded section**:
   - Should show SQL Definition
   - Should show Dependencies section with:
     - Tables (grey badges)
     - Views (blue badges)
     - Functions (yellow badges)

5. **Go to Stored Procedures tab**
6. **Click on a procedure name**
7. **Check expanded section**:
   - Should show Routine Information
   - Should show Definition
   - Should show Dependencies section with:
     - Tables (grey badges)
     - Views (blue badges)
     - Functions (yellow badges)
     - Calls Procedures (red badges)

## Troubleshooting

### Script Fails with "DATABASE_URL not found"
Make sure you have a `.env` file in the backend directory with database connection details:
```
APP_DB_HOST=localhost
APP_DB_PORT=5432
APP_DB_NAME=db_migrator
APP_DB_USER=db_migrator_user
APP_DB_PASSWORD=your_password
```

Or set `DATABASE_URL` directly:
```
DATABASE_URL=postgresql://user:password@host:port/database
```

### Still Shows "No dependencies found"
1. Check browser console for errors
2. Verify the script ran successfully (should show "✓ Updated X views/routines")
3. Hard refresh the page (Ctrl+Shift+R or Cmd+Shift+R)
4. Check if the view/procedure actually has dependencies in its SQL definition

### Dependencies Not Showing Correctly
1. Check the SQL definition in the expanded section
2. Verify it contains table/view references
3. The parser looks for FROM, JOIN, INTO clauses
4. CTEs (WITH clauses) are excluded from dependencies

## Technical Details

### Database Fields Updated
- `assessment_views.dependencies` - Array of all references
- `assessment_views.dependent_tables` - Array of table names
- `assessment_views.dependent_views` - Array of view names
- `assessment_views.dependent_functions` - Array of function names
- `assessment_views.dependency_depth` - Nesting level (set to 1)

- `assessment_routines.dependencies` - Array of all references
- `assessment_routines.dependent_tables` - Array of table names
- `assessment_routines.dependent_views` - Array of view names
- `assessment_routines.dependent_functions` - Array of function names
- `assessment_routines.calls_procedures` - Array of called procedures
- `assessment_routines.dependency_depth` - Nesting level (set to 1)

### SQL Dependency Parser
The parser (`backend/utils/sql_dependency_parser.py`) uses regex patterns to extract:
- Table/view references from FROM, JOIN, INTO clauses
- Function calls (excluding system functions)
- Procedure calls from CALL statements
- Handles backticks, schema qualifiers, nested queries

## Future Assessments

All new assessments created after the backend changes will automatically have dependencies parsed and stored. No manual intervention needed.

---

**Created**: February 14, 2026  
**Status**: Ready to use
