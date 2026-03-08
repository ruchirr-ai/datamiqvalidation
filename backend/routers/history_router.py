"""
History Router

API endpoints for Copy History, Task History, and DataSync Agent operations.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import logging

from database import get_db
from shared.middleware.auth_middleware import get_current_user, get_workspace_id
from services.history_service import HistoryService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["history"])


def get_history_service(db: Session = Depends(get_db)) -> HistoryService:
    """Dependency for HistoryService"""
    # TODO: Add Redis client
    return HistoryService(db=db, redis_client=None)


# Copy History Endpoints

@router.get("/copy-history")
async def list_copy_history(
    migration_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    workspace_id: int = Depends(get_workspace_id),
    history_service: HistoryService = Depends(get_history_service)
):
    """
    List Copy History records with filters and pagination.
    
    Query Parameters:
    - migration_id: Filter by migration ID
    - status: Filter by status (running, completed, failed)
    - start_date: Filter by started_at >= start_date
    - end_date: Filter by started_at <= end_date
    - page: Page number (default 1)
    - page_size: Items per page (default 50, max 200)
    """
    try:
        result = await history_service.list_copy_history(
            workspace_id=workspace_id,
            migration_id=migration_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to list copy history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list copy history")


@router.get("/copy-history/{id}")
async def get_copy_history_detail(
    id: int,
    workspace_id: int = Depends(get_workspace_id),
    history_service: HistoryService = Depends(get_history_service)
):
    """
    Get detailed Copy History record.
    
    Returns complete record including copy_command and error_details.
    """
    try:
        record = await history_service.get_copy_history_by_id(id, workspace_id)
        
        if not record:
            raise HTTPException(
                status_code=404,
                detail="Copy history record not found or access denied"
            )
        
        return record
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get copy history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get copy history")


# Task History Endpoints

@router.get("/task-history")
async def list_task_history(
    migration_id: Optional[int] = None,
    status: Optional[str] = None,
    agent_ip: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    workspace_id: int = Depends(get_workspace_id),
    history_service: HistoryService = Depends(get_history_service)
):
    """
    List Task History records with filters and pagination.
    
    Query Parameters:
    - migration_id: Filter by migration ID
    - status: Filter by status (running, completed, failed, agent_offline)
    - agent_ip: Filter by agent IP address
    - start_date: Filter by started_at >= start_date
    - end_date: Filter by started_at <= end_date
    - page: Page number (default 1)
    - page_size: Items per page (default 50, max 200)
    """
    try:
        result = await history_service.list_task_history(
            workspace_id=workspace_id,
            migration_id=migration_id,
            status=status,
            agent_ip=agent_ip,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to list task history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list task history")


@router.get("/task-history/{id}")
async def get_task_history_detail(
    id: int,
    workspace_id: int = Depends(get_workspace_id),
    history_service: HistoryService = Depends(get_history_service)
):
    """
    Get detailed Task History record.
    
    Returns complete record including raw_result JSONB and error_details.
    """
    try:
        record = await history_service.get_task_history_by_id(id, workspace_id)
        
        if not record:
            raise HTTPException(
                status_code=404,
                detail="Task history record not found or access denied"
            )
        
        return record
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get task history")


# DataSync Agent Endpoints

@router.post("/datasync-agents")
async def register_datasync_agent(
    vm_ip: str,
    aws_region: str = "us-east-1",
    workspace_id: int = Depends(get_workspace_id),
    current_user = Depends(get_current_user),
    history_service: HistoryService = Depends(get_history_service)
):
    """
    Register DataSync agent.
    
    Request Body:
    {
        "vm_ip": "10.0.1.50",
        "aws_region": "us-east-1"
    }
    
    Returns agent_arn (new or existing if VM IP already registered).
    """
    try:
        result = await history_service.register_datasync_agent(
            workspace_id=workspace_id,
            vm_ip=vm_ip,
            aws_region=aws_region
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to register agent: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to register agent")


@router.get("/datasync-agents")
async def list_datasync_agents(
    status: Optional[str] = None,
    workspace_id: int = Depends(get_workspace_id),
    history_service: HistoryService = Depends(get_history_service)
):
    """
    List registered DataSync agents.
    
    Query Parameters:
    - status: Filter by status (online, offline, unknown)
    """
    try:
        agents = await history_service.list_datasync_agents(
            workspace_id=workspace_id,
            status=status
        )
        
        return {'agents': agents, 'total': len(agents)}
        
    except Exception as e:
        logger.error(f"Failed to list agents: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list agents")


@router.delete("/datasync-agents/{id}")
async def delete_datasync_agent(
    id: int,
    workspace_id: int = Depends(get_workspace_id),
    current_user = Depends(get_current_user),
    history_service: HistoryService = Depends(get_history_service)
):
    """
    Delete DataSync agent.
    
    Returns 409 Conflict if agent is used by active migrations.
    """
    try:
        result = await history_service.delete_datasync_agent(id, workspace_id)
        
        if not result['success']:
            if 'in use' in result.get('message', '').lower():
                raise HTTPException(status_code=409, detail=result['message'])
            raise HTTPException(status_code=404, detail=result['message'])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete agent: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete agent")
