# EC2 Deployment Guide - DataMIQ Application

## Overview
This guide will help you deploy the DataMIQ application (React frontend + FastAPI backend) on an AWS EC2 instance.

## Prerequisites

### AWS Resources Required
- EC2 instance (t3.medium or larger recommended)
- RDS PostgreSQL database
- ElastiCache Redis (optional but recommended)
- Security Groups configured
- IAM role for EC2 with necessary permissions

### EC2 Instance Specifications
- **Instance Type**: t3.medium or larger (2 vCPU, 4GB RAM minimum)
- **OS**: Ubuntu 22.04 LTS or Amazon Linux 2023
- **Storage**: 30GB+ EBS volume
- **Security Group**: Allow ports 22 (SSH), 80 (HTTP), 443 (HTTPS), 8000 (Backend), 3000 (Frontend - dev only)

## Step 1: Initial EC2 Setup

### 1.1 Connect to EC2 Instance

```bash
ssh -i your-key.pem ubuntu@your-ec2-public-ip
```

### 1.2 Update System Packages

```bash
sudo apt update && sudo apt upgrade -y
```

### 1.3 Install Required System Dependencies

```bash
# Install Python 3.11+
sudo apt install -y python3.11 python3.11-venv python3-pip

# Install Node.js 18+ and npm
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Install PostgreSQL client (for database operations)
sudo apt install -y postgresql-client

# Install Redis client (optional)
sudo apt install -y redis-tools

# Install Nginx (for reverse proxy)
sudo apt install -y nginx

# Install PM2 (process manager)
sudo npm install -g pm2

# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env
```

## Step 2: Clone and Setup Application

### 2.1 Clone Repository

```bash
cd /home/ubuntu
git clone https://github.com/your-repo/datamiq.git
cd datamiq
```

### 2.2 Setup Backend

```bash
cd backend

# Create virtual environment using uv
uv venv

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt

# Verify installation
python --version
pip list
```

### 2.3 Setup Frontend

```bash
cd ../frontend

# Install dependencies
npm install

# Build for production
npm run build
```

## Step 3: Configure Environment Variables

### 3.1 Backend Configuration

Create `.env` file in `backend/` directory:

```bash
cd /home/ubuntu/datamiq/backend
nano .env
```

Add the following configuration:

```env
# Database Configuration
DATABASE_URL=postgresql://username:password@your-rds-endpoint:5432/datamiq
DB_HOST=your-rds-endpoint.rds.amazonaws.com
DB_PORT=5432
DB_NAME=datamiq
DB_USER=your_db_user
DB_PASSWORD=your_db_password

# Redis Configuration (if using ElastiCache)
REDIS_HOST=your-elasticache-endpoint.cache.amazonaws.com
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_redis_password
REDIS_SSL=true

# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key

# KMS Configuration (for encryption)
KMS_KEY_ID=your-kms-key-id
SECRET_MANAGER_SECRET_NAME=datamiq-secrets

# Application Configuration
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# CORS Configuration
ALLOWED_ORIGINS=http://your-domain.com,https://your-domain.com

# Security
SECRET_KEY=your-secret-key-here-generate-a-strong-one
```

Save and exit (Ctrl+X, Y, Enter)

### 3.2 Frontend Configuration

Create `.env.production` file in `frontend/` directory:

```bash
cd /home/ubuntu/datamiq/frontend
nano .env.production
```

Add:

```env
REACT_APP_API_URL=http://your-ec2-public-ip:8000
REACT_APP_ENVIRONMENT=production
```

Rebuild frontend with production config:

```bash
npm run build
```

## Step 4: Database Setup

### 4.1 Run Database Migrations

```bash
cd /home/ubuntu/datamiq/backend
source .venv/bin/activate

# Run Alembic migrations
alembic upgrade head

# Verify migrations
alembic current
```

### 4.2 Create Initial Data (Optional)

```bash
# If you have seed data scripts
python scripts/seed_data.py
```

## Step 5: Configure Process Manager (PM2)

### 5.1 Create PM2 Ecosystem File

```bash
cd /home/ubuntu/datamiq
nano ecosystem.config.js
```

