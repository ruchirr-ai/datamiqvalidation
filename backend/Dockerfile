# Backend Dockerfile for BigQuery to Redshift Migration Tool

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for package management
RUN pip install uv

# Copy requirements files
COPY requirements.txt requirements_bq_redshift.txt ./

# Create virtual environment and install dependencies
RUN uv venv .venv
RUN . .venv/bin/activate && \
    uv pip install -r requirements.txt && \
    uv pip install -r requirements_bq_redshift.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV PATH="/app/.venv/bin:$PATH"

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
