# 🚀 DataMIQ - Start Here!

## Quick Setup (Using UV - Fast!)

### 1. Install UV (if not installed)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# or: brew install uv
```

### 2. Setup Backend
```bash
cd backend
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
alembic upgrade head
python scripts/setup_admin.py
python main.py
```

### 3. Setup Frontend (new terminal)
```bash
cd frontend
npm install
echo "REACT_APP_API_URL=http://localhost:8000" > .env
npm start
```

### 4. Login
- Open: http://localhost:3000
- Username: `admin`
- Password: `AdminPass123!`

---

## ✅ Your Configuration is Ready!

Everything is already configured in `backend/.env`:
- ✅ Database: 34.226.150.199:5432/datamiq
- ✅ Redis: 34.226.150.199:6379
- ✅ Admin credentials: admin / AdminPass123!
- ✅ JWT Secret: Configured

**Just run the commands above!**

---

## 📚 Documentation

| File | Purpose |
|------|---------|
| **UV_SETUP_GUIDE.md** | Complete UV setup guide (recommended!) |
| **QUICK_START.md** | 5-minute quick start |
| **HOW_TO_RUN.md** | Detailed setup with troubleshooting |
| **SETUP_CHECKLIST.md** | Step-by-step checklist |
| **ARCHITECTURE.md** | System architecture |

---

## 💡 Why UV?

UV is **10-100x faster** than pip:
- Install dependencies in **3-5 seconds** (vs 30-60 seconds with pip)
- Better dependency resolution
- Drop-in replacement for pip
- Built by the Ruff team (Astral)

See `UV_SETUP_GUIDE.md` for complete UV documentation.

---

## 🆘 Need Help?

1. **UV not installed?** → See `UV_SETUP_GUIDE.md`
2. **Database issues?** → See `HOW_TO_RUN.md` troubleshooting
3. **General setup?** → See `QUICK_START.md`
4. **Architecture questions?** → See `ARCHITECTURE.md`

---

**Ready? Run the 3 commands at the top!**
