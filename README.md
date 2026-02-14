# DataMIQ - Database Migration Platform

A comprehensive SaaS database migration platform that enables multiple organizations to seamlessly migrate data from any database to any database with assessment, monitoring, and validation capabilities.

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

## 📋 What's Already Configured

Your `backend/.env` file has everything set up:

✅ **Database**: PostgreSQL at 34.226.150.199:5432/datamiq  
✅ **Redis**: Redis at 34.226.150.199:6379  
✅ **JWT Secret**: Configured  
✅ **Admin Credentials**: admin / AdminPass123!  
✅ **CORS**: Configured for localhost:3000  

**No additional configuration needed!**

## 🏗️ Architecture

### Technology Stack
- **Frontend**: React + TypeScript
- **Backend**: Python + FastAPI (Microservices Architecture)
- **Database**: PostgreSQL (application backend)
- **Cache**: Redis (primary cache layer with database fallback)
- **Cloud**: AWS with security best practices
- **Orchestration**: Kubernetes for microservices deployment
- **Architecture**: Multi-tenant SaaS with workspace isolation

### Core Modules

1. **Connections** - Database connection management for source and target databases
2. **Assessment & Reports** - Analyzes source databases and generates detailed assessment reports
3. **Migration Projects** - Organizes migrations into projects with configuration and planning
4. **Migration Tasks** - Breaks down migrations into discrete, trackable tasks
5. **Monitoring** - Real-time monitoring of migration progress and performance metrics
6. **Validation** - Post-migration validation for data integrity and completeness

## 📖 Documentation

### Quick Start Guides
- **[Quick Start Guide](docs/quickstart/README.md)** - Get started in 5 minutes
- **[Setup Checklist](SETUP_CHECKLIST.md)** - Step-by-step verification
- **[How to Run](HOW_TO_RUN.md)** - Complete detailed setup guide

### Module Documentation
- **[Connections Module](docs/CONNECTIONS.md)** - Connection management overview
- **[Migrations Module](docs/MIGRATIONS.md)** - Migration workflow and features
- **[Assessments Module](docs/ASSESSMENTS.md)** - Assessment and reporting capabilities

### Technical Documentation
- **[Architecture](ARCHITECTURE.md)** - System architecture and design
- **[Deployment Guide](DEPLOYMENT_GUIDE.md)** - Production deployment instructions
- **[Testing Guide](TESTING_GUIDE.md)** - Testing standards and practices
- **[API Documentation](docs/api/)** - API endpoint documentation
- **[Database Schema](docs/database/)** - Database structure and design

### Development Standards
See `.kiro/steering/` for:
- Security standards
- Testing standards
- Logging standards
- Documentation standards
- Multi-tenant architecture guidelines
- Caching strategy
- AWS deployment best practices

## 🎯 Step-by-Step Setup

### Prerequisites

- **Python 3.9+** with uv package manager
- **PostgreSQL 12+** (already configured at 34.226.150.199)
- **Redis 6+** (already configured at 34.226.150.199)
- **Node.js 16+** and npm

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

## 🧪 Verify Setup

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

## 🚨 Common Issues

### Database Connection Failed
```bash
# Test connection
psql -h 34.226.150.199 -U datamig -d datamiq

# Check credentials in backend/.env
cat backend/.env | grep APP_DB_
```

### Redis Connection Failed
```bash
# Test Redis
redis-cli -h 34.226.150.199 -p 6379 ping

# Or disable Redis in backend/.env
REDIS_ENABLED=false
```

### Port Already in Use
```bash
# Find process on port 8000
lsof -i :8000

# Kill it
kill -9 <PID>

# Or change port in backend/.env
APP_PORT=8001
```

### Admin User Already Exists
```bash
# This is normal if you've run setup before
# To reset password:
psql -h 34.226.150.199 -U datamig -d datamiq
DELETE FROM users WHERE username = 'admin';
\q
python scripts/setup_admin.py
```

## 🎓 Features

✅ **Authentication & Authorization**
- Username/password login with JWT tokens
- Role-based access control (owner, admin, member)
- Workspace isolation
- Account locking after failed attempts

