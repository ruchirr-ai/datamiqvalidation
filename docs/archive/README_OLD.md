# Database Migrator Tool

A comprehensive database migration tool that enables seamless data migration from any database to any database.

## Architecture

### Backend (Python + FastAPI)
- **Connections**: Database connection management
- **Assessment**: Migration assessment and reporting
- **Projects**: Migration project management
- **Tasks**: Migration task execution
- **Monitoring**: Real-time migration monitoring
- **Validation**: Post-migration validation

### Frontend (React)
- Modular React application with TypeScript
- Feature-based organization matching backend modules

## Getting Started

### Backend Setup
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend Setup
```bash
cd frontend
npm install
npm start
```

## Development

See `.kiro/steering/` for development standards and best practices.
