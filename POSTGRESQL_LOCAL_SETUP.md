# PostgreSQL Local Installation on EC2 - Complete Guide

## Overview
This guide will help you install and configure PostgreSQL locally on your EC2 instance instead of using RDS.

## Step 1: Install PostgreSQL

### 1.1 Update System Packages

```bash
sudo apt update
sudo apt upgrade -y
```

### 1.2 Install PostgreSQL

```bash
# Install PostgreSQL 14 (or latest stable version)
sudo apt install -y postgresql postgresql-contrib

# Verify installation
psql --version
```

Expected output: `psql (PostgreSQL) 14.x`

### 1.3 Check PostgreSQL Service Status

```bash
sudo systemctl status postgresql
```

Should show "active (running)". If not:

```bash
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

## Step 2: Configure PostgreSQL

### 2.1 Switch to PostgreSQL User

```bash
sudo -i -u postgres
```

### 2.2 Access PostgreSQL Shell

```bash
psql
```

You should see: `postgres=#`

### 2.3 Create Database and User

```sql
-- Create database
CREATE DATABASE datamiq;

-- Create user with password
CREATE USER datamiq_user WITH PASSWORD 'your_secure_password_here';

-- Grant all privileges on database
GRANT ALL PRIVILEGES ON DATABASE datamiq TO datamiq_user;

-- Connect to the database
\c datamiq

-- Grant schema privileges
GRANT ALL ON SCHEMA public TO datamiq_user;

-- Grant default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO datamiq_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO datamiq_user;

-- Verify user and database
\l
\du

-- Exit PostgreSQL shell
\q
```

### 2.4 Exit PostgreSQL User

```bash
exit
```

## Step 3: Configure PostgreSQL for Remote Access (Optional)

If you need to access PostgreSQL from outside the EC2 instance:

### 3.1 Edit PostgreSQL Configuration

```bash
sudo nano /etc/postgresql/14/main/postgresql.conf
```

Find and modify:

```conf
# Change from:
#listen_addresses = 'localhost'

# To (listen on all interfaces):
listen_addresses = '*'
```

Save and exit (Ctrl+X, Y, Enter)

### 3.2 Configure Client Authentication

```bash
sudo nano /etc/postgresql/14/main/pg_hba.conf
```

Add at the end of the file:

```conf
# Allow connections from local network
host    all             all             0.0.0.0/0               md5

# Or for specific IP range (more secure):
# host    all             all             10.0.0.0/8              md5
```

Save and exit (Ctrl+X, Y, Enter)

### 3.3 Restart PostgreSQL

```bash
sudo systemctl restart postgresql
```

## Step 4: Test Database Connection

### 4.1 Test Local Connection

```bash
psql -h localhost -U datamiq_user -d datamiq
```

Enter password when prompted. You should see: `datamiq=>`

Test with a query:

```sql
SELECT version();
\q
```

### 4.2 Test Connection String

```bash
psql "postgresql://datamiq_user:your_secure_password_here@localhost:5432/datamiq"
```

Should connect successfully.

## Step 5: Configure Application

### 5.1 Update Backend .env File

```bash
cd ~/datamiq/backend
nano .env
```

Add/update these lines:

```env
# Database Configuration
DATABASE_URL=postgresql://datamiq_user:your_secure_password_here@localhost:5432/datamiq
DB_HOST=localhost
DB_PORT=5432
DB_NAME=datamiq
DB_USER=datamiq_user
DB_PASSWORD=your_secure_password_here

# Other configurations...
AWS_REGION=us-east-1
# ... rest of your config
```

Save and exit (Ctrl+X, Y, Enter)

### 5.2 Test Database Connection from Application

```bash
cd ~/datamiq/backend
source .venv/bin/activate

# Test connection with Python
python -c "
from database import db_instance
try:
    db = db_instance.SessionLocal()
    print('✅ Database connection successful!')
    db.close()
except Exception as e:
    print(f'❌ Database connection failed: {e}')
"
```

## Step 6: Run Database Migrations

### 6.1 Initialize Database Schema

```bash
cd ~/datamiq/backend
source .venv/bin/activate

# Run all migrations
alembic upgrade head

# Verify migrations
alembic current
```

Expected output: Shows the latest migration version.

### 6.2 Verify Tables Created

```bash
psql -h localhost -U datamiq_user -d datamiq
```

```sql
-- List all tables
\dt

-- Should see tables like:
-- assessments
-- connections
-- users
-- workspaces
-- etc.

-- Check a specific table
\d assessments

-- Exit
\q
```

