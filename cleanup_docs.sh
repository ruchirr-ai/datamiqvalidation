#!/bin/bash

# Documentation Cleanup Script
# Removes test/debug/fix documents and consolidates related docs

echo "Starting documentation cleanup..."

# Create archive directory for old docs
mkdir -p docs/archive

# Move test/debug/diagnostic scripts
echo "Moving test and debug files..."
find backend -name "test_*.py" -not -path "*/tests/*" -exec mv {} docs/archive/ \; 2>/dev/null
find backend -name "debug_*.py" -exec mv {} docs/archive/ \; 2>/dev/null
find backend -name "diagnose_*.py" -exec mv {} docs/archive/ \; 2>/dev/null
find backend -name "check_*.py" -exec mv {} docs/archive/ \; 2>/dev/null
find backend -name "verify_*.py" -exec mv {} docs/archive/ \; 2>/dev/null
find backend -name "fix_*.py" -exec mv {} docs/archive/ \; 2>/dev/null

# Move temporary/status documents
echo "Moving temporary status documents..."
mv *_COMPLETE.md docs/archive/ 2>/dev/null
mv *_STATUS.md docs/archive/ 2>/dev/null
mv *_FIX*.md docs/archive/ 2>/dev/null
mv *_DEBUG*.md docs/archive/ 2>/dev/null
mv *_FIXES*.md docs/archive/ 2>/dev/null
mv *_ISSUE*.md docs/archive/ 2>/dev/null
mv *_PROGRESS.md docs/archive/ 2>/dev/null
mv *_SUMMARY.md docs/archive/ 2>/dev/null
mv CONTEXT_TRANSFER*.md docs/archive/ 2>/dev/null
mv IMPLEMENTATION_*.md docs/archive/ 2>/dev/null
mv TROUBLESHOOTING*.md docs/archive/ 2>/dev/null
mv QUICK_FIX*.md docs/archive/ 2>/dev/null
mv DROPDOWN_DEBUG*.md docs/archive/ 2>/dev/null
mv SERVERS_*.md docs/archive/ 2>/dev/null
mv BACKEND_*.md docs/archive/ 2>/dev/null
mv FINAL_*.md docs/archive/ 2>/dev/null
mv HOW_TO_FIX*.md docs/archive/ 2>/dev/null
mv QUERY_*.md docs/archive/ 2>/dev/null
mv USER_INSIGHTS*.md docs/archive/ 2>/dev/null
mv HOURLY_*.md docs/archive/ 2>/dev/null

echo "Cleanup complete!"
echo "Archived files moved to docs/archive/"
echo ""
echo "Remaining documentation:"
ls -1 *.md 2>/dev/null | wc -l
