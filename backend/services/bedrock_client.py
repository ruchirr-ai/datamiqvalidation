"""
AWS Bedrock Client Service

Reusable client for AWS Bedrock API interactions.
Handles model-specific payload formatting and response parsing.
"""

import json
import logging
import time
import os
from typing import Optional, Dict, Any, List
import boto3
from botocore.exceptions import ClientError, BotoCoreError

logger = logging.getLogger(__name__)


class BedrockResponse:
    """Response from Bedrock model invocation"""
    
    def __init__(
        self,
        generated_text: str,
        model_id: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        duration_ms: int = 0
    ):
        self.generated_text = generated_text
        self.model_id = model_id
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.duration_ms = duration_ms
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary"""
        return {
            'generated_text': self.generated_text,
            'model_id': self.model_id,
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'duration_ms': self.duration_ms
        }


class ModelMetadata:
    """Metadata for a Bedrock foundation model"""
    
    def __init__(
        self,
        model_id: str,
        model_name: str,
        provider: str,
        input_modalities: List[str],
        output_modalities: List[str]
    ):
        self.model_id = model_id
        self.model_name = model_name
        self.provider = provider
        self.input_modalities = input_modalities
        self.output_modalities = output_modalities
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary"""
        return {
            'model_id': self.model_id,
            'model_name': self.model_name,
            'provider': self.provider,
            'input_modalities': self.input_modalities,
            'output_modalities': self.output_modalities
        }


class BedrockThrottlingError(Exception):
    """Exception raised when Bedrock API rate limit is exceeded"""
    pass


class BedrockValidationError(Exception):
    """Exception raised for invalid Bedrock API requests"""
    pass


class BedrockServiceError(Exception):
    """Exception raised for Bedrock service errors"""
    pass


class RateLimiter:
    """Simple rate limiter for Bedrock API calls"""
    
    def __init__(self, max_calls_per_hour: int = 100):
        self.max_calls_per_hour = max_calls_per_hour
        self.calls = {}  # workspace_id -> [(timestamp, count)]
    
    def check_rate_limit(self, workspace_id: int) -> bool:
        """
        Check if workspace is within rate limit.
        
        Args:
            workspace_id: Workspace identifier
            
        Returns:
            True if within limit, False otherwise
        """
        now = time.time()
        hour_ago = now - 3600
        
        # Clean up old entries
        if workspace_id in self.calls:
            self.calls[workspace_id] = [
                (ts, count) for ts, count in self.calls[workspace_id]
                if ts > hour_ago
            ]
        else:
            self.calls[workspace_id] = []
        
        # Count calls in last hour
        total_calls = sum(count for _, count in self.calls[workspace_id])
        
        return total_calls < self.max_calls_per_hour
    
    def record_call(self, workspace_id: int):
        """Record a Bedrock API call"""
        now = time.time()
        if workspace_id not in self.calls:
            self.calls[workspace_id] = []
        self.calls[workspace_id].append((now, 1))


