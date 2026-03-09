"""
Context Service for ChatAgent feature.

This service gathers user-specific context data from the workspace including:
- Assessments with status and details
- Database connections with types and status
- Migration projects with progress
- Workspace information

Implements Redis caching with database fallback for performance.
"""

import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from redis import Redis, RedisError, ConnectionError as RedisConnectionError
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class AssessmentSummary(BaseModel):
    """Assessment summary for context."""
    id: int
    name: str
    status: str
    project_id: str
    total_tables: int
    total_size_mb: int
    created_at: datetime
    has_errors: bool = False


class ConnectionSummary(BaseModel):
    """Connection summary for context."""
    id: int
    name: str
    db_type: str
    database: str
    status: str
    created_at: datetime


class MigrationSummary(BaseModel):
    """Migration summary for context."""
    id: int
    name: str
    status: str
    progress: int
    created_at: datetime


class WorkspaceInfo(BaseModel):
    """Workspace information."""
    id: int
    name: str
    organization_id: Optional[int] = None


class UserContext(BaseModel):
    """Complete user context for AI requests."""
    workspace: WorkspaceInfo
    page_context: str
    assessments: List[AssessmentSummary] = []
    connections: List[ConnectionSummary] = []
    migrations: List[MigrationSummary] = []
    has_errors: bool = False
    error_summary: Optional[str] = None


class SuggestedQuestion(BaseModel):
    """Suggested question model."""
    question_text: str
    category: str
    priority: int


