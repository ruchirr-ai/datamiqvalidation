"""
Prompt Template Manager

Manages loading and caching of prompt templates for SQL conversion
"""

import os
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class PromptTemplateManager:
    """Manages prompt templates with caching"""
    
    # Cache for loaded templates
    _template_cache: Dict[str, Dict[str, any]] = {}
    
    # Cache TTL (1 hour)
    CACHE_TTL_SECONDS = 3600
    
    @classmethod
    def get_template(cls, template_name: str) -> str:
        """
        Get prompt template by name with caching
        
        Args:
            template_name: Name of the template file (without .txt extension)
        
        Returns:
            Template content as string
        
        Raises:
            FileNotFoundError: If template file doesn't exist
            ValueError: If template path is invalid
        """
        # Check cache first
        if template_name in cls._template_cache:
            cached_entry = cls._template_cache[template_name]
            cache_time = cached_entry['cached_at']
            
            # Check if cache is still valid
            if datetime.utcnow() - cache_time < timedelta(seconds=cls.CACHE_TTL_SECONDS):
                logger.debug(f"Template cache hit for: {template_name}")
                return cached_entry['content']
            else:
                logger.debug(f"Template cache expired for: {template_name}")
                del cls._template_cache[template_name]
        
        # Cache miss - load from file
        logger.debug(f"Loading template from file: {template_name}")
        template_content = cls._load_template_from_file(template_name)
        
        # Cache the template
        cls._template_cache[template_name] = {
            'content': template_content,
            'cached_at': datetime.utcnow()
        }
        
        return template_content
    
    @classmethod
    def _load_template_from_file(cls, template_name: str) -> str:
        """
        Load template from file system
        
        Args:
            template_name: Name of the template file (without .txt extension)
        
        Returns:
            Template content as string
        
        Raises:
            FileNotFoundError: If template file doesn't exist
            ValueError: If template path is invalid
        """
        # Get templates directory from environment
        templates_dir = os.getenv('CONVERSION_PROMPT_TEMPLATES_DIR', 'backend/prompts')
        
        # Validate template name (prevent path traversal)
        if '..' in template_name or '/' in template_name or '\\' in template_name:
            raise ValueError(f"Invalid template name: {template_name}")
        
        # Construct file path
        template_file = f"{template_name}.txt"
        template_path = os.path.join(templates_dir, template_file)
        
        # Validate file exists
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template file not found: {template_path}")
        
        # Load template content
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            logger.info(f"Loaded template: {template_name} from {template_path}")
            return content
        
        except Exception as e:
            logger.error(f"Failed to load template {template_name}: {e}")
            raise
    
    @classmethod
    def format_template(cls, template_name: str, **variables) -> str:
        """
        Get template and substitute variables
        
        Args:
            template_name: Name of the template file (without .txt extension)
            **variables: Variables to substitute in the template
        
        Returns:
            Formatted template with variables substituted
        
        Example:
            formatted = PromptTemplateManager.format_template(
                'bigquery-to-redshift-conversion',
                source_dialect='bigquery',
                target_dialect='redshift',
                source_code='SELECT * FROM table'
            )
        """
        template = cls.get_template(template_name)
        
        try:
            # Substitute variables using {variable_name} syntax
            formatted = template.format(**variables)
            return formatted
        except KeyError as e:
            logger.error(f"Missing variable in template {template_name}: {e}")
            raise ValueError(f"Missing required variable: {e}")
    
    @classmethod
    def clear_cache(cls):
        """Clear the template cache"""
        cls._template_cache.clear()
        logger.info("Template cache cleared")
    
    @classmethod
    def get_default_template_name(cls, source_dialect: str, target_dialect: str) -> str:
        """
        Get default template name for dialect pair
        
        Args:
            source_dialect: Source SQL dialect
            target_dialect: Target SQL dialect
        
        Returns:
            Template name (without .txt extension)
        """
        # For now, use a generic template
        # In the future, we can have dialect-specific templates
        return 'bigquery-to-redshift-conversion'
    
    @classmethod
    def list_available_templates(cls) -> list:
        """
        List all available template files
        
        Returns:
            List of template names (without .txt extension)
        """
        templates_dir = os.getenv('CONVERSION_PROMPT_TEMPLATES_DIR', 'backend/prompts')
        
        if not os.path.exists(templates_dir):
            logger.warning(f"Templates directory not found: {templates_dir}")
            return []
        
        try:
            files = os.listdir(templates_dir)
            templates = [
                f.replace('.txt', '')
                for f in files
                if f.endswith('.txt')
            ]
            return templates
        except Exception as e:
            logger.error(f"Failed to list templates: {e}")
            return []
