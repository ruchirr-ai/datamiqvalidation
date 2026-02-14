# Production-Grade Configuration UI - Requirements

## Overview
Transform the Configuration step into a production-grade UI with collapsible sections, better visual hierarchy, and integrated logging/monitoring capabilities.

## UI Design Changes

### 1. Collapsible Stage Sections

Each stage should be collapsible with:
- **Header**: Always visible with stage number, title, description
- **Collapse button**: Chevron icon that rotates when expanded
- **Content**: Shows/hides on click
- **Save & Continue button**: At the bottom of each expanded section

### 2. Visual Design (Based on Image)

#### Stage Header
```
┌─────────────────────────────────────────────────────────┐
│ [1] BigQuery to GCS Export                          [▼] │
│     Configure BigQuery export settings to GCS           │
└─────────────────────────────────────────────────────────┘
```

- Light gray background (#F7F7F7)
- Blue circular badge with white number
- Title in bold
- Subtitle in gray
- Chevron button on right

#### Expanded Content
- White background
- Form fields with labels
- Helper text below inputs
- "Save & Continue" button (blue) at bottom right

#### Collapsed State
- Only header visible
- Chevron points down
- Click to expand

#### Expanded State
- Header + content visible
- Chevron points up
- Click to collapse

### 3. Stage Progression

**Default State**: Stage 1 expanded, others collapsed

**User Flow**:
1. User fills Stage 1 → clicks "Save & Continue"
2. Stage 1 collapses, Stage 2 expands automatically
3. User fills Stage 2 → clicks "Save & Continue"
4. Stage 2 collapses, Stage 3 expands automatically
5. User fills Stage 3 → clicks "Save & Continue"
6. All stages collapse, user proceeds to next wizard step

### 4. Pathway Badge

For Stage 2, show the selected pathway:
```
[2] GCS S3 Transfer                    [Path A] [▼]
    Select migration path for data transfer
```

- Pathway badge in blue with white text
- Shows "Path A", "Path B", "Path C", or "Path D"

## Production-Grade Features

### 1. Form Validation

**Real-time Validation**:
- Required fields marked with red asterisk (*)
- Validate on blur
- Show error messages below fields
- Disable "Save & Continue" if validation fails

**Validation Rules**:
- GCS Bucket: Must start with "gs://"
- S3 Bucket: Must start with "s3://"
- Email: Valid email format
- ARN: Valid AWS ARN format
- JSON: Valid JSON syntax

### 2. Field Helpers

**Smart Defaults**:
- Auto-populate fields where possible
- Suggest values based on previous inputs
- Show examples in placeholders

**Helper Text**:
- Clear, concise descriptions
- Link to documentation where needed
- Show character limits

### 3. Error Handling

**Error States**:
- Red border on invalid fields
- Error icon next to field
- Error message below field
- Summary of errors at top

**Success States**:
- Green checkmark when stage is complete
- Confirmation message
- Auto-collapse and expand next stage

### 4. Loading States

**During Save**:
- Show spinner on "Save & Continue" button
- Disable form fields
- Show "Saving..." text

**During Validation**:
- Show inline spinner
- Validate credentials
- Test connections

## Logging & Monitoring Integration

### 1. Stage-Level Logging

**For Each Stage**:
- Log when stage is started
- Log when stage is completed
- Log validation errors
- Log save actions

**Log Format**:
```json
{
  "timestamp": "2026-02-08T10:30:00Z",
  "migration_id": "mig-123",
  "stage": "bigquery_to_gcs",
  "action": "save",
  "status": "success",
  "user_id": "user-456",
  "data": {
    "gcs_bucket": "gs://my-bucket",
    "export_format": "PARQUET"
  }
}
```

### 2. Real-Time Monitoring

**During Migration Execution**:
- Show progress for each stage
- Display current status
- Show logs in real-time
- Alert on errors

**Monitoring Dashboard**:
```
┌─────────────────────────────────────────────────────────┐
│ Migration Progress                                       │
├─────────────────────────────────────────────────────────┤
│ [✓] Stage 1: BigQuery to GCS Export      [Completed]   │
│     Duration: 2m 34s | Rows: 1.2M | Size: 450MB        │
│                                                          │
│ [⟳] Stage 2: GCS to S3 Transfer          [In Progress] │
│     Progress: 67% | Transferred: 300MB / 450MB          │
│     ETA: 1m 15s                                         │
│                                                          │
│ [ ] Stage 3: S3 to Redshift Load          [Pending]    │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 3. Logging Configuration

**Per-Stage Logging**:
- Enable/disable logging for each stage
- Set log level (DEBUG, INFO, WARNING, ERROR)
- Configure log destination (CloudWatch, S3, Database)
- Set retention period

**Log Viewer**:
- Real-time log streaming
- Filter by level, stage, timestamp
- Search logs
- Download logs

### 4. Monitoring Metrics

**Track for Each Stage**:
- Start time
- End time
- Duration
- Rows processed
- Data size
- Success/failure rate
- Error count
- Retry count

**Alerts**:
- Email on failure
- Slack notification on completion
- Webhook on error
- SMS for critical issues

## Implementation Plan

### Phase 1: UI Redesign (Current)
1. ✅ Create collapsible stage components
2. ✅ Add "Save & Continue" buttons
3. ✅ Implement expand/collapse logic
4. ✅ Add pathway badge
5. ✅ Style matching the image

### Phase 2: Validation & Error Handling
1. Add form validation
2. Implement error states
3. Add success states
4. Add loading states

### Phase 3: Backend Integration
1. Create API endpoints for stage save
2. Implement validation on backend
3. Store stage configurations
4. Test connections/credentials

### Phase 4: Logging & Monitoring
1. Add logging infrastructure
2. Create monitoring dashboard
3. Implement real-time updates
4. Add alerting system

### Phase 5: Testing & Polish
1. Unit tests for validation
2. Integration tests for API
3. E2E tests for user flow
4. Performance optimization

## CSS Updates Needed

```css
/* Collapsible Stage */
.migration-stage-collapsible {
  background: white;
  border: 1px solid #E5E7EB;
  border-radius: 12px;
  margin-bottom: 16px;
  overflow: hidden;
}

.stage-header-collapsible {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  background: #F7F7F7;
  cursor: pointer;
  transition: background 0.2s ease;
}

.stage-header-collapsible:hover {
  background: #EEEEEE;
}

.stage-header-left {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
}

.collapse-button {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.2s ease;
}

.collapse-button svg.expanded {
  transform: rotate(180deg);
}

.stage-content-collapsible {
  padding: 24px;
  animation: slideDown 0.3s ease;
}

@keyframes slideDown {
  from {
    opacity: 0;
    max-height: 0;
  }
  to {
    opacity: 1;
    max-height: 2000px;
  }
}

.stage-footer {
  display: flex;
  justify-content: flex-end;
  padding-top: 20px;
  border-top: 1px solid #E5E7EB;
  margin-top: 20px;
}

.btn-save-continue {
  background: var(--color-primary);
  color: white;
  border: none;
  padding: 10px 24px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-save-continue:hover {
  background: var(--color-primary-dark);
  box-shadow: 0 2px 8px rgba(42, 107, 219, 0.3);
}

.btn-save-continue:disabled {
  background: #9AA6B2;
  cursor: not-allowed;
}

/* Pathway Badge */
.pathway-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  background: var(--color-primary);
  color: white;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  margin-left: 12px;
}

/* Stage Complete Indicator */
.stage-complete {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #4CAF50;
  font-size: 13px;
  font-weight: 500;
}

.stage-complete svg {
  width: 16px;
  height: 16px;
}
```

## Next Steps

1. Implement the collapsible UI
2. Add form validation
3. Create backend API endpoints
4. Integrate logging infrastructure
5. Build monitoring dashboard
6. Add real-time updates
7. Implement alerting system

This will create a production-grade configuration experience with proper logging and monitoring capabilities.
