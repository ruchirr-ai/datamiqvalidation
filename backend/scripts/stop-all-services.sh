#!/bin/bash
# Stop all DataMIQ microservices
# Usage: ./scripts/stop-all-services.sh

set -e

echo "Stopping DataMIQ Microservices..."

# Function to stop a service
stop_service() {
    local service_name=$1
    local pid_file="pids/${service_name}.pid"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null 2>&1; then
            echo "Stopping $service_name (PID: $pid)..."
            kill $pid
            rm "$pid_file"
            echo "$service_name stopped"
        else
            echo "$service_name is not running"
            rm "$pid_file"
        fi
    else
        echo "$service_name PID file not found"
    fi
}

# Stop all services
stop_service "api-gateway"
stop_service "validation-service"
stop_service "monitoring-service"
stop_service "migration-service"
stop_service "assessment-service"
stop_service "connection-service"
stop_service "auth-service"

echo ""
echo "All services stopped successfully!"
