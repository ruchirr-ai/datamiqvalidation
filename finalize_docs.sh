#!/bin/bash

# Final Documentation Cleanup
# This script consolidates remaining setup guides and replaces the main README

echo "Finalizing documentation cleanup..."

# Create archive directory if it doesn't exist
mkdir -p docs/archive/setup-guides

# Move redundant setup guides to archive
echo "Archiving redundant setup guides..."
mv README_SETUP.md docs/archive/setup-guides/ 2>/dev/null
mv VERIFY_SETUP.md docs/archive/setup-guides/ 2>/dev/null
mv RUN_DIAGNOSTIC.md docs/archive/setup-guides/ 2>/dev/null

# Keep these essential guides in root:
# - README.md (will be replaced)
# - HOW_TO_RUN.md (detailed setup)
# - SETUP_CHECKLIST.md (verification checklist)
# - ARCHITECTURE.md (architecture overview)
# - DEPLOYMENT_GUIDE.md (deployment instructions)
# - TESTING_GUIDE.md (testing standards)
# - CREATE_NEW_MIGRATION_GUIDE.md (user guide)
# - UV_QUICK_REFERENCE.md (uv tool reference)
# - UV_SETUP_GUIDE.md (uv setup guide)

# Backup old README
echo "Backing up old README..."
cp README.md docs/archive/README_OLD.md 2>/dev/null

# Replace with new comprehensive README
echo "Installing new comprehensive README..."
mv README_NEW.md README.md

echo ""
echo "✅ Documentation cleanup complete!"
echo ""
echo "📁 Root-level documentation structure:"
echo ""
ls -1 *.md
echo ""
echo "📚 Documentation organization:"
echo "  - README.md                      → Main project overview and quick start"
echo "  - HOW_TO_RUN.md                  → Detailed setup and troubleshooting"
echo "  - SETUP_CHECKLIST.md             → Step-by-step verification checklist"
echo "  - ARCHITECTURE.md                → System architecture and design"
echo "  - DEPLOYMENT_GUIDE.md            → Production deployment instructions"
echo "  - TESTING_GUIDE.md               → Testing standards and practices"
echo "  - CREATE_NEW_MIGRATION_GUIDE.md  → User guide for creating migrations"
echo "  - UV_QUICK_REFERENCE.md          → UV package manager reference"
echo "  - UV_SETUP_GUIDE.md              → UV setup instructions"
echo ""
echo "📂 Organized documentation:"
echo "  - docs/CONNECTIONS.md            → Connections module overview"
echo "  - docs/MIGRATIONS.md             → Migrations module overview"
echo "  - docs/ASSESSMENTS.md            → Assessments module overview"
echo "  - docs/api/                      → API documentation"
echo "  - docs/backend/                  → Backend service documentation"
echo "  - docs/frontend/                 → Frontend component documentation"
echo "  - docs/database/                 → Database schema documentation"
echo "  - docs/quickstart/               → Quick start guides"
echo "  - docs/testing/                  → Testing guides"
echo "  - docs/fixes/                    → Fix documentation"
echo "  - docs/archive/                  → Archived implementation docs"
echo ""
echo "🎯 Next steps:"
echo "  1. Review the new README.md"
echo "  2. Update ARCHITECTURE.md if needed"
echo "  3. Consolidate any remaining duplicate content"
echo "  4. Remove cleanup scripts when satisfied"
