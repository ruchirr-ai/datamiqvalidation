"""
Database connection and session management
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Create declarative base for models
Base = declarative_base()


class Database:
    """Database connection manager"""
    
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self._initialize()
    
    def _initialize(self):
        """Initialize database connection"""
        # Get database configuration from environment
        db_host = os.getenv('APP_DB_HOST', 'localhost')
        db_port = os.getenv('APP_DB_PORT', '5432')
        db_name = os.getenv('APP_DB_NAME')
        db_user = os.getenv('APP_DB_USER')
        db_password = os.getenv('APP_DB_PASSWORD', '')
        
        if not db_name or not db_user:
            raise ValueError("Missing required database environment variables: APP_DB_NAME and APP_DB_USER")
        
        # Construct database URL
        if db_password:
            database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        else:
            database_url = f"postgresql://{db_user}@{db_host}:{db_port}/{db_name}"
        
        # Create engine with connection pooling
        self.engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=int(os.getenv('DB_POOL_SIZE', '20')),
            max_overflow=int(os.getenv('DB_POOL_MAX_OVERFLOW', '10')),
            pool_timeout=int(os.getenv('DB_POOL_TIMEOUT', '30')),
            pool_pre_ping=True,  # Verify connections before using
            echo=os.getenv('APP_ENV') == 'development'
        )
        
        # Create session factory
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        
        logger.info("Database connection initialized")
    
    @contextmanager
    def get_session(self):
        """Get database session with automatic cleanup"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_db(self):
        """Get database session (for FastAPI dependency injection)"""
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()


# Global database instance
db_instance = Database()


def get_db():
    """Get database session for dependency injection"""
    db = db_instance.SessionLocal()
    try:
        yield db
    finally:
        db.close()
