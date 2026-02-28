# EC2 Quick Start Guide

## 🚀 Fast Deployment (5 Minutes)

### Prerequisites
- EC2 instance running Ubuntu 22.04
- RDS PostgreSQL database created
- Security groups configured
- Code pulled from GitHub

### One-Command Deployment

```bash
# Make deployment script executable
chmod +x deploy-ec2.sh

# Run deployment
./deploy-ec2.sh
```

The script will:
1. ✅ Install all system dependencies
2. ✅ Setup Python backend with uv
3. ✅ Setup React frontend
4. ✅ Configure PM2 process manager
5. ✅ Configure Nginx reverse proxy
6. ✅ Start all services

### Manual Steps Required

#### 1. Create Backend .env File

```bash
cd backend
nano .env
```

Add:
```env
DATABASE_URL=postgresql://user:pass@your-rds-endpoint:5432/datamiq
AWS_REGION=us-east-1
# ... other config
```

#### 2. Create Frontend .env.production File

```bash
cd frontend
nano .env.production
```

Add:
```env
REACT_APP_API_URL=http://your-ec2-ip:8000
```

#### 3. Run Deployment Script

```bash
./deploy-ec2.sh
```

## 📋 Essential Commands

### Application Management
```bash
pm2 status              # Check status
pm2 logs                # View logs
pm2 restart all         # Restart apps
pm2 stop all            # Stop apps
```

### View Logs
```bash
pm2 logs datamiq-backend --lines 100
pm2 logs datamiq-frontend --lines 100
```

### Update Application
```bash
git pull
cd backend && source .venv/bin/activate && uv pip install -r requirements.txt
cd ../frontend && npm install && npm run build
pm2 restart all
```

### Database Operations
```bash
cd backend
source .venv/bin/activate
alembic upgrade head    # Run migrations
alembic current         # Check current version
```

## 🔍 Troubleshooting

### Backend Not Working
```bash
pm2 logs datamiq-backend
cd backend && source .venv/bin/activate
uvicorn main:app --reload  # Test manually
```

### Frontend Not Loading
```bash
pm2 logs datamiq-frontend
cd frontend && npm run build
pm2 restart datamiq-frontend
```

### Check Nginx
```bash
sudo nginx -t                          # Test config
sudo systemctl status nginx            # Check status
sudo tail -f /var/log/nginx/error.log  # View errors
```

## 🌐 Access Application

After deployment, access at:
- **Application**: `http://your-ec2-public-ip`
- **Backend API**: `http://your-ec2-public-ip/api`
- **Health Check**: `http://your-ec2-public-ip/health`

## 📚 Full Documentation

See `EC2_DEPLOYMENT_GUIDE.md` for:
- Detailed setup instructions
- Security configuration
- SSL/TLS setup
- Monitoring and maintenance
- Performance optimization

## ⚙️ Required AWS Resources

### EC2 Instance
- Type: t3.medium or larger
- OS: Ubuntu 22.04 LTS
- Storage: 30GB+
- Security Group: Ports 22, 80, 443, 8000, 3000

### RDS PostgreSQL
- Engine: PostgreSQL 14+
- Instance: db.t3.micro or larger
- Storage: 20GB+
- Security Group: Port 5432 from EC2

### ElastiCache Redis (Optional)
- Engine: Redis 6.x+
- Node: cache.t3.micro or larger
- Security Group: Port 6379 from EC2

## 🔐 Security Checklist

- [ ] Configure .env files with secure credentials
- [ ] Setup SSL certificate (certbot)
- [ ] Restrict security group rules
- [ ] Use IAM roles instead of access keys
- [ ] Enable CloudWatch logging
- [ ] Setup automated backups
- [ ] Enable MFA for AWS console

## 📊 Monitoring

### Check Application Health
```bash
curl http://localhost:8000/health
pm2 monit
```

### System Resources
```bash
df -h      # Disk space
free -h    # Memory
top        # CPU usage
```

## 🆘 Support

If you encounter issues:
1. Check logs: `pm2 logs`
2. Review `EC2_DEPLOYMENT_GUIDE.md`
3. Check security groups
4. Verify .env configuration
5. Test database connectivity
