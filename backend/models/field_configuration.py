"""
Field Configuration Model
Stores dynamic field configurations for database connection forms
"""

from sqlalchemy import Column, Integer, String, Boolean, Text, JSON, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class FieldConfiguration(Base):
    """Field configuration for database connection forms"""
    
    __tablename__ = "field_configurations"
    
    id = Column(String(255), primary_key=True)
    database_type = Column(String(50), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    label = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)  # text, number, password, checkbox, select, textarea
    enabled = Column(Boolean, nullable=False, default=True)
    required = Column(Boolean, nullable=False, default=False)
    default_value = Column(String(255), nullable=True)
    placeholder = Column(String(255), nullable=True)
    help_text = Column(Text, nullable=True)
    display_order = Column(Integer, nullable=False, default=0)
    validation = Column(JSON, nullable=True)  # JSON object with validation rules
    options = Column(JSON, nullable=True)  # For select fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            'id': self.id,
            'databaseType': self.database_type,
            'name': self.name,
            'label': self.label,
            'type': self.type,
            'enabled': self.enabled,
            'required': self.required,
            'defaultValue': self.default_value,
            'placeholder': self.placeholder,
            'helpText': self.help_text,
            'displayOrder': self.display_order,
            'validation': self.validation,
            'options': self.options,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
        }
