# How to Run DataMIQ

## Quick Start Guide

This guide will help you set up and run the DataMIQ Authentication and Navigation System on your local machine.

---

## Prerequisites

### Required Software

1. **Python 3.9+**
   ```bash
   python3 --version
   # Should show Python 3.9 or higher
   ```

2. **PostgreSQL 12+**
   ```bash
   psql --version
   # Should show PostgreSQL 12 or higher
   ```

3. **Redis 6+** (Optional but recommended)
   ```bash
   redis-cli --version
   # Should show Redis 6 or higher
   ```

4. **Node.js 16+** (for frontend)
   ```bash
   node --version
   # Should show v16 or higher
   ```

5. **npm or yarn** (for frontend)
   ```bash
   npm --version
   # or
   yarn --version
   ```

### Optional Software

- **AWS CLI** (if using AWS services)
- **Docker** (for containerized deployment)
- **PM2** (for process management)

---

## Step 1: Database Setup

### Option A: Local PostgreSQL

1. **Install PostgreSQL** (if not already installed)
   ```bash
   # macOS
   brew install postgresql@14
   brew services start postgresql@14
   
   # Ubuntu/Debian
   sudo apt-get install postgresql postgresql-contrib
   sudo systemctl start postgresql
   
   # Windows
   # Download from https://www.postgresql.org/download/windows/
   ```

2. **Create Database and User**
   ```bash
   # Connect to PostgreSQL
   psql postgres
   
   # Create database
   CREATE DATABASE datamiq;
   
   # Create user
   CREATE USER datamiq WITH PASSWORD 'your_secure_password';
   
   # Grant privileges
   GRANT ALL PRIVILEGES ON DATABASE datamiq TO datamiq;
   
   # Exit
   \q
   ```

3. **Verify Connection**
   ```bash
   psql -h localhost -U datamiq -d datamiq
   # Enter password when prompted
   ```

### Option B: Use Existing Database

If you already have a PostgreSQL database (like the one in your .env):
- Host: `34.226.150.199`
- Port: `5432`
- Database: `datamiq`
- User: `datamiq`
- Password: `datamiq`

Skip to Step 2.

---

## Step 2: Redis Setup (Optional)

### Option A: Local Redis

1. **Install Redis**
   ```bash
   # macOS
   brew install redis
   brew services start redis
   
   # Ubuntu/Debian
   sudo apt-get install redis-server
   sudo systemctl start redis
   
   # Windows
   # Download from https://github.com/microsoftarchive/redis/releases
   ```

2. **Verify Redis is Running**
   ```bash
   redis-cli ping
   # Should return: PONG
   ```

### Option B: Skip Redis

The application will work without Redis by falling back to the database. Set in `.env`:
```bash
REDIS_ENABLED=false
```

---

## Step 3: Backend Setup

### 1. Navigate to Backend Directory
```bash
cd backend
```

### 2. Create Python Virtual Environment
```bash
# Create virtual environment with uv
uv venv

# Activate virtual environment
# macOS/Linux:
source .venv/bin/activate

# Windows:
.venv\Scripts\activate

# Verify activation (should show (venv) in prompt)
which python
# Should show path to .venv/bin/python
```

### 3. Install Dependencies
```bash
uv pip install --upgrade pip
uv pip install -r requirements.txt
```

### 4. Configure Environment Variables

**Option A: Use Existing Configuration**

Your current `.env` file is already configured. Verify it has:
```bash
cat .env | grep -E "APP_DB_|JWT_SECRET_KEY|REDIS_"
```

**Option B: Create New Configuration**

```bash
# Copy example file
cp .env.example .env

# Edit with your values
nano .env  # or vim, code, etc.
```

**Required Variables**:
```bash
# Database
APP_DB_HOST=localhost  # or 34.226.150.199
APP_DB_PORT=5432
APP_DB_NAME=datamiq
APP_DB_USER=datamiq
APP_DB_PASSWORD=your_password

# JWT Secret (generate a secure random string)
JWT_SECRET_KEY=your_long_random_secret_key_here

# Redis (optional)
REDIS_HOST=localhost  # or 34.226.150.199
REDIS_PORT=6379
REDIS_ENABLED=true  # or false to disable
```

**Generate Secure JWT Secret**:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# Copy output to JWT_SECRET_KEY in .env
```

### 5. Run Database Migrations
```bash
# Run Alembic migrations to create tables
alembic upgrade head

# Verify tables were created
psql -h localhost -U datamiq -d datamiq -c "\dt"
# Should show: users, sessions, audit_logs, organizations, workspaces, user_workspaces
```

### 6. Create Admin User
```bash
# Admin credentials are already in .env:
# ADMIN_USER=admin
# ADMIN_PASSWORD=AdminPass123!

# Run setup script (reads from .env)
python scripts/setup_admin.py

