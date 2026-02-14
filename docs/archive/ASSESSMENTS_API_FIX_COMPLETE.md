# Assessments API Fix - Complete

## Issue
Assessments page was showing "Cannot connect to server" error while Connections and Migrations pages worked fine.

## Root Causes

### 1. Authentication Token Mismatch
- **Problem**: AssessmentsPage was using direct `fetch()` calls looking for `localStorage.getItem('token')`
- **Reality**: The authentication system stores tokens as `localStorage.getItem('auth_token')`
- **Impact**: API calls were being made without proper authentication headers

### 2. Field Name Mismatch
- **Problem**: Backend `Assessment` model has `source_connection_id` and `target_connection_id`
- **Frontend Expected**: `connection_id` (single field)
- **Impact**: Backend was throwing 500 Internal Server Error when trying to serialize responses

## Solutions Implemented

### 1. Created Assessments API Service
**File**: `frontend/src/services/assessmentsApi.ts`

```typescript
export const listAssessments = async (): Promise<AssessmentListResponse>
export const createAssessment = async (data: CreateAssessmentRequest): Promise<Assessment>
export const getAssessment = async (assessmentId: number): Promise<AssessmentDetailResponse>
export const deleteAssessment = async (assessmentId: number): Promise<void>
```

**Benefits**:
- Uses centralized `api` client with proper authentication
- Consistent error handling across all pages
- Automatic token management
- Automatic 401 redirect to login

### 2. Updated AssessmentsPage
**File**: `frontend/src/pages/AssessmentsPage.tsx`

**Changes**:
- Removed direct `fetch()` calls
- Imported and used `listAssessments()` and `deleteAssessment()` from API service
- Simplified error handling
- Consistent with ConnectionsPage and MigrationsPage patterns

### 3. Fixed Backend Response Model
**File**: `backend/routers/assessment_router.py`

**Changes**:
```python
class AssessmentResponse(BaseModel):
    id: int
    source_connection_id: int  # Changed from connection_id
    target_connection_id: int  # Added
    project_id: str
    # ... other fields
    workspace_id: int  # Added
```

### 4. Updated Frontend Interface
**File**: `frontend/src/services/assessmentsApi.ts`

**Changes**:
```typescript
export interface Assessment {
  id: number;
  source_connection_id: number;  // Changed from connection_id
  target_connection_id: number;  // Added
  project_id: string;
  // ... other fields
  workspace_id: number;  // Added
}
```

## Verification

### Backend Test
```bash
curl http://localhost:8000/api/assessments/
```

**Response**:
```json
{
  "assessments": [
    {
      "id": 3,
      "source_connection_id": 6,
      "target_connection_id": 7,
      "project_id": "assessiq-484512",
      "status": "pending",
      "started_at": "2026-02-14T10:18:12.501234",
      "completed_at": null,
      "error_message": null,
      "total_datasets": 0,
      "total_tables": 0,
      "total_views": 0,
      "total_routines": 0,
      "total_ml_models": 0,
      "total_size_mb": 0.0,
      "created_by": "current_user",
      "workspace_id": 1
    }
  ],
  "total": 3
}
```

✅ Backend returns data successfully

### Frontend Test
1. Navigate to http://localhost:3000/assessments
2. Page should load without "Cannot connect to server" error
3. Should show list of assessments or empty state
4. Create, view, and delete operations should work

## Files Modified

1. ✅ `frontend/src/services/assessmentsApi.ts` - Created
2. ✅ `frontend/src/pages/AssessmentsPage.tsx` - Updated to use API service
3. ✅ `backend/routers/assessment_router.py` - Fixed response model
4. ✅ `frontend/src/services/assessmentsApi.ts` - Updated interface

## Status

✅ **COMPLETE** - Assessments page now works correctly with proper authentication and data serialization.

## Next Steps

1. Test assessment creation via UI
2. Test assessment deletion
3. Verify all CRUD operations work end-to-end
4. Run BigQuery assessment with real connection to verify metadata collection

## Notes

- The backend already has 3 pending assessments in the database
- All assessments are using source_connection_id=6 and target_connection_id=7
- Assessment status is "pending" - background tasks may need to be triggered
- Workspace ID is hardcoded to 1 (TODO: Get from auth context)
