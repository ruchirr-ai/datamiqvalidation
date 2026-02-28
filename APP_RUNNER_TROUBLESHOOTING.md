# AWS App Runner Troubleshooting Guide

## Current Issue: Container Exit Code 1

### Diagnosis
The container is starting but exiting with code 1, which typically means:
1. Database connection failure
2. Missing environment variables
3. Migration errors
4. Application startup errors

### Updated Dockerfile
I've updated the Dockerfile with comprehensive diagnostics that will:
- Print all environment variables (sanitized)
- Test database connectivity before starting
- Show clear error messages if connection fails
- Run migrations with better error handling
- Provide detailed startup logs

### Next Steps

#### 1. Rebuild Docker Image
```bash
cd backend
docker build -t datamiq-backend .
```

#### 2. Push to ECR
```bash
# Tag the image
docker tag datamiq-backend:latest <your-ecr-repo-url>:latest

# Push to ECR
docker push <your-ecr-repo-url>:latest
```

#### 3. Check CloudWatch Logs
After App Runner deploys the new image, check CloudWatch Logs for:
- Environment variable values (to confirm they're set)
- Database connection test results
- Specific error messages

**To access CloudWatch Logs:**
1. Go to AWS App Runner console
2. Select your service
3. Click "Logs" tab
4. Look for the startup messages

#### 4. Common Issues and Solutions

**Issue: Database connection timeout**
- **Cause**: App Runner cannot reach database at 34.226.150.199:5432
- **Solution**: Check security group rules on the database to allow App Runner IP ranges

**Issue: Missing environment variables**
- **Cause**: Variables not set in App Runner configuration
- **Solution**: See "Solution 3: Add Variables After Service Creation" below

**Issue: Database doesn't exist**
- **Cause**: Database "datamiq" not created
- **Solution**: Connect to PostgreSQL and create database:
  ```sql
  CREATE DATABASE datamiq;
  ```

**Issue: User doesn't have permissions**
- **Cause**: User "datamig" lacks permissions
- **Solution**: Grant permissions:
  ```sql
  GRANT ALL PRIVILEGES ON DATABASE datamiq TO datamig;
  ```

## Issue: Unable to Add Environment Variables

If you're having trouble adding environment variables in the AWS App Runner console, here are several solutions:

### Solution 1: Use apprunner.yaml (Recommended - Already Done!)

I've updated the `apprunner.yaml` file to include all environment variables directly. This means you don't need to add them manually in the console.

**What's included in apprunner.yaml:**
- Database configuration (PostgreSQL)
- Redis configuration
- JWT secret
- Admin credentials
- CORS settings
- Application port

**Action Required:** Just push the updated code and App Runner will use these values automatically.

```bash
git add apprunner.yaml
git commit -m "Add environment variables to apprunner.yaml"
git push origin feature/bq_rs
```

### Solution 2: Add Variables During Service Creation

If you're creating a new service:

1. **Step 1**: In the "Configure service" section
2. **Step 2**: Scroll down to "Environment variables"
3. **Step 3**: Click "Add environment variable"
4. **Step 4**: Enter:
   - **Key**: `APP_DB_HOST`
   - **Value**: `34.226.150.199`
5. **Step 5**: Click "Add environment variable" again for each variable
6. **Step 6**: Repeat for all variables

**Common Issue**: The "Add environment variable" button might be at the bottom of a scrollable section. Make sure to scroll down in the configuration panel.

### Solution 3: Add Variables After Service Creation

If your service is already created:

1. Go to AWS App Runner console
2. Select your service (`datamiq-backend`)
3. Click **"Configuration"** tab
4. Click **"Edit"** button
5. Scroll to **"Environment variables"** section
6. Click **"Add environment variable"**
7. Add each variable one by one
8. Click **"Save changes"**
9. Service will automatically redeploy with new variables

### Solution 4: Use AWS Secrets Manager (For Sensitive Data)

For production, it's better to use AWS Secrets Manager for sensitive values:

#### Step 1: Create Secret in AWS Secrets Manager

1. Go to AWS Secrets Manager
2. Click "Store a new secret"
3. Choose "Other type of secret"
4. Add key-value pairs:
   ```
   APP_DB_PASSWORD: datamig
   JWT_SECRET_KEY: your_secret_key
   ADMIN_PASSWORD: AdminPass123!
   ```
5. Name it: `datamiq/backend/credentials`
6. Create secret

#### Step 2: Reference in App Runner

In App Runner environment variables, use the secret ARN:

```
APP_DB_PASSWORD=arn:aws:secretsmanager:us-east-1:123456789:secret:datamiq/backend/credentials:APP_DB_PASSWORD::
```

#### Step 3: Update IAM Role

Add this policy to your App Runner service role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:*:*:secret:datamiq/backend/credentials*"
    }
  ]
}
```

### Solution 5: Use AWS CLI

If the console isn't working, use AWS CLI:

```bash
# Update service with environment variables
aws apprunner update-service \
  --service-arn "arn:aws:apprunner:region:account:service/datamiq-backend/xxxxx" \
  --source-configuration '{
    "CodeRepository": {
      "CodeConfiguration": {
        "CodeConfigurationValues": {
          "RuntimeEnvironmentVariables": {
            "APP_DB_HOST": "34.226.150.199",
            "APP_DB_PORT": "5432",
            "APP_DB_NAME": "datamiq",
            "APP_DB_USER": "datamig",
            "APP_DB_PASSWORD": "datamig",
            "JWT_SECRET_KEY": "change_me_in_production",
            "REDIS_HOST": "34.226.150.199",
            "REDIS_PORT": "6379",
            "REDIS_ENABLED": "true",
            "ADMIN_USER": "admin",
            "ADMIN_PASSWORD": "AdminPass123!",
            "CORS_ORIGINS": "*",
            "APP_PORT": "8080"
          }
        }
      }
    }
  }'
