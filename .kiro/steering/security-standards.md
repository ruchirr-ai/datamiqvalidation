---
inclusion: always
---

# Security Standards

## Encryption & Key Management

### Database Connection Strings
All database connection strings (including passwords) MUST be encrypted using AWS KMS.

**Encryption Flow**:
1. Generate a data encryption key using AWS KMS
2. Store the encrypted data key in AWS Secrets Manager
3. Use KMS to decrypt the data key when needed
4. Use the decrypted data key to encrypt/decrypt connection strings

**Configuration**:
- KMS Key ID: from .env (`KMS_KEY_ID`)
- Secret Manager Secret Name: from .env (`SECRET_MANAGER_SECRET_NAME`)
- AWS Region: from .env (`AWS_REGION`)

### Setup Script Requirements
Create a setup script (`setup.py` or `setup.sh`) that:
1. Creates KMS data encryption key
2. Stores encrypted key in AWS Secrets Manager
3. Validates AWS permissions
4. Initializes database schema
5. Runs on first deployment or environment setup

### Encryption Best Practices
- Use envelope encryption (KMS + data keys)
- Rotate data keys periodically
- Use separate KMS keys per environment
- Never log decrypted values
- Implement key caching with TTL
- Use AWS KMS key policies for access control

## Application Security

### Authentication & Authorization
- Implement proper authentication for all API endpoints
- Use JWT tokens or AWS Cognito
- Implement role-based access control (RBAC)
- Validate all user inputs

### API Security
- Use HTTPS only (TLS 1.2+)
- Implement rate limiting
- Use CORS properly
- Validate content types
- Sanitize all inputs
- Implement request signing for sensitive operations

### Data Security
- Encrypt data at rest (database encryption)
- Encrypt data in transit (TLS)
- Encrypt sensitive fields in database
- Implement data masking for logs
- Use parameterized queries (prevent SQL injection)

### AWS Security Best Practices
- Use IAM roles, not access keys
- Follow principle of least privilege
- Enable CloudTrail for audit logging
- Use VPC for network isolation
- Enable AWS GuardDuty
- Use Security Groups and NACLs properly
- Enable AWS Config for compliance
- Use AWS WAF for web application firewall

### Secrets Management
- Never hardcode secrets
- Use AWS Secrets Manager for all credentials
- Rotate secrets regularly
- Use IAM roles for service-to-service auth
- Implement secret versioning

### Dependency Security
- Regularly update dependencies
- Use dependency scanning tools
- Pin dependency versions
- Review security advisories
