#!/bin/bash
# DataMIQ EC2 Deployment Script
# Run this script on your EC2 instance after cloning the repository

set -e

echo "🚀 DataMIQ EC2 Deployment Script"
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo -e "${RED}❌ Please do not run as root${NC}"
   exit 1
fi

# Get current directory
APP_DIR=$(pwd)
echo -e "${GREEN}📁 Application directory: $APP_DIR${NC}"

# Step 1: Install system dependencies
echo -e "\n${YELLOW}Step 1: Installing system dependencies...${NC}"
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip nodejs npm postgresql-client nginx

# Install uv
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
fi

# Install PM2
if ! command -v pm2 &> /dev/null; then
    echo "Installing PM2..."
    sudo npm install -g pm2
fi

# Step 2: Setup Backend
echo -e "\n${YELLOW}Step 2: Setting up backend...${NC}"
cd $APP_DIR/backend

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    uv venv
fi

# Activate and install dependencies
source .venv/bin/activate
echo "Installing Python dependencies..."
uv pip install -r requirements.txt

# Check for .env file
if [ ! -f ".env" ]; then
    echo -e "${RED}⚠️  Warning: .env file not found in backend/${NC}"
    echo "Please create backend/.env file with your configuration"
    echo "See .env.example for reference"
    read -p "Press enter to continue or Ctrl+C to exit..."
fi

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Step 3: Setup Frontend
echo -e "\n${YELLOW}Step 3: Setting up frontend...${NC}"
cd $APP_DIR/frontend

# Install dependencies
echo "Installing Node dependencies..."
npm install

# Check for .env.production file
if [ ! -f ".env.production" ]; then
    echo -e "${RED}⚠️  Warning: .env.production file not found in frontend/${NC}"
    echo "Please create frontend/.env.production file"
    read -p "Press enter to continue or Ctrl+C to exit..."
fi

# Build frontend
echo "Building frontend for production..."
npm run build

# Step 4: Create PM2 ecosystem file
echo -e "\n${YELLOW}Step 4: Creating PM2 configuration...${NC}"
cd $APP_DIR

cat > ecosystem.config.js << 'EOF'
module.exports = {
  apps: [
    {
      name: 'datamiq-backend',
      cwd: process.env.HOME + '/datamiq/backend',
      script: '.venv/bin/uvicorn',
      args: 'main:app --host 0.0.0.0 --port 8000 --workers 4',
      interpreter: 'none',
      env: {
        PYTHONPATH: process.env.HOME + '/datamiq/backend',
      },
      error_file: process.env.HOME + '/logs/backend-error.log',
      out_file: process.env.HOME + '/logs/backend-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
      autorestart: true,
      max_restarts: 10,
      min_uptime: '10s',
    },
    {
      name: 'datamiq-frontend',
      cwd: process.env.HOME + '/datamiq/frontend',
      script: 'npx',
      args: 'serve -s build -l 3000',
      env: {
        NODE_ENV: 'production',
      },
      error_file: process.env.HOME + '/logs/frontend-error.log',
      out_file: process.env.HOME + '/logs/frontend-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
      autorestart: true,
    }
  ]
};
EOF

# Create logs directory
mkdir -p $HOME/logs

# Step 5: Configure Nginx
echo -e "\n${YELLOW}Step 5: Configuring Nginx...${NC}"

# Get EC2 public IP
EC2_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
echo "EC2 Public IP: $EC2_IP"

sudo tee /etc/nginx/sites-available/datamiq > /dev/null << EOF
server {
    listen 80;
    server_name $EC2_IP;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Backend API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        proxy_connect_timeout 600;
        proxy_send_timeout 600;
        proxy_read_timeout 600;
        send_timeout 600;
    }

    location /health {
        proxy_pass http://localhost:8000/health;
        access_log off;
    }

    client_max_body_size 100M;
}
EOF

# Enable site
sudo ln -sf /etc/nginx/sites-available/datamiq /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test and restart Nginx
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx

# Step 6: Start applications with PM2
echo -e "\n${YELLOW}Step 6: Starting applications...${NC}"
cd $APP_DIR

# Stop any existing PM2 processes
pm2 delete all 2>/dev/null || true

# Start applications
pm2 start ecosystem.config.js

# Save PM2 configuration
pm2 save

# Setup PM2 startup
pm2 startup | tail -n 1 | sudo bash

# Step 7: Verification
echo -e "\n${YELLOW}Step 7: Verifying deployment...${NC}"

sleep 5

# Check PM2 status
echo -e "\n${GREEN}PM2 Status:${NC}"
pm2 status

# Check Nginx status
echo -e "\n${GREEN}Nginx Status:${NC}"
sudo systemctl status nginx --no-pager

# Test endpoints
echo -e "\n${GREEN}Testing endpoints:${NC}"
echo "Backend health: $(curl -s http://localhost:8000/health || echo 'Failed')"
echo "Frontend: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:3000)"

# Final message
echo -e "\n${GREEN}=================================="
echo "✅ Deployment Complete!"
echo "==================================${NC}"
echo ""
echo "🌐 Access your application at:"
echo "   http://$EC2_IP"
echo ""
echo "📊 Useful commands:"
echo "   pm2 status          - Check application status"
echo "   pm2 logs            - View application logs"
echo "   pm2 restart all     - Restart all applications"
echo "   pm2 stop all        - Stop all applications"
echo ""
echo "📝 Next steps:"
echo "   1. Configure your domain DNS to point to $EC2_IP"
echo "   2. Setup SSL certificate with: sudo certbot --nginx"
echo "   3. Review logs: pm2 logs"
echo ""
echo "📚 Full documentation: EC2_DEPLOYMENT_GUIDE.md"
