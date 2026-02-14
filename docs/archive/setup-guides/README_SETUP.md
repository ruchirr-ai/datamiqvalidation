# DataMIQ - Setup & Run Guide

## 🚀 Quick Start (3 Commands)

Your configuration is already complete! Just run:

```bash
# 1. Setup Backend
cd backend && uv venv && source .venv/bin/activate && \
uv pip install -r requirements.txt && alembic upgrade head && \
python scripts/setup_admin.py && python main.py

# 2. Setup Frontend (in new terminal)
cd frontend && npm install && \
echo "REACT_APP_API_URL=http://localhost:8000" > .env && npm start

# 3. Login
# Open http://localhost:3000
# Username: admin
# Password: AdminPass123!
```

---

## 📋 What's Already Configured

Your `backend/.env` file has everything set up:

✅ **Database**: PostgreSQL at 34.226.150.199:5432/datamiq  
✅ **Redis**: Redis at 34.226.150.199:6379  
✅ **JWT Secret**: Configured  
✅ **Admin Credentials**: admin / AdminPass123!  
✅ **CORS**: Configured for localhost:3000  

**No additional configuration needed!**

---

## 📖 Documentation Files

| File | Purpose |
|------|---------|
| **QUICK_START.md** | 5-minute quick start guide |
| **HOW_TO_RUN.md** | Complete detailed setup guide |
| **SETUP_CHECKLIST.md** | Step-by-step checklist |
| **ARCHITECTURE.md** | System architecture diagrams |
| **CURRENT_STATUS.md** | Project status overview |

---

## 🎯 Step-by-Step Setup

### Backend Setup

```bash
cd backend

# 1. Create virtual environment with uv
uv venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# 2. Install dependencies with uv
uv pip install -r requirements.txt

# 3. Run database migrations
alembic upgrade head

# 4. Create admin user (reads from .env)
python scripts/setup_admin.py

# 5. Start backend
python main.py
```

**Backend Running**: http://localhost:8000  
**API Docs**: http://localhost:8000/api/docs

### Frontend Setup

```bash
cd frontend

# 1. Install dependencies
npm install

# 2. Configure API URL
echo "REACT_APP_API_URL=http://localhost:8000" > .env

# 3. Start frontend
npm start
```

**Frontend Running**: http://localhost:3000

---

## 🧪 Test It Works

### Test Backend
```bash
curl http://localhost:8000/health
# Should return: {"status":"healthy","service":"datamiq-api","version":"1.0.0"}

curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"AdminPass123!"}'
# Should return: {"access_token":"...","token_type":"bearer","user":{...}}
```

### Test Frontend
1. Open: http://localhost:3000/login
2. Login with: admin / AdminPass123!
3. Should redirect to dashboard

---

## 🔧 Environment Variables

### backend/.env (Already Configured ✅)

The setup script reads these variables automatically:

```bash
# Database Connection
APP_DB_HOST=34.226.150.199
APP_DB_PORT=5432
APP_DB_NAME=datamiq
APP_DB_USER=datamig
APP_DB_PASSWORD=datamig

# Redis Cache
REDIS_HOST=34.226.150.199
REDIS_PORT=6379
REDIS_ENABLED=true

# Security
JWT_SECRET_KEY=change_me_in_production_use_long_random_string

# Admin User (for setup script)
ADMIN_USER=admin
ADMIN_PASSWORD=AdminPass123!

# Application
APP_PORT=8000
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

### frontend/.env (Create This)

```bash
REACT_APP_API_URL=http://localhost:8000
```

---

## 🚨 Common Issues

### Database Connection Failed
```bash
# Test connection
psql -h 34.226.150.199 -U datamig -d datamig

# Check credentials in backend/.env
cat backend/.env | grep APP_DB_
```

### Redis Connection Failed
```bash
# Test Redis
redis-cli -h 34.226.150.199 -p 6379 ping