# Expected output:
# Admin user created successfully
# Username: admin
# Role: admin
```

**Alternative: Set via environment variables**:
```bash
export ADMIN_USER=admin
export ADMIN_PASSWORD=AdminPass123!
python scripts/setup_admin.py
```

### 7. Start Backend Server
```bash
# Development mode (with auto-reload)
python main.py

# Or using uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Expected output:
# INFO:     Started server process
# INFO:     Waiting for application startup.
# INFO:     Application startup complete.
# INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 8. Verify Backend is Running

**Test Health Endpoint**:
```bash
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","service":"datamiq-api","version":"1.0.0"}
```

**Test API Documentation**:
Open browser to: http://localhost:8000/api/docs

**Test Login Endpoint**:
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"AdminPass123!"}'

# Expected response:
# {
#   "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
#   "token_type": "bearer",
#   "user": {
#     "id": 1,
#     "username": "admin",
#     "role": "admin",
#     "organization_id": 1
#   }
# }
```

---

## Step 4: Frontend Setup

### 1. Navigate to Frontend Directory
```bash
cd ../frontend  # from backend directory
# or
cd frontend  # from project root
```

### 2. Install Dependencies

**If package.json exists**:
```bash
npm install
# or
yarn install
```

**If package.json doesn't exist**, create it:
```bash
npm init -y

# Install React and dependencies
npm install react react-dom react-router-dom
npm install axios
npm install lucide-react

# Install TypeScript and types
npm install --save-dev typescript @types/react @types/react-dom @types/node

# Install build tools
npm install --save-dev vite @vitejs/plugin-react

# Or use Create React App
npx create-react-app . --template typescript
```

### 3. Configure Environment

Create `.env` file:
```bash
echo "REACT_APP_API_URL=http://localhost:8000" > .env
```

Or for Vite:
```bash
echo "VITE_API_URL=http://localhost:8000" > .env
```

### 4. Start Frontend Development Server

**If using Vite**:
```bash
npm run dev
# Opens on http://localhost:5173
```

**If using Create React App**:
```bash
npm start
# Opens on http://localhost:3000
```

**If using custom setup**:
```bash
# Add to package.json scripts:
# "start": "react-scripts start"
# or
# "dev": "vite"

npm start
```

---

## Step 5: Access the Application

### Backend API
- **URL**: http://localhost:8000
- **API Docs**: http://localhost:8000/api/docs
- **Health Check**: http://localhost:8000/health

### Frontend Application
- **URL**: http://localhost:3000 (or http://localhost:5173 for Vite)
- **Login**: Use admin credentials
  - Username: `admin`
  - Password: `AdminPass123!` (or what you set)

---

## Common Issues and Solutions

### Issue 1: Database Connection Failed

**Error**: `psycopg2.OperationalError: could not connect to server`

**Solutions**:
```bash
# Check PostgreSQL is running
pg_isready

# Check connection details in .env
cat backend/.env | grep APP_DB_

# Test connection manually
psql -h localhost -U datamiq -d datamiq

# Check PostgreSQL logs
tail -f /usr/local/var/log/postgresql@14.log  # macOS
sudo tail -f /var/log/postgresql/postgresql-14-main.log  # Linux
```

### Issue 2: Redis Connection Failed

**Error**: `redis.exceptions.ConnectionError`

**Solutions**:
```bash
# Check Redis is running
redis-cli ping

# Or disable Redis in .env
REDIS_ENABLED=false

# Restart Redis
brew services restart redis  # macOS
sudo systemctl restart redis  # Linux
```

### Issue 3: Alembic Migration Failed

**Error**: `alembic.util.exc.CommandError`

**Solutions**:
```bash
# Check database connection
psql -h localhost -U datamiq -d datamiq

# Reset migrations (CAUTION: drops all tables)
alembic downgrade base
alembic upgrade head

# Check migration status
alembic current
alembic history
```

### Issue 4: Admin User Already Exists

**Error**: `User already exists`

**Solution**:
```bash
# This is normal if you've run setup before
# To reset admin password, delete and recreate:

psql -h localhost -U datamiq -d datamiq
DELETE FROM users WHERE username = 'admin';
\q

# Run setup again
python scripts/setup_admin.py
```

### Issue 5: JWT Secret Key Not Set

**Error**: `ValueError: JWT_SECRET_KEY environment variable not set`

**Solution**:
```bash
# Generate secure key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Add to .env
echo "JWT_SECRET_KEY=<generated_key>" >> backend/.env

# Restart backend
```

### Issue 6: CORS Error in Frontend

**Error**: `Access to XMLHttpRequest blocked by CORS policy`

**Solution**:
```bash
# Check CORS_ORIGINS in backend/.env
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# Restart backend after changing
```

### Issue 7: Port Already in Use

**Error**: `Address already in use`

**Solutions**:
```bash
# Find process using port 8000
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Kill process
kill -9 <PID>  # macOS/Linux
taskkill /PID <PID> /F  # Windows

