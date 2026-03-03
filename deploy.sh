#!/bin/bash
# DataMIQ Deploy Script
# Usage: ssh into EC2 and run: sudo /opt/datamiq/deploy.sh
# Or from local: ssh -i <pem> ec2-user@44.223.17.119 "sudo /opt/datamiq/deploy.sh"

set -e

APP_DIR="/opt/datamiq"
BRANCH="shivansh-dev"

echo "=========================================="
echo "  DataMIQ Deploy - $(date)"
echo "=========================================="

# 1. Pull latest code
echo ""
echo "[1/5] Pulling latest from $BRANCH..."
cd "$APP_DIR"
git fetch origin "$BRANCH"
git reset --hard "origin/$BRANCH"
echo "✓ Code updated"

# 2. Install backend dependencies (only if requirements.txt changed)
echo ""
echo "[2/5] Checking backend dependencies..."
cd "$APP_DIR/backend"
source .venv/bin/activate
pip install -r requirements.txt --quiet 2>&1 | tail -3
echo "✓ Backend dependencies up to date"

# 3. Run database migrations
echo ""
echo "[3/5] Running database migrations..."
cd "$APP_DIR/backend"
alembic upgrade head 2>&1 | tail -5
echo "✓ Database migrations applied"

# 4. Rebuild frontend
echo ""
echo "[4/5] Building frontend..."
cd "$APP_DIR/frontend"
npx vite build 2>&1 | tail -5
echo "✓ Frontend built"

# 5. Restart services
echo ""
echo "[5/5] Restarting services..."
systemctl restart datamiq-backend
systemctl restart nginx
sleep 3

# Verify
HEALTH=$(curl -s http://localhost:8000/health 2>/dev/null || echo '{"status":"error"}')
echo ""
echo "=========================================="
echo "  Deploy complete!"
echo "  Health: $HEALTH"
echo "=========================================="
