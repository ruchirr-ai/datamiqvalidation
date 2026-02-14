# AWS App Runner Setup Guide

This guide will help you deploy DataMIQ backend to AWS App Runner from your GitHub repository.

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **GitHub Repository**: `https://github.com/shellkodelabs/datamiq.git`
3. **AWS CLI** installed and configured (optional but recommended)
4. **Database**: PostgreSQL instance accessible from AWS (RDS recommended)
5. **Redis**: ElastiCache Redis instance (optional, app works without it)

## Architecture Overview

```
GitHub (feature/bq_rs branch)
    ↓ (Auto-deploy on push)
AWS App Runner
    ↓
Backend API (Python/FastAPI)
    ↓
RDS PostgreSQL + ElastiCache Redis
```

## Step 1: Prepare Environment Variables

Before setting up App Runner, prepare these environment variables:

### Required Variables
```bash
# Database Configuration
APP_DB_HOST=your-rds-endpoint.rds.amazonaws.com
APP_DB_PORT=5432
APP_DB_NAME=datamiq
APP_DB_USER=datamiq
APP_DB_PASSWORD=your_secure_password

# Application Configuration
APP_PORT=8080
JWT_SECRET_KEY=your_long_random_secret_key_here
CORS_ORIGINS=https://your-frontend-domain.com

# Admin User
ADMIN_USER=admin
ADMIN_PASSWORD=AdminPass123!

# Redis (Optional)
REDIS_HOST=your-elasticache-endpoint.cache.amazonaws.com
REDIS_PORT=6379
REDIS_ENABLED=true

# AWS Services (if using)
AWS_REGION=us-east-1
KMS_KEY_ID=your-kms-key-id
SECRET_MANAGER_SECRET_NAME=datamiq-secrets
```

### Optional Variables
```bash
# Logging
LOG_LEVEL=INFO

# Feature Flags
ENABLE_BACKGROUND_TASKS=true
```

## Step 2: Set Up AWS App Runner via AWS Console

### 2.1 Navigate to App Runner
1. Log in to AWS Console
2. Search for "App Runner" in the services search bar
3. Click "Create service"

### 2.2 Configure Source and Deployment

**Source:**
- **Repository type**: Source code repository
- **Connect to GitHub**: 
  - Click "Add new"
  - Authorize AWS Connector for GitHub
  - Select your GitHub account
  - Choose repository: `shellkodelabs/datamiq`
  - Choose branch: `feature/bq_rs`
- **Deployment trigger**: Automatic (deploys on every push)

**Build settings:**
- **Configuration file**: Use a configuration file
- **Configuration file**: `apprunner.yaml` (already created in your repo)

### 2.3 Configure Service

**Service name**: `datamiq-backend`

**Virtual CPU & memory**:
- CPU: 1 vCPU (or 2 vCPU for production)
- Memory: 2 GB (or 4 GB for production)

**Environment variables**:
Click "Add environment variable" for each variable from Step 1.

**Important**: For sensitive values like passwords, use AWS Secrets Manager:
- Store secrets in AWS Secrets Manager
- Reference them in App Runner using ARN

### 2.4 Configure Auto Scaling

**Auto scaling configuration**:
- **Min instances**: 1
- **Max instances**: 3 (adjust based on load)
- **Concurrency**: 100 (requests per instance)

### 2.5 Configure Health Check

**Health check**:
- **Protocol**: HTTP
- **Path**: `/health`
- **Interval**: 10 seconds
- **Timeout**: 5 seconds
- **Healthy threshold**: 1
- **Unhealthy threshold**: 5

### 2.6 Configure Security

**IAM role**:
- Create a new service role or use existing
- Ensure it has permissions for:
  - ECR (if using custom images)
  - Secrets Manager (if using secrets)
  - CloudWatch Logs
  - KMS (if using encryption)

### 2.7 Configure Networking (Optional)

If your database is in a VPC:
- **VPC connector**: Create or select existing
- **Subnets**: Select private subnets
- **Security groups**: Allow outbound to RDS and Redis

### 2.8 Review and Create

1. Review all settings
2. Click "Create & deploy"
3. Wait for deployment (5-10 minutes)

## Step 3: Set Up Database (RDS PostgreSQL)

If you don't have RDS set up yet:

### 3.1 Create RDS Instance

