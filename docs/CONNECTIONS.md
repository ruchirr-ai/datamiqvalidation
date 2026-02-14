# Connections Module

## Overview
The Connections module manages database connections for source and target systems.

## Supported Database Types

### Source Databases
- **BigQuery**: Google Cloud BigQuery
- **PostgreSQL**: PostgreSQL databases
- **MySQL**: MySQL databases

### Target Databases
- **Redshift**: Amazon Redshift
- **PostgreSQL**: PostgreSQL databases

## Key Components

### Backend
- **Router**: `backend/routers/connections_router.py`
- **Repository**: `backend/repositories/connection_repository.py`
- **Model**: `backend/models/connection.py`
- **Encryption**: `backend/services/encryption_service.py`

### Frontend
- **Page**: `frontend/src/pages/ConnectionsPage.tsx`
- **Components**: `frontend/src/components/connections/`

## Features

- ✅ Connection management (CRUD)
- ✅ Connection testing
- ✅ Encrypted credential storage
- ✅ Status tracking
- ✅ Field configuration
- ✅ Connection validation

## Security

### Encryption
- All passwords encrypted using AWS KMS
- Connection strings encrypted at rest
- Credentials never logged
- Secure parameter handling

### AWS Integration
- KMS for key management
- Secrets Manager for credential storage
- IAM roles for service access

## Connection Configuration

### BigQuery
Required fields:
- Project ID
- Service Account JSON
- Dataset (optional)

### Redshift
Required fields:
- Host
- Port
- Database
- Username
- Password
- IAM Role ARN (for COPY operations)

### PostgreSQL
Required fields:
- Host
- Port
- Database
- Username
- Password

## API Endpoints

- `POST /api/connections/` - Create connection
- `GET /api/connections/` - List connections
- `GET /api/connections/{id}` - Get connection details
- `PUT /api/connections/{id}` - Update connection
- `DELETE /api/connections/{id}` - Delete connection
- `POST /api/connections/{id}/test` - Test connection
- `GET /api/connections/{id}/status` - Get connection status

## Field Configuration

Dynamic field configuration allows customization of connection forms based on database type. Managed through:
- `backend/routers/field_config_router.py`
- `frontend/src/services/fieldConfigApi.ts`
