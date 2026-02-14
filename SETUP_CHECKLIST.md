# DataMIQ Setup Checklist

## ✅ Pre-Setup Verification

Your `.env` file is already configured! Verify these settings:

```bash
cd backend
cat .env | grep -E "APP_DB_|REDIS_|JWT_SECRET_KEY|ADMIN_"
```

Should show:
- ✅ `APP_DB_HOST=34.226.150.199`
- ✅ `APP_DB_NAME=datamiq`
- ✅ `REDIS_HOST=34.226.150.199`
- ✅ `JWT_SECRET_KEY=<configured>`
- ✅ `ADMIN_USER=admin`
- ✅ `ADMIN_PASSWORD=AdminPass123!`

---

## 📋 Setup Steps

### Step 1: Backend Setup
```bash
cd backend

# Create virtual environment with uv
uv venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install dependencies with uv
uv pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Create admin user (reads from .env automatically)
python scripts/setup_admin.py

# Start backend
python main.py
```

**Expected Output**:
```
✅ Admin user created successfully
✅ Database connection successful
✅ Uvicorn running on http://0.0.0.0:8000
```

**Test Backend**:
```bash
curl http://localhost:8000/health
# Should return: {"status":"healthy","service":"datamiq-api","version":"1.0.0"}
```

---

### Step 2: Frontend Setup
```bash
cd frontend

# Install dependencies (if package.json exists)
npm install

# Configure API URL
echo "REACT_APP_API_URL=http://localhost:8000" > .env

# Start frontend
npm start
```

**Expected Output**:
```
✅ Compiled successfully!
✅ Local: http://localhost:3000
```

---

## 🧪 Test the Application

### 1. Test Backend API
```bash
# Test login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"AdminPass123!"}'

# Should return:
# {
#   "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
#   "token_type": "bearer",
#   "user": {
#     "id": 1,
#     "username": "admin",
#     "role": "admin"
#   }
# }
```

### 2. Test Frontend Login
1. Open: http://localhost:3000/login
2. Enter:
   - Username: `admin`
   - Password: `AdminPass123!`
3. Click "Login"
4. Should redirect to: http://localhost:3000/dashboard

---

## 🔧 Configuration Files

### backend/.env (Already Configured ✅)
```bash
# Database
APP_DB_HOST=34.226.150.199
APP_DB_PORT=5432
APP_DB_NAME=datamiq
APP_DB_USER=datamig
APP_DB_PASSWORD=datamig

# Redis
REDIS_HOST=34.226.150.199
REDIS_PORT=6379
REDIS_ENABLED=true

# Security
JWT_SECRET_KEY=change_me_in_production_use_long_random_string

# Admin User (for setup script)
ADMIN_USER=admin
ADMIN_PASSWORD=AdminPass123!
```

### frontend/.env (Create This)
```bash
REACT_APP_API_URL=http://localhost:8000
```

---

## 🚨 Troubleshooting

### Issue: Database Connection Failed
```bash
# Test connection
psql -h 34.226.150.199 -U datamig -d datamig

# If fails, check:
# 1. Database is running
# 2. Credentials in .env are correct
# 3. Network allows connection to 34.226.150.199:5432
```

### Issue: Redis Connection Failed
```bash
# Test Redis
redis-cli -h 34.226.150.199 -p 6379 ping

# If fails, disable Redis in .env:
REDIS_ENABLED=false

# Application will fallback to database
```

### Issue: Admin User Already Exists
```bash
# This is normal if you've run setup before
# To reset, delete and recreate:
psql -h 34.226.150.199 -U datamig -d datamig
DELETE FROM users WHERE username = 'admin';
\q

# Run setup again
python scripts/setup_admin.py
```

### Issue: Port 8000 Already in Use
```bash
# Find process
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Kill process
kill -9 <PID>  # macOS/Linux
taskkill /PID <PID> /F  # Windows

# Or change port in .env
APP_PORT=8001
```

---

## 📊 Verification Checklist

After setup, verify:

- [ ] Backend running on http://localhost:8000
- [ ] Frontend running on http://localhost:3000
- [ ] Health endpoint returns healthy: http://localhost:8000/health
- [ ] API docs accessible: http://localhost:8000/api/docs
- [ ] Can login with admin credentials
- [ ] Dashboard loads after login
- [ ] Navigation works (Dashboard, Connections, Migrations, Jobs)
- [ ] Can logout successfully

---

## 🎯 Quick Commands Reference

### Start Backend
```bash
cd backend && source .venv/bin/activate && python main.py
```

### Start Frontend
```bash
cd frontend && npm start
```

### Run Migrations
```bash
cd backend && source .venv/bin/activate && alembic upgrade head
```

### Create Admin User
```bash
cd backend && source .venv/bin/activate && python scripts/setup_admin.py
```

### Test API
```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/docs
```

### Check Database
```bash
psql -h 34.226.150.199 -U datamig -d datamig -c "\dt"
```

### Check Redis
```bash
redis-cli -h 34.226.150.199 -p 6379 ping
```

---

## 📚 Additional Resources

- **Full Setup Guide**: `HOW_TO_RUN.md`
- **Quick Start**: `QUICK_START.md`
- **Architecture**: `ARCHITECTURE.md`
- **API Documentation**: `docs/api/authentication.md`
- **Database Schema**: `docs/database/schema/overview.md`

---

## ✨ Success!

If all checks pass, you're ready to use DataMIQ!

**Access Points**:
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/api/docs
- Frontend App: http://localhost:3000
- Login: admin / AdminPass123!

**Next Steps**:
1. Explore the API documentation
2. Create additional users
3. Set up workspaces
4. Start using the application

---

**Last Updated**: 2026-01-25
**Version**: 1.0.0
