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

# Create startup script
RUN echo '#!/bin/bash\n\
set -e\n\
echo "Starting application..."\n\
echo "Database host: $APP_DB_HOST"\n\
echo "Database name: $APP_DB_NAME"\n\
\n\
# Try to run migrations, but dont fail if they error\n\
echo "Running database migrations..."\n\
alembic upgrade head || echo "Migrations failed or already up to date"\n\
\n\
# Start the application\n\
echo "Starting uvicorn server on port 8080..."\n\
exec uvicorn main:app --host 0.0.0.0 --port 8080\n\
' > /app/start.sh && chmod +x /app/start.sh

# Run startup script
CMD ["/app/start.sh"]