# Or use different port in .env
APP_PORT=8001
```

---

## Development Workflow

### Running Both Backend and Frontend

**Terminal 1 - Backend**:
```bash
cd backend
source venv/bin/activate
python main.py
```

**Terminal 2 - Frontend**:
```bash
cd frontend
npm run dev
```

### Watching Logs

**Backend Logs**:
```bash
# In backend directory
tail -f logs/app.log  # if logging to file

# Or watch console output
python main.py
```

**Database Logs**:
```bash
# PostgreSQL logs
tail -f /usr/local/var/log/postgresql@14.log  # macOS
sudo tail -f /var/log/postgresql/postgresql-14-main.log  # Linux
```

**Redis Logs**:
```bash
# Redis logs
tail -f /usr/local/var/log/redis.log  # macOS
sudo tail -f /var/log/redis/redis-server.log  # Linux
```

---

## Production Deployment

### Using PM2 (Process Manager)

1. **Install PM2**:
   ```bash
   npm install -g pm2
   ```

2. **Create ecosystem.config.js**:
   ```javascript
   module.exports = {
     apps: [{
       name: 'datamiq-backend',
       script: 'main.py',
       interpreter: 'python3',
       cwd: './backend',
       env: {
         APP_ENV: 'production',
         APP_PORT: 8000
       }
     }]
   };
   ```

3. **Start with PM2**:
   ```bash
   pm2 start ecosystem.config.js
   pm2 logs datamiq-backend
   pm2 status
   ```

### Using Docker

1. **Create Dockerfile** (backend):
   ```dockerfile
   FROM python:3.9-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install -r requirements.txt
   COPY . .
   CMD ["python", "main.py"]
   ```

2. **Build and Run**:
   ```bash
   docker build -t datamiq-backend .
   docker run -p 8000:8000 --env-file .env datamiq-backend
   ```

### Using Systemd (Linux)

1. **Create service file** `/etc/systemd/system/datamiq.service`:
   ```ini
   [Unit]
   Description=DataMIQ Backend
   After=network.target postgresql.service redis.service

   [Service]
   Type=simple
   User=datamiq
   WorkingDirectory=/opt/datamiq/backend
   Environment="PATH=/opt/datamiq/backend/venv/bin"
   ExecStart=/opt/datamiq/backend/venv/bin/python main.py
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

2. **Enable and start**:
   ```bash
   sudo systemctl enable datamiq
   sudo systemctl start datamiq
   sudo systemctl status datamiq
   ```

---

## Testing the Application

### Manual Testing

1. **Login**:
   - Go to http://localhost:3000/login
   - Enter username: `admin`
   - Enter password: `AdminPass123!`
   - Click "Login"
   - Should redirect to dashboard

2. **Navigation**:
   - Click "Dashboard" - should navigate
   - Click "Connections" - should navigate
   - Click "Migrations" - should navigate
   - Click "Jobs" - should navigate
   - Click "Administration" (admin only) - should navigate

3. **Logout**:
   - Click user profile
   - Click "Logout"
   - Should redirect to login

### API Testing

```bash
# Test login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"AdminPass123!"}'

# Save token
TOKEN="<paste_token_here>"

# Test authenticated endpoint
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer $TOKEN"

# Test logout
curl -X POST http://localhost:8000/api/auth/logout \
  -H "Authorization: Bearer $TOKEN"
```

---

## Stopping the Application

### Stop Backend
```bash
# If running in terminal
Ctrl+C

# If using PM2
pm2 stop datamiq-backend

# If using systemd
sudo systemctl stop datamiq
```

### Stop Frontend
```bash
# If running in terminal
Ctrl+C
```

### Stop Services
```bash
# Stop PostgreSQL
brew services stop postgresql@14  # macOS
sudo systemctl stop postgresql  # Linux

# Stop Redis
brew services stop redis  # macOS
sudo systemctl stop redis  # Linux
```

---

## Next Steps

1. **Explore the API**: http://localhost:8000/api/docs
2. **Read Documentation**: See `docs/` folder
3. **Add Users**: Use admin panel to create more users
4. **Configure Workspaces**: Set up workspaces for multi-tenancy
5. **Customize**: Modify UI components and add features

---

## Support

### Documentation
- API Documentation: `docs/api/authentication.md`
- Database Schema: `docs/database/schema/overview.md`
- Backend Services: `docs/backend/services/`
- Implementation Guide: `IMPLEMENTATION_COMPLETE.md`

### Configuration
- Environment Variables: `.env.example`
- Database Migrations: `backend/alembic/versions/`
- Steering Files: `.kiro/steering/`

### Troubleshooting
- Check logs in terminal output
- Verify environment variables in `.env`
- Test database connection with `psql`
- Test Redis connection with `redis-cli ping`
- Check API docs at http://localhost:8000/api/docs

---

**Last Updated**: 2026-01-25
**Version**: 1.0.0