## Step 7: PostgreSQL Performance Tuning

### 7.1 Optimize PostgreSQL Configuration

```bash
sudo nano /etc/postgresql/14/main/postgresql.conf
```

Recommended settings for t3.medium (4GB RAM):

```conf
# Memory Settings
shared_buffers = 1GB                    # 25% of RAM
effective_cache_size = 3GB              # 75% of RAM
maintenance_work_mem = 256MB
work_mem = 16MB

# Checkpoint Settings
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100

# Query Planner
random_page_cost = 1.1                  # For SSD storage
effective_io_concurrency = 200

# Connection Settings
max_connections = 100

# Logging (for debugging)
log_destination = 'stderr'
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_statement = 'none'                  # Change to 'all' for debugging
log_duration = off
log_line_prefix = '%m [%p] %q%u@%d '
```

Save and restart:

```bash
sudo systemctl restart postgresql
```

### 7.2 Create Indexes (After Initial Data Load)

```bash
psql -h localhost -U datamiq_user -d datamiq
```

```sql
-- Add indexes for better performance
CREATE INDEX IF NOT EXISTS idx_assessments_status ON assessments(status);
CREATE INDEX IF NOT EXISTS idx_assessments_workspace ON assessments(workspace_id);
CREATE INDEX IF NOT EXISTS idx_connections_workspace ON connections(workspace_id);
CREATE INDEX IF NOT EXISTS idx_assessment_tables_assessment ON assessment_tables(assessment_id);

-- Verify indexes
\di

-- Exit
\q
```

## Step 8: Setup Automated Backups

### 8.1 Create Backup Directory

```bash
sudo mkdir -p /var/backups/postgresql
sudo chown postgres:postgres /var/backups/postgresql
```

### 8.2 Create Backup Script

```bash
sudo nano /usr/local/bin/backup-postgres.sh
```

Add:

```bash
#!/bin/bash
# PostgreSQL Backup Script

BACKUP_DIR="/var/backups/postgresql"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_NAME="datamiq"
DB_USER="datamiq_user"
RETENTION_DAYS=7

# Create backup
pg_dump -U $DB_USER -d $DB_NAME -F c -f "$BACKUP_DIR/datamiq_$TIMESTAMP.backup"

# Compress backup
gzip "$BACKUP_DIR/datamiq_$TIMESTAMP.backup"

# Remove old backups
find $BACKUP_DIR -name "datamiq_*.backup.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: datamiq_$TIMESTAMP.backup.gz"
```

Make executable:

```bash
sudo chmod +x /usr/local/bin/backup-postgres.sh
```

### 8.3 Setup Cron Job for Daily Backups

```bash
sudo crontab -e
```

Add (runs daily at 2 AM):

```cron
0 2 * * * /usr/local/bin/backup-postgres.sh >> /var/log/postgres-backup.log 2>&1
```

### 8.4 Test Backup Script

```bash
sudo -u postgres /usr/local/bin/backup-postgres.sh
```

Verify backup created:

```bash
ls -lh /var/backups/postgresql/
```

## Step 9: Security Hardening

### 9.1 Set Strong Password Policy

```bash
psql -h localhost -U datamiq_user -d datamiq
```

```sql
-- Set password encryption
ALTER SYSTEM SET password_encryption = 'scram-sha-256';

-- Reload configuration
SELECT pg_reload_conf();

\q
```

### 9.2 Restrict PostgreSQL User

```bash
sudo nano /etc/postgresql/14/main/pg_hba.conf
```

Change to more restrictive:

```conf
# Local connections
local   all             postgres                                peer
local   all             datamiq_user                            md5

# IPv4 local connections
host    all             datamiq_user        127.0.0.1/32        md5
host    all             datamiq_user        ::1/128             md5

# Reject all other connections
host    all             all                 0.0.0.0/0           reject
```

Restart:

```bash
sudo systemctl restart postgresql
```

### 9.3 Setup Firewall (UFW)

```bash
# Enable firewall
sudo ufw enable

# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# PostgreSQL should NOT be exposed externally
# Only allow from localhost (already default)

# Check status
sudo ufw status
```

## Step 10: Monitoring and Maintenance

### 10.1 Check Database Size

```bash
psql -h localhost -U datamiq_user -d datamiq -c "
SELECT 
    pg_size_pretty(pg_database_size('datamiq')) as database_size;
"
```

### 10.2 Check Table Sizes

```bash
psql -h localhost -U datamiq_user -d datamiq -c "
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;
"
```