✅ **Multi-Tenant SaaS**
- Organization and workspace management
- Complete data isolation per workspace
- Resource quotas and rate limiting

✅ **Database Connections**
- Support for multiple database types
- Encrypted connection strings (AWS KMS)
- Connection testing and validation

✅ **Migration Assessment**
- Schema compatibility analysis
- Data type mapping
- Complexity estimation
- Detailed assessment reports

✅ **Migration Execution**
- Multiple migration pathways
- Real-time progress monitoring
- Error handling and retry logic
- Pause/resume functionality

✅ **Validation**
- Row count comparison
- Data integrity checks
- Sample data validation
- Constraint verification

✅ **Security**
- Encryption at rest and in transit
- AWS KMS integration
- Secrets Manager for credentials
- Audit logging

✅ **Performance**
- Redis caching with database fallback
- Connection pooling
- Batch processing
- Optimized queries

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
│   ├── models/                 # Database models
│   └── scripts/                # Setup scripts
├── frontend/
│   ├── src/
│   │   ├── components/         # React components
│   │   ├── pages/              # Page components
│   │   ├── contexts/           # React contexts
│   │   └── services/           # API services
│   └── package.json            # Node dependencies
├── docs/                       # Documentation
│   ├── api/                    # API documentation
│   ├── backend/                # Backend documentation
│   ├── frontend/               # Frontend documentation
│   ├── database/               # Database documentation
│   ├── quickstart/             # Quick start guides
│   ├── testing/                # Testing guides
│   ├── fixes/                  # Fix documentation
│   └── archive/                # Archived documents
├── .kiro/
│   └── steering/               # Development standards
├── ARCHITECTURE.md             # Architecture overview
├── DEPLOYMENT_GUIDE.md         # Deployment instructions
├── HOW_TO_RUN.md              # Detailed setup guide
├── SETUP_CHECKLIST.md         # Setup verification
├── TESTING_GUIDE.md           # Testing standards
└── README.md                  # This file
```

## 🔐 Default Credentials

**Username**: `admin`  
**Password**: `AdminPass123!`

(Configured in `backend/.env`)

## 📚 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/docs` | GET | API documentation |
| `/api/auth/login` | POST | User login |
| `/api/auth/logout` | POST | User logout |
| `/api/auth/me` | GET | Get current user |
| `/api/connections/*` | * | Connection management |
| `/api/assessments/*` | * | Assessment operations |
| `/api/migrations/*` | * | Migration management |

## 🛠️ Development Workflow

### Running Both Services

**Terminal 1 - Backend**:
```bash
cd backend
source .venv/bin/activate
python main.py
```

**Terminal 2 - Frontend**:
```bash
cd frontend
npm run dev
```

### Running Tests

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test
```

## 🚀 Production Deployment

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for:
- AWS deployment instructions
- Kubernetes configuration
- Docker containerization
- CI/CD pipeline setup
- Security best practices

## 💡 Development Principles

- Multi-tenant SaaS architecture with workspace isolation
- Microservices design for scalability
- Test-driven development with comprehensive test coverage
- Security-first approach with encryption
- Configuration-driven design using .env files
- Database-agnostic abstractions
- Always filter by workspace_id for data isolation

## 📝 Contributing

1. Follow the coding standards in `.kiro/steering/`
2. Write tests for all new features
3. Document all APIs and database changes
4. Ensure security best practices
5. Test in development before production

## 🆘 Need Help?

1. Check [HOW_TO_RUN.md](HOW_TO_RUN.md) for detailed troubleshooting
2. Check [SETUP_CHECKLIST.md](SETUP_CHECKLIST.md) for step-by-step verification
3. Review logs in terminal output
4. Verify `.env` configuration
5. Check API docs at http://localhost:8000/api/docs
6. See [docs/](docs/) for module-specific documentation

## 📄 License

Copyright © 2026 DataMIQ. All rights reserved.

---

**Last Updated**: February 15, 2026  
**Version**: 1.0.0
