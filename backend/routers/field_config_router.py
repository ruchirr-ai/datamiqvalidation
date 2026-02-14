"""
Field Configuration Router
Handles field configuration management for database connection forms
"""

import logging
from typing import List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models.field_configuration import FieldConfiguration

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/field-configs", tags=["field-configs"])


# Request/Response Models
class FieldConfigRequest(BaseModel):
    """Request model for creating/updating field configuration"""
    name: str = Field(..., description="Field name (used as form field key)")
    label: str = Field(..., description="Display label")
    type: str = Field(..., description="Field type (text, number, password, etc.)")
    enabled: bool = Field(default=True, description="Whether field is enabled")
    required: bool = Field(default=False, description="Whether field is required")
    default_value: str | None = Field(default=None, description="Default value")
    placeholder: str | None = Field(default=None, description="Placeholder text")
    help_text: str | None = Field(default=None, description="Help text")
    display_order: int = Field(default=0, description="Display order")
    validation: Dict[str, Any] | None = Field(default=None, description="Validation rules")
    options: List[Dict[str, Any]] | None = Field(default=None, description="Options for select fields")


class FieldConfigUpdateRequest(BaseModel):
    """Request model for updating field configuration (all fields optional)"""
    name: str | None = Field(default=None, description="Field name (used as form field key)")
    label: str | None = Field(default=None, description="Display label")
    type: str | None = Field(default=None, description="Field type (text, number, password, etc.)")
    enabled: bool | None = Field(default=None, description="Whether field is enabled")
    required: bool | None = Field(default=None, description="Whether field is required")
    default_value: str | None = Field(default=None, description="Default value")
    placeholder: str | None = Field(default=None, description="Placeholder text")
    help_text: str | None = Field(default=None, description="Help text")
    display_order: int | None = Field(default=None, description="Display order")
    validation: Dict[str, Any] | None = Field(default=None, description="Validation rules")
    options: List[Dict[str, Any]] | None = Field(default=None, description="Options for select fields")


class FieldConfigResponse(BaseModel):
    """Response model for field configuration"""
    id: str
    databaseType: str
    name: str
    label: str
    type: str
    enabled: bool
    required: bool
    defaultValue: str | None
    placeholder: str | None
    helpText: str | None
    displayOrder: int
    validation: Dict[str, Any] | None
    options: List[Dict[str, Any]] | None
    createdAt: str | None
    updatedAt: str | None


# API Endpoints
@router.get("/{database_type}", response_model=List[FieldConfigResponse])
async def get_field_configs(database_type: str, db: Session = Depends(get_db)):
    """
    Get all field configurations for a database type
    """
    try:
        logger.info(f"Fetching field configurations for {database_type}")
        
        configs = db.query(FieldConfiguration).filter(
            FieldConfiguration.database_type == database_type
        ).order_by(FieldConfiguration.display_order).all()
        
        logger.info(f"Found {len(configs)} field configurations for {database_type}")
        
        return [
            FieldConfigResponse(**config.to_dict())
            for config in configs
        ]
        
    except Exception as e:
        logger.error(f"Failed to fetch field configurations: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch field configurations: {str(e)}"
        )


@router.post("/{database_type}", response_model=FieldConfigResponse)
async def create_field_config(
    database_type: str,
    request: FieldConfigRequest,
    db: Session = Depends(get_db)
):
    """
    Create a new field configuration
    """
    try:
        logger.info(f"Creating field configuration for {database_type}: {request.name}")
        
        # Generate unique ID
        field_id = f"{database_type}-{request.name}-{int(datetime.utcnow().timestamp() * 1000)}"
        
        # Create field configuration
        config = FieldConfiguration(
            id=field_id,
            database_type=database_type,
            name=request.name,
            label=request.label,
            type=request.type,
            enabled=request.enabled,
            required=request.required,
            default_value=request.default_value,
            placeholder=request.placeholder,
            help_text=request.help_text,
            display_order=request.display_order,
            validation=request.validation,
            options=request.options,
        )
        
        db.add(config)
        db.commit()
        db.refresh(config)
        
        logger.info(f"Field configuration created: {field_id}")
        
        return FieldConfigResponse(**config.to_dict())
        
    except Exception as e:
        logger.error(f"Failed to create field configuration: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create field configuration: {str(e)}"
        )


