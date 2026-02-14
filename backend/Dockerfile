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

# Run database migrations
RUN python -c "print('Migrations will run at startup')"

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV APP_PORT=8080

# Expose port 8080 (App Runner default)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run migrations and start application
CMD alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8080
