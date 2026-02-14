#!/bin/bash
# Start all DataMIQ microservices
# Usage: ./scripts/start-all-services.sh

set -e

echo "Starting DataMIQ Microservices..."

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Function to start a service
start_service() {
    local service_name=$1
    local service_port=$2
    local service_path=$3
    
    echo "Starting $service_name on port $service_port..."
    
    # Start service in background
    SERVICE_NAME=$service_name SERVICE_PORT=$service_port \
    uvicorn $service_path:app --host 0.0.0.0 --port $service_port \
    --log-level info > logs/${service_name}.log 2>&1 &
    
    echo $! > pids/${service_name}.pid
    echo "$service_name started (PID: $(cat pids/${service_name}.pid))"
}

# Create directories for logs and PIDs
mkdir -p logs pids

# Start all services
start_service "auth-service" 8001 "services.auth.main"
sleep 2

start_service "connection-service" 8002 "services.connections.main"
sleep 2

start_service "assessment-service" 8003 "services.assessment.main"
sleep 2

start_service "migration-service" 8004 "services.migration.main"
sleep 2

start_service "monitoring-service" 8005 "services.monitoring.main"
sleep 2

start_service "validation-service" 8006 "services.validation.main"
sleep 2

# Start API Gateway
start_service "api-gateway" 8000 "gateway.main"

echo ""
echo "All services started successfully!"
echo ""
echo "Service URLs:"
echo "  API Gateway:        http://localhost:8000"
echo "  Auth Service:       http://localhost:8001"
echo "  Connection Service: http://localhost:8002"
echo "  Assessment Service: http://localhost:8003"
echo "  Migration Service:  http://localhost:8004"
echo "  Monitoring Service: http://localhost:8005"
echo "  Validation Service: http://localhost:8006"
echo ""
echo "Logs are available in: ./logs/"
echo "To stop all services: ./scripts/stop-all-services.sh"
