# UV Quick Reference

## 🚀 Fast Python Package Manager

UV is 10-100x faster than pip and uses modern Python standards.

---

## Installation

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# With Homebrew (macOS)
brew install uv
```

---

## Quick Start

```bash
# 1. Create virtual environment
uv venv

# 2. Activate
source .venv/bin/activate        # macOS/Linux
.venv\Scripts\activate           # Windows

# 3. Install dependencies
uv pip install -r requirements.txt

# Or use modern approach
uv init                          # Creates pyproject.toml
uv add -r requirements.txt       # Imports requirements
```

---

## Common Commands

### Environment Management
```bash
uv venv                          # Create .venv/
uv venv --python 3.11            # Specific Python version
source .venv/bin/activate        # Activate (macOS/Linux)
.venv\Scripts\activate           # Activate (Windows)
```

### Package Installation
```bash
uv pip install <package>         # Install package
uv pip install -r requirements.txt  # Install from file
uv add <package>                 # Add to pyproject.toml
uv add <package> --dev           # Add dev dependency
uv sync                          # Sync with lockfile
```

### Package Management
```bash
uv add fastapi                   # Add package
uv remove fastapi                # Remove package
uv pip list                      # List installed
uv pip freeze                    # Show versions
uv lock                          # Update lockfile
```

### Project Management
```bash
uv init                          # Create pyproject.toml
uv add -r requirements.txt       # Import requirements
```

---

## UV vs Pip

| Feature | UV | Pip |
|---------|----|----|
| Speed | ⚡ 10-100x faster | Standard |
| Lockfile | ✅ Automatic | ❌ Manual |
| Format | ✅ pyproject.toml | ❌ requirements.txt |
| Resolution | ✅ Fast | ⏱️ Slow |

---

## Two Approaches

### Approach 1: Keep requirements.txt (Simple)
```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

### Approach 2: Use pyproject.toml (Modern)
```bash
uv venv
source .venv/bin/activate
uv init
uv add -r requirements.txt
```

---

## Troubleshooting

**UV not found**
```bash
export PATH="$HOME/.cargo/bin:$PATH"
# Or restart terminal
```

**Permission denied**
```bash
chmod +x ~/.cargo/bin/uv
```

**Python version**
```bash
uv venv --python 3.11
```

---

## Learn More

- **Docs**: https://docs.astral.sh/uv/
- **GitHub**: https://github.com/astral-sh/uv
- **Install**: https://docs.astral.sh/uv/getting-started/installation/

---

## DataMIQ Backend Setup

```bash
cd backend
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
alembic upgrade head
python scripts/setup_admin.py
python main.py
```

✅ Backend running on http://localhost:8000
