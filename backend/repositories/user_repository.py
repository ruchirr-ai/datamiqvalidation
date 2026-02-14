"""
User Repository
Handles database operations for users
"""

from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


class UserRepository:
    """Repository for user database operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_user(
        self,
        username: str,
        password_hash: str,
        role: str = "user"
    ) -> dict:
        """
        Create a new user in the database
        
        Args:
            username: User's username (must be unique)
            password_hash: Hashed password
            role: User's role (default: "user")
            
        Returns:
            Created user as dict
            
        Raises:
            Exception: If username already exists or database error
        """
        try:
            query = text("""
                INSERT INTO users (username, password_hash, role)
                VALUES (:username, :password_hash, :role)
                RETURNING id, username, password_hash, role, created_at, updated_at,
                          last_login, is_locked, failed_login_attempts, locked_until
            """)
            
            result = self.db.execute(
                query,
                {
                    "username": username,
                    "password_hash": password_hash,
                    "role": role
                }
            )
            
            row = result.fetchone()
            self.db.commit()
            
            return {
                "id": row[0],
                "username": row[1],
                "password_hash": row[2],
                "role": row[3],
                "created_at": row[4],
                "updated_at": row[5],
                "last_login": row[6],
                "is_locked": row[7],
                "failed_login_attempts": row[8],
                "locked_until": row[9]
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating user: {str(e)}")
            raise
    
    def get_user_by_username(self, username: str) -> Optional[dict]:
        """
        Get user by username
        
        Args:
            username: Username to search for
            
        Returns:
            User dict if found, None otherwise
        """
        try:
            query = text("""
                SELECT id, username, password_hash, role, created_at, updated_at,
                       last_login, is_locked, failed_login_attempts, locked_until
                FROM users
                WHERE username = :username
            """)
            
            result = self.db.execute(query, {"username": username})
            row = result.fetchone()
            
            if row is None:
                return None
            
            return {
                "id": row[0],
                "username": row[1],
                "password_hash": row[2],
                "role": row[3],
                "created_at": row[4],
                "updated_at": row[5],
                "last_login": row[6],
                "is_locked": row[7],
                "failed_login_attempts": row[8],
                "locked_until": row[9]
            }
            
        except Exception as e:
            logger.error(f"Error getting user by username: {str(e)}")
            return None
    
    def get_user_by_id(self, user_id: int) -> Optional[dict]:
        """
        Get user by ID
        
        Args:
            user_id: User ID to search for
            
        Returns:
            User dict if found, None otherwise
        """
        try:
            query = text("""
                SELECT id, username, password_hash, role, created_at, updated_at,
                       last_login, is_locked, failed_login_attempts, locked_until
                FROM users
                WHERE id = :user_id
            """)
            
            result = self.db.execute(query, {"user_id": user_id})
            row = result.fetchone()
            
            if row is None:
                return None
            
            return {
                "id": row[0],
                "username": row[1],
                "password_hash": row[2],
                "role": row[3],
                "created_at": row[4],
                "updated_at": row[5],
                "last_login": row[6],
                "is_locked": row[7],
                "failed_login_attempts": row[8],
                "locked_until": row[9]
            }
            
        except Exception as e:
            logger.error(f"Error getting user by ID: {str(e)}")
            return None
    
    def update_last_login(self, user_id: int) -> None:
        """
        Update user's last login timestamp
        
        Args:
            user_id: User ID to update
        """
        try:
            query = text("""
                UPDATE users
                SET last_login = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :user_id
            """)
            
            self.db.execute(query, {"user_id": user_id})
            self.db.commit()
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating last login: {str(e)}")
            raise
    
    def update_failed_attempts(self, user_id: int, attempts: int) -> None:
        """
        Update user's failed login attempts count
        
        Args:
            user_id: User ID to update
            attempts: New failed attempts count
        """
        try:
            query = text("""
                UPDATE users
                SET failed_login_attempts = :attempts,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :user_id
            """)
            
            self.db.execute(query, {"user_id": user_id, "attempts": attempts})
            self.db.commit()
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating failed attempts: {str(e)}")
            raise
    
    def lock_user(self, user_id: int, locked_until: datetime) -> None:
        """
        Lock user account until specified time
        
        Args:
            user_id: User ID to lock
            locked_until: Timestamp when lock expires
        """
        try:
            query = text("""
                UPDATE users
                SET is_locked = TRUE,
                    locked_until = :locked_until,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :user_id
            """)
            
            self.db.execute(
                query,
                {"user_id": user_id, "locked_until": locked_until}
            )
            self.db.commit()
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error locking user: {str(e)}")
            raise
    
    def unlock_user(self, user_id: int) -> None:
        """
        Unlock user account and reset failed attempts
        
        Args:
            user_id: User ID to unlock
        """
        try:
            query = text("""
                UPDATE users
                SET is_locked = FALSE,
                    locked_until = NULL,
                    failed_login_attempts = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :user_id
            """)
            
            self.db.execute(query, {"user_id": user_id})
            self.db.commit()
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error unlocking user: {str(e)}")
            raise
    
    def user_exists(self, username: str) -> bool:
        """
        Check if user exists by username
        
        Args:
            username: Username to check
            
        Returns:
            True if user exists, False otherwise
        """
        try:
            query = text("""
                SELECT EXISTS(SELECT 1 FROM users WHERE username = :username)
            """)
            
            result = self.db.execute(query, {"username": username})
            return result.scalar()
            
        except Exception as e:
            logger.error(f"Error checking user existence: {str(e)}")
            return False
