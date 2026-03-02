"""
FastAPI Application Entry Point
Main application with authentication and CORS configuration
"""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from routers.auth_router import router as auth_router
from routers.connections_router import router as connections_router
from routers.field_config_router import router as field_config_router
from routers.bq_redshift_migration import router as bq_redshift_router
from routers.pathway_a_test_router import router as pathway_a_test_router
from routers.bq_export_test_router import router as bq_export_test_router
from routers.assessment_router import router as assessment_router
from database import db_instance

# Import all models to ensure they're registered with SQLAlchemy
from models.assessment import Assessment
from models.assessment_log import AssessmentLog
from models.connection import Connection

# Load environment variables
load_dotenv()

# Configure logging - use INFO level
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Lifespan event handler (replaces on_event)
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting DataMIQ API...")
    logger.info(f"Environment: {os.getenv('APP_ENV', 'development')}")
    
    # Test database connection
    try:
        with db_instance.get_session() as db:
            logger.info("Database connection successful")
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
    
    # Recover stuck "running" migrations from previous crashes
    try:
        from models.bq_redshift_migration import MigrationBQRedshift
        from datetime import datetime
        
        with db_instance.get_session() as db:
            stuck_migrations = db.query(MigrationBQRedshift).filter(
                MigrationBQRedshift.status == 'running'
            ).all()
            
            if stuck_migrations:
                logger.warning(f"Found {len(stuck_migrations)} stuck 'running' migration(s) from previous session — resetting to 'failed'")
                for mig in stuck_migrations:
                    logger.warning(f"  Resetting migration {mig.id} ('{mig.migration_name}') from 'running' to 'failed'")
                    mig.status = 'failed'
                    mig.end_time = datetime.utcnow()
                    mig.updated_at = datetime.utcnow()
                db.commit()
                logger.info("✓ Stuck migrations reset — they can now be resumed from the UI")
            else:
                logger.info("No stuck migrations found")
    except Exception as e:
        logger.error(f"Failed to recover stuck migrations: {str(e)}")
    
    # Start background scheduler for scheduled migrations
    import asyncio
    import threading
    
    async def check_scheduled_migrations():
        """Background task that checks for due scheduled migrations every 30 seconds."""
        while True:
            try:
                await asyncio.sleep(30)
                from models.bq_redshift_migration import MigrationBQRedshift
                from services.bq_redshift_migration.orchestrator import MigrationOrchestrator
                from datetime import datetime
                
                with db_instance.get_session() as db:
                    now = datetime.now()  # Use local time since frontend sends local datetime
                    due_migrations = db.query(MigrationBQRedshift).filter(
                        MigrationBQRedshift.status == 'scheduled',
                        MigrationBQRedshift.next_run_time.isnot(None),
                        MigrationBQRedshift.next_run_time <= now
                    ).all()
                    
                    for mig in due_migrations:
                        logger.info(f"Scheduled migration {mig.id} ('{mig.migration_name}') is due (scheduled: {mig.next_run_time}) — starting now")
                        
                        def run_scheduled_migration(mid: int):
                            bg_db = db_instance.SessionLocal()
                            try:
                                orchestrator = MigrationOrchestrator(bg_db)
                                orchestrator.start_migration(mid)
                            except Exception as ex:
                                logger.error(f"Scheduled migration {mid} failed: {ex}")
                                try:
                                    failed_mig = bg_db.query(MigrationBQRedshift).filter_by(id=mid).first()
                                    if failed_mig and failed_mig.status == 'running':
                                        failed_mig.status = 'failed'
                                        failed_mig.end_time = datetime.utcnow()
                                        failed_mig.updated_at = datetime.utcnow()
                                        bg_db.commit()
                                except Exception:
                                    pass
                            finally:
                                bg_db.close()
                        
                        thread = threading.Thread(target=run_scheduled_migration, args=(mig.id,), daemon=True)
                        thread.start()
                        
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
    
    # Run the scheduler as a background asyncio task
    asyncio.create_task(check_scheduled_migrations())
    logger.info("✓ Background migration scheduler started (checking every 30s)")
    
    yield
    
    # Shutdown
    logger.info("Shutting down DataMIQ API...")


# Create FastAPI application with lifespan
app = FastAPI(
    title="DataMIQ API",
    description="Database Migration Platform API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# Configure CORS
cors_origins = os.getenv('CORS_ORIGINS', 'http://localhost:3000').split(',')
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router)
app.include_router(connections_router)
app.include_router(field_config_router)
app.include_router(bq_redshift_router)
app.include_router(pathway_a_test_router)
app.include_router(bq_export_test_router)
app.include_router(assessment_router)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "datamiq-api",
        "version": "1.0.0"
    }

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "DataMIQ API",
        "version": "1.0.0",
        "docs": "/api/docs"
    }


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv('APP_PORT', '8000'))
    host = os.getenv('APP_HOST', '0.0.0.0')
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=os.getenv('APP_ENV') != 'production'
    )