```

### Solution 6: Check Browser Console

Sometimes the UI has issues. Try:

1. **Clear browser cache**: Ctrl+Shift+Delete (or Cmd+Shift+Delete on Mac)
2. **Try different browser**: Chrome, Firefox, or Edge
3. **Disable browser extensions**: Ad blockers might interfere
4. **Check browser console**: Press F12 and look for JavaScript errors

### Solution 7: Verify IAM Permissions

Make sure your AWS user has these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "apprunner:CreateService",
        "apprunner:UpdateService",
        "apprunner:DescribeService"
      ],
      "Resource": "*"
    }
  ]
}
```

## Current Configuration

Since I've updated `apprunner.yaml`, your environment variables are now:

```yaml
env:
  - name: APP_PORT
    value: "8080"
  - name: PYTHONUNBUFFERED
    value: "1"
  - name: APP_DB_HOST
    value: "34.226.150.199"
  - name: APP_DB_PORT
    value: "5432"
  - name: APP_DB_NAME
    value: "datamiq"
  - name: APP_DB_USER
    value: "datamig"
  - name: APP_DB_PASSWORD
    value: "datamig"
  - name: JWT_SECRET_KEY
    value: "change_me_in_production_use_long_random_string"
  - name: REDIS_HOST
    value: "34.226.150.199"
  - name: REDIS_PORT
    value: "6379"
  - name: REDIS_ENABLED
    value: "true"
  - name: ADMIN_USER
    value: "admin"
  - name: ADMIN_PASSWORD
    value: "AdminPass123!"
  - name: CORS_ORIGINS
    value: "*"
```

## Next Steps

### Option A: Use apprunner.yaml (Easiest)

1. The file is already updated with all variables
2. Just create the App Runner service
3. Choose "Use a configuration file"
4. App Runner will read variables from `apprunner.yaml`
5. No need to add variables manually!

### Option B: Override in Console

If you want to override specific values:

1. Create service with `apprunner.yaml`
2. After creation, go to Configuration → Edit
3. Add/override only the variables you want to change
4. Console variables override `apprunner.yaml` values

## Verification

After deployment, verify environment variables are loaded:

```bash
# Check if service is running
curl https://your-app-runner-url.awsapprunner.com/health

# Should return:
# {"status":"healthy","service":"datamiq-api","version":"1.0.0"}
```

## Common Errors and Solutions

### Error: "Configuration file not found"
**Solution**: Make sure `apprunner.yaml` is in the root of your repository (not in a subdirectory).

### Error: "Invalid configuration file"
**Solution**: Check YAML syntax. Use a YAML validator online.

### Error: "Environment variable not set"
**Solution**: Check the application logs in CloudWatch to see which variable is missing.

### Error: "Database connection failed"
**Solution**: 
- Verify `APP_DB_HOST` is correct
- Check if RDS security group allows connections from App Runner
- Verify database credentials

## Support

If you're still having issues:

1. **Check AWS Service Health**: https://status.aws.amazon.com/
2. **AWS Support**: Open a support ticket if you have a support plan
3. **AWS Forums**: https://forums.aws.amazon.com/forum.jspa?forumID=322
4. **Check CloudWatch Logs**: Look for deployment errors

## Security Note

⚠️ **Important**: The current `apprunner.yaml` contains actual credentials. For production:

1. Move sensitive values to AWS Secrets Manager
2. Use IAM roles for AWS service access
3. Rotate credentials regularly
4. Enable encryption at rest and in transit
5. Use VPC for network isolation

---

**Last Updated**: February 15, 2026  
**Status**: apprunner.yaml updated with all environment variables
