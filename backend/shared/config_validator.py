"""
Configuration Validator

Validates required configuration on application startup
"""

import os
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class ConfigValidator:
    """Validates application configuration on startup"""
    
    # Required configuration variables
    REQUIRED_CONFIG = [
        'APP_DB_HOST',
        'APP_DB_PORT',
        'APP_DB_NAME',
        'APP_DB_USER',
        'APP_DB_PASSWORD',
        'JWT_SECRET_KEY',
        'AWS_REGION',
    ]
    
    # Optional configuration with defaults
    OPTIONAL_CONFIG = {
        'APP_ENV': 'development',
        'APP_PORT': '8000',
        'APP_HOST': '0.0.0.0',
        'LOG_LEVEL': 'INFO',
        'REDIS_ENABLED': 'false',
        'REDIS_HOST': 'localhost',
        'REDIS_PORT': '6379',
        'REDIS_DB': '0',
        'REDIS_MAX_CONNECTIONS': '50',
        'REDIS_SOCKET_TIMEOUT': '5',
        'REDIS_SOCKET_CONNECT_TIMEOUT': '5',
        'AWS_BEDROCK_REGION': 'us-east-1',
        'AWS_BEDROCK_DEFAULT_MODEL': 'anthropic.claude-v2',
        'BEDROCK_RATE_LIMIT_PER_WORKSPACE_HOUR': '100',
        'CONVERSION_PROMPT_TEMPLATES_DIR': 'backend/prompts',
        'CONVERSION_MAX_RETRIES': '3',
        'CONVERSION_BATCH_PARALLELISM': '5',
        'AWS_DATASYNC_REGION': 'us-east-1',
        'DATASYNC_ROLE_ARN': '',
        'DATASYNC_AGENT_HEALTH_CHECK_INTERVAL_SECONDS': '300',
        'COPY_HISTORY_CACHE_TTL_SECONDS': '300',
        'TASK_HISTORY_CACHE_TTL_SECONDS': '60',
        'HISTORY_DEFAULT_PAGE_SIZE': '50',
        'HISTORY_MAX_PAGE_SIZE': '200',
        'DB_POOL_SIZE': '20',
        'DB_POOL_MAX_OVERFLOW': '10',
        'DB_POOL_TIMEOUT': '30',
    }
    
    @classmethod
    def validate(cls) -> Dict[str, Any]:
        """
        Validate configuration on startup
        
        Returns:
            Dict with validation results
        
        Raises:
            ValueError: If critical configuration is missing
        """
        missing_required = []
        warnings = []
        
        # Check required configuration
        for config_key in cls.REQUIRED_CONFIG:
            value = os.getenv(config_key)
            if not value:
                missing_required.append(config_key)
        
        # Fail fast if critical configuration is missing
        if missing_required:
            error_msg = f"Missing required configuration: {', '.join(missing_required)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Check optional configuration and set defaults
        for config_key, default_value in cls.OPTIONAL_CONFIG.items():
            value = os.getenv(config_key)
            if not value:
                os.environ[config_key] = default_value
                warnings.append(f"{config_key} not set, using default: {default_value}")
        
        # Log warnings for missing optional values
        if warnings:
            for warning in warnings:
                logger.warning(warning)
        
        # Validate specific configuration values
        cls._validate_numeric_configs()
        cls._validate_paths()
        cls._validate_aws_config()
        
        logger.info("Configuration validation completed successfully")
        
        return {
            'status': 'success',
            'warnings': warnings,
            'environment': os.getenv('APP_ENV'),
        }
    
    @classmethod
    def _validate_numeric_configs(cls):
        """Validate numeric configuration values"""
        numeric_configs = {
            'APP_PORT': (1, 65535),
            'REDIS_PORT': (1, 65535),
            'REDIS_DB': (0, 15),
            'REDIS_MAX_CONNECTIONS': (1, 1000),
            'REDIS_SOCKET_TIMEOUT': (1, 60),
            'CONVERSION_MAX_RETRIES': (0, 10),
            'CONVERSION_BATCH_PARALLELISM': (1, 50),
            'HISTORY_DEFAULT_PAGE_SIZE': (1, 200),
            'HISTORY_MAX_PAGE_SIZE': (1, 1000),
            'DB_POOL_SIZE': (1, 100),
        }
        
        for config_key, (min_val, max_val) in numeric_configs.items():
            value = os.getenv(config_key)
            if value:
                try:
                    num_value = int(value)
                    if not (min_val <= num_value <= max_val):
                        logger.warning(
                            f"{config_key}={num_value} is outside recommended range [{min_val}, {max_val}]"
                        )
                except ValueError:
                    logger.error(f"{config_key} must be a valid integer, got: {value}")
                    raise ValueError(f"Invalid numeric configuration: {config_key}")
    
    @classmethod
    def _validate_paths(cls):
        """Validate path configuration values"""
        prompt_templates_dir = os.getenv('CONVERSION_PROMPT_TEMPLATES_DIR')
        if prompt_templates_dir:
            # Check if path contains suspicious patterns (path traversal prevention)
            if '..' in prompt_templates_dir or prompt_templates_dir.startswith('/'):
                logger.error(f"Invalid prompt templates directory: {prompt_templates_dir}")
                raise ValueError("CONVERSION_PROMPT_TEMPLATES_DIR must be a relative path without '..'")
    
    @classmethod
    def _validate_aws_config(cls):
        """Validate AWS configuration"""
        aws_region = os.getenv('AWS_REGION')
        bedrock_region = os.getenv('AWS_BEDROCK_REGION')
        datasync_region = os.getenv('AWS_DATASYNC_REGION')
        
        # Valid AWS regions
        valid_regions = [
            'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
            'eu-west-1', 'eu-west-2', 'eu-central-1',
            'ap-southeast-1', 'ap-southeast-2', 'ap-northeast-1',
        ]
        
        for region_key, region_value in [
            ('AWS_REGION', aws_region),
            ('AWS_BEDROCK_REGION', bedrock_region),
            ('AWS_DATASYNC_REGION', datasync_region)
        ]:
            if region_value and region_value not in valid_regions:
                logger.warning(f"{region_key}={region_value} may not be a valid AWS region")
    
    @classmethod
    def get_config_summary(cls) -> Dict[str, Any]:
        """Get a summary of current configuration (without sensitive values)"""
        return {
            'environment': os.getenv('APP_ENV'),
            'app_host': os.getenv('APP_HOST'),
            'app_port': os.getenv('APP_PORT'),
            'database_host': os.getenv('APP_DB_HOST'),
            'database_name': os.getenv('APP_DB_NAME'),
            'redis_enabled': os.getenv('REDIS_ENABLED'),
            'redis_host': os.getenv('REDIS_HOST'),
            'aws_region': os.getenv('AWS_REGION'),
            'bedrock_region': os.getenv('AWS_BEDROCK_REGION'),
            'datasync_region': os.getenv('AWS_DATASYNC_REGION'),
            'log_level': os.getenv('LOG_LEVEL'),
        }


def validate_config_on_startup():
    """
    Validate configuration on application startup
    Call this function in main.py before starting the application
    """
    try:
        result = ConfigValidator.validate()
        logger.info("Configuration validation passed")
        
        # Log configuration summary (without sensitive values)
        config_summary = ConfigValidator.get_config_summary()
        logger.info(f"Configuration summary: {config_summary}")
        
        return result
    except ValueError as e:
        logger.error(f"Configuration validation failed: {e}")
        raise