Add the following configuration:

```javascript
module.exports = {
  apps: [
    {
      name: 'datamiq-backend',
      cwd: '/home/ubuntu/datamiq/backend',
      script: '.venv/bin/uvicorn',
      args: 'main:app --host 0.0.0.0 --port 8000 --workers 4',
      interpreter: 'none',
      env: {
        PYTHONPATH: '/home/ubuntu/datamiq/backend',
      },
      error_file: '/home/ubuntu/logs/backend-error.log',
      out_file: '/home/ubuntu/logs/backend-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
      autorestart: true,
      max_restarts: 10,
      min_uptime: '10s',
    },
    {
      name: 'datamiq-frontend',
      cwd: '/home/ubuntu/datamiq/frontend',
      script: 'npx',
      args: 'serve -s build -l 3000',
      env: {
        NODE_ENV: 'production',
      },
      error_file: '/home/ubuntu/logs/frontend-error.log',
      out_file: '/home/ubuntu/logs/frontend-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
      autorestart: true,
    }
  ]
};
```

### 5.2 Create Log Directory

```bash
mkdir -p /home/ubuntu/logs
```

### 5.3 Start Applications with PM2

```bash
cd /home/ubuntu/datamiq

# Start all applications
pm2 start ecosystem.config.js

# Check status
pm2 status

# View logs
pm2 logs

# Save PM2 configuration
pm2 save

# Setup PM2 to start on system boot
pm2 startup
# Follow the command it outputs
```

## Step 6: Configure Nginx Reverse Proxy

### 6.1 Create Nginx Configuration

```bash
sudo nano /etc/nginx/sites-available/datamiq
```

Add the following configuration:

```nginx
# Backend API
server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain or EC2 public IP

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Backend API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Increase timeouts for long-running operations
        proxy_connect_timeout 600;
        proxy_send_timeout 600;
        proxy_read_timeout 600;
        send_timeout 600;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://localhost:8000/health;
        access_log off;
    }

    # Increase max body size for file uploads
    client_max_body_size 100M;
}
```

### 6.2 Enable Site and Restart Nginx

```bash
# Enable the site
sudo ln -s /etc/nginx/sites-available/datamiq /etc/nginx/sites-enabled/

# Remove default site
sudo rm /etc/nginx/sites-enabled/default

# Test Nginx configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx

# Enable Nginx to start on boot
sudo systemctl enable nginx
```

## Step 7: Configure Security Groups

### 7.1 EC2 Security Group Rules

Ensure your EC2 security group allows:

| Type | Protocol | Port Range | Source | Description |
|------|----------|------------|--------|-------------|
| SSH | TCP | 22 | Your IP | SSH access |
| HTTP | TCP | 80 | 0.0.0.0/0 | Web traffic |
| HTTPS | TCP | 443 | 0.0.0.0/0 | Secure web traffic |
| Custom TCP | TCP | 8000 | Security Group ID | Backend API (internal) |
| Custom TCP | TCP | 3000 | Security Group ID | Frontend (internal) |

### 7.2 RDS Security Group Rules

Allow inbound PostgreSQL (port 5432) from EC2 security group.

### 7.3 ElastiCache Security Group Rules

Allow inbound Redis (port 6379) from EC2 security group.

## Step 8: Setup SSL/TLS (Optional but Recommended)

### 8.1 Install Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 8.2 Obtain SSL Certificate

```bash
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

Follow the prompts to configure SSL.

### 8.3 Auto-Renewal

```bash
# Test renewal
sudo certbot renew --dry-run

# Certbot will automatically setup a cron job for renewal
```

## Step 9: Verify Deployment

### 9.1 Check Application Status

```bash
# Check PM2 processes
pm2 status

# Check Nginx status
sudo systemctl status nginx

# Check backend logs
pm2 logs datamiq-backend --lines 50

# Check frontend logs
pm2 logs datamiq-frontend --lines 50
```

### 9.2 Test Endpoints

```bash
# Test backend health
curl http://localhost:8000/health

# Test backend API
curl http://localhost:8000/api/health

# Test frontend
curl http://localhost:3000