```bash
# Via AWS Console:
1. Go to RDS → Create database
2. Choose PostgreSQL
3. Template: Production or Dev/Test
4. DB instance identifier: datamiq-db
5. Master username: datamiq
6. Master password: <secure-password>
7. DB instance class: db.t3.micro (or larger)
8. Storage: 20 GB (with autoscaling)
9. VPC: Same as App Runner (if using VPC connector)
10. Public access: No (if using VPC connector)
11. Create database
```

### 3.2 Configure Security Group

Allow inbound traffic from App Runner:
- Type: PostgreSQL
- Port: 5432
- Source: App Runner security group (or 0.0.0.0/0 if public)

### 3.3 Initialize Database

Once RDS is ready, run migrations:

```bash
# Option 1: From local machine (if RDS is publicly accessible)
cd backend
export APP_DB_HOST=your-rds-endpoint.rds.amazonaws.com
export APP_DB_PORT=5432
export APP_DB_NAME=datamiq
export APP_DB_USER=datamiq
export APP_DB_PASSWORD=your_password
alembic upgrade head
python scripts/setup_admin.py

# Option 2: Via App Runner (automatic on first deploy)
# Migrations run automatically via apprunner.yaml build commands
```

## Step 4: Set Up Redis (ElastiCache) - Optional

### 4.1 Create ElastiCache Redis Cluster

```bash
# Via AWS Console:
1. Go to ElastiCache → Create
2. Choose Redis
3. Cluster mode: Disabled (for simplicity)
4. Name: datamiq-redis
5. Node type: cache.t3.micro (or larger)
6. Number of replicas: 0 (or 1-2 for HA)
7. Subnet group: Same VPC as App Runner
8. Security group: Allow inbound from App Runner
9. Create
```

### 4.2 Configure Security Group

Allow inbound traffic from App Runner:
- Type: Custom TCP
- Port: 6379
- Source: App Runner security group

## Step 5: Configure Secrets Manager (Recommended)

Store sensitive credentials in AWS Secrets Manager:

### 5.1 Create Secret

```bash
# Via AWS Console:
1. Go to Secrets Manager → Store a new secret
2. Secret type: Other type of secret
3. Key/value pairs:
   - APP_DB_PASSWORD: your_db_password
   - JWT_SECRET_KEY: your_jwt_secret
   - ADMIN_PASSWORD: your_admin_password
4. Secret name: datamiq/backend/credentials
5. Create secret
```

### 5.2 Update App Runner Environment Variables

Instead of plain text passwords, use secret ARNs:

```bash
# In App Runner environment variables:
APP_DB_PASSWORD=arn:aws:secretsmanager:region:account:secret:datamiq/backend/credentials:APP_DB_PASSWORD::
JWT_SECRET_KEY=arn:aws:secretsmanager:region:account:secret:datamiq/backend/credentials:JWT_SECRET_KEY::
```

### 5.3 Update IAM Role

Add Secrets Manager permissions to App Runner service role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:region:account:secret:datamiq/backend/credentials*"
    }
  ]
}
```

## Step 6: Configure Custom Domain (Optional)

### 6.1 Add Custom Domain in App Runner

1. Go to your App Runner service
2. Click "Custom domains" tab
3. Click "Link domain"
4. Enter your domain: `api.yourdomain.com`
5. Follow DNS configuration instructions

### 6.2 Update DNS Records

Add CNAME record in your DNS provider:
```
api.yourdomain.com → your-app-runner-url.awsapprunner.com
```

### 6.3 Update CORS Origins

Update App Runner environment variable:
```bash
CORS_ORIGINS=https://yourdomain.com,https://api.yourdomain.com
```

## Step 7: Verify Deployment

### 7.1 Check Service Status

1. Go to App Runner console
2. Check service status: Should be "Running"
3. Check logs in CloudWatch Logs

### 7.2 Test Health Endpoint

```bash
curl https://your-app-runner-url.awsapprunner.com/health

# Expected response:
# {"status":"healthy","service":"datamiq-api","version":"1.0.0"}
```

### 7.3 Test API Endpoints

```bash
# Test login
curl -X POST https://your-app-runner-url.awsapprunner.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"AdminPass123!"}'

# Should return access token
```

### 7.4 Check API Documentation

Open in browser:
```
https://your-app-runner-url.awsapprunner.com/api/docs
```

## Step 8: Set Up Continuous Deployment

App Runner automatically deploys when you push to the `feature/bq_rs` branch:

```bash
# Make changes locally
git add .
git commit -m "Update feature"
git push origin feature/bq_rs