# Or disable Redis
# Edit backend/.env: REDIS_ENABLED=false
```

### Port Already in Use
```bash
# Find process on port 8000
lsof -i :8000

# Kill it
kill -9 <PID>

# Or change port in backend/.env
# APP_PORT=8001
```

### Admin User Already Exists
```bash
# This is normal if you've run setup before
# The application will work fine
# To reset password, delete user and run setup again:
psql -h 34.226.150.199 -U datamig -d datamig
DELETE FROM users WHERE username = 'admin';
\q
python scripts/setup_admin.py
```

---

## 📊 System Architecture

```
Browser (localhost:3000)
    ↓
Frontend (React)
    ↓ REST API
Backend (FastAPI - localhost:8000)
    ↓
PostgreSQL (34.226.150.199:5432)
Redis (34.226.150.199:6379)
```

---

## 🎓 Features Implemented

✅ **Authentication**
- Username/password login
- JWT tokens (8-hour expiration)
- Account locking (5 failed attempts)
- Token blacklisting on logout

✅ **Authorization**
- Role-based access control (owner, admin, member)
- Workspace isolation
- Permission checking

✅ **UI/UX**
- Responsive design (mobile, tablet, desktop)
- Snowflake-inspired minimal design
- Collapsible sidebar
- Role-based navigation

✅ **Security**
- Password hashing (bcrypt)
- JWT token validation
- Audit logging
- AWS KMS integration ready

✅ **Performance**
- Redis caching with database fallback
- Connection pooling
- Session management

---

## 📚 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/docs` | GET | API documentation |
| `/api/auth/login` | POST | User login |
| `/api/auth/logout` | POST | User logout |
| `/api/auth/me` | GET | Get current user |
| `/api/auth/refresh` | POST | Refresh token |

---

## 🔐 Default Credentials

**Username**: `admin`  
**Password**: `AdminPass123!`

(Configured in `backend/.env`)

---

## 📖 Next Steps

1. ✅ Run the setup commands above
2. ✅ Test login at http://localhost:3000
3. 📖 Read `HOW_TO_RUN.md` for detailed guide
4. 📖 Read `ARCHITECTURE.md` for system design
5. 📖 Explore API docs at http://localhost:8000/api/docs
6. 🔧 Customize and extend the application

---

## 💡 Tips

- **Development**: Backend auto-reloads on code changes
- **API Testing**: Use http://localhost:8000/api/docs (Swagger UI)
- **Database**: Use `psql` to inspect tables
- **Redis**: Use `redis-cli` to inspect cache
- **Logs**: Check terminal output for errors

---

## 🆘 Need Help?

1. Check `HOW_TO_RUN.md` for detailed troubleshooting
2. Check `SETUP_CHECKLIST.md` for step-by-step verification
3. Review logs in terminal output
4. Verify `.env` configuration
5. Test database and Redis connections

---

## 📦 Project Structure

```
.
├── backend/
│   ├── .env                    # Configuration (already set up!)
│   ├── main.py                 # FastAPI application
│   ├── requirements.txt        # Python dependencies
│   ├── alembic/                # Database migrations
│   ├── services/               # Business logic
│   ├── routers/                # API endpoints
│   ├── repositories/           # Database operations
│   └── scripts/                # Setup scripts
├── frontend/
│   ├── src/
│   │   ├── components/         # React components
│   │   ├── pages/              # Page components
│   │   ├── contexts/           # React contexts
│   │   └── services/           # API services
│   └── package.json            # Node dependencies
├── docs/                       # Documentation
├── HOW_TO_RUN.md              # Detailed setup guide
├── QUICK_START.md             # Quick start guide
├── SETUP_CHECKLIST.md         # Setup checklist
└── ARCHITECTURE.md            # Architecture diagrams
```

---

**Ready to start?** Run the 3 commands at the top of this file!

**Last Updated**: 2026-01-25  
**Version**: 1.0.0
