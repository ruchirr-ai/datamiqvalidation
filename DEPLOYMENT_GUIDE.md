# BigQuery to Redshift Migration Tool - Deployment Guide

## Overview

This guide covers deploying the BigQuery to Redshift migration tool to AWS with proper networking, security, and high availability.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          AWS Cloud                               │
│                                                                   │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │   Route 53   │──────│     ALB      │──────│   CloudFront │  │
│  └──────────────┘      └──────────────┘      └──────────────┘  │
│                               │                                   │
│                               ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    VPC (10.0.0.0/16)                     │   │
│  │                                                           │   │
│  │  ┌──────────────────┐         ┌──────────────────┐     │   │
│  │  │  Public Subnet   │         │  Public Subnet   │     │   │
│  │  │   (AZ-1)         │         │   (AZ-2)         │     │   │
│  │  └──────────────────┘         └──────────────────┘     │   │
│  │           │                             │                │   │
│  │  ┌──────────────────┐         ┌──────────────────┐     │   │
│  │  │ Private Subnet   │         │ Private Subnet   │     │   │
│  │  │   (AZ-1)         │         │   (AZ-2)         │     │   │
│  │  │                  │         │                  │     │   │
│  │  │  ┌────────────┐  │         │  ┌────────────┐  │     │   │
│  │  │  │ ECS Tasks  │  │         │  │ ECS Tasks  │  │     │   │
│  │  │  │ (Backend)  │  │         │  │ (Backend)  │  │     │   │
│  │  │  └────────────┘  │         │  └────────────┘  │     │   │
│  │  │                  │         │                  │     │   │
│  │  │  ┌────────────┐  │         │  ┌────────────┐  │     │   │
│  │  │  │ Background │  │         │  │ Background │  │     │   │
│  │  │  │  Worker    │  │         │  │  Worker    │  │     │   │
│  │  │  └────────────┘  │         │  └────────────┘  │     │   │
│  │  └──────────────────┘         └──────────────────┘     │   │
│  │           │                             │                │   │
│  │  ┌──────────────────┐         ┌──────────────────┐     │   │
│  │  │   RDS Multi-AZ   │◄────────┤  ElastiCache     │     │   │
│  │  │   PostgreSQL     │         │  Redis Cluster   │     │   │
│  │  └──────────────────┘         └──────────────────┘     │   │
│  │                                                           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                               │                                   │
│                               ▼                                   │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │   Redshift   │      │      S3      │      │     KMS      │  │
│  │   Cluster    │      │   Buckets    │      │   Keys       │  │
│  └──────────────┘      └──────────────┘      └──────────────┘  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                               │
                               │ VPN Tunnel
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                         GCP Cloud                                │
│                                                                   │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │   BigQuery   │      │     GCS      │      │   Storage    │  │
│  │   Datasets   │      │   Buckets    │      │   Transfer   │  │
│  └──────────────┘      └──────────────┘      └──────────────┘  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Prerequisites

### AWS Account Setup
- AWS account with admin access
- AWS CLI configured
- Terraform installed (>= 1.0)
- Docker installed

### GCP Account Setup
- GCP project with billing enabled
- gcloud CLI configured
- BigQuery API enabled
- Storage Transfer API enabled

### Required Tools
```bash
# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Install Terraform
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
unzip terraform_1.6.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/

# Install gcloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud init
```

## Step 1: Infrastructure Deployment

### 1.1 Configure Terraform Variables

Create `infrastructure/terraform/terraform.tfvars`:

```hcl
project_name    = "datamiq-bq-redshift"
environment     = "production"
aws_region      = "us-east-1"
gcp_project_id  = "your-gcp-project-id"
gcp_region      = "us-central1"
vpc_cidr        = "10.0.0.0/16"
gcp_vpc_cidr    = "10.1.0.0/16"
```

### 1.2 Deploy Infrastructure