@router.put("/{field_id}", response_model=FieldConfigResponse)
async def update_field_config(
    field_id: str,
    request: FieldConfigUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Update an existing field configuration (partial updates supported)
    """
    try:
        logger.info(f"Updating field configuration: {field_id}")
        
        config = db.query(FieldConfiguration).filter(
            FieldConfiguration.id == field_id
        ).first()
        
        if not config:
            raise HTTPException(
                status_code=404,
                detail=f"Field configuration not found: {field_id}"
            )
        
        # Update only provided fields
        if request.name is not None:
            config.name = request.name
        if request.label is not None:
            config.label = request.label
        if request.type is not None:
            config.type = request.type
        if request.enabled is not None:
            config.enabled = request.enabled
        if request.required is not None:
            config.required = request.required
        if request.default_value is not None:
            config.default_value = request.default_value
        if request.placeholder is not None:
            config.placeholder = request.placeholder
        if request.help_text is not None:
            config.help_text = request.help_text
        if request.display_order is not None:
            config.display_order = request.display_order
        if request.validation is not None:
            config.validation = request.validation
        if request.options is not None:
            config.options = request.options
        
        config.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(config)
        
        logger.info(f"Field configuration updated: {field_id}")
        
        return FieldConfigResponse(**config.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update field configuration: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update field configuration: {str(e)}"
        )


@router.delete("/{field_id}")
async def delete_field_config(field_id: str, db: Session = Depends(get_db)):
    """
    Delete a field configuration
    """
    try:
        logger.info(f"Deleting field configuration: {field_id}")
        
        config = db.query(FieldConfiguration).filter(
            FieldConfiguration.id == field_id
        ).first()
        
        if not config:
            raise HTTPException(
                status_code=404,
                detail=f"Field configuration not found: {field_id}"
            )
        
        db.delete(config)
        db.commit()
        
        logger.info(f"Field configuration deleted: {field_id}")
        
        return {"success": True, "message": "Field configuration deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete field configuration: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete field configuration: {str(e)}"
        )


@router.post("/{database_type}/seed")
async def seed_default_configs(database_type: str, db: Session = Depends(get_db)):
    """
    Seed default field configurations for a database type
    This is useful for initializing the database with default configs
    """
    try:
        logger.info(f"Seeding default configurations for {database_type}")
        
        # Check if configs already exist
        existing = db.query(FieldConfiguration).filter(
            FieldConfiguration.database_type == database_type
        ).count()
        
        if existing > 0:
            return {
                "success": False,
                "message": f"Configurations already exist for {database_type}",
                "count": existing
            }
        
        # Import default configs
        from constants.default_field_configs import get_default_configs
        default_configs = get_default_configs(database_type)
        
        if not default_configs:
            raise HTTPException(
                status_code=404,
                detail=f"No default configurations found for {database_type}"
            )
        
        # Create configurations
        created_count = 0
        for config_data in default_configs:
            config = FieldConfiguration(
                id=config_data['id'],
                database_type=database_type,
                name=config_data['name'],
                label=config_data['label'],
                type=config_data['type'],
                enabled=config_data.get('enabled', True),
                required=config_data.get('required', False),
                default_value=config_data.get('defaultValue'),
                placeholder=config_data.get('placeholder'),
                help_text=config_data.get('helpText'),
                display_order=config_data.get('displayOrder', 0),
                validation=config_data.get('validation'),
                options=config_data.get('options'),
            )
            db.add(config)
            created_count += 1
        
        db.commit()
        
        logger.info(f"Seeded {created_count} configurations for {database_type}")
        
        return {
            "success": True,
            "message": f"Seeded {created_count} configurations",
            "count": created_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to seed configurations: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to seed configurations: {str(e)}"
        )
