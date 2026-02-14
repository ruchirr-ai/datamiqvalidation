# DataMIQ Quick Start

## 🚀 Get Running in 5 Minutes

### Prerequisites
- **UV** (fast Python package manager) - [Install UV](https://docs.astral.sh/uv/getting-started/installation/)
- Python 3.9+
- PostgreSQL 12+
- Redis 6+ (optional, can be disabled)

---

## Why UV?

UV is a modern, fast Python package manager that:
- ⚡ **10-100x faster** than pip for installing packages
- 📦 **Modern standard**: Uses `pyproject.toml` (PEP 621)
- 🔒 **Reproducible builds**: Creates lockfiles automatically
- 🎯 **Simple commands**: `uv add`, `uv remove`, `uv sync`
- 🔄 **Compatible**: Works with existing `requirements.txt`

### UV Commands Reference

```bash
# Create virtual environment
uv venv                          # Creates .venv/

# Activate environment
source .venv/bin/activate        # macOS/Linux
.venv\Scripts\activate           # Windows

# Initialize project (creates pyproject.toml)
uv init

# Add packages from requirements.txt
uv add -r requirements.txt       # Recommended: adds to pyproject.toml

# Or install directly (faster, no pyproject.toml)
uv pip install -r requirements.txt

# Add a single package
uv add fastapi                   # Adds to pyproject.toml + installs

# Remove a package
uv remove fastapi                # Removes from pyproject.toml + uninstalls

# Sync environment with lockfile
uv sync                          # Install exact versions from lockfile

# Update all packages
uv lock --upgrade                # Update lockfile with latest versions
```

---

## Backend Setup

```bash
# 1. Navigate to backend
cd backend

# 2. Create virtual environment with UV
uv venv

# 3. Activate the environment
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# 4. Initialize UV project (creates pyproject.toml)
uv init

# 5. Add requirements to project (modern approach)
uv add -r requirements.txt
# This reads requirements.txt, adds packages to pyproject.toml,
# installs them, and creates a lockfile for reproducible builds

# Alternative: Direct install (faster, but no pyproject.toml)
# uv pip install -r requirements.txt

# 6. Configure environment (use existing .env or create new)
# Your .env is already configured with:
# - Database: 34.226.150.199:5432/datamiq
# - Redis: 34.226.150.199:6379
# - JWT_SECRET_KEY: (already set)
# - Admin credentials: ADMIN_USER=admin, ADMIN_PASSWORD=AdminPass123!

# 7. Run migrations
alembic upgrade head

# 8. Create admin user (credentials already in .env)
python scripts/setup_admin.py

# 9. Start server
python main.py
```

**Backend Running**: http://localhost:8000

---

## Frontend Setup

```bash
# 1. Navigate to frontend
cd frontend

# 2. Install dependencies (if package.json exists)
npm install

# 3. Configure API URL
echo "REACT_APP_API_URL=http://localhost:8000" > .env

# 4. Start development server
npm start  # or npm run dev
```

**Frontend Running**: http://localhost:3000

---

## Test Login

1. Open: http://localhost:3000/login
2. Username: `admin`
3. Password: `AdminPass123!`
4. Click "Login"

---

## Quick Commands

### Backend
```bash
# Start backend (with UV)
cd backend && source .venv/bin/activate && python main.py

# Install/update dependencies with UV
uv add -r requirements.txt

# Add a new package with UV
uv add <package-name>

# Run migrations
alembic upgrade head

# Create admin
python scripts/setup_admin.py

# Check health
curl http://localhost:8000/health
```

### Frontend
```bash
# Start frontend
cd frontend && npm start

# Install dependencies
npm install
```

### Database
```bash
# Connect to database
psql -h 34.226.150.199 -U datamiq -d datamiq

# Check tables
psql -h 34.226.150.199 -U datamiq -d datamiq -c "\dt"
```

### Redis
```bash
# Test Redis
redis-cli -h 34.226.150.199 -p 6379 ping

# Or disable Redis in .env
REDIS_ENABLED=false
```

---

## Troubleshooting

### Database Connection Failed
```bash
# Test connection
psql -h 34.226.150.199 -U datamiq -d datamiq

# Check .env
cat backend/.env | grep APP_DB_
```

### Port Already in Use
```bash
# Find process on port 8000
lsof -i :8000

# Kill process
kill -9 <PID>
```

### JWT Secret Not Set
```bash
# Generate new secret
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Add to .env
echo "JWT_SECRET_KEY=<generated>" >> backend/.env
```

---

## API Endpoints

- **Health**: http://localhost:8000/health
- **API Docs**: http://localhost:8000/api/docs
- **Login**: POST http://localhost:8000/api/auth/login
- **Logout**: POST http://localhost:8000/api/auth/logout
- **Me**: GET http://localhost:8000/api/auth/me
- **Refresh**: POST http://localhost:8000/api/auth/refresh

---

## Test API

```bash
# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"AdminPass123!"}'

# Get current user (replace TOKEN)
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer <TOKEN>"
```

---

## Your Current Configuration

Based on your `.env` file:

- **Database**: 34.226.150.199:5432/datamiq ✅
- **Redis**: 34.226.150.199:6379 ✅
- **JWT Secret**: Configured ✅
- **CORS**: http://localhost:3000 ✅
- **Port**: 8000 ✅

Everything is already configured! Just run the commands above.

---

## Next Steps

1. ✅ Backend running on http://localhost:8000
2. ✅ Frontend running on http://localhost:3000
3. ✅ Login with admin credentials
4. ✅ Explore the application
5. 📖 Read full guide: `HOW_TO_RUN.md`
6. 📚 Read documentation: `docs/` folder

---

**Need Help?** See `HOW_TO_RUN.md` for detailed instructions.


---

## 📚 UV Package Manager Guide

### What is UV?

UV is a fast Python package manager written in Rust. It's 10-100x faster than pip and uses modern Python standards.

### Installation

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# With pip (if you have Python already)
pip install uv

# With Homebrew (macOS)
brew install uv
```

### Basic Workflow

```bash
# 1. Create virtual environment
uv venv                          # Creates .venv/ folder

# 2. Activate environment
source .venv/bin/activate        # macOS/Linux
.venv\Scripts\activate           # Windows

# 3. Initialize project (optional, creates pyproject.toml)
uv init

# 4. Add dependencies
uv add -r requirements.txt       # From requirements.txt
uv add fastapi sqlalchemy        # Add specific packages
uv add pytest --dev              # Add dev dependency

# 5. Install dependencies
uv sync                          # Install from lockfile
uv pip install -r requirements.txt  # Direct install (faster)
```

### UV vs Pip

| Feature | UV | Pip |
|---------|----|----|
| Speed | ⚡ 10-100x faster | Standard |
| Lockfile | ✅ Automatic | ❌ Manual |
| Modern format | ✅ pyproject.toml | ❌ requirements.txt |
| Dependency resolution | ✅ Fast | ⏱️ Slow |
| Reproducible builds | ✅ Yes | ⚠️ Requires pip-tools |

### Common UV Commands

```bash
# Package management
uv add <package>                 # Add package
uv remove <package>              # Remove package
uv add <package> --dev           # Add dev dependency
uv sync                          # Sync with lockfile
uv lock                          # Update lockfile

# Environment management
uv venv                          # Create virtual environment
uv venv --python 3.11            # Create with specific Python version
uv pip list                      # List installed packages
uv pip freeze                    # Show installed packages (pip format)

# Installation
uv pip install <package>         # Install package (pip-compatible)
uv pip install -r requirements.txt  # Install from requirements.txt
uv pip install -e .              # Install in editable mode

# Project management
uv init                          # Initialize project (creates pyproject.toml)
uv add -r requirements.txt       # Import requirements.txt to pyproject.toml
```

### Migrating from Pip to UV

If you have an existing project with `requirements.txt`:

```bash
# Option 1: Keep using requirements.txt (faster)
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# Option 2: Migrate to pyproject.toml (modern)
uv venv
source .venv/bin/activate
uv init                          # Creates pyproject.toml
uv add -r requirements.txt       # Imports requirements
# Now you can delete requirements.txt if you want
```

### pyproject.toml Example

After running `uv init` and `uv add -r requirements.txt`, you'll have:

```toml
[project]
name = "datamiq-backend"
version = "0.1.0"
description = "DataMIQ Backend API"
requires-python = ">=3.9"
dependencies = [
    "fastapi>=0.104.0",
    "sqlalchemy>=2.0.0",
    "alembic>=1.12.0",
    "bcrypt>=4.0.1",
    "pyjwt>=2.8.0",
    "redis>=5.0.0",
    "boto3>=1.28.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
]
```

### Troubleshooting UV

**Issue: UV not found after installation**
```bash
# Add UV to PATH (macOS/Linux)
export PATH="$HOME/.cargo/bin:$PATH"

# Or restart terminal
```

**Issue: Permission denied**
```bash
# Run with proper permissions
chmod +x ~/.cargo/bin/uv
```

**Issue: Python version mismatch**
```bash
# Create venv with specific Python version
uv venv --python 3.11
```

### Learn More

- **UV Documentation**: https://docs.astral.sh/uv/
- **UV GitHub**: https://github.com/astral-sh/uv
- **Installation Guide**: https://docs.astral.sh/uv/getting-started/installation/
