#!/bin/bash

# Phase 2: Documentation Cleanup - Move remaining temporary docs to archive
# This script moves implementation plans, status docs, and temporary guides to docs/archive/

echo "Starting Phase 2 Documentation Cleanup..."

# Create archive directory if it doesn't exist
mkdir -p docs/archive

# Move BigQuery-related implementation/status docs
echo "Moving BigQuery implementation docs..."
mv BIGQUERY_ASSESSMENT_IMPLEMENTATION_PLAN.md docs/archive/ 2>/dev/null
mv BIGQUERY_EXPORT_ERROR_IMPROVEMENTS.md docs/archive/ 2>/dev/null
mv BIGQUERY_EXPORT_WORKING.md docs/archive/ 2>/dev/null
mv BIGQUERY_METADATA_REAL_DATA_READY.md docs/archive/ 2>/dev/null
mv BIGQUERY_REAL_DATA_INTEGRATION.md docs/archive/ 2>/dev/null
mv BIGQUERY_REDSHIFT_MIGRATION_ARCHITECTURE.md docs/archive/ 2>/dev/null
mv BIGQUERY_REDSHIFT_SAMPLE_FLOW.md docs/archive/ 2>/dev/null
mv BQ_REDSHIFT_MIGRATION_IMPLEMENTATION.md docs/archive/ 2>/dev/null

# Move GCS-related implementation/status docs
echo "Moving GCS implementation docs..."
mv GCS_EXPORT_PATH_ORGANIZED.md docs/archive/ 2>/dev/null
mv GCS_EXPORT_PATH_STRUCTURE.md docs/archive/ 2>/dev/null
mv GCS_S3_TRANSFER_ENHANCED_LOGGING.md docs/archive/ 2>/dev/null
mv GCS_TO_S3_DIRECT_TRANSFER_IMPLEMENTATION.md docs/archive/ 2>/dev/null

# Move Redshift-related implementation/status docs
echo "Moving Redshift implementation docs..."
mv REDSHIFT_LOAD_IAM_ROLE_REQUIRED.md docs/archive/ 2>/dev/null
mv DATA_LOADED_TO_REDSHIFT_SUCCESS.md docs/archive/ 2>/dev/null

# Move Production/Status docs
echo "Moving production status docs..."
mv PRODUCTION_GRADE_CONFIGURATION_UI.md docs/archive/ 2>/dev/null
mv PRODUCTION_LOGGING_ENHANCED.md docs/archive/ 2>/dev/null
mv PRODUCTION_S3_REDSHIFT_READY.md docs/archive/ 2>/dev/null
mv UI_REDSHIFT_LOAD_STATUS_UPDATED.md docs/archive/ 2>/dev/null
mv STAGING_CONFIGURATION_REMOVED.md docs/archive/ 2>/dev/null

# Move Fix/Error docs
echo "Moving fix/error docs..."
mv FIX_DEPENDENCY_SCRIPT_ERROR.md docs/archive/ 2>/dev/null
mv FIX_MISSING_DEPENDENCIES.md docs/archive/ 2>/dev/null
mv EXPORT_FORMAT_COMPRESSION_VERIFIED.md docs/archive/ 2>/dev/null

# Move Sample/Test data docs
echo "Moving sample/test data docs..."
mv COMPLETE_SAMPLE_DATA_GUIDE.md docs/archive/ 2>/dev/null
mv SAMPLE_DATA_ADDED.md docs/archive/ 2>/dev/null

# Move Design/UI implementation docs
echo "Moving design/UI implementation docs..."
mv DESIGN_SYSTEM_UPDATE.md docs/archive/ 2>/dev/null
mv DYNAMIC_FORM_IMPLEMENTATION.md docs/archive/ 2>/dev/null

# Move AWS/Field config docs
echo "Moving AWS field config docs..."
mv AWS_DMS_REDSHIFT_FIELDS.md docs/archive/ 2>/dev/null

# Move dependency/SQL analysis docs
echo "Moving dependency analysis docs..."
mv SQL_DEPENDENCY_ANALYSIS_IMPLEMENTATION_PLAN.md docs/archive/ 2>/dev/null
mv VIEWS_PROCEDURES_TABLE_DEPENDENCIES_PLAN.md docs/archive/ 2>/dev/null

# Move workspace/filter docs
echo "Moving workspace filter docs..."
mv WORKSPACE_ID_FILTER_REMOVED.md docs/archive/ 2>/dev/null

# Move issues/next steps docs
echo "Moving issues/next steps docs..."
mv ISSUES_RESOLVED.md docs/archive/ 2>/dev/null
mv NEXT_STEPS.md docs/archive/ 2>/dev/null

# Move SaaS implementation guide
echo "Moving SaaS implementation guide..."
mv SAAS_IMPLEMENTATION_GUIDE.md docs/archive/ 2>/dev/null

echo ""
echo "Phase 2 Cleanup Complete!"
echo ""
echo "Remaining root-level docs (should be kept):"
ls -1 *.md 2>/dev/null | grep -v "^README" | grep -v "^ARCHITECTURE" | grep -v "^DEPLOYMENT_GUIDE" | grep -v "^HOW_TO_RUN" | grep -v "^TESTING_GUIDE" | grep -v "^SETUP_CHECKLIST" | grep -v "^VERIFY_SETUP" | grep -v "^RUN_DIAGNOSTIC" | grep -v "^CREATE_NEW_MIGRATION_GUIDE" | grep -v "^UV_"
