# DataMIQ Setup with UV

## 🚀 Quick Setup with UV

This project uses **UV** for fast Python package management instead of pip.

---

## Prerequisites

### 1. Install UV

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with pip (if you have it)
pip install uv

# Or with Homebrew
brew install uv

# Verify installation
uv --version
```

### 2. Other Requirements
- Python 3.9+
- PostgreSQL 12+
- Redis 6+ (optional)
- Node.js 16+ (for frontend)

---

## 🎯 Complete Setup (3 Steps)

### Step 1: Backend Setup with UV

```bash
cd backend

# Create virtual environment with uv
uv venv

# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install all dependencies with uv (much faster than pip!)
uv pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Create admin user (reads from .env)
python scripts/setup_admin.py

# Start backend
python main.py
```

**Backend Running**: http://localhost:8000

---

### Step 2: Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Configure API URL
echo "REACT_APP_API_URL=http://localhost:8000" > .env

# Start frontend
npm start
```

**Frontend Running**: http://localhost:3000

---

### Step 3: Test Login

1. Open: http://localhost:3000/login
2. Username: `admin`
3. Password: `AdminPass123!`
4. Click "Login"

---

## 💡 Why UV?

UV is a **blazingly fast** Python package installer and resolver written in Rust:

- ⚡ **10-100x faster** than pip
- 🔒 **Better dependency resolution**
- 📦 **Compatible with pip** (drop-in replacement)
- 🎯 **Works with requirements.txt**
- 🚀 **Built by the Ruff team** (Astral)

### Speed Comparison

```bash
# Traditional pip
pip install -r requirements.txt  # ~30-60 seconds

# With uv
uv pip install -r requirements.txt  # ~3-5 seconds
```

---

## 📋 UV Commands Reference

### Virtual Environment

```bash
# Create virtual environment
uv venv

# Create with specific Python version
uv venv --python 3.11

# Activate
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows

# Deactivate
deactivate
```

### Package Installation

```bash
# Install from requirements.txt
uv pip install -r requirements.txt

# Install single package
uv pip install fastapi

# Install with version
uv pip install "fastapi==0.109.0"

# Install in editable mode
uv pip install -e .

# Upgrade package
uv pip install --upgrade fastapi

# Uninstall package
uv pip uninstall fastapi
```

### Package Management

```bash
# List installed packages
uv pip list

# Show package info
uv pip show fastapi

# Freeze dependencies
uv pip freeze > requirements.txt

# Check for updates
uv pip list --outdated
```

### Sync Dependencies

```bash
# Install exact versions from requirements.txt
uv pip sync requirements.txt

# This ensures exact match with requirements.txt
# (removes packages not in requirements.txt)
```

---

## 🔧 Project-Specific Commands

### Backend Development

```bash
# Activate environment
cd backend
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt

# Add new package
uv pip install <package-name>

# Update requirements.txt
uv pip freeze > requirements.txt

# Run migrations
alembic upgrade head

# Start server
python main.py
```

### Adding New Dependencies

```bash
# 1. Install with uv
uv pip install sqlalchemy

# 2. Update requirements.txt
uv pip freeze > requirements.txt

# 3. Commit requirements.txt
git add requirements.txt
git commit -m "Add sqlalchemy dependency"
```

---

## 🐛 Troubleshooting

### UV Not Found

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add to PATH (if needed)
export PATH="$HOME/.cargo/bin:$PATH"

# Verify
uv --version
```

### Virtual Environment Issues

```bash
# Remove old venv
rm -rf .venv

# Create new with uv
uv venv

# Activate
source .venv/bin/activate

# Reinstall dependencies
uv pip install -r requirements.txt
```

### Package Installation Fails

```bash
# Try with verbose output
uv pip install -r requirements.txt -v

# Clear cache
uv cache clean

# Try again
uv pip install -r requirements.txt
```

### Compatibility Issues

```bash
# UV is compatible with pip
# If uv fails, you can always fall back to pip:
pip install -r requirements.txt

# But uv should work for 99% of cases
```

---

## 📊 Performance Comparison

### Installation Speed

| Tool | Time | Speed |
|------|------|-------|
| pip | 45s | 1x |
| pip-tools | 38s | 1.2x |
| poetry | 52s | 0.9x |
| **uv** | **4s** | **11x** |

### Dependency Resolution

| Tool | Time | Speed |
|------|------|-------|
| pip | 12s | 1x |
| poetry | 25s | 0.5x |
| **uv** | **0.8s** | **15x** |

---

## 🔄 Migration from pip

If you're used to pip, here's the mapping:

| pip Command | uv Command |
|-------------|------------|
| `pip install package` | `uv pip install package` |
| `pip install -r requirements.txt` | `uv pip install -r requirements.txt` |
| `pip uninstall package` | `uv pip uninstall package` |
| `pip list` | `uv pip list` |
| `pip freeze` | `uv pip freeze` |
| `pip show package` | `uv pip show package` |
| `python -m venv venv` | `uv venv` |

**Just add `uv` before `pip` commands!**

---

## 📚 Additional Resources

- **UV Documentation**: https://github.com/astral-sh/uv
- **UV Installation**: https://astral.sh/uv
- **Ruff (by same team)**: https://github.com/astral-sh/ruff

---

## ✅ Complete Setup Checklist

- [ ] UV installed (`uv --version`)
- [ ] Virtual environment created (`uv venv`)
- [ ] Virtual environment activated (`source .venv/bin/activate`)
- [ ] Dependencies installed (`uv pip install -r requirements.txt`)
- [ ] Database migrations run (`alembic upgrade head`)
- [ ] Admin user created (`python scripts/setup_admin.py`)
- [ ] Backend running (`python main.py`)
- [ ] Frontend running (`npm start`)
- [ ] Can login at http://localhost:3000

---

## 🎓 Best Practices

### 1. Always Use UV for Package Management
```bash
# Good
uv pip install fastapi

# Avoid
pip install fastapi
```

### 2. Keep requirements.txt Updated
```bash
# After installing new packages
uv pip freeze > requirements.txt
```

### 3. Use Virtual Environments
```bash
# Always activate before working
source .venv/bin/activate
```

### 4. Sync Dependencies in CI/CD
```bash
# In CI/CD pipelines
uv pip sync requirements.txt
```

### 5. Cache UV in CI/CD
```yaml
# GitHub Actions example
- name: Set up UV
  uses: astral-sh/setup-uv@v1
  
- name: Install dependencies
  run: uv pip install -r requirements.txt
```

---

## 🚀 Next Steps

1. ✅ Setup complete with UV
2. 📖 Read `HOW_TO_RUN.md` for detailed guide
3. 📚 Explore `docs/` for API documentation
4. 🔧 Start developing!

---

**UV makes Python package management fast and reliable!**

**Last Updated**: 2026-01-25  
**Version**: 1.0.0
