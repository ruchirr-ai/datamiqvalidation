# AWS App Runner Setup with Docker

## Problem Solved
The `apprunner.yaml` configuration file approach was causing "runtime version not supported" errors. This guide uses Docker containers instead, which is more reliable and gives you full control over the Python version.

## Prerequisites
- AWS Account with App Runner access
- GitHub repository: `https://github.com/shellkodelabs/datamiq.git`
- Branch: `feature/bq_rs`

## Step-by-Step Setup

### Step 1: Create App Runner Service

1. Go to **AWS Console** → **App Runner**
2. Click **"Create service"**

### Step 2: Source Configuration

**Repository:**
- **Source**: Source code repository
- **Connect to GitHub**: 
  - Click "Add new"
  - Authorize AWS Connector for GitHub
  - Select repository: `shellkodelabs/datamiq`
  - Branch: `feature/bq_rs`
- **Deployment trigger**: Automatic

**Build settings:**
- **Configuration source**: Configure all settings here ✅ (NOT "Use a configuration file")

### Step 3: Build Configuration

**Build command:**
```bash
cd backend && docker build -t datamiq-backend .
```

**Start command:**
```bash
docker run -p 8080:8080 \
  -e APP_DB_HOST=$APP_DB_HOST \
  -e APP_DB_PORT=$APP_DB_PORT \
  -e APP_DB_NAME=$APP_DB_NAME \
  -e APP_DB_USER=$APP_DB_USER \
  -e APP_DB_PASSWORD=$APP_DB_PASSWORD \
  -e JWT_SECRET_KEY=$JWT_SECRET_KEY \
  -e REDIS_HOST=$REDIS_HOST \
  -e REDIS_PORT=$REDIS_PORT \
  -e REDIS_ENABLED=$REDIS_ENABLED \
  -e ADMIN_USER=$ADMIN_USER \
  -e ADMIN_PASSWORD=$ADMIN_PASSWORD \
  -e CORS_ORIGINS=$CORS_ORIGINS \
  datamiq-backend
```

**Port:** `8080`

### Step 4: Service Settings

**Service name:** `datamiq-backend`

**Virtual CPU & Memory:**
- CPU: 1 vCPU (or 2 for production)
- Memory: 2 GB (or 4 for production)

**Environment variables:** (Add each one)

```
APP_PORT=8080
APP_DB_HOST=34.226.150.199
APP_DB_PORT=5432
APP_DB_NAME=datamiq
APP_DB_USER=datamig
APP_DB_PASSWORD=datamig
JWT_SECRET_KEY=change_me_in_production_use_long_random_string
REDIS_HOST=34.226.150.199
REDIS_PORT=6379
REDIS_ENABLED=true
ADMIN_USER=admin
ADMIN_PASSWORD=AdminPass123!
CORS_ORIGINS=*
```

### Step 5: Auto Scaling

- **Min instances**: 1
- **Max instances**: 3
- **Concurrency**: 100

### Step 6: Health Check

- **Protocol**: HTTP
- **Path**: `/health`
- **Interval**: 10 seconds
- **Timeout**: 5 seconds
- **Healthy threshold**: 1
- **Unhealthy threshold**: 5

### Step 7: Create & Deploy

Click **"Create & deploy"** and wait 5-10 minutes.

## Alternative: Use ECR (Recommended for Production)

For better control and faster deployments, push your Docker image to Amazon ECR:

### Step 1: Create ECR Repository

```bash
aws ecr create-repository --repository-name datamiq-backend --region us-east-1
```

### Step 2: Build and Push Image

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build image
cd backend
docker build -t datamiq-backend .

# Tag image
docker tag datamiq-backend:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/datamiq-backend:latest

# Push to ECR
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/datamiq-backend:latest
```

### Step 3: Create App Runner Service from ECR

1. Go to App Runner → Create service
2. **Source**: Container registry
3. **Provider**: Amazon ECR
4. **Container image URI**: `<account-id>.dkr.ecr.us-east-1.amazonaws.com/datamiq-backend:latest`
5. **Deployment trigger**: Automatic (on new image push)
6. **Port**: 8080
7. Add environment variables
8. Create service

## Dockerfile Explanation

The `backend/Dockerfile` is configured for App Runner:

```dockerfile
FROM python:3.9-slim          # Uses Python 3.9 (supported)
WORKDIR /app
# Install dependencies
RUN apt-get update && apt-get install -y gcc g++ libpq-dev curl
COPY requirements.txt requirements_bq_redshift.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements_bq_redshift.txt
COPY . .
ENV PYTHONUNBUFFERED=1
ENV APP_PORT=8080
EXPOSE 8080
# Run migrations and start app
CMD alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8080
```

## Verification

After deployment:

```bash
# Test health endpoint
curl https://your-app-runner-url.awsapprunner.com/health

# Expected response:
# {"status":"healthy","service":"datamiq-api","version":"1.0.0"}

# Test login
curl -X POST https://your-app-runner-url.awsapprunner.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"AdminPass123!"}'
```

## Troubleshooting

### Build Fails
- Check CloudWatch Logs for build errors
- Verify Dockerfile syntax
- Ensure all dependencies in requirements.txt

### Container Won't Start
- Check environment variables are set
- Verify database connection
- Check CloudWatch Logs for startup errors

### Health Check Fails
- Verify `/health` endpoint works
- Check port 8080 is exposed
- Ensure app starts within timeout

## Why Docker Approach Works

1. **Full Control**: You control the exact Python version (3.9)
2. **No Runtime Issues**: Docker handles all dependencies
3. **Consistent**: Same image works locally and in App Runner
4. **Portable**: Easy to move to ECS/EKS later if needed

## Cost Estimate

- **App Runner**: ~$46/month (1 vCPU, 2 GB)
- **ECR Storage**: ~$0.10/month (for Docker images)
- **Data Transfer**: Minimal for API traffic

## Next Steps

1. Deploy using this Docker approach
2. Test all endpoints
3. Set up custom domain
4. Configure production secrets in AWS Secrets Manager
5. Set up monitoring and alerts

---

**Last Updated**: February 15, 2026  
**Status**: Docker-based deployment (no apprunner.yaml needed)
