---
inclusion: always
---

# Configuration Management

## Configuration-Driven Design
All application behavior must be configurable via environment variables and .env files.

### Environment Files
- Use `.env` files for all configuration
- Never hardcode configuration values
- Support multiple environments (dev, staging, prod)
- Use `.env.example` as template with dummy values

### Configuration Categories
- Database connection strings
- AWS service endpoints and regions
- KMS key IDs
- Secret Manager secret names
- Application settings (timeouts, batch sizes, etc.)
- Logging levels and destinations
- Feature flags

### Loading Configuration
- Use python-dotenv or similar for loading .env files
- Validate required configuration on startup
- Fail fast if critical configuration is missing
- Log configuration loading (without sensitive values)

### Configuration Security
- Never commit .env files to version control
- Add .env to .gitignore
- Use .env.example for documentation
- Rotate credentials regularly
- Use AWS Secrets Manager for sensitive values when possible