class BedrockClient:
    """
    Client for AWS Bedrock foundation model invocations.
    Handles model-specific payload formatting and response parsing.
    """
    
    def __init__(
        self,
        aws_region: Optional[str] = None,
        rate_limiter: Optional[RateLimiter] = None
    ):
        """
        Initialize Bedrock client.
        
        Args:
            aws_region: AWS region (defaults to env var AWS_BEDROCK_REGION)
            rate_limiter: Rate limiter instance
        """
        self.aws_region = aws_region or os.getenv('AWS_BEDROCK_REGION', 'us-east-1')
        self.rate_limiter = rate_limiter or RateLimiter(
            max_calls_per_hour=int(os.getenv('BEDROCK_RATE_LIMIT_PER_WORKSPACE_HOUR', '100'))
        )
        self.logger = logger
        
        try:
            # Initialize Bedrock runtime client
            self.client = boto3.client(
                'bedrock-runtime',
                region_name=self.aws_region
            )
            
            # Initialize Bedrock client for model listing
            self.bedrock_client = boto3.client(
                'bedrock',
                region_name=self.aws_region
            )
            
            # Validate IAM permissions on initialization
            self._validate_permissions()
            
            self.logger.info(
                f"Bedrock client initialized successfully in region {self.aws_region}"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Bedrock client: {str(e)}")
            raise
    
    def _validate_permissions(self):
        """
        Validate AWS IAM permissions for Bedrock access.
        Fails fast if permissions are denied.
        """
        try:
            # Try to list models as a permission check (no maxResults parameter)
            response = self.bedrock_client.list_foundation_models()
            self.logger.info("Bedrock IAM permissions validated successfully")
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code in ['AccessDeniedException', 'UnauthorizedException']:
                self.logger.error(
                    "Bedrock access denied. Check IAM permissions."
                )
                raise BedrockValidationError(
                    "Bedrock access denied. Ensure IAM role has bedrock:InvokeModel "
                    "and bedrock:ListFoundationModels permissions."
                )
            raise
        except Exception as e:
            # In development, log warning but don't fail
            self.logger.warning(
                f"Could not validate Bedrock permissions: {str(e)}. "
                "This is expected in development without AWS credentials."
            )
    
    async def invoke_model(
        self,
        model_id: str,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        top_p: float = 0.9,
        workspace_id: Optional[int] = None
    ) -> BedrockResponse:
        """
        Invoke AWS Bedrock model with prompt.
        
        Args:
            model_id: Bedrock model identifier
            prompt: Input prompt text
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum output tokens
            top_p: Nucleus sampling parameter (0.0-1.0)
            workspace_id: For rate limiting per workspace
            
        Returns:
            BedrockResponse with generated text
            
        Raises:
            BedrockThrottlingError: Rate limit exceeded
            BedrockValidationError: Invalid request
            BedrockServiceError: Service unavailable
        """
        # Check rate limit
        if workspace_id and not self.rate_limiter.check_rate_limit(workspace_id):
            raise BedrockThrottlingError(
                f"Rate limit exceeded for workspace {workspace_id}"
            )
        
        start_time = time.time()
        
        try:
            # Format request based on model
            request_body = self._format_request(
                model_id, prompt, temperature, max_tokens, top_p
            )
            
            self.logger.info(
                f"Invoking Bedrock model {model_id}",
                extra={
                    'workspace_id': workspace_id,
                    'model_id': model_id,
                    'prompt_length': len(prompt)
                }
            )
            
            # Invoke model with retry logic
            response = await self._invoke_with_retry(model_id, request_body)
            
            # Parse response based on model
            generated_text, input_tokens, output_tokens = self._parse_response(
                model_id, response
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Record call for rate limiting
            if workspace_id:
                self.rate_limiter.record_call(workspace_id)
            
            self.logger.info(
                f"Bedrock invocation successful",
                extra={
                    'workspace_id': workspace_id,
                    'model_id': model_id,
                    'duration_ms': duration_ms,
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens
                }
            )
            
            return BedrockResponse(
                generated_text=generated_text,
                model_id=model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_ms=duration_ms
            )
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            if error_code in ['ThrottlingException', 'TooManyRequestsException']:
                raise BedrockThrottlingError(f"Bedrock throttling: {error_message}")
            elif error_code in ['ValidationException', 'InvalidRequestException']:
                raise BedrockValidationError(f"Invalid request: {error_message}")
            else:
                raise BedrockServiceError(f"Bedrock error: {error_message}")
    
    async def _invoke_with_retry(
        self,
        model_id: str,
        request_body: Dict[str, Any],
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Invoke model with exponential backoff retry.
        
        Args:
            model_id: Model identifier
            request_body: Request payload
            max_retries: Maximum retry attempts
            
        Returns:
            Response from Bedrock
        """
        delays = [5, 10, 20]  # Exponential backoff delays in seconds
        
        for attempt in range(max_retries):
            try:
                response = self.client.invoke_model(
                    modelId=model_id,
                    body=json.dumps(request_body)
                )
                
                # Parse response body
                response_body = json.loads(response['body'].read())
                return response_body
                
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                
                # Retry on throttling and service errors
                if error_code in ['ThrottlingException', 'ServiceUnavailableException']:
                    if attempt < max_retries - 1:
                        delay = delays[attempt]
                        self.logger.warning(
                            f"Bedrock throttled, retrying in {delay}s "
                            f"(attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(delay)
                        continue
                
                # Don't retry validation errors
                raise
        
        raise BedrockServiceError("Max retries exceeded")
    
    def _format_request(
        self,
        model_id: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
        top_p: float
    ) -> Dict[str, Any]:
        """Format request payload based on model type"""
        
        # Claude models
        if 'claude' in model_id.lower():
            return {
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': max_tokens,
                'temperature': temperature,
                'top_p': top_p,
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ]
            }
        
        # Titan models
        elif 'titan' in model_id.lower():
            return {
                'inputText': prompt,
                'textGenerationConfig': {
                    'maxTokenCount': max_tokens,
                    'temperature': temperature,
                    'topP': top_p
                }
            }
        
        # Default format
        else:
            return {
                'prompt': prompt,
                'max_tokens': max_tokens,
                'temperature': temperature,
                'top_p': top_p
            }
    
    def _parse_response(
        self,
        model_id: str,
        response: Dict[str, Any]
    ) -> tuple[str, int, int]:
        """
        Parse response based on model type.
        
        Returns:
            Tuple of (generated_text, input_tokens, output_tokens)
        """
        
        # Claude models
        if 'claude' in model_id.lower():
            content = response.get('content', [])
            if content and len(content) > 0:
                generated_text = content[0].get('text', '')
            else:
                generated_text = ''
            
            usage = response.get('usage', {})
            input_tokens = usage.get('input_tokens', 0)
            output_tokens = usage.get('output_tokens', 0)
            
            return generated_text, input_tokens, output_tokens
        
        # Titan models
        elif 'titan' in model_id.lower():
            results = response.get('results', [])
            if results and len(results) > 0:
                generated_text = results[0].get('outputText', '')
            else:
                generated_text = ''
            
            input_tokens = response.get('inputTextTokenCount', 0)
            output_tokens = len(generated_text.split())  # Approximate
            
            return generated_text, input_tokens, output_tokens
        
        # Default parsing
        else:
            generated_text = response.get('completion', response.get('text', ''))
            input_tokens = 0
            output_tokens = 0
            
            return generated_text, input_tokens, output_tokens
    
    async def list_available_models(self) -> List[ModelMetadata]:
        """
        List available Bedrock foundation models.
        
        Returns:
            List of model metadata
        """
        try:
            response = self.bedrock_client.list_foundation_models()
            
            models = []
            for model in response.get('modelSummaries', []):
                models.append(ModelMetadata(
                    model_id=model.get('modelId', ''),
                    model_name=model.get('modelName', ''),
                    provider=model.get('providerName', ''),
                    input_modalities=model.get('inputModalities', []),
                    output_modalities=model.get('outputModalities', [])
                ))
            
            return models
            
        except Exception as e:
            self.logger.error(f"Failed to list models: {str(e)}")
            return []
    
    def load_prompt_template(
        self,
        template_path: str,
        variables: Dict[str, str]
    ) -> str:
        """
        Load and populate prompt template.
        
        Args:
            template_path: Path to template file
            variables: Template variable values
            
        Returns:
            Populated prompt text
        """
        try:
            # Validate path to prevent path traversal
            if '..' in template_path or template_path.startswith('/'):
                raise BedrockValidationError(
                    "Invalid template path: path traversal not allowed"
                )
            
            # Read template file
            templates_dir = os.getenv(
                'CONVERSION_PROMPT_TEMPLATES_DIR',
                'backend/prompts'
            )
            full_path = os.path.join(templates_dir, template_path)
            
            if not os.path.exists(full_path):
                raise FileNotFoundError(f"Template not found: {template_path}")
            
            with open(full_path, 'r', encoding='utf-8') as f:
                template = f.read()
            
            # Substitute variables
            for key, value in variables.items():
                placeholder = f"{{{key}}}"
                template = template.replace(placeholder, value)
            
            return template
            
        except Exception as e:
            self.logger.error(f"Failed to load template: {str(e)}")
            raise
