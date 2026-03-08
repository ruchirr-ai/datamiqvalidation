"""
Retry Strategy

Implements exponential backoff retry logic for transient errors
"""

import time
import logging
from typing import Callable, Any, Optional, List, Type
from functools import wraps

logger = logging.getLogger(__name__)


class RetryStrategy:
    """Retry strategy with exponential backoff"""
    
    # Default retry configuration
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_BASE_DELAY = 5  # seconds
    DEFAULT_MAX_DELAY = 60  # seconds
    DEFAULT_BACKOFF_MULTIPLIER = 2
    
    # Error codes that should trigger retry
    RETRYABLE_ERROR_CODES = [429, 503, 504]
    
    # Error codes that should NOT trigger retry
    NON_RETRYABLE_ERROR_CODES = [400, 401, 403, 404]
    
    def __init__(
        self,
        max_retries: Optional[int] = None,
        base_delay: Optional[int] = None,
        max_delay: Optional[int] = None,
        backoff_multiplier: Optional[int] = None
    ):
        """
        Initialize retry strategy
        
        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            backoff_multiplier: Multiplier for exponential backoff
        """
        self.max_retries = max_retries or self.DEFAULT_MAX_RETRIES
        self.base_delay = base_delay or self.DEFAULT_BASE_DELAY
        self.max_delay = max_delay or self.DEFAULT_MAX_DELAY
        self.backoff_multiplier = backoff_multiplier or self.DEFAULT_BACKOFF_MULTIPLIER
    
    def calculate_delay(self, attempt: int) -> int:
        """
        Calculate delay for given attempt using exponential backoff
        
        Args:
            attempt: Current attempt number (0-indexed)
        
        Returns:
            Delay in seconds
        """
        delay = self.base_delay * (self.backoff_multiplier ** attempt)
        return min(delay, self.max_delay)
    
    def is_retryable_error(self, error: Exception) -> bool:
        """
        Check if error is retryable
        
        Args:
            error: Exception to check
        
        Returns:
            True if error should trigger retry, False otherwise
        """
        # Check for HTTP status code in error
        if hasattr(error, 'status_code'):
            status_code = error.status_code
            
            # Don't retry validation errors
            if status_code in self.NON_RETRYABLE_ERROR_CODES:
                return False
            
            # Retry throttling and service errors
            if status_code in self.RETRYABLE_ERROR_CODES:
                return True
        
        # Check for specific error types
        error_type = type(error).__name__
        
        # Retry on connection errors, timeouts, throttling
        retryable_types = [
            'ConnectionError',
            'Timeout',
            'TimeoutError',
            'ThrottlingException',
            'ServiceUnavailable',
            'InternalServerError',
        ]
        
        return error_type in retryable_types
    
    def execute_with_retry(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function with retry logic
        
        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function
        
        Returns:
            Function result
        
        Raises:
            Exception: If all retry attempts fail
        """
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # Success - log if this was a retry
                if attempt > 0:
                    logger.info(f"Function succeeded on attempt {attempt + 1}")
                
                return result
            
            except Exception as e:
                last_error = e
                
                # Check if we should retry
                if not self.is_retryable_error(e):
                    logger.error(f"Non-retryable error: {e}")
                    raise
                
                # Check if we have retries left
                if attempt >= self.max_retries:
                    logger.error(f"Max retries ({self.max_retries}) exceeded")
                    raise
                
                # Calculate delay and wait
                delay = self.calculate_delay(attempt)
                logger.warning(
                    f"Attempt {attempt + 1} failed with error: {e}. "
                    f"Retrying in {delay} seconds..."
                )
                time.sleep(delay)
        
        # Should never reach here, but just in case
        raise last_error


def retry_with_backoff(
    max_retries: Optional[int] = None,
    base_delay: Optional[int] = None,
    max_delay: Optional[int] = None
):
    """
    Decorator for adding retry logic with exponential backoff
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
    
    Example:
        @retry_with_backoff(max_retries=3, base_delay=5)
        def call_bedrock_api():
            # API call that might fail
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            strategy = RetryStrategy(
                max_retries=max_retries,
                base_delay=base_delay,
                max_delay=max_delay
            )
            return strategy.execute_with_retry(func, *args, **kwargs)
        return wrapper
    return decorator


class BedrockThrottlingError(Exception):
    """Exception for Bedrock API throttling (429)"""
    def __init__(self, message: str = "Bedrock API throttling"):
        self.status_code = 429
        super().__init__(message)


class BedrockServiceError(Exception):
    """Exception for Bedrock service errors (503)"""
    def __init__(self, message: str = "Bedrock service unavailable"):
        self.status_code = 503
        super().__init__(message)


class BedrockValidationError(Exception):
    """Exception for Bedrock validation errors (400) - NOT retryable"""
    def __init__(self, message: str = "Bedrock validation error"):
        self.status_code = 400
        super().__init__(message)
