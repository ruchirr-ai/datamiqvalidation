# Migration Type Selection Implementation

## Summary

Successfully implemented migration type selection dropdown that filters source and target connections based on the selected migration type. The wizard now adapts its workflow based on whether the user selects BigQuery to Redshift or MongoDB to DocumentDB migration.

## Implementation Details

### 1. Migration Type Dropdown

Added a new dropdown in Step 1 (Connection & Staging Configuration) that allows users to choose between:
- **BigQuery to Redshift**
- **MongoDB to DocumentDB**

### 2. Connection Filtering

**Source Connections:**
- When "BigQuery to Redshift" is selected: Only BigQuery source connections are shown
- When "MongoDB to DocumentDB" is selected: Only MongoDB source connections are shown

**Target Connections:**
- When "BigQuery to Redshift" is selected: Only Redshift target connections are shown
- When "MongoDB to DocumentDB" is selected: Only DocumentDB target connections are shown

### 3. Sample Data Updates

Added new sample connections to support both migration types:
- Production BigQuery (source)
- Dev BigQuery (source)
- Production Redshift (target)
- Staging Redshift (target)
- Analytics MongoDB (source)
- Dev MongoDB (source)
- Production DocumentDB (target)
- Staging DocumentDB (target)

### 4. Workflow Adaptation

The wizard now conditionally renders steps based on migration type:

**BigQuery to Redshift (Fully Implemented):**
- Step 1: Connection & Staging Configuration
- Step 2: Metadata Discovery (BigQuery tables)
- Step 3: Strategy Selection (4 pathways: A, B, C, D)
- Step 4: Configuration & Setup (3-stage migration)
- Step 5: Scheduling & Monitoring

**MongoDB to DocumentDB (Placeholder):**
- Step 1: Connection & Staging Configuration
- Step 2: Collection Selection (placeholder)
- Step 3: Migration Strategy (placeholder)
- Step 4: Migration Configuration (placeholder)
- Step 5: Scheduling & Monitoring

### 5. User Experience Improvements

**Migration Type Selection:**
- Dropdown appears immediately after migration name
- Clear labels: "BigQuery to Redshift" and "MongoDB to DocumentDB"
- Help text: "Choose the type of database migration"

**Connection Dropdowns:**
- Only appear after migration type is selected
- Placeholder text dynamically updates based on migration type
  - "Select BIGQUERY connection" for BigQuery sources
  - "Select MONGODB connection" for MongoDB sources
  - "Select REDSHIFT connection" for Redshift targets
  - "Select DOCUMENTDB connection" for DocumentDB targets

**Error Handling:**
- If no connections of the required type exist, show helpful error message
- Example: "No BIGQUERY source connections available. Please create one first."

**Connection Reset:**
- When migration type changes, source and target connections are automatically reset
- Prevents invalid connection combinations

### 6. Technical Implementation

#### Form Data Interface Updates

```typescript
export interface MigrationFormData {
  migrationName: string;
  migrationType: 'bigquery-redshift' | 'mongodb-documentdb' | null;
  sourceConnectionId: number | null;
  targetConnectionId: number | null;
  // ... other fields
}
```

#### Migration Type Configuration

```typescript
const getMigrationTypeConfig = () => {
  if (formData.migrationType === 'bigquery-redshift') {
    return {
      sourceDb: 'bigquery',
      targetDb: 'redshift',
      label: 'BigQuery to Redshift'
    };
  } else if (formData.migrationType === 'mongodb-documentdb') {
    return {
      sourceDb: 'mongodb',
      targetDb: 'documentdb',
      label: 'MongoDB to DocumentDB'
    };
  }
  return null;
};
```

#### Connection Filtering Logic

```typescript
const sourceConnections = migrationConfig
  ? connections.filter(c => 
      c.type === 'source' && 
      c.database.toLowerCase() === migrationConfig.sourceDb
    )
  : connections.filter(c => c.type === 'source');

const targetConnections = migrationConfig
  ? connections.filter(c => 
      c.type === 'target' && 
      c.database.toLowerCase() === migrationConfig.targetDb
    )
  : connections.filter(c => c.type === 'target');
```

#### Conditional Step Rendering