# App Runner will automatically:
# 1. Detect the push
# 2. Pull latest code
# 3. Run build commands
# 4. Deploy new version
# 5. Health check
# 6. Route traffic to new version
```

## Step 9: Monitor and Troubleshoot

### 9.1 View Logs

**Via AWS Console:**
1. Go to App Runner service
2. Click "Logs" tab
3. View deployment logs and application logs

**Via CloudWatch:**
1. Go to CloudWatch → Log groups
2. Find `/aws/apprunner/datamiq-backend/...`
3. View log streams

### 9.2 Common Issues

**Issue: Deployment fails**
- Check build logs in App Runner console
- Verify `apprunner.yaml` syntax
- Ensure all dependencies in `requirements.txt`

**Issue: Health check fails**
- Verify `/health` endpoint works
- Check application logs for errors
- Ensure port 8080 is configured correctly

**Issue: Database connection fails**
- Verify RDS endpoint and credentials
- Check security group rules
- Ensure VPC connector is configured (if using private RDS)

**Issue: Environment variables not working**
- Verify all required variables are set
- Check for typos in variable names
- Restart service after updating variables

### 9.3 View Metrics

1. Go to App Runner service
2. Click "Metrics" tab
3. View:
   - Request count
   - Response time
   - CPU utilization
   - Memory utilization
   - Active instances

## Step 10: Production Checklist

Before going to production:

- [ ] Use RDS Multi-AZ for high availability
- [ ] Enable RDS automated backups
- [ ] Use ElastiCache Redis with replication
- [ ] Store all secrets in Secrets Manager
- [ ] Enable AWS WAF for API protection
- [ ] Set up CloudWatch alarms for errors
- [ ] Configure auto-scaling based on load
- [ ] Use custom domain with SSL
- [ ] Enable CloudTrail for audit logging
- [ ] Set up VPC for network isolation
- [ ] Configure backup and disaster recovery
- [ ] Test failover scenarios
- [ ] Document runbooks for incidents

## Cost Estimation

**App Runner:**
- 1 vCPU, 2 GB RAM: ~$0.064/hour = ~$46/month
- 2 vCPU, 4 GB RAM: ~$0.128/hour = ~$92/month

**RDS PostgreSQL:**
- db.t3.micro: ~$15/month
- db.t3.small: ~$30/month

**ElastiCache Redis:**
- cache.t3.micro: ~$12/month
- cache.t3.small: ~$24/month

**Total estimated cost:**
- Development: ~$73/month
- Production: ~$146/month

## Alternative: Deploy via AWS CLI

If you prefer CLI over console:

```bash
# Create App Runner service
aws apprunner create-service \
  --service-name datamiq-backend \
  --source-configuration '{
    "AuthenticationConfiguration": {
      "ConnectionArn": "arn:aws:apprunner:region:account:connection/github-connection"
    },
    "AutoDeploymentsEnabled": true,
    "CodeRepository": {
      "RepositoryUrl": "https://github.com/shellkodelabs/datamiq",
      "SourceCodeVersion": {
        "Type": "BRANCH",
        "Value": "feature/bq_rs"
      },
      "CodeConfiguration": {
        "ConfigurationSource": "API",
        "CodeConfigurationValues": {
          "Runtime": "PYTHON_3",
          "BuildCommand": "cd backend && pip install -r requirements.txt && alembic upgrade head",
          "StartCommand": "cd backend && uvicorn main:app --host 0.0.0.0 --port 8080",
          "Port": "8080",
          "RuntimeEnvironmentVariables": {
            "APP_DB_HOST": "your-rds-endpoint.rds.amazonaws.com",
            "APP_DB_PORT": "5432",
            "APP_DB_NAME": "datamiq",
            "APP_PORT": "8080"
          }
        }
      }
    }
  }' \
  --instance-configuration '{
    "Cpu": "1 vCPU",
    "Memory": "2 GB"
  }' \
  --health-check-configuration '{
    "Protocol": "HTTP",
    "Path": "/health",
    "Interval": 10,
    "Timeout": 5,
    "HealthyThreshold": 1,
    "UnhealthyThreshold": 5
  }'
```

## Support and Resources

- **AWS App Runner Documentation**: https://docs.aws.amazon.com/apprunner/
- **GitHub Repository**: https://github.com/shellkodelabs/datamiq
- **Project Documentation**: See `docs/` folder in repository

## Next Steps

1. Set up frontend deployment (S3 + CloudFront or Amplify)
2. Configure CI/CD pipeline with GitHub Actions
3. Set up monitoring and alerting
4. Implement backup and disaster recovery
5. Configure staging environment

---

**Last Updated**: February 15, 2026  
**Version**: 1.0.0
