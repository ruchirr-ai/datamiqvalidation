#!/bin/bash
# PostgreSQL Local Setup Script for EC2
# This script automates PostgreSQL installation and configuration

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=================================="
echo "PostgreSQL Setup for DataMIQ"
echo "==================================${NC}"

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo -e "${RED}❌ Please do not run as root${NC}"
   exit 1
fi

# Get database credentials
echo -e "\n${YELLOW}Enter database configuration:${NC}"
read -p "Database name [datamiq]: " DB_NAME
DB_NAME=${DB_NAME:-datamiq}

read -p "Database user [datamiq_user]: " DB_USER
DB_USER=${DB_USER:-datamiq_user}

read -sp "Database password: " DB_PASSWORD
echo

if [ -z "$DB_PASSWORD" ]; then
    echo -e "${RED}❌ Password cannot be empty${NC}"
    exit 1
fi

# Step 1: Install PostgreSQL
echo -e "\n${YELLOW}Step 1: Installing PostgreSQL...${NC}"
sudo apt update
sudo apt install -y postgresql postgresql-contrib

# Start and enable PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Wait for PostgreSQL to start
sleep 3

# Step 2: Create database and user
echo -e "\n${YELLOW}Step 2: Creating database and user...${NC}"

sudo -u postgres psql << EOF
-- Create database
CREATE DATABASE $DB_NAME;

-- Create user
CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;

-- Connect to database and grant schema privileges
\c $DB_NAME

GRANT ALL ON SCHEMA public TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $DB_USER;

-- Verify
\l
\du
EOF

echo -e "${GREEN}✅ Database and user created${NC}"

# Step 3: Configure PostgreSQL for local access
echo -e "\n${YELLOW}Step 3: Configuring PostgreSQL...${NC}"

# Backup original pg_hba.conf
sudo cp /etc/postgresql/14/main/pg_hba.conf /etc/postgresql/14/main/pg_hba.conf.backup

# Add local access configuration
sudo tee -a /etc/postgresql/14/main/pg_hba.conf > /dev/null << EOF

# DataMIQ Application Access
local   all             $DB_USER                                md5
host    all             $DB_USER        127.0.0.1/32            md5
host    all             $DB_USER        ::1/128                 md5
EOF

# Restart PostgreSQL
sudo systemctl restart postgresql

echo -e "${GREEN}✅ PostgreSQL configured${NC}"

# Step 4: Test connection
echo -e "\n${YELLOW}Step 4: Testing database connection...${NC}"

export PGPASSWORD=$DB_PASSWORD
if psql -h localhost -U $DB_USER -d $DB_NAME -c "SELECT version();" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Database connection successful${NC}"
else
    echo -e "${RED}❌ Database connection failed${NC}"
    exit 1
fi
unset PGPASSWORD

# Step 5: Create .env configuration
echo -e "\n${YELLOW}Step 5: Creating .env configuration...${NC}"

if [ -d "backend" ]; then
    ENV_FILE="backend/.env"
    
    # Backup existing .env if it exists
    if [ -f "$ENV_FILE" ]; then
        cp "$ENV_FILE" "$ENV_FILE.backup.$(date +%Y%m%d_%H%M%S)"
        echo -e "${YELLOW}⚠️  Existing .env backed up${NC}"
    fi
    
    # Create or update .env file
    cat > "$ENV_FILE" << EOF
# Database Configuration
DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME
DB_HOST=localhost
DB_PORT=5432
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD

# Redis Configuration (optional - will fallback to database if not available)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# AWS Configuration (update with your values)
AWS_REGION=us-east-1
# AWS_ACCESS_KEY_ID=your_access_key
# AWS_SECRET_ACCESS_KEY=your_secret_key

# KMS Configuration (update with your values)
# KMS_KEY_ID=your-kms-key-id
# SECRET_MANAGER_SECRET_NAME=datamiq-secrets

# Application Configuration
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# Security
SECRET_KEY=$(openssl rand -hex 32)

