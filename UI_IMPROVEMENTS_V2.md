# UI Improvements V2 - Load Type Configuration

## Status: ⚠️ LOCAL TESTING (Not Pushed to Git)

These changes are ready for local testing. Review them at `http://localhost:3000` before deploying.

---

## Changes Made

### 1. ✅ Truncate Option for Full Load Mode

**Before:** Truncate option only available in Incremental mode  
**After:** Truncate option available for BOTH Full and Incremental modes

- Single table: Shows truncate toggle below the configuration
- Multiple tables: Truncate column available for all tables regardless of load type

### 2. ✅ Bulk Actions for Multiple Tables

Added a new "BULK ACTIONS" toolbar above the table configuration with:

**Load Type Bulk Actions:**
- "Set All Incremental" button - Sets all tables to incremental mode
- "Set All Full" button - Sets all tables to full load mode

**Truncate Bulk Actions:**
- "Truncate All: ON" button - Enables truncate for all tables
- "Truncate All: OFF" button - Disables truncate for all tables

**Design:**
- Light grey background (#F8F9FA)
- Compact buttons with clear labels
- Positioned above the table for easy access

### 3. ✅ Radio Buttons Instead of Dropdown

**Before:** Dropdown select for Incremental/Full  
**After:** Radio buttons for better UX

**Benefits:**
- Faster selection (one click instead of two)
- Visual clarity - see current selection immediately
- More compact - takes less space
- Better mobile experience

**Design:**
- Two radio buttons: "Incr" and "Full"
- Inline layout with proper spacing
- Proper cursor pointer on hover

---

## UI Layout (Multiple Tables)

```
┌─────────────────────────────────────────────────────────────────┐
│ BULK ACTIONS:  [Set All Incremental] [Set All Full]            │
│                                    Truncate All: [ON] [OFF]     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ TABLE          │ LOAD TYPE    │ PRIMARY KEY │ TIMESTAMP │ TRUNC │
├─────────────────────────────────────────────────────────────────┤
│ orders_data    │ ○ Incr ● Full│ id          │ updated_at│  ●    │
│ customers      │ ● Incr ○ Full│ cust_id     │ modified  │  ○    │
│ products       │ ○ Incr ● Full│ —           │ —         │  ●    │
└─────────────────────────────────────────────────────────────────┘
```

---

## UI Layout (Single Table)

### Full Load Mode:
```
┌─────────────────────────────────────────────┐
│ Truncate Before Load                    [●] │
│ Delete all existing data in the target      │
│ table before loading new data               │
└─────────────────────────────────────────────┘
```

### Incremental Load Mode:
```
┌─────────────────────────────────────────────┐
│ Primary Key Column                          │
│ [id                                      ]  │
│ Column used to uniquely identify rows...    │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ Timestamp Column                            │
│ [updated_at                              ]  │
│ Column used to detect changed rows...       │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ Truncate Before Load                    [●] │
│ Delete all existing data in the target      │
│ table before loading new data               │
└─────────────────────────────────────────────┘
```

---

## Technical Implementation

### State Management

Each table config now includes:
```typescript
{
  "table_name": {
    "load_type": "incremental" | "full",
    "primary_key_column": "id",
    "timestamp_column": "updated_at",
    "truncate_before_load": true | false
  }
}
```

### Bulk Operations Logic

**Set All Load Type:**
- Updates all tables in `tableLoadConfigs`
- Clears PK and timestamp columns when switching to Full
- Preserves truncate settings

**Set All Truncate:**
- Updates `truncate_before_load` for all tables
- Works independently of load type
- Preserves other table settings

### Radio Button Implementation

```tsx
<label style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
  <input
    type="radio"
    name={`load-type-${tbl}`}
    checked={isIncremental}
    onChange={() => updateTableConfig(tbl, 'load_type', 'incremental')}
    style={{ cursor: 'pointer' }}
  />
  <span>Incr</span>
</label>
```

---

## Testing Checklist

### Single Table Mode:
- [ ] Full Load: Truncate toggle appears and works
- [ ] Incremental Load: PK, Timestamp, and Truncate all appear
- [ ] Truncate toggle turns blue when enabled
- [ ] Settings persist when switching between stages

### Multiple Tables Mode:
- [ ] Bulk "Set All Incremental" button works
- [ ] Bulk "Set All Full" button works
- [ ] Bulk "Truncate All: ON" button works
- [ ] Bulk "Truncate All: OFF" button works
- [ ] Radio buttons work for each table
- [ ] PK and Timestamp fields disable when Full is selected
- [ ] Truncate toggle works for each table independently
- [ ] Settings persist when switching between stages

### Edge Cases:
- [ ] Switching from Incremental to Full clears PK/Timestamp
- [ ] Switching from Full to Incremental preserves Truncate setting
- [ ] Bulk actions work with mixed table configurations
- [ ] All settings save correctly when clicking "Save & Continue"

---

## Files Modified

1. `frontend/src/components/migrations/steps/ConfigurationSetupStep.tsx`
   - Added bulk action buttons
   - Replaced dropdown with radio buttons
   - Added truncate option for Full load mode
   - Improved single table UI with truncate toggle

---

## Next Steps

1. **Test Locally:**
   - Open `http://localhost:3000`
   - Navigate to Migrations → Create Migration
   - Go to Stage 3 (Redshift Load Configuration)
   - Test all scenarios above

2. **If Tests Pass:**
   - Commit changes with descriptive message
   - Push to `shivansh-dev` branch
   - Deploy to EC2 using deploy script

3. **If Issues Found:**
   - Document issues
   - Make fixes
   - Re-test

---

## Design Decisions

### Why Radio Buttons?
- Faster interaction (one click vs two)
- Better visual feedback
- More intuitive for binary choice
- Saves horizontal space
- Better accessibility

### Why Bulk Actions?
- Saves time when configuring many tables
- Common use case: all tables same load type
- Easy to override individual tables after bulk action
- Professional enterprise software pattern

### Why Truncate for Full Load?
- User requested feature
- Makes sense: Full load often needs clean slate
- Gives flexibility: can do full load without truncate (append mode)
- Consistent with incremental mode having truncate option

---

**Created:** March 3, 2026  
**Status:** Ready for Testing  
**Branch:** Local (not committed)  
**Test URL:** http://localhost:3000
