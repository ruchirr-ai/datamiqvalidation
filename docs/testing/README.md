# Testing Documentation

This folder contains all test-related documentation for the DataMIQ platform.

## Directory Structure

```
docs/testing/
├── README.md (this file)
├── Testing Guides/
├── Quick Tests/
├── Test Execution/
├── Test Readiness/
├── Feature Testing/
├── Database Tests/
└── UI Testing/
```

## Testing Guides & Instructions

Comprehensive testing guides for different components:

- **TESTING_GUIDE.md** - General testing guide for the platform
- **MIGRATION_EXECUTION_TEST_GUIDE.md** - How to test migration execution
- **TEST_MIGRATION_FROM_DB_GUIDE.md** - Database migration testing procedures
- **TEST_GCS_S3_TRANSFER_GUIDE.md** - GCS to S3 transfer testing guide
- **PATH_C_END_TO_END_TEST_GUIDE.md** - Path C end-to-end testing
- **PATHWAY_A_TESTING_GUIDE.md** - Pathway A comprehensive testing
- **MIGRATIONS_LIST_TESTING_GUIDE.md** - Migrations list UI testing

## Quick Test Guides

Fast testing procedures for rapid validation:

- **QUICK_TEST.md** - Quick test instructions
- **QUICK_TEST_NOW.md** - Immediate quick test procedures
- **QUICK_TEST_BIGQUERY_EXPORT.md** - BigQuery export quick test
- **QUICK_TEST_PATH_C.md** - Path C quick test
- **QUICK_TEST_PATH_C_GCS_S3.md** - Path C GCS to S3 quick test

## Test Execution Instructions

Step-by-step instructions to run specific tests:

- **TEST_MIGRATION_NOW.md** - Run migration test immediately
- **RUN_PATHWAY_A_TEST.md** - Execute Pathway A test
- **RUN_PATH_C_TEST.md** - Execute Path C test
- **TEST_PATH_C_NOW.md** - Execute Path C test immediately

## Test Readiness Status

Documents indicating when features are ready for testing:

- **READY_FOR_TESTING.md** - General testing readiness status
- **MIGRATION_READY_TO_TEST.md** - Migration testing ready
- **DATABASE_MIGRATION_TEST_READY.md** - Database migration ready
- **PATHWAY_A_TEST_READY.md** - Pathway A ready for testing
- **PATH_C_TEST_SCRIPT_READY.md** - Path C test script ready
- **PATH_C_TEST_SCRIPT_VALIDATED.md** - Path C test script validated
- **FINAL_STATUS_READY_TO_TEST.md** - Final status ready

## Feature-Specific Testing

Testing documentation for specific features:

### Connection Testing
- **CONNECTION_TESTING_IMPLEMENTATION.md** - Connection testing implementation
- **CONNECTION_TEST_ERROR_DISPLAY_COMPLETE.md** - Connection test error display
- **CONNECTION_UPDATE_TEST_COMPLETE.md** - Connection update testing

### Frontend Testing
- **TEST_FRONTEND_DATA.md** - Frontend data testing procedures

### BigQuery Testing
- **BIGQUERY_GCS_EXPORT_TESTING.md** - BigQuery GCS export testing

### UI Testing
- **UI_AND_TEST_IMPROVEMENTS_COMPLETE.md** - UI and test improvements

## Database-Specific Tests

Testing procedures for database operations:

- **TEST_IAM_ROLE_FROM_DATABASE.md** - IAM role database testing
- **TEST_PATH_C_FROM_DATABASE.md** - Path C database testing
- **TEST_S3_TO_REDSHIFT_LOAD.md** - S3 to Redshift load testing
- **TEST_S3_REDSHIFT_FIX.md** - S3 Redshift fix testing
- **TEST_PATH_C_TRANSFER_FIX.md** - Path C transfer fix testing

## Testing Best Practices

### Before Running Tests

1. **Environment Setup**
   - Ensure backend server is running (`./START_BACKEND_HERE.sh`)
   - Ensure frontend server is running (`npm run dev`)
   - Verify database connection
   - Check AWS credentials are configured