```bash
cd infrastructure/terraform

# Initialize Terraform
terraform init

# Plan deployment
terraform plan -out=tfplan

# Apply infrastructure
terraform apply tfplan

# Save outputs
terraform output -json > outputs.json
```

### 1.3 Verify VPN Connection

```bash
# Check AWS VPN status
aws ec2 describe-vpn-connections \
  --filters "Name=tag:Name,Values=datamiq-bq-redshift-production-vpn-to-gcp"

# Check GCP VPN status
gcloud compute vpn-tunnels list --project=your-gcp-project-id
```

## Step 2: Database Setup

### 2.1 Create RDS PostgreSQL Instance

```bash
# Create RDS instance (if not using Terraform)
aws rds create-db-instance \
  --db-instance-identifier datamiq-production \
  --db-instance-class db.r6g.xlarge \
  --engine postgres \
  --engine-version 15.4 \
  --master-username admin \
  --master-user-password <SECURE_PASSWORD> \
  --allocated-storage 100 \
  --storage-type gp3 \
  --storage-encrypted \
  --multi-az \
  --vpc-security-group-ids sg-xxxxx \
  --db-subnet-group-name datamiq-db-subnet-group \
  --backup-retention-period 7 \
  --preferred-backup-window "03:00-04:00" \
  --preferred-maintenance-window "mon:04:00-mon:05:00"
```

### 2.2 Run Database Migrations

```bash
# Connect to RDS
export DATABASE_URL="postgresql://admin:<PASSWORD>@datamiq-production.xxxxx.us-east-1.rds.amazonaws.com:5432/datamiq"

# Run Alembic migrations
cd backend
source .venv/bin/activate
alembic upgrade head
```

## Step 3: ElastiCache Redis Setup

### 3.1 Create Redis Cluster

```bash
# Create Redis replication group
aws elasticache create-replication-group \
  --replication-group-id datamiq-production-redis \
  --replication-group-description "DataMIQ Production Redis" \
  --engine redis \
  --engine-version 7.0 \
  --cache-node-type cache.r6g.large \
  --num-cache-clusters 2 \
  --automatic-failover-enabled \
  --multi-az-enabled \
  --cache-subnet-group-name datamiq-redis-subnet-group \
  --security-group-ids sg-xxxxx \
  --at-rest-encryption-enabled \
  --transit-encryption-enabled \
  --auth-token <SECURE_TOKEN>
```

### 3.2 Get Redis Endpoint

```bash
aws elasticache describe-replication-groups \
  --replication-group-id datamiq-production-redis \
  --query 'ReplicationGroups[0].NodeGroups[0].PrimaryEndpoint.Address'
```

## Step 4: Secrets Management

### 4.1 Store Database Credentials

```bash
# Store RDS credentials
aws secretsmanager create-secret \
  --name datamiq/production/database \
  --description "Database credentials" \
  --secret-string '{
    "username": "admin",
    "password": "<SECURE_PASSWORD>",
    "host": "datamiq-production.xxxxx.us-east-1.rds.amazonaws.com",
    "port": 5432,
    "database": "datamiq"
  }'

# Store Redis credentials
aws secretsmanager create-secret \
  --name datamiq/production/redis \
  --description "Redis credentials" \
  --secret-string '{
    "host": "datamiq-production-redis.xxxxx.cache.amazonaws.com",
    "port": 6379,
    "auth_token": "<SECURE_TOKEN>"
  }'
```

### 4.2 Store GCP Service Account Key

```bash
# Get service account key from Terraform output
terraform output -raw gcp_service_account_key > gcp-key.json

# Store in Secrets Manager (already done by Terraform)
# Verify it exists
aws secretsmanager describe-secret \
  --secret-id datamiq/production/gcp-service-account-key
```

## Step 5: Container Registry

### 5.1 Create ECR Repositories