# Test through Nginx
curl http://your-ec2-public-ip
```

### 9.3 Access Application

Open browser and navigate to:
- `http://your-ec2-public-ip` or `http://your-domain.com`

## Step 10: Monitoring and Maintenance

### 10.1 Setup CloudWatch Logs (Optional)

```bash
# Install CloudWatch agent
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i amazon-cloudwatch-agent.deb

# Configure CloudWatch agent
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-config-wizard
```

### 10.2 Regular Maintenance Commands

```bash
# View PM2 logs
pm2 logs

# Restart applications
pm2 restart all

# Stop applications
pm2 stop all

# Update application
cd /home/ubuntu/datamiq
git pull
cd backend && source .venv/bin/activate && uv pip install -r requirements.txt
cd ../frontend && npm install && npm run build
pm2 restart all

# Check disk space
df -h

# Check memory usage
free -h

# Check CPU usage
top
```

### 10.3 Backup Strategy

```bash
# Backup database (run from EC2)
pg_dump -h your-rds-endpoint -U your_db_user -d datamiq > backup_$(date +%Y%m%d).sql

# Upload to S3
aws s3 cp backup_$(date +%Y%m%d).sql s3://your-backup-bucket/
```

## Troubleshooting

### Backend Not Starting

```bash
# Check logs
pm2 logs datamiq-backend

# Check if port 8000 is in use
sudo lsof -i :8000

# Manually test backend
cd /home/ubuntu/datamiq/backend
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend Not Loading

```bash
# Check logs
pm2 logs datamiq-frontend

# Check if port 3000 is in use
sudo lsof -i :3000

# Rebuild frontend
cd /home/ubuntu/datamiq/frontend
npm run build
pm2 restart datamiq-frontend
```

### Database Connection Issues

```bash
# Test database connection
psql -h your-rds-endpoint -U your_db_user -d datamiq

# Check .env file
cat /home/ubuntu/datamiq/backend/.env | grep DATABASE
```

### Nginx Issues

```bash
# Check Nginx error logs
sudo tail -f /var/log/nginx/error.log

# Test Nginx configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
```

## Quick Start Script

Create a deployment script for easy updates:

```bash
nano /home/ubuntu/deploy.sh
```

Add:

```bash
#!/bin/bash
set -e

echo "🚀 Deploying DataMIQ Application..."

# Pull latest code
cd /home/ubuntu/datamiq
git pull

# Update backend
echo "📦 Updating backend..."
cd backend
source .venv/bin/activate
uv pip install -r requirements.txt
alembic upgrade head

# Update frontend
echo "📦 Updating frontend..."
cd ../frontend
npm install
npm run build

# Restart applications
echo "🔄 Restarting applications..."
pm2 restart all

echo "✅ Deployment complete!"
pm2 status
```

Make it executable:

```bash
chmod +x /home/ubuntu/deploy.sh
```

Run deployments:

```bash
/home/ubuntu/deploy.sh
```

## Security Checklist

- [ ] Change default SSH port
- [ ] Setup firewall (ufw)
- [ ] Enable automatic security updates
- [ ] Use IAM roles instead of access keys
- [ ] Enable CloudTrail logging
- [ ] Setup SSL/TLS certificates
- [ ] Restrict database access
- [ ] Use strong passwords
- [ ] Enable MFA for AWS console
- [ ] Regular security audits

## Performance Optimization

- [ ] Enable Nginx gzip compression
- [ ] Setup CloudFront CDN
- [ ] Use ElastiCache for Redis
- [ ] Enable RDS Multi-AZ
- [ ] Setup Auto Scaling
- [ ] Optimize database queries
- [ ] Enable connection pooling
- [ ] Monitor with CloudWatch

## Support

For issues or questions:
1. Check application logs: `pm2 logs`
2. Check Nginx logs: `sudo tail -f /var/log/nginx/error.log`
3. Review this guide
4. Check GitHub issues

## Next Steps

1. Setup monitoring and alerting
2. Configure automated backups
3. Implement CI/CD pipeline
4. Setup staging environment
5. Configure auto-scaling
6. Enable CloudWatch dashboards
