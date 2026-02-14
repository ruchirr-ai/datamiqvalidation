// PM2 Ecosystem Configuration for DataMIQ Microservices
// Usage: pm2 start ecosystem.config.js

module.exports = {
  apps: [
    {
      name: 'api-gateway',
      script: 'uvicorn',
      args: 'gateway.main:app --host 0.0.0.0 --port 8000',
      interpreter: 'python3',
      env: {
        SERVICE_NAME: 'api-gateway',
        SERVICE_PORT: '8000'
      },
      instances: 2,
      exec_mode: 'cluster',
      max_memory_restart: '500M',
      error_file: './logs/api-gateway-error.log',
      out_file: './logs/api-gateway-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'auth-service',
      script: 'uvicorn',
      args: 'services.auth.main:app --host 0.0.0.0 --port 8001',
      interpreter: 'python3',
      env: {
        SERVICE_NAME: 'auth-service',
        SERVICE_PORT: '8001'
      },
      instances: 2,
      exec_mode: 'cluster',
      max_memory_restart: '500M',
      error_file: './logs/auth-service-error.log',
      out_file: './logs/auth-service-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'connection-service',
      script: 'uvicorn',
      args: 'services.connections.main:app --host 0.0.0.0 --port 8002',
      interpreter: 'python3',
      env: {
        SERVICE_NAME: 'connection-service',
        SERVICE_PORT: '8002'
      },
      instances: 2,
      exec_mode: 'cluster',
      max_memory_restart: '500M',
      error_file: './logs/connection-service-error.log',
      out_file: './logs/connection-service-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'assessment-service',
      script: 'uvicorn',
      args: 'services.assessment.main:app --host 0.0.0.0 --port 8003',
      interpreter: 'python3',
      env: {
        SERVICE_NAME: 'assessment-service',
        SERVICE_PORT: '8003'
      },
      instances: 2,
      exec_mode: 'cluster',
      max_memory_restart: '500M',
      error_file: './logs/assessment-service-error.log',
      out_file: './logs/assessment-service-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'migration-service',
      script: 'uvicorn',
      args: 'services.migration.main:app --host 0.0.0.0 --port 8004',
      interpreter: 'python3',
      env: {
        SERVICE_NAME: 'migration-service',
        SERVICE_PORT: '8004'
      },
      instances: 2,
      exec_mode: 'cluster',
      max_memory_restart: '1G',
      error_file: './logs/migration-service-error.log',
      out_file: './logs/migration-service-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'monitoring-service',
      script: 'uvicorn',
      args: 'services.monitoring.main:app --host 0.0.0.0 --port 8005',
      interpreter: 'python3',
      env: {
        SERVICE_NAME: 'monitoring-service',
        SERVICE_PORT: '8005'
      },
      instances: 2,
      exec_mode: 'cluster',
      max_memory_restart: '500M',
      error_file: './logs/monitoring-service-error.log',
      out_file: './logs/monitoring-service-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'validation-service',
      script: 'uvicorn',
      args: 'services.validation.main:app --host 0.0.0.0 --port 8006',
      interpreter: 'python3',
      env: {
        SERVICE_NAME: 'validation-service',
        SERVICE_PORT: '8006'
      },
      instances: 2,
      exec_mode: 'cluster',
      max_memory_restart: '500M',
      error_file: './logs/validation-service-error.log',
      out_file: './logs/validation-service-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    }
  ]
};