```bash
# Create backend repository
aws ecr create-repository \
  --repository-name datamiq/backend \
  --image-scanning-configuration scanOnPush=true \
  --encryption-configuration encryptionType=KMS

# Create worker repository
aws ecr create-repository \
  --repository-name datamiq/worker \
  --image-scanning-configuration scanOnPush=true \
  --encryption-configuration encryptionType=KMS
```

### 5.2 Build and Push Images

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com

# Build backend image
cd backend
docker build -t datamiq/backend:latest .
docker tag datamiq/backend:latest <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/datamiq/backend:latest
docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/datamiq/backend:latest

# Build worker image
docker build -f Dockerfile.worker -t datamiq/worker:latest .
docker tag datamiq/worker:latest <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/datamiq/worker:latest
docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/datamiq/worker:latest
```

## Step 6: ECS Deployment

### 6.1 Create ECS Cluster

```bash
aws ecs create-cluster \
  --cluster-name datamiq-production \
  --capacity-providers FARGATE FARGATE_SPOT \
  --default-capacity-provider-strategy \
    capacityProvider=FARGATE,weight=1 \
    capacityProvider=FARGATE_SPOT,weight=4
```

### 6.2 Create Task Definitions

Create `backend-task-definition.json`:

```json
{
  "family": "datamiq-backend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "2048",
  "memory": "4096",
  "executionRoleArn": "arn:aws:iam::<ACCOUNT_ID>:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::<ACCOUNT_ID>:role/datamiq-production-migration-role",
  "containerDefinitions": [
    {
      "name": "backend",
      "image": "<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/datamiq/backend:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "ENVIRONMENT", "va lue": "production"},
        {"name": "AWS_REGION", "value": "us-east-1"}
      ],
      "secrets": [
        {
          "name": "DATABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:datamiq/production/database"
        },
        {
          "name": "REDIS_URL",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:datamiq/production/redis"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/datamiq-backend",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

Register task definition:

```bash
aws ecs register-task-definition \
  --cli-input-json file://backend-task-definition.json
```

### 6.3 Create ECS Service

```bash
aws ecs create-service \
  --cluster datamiq-production \
  --service-name backend \
  --task-definition datamiq-backend \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={
    subnets=[subnet-xxxxx,subnet-yyyyy],
    securityGroups=[sg-xxxxx],
    assignPublicIp=DISABLED
  }" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:...,containerName=backend,containerPort=8000" \
  --health-check-grace-period-seconds 60
```

### 6.4 Deploy Background Worker

Create `worker-task-definition.json` (similar to backend but without load balancer).

```bash
aws ecs register-task-definition \
  --cli-input-json file://worker-task-definition.json

aws ecs create-service \
  --cluster datamiq-production \
  --service-name worker \
  --task-definition datamiq-worker \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={
    subnets=[subnet-xxxxx,subnet-yyyyy],
    securityGroups=[sg-xxxxx],
    assignPublicIp=DISABLED
  }"
```

## Step 7: Monitoring & Logging

### 7.1 Create CloudWatch Log Groups

```bash
aws logs create-log-group --log-group-name /ecs/datamiq-backend
aws logs create-log-group --log-group-name /ecs/datamiq-worker
aws logs put-retention-policy --log-group-name /ecs/datamiq-backend --retention-in-days 30
aws logs put-retention-policy --log-group-name /ecs/datamiq-worker --retention-in-days 30
```

### 7.2 Create CloudWatch Alarms

```bash
# High error rate alarm
aws cloudwatch put-metric-alarm \
  --alarm-name datamiq-high-error-rate \
  --alarm-description "Alert when error rate exceeds 5%" \
  --metric-name Errors \
  --namespace AWS/ApplicationELB \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 50 \
  --comparison-operator GreaterThanThreshold

# Database connection alarm
aws cloudwatch put-metric-alarm \
  --alarm-name datamiq-db-connections \
  --alarm-description "Alert when DB connections exceed 80%" \
  --metric-name DatabaseConnections \
  --namespace AWS/RDS \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold
```

## Step 8: Frontend Deployment

### 8.1 Build Frontend

```bash
cd frontend
npm install
npm run build
```

### 8.2 Deploy to S3 + CloudFront

```bash
# Create S3 bucket
aws s3 mb s3://datamiq-production-frontend

# Enable static website hosting
aws s3 website s3://datamiq-production-frontend \
  --index-document index.html \
  --error-document index.html

# Upload build
aws s3 sync dist/ s3://datamiq-production-frontend/ \
  --delete \
  --cache-control "max-age=31536000"

# Create CloudFront distribution (use AWS Console or Terraform)
```

## Step 9: Testing

### 9.1 Health Checks

```bash
# Test backend health
curl https://api.datamiq.com/health

# Test database connection
curl https://api.datamiq.com/api/health/db

# Test Redis connection
curl https://api.datamiq.com/api/health/redis
```

### 9.2 Create Test Migration

```bash
curl -X POST https://api.datamiq.com/api/migrations/bq-redshift/create \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{
    "migration_name": "Test Migration",
    "pathway": "A",
    "source_connection_id": 1,
    "source_project_id": "test-project",
    "source_dataset": "test_dataset",
    "source_tables": ["test_table"],
    "target_connection_id": 2,
    "target_cluster": "test-cluster.redshift.amazonaws.com",
    "target_database": "test_db",
    "target_schema": "public",
    "gcs_bucket": "test-gcs-bucket",
    "gcs_path": "test/",
    "s3_bucket": "test-s3-bucket",
    "s3_path": "test/"
  }'
```

## Step 10: Production Checklist

- [ ] VPN tunnel established and tested
- [ ] Database migrations applied
- [ ] Redis cluster operational
- [ ] All secrets stored in Secrets Manager
- [ ] IAM roles configured with least privilege
- [ ] Security groups configured properly
- [ ] ECS services running with desired count
- [ ] Load balancer health checks passing
- [ ] CloudWatch alarms configured
- [ ] Backup policies enabled
- [ ] SSL certificates installed
- [ ] DNS records configured
- [ ] Monitoring dashboards created
- [ ] Documentation updated
- [ ] Team trained on operations

## Maintenance

### Daily
- Monitor CloudWatch dashboards
- Check migration success rates
- Review error logs

### Weekly
- Review cost reports
- Check security alerts
- Update dependencies

### Monthly
- Review and rotate credentials
- Test disaster recovery procedures
- Optimize resource allocation
- Review and update documentation

## Troubleshooting

### VPN Connection Issues
```bash
# Check tunnel status
aws ec2 describe-vpn-connections --vpn-connection-ids vpn-xxxxx

# Check GCP tunnel status
gcloud compute vpn-tunnels describe tunnel-name --region=us-central1

# Test connectivity
ping 10.1.0.1  # From AWS to GCP
```

### Database Connection Issues
```bash
# Check RDS status
aws rds describe-db-instances --db-instance-identifier datamiq-production

# Test connection
psql -h datamiq-production.xxxxx.rds.amazonaws.com -U admin -d datamiq
```

### Redis Connection Issues
```bash
# Check ElastiCache status
aws elasticache describe-replication-groups \
  --replication-group-id datamiq-production-redis

# Test connection
redis-cli -h datamiq-production-redis.xxxxx.cache.amazonaws.com -p 6379 --tls
```

## Rollback Procedures

### Application Rollback
```bash
# Update ECS service to previous task definition
aws ecs update-service \
  --cluster datamiq-production \
  --service backend \
  --task-definition datamiq-backend:PREVIOUS_VERSION
```

### Database Rollback
```bash
# Downgrade Alembic migration
alembic downgrade -1
```

## Support

For issues or questions:
- Email: support@datamiq.com
- Slack: #datamiq-ops
- On-call: PagerDuty rotation
