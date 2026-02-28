# Backend Dockerfile for BigQuery to Redshift Migration Tool
# Optimized for AWS App Runner

FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files
COPY requirements.txt requirements_bq_redshift.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements_bq_redshift.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV APP_PORT=8080

# Expose port 8080 (App Runner default)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Create startup script with better error handling and diagnostics
RUN echo '#!/bin/bash\n\
echo "=== DataMIQ Backend Startup ==="\n\
echo "Time: $(date)"\n\
echo ""\n\
\n\
# Print environment variables (sanitized)\n\
echo "Environment Configuration:"\n\
echo "  APP_DB_HOST: ${APP_DB_HOST:-NOT_SET}"\n\
echo "  APP_DB_PORT: ${APP_DB_PORT:-NOT_SET}"\n\
echo "  APP_DB_NAME: ${APP_DB_NAME:-NOT_SET}"\n\
echo "  APP_DB_USER: ${APP_DB_USER:-NOT_SET}"\n\
echo "  APP_DB_PASSWORD: ${APP_DB_PASSWORD:+***SET***}"\n\
echo "  REDIS_HOST: ${REDIS_HOST:-NOT_SET}"\n\
echo "  REDIS_PORT: ${REDIS_PORT:-NOT_SET}"\n\
echo "  JWT_SECRET_KEY: ${JWT_SECRET_KEY:+***SET***}"\n\
echo "  APP_PORT: ${APP_PORT:-8080}"\n\
echo ""\n\
\n\
# Check if required environment variables are set\n\
if [ -z "$APP_DB_HOST" ] || [ -z "$APP_DB_NAME" ] || [ -z "$APP_DB_USER" ]; then\n\
    echo "ERROR: Missing required environment variables!"\n\
    echo "Required: APP_DB_HOST, APP_DB_NAME, APP_DB_USER"\n\
    exit 1\n\
fi\n\
\n\
# Test database connectivity\n\
echo "Testing database connectivity..."\n\
python3 << EOF\n\
import sys\n\
import psycopg2\n\
try:\n\
    conn = psycopg2.connect(\n\
        host="${APP_DB_HOST}",\n\
        port="${APP_DB_PORT:-5432}",\n\
        database="${APP_DB_NAME}",\n\
        user="${APP_DB_USER}",\n\
        password="${APP_DB_PASSWORD}",\n\
        connect_timeout=10\n\
    )\n\
    conn.close()\n\
    print("✓ Database connection successful")\n\
    sys.exit(0)\n\
except Exception as e:\n\
    print(f"✗ Database connection failed: {e}")\n\
    sys.exit(1)\n\
EOF\n\
\n\
DB_TEST_RESULT=$?\n\
if [ $DB_TEST_RESULT -ne 0 ]; then\n\
    echo ""\n\
    echo "ERROR: Cannot connect to database!"\n\
    echo "Please verify:"\n\
    echo "  1. Database is running at ${APP_DB_HOST}:${APP_DB_PORT}"\n\
    echo "  2. Database ${APP_DB_NAME} exists"\n\
    echo "  3. User ${APP_DB_USER} has access"\n\
    echo "  4. Network allows connection from App Runner"\n\
    echo ""\n\
    exit 1\n\
fi\n\
\n\
echo ""\n\
\n\
# Run database migrations (non-blocking)\n\
echo "Running database migrations..."\n\
if alembic upgrade head 2>&1; then\n\
    echo "✓ Migrations completed successfully"\n\
else\n\
    echo "⚠ Migrations failed or already up to date (continuing anyway)"\n\
fi\n\
\n\
echo ""\n\
echo "Starting uvicorn server on port ${APP_PORT:-8080}..."\n\
echo "================================="\n\
echo ""\n\
\n\
# Start the application\n\
exec uvicorn main:app --host 0.0.0.0 --port ${APP_PORT:-8080} --log-level info\n\
' > /app/start.sh && chmod +x /app/start.sh

# Run startup script
CMD ["/app/start.sh"]
