# Quick Start Documentation

This directory contains all quick start guides and run documentation for getting DataMIQ up and running quickly. Whether you're setting up for the first time, running migrations, or debugging issues, you'll find the right guide here.

## 🚀 Start Here

**New to DataMIQ?** Start with these guides in order:

1. **[START_HERE.md](./START_HERE.md)** - Main entry point with 3-command setup
2. **[QUICK_START.md](./QUICK_START.md)** - Comprehensive 5-minute setup guide
3. **[RUN_NOW.md](./RUN_NOW.md)** - Simple "ready to run" guide

## Quick Navigation

- [Initial Setup Guides](#initial-setup-guides)
- [Migration Guides](#migration-guides)
- [Debugging Guides](#debugging-guides)
- [Common Tasks](#common-tasks)

---

## Initial Setup Guides

### For First-Time Setup

**[START_HERE.md](./START_HERE.md)** - Best starting point
- 3-command quick setup
- UV package manager introduction
- Links to all documentation
- Help resources

**[QUICK_START.md](./QUICK_START.md)** - Most comprehensive
- UV package manager setup and commands
- Backend and frontend setup
- Configuration details
- API testing examples
- Troubleshooting guide
- Complete UV reference

**[QUICK_START_GUIDE.md](./QUICK_START_GUIDE.md)** - After dependency fixes
- Post-fix setup instructions
- Virtual environment setup
- Frontend server location fix
- Verification steps

**[RUN_NOW.md](./RUN_NOW.md)** - Simplest approach
- 3 commands to get running
- Pre-configured settings
- Quick health checks
- Documentation index

### When to Use Each Guide

| Scenario | Recommended Guide |
|----------|------------------|
| Brand new setup | START_HERE.md |
| Want detailed instructions | QUICK_START.md |
| After fixing dependencies | QUICK_START_GUIDE.md |
| Just want to run it | RUN_NOW.md |
| Using UV package manager | QUICK_START.md |

---

## Migration Guides

### Running Migrations

**[QUICK_START_NEW_MIGRATION.md](./QUICK_START_NEW_MIGRATION.md)** - Test new migrations
- Create migration via UI
- Monitor progress
- Expected timeline
- Success indicators
- Troubleshooting migration issues
- Connection requirements checklist

**[QUICK_START_GCS_S3_TRANSFER.md](./QUICK_START_GCS_S3_TRANSFER.md)** - GCS to S3 transfer (Pathway A)
- Prerequisites and permissions
- Step-by-step migration creation
- Stage-by-stage monitoring
- Verification procedures
- Troubleshooting transfer issues
- Expected timeline

**[RUN_MIGRATION_NOW.md](./RUN_MIGRATION_NOW.md)** - Run specific migration
- Run reset migration
- Stage-by-stage execution
- Monitor progress
- Verify success in Redshift
- Common issues

**[QUICK_START_AFTER_RESTART.md](./QUICK_START_AFTER_RESTART.md)** - After server restart
- Background migration execution
- View logs feature
- Expected behavior changes
- Monitoring progress
- Success indicators

### Migration Workflow Comparison

| Guide | Use Case | Pathway | Complexity |
|-------|----------|---------|------------|
| QUICK_START_NEW_MIGRATION.md | General migration testing | All | Medium |
| QUICK_START_GCS_S3_TRANSFER.md | GCS → S3 transfer | Path A | High |
| RUN_MIGRATION_NOW.md | Specific migration | Path C | Low |
| QUICK_START_AFTER_RESTART.md | Post-restart testing | All | Low |

---

## Debugging Guides

### Troubleshooting & Diagnostics

**[RUN_DEBUG_SCRIPTS.md](./RUN_DEBUG_SCRIPTS.md)** - Debug Redshift load issues
- Find migration ID
- Run diagnostic scripts
- Run load test scripts
- Expected output examples
- Common issues and solutions
- Redshift verification queries

### When to Use Debug Guides

| Symptom | Guide | What It Does |
|---------|-------|--------------|
| Data not in Redshift | RUN_DEBUG_SCRIPTS.md | Diagnoses load stage issues |
| Migration stuck | RUN_DEBUG_SCRIPTS.md | Shows stage completion status |
| Silent failures | RUN_DEBUG_SCRIPTS.md | Reveals hidden errors |
| Configuration issues | RUN_DEBUG_SCRIPTS.md | Validates all settings |

---

## Common Tasks

### Quick Commands Reference

#### Start Backend
```bash
cd backend
source .venv/bin/activate
python main.py
```

#### Start Frontend
```bash
cd frontend
npm install
npm start
```

#### Check Health
```bash
curl http://localhost:8000/health
```

#### Login (API)
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"AdminPass123!"}'
```

#### Run Migrations
```bash
cd backend
alembic upgrade head
```

#### Create Admin User
```bash
cd backend
python scripts/setup_admin.py
```

### UV Package Manager Commands

#### Setup
```bash
uv venv                          # Create virtual environment
source .venv/bin/activate        # Activate environment
uv pip install -r requirements.txt  # Install dependencies
```

#### Package Management
```bash
uv add <package>                 # Add package
uv remove <package>              # Remove package
uv pip list                      # List packages
```

See **[QUICK_START.md](./QUICK_START.md)** for complete UV reference.

---

## Guide Comparison Matrix

### Setup Guides

| Feature | START_HERE | QUICK_START | QUICK_START_GUIDE | RUN_NOW |
|---------|-----------|-------------|-------------------|---------|
| Setup Time | 5 min | 10 min | 5 min | 3 min |
| Detail Level | Low | High | Medium | Low |
| UV Guide | Yes | Complete | No | No |
| Troubleshooting | No | Yes | Yes | No |
| Best For | Beginners | Power users | Post-fix | Quick run |

### Migration Guides

| Feature | NEW_MIGRATION | GCS_S3_TRANSFER | RUN_MIGRATION | AFTER_RESTART |
|---------|--------------|-----------------|---------------|---------------|
| Pathway | All | Path A | Path C | All |
| Detail Level | High | Very High | Medium | Low |
| Prerequisites | Medium | High | Low | Low |
| Troubleshooting | Yes | Yes | Yes | Yes |
| Best For | Testing | Production | Specific run | Post-update |

---

## Prerequisites

### Required Software

- **Python 3.9+**
- **PostgreSQL 12+**
- **Node.js 16+** (for frontend)
- **UV** (recommended) or pip

### Optional Software

- **Redis 6+** (can be disabled)
- **AWS CLI** (for S3 operations)
- **Google Cloud SDK** (for GCS operations)

### Configuration Files

All guides assume you have:
- `backend/.env` configured
- Database connection details
- Admin credentials set
- JWT secret key configured

See **[QUICK_START.md](./QUICK_START.md)** for configuration details.

---

## Quick Start Decision Tree

```
Are you setting up for the first time?
├─ Yes → START_HERE.md
│   └─ Want more details? → QUICK_START.md
│
└─ No → Already set up?
    ├─ Yes → Want to run migrations?
    │   ├─ Yes → Testing new migration? → QUICK_START_NEW_MIGRATION.md
    │   │   └─ GCS to S3 transfer? → QUICK_START_GCS_S3_TRANSFER.md
    │   │
    │   └─ No → Just run existing? → RUN_MIGRATION_NOW.md
    │
    └─ No → Having issues?
        └─ Yes → Redshift load problem? → RUN_DEBUG_SCRIPTS.md
```

---

## File Descriptions

### Setup Files

**START_HERE.md**
- Main entry point for new users
- 3-command quick setup
- UV installation guide
- Documentation index
- Help resources

**QUICK_START.md**
- Most comprehensive setup guide
- Complete UV package manager guide
- Backend and frontend setup
- Configuration details
- API testing examples
- Troubleshooting section
- UV vs pip comparison

**QUICK_START_GUIDE.md**
- Setup after dependency fixes
- Virtual environment recreation
- Frontend server location fix
- Verification steps
- Browser cache clearing

**RUN_NOW.md**
- Simplest "ready to run" guide
- Pre-configured settings
- 3 commands to start
- Quick health checks
- Documentation links

### Migration Files

**QUICK_START_NEW_MIGRATION.md**
- Test new migration creation
- UI-based workflow
- Stage-by-stage monitoring
- Expected timeline (5-15 min)
- Success indicators
- Connection requirements
- Before/after comparison

**QUICK_START_GCS_S3_TRANSFER.md**
- Pathway A specific guide
- GCS to S3 transfer setup
- Prerequisites and permissions
- Step-by-step instructions
- Verification procedures
- Expected timeline (7-40 min)
- Troubleshooting section

**RUN_MIGRATION_NOW.md**
- Run specific reset migration
- Stage execution details
- Expected duration (~1 min)
- Monitor progress
- Verify in Redshift
- Common issues

**QUICK_START_AFTER_RESTART.md**
- Post-server restart guide
- Background migration changes
- View logs feature
- Expected behavior
- Success indicators
- Monitoring tips

### Debug Files

**RUN_DEBUG_SCRIPTS.md**
- Debug Redshift load issues
- Diagnostic script usage
- Load test script usage
- Expected output examples
- Common issues and solutions
- Redshift verification queries
- Step-by-step troubleshooting

---

## Success Indicators

### Backend Running Successfully
✅ Health endpoint returns 200 OK
✅ API docs accessible at /api/docs
✅ No error messages in logs
✅ Database connection established

### Frontend Running Successfully
✅ UI loads at http://localhost:3000
✅ Login page displays
✅ No console errors
✅ API calls succeed

### Migration Running Successfully
✅ Status changes: pending → running → completed
✅ All stages complete (export, transfer, load)
✅ Logs show progress
✅ Data appears in target database

---

## Troubleshooting Quick Reference

### Backend Won't Start
1. Check database connection
2. Verify .env file exists
3. Check port 8000 is free
4. Review error logs

**See**: QUICK_START.md troubleshooting section

### Frontend Won't Start
1. Check npm install completed
2. Verify .env file exists
3. Check port 3000 is free
4. Clear node_modules and reinstall

**See**: QUICK_START_GUIDE.md

### Migration Fails
1. Check connection credentials
2. Verify IAM roles and permissions
3. Check S3/GCS bucket access
4. Review migration logs

**See**: RUN_DEBUG_SCRIPTS.md

### Data Not in Redshift
1. Run diagnostic script
2. Check load stage executed
3. Verify IAM role
4. Check S3 files exist

**See**: RUN_DEBUG_SCRIPTS.md

---

## Related Documentation

### Architecture & Design
- [Architecture Overview](../../ARCHITECTURE.md)
- [SaaS Implementation Guide](../../SAAS_IMPLEMENTATION_GUIDE.md)
- [Migration Best Practices](../../.kiro/steering/migration-best-practices.md)

### API Documentation
- [API Docs](../api/) - API endpoint documentation
- Interactive Docs: http://localhost:8000/api/docs (when running)

### Fix Documentation
- [Fixes](../fixes/README.md) - All bug fixes and solutions

### Testing Documentation
- [Testing](../testing/README.md) - Test cases and standards

---

## Tips & Best Practices

### Setup Tips
- Use UV for faster package installation (10-100x faster than pip)
- Always activate virtual environment before running commands
- Keep .env file secure and never commit it
- Use hard refresh (Cmd+Shift+R) after code changes

### Migration Tips
- Start with small datasets for testing
- Monitor logs in real-time
- Verify data at each stage
- Keep source data until verification complete
- Use appropriate pathway for your use case

### Debugging Tips
- Check logs first (backend and browser console)
- Use diagnostic scripts before manual debugging
- Verify configuration before running migrations
- Test connections independently
- Check IAM roles and permissions

---

## Quick Start Checklist

### First Time Setup
- [ ] Install UV or ensure pip is available
- [ ] Clone repository
- [ ] Configure backend/.env file
- [ ] Create virtual environment
- [ ] Install dependencies
- [ ] Run database migrations
- [ ] Create admin user
- [ ] Start backend server
- [ ] Start frontend server
- [ ] Test login

### Before Running Migration
- [ ] Backend server running
- [ ] Frontend server running
- [ ] Source connection configured
- [ ] Target connection configured
- [ ] IAM roles configured
- [ ] S3/GCS buckets accessible
- [ ] Credentials encrypted

### After Migration
- [ ] Check migration status
- [ ] Review logs
- [ ] Verify data in target
- [ ] Compare row counts
- [ ] Test data integrity
- [ ] Clean up if needed

---

## Support & Help

### Getting Help
1. Check the relevant quick start guide
2. Review troubleshooting sections
3. Check related documentation
4. Review error logs
5. Use diagnostic scripts

### Common Resources
- **Setup Issues**: QUICK_START.md
- **Migration Issues**: QUICK_START_NEW_MIGRATION.md
- **Debug Issues**: RUN_DEBUG_SCRIPTS.md
- **Configuration**: Backend .env file
- **API Testing**: http://localhost:8000/api/docs

---

## Version History

- **v1.0** - Initial quick start guides
- **v1.1** - Added UV package manager support
- **v1.2** - Added GCS to S3 transfer guide
- **v1.3** - Added debug scripts guide
- **v1.4** - Added after restart guide
- **v1.5** - Organized into docs/quickstart/

---

**Last Updated**: February 14, 2026
**Maintained By**: DataMIQ Development Team

**Ready to start?** → [START_HERE.md](./START_HERE.md)
