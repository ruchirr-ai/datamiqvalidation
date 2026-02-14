---
inclusion: fileMatch
fileMatchPattern: '**/*.py'
---

# Backend Development Standards

## Framework: FastAPI + Python

### Package Management
- **Use `uv` for all Python package management** (not pip or pip-tools)
- Create virtual environments with: `uv venv`
- Install dependencies with: `uv pip install -r requirements.txt`
- Add new packages with: `uv pip install <package>`
- Virtual environment location: `.venv/` (not `venv/`)
- Always activate virtual environment: `source .venv/bin/activate`

### Code Organization
- Use modular structure with clear separation by feature/module
- Each module should have its own router, services, and models
- Keep business logic in service layers, not in route handlers

### API Design
- Follow RESTful conventions
- Use Pydantic models for request/response validation
- Include proper HTTP status codes
- Implement consistent error responses
- Version APIs appropriately (e.g., `/api/v1/`)

### Database Abstractions
- Create database-agnostic interfaces for migration sources/targets
- Use adapter pattern for different database types
- PostgreSQL as application backend (all app data in DB)
- Implement connection pooling (SQLAlchemy + pgbouncer)
- Handle transactions properly
- Store all state in PostgreSQL, no static files

### Caching Layer
- Use Redis as primary cache layer for UI acceleration
- Implement cache-aside pattern with database fallback
- If Redis is unavailable, fallback to PostgreSQL
- Cache frequently accessed data with appropriate TTL
- Never let Redis failures break the application
- Use AWS ElastiCache for production

### Error Handling
- Use custom exception classes
- Implement global exception handlers
- Log errors with context
- Return user-friendly error messages

### Testing
- Write tests for EVERY feature and API endpoint
- Include sample payloads in all tests
- Write unit tests for services
- Write integration tests for API endpoints
- Use property-based testing for data transformations
- Mock external database connections in tests
- Minimum 80% code coverage
- Test success cases, error cases, and edge cases

### Code Style
- Follow PEP 8
- Use type hints consistently
- Document functions with docstrings
- Keep functions focused and small

### Configuration
- All configuration via .env files
- Use python-dotenv for loading
- Validate configuration on startup
- Never hardcode credentials or settings

### Security
- Encrypt all database connection strings using KMS
- Store encrypted keys in AWS Secrets Manager
- Use IAM roles, not access keys
- Implement proper input validation
- Follow AWS security best practices

### Logging
- Use Python logging module with structured logs
- Log to PostgreSQL database
- Send logs to CloudWatch
- Never log sensitive data
- Include request IDs for tracing