```typescript
const renderStep = () => {
  const isBigQueryRedshift = formData.migrationType === 'bigquery-redshift';
  const isMongoDocumentDB = formData.migrationType === 'mongodb-documentdb';

  switch (currentStep) {
    case 1:
      return <ConnectionStagingStep />;
    case 2:
      if (isMongoDocumentDB) {
        return <MongoCollectionSelectionPlaceholder />;
      }
      return <MetadataDiscoveryStep />;
    // ... other cases
  }
};
```

### 7. Files Modified

1. **frontend/src/components/migrations/CreateMigrationWizard.tsx**
   - Added `migrationType` field to `MigrationFormData` interface
   - Updated `INITIAL_FORM_DATA` with default migration type
   - Implemented conditional step rendering based on migration type
   - Added placeholder steps for MongoDB to DocumentDB workflow

2. **frontend/src/components/migrations/steps/ConnectionStagingStep.tsx**
   - Added migration type dropdown
   - Implemented `getMigrationTypeConfig()` function
   - Added connection filtering logic based on migration type
   - Updated sample connections to include MongoDB and DocumentDB
   - Added error messages for missing connections
   - Implemented connection reset when migration type changes

3. **frontend/src/components/migrations/steps/StepStyles.css**
   - Added `.form-error` style for error messages

## User Flow

### Selecting BigQuery to Redshift

1. User enters migration name
2. User selects "BigQuery to Redshift" from migration type dropdown
3. Source connection dropdown shows only BigQuery connections
4. Target connection dropdown shows only Redshift connections
5. User proceeds through all 5 steps with full BigQuery → Redshift workflow

### Selecting MongoDB to DocumentDB

1. User enters migration name
2. User selects "MongoDB to DocumentDB" from migration type dropdown
3. Source connection dropdown shows only MongoDB connections
4. Target connection dropdown shows only DocumentDB connections
5. User proceeds through steps 1 and 5 (steps 2-4 show placeholder messages)

## Validation

**Migration Type Required:**
- User must select a migration type before seeing connection dropdowns
- Prevents confusion about which connections to select

**Connection Type Validation:**
- Only connections matching the selected migration type are shown
- Impossible to select invalid connection combinations

**Empty State Handling:**
- If no connections of required type exist, show clear error message
- Guides user to create appropriate connections first

## Future Enhancements

### MongoDB to DocumentDB Workflow (Next Phase)

**Step 2: Collection Selection**
- List all collections from source MongoDB
- Allow multi-select with search/filter
- Show collection size and document count
- Preview collection schema

**Step 3: Migration Strategy**
- Online migration (minimal downtime)
- Offline migration (full dump/restore)
- Continuous replication
- One-time snapshot

**Step 4: Migration Configuration**
- Index migration settings
- Data transformation rules
- Conflict resolution strategy
- Performance tuning options

### Additional Migration Types

Future migration types to support:
- PostgreSQL to Aurora PostgreSQL
- MySQL to Aurora MySQL
- Oracle to PostgreSQL
- SQL Server to RDS SQL Server
- Cassandra to DynamoDB
- Redis to ElastiCache

### Enhanced Filtering

- Filter by connection status (connected, disconnected)
- Filter by workspace
- Search connections by name
- Show connection details on hover

## Testing Checklist

- [x] Migration type dropdown appears after migration name
- [x] Migration type dropdown has correct options
- [x] Connection dropdowns only appear after migration type is selected
- [x] Source connections filtered correctly for BigQuery to Redshift
- [x] Target connections filtered correctly for BigQuery to Redshift
- [x] Source connections filtered correctly for MongoDB to DocumentDB
- [x] Target connections filtered correctly for MongoDB to DocumentDB
- [x] Connections reset when migration type changes
- [x] Error messages show when no connections available
- [x] Placeholder steps show for MongoDB to DocumentDB
- [x] Full workflow works for BigQuery to Redshift
- [x] Sample data includes all required connection types

## Conclusion

The migration type selection feature is now complete and functional. Users can choose between BigQuery to Redshift and MongoDB to DocumentDB migrations, with the wizard automatically filtering connections and adapting the workflow accordingly. The BigQuery to Redshift workflow is fully implemented with all 5 steps, while MongoDB to DocumentDB shows placeholder steps that will be implemented in the next phase.