### 10.3 Check Active Connections

```bash
psql -h localhost -U datamiq_user -d datamiq -c "
SELECT 
    count(*) as active_connections,
    state
FROM pg_stat_activity
WHERE datname = 'datamiq'
GROUP BY state;
"
```

### 10.4 Vacuum and Analyze (Maintenance)

```bash
# Run vacuum analyze (do this weekly)
psql -h localhost -U datamiq_user -d datamiq -c "VACUUM ANALYZE;"
```

### 10.5 Setup Auto-Vacuum

```bash
sudo nano /etc/postgresql/14/main/postgresql.conf
```

Ensure these are enabled:

```conf
autovacuum = on
autovacuum_max_workers = 3
autovacuum_naptime = 1min
```

## Step 11: Restore from Backup (If Needed)

### 11.1 Restore Database

```bash
# Stop application first
pm2 stop all

# Drop and recreate database
sudo -u postgres psql -c "DROP DATABASE IF EXISTS datamiq;"
sudo -u postgres psql -c "CREATE DATABASE datamiq OWNER datamiq_user;"

# Restore from backup
gunzip -c /var/backups/postgresql/datamiq_YYYYMMDD_HHMMSS.backup.gz | \
    pg_restore -U datamiq_user -d datamiq

# Restart application
pm2 restart all
```

## Step 12: Useful PostgreSQL Commands

### Database Management

```bash
# Connect to database
psql -h localhost -U datamiq_user -d datamiq

# List databases
\l

# List tables
\dt

# Describe table
\d table_name

# List users
\du

# Show current database
SELECT current_database();

# Show current user
SELECT current_user;

# Exit
\q
```

### Performance Queries

```sql
-- Show slow queries
SELECT pid, now() - pg_stat_activity.query_start AS duration, query 
FROM pg_stat_activity 
WHERE state = 'active' 
ORDER BY duration DESC;

-- Show table sizes
SELECT 
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Show index usage
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
```

## Troubleshooting

### Issue: Can't connect to PostgreSQL

```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Check PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-14-main.log

# Restart PostgreSQL
sudo systemctl restart postgresql
```

### Issue: Authentication failed

```bash
# Reset user password
sudo -u postgres psql
ALTER USER datamiq_user WITH PASSWORD 'new_password';
\q

# Update .env file with new password
```

### Issue: Out of disk space

```bash
# Check disk usage
df -h

# Check PostgreSQL data directory size
sudo du -sh /var/lib/postgresql/14/main/

# Clean old backups
sudo find /var/backups/postgresql -name "*.backup.gz" -mtime +7 -delete

# Vacuum database
psql -h localhost -U datamiq_user -d datamiq -c "VACUUM FULL;"
```

### Issue: Slow queries

```bash
# Enable query logging temporarily
sudo nano /etc/postgresql/14/main/postgresql.conf

# Set:
log_statement = 'all'
log_duration = on
log_min_duration_statement = 1000  # Log queries > 1 second

# Restart
sudo systemctl restart postgresql

# Check logs
sudo tail -f /var/log/postgresql/postgresql-14-main.log
```

## Quick Reference Commands

```bash
# Start PostgreSQL
sudo systemctl start postgresql

# Stop PostgreSQL
sudo systemctl stop postgresql

# Restart PostgreSQL
sudo systemctl restart postgresql

# Check status
sudo systemctl status postgresql

# Connect to database
psql -h localhost -U datamiq_user -d datamiq

# Run backup
sudo -u postgres /usr/local/bin/backup-postgres.sh

# Check database size
psql -h localhost -U datamiq_user -d datamiq -c "SELECT pg_size_pretty(pg_database_size('datamiq'));"

# Run migrations
cd ~/datamiq/backend && source .venv/bin/activate && alembic upgrade head
```

## Summary Checklist

- [ ] PostgreSQL installed and running
- [ ] Database `datamiq` created
- [ ] User `datamiq_user` created with password
- [ ] Privileges granted
- [ ] Backend .env configured
- [ ] Database connection tested
- [ ] Migrations run successfully
- [ ] Tables created and verified
- [ ] Performance tuning applied
- [ ] Backups configured
- [ ] Security hardened
- [ ] Monitoring setup

## Next Steps

1. Run the application deployment script: `./deploy-ec2.sh`
2. Verify application can connect to database
3. Test creating assessments and connections
4. Monitor database performance
5. Setup regular maintenance schedule

Your PostgreSQL database is now ready for production use on EC2!