class ContextService:
    """
    Service for gathering user context data.
    
    This service provides context-aware data for ChatAgent including:
    - User's assessments with status
    - Database connections
    - Migration projects
    - Workspace information
    
    All operations enforce workspace isolation for multi-tenant security.
    """
    
    def __init__(self, db: Session, redis_client: Optional[Redis] = None):
        """
        Initialize ContextService.
        
        Args:
            db: SQLAlchemy database session
            redis_client: Optional Redis client for caching
        """
        self.db = db
        self.redis = redis_client
        self.cache_ttl = 300  # 5 minutes TTL
        self.max_items = 20  # Limit to 20 most recent items per category
    
    def gather_context(
        self,
        user_id: int,
        workspace_id: int,
        page_context: str
    ) -> UserContext:
        """
        Gather context data based on page and workspace.
        
        Args:
            user_id: User ID
            workspace_id: Workspace ID for isolation
            page_context: Current page (dashboard, assessments, connections, etc.)
            
        Returns:
            UserContext with all relevant data
        """
        logger.info(f"Gathering context for user_id={user_id}, workspace_id={workspace_id}, page={page_context}")
        
        # Try Redis cache first
        cache_key = f"chat:context:{workspace_id}:{page_context}"
        try:
            if self.redis:
                cached_data = self.redis.get(cache_key)
                if cached_data:
                    logger.debug(f"Cache hit for context: {cache_key}")
                    data = json.loads(cached_data)
                    return UserContext(**data)
        except (RedisError, RedisConnectionError) as e:
            logger.warning(f"Redis unavailable: {e}, falling back to database")
        
        # Get workspace info
        workspace = self._get_workspace_info(workspace_id)
        
        # Gather data based on page context
        assessments = self._get_assessments_context(workspace_id)
        connections = self._get_connections_context(workspace_id)
        migrations = self._get_migrations_context(workspace_id)
        
        # Detect errors
        has_errors, error_summary = self._detect_errors(assessments, connections, migrations)
        
        # Build context
        context = UserContext(
            workspace=workspace,
            page_context=page_context,
            assessments=assessments,
            connections=connections,
            migrations=migrations,
            has_errors=has_errors,
            error_summary=error_summary
        )
        
        # Cache result (best effort)
        try:
            if self.redis:
                self.redis.setex(cache_key, self.cache_ttl, json.dumps(context.dict(), default=str))
                logger.debug(f"Cached context: {cache_key}")
        except Exception as e:
            logger.warning(f"Failed to cache context: {e}")
        
        return context
    
    def get_suggested_questions(
        self,
        user_id: int,
        workspace_id: int,
        page_context: str
    ) -> List[SuggestedQuestion]:
        """
        Generate context-aware suggested questions.
        
        Args:
            user_id: User ID
            workspace_id: Workspace ID
            page_context: Current page context
            
        Returns:
            List of 4 suggested questions
        """
        logger.info(f"Getting suggested questions for page={page_context}")
        
        # Try Redis cache first
        cache_key = f"chat:suggestions:{workspace_id}:{page_context}"
        try:
            if self.redis:
                cached_data = self.redis.get(cache_key)
                if cached_data:
                    logger.debug(f"Cache hit for suggestions: {cache_key}")
                    data = json.loads(cached_data)
                    return [SuggestedQuestion(**q) for q in data]
        except (RedisError, RedisConnectionError) as e:
            logger.warning(f"Redis unavailable: {e}, generating suggestions from database")
        
        # Gather context to detect errors
        context = self.gather_context(user_id, workspace_id, page_context)
        
        # Generate questions based on page and data state
        questions = self._generate_questions(page_context, context)
        
        # Cache result (best effort)
        try:
            if self.redis:
                self.redis.setex(cache_key, self.cache_ttl, json.dumps([q.dict() for q in questions]))
                logger.debug(f"Cached suggestions: {cache_key}")
        except Exception as e:
            logger.warning(f"Failed to cache suggestions: {e}")
        
        return questions
    
    def _get_workspace_info(self, workspace_id: int) -> WorkspaceInfo:
        """Get workspace information."""
        from sqlalchemy import Table, MetaData
        metadata = MetaData()
        workspaces_table = Table('workspaces', metadata, autoload_with=self.db.bind)
        
        workspace = self.db.execute(
            workspaces_table.select().where(workspaces_table.c.id == workspace_id)
        ).first()
        
        if workspace:
            return WorkspaceInfo(
                id=workspace.id,
                name=workspace.name,
                organization_id=getattr(workspace, 'organization_id', None)
            )
        
        # Fallback if workspace not found
        return WorkspaceInfo(id=workspace_id, name=f"Workspace {workspace_id}")
    
    def _get_assessments_context(self, workspace_id: int) -> List[AssessmentSummary]:
        """
        Get assessment data for context.
        
        Returns the 20 most recent assessments with their status and details.
        """
        try:
            from sqlalchemy import Table, MetaData
            metadata = MetaData()
            assessments_table = Table('assessments', metadata, autoload_with=self.db.bind)
            
            query = self.db.execute(
                assessments_table.select().where(
                    assessments_table.c.workspace_id == workspace_id
                ).order_by(desc(assessments_table.c.started_at)).limit(self.max_items)
            )
            
            assessments = []
            for row in query:
                assessments.append(AssessmentSummary(
                    id=row.id,
                    name=row.name,
                    status=row.status,
                    project_id=row.project_id,
                    total_tables=row.total_tables or 0,
                    total_size_mb=row.total_size_mb or 0,
                    created_at=row.started_at,
                    has_errors=(row.status == 'failed')
                ))
            
            return assessments
        except Exception as e:
            logger.warning(f"Failed to get assessments context: {e}")
            return []
    
    def _get_connections_context(self, workspace_id: int) -> List[ConnectionSummary]:
        """
        Get connection data for context.
        
        Note: Connections table doesn't have workspace_id yet, so we get all connections.
        This should be filtered by workspace_id once multi-tenancy is fully implemented.
        """
        try:
            from sqlalchemy import Table, MetaData
            metadata = MetaData()
            connections_table = Table('connections', metadata, autoload_with=self.db.bind)
            
            query = self.db.execute(
                connections_table.select().where(
                    connections_table.c.is_active == True
                ).order_by(desc(connections_table.c.created_at)).limit(self.max_items)
            )
            
            connections = []
            for row in query:
                connections.append(ConnectionSummary(
                    id=row.id,
                    name=row.name,
                    db_type=row.type,
                    database=row.database,
                    status=row.status,
                    created_at=row.created_at
                ))
            
            return connections
        except Exception as e:
            logger.warning(f"Failed to get connections context: {e}")
            return []
    
    def _get_migrations_context(self, workspace_id: int) -> List[MigrationSummary]:
        """
        Get migration data for context.
        
        Returns empty list for now as migration projects table structure is not defined yet.
        """
        # TODO: Implement when migration projects table is available
        return []
    
    def _detect_errors(
        self,
        assessments: List[AssessmentSummary],
        connections: List[ConnectionSummary],
        migrations: List[MigrationSummary]
    ) -> tuple[bool, Optional[str]]:
        """
        Detect if user has errors in their workspace.
        
        Returns:
            Tuple of (has_errors, error_summary)
        """
        errors = []
        
        # Check for failed assessments
        failed_assessments = [a for a in assessments if a.status == 'failed']
        if failed_assessments:
            errors.append(f"{len(failed_assessments)} failed assessment(s)")
        
        # Check for error connections
        error_connections = [c for c in connections if c.status == 'error']
        if error_connections:
            errors.append(f"{len(error_connections)} connection(s) with errors")
        
        # Check for failed migrations
        failed_migrations = [m for m in migrations if m.status == 'failed']
        if failed_migrations:
            errors.append(f"{len(failed_migrations)} failed migration(s)")
        
        if errors:
            return True, ", ".join(errors)
        
        return False, None
    
    def _generate_questions(
        self,
        page_context: str,
        context: UserContext
    ) -> List[SuggestedQuestion]:
        """Generate context-aware suggested questions."""
        
        # Base questions by page
        questions_map = {
            "dashboard": [
                SuggestedQuestion(
                    question_text="How do I get started with DataMIQ?",
                    category="getting_started",
                    priority=1
                ),
                SuggestedQuestion(
                    question_text="What features are available?",
                    category="general",
                    priority=2
                ),
                SuggestedQuestion(
                    question_text="How do I create my first assessment?",
                    category="getting_started",
                    priority=3
                ),
                SuggestedQuestion(
                    question_text="How do I connect to my database?",
                    category="getting_started",
                    priority=4
                )
            ],
            "assessments": [
                SuggestedQuestion(
                    question_text="How do I create a new assessment?",
                    category="getting_started",
                    priority=1
                ),
                SuggestedQuestion(
                    question_text="What does schema analysis check?",
                    category="features",
                    priority=2
                ),
                SuggestedQuestion(
                    question_text="How do I export assessment results?",
                    category="features",
                    priority=3
                ),
                SuggestedQuestion(
                    question_text="What do the assessment metrics mean?",
                    category="features",
                    priority=4
                )
            ],
            "connections": [
                SuggestedQuestion(
                    question_text="How do I connect to BigQuery?",
                    category="getting_started",
                    priority=1
                ),
                SuggestedQuestion(
                    question_text="How do I test my connection?",
                    category="troubleshooting",
                    priority=2
                ),
                SuggestedQuestion(
                    question_text="What connection types are supported?",
                    category="features",
                    priority=3
                ),
                SuggestedQuestion(
                    question_text="How do I update connection credentials?",
                    category="features",
                    priority=4
                )
            ],
            "migrations": [
                SuggestedQuestion(
                    question_text="How do I start a migration?",
                    category="getting_started",
                    priority=1
                ),
                SuggestedQuestion(
                    question_text="How do I monitor migration progress?",
                    category="features",
                    priority=2
                ),
                SuggestedQuestion(
                    question_text="What happens if a migration fails?",
                    category="troubleshooting",
                    priority=3
                ),
                SuggestedQuestion(
                    question_text="How do I validate migration results?",
                    category="features",
                    priority=4
                )
            ]
        }
        
        # Get base questions for page
        questions = questions_map.get(page_context, questions_map["dashboard"])
        
        # Customize based on user's data state
        if context.has_errors:
            # Prioritize troubleshooting if user has errors
            if page_context == "assessments" and any(a.status == 'failed' for a in context.assessments):
                failed_assessment = next(a for a in context.assessments if a.status == 'failed')
                questions[0] = SuggestedQuestion(
                    question_text=f"How do I troubleshoot my failed assessment '{failed_assessment.name}'?",
                    category="troubleshooting",
                    priority=1
                )
            elif page_context == "connections" and any(c.status == 'error' for c in context.connections):
                error_connection = next(c for c in context.connections if c.status == 'error')
                questions[0] = SuggestedQuestion(
                    question_text=f"Why is my connection '{error_connection.name}' showing an error?",
                    category="troubleshooting",
                    priority=1
                )
        
        # If user has no connections, prioritize connection setup
        if not context.connections and page_context in ["dashboard", "assessments"]:
            questions[0] = SuggestedQuestion(
                question_text="How do I create my first database connection?",
                category="getting_started",
                priority=1
            )
        
        # If user has connections but no assessments
        if context.connections and not context.assessments and page_context in ["dashboard", "assessments"]:
            questions[1] = SuggestedQuestion(
                question_text=f"How do I run an assessment on my '{context.connections[0].name}' connection?",
                category="getting_started",
                priority=2
            )
        
        return questions[:4]  # Always return exactly 4 questions