# CORS Configuration (update with your domain)
ALLOWED_ORIGINS=http://localhost:3000,http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
EOF

    echo -e "${GREEN}✅ .env file created at $ENV_FILE${NC}"
    echo -e "${YELLOW}⚠️  Please update AWS and KMS configuration in $ENV_FILE${NC}"
else
    echo -e "${YELLOW}⚠️  backend directory not found. Please create .env manually${NC}"
    echo -e "\nDatabase connection string:"
    echo "DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME"
fi

# Step 6: Setup backup script
echo -e "\n${YELLOW}Step 6: Setting up automated backups...${NC}"

sudo mkdir -p /var/backups/postgresql
sudo chown postgres:postgres /var/backups/postgresql

sudo tee /usr/local/bin/backup-postgres.sh > /dev/null << 'BACKUP_SCRIPT'
#!/bin/bash
BACKUP_DIR="/var/backups/postgresql"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_NAME="datamiq"
DB_USER="datamiq_user"
RETENTION_DAYS=7

pg_dump -U $DB_USER -d $DB_NAME -F c -f "$BACKUP_DIR/datamiq_$TIMESTAMP.backup"
gzip "$BACKUP_DIR/datamiq_$TIMESTAMP.backup"
find $BACKUP_DIR -name "datamiq_*.backup.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: datamiq_$TIMESTAMP.backup.gz"
BACKUP_SCRIPT

sudo chmod +x /usr/local/bin/backup-postgres.sh

# Add to crontab (daily at 2 AM)
(sudo crontab -l 2>/dev/null; echo "0 2 * * * /usr/local/bin/backup-postgres.sh >> /var/log/postgres-backup.log 2>&1") | sudo crontab -

echo -e "${GREEN}✅ Backup script configured (runs daily at 2 AM)${NC}"

# Step 7: Performance tuning
echo -e "\n${YELLOW}Step 7: Applying performance tuning...${NC}"

# Get total RAM in GB
TOTAL_RAM=$(free -g | awk '/^Mem:/{print $2}')
SHARED_BUFFERS=$((TOTAL_RAM / 4))
EFFECTIVE_CACHE=$((TOTAL_RAM * 3 / 4))

if [ $SHARED_BUFFERS -lt 1 ]; then
    SHARED_BUFFERS=1
fi

if [ $EFFECTIVE_CACHE -lt 1 ]; then
    EFFECTIVE_CACHE=1
fi

sudo tee -a /etc/postgresql/14/main/postgresql.conf > /dev/null << EOF

# DataMIQ Performance Tuning
shared_buffers = ${SHARED_BUFFERS}GB
effective_cache_size = ${EFFECTIVE_CACHE}GB
maintenance_work_mem = 256MB
work_mem = 16MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
random_page_cost = 1.1
effective_io_concurrency = 200
max_connections = 100
EOF

sudo systemctl restart postgresql

echo -e "${GREEN}✅ Performance tuning applied${NC}"

# Summary
echo -e "\n${GREEN}=================================="
echo "✅ PostgreSQL Setup Complete!"
echo "==================================${NC}"
echo ""
echo "📊 Database Information:"
echo "   Database: $DB_NAME"
echo "   User: $DB_USER"
echo "   Host: localhost"
echo "   Port: 5432"
echo ""
echo "🔗 Connection String:"
echo "   postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME"
echo ""
echo "📝 Next Steps:"
echo "   1. Review and update backend/.env file"
echo "   2. Run database migrations:"
echo "      cd backend"
echo "      source .venv/bin/activate"
echo "      alembic upgrade head"
echo "   3. Deploy application:"
echo "      ./deploy-ec2.sh"
echo ""
echo "🔧 Useful Commands:"
echo "   Connect: psql -h localhost -U $DB_USER -d $DB_NAME"
echo "   Backup: sudo -u postgres /usr/local/bin/backup-postgres.sh"
echo "   Status: sudo systemctl status postgresql"
echo ""
echo "📚 Full documentation: POSTGRESQL_LOCAL_SETUP.md"
