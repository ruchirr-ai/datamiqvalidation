"""
Agent Repository

Database operations for DataSync agents
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from datetime import datetime

from models.datasync_agent import DataSyncAgent


class AgentRepository:
    """Repository for DataSync agent database operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def register_agent(
        self,
        workspace_id: int,
        vm_ip: str,
        agent_arn: str,
        aws_region: str,
        status: str = 'online'
    ) -> DataSyncAgent:
        """Register a new DataSync agent or return existing one"""
        # Check if agent with this VM IP already exists for this workspace
        existing_agent = self.get_agent_by_vm_ip(vm_ip, workspace_id)
        
        if existing_agent:
            # Update last_used_at and return existing agent
            existing_agent.last_used_at = datetime.utcnow()
            existing_agent.status = status
            self.db.commit()
            self.db.refresh(existing_agent)
            return existing_agent
        
        # Create new agent
        agent = DataSyncAgent(
            workspace_id=workspace_id,
            vm_ip=vm_ip,
            agent_arn=agent_arn,
            aws_region=aws_region,
            status=status,
            created_at=datetime.utcnow(),
            last_used_at=datetime.utcnow()
        )
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)
        return agent
    
    def get_agent_by_id(
        self,
        agent_id: int,
        workspace_id: int
    ) -> Optional[DataSyncAgent]:
        """Get agent by ID with workspace isolation"""
        return self.db.query(DataSyncAgent).filter(
            and_(
                DataSyncAgent.id == agent_id,
                DataSyncAgent.workspace_id == workspace_id
            )
        ).first()
    
    def get_agent_by_vm_ip(
        self,
        vm_ip: str,
        workspace_id: int
    ) -> Optional[DataSyncAgent]:
        """Get agent by VM IP with workspace isolation"""
        return self.db.query(DataSyncAgent).filter(
            and_(
                DataSyncAgent.vm_ip == vm_ip,
                DataSyncAgent.workspace_id == workspace_id
            )
        ).first()
    
    def get_agent_by_arn(
        self,
        agent_arn: str,
        workspace_id: int
    ) -> Optional[DataSyncAgent]:
        """Get agent by ARN with workspace isolation"""
        return self.db.query(DataSyncAgent).filter(
            and_(
                DataSyncAgent.agent_arn == agent_arn,
                DataSyncAgent.workspace_id == workspace_id
            )
        ).first()
    
    def list_agents(
        self,
        workspace_id: int,
        status: Optional[str] = None
    ) -> List[DataSyncAgent]:
        """List all agents for a workspace with optional status filter"""
        query = self.db.query(DataSyncAgent).filter(
            DataSyncAgent.workspace_id == workspace_id
        )
        
        if status:
            query = query.filter(DataSyncAgent.status == status)
        
        return query.order_by(DataSyncAgent.created_at.desc()).all()
    
    def update_agent_status(
        self,
        agent_id: int,
        workspace_id: int,
        status: str
    ) -> Optional[DataSyncAgent]:
        """Update agent status"""
        agent = self.get_agent_by_id(agent_id, workspace_id)
        if not agent:
            return None
        
        agent.status = status
        agent.last_used_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(agent)
        return agent
    
    def update_last_used(
        self,
        agent_id: int,
        workspace_id: int
    ) -> Optional[DataSyncAgent]:
        """Update agent last_used_at timestamp"""
        agent = self.get_agent_by_id(agent_id, workspace_id)
        if not agent:
            return None
        
        agent.last_used_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(agent)
        return agent
    
    def delete_agent(
        self,
        agent_id: int,
        workspace_id: int
    ) -> bool:
        """Delete an agent if not in use"""
        agent = self.get_agent_by_id(agent_id, workspace_id)
        if not agent:
            return False
        
        # Check if agent is used by any active migrations
        # This would require checking TaskHistory for active tasks using this agent
        from models.task_history import TaskHistory
        
        active_tasks = self.db.query(TaskHistory).filter(
            and_(
                TaskHistory.agent_arn == agent.agent_arn,
                TaskHistory.status.in_(['running', 'pending'])
            )
        ).count()
        
        if active_tasks > 0:
            # Agent is in use, cannot delete
            return False
        
        self.db.delete(agent)
        self.db.commit()
        return True
    
    def is_agent_in_use(
        self,
        agent_id: int,
        workspace_id: int
    ) -> bool:
        """Check if agent is currently in use by any active migrations"""
        agent = self.get_agent_by_id(agent_id, workspace_id)
        if not agent:
            return False
        
        from models.task_history import TaskHistory
        
        active_tasks = self.db.query(TaskHistory).filter(
            and_(
                TaskHistory.agent_arn == agent.agent_arn,
                TaskHistory.status.in_(['running', 'pending'])
            )
        ).count()
        
        return active_tasks > 0
