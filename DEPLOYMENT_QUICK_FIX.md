# Quick Fix for App Runner Deployment

## Current Status
Container exits with code 1 - likely database connection or environment variable issue.

## Immediate Actions Required

### 1. Rebuild and Push Docker Image
```bash
# Navigate to backend
cd backend

# Build the updated image with diagnostics
docker build -t datamiq-backend .

# Tag for ECR (replace with your ECR URL)
docker tag datamiq-backend:latest <YOUR_ECR_REPO_URL>:latest

# Push to ECR
docker push <YOUR_ECR_REPO_URL>:latest
```

### 2. Verify Environment Variables in App Runner

Go to AWS App Runner console and verify these variables are set:

**Required Variables:**
```
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
APP_PORT=8080
```

**How to add/verify:**
1. AWS App Runner Console → Your Service
2. Configuration tab → Edit
3. Scroll to "Environment variables"
4. Add each variable if missing
5. Save changes (service will redeploy)

### 3. Check CloudWatch Logs

After redeployment, check logs:

1. AWS App Runner Console → Your Service
2. Logs tab
3. Look for these messages:

**Success indicators:**
```
✓ Database connection successful
✓ Migrations completed successfully
Starting uvicorn server on port 8080...
```

**Failure indicators:**
```
✗ Database connection failed: [error message]
ERROR: Missing required environment variables!
```

### 4. Database Connectivity Issues

If you see "Database connection failed", check:

#### A. Database is Running
```bash
# From your local machine or a server that can reach the DB
psql -h 34.226.150.199 -p 5432 -U datamig -d datamiq
```

#### B. Database Exists
```sql
-- Connect as superuser
psql -h 34.226.150.199 -p 5432 -U postgres

-- Check if database exists
\l

-- If not, create it
CREATE DATABASE datamiq;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE datamiq TO datamig;
```

#### C. Network Access
The database at 34.226.150.199 must allow connections from App Runner.

**Security Group Rules Needed:**
- Type: PostgreSQL
- Protocol: TCP
- Port: 5432
- Source: 0.0.0.0/0 (or specific App Runner IP ranges)

**To find App Runner IP ranges:**
```bash
# App Runner uses AWS IP ranges for the region
# Check: https://ip-ranges.amazonaws.com/ip-ranges.json
# Look for "service": "APPRUNNER" in your region
```

### 5. Alternative: Use Docker Deployment Instead of Source Code

If you're currently using "Source code repository" deployment:

1. Switch to "Container registry" deployment
2. Use ECR as the registry
3. This gives you more control over the build process

**Steps:**
1. Create ECR repository (if not exists)
2. Build and push image (see step 1 above)
3. Create new App Runner service
4. Choose "Container registry"
5. Select your ECR repository
6. Add environment variables
7. Deploy

## What Changed in the Dockerfile

The updated Dockerfile now:
1. **Tests database connectivity** before starting the app
2. **Prints all environment variables** (sanitized) for debugging
3. **Shows clear error messages** if something is wrong
4. **Fails fast** if database is unreachable
5. **Provides detailed logs** for troubleshooting

## Expected Startup Log Output

When successful, you should see:
```
=== DataMIQ Backend Startup ===
Time: Sat Feb 15 01:23:45 UTC 2026

Environment Configuration:
  APP_DB_HOST: 34.226.150.199
  APP_DB_PORT: 5432
  APP_DB_NAME: datamiq
  APP_DB_USER: datamig
  APP_DB_PASSWORD: ***SET***
  REDIS_HOST: 34.226.150.199
  REDIS_PORT: 6379
  JWT_SECRET_KEY: ***SET***
  APP_PORT: 8080

Testing database connectivity...
✓ Database connection successful

Running database migrations...
✓ Migrations completed successfully

Starting uvicorn server on port 8080...
=================================

INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8080
```

## Still Having Issues?

### Check These Common Problems:

1. **Wrong database credentials**
   - Verify APP_DB_USER and APP_DB_PASSWORD are correct
   - Try connecting manually from another machine

2. **Database doesn't exist**
   - Create the database: `CREATE DATABASE datamiq;`

3. **Network/firewall blocking**
   - Check security groups
   - Check network ACLs
   - Verify database is publicly accessible (if intended)

4. **App Runner service role missing permissions**
   - If using Secrets Manager, verify IAM role has access
   - If using ECR, verify IAM role can pull images

5. **Port mismatch**
   - App Runner expects port 8080
   - Verify APP_PORT=8080 is set
   - Dockerfile exposes port 8080

## Contact Points

If you need more help, provide:
1. CloudWatch logs (full startup output)
2. App Runner service configuration (sanitized)
3. Database connection test results
4. Any error messages

---

**Last Updated**: February 15, 2026  
**Status**: Dockerfile updated with diagnostics - ready for rebuild and redeploy