2. **Test Data Preparation**
   - Create test connections (BigQuery source, Redshift target)
   - Prepare sample datasets in BigQuery
   - Verify S3 buckets are accessible
   - Ensure Redshift cluster is running

3. **Configuration Validation**
   - Check `.env` file has all required variables
   - Verify KMS keys are accessible
   - Confirm IAM roles have proper permissions

### Running Tests

1. **Unit Tests**
   ```bash
   cd backend
   pytest tests/unit -v
   ```

2. **Integration Tests**
   ```bash
   cd backend
   pytest tests/integration -v
   ```

3. **End-to-End Tests**
   ```bash
   cd backend
   python test_pathway_a_end_to_end.py
   python test_path_c_from_db.py
   ```

4. **Frontend Tests**
   ```bash
   cd frontend
   npm test
   ```

### After Testing

1. **Cleanup**
   - Remove test data from databases
   - Delete temporary S3 files
   - Clean up test connections
   - Reset test migrations

2. **Documentation**
   - Update test results in relevant documents
   - Document any issues found
   - Update test procedures if needed

## Test Categories

### 1. Connection Tests
Test database connections, connection validation, and connection management.

### 2. Migration Tests
Test migration creation, execution, monitoring, and completion.

### 3. Assessment Tests
Test BigQuery metadata collection and assessment reporting.

### 4. Transfer Tests
Test data transfer between GCS and S3, and S3 to Redshift.

### 5. UI Tests
Test frontend components, user interactions, and data display.

### 6. Integration Tests
Test end-to-end workflows across multiple components.

## Test Execution Order

For comprehensive testing, follow this order:

1. **Connection Tests** - Verify connections work
2. **Assessment Tests** - Verify metadata collection
3. **Migration Creation Tests** - Verify migration setup
4. **Transfer Tests** - Verify data movement
5. **Load Tests** - Verify data loading to target
6. **Validation Tests** - Verify data integrity
7. **UI Tests** - Verify user interface

## Common Test Scenarios

### Scenario 1: BigQuery to Redshift Migration (Path C)
1. Create BigQuery source connection
2. Create Redshift target connection
3. Run assessment on BigQuery
4. Create migration project
5. Execute migration
6. Monitor progress
7. Validate results

### Scenario 2: Connection Testing
1. Create new connection
2. Test connection
3. Update connection parameters
4. Re-test connection
5. Delete connection

### Scenario 3: Assessment Testing
1. Create BigQuery connection
2. Start assessment
3. Monitor assessment progress
4. View assessment results
5. Export assessment report

## Troubleshooting

### Common Issues

1. **Connection Failures**
   - Check credentials
   - Verify network connectivity
   - Check firewall rules
   - Verify IAM permissions

2. **Test Failures**
   - Check test data exists
   - Verify environment variables
   - Check server logs
   - Verify database state

3. **Performance Issues**
   - Check database connection pool
   - Verify Redis is running
   - Check network latency
   - Monitor resource usage

## Test Data

### Sample Connections
- BigQuery: `test-project-id`
- Redshift: `test-cluster.region.redshift.amazonaws.com`
- S3 Bucket: `test-migration-bucket`
- GCS Bucket: `test-export-bucket`

### Sample Datasets
- `test_dataset_1` - Small dataset (< 1GB)
- `test_dataset_2` - Medium dataset (1-10GB)
- `test_dataset_3` - Large dataset (> 10GB)

## Continuous Integration

Tests are automatically run on:
- Pull requests
- Merges to main branch
- Nightly builds

## Test Coverage

Current test coverage targets:
- Backend: 80% minimum
- Frontend: 70% minimum
- Critical paths: 100%

## Contributing

When adding new features:
1. Write tests first (TDD)
2. Include sample payloads
3. Test success and failure cases
4. Test edge cases
5. Update this documentation

## Related Documentation

- [Testing Standards](../../.kiro/steering/testing-standards.md)
- [Backend Standards](../../.kiro/steering/backend-standards.md)
- [Frontend Standards](../../.kiro/steering/frontend-standards.md)
- [Security Standards](../../.kiro/steering/security-standards.md)

## Contact

For questions about testing:
- Review the testing standards document
- Check existing test files for examples
- Consult the team lead

---

Last Updated: February 13, 2026
