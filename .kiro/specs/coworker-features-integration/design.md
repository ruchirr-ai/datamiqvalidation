# Design Document: Coworker Features Integration

## Overview

This design document provides comprehensive technical specifications for integrating all missing features from coworker_version1 and coworker_version2 into the current DataMIQ implementation. The integration encompasses 10 major feature groups with 45 requirements, focusing on SQL code conversion, history tracking, AWS service integration, and enhanced testing infrastructure.

### Design Goals

1. **Seamless Integration**: Integrate new features without disrupting existing functionality
2. **Workspace Isolation**: Maintain strict workspace boundaries across all new features
3. **Performance**: Implement efficient caching and query optimization strategies
4. **Scalability**: Design for concurrent batch processing and high-volume operations
5. **Security**: Follow AWS best practices with IAM roles, KMS encryption, and rate limiting
6. **Maintainability**: Clear separation of concerns with well-defined service boundaries
7. **Testability**: Comprehensive unit, integration, and property-based test coverage

### Feature Groups

1. **SQL Code Converter Module** - AI-powered conversion using AWS Bedrock and SQLGlot
2. **Copy History Tracking** - Audit trail for Redshift COPY commands
3. **Task History Tracking** - Audit trail for AWS DataSync tasks
4. **DataSync Agent Registry** - Centralized agent management
5. **AWS Bedrock Client Service** - Reusable AI model integration
6. **SQLGlot Parser Integration** - Fast SQL transpilation
7. **Enhanced Testing Infrastructure** - Comprehensive test framework
8. **Frontend UI Components** - User interfaces for new features
9. **Security & Workspace Isolation** - Access control and data segregation
10. **Documentation & Deployment** - Complete technical documentation

## Architecture

### High-Level System Architecture


```mermaid
graph TB
    subgraph "Frontend Layer"
        UI[React UI Components]
        StandaloneConverter[Standalone Converter Page]
        BatchConverter[Batch Converter Page]
        CopyHistory[Copy History Page]
        TaskHistory[Task History Page]
    end

    subgraph "API Gateway Layer"
        Gateway[FastAPI Gateway]
        ConversionRouter[Conversion Router]
        HistoryRouter[History Router]
        AgentRouter[DataSync Agent Router]
    end

    subgraph "Service Layer"
        ConversionService[Conversion Service]
        BedrockClient[Bedrock Client]
        SQLGlotParser[SQLGlot Parser]
        ExportService[Export Service]
        DeployService[Deploy Service]
        HistoryService[History Service]
    end

    subgraph "Repository Layer"
        ConversionRepo[Conversion Repository]
        HistoryRepo[History Repository]
        AgentRepo[Agent Repository]
    end

    subgraph "Data Layer"
        PostgreSQL[(PostgreSQL)]
        Redis[(Redis Cache)]
    end

    subgraph "AWS Services"
        Bedrock[AWS Bedrock]
        DataSync[AWS DataSync]
        KMS[AWS KMS]
        CloudWatch[CloudWatch]
        S3[S3 Storage]
    end

    UI --> Gateway
    StandaloneConverter --> ConversionRouter
    BatchConverter --> ConversionRouter
    CopyHistory --> HistoryRouter
    TaskHistory --> HistoryRouter

    Gateway --> ConversionRouter
    Gateway --> HistoryRouter
    Gateway --> AgentRouter

    ConversionRouter --> ConversionService
    HistoryRouter --> HistoryService
    AgentRouter --> HistoryService

    ConversionService --> BedrockClient
    ConversionService --> SQLGlotParser
    ConversionService --> ExportService
    ConversionService --> DeployService
    ConversionService --> ConversionRepo

    HistoryService --> HistoryRepo
    HistoryService --> AgentRepo

    ConversionRepo --> PostgreSQL
    ConversionRepo --> Redis
    HistoryRepo --> PostgreSQL
    HistoryRepo --> Redis
    AgentRepo --> PostgreSQL
    AgentRepo --> Redis

    BedrockClient --> Bedrock
    HistoryService --> DataSync
    ConversionService --> KMS
    ConversionService --> CloudWatch
    ExportService --> S3
```

### Component Interaction Flow

#### Standalone Conversion Flow

```mermaid
sequenceDiagram
    participant User
    participant UI as Standalone Converter UI
    participant API as Conversion API
    participant Service as Conversion Service
    participant SQLGlot as SQLGlot Parser
    participant Bedrock as Bedrock Client
    participant DB as PostgreSQL
    participant Cache as Redis

    User->>UI: Enter SQL code & dialects
    UI->>API: POST /api/conversions/standalone
    API->>Service: convert_standalone()
    Service->>DB: Create Conversion_Job (status=pending)
    
    alt use_sqlglot enabled
        Service->>SQLGlot: parse_and_transpile()
        alt SQLGlot success
            SQLGlot-->>Service: Transpiled SQL
            Service->>DB: Update job (sqlglot_success=true)
        else SQLGlot failure
            SQLGlot-->>Service: Parse error
            Service->>Bedrock: invoke_model()
            Bedrock-->>Service: Converted SQL
        end
    else use_sqlglot disabled
        Service->>Bedrock: invoke_model()
        Bedrock-->>Service: Converted SQL
    end
    
    Service->>DB: Update job (status=completed)
    Service->>Cache: Cache result (TTL=1h)
    Service-->>API: Conversion result
    API-->>UI: Display converted code
    UI-->>User: Show result with metadata
```



#### Batch Conversion Flow

```mermaid
sequenceDiagram
    participant User
    participant UI as Batch Converter UI
    participant API as Conversion API
    participant Service as Conversion Service
    participant Worker as Async Worker Pool
    participant DB as PostgreSQL
    participant Cache as Redis

    User->>UI: Select connections & assets
    UI->>API: POST /api/conversions/batch
    API->>Service: convert_batch()
    Service->>DB: Create Conversion_Batch
    Service->>DB: Create Conversion_Jobs (N jobs)
    
    loop For each job (parallel)
        Service->>Worker: Process job
        Worker->>Service: convert_standalone()
        Service->>DB: Update job status
        Service->>DB: Increment batch counters
        Service->>Cache: Invalidate batch cache
    end
    
    Service->>DB: Update batch (status=completed)
    Service-->>API: Batch result
    API-->>UI: Display progress
    
    loop Poll for updates
        UI->>API: GET /api/conversions/batches/{id}
        API->>Cache: Check cache
        alt Cache hit
            Cache-->>API: Cached batch data
        else Cache miss
            API->>DB: Query batch
            DB-->>API: Batch data
            API->>Cache: Cache result
        end
        API-->>UI: Progress update
    end
```

### Data Flow Architecture

```mermaid
graph LR
    subgraph "Input Sources"
        UserInput[User Input]
        SourceDB[Source Database]
        MigrationProject[Migration Project]
    end

    subgraph "Processing Pipeline"
        Validation[Input Validation]
        SQLGlot[SQLGlot Parser]
        Bedrock[AWS Bedrock]
        Transformation[Code Transformation]
    end

    subgraph "Storage & Caching"
        PostgreSQL[(PostgreSQL)]
        Redis[(Redis)]
        S3[(S3 Export)]
    end

    subgraph "Output Destinations"
        UI[UI Display]
        TargetDB[Target Database]
        FileExport[File Export]
    end

    UserInput --> Validation
    SourceDB --> Validation
    MigrationProject --> Validation

    Validation --> SQLGlot
    Validation --> Bedrock
    SQLGlot --> Transformation
    Bedrock --> Transformation

    Transformation --> PostgreSQL
    Transformation --> Redis
    PostgreSQL --> UI
    Redis --> UI

    Transformation --> TargetDB
    Transformation --> S3
    S3 --> FileExport
```

## Components and Interfaces

### Backend Services

#### ConversionService

Primary service for SQL code conversion operations.

**Class Definition:**
```python
class ConversionService:
    """
    Service for managing SQL code conversions using AWS Bedrock and SQLGlot.
    Handles standalone and batch conversion workflows with retry logic.
    """
    
    def __init__(
        self,
        conversion_repo: ConversionRepository,
        bedrock_client: BedrockClient,
        sqlglot_parser: SQLGlotParser,
        export_service: ConversionExportService,
        deploy_service: ConversionDeployService,
        cache: ConversionCache
    ):
        self.conversion_repo = conversion_repo
        self.bedrock_client = bedrock_client
        self.sqlglot_parser = sqlglot_parser
        self.export_service = export_service
        self.deploy_service = deploy_service
        self.cache = cache
```



**Key Methods:**

```python
async def convert_standalone(
    self,
    workspace_id: int,
    user_id: int,
    source_code: str,
    source_dialect: str,
    target_dialect: str,
    asset_type: str,
    bedrock_model: str = None,
    use_sqlglot: bool = True,
    prompt_template_path: str = None
) -> ConversionJob:
    """
    Convert a single SQL code snippet.
    
    Args:
        workspace_id: Workspace identifier for isolation
        user_id: User performing conversion
        source_code: SQL code to convert
        source_dialect: Source database dialect
        target_dialect: Target database dialect
        asset_type: Type of asset (view, stored_procedure, function, etc.)
        bedrock_model: AWS Bedrock model ID (optional)
        use_sqlglot: Whether to attempt SQLGlot first
        prompt_template_path: Custom prompt template path
        
    Returns:
        ConversionJob with converted code
        
    Raises:
        ValidationError: Invalid input parameters
        ConversionError: Conversion failed after retries
    """
    pass

async def convert_batch(
    self,
    workspace_id: int,
    user_id: int,
    source_connection_id: int,
    target_connection_id: int,
    asset_list: List[Dict[str, Any]],
    bedrock_model: str = None,
    use_sqlglot: bool = True,
    max_retries: int = 3,
    parallelism: int = 5
) -> ConversionBatch:
    """
    Convert multiple SQL assets in batch.
    
    Args:
        workspace_id: Workspace identifier
        user_id: User performing conversion
        source_connection_id: Source database connection
        target_connection_id: Target database connection
        asset_list: List of assets to convert
        bedrock_model: AWS Bedrock model ID
        use_sqlglot: Whether to attempt SQLGlot first
        max_retries: Maximum retry attempts per job
        parallelism: Number of concurrent jobs
        
    Returns:
        ConversionBatch with job references
    """
    pass

async def export_conversion(
    self,
    workspace_id: int,
    job_id: int,
    export_format: str = "sql"
) -> bytes:
    """
    Export converted SQL code to file.
    
    Args:
        workspace_id: Workspace identifier
        job_id: Conversion job ID
        export_format: Export format (sql, zip)
        
    Returns:
        File content as bytes
    """
    pass

async def deploy_conversion(
    self,
    workspace_id: int,
    job_id: int,
    target_connection_id: int,
    dry_run: bool = False
) -> DeploymentResult:
    """
    Deploy converted code to target database.
    
    Args:
        workspace_id: Workspace identifier
        job_id: Conversion job ID
        target_connection_id: Target database connection
        dry_run: Validate without executing
        
    Returns:
        DeploymentResult with execution details
    """
    pass
```

#### BedrockClient

Reusable client for AWS Bedrock API interactions.

**Class Definition:**
```python
class BedrockClient:
    """
    Client for AWS Bedrock foundation model invocations.
    Handles model-specific payload formatting and response parsing.
    """
    
    def __init__(
        self,
        aws_region: str,
        rate_limiter: RateLimiter,
        logger: Logger
    ):
        self.aws_region = aws_region
        self.rate_limiter = rate_limiter
        self.logger = logger
        self.client = boto3.client('bedrock-runtime', region_name=aws_region)
```

**Key Methods:**

```python
async def invoke_model(
    self,
    model_id: str,
    prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    top_p: float = 0.9,
    workspace_id: int = None
) -> BedrockResponse:
    """
    Invoke AWS Bedrock model with prompt.
    
    Args:
        model_id: Bedrock model identifier
        prompt: Input prompt text
        temperature: Sampling temperature
        max_tokens: Maximum output tokens
        top_p: Nucleus sampling parameter
        workspace_id: For rate limiting per workspace
        
    Returns:
        BedrockResponse with generated text
        
    Raises:
        BedrockThrottlingError: Rate limit exceeded
        BedrockValidationError: Invalid request
        BedrockServiceError: Service unavailable
    """
    pass

async def list_available_models(self) -> List[ModelMetadata]:
    """
    List available Bedrock foundation models.
    
    Returns:
        List of model metadata
    """
    pass

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
    pass
```



#### SQLGlotParser

Parser and transpiler for SQL code using SQLGlot library.

**Class Definition:**
```python
class SQLGlotParser:
    """
    SQL parser and transpiler using SQLGlot library.
    Provides fast, deterministic conversions for supported dialect pairs.
    """
    
    SUPPORTED_DIALECTS = [
        'bigquery', 'redshift', 'postgres', 'mysql', 
        'snowflake', 'oracle', 'mssql'
    ]
    
    def __init__(self, logger: Logger):
        self.logger = logger
```

**Key Methods:**

```python
def parse_and_transpile(
    self,
    source_code: str,
    source_dialect: str,
    target_dialect: str,
    pretty: bool = True
) -> TranspileResult:
    """
    Parse SQL and transpile to target dialect.
    
    Args:
        source_code: SQL code to parse
        source_dialect: Source database dialect
        target_dialect: Target database dialect
        pretty: Format output with indentation
        
    Returns:
        TranspileResult with success status and code
        
    Raises:
        SQLGlotParseError: Syntax error in source code
        SQLGlotDialectError: Unsupported dialect
    """
    pass

def validate_dialects(
    self,
    source_dialect: str,
    target_dialect: str
) -> bool:
    """
    Validate dialect pair is supported.
    
    Args:
        source_dialect: Source dialect
        target_dialect: Target dialect
        
    Returns:
        True if both dialects supported
    """
    pass

def format_sql(
    self,
    sql_code: str,
    dialect: str,
    indent_width: int = 2
) -> str:
    """
    Format SQL with consistent indentation.
    
    Args:
        sql_code: SQL to format
        dialect: SQL dialect
        indent_width: Spaces per indent level
        
    Returns:
        Formatted SQL code
    """
    pass
```

#### ConversionExportService

Service for exporting conversion results to files.

**Class Definition:**
```python
class ConversionExportService:
    """
    Service for exporting conversion results to SQL files or ZIP archives.
    Supports local file generation and S3 upload.
    """
    
    def __init__(
        self,
        s3_client: S3Client,
        config: ExportConfig
    ):
        self.s3_client = s3_client
        self.config = config
```

**Key Methods:**

```python
async def export_single_job(
    self,
    job: ConversionJob,
    workspace_id: int
) -> ExportResult:
    """
    Export single conversion job to SQL file.
    
    Args:
        job: Conversion job to export
        workspace_id: Workspace identifier
        
    Returns:
        ExportResult with file path or S3 URL
    """
    pass

async def export_batch(
    self,
    batch: ConversionBatch,
    jobs: List[ConversionJob],
    workspace_id: int
) -> ExportResult:
    """
    Export batch conversion to ZIP archive.
    
    Args:
        batch: Conversion batch
        jobs: List of conversion jobs
        workspace_id: Workspace identifier
        
    Returns:
        ExportResult with ZIP file path or S3 URL
    """
    pass

async def upload_to_s3(
    self,
    file_content: bytes,
    workspace_id: int,
    file_name: str
) -> str:
    """
    Upload file to S3 with workspace-scoped prefix.
    
    Args:
        file_content: File content bytes
        workspace_id: Workspace identifier
        file_name: Destination file name
        
    Returns:
        S3 URL
    """
    pass
```

#### ConversionDeployService

Service for deploying converted code to target databases.

**Class Definition:**
```python
class ConversionDeployService:
    """
    Service for deploying converted SQL code to target databases.
    Supports dry-run validation and actual execution.
    """
    
    def __init__(
        self,
        connection_service: ConnectionService,
        kms_client: KMSClient
    ):
        self.connection_service = connection_service
        self.kms_client = kms_client
```

**Key Methods:**

```python
async def deploy_to_target(
    self,
    job: ConversionJob,
    target_connection_id: int,
    workspace_id: int,
    dry_run: bool = False
) -> DeploymentResult:
    """
    Deploy converted code to target database.
    
    Args:
        job: Conversion job with target code
        target_connection_id: Target database connection
        workspace_id: Workspace identifier
        dry_run: Validate without executing
        
    Returns:
        DeploymentResult with execution status
        
    Raises:
        DeploymentError: Execution failed
        ConnectionError: Database connection failed
    """
    pass

async def validate_target_code(
    self,
    target_code: str,
    target_connection_id: int,
    workspace_id: int
) -> ValidationResult:
    """
    Validate target code syntax without execution.
    
    Args:
        target_code: SQL code to validate
        target_connection_id: Target database connection
        workspace_id: Workspace identifier
        
    Returns:
        ValidationResult with syntax check status
    """
    pass
```



#### HistoryService

Service for managing Copy History and Task History tracking.

**Class Definition:**
```python
class HistoryService:
    """
    Service for tracking Redshift COPY commands and AWS DataSync tasks.
    Provides audit trail and monitoring capabilities.
    """
    
    def __init__(
        self,
        history_repo: HistoryRepository,
        agent_repo: AgentRepository,
        datasync_client: DataSyncClient,
        cache: HistoryCache
    ):
        self.history_repo = history_repo
        self.agent_repo = agent_repo
        self.datasync_client = datasync_client
        self.cache = cache
```

**Key Methods:**

```python
async def create_copy_history(
    self,
    migration_id: int,
    workspace_id: int,
    copy_command: str,
    source_uri: str,
    table_name: str,
    **kwargs
) -> CopyHistory:
    """
    Create Copy History record for Redshift COPY command.
    
    Args:
        migration_id: Migration identifier
        workspace_id: Workspace identifier
        copy_command: Full COPY command text
        source_uri: S3 source URI
        table_name: Target table name
        
    Returns:
        CopyHistory record
    """
    pass

async def update_copy_history(
    self,
    copy_history_id: int,
    workspace_id: int,
    status: str,
    rows_loaded: int = None,
    bytes_loaded: int = None,
    error_message: str = None
) -> CopyHistory:
    """
    Update Copy History with completion status.
    
    Args:
        copy_history_id: Copy History record ID
        workspace_id: Workspace identifier
        status: Completion status (completed, failed)
        rows_loaded: Number of rows loaded
        bytes_loaded: Bytes loaded
        error_message: Error details if failed
        
    Returns:
        Updated CopyHistory record
    """
    pass

async def create_task_history(
    self,
    migration_id: int,
    workspace_id: int,
    task_arn: str,
    agent_arn: str,
    agent_ip: str,
    source_uri: str,
    dest_uri: str,
    **kwargs
) -> TaskHistory:
    """
    Create Task History record for DataSync task.
    
    Args:
        migration_id: Migration identifier
        workspace_id: Workspace identifier
        task_arn: DataSync task ARN
        agent_arn: DataSync agent ARN
        agent_ip: Agent VM IP address
        source_uri: GCS source URI
        dest_uri: S3 destination URI
        
    Returns:
        TaskHistory record
    """
    pass

async def register_datasync_agent(
    self,
    workspace_id: int,
    vm_ip: str,
    aws_region: str
) -> DataSyncAgent:
    """
    Register or retrieve DataSync agent.
    
    Args:
        workspace_id: Workspace identifier
        vm_ip: Agent VM IP address
        aws_region: AWS region
        
    Returns:
        DataSyncAgent record with agent_arn
    """
    pass

async def check_agent_health(
    self,
    agent_id: int,
    workspace_id: int
) -> AgentHealthStatus:
    """
    Check DataSync agent health status.
    
    Args:
        agent_id: Agent record ID
        workspace_id: Workspace identifier
        
    Returns:
        AgentHealthStatus with online/offline status
    """
    pass
```

### Repository Layer

#### ConversionRepository

Data access layer for conversion entities.

**Class Definition:**
```python
class ConversionRepository:
    """
    Repository for Conversion_Job, Conversion_Batch, and Conversion_Log entities.
    Implements workspace isolation and caching strategies.
    """
    
    def __init__(
        self,
        db: Database,
        cache: RedisCache
    ):
        self.db = db
        self.cache = cache
```

**Key Methods:**

```python
async def create_job(
    self,
    workspace_id: int,
    job_data: Dict[str, Any]
) -> ConversionJob:
    """Create conversion job with workspace isolation."""
    pass

async def get_job(
    self,
    job_id: int,
    workspace_id: int
) -> Optional[ConversionJob]:
    """Get job by ID with workspace validation."""
    pass

async def update_job_status(
    self,
    job_id: int,
    workspace_id: int,
    status: str,
    target_code: str = None,
    error_message: str = None
) -> ConversionJob:
    """Update job status and invalidate cache."""
    pass

async def create_batch(
    self,
    workspace_id: int,
    batch_data: Dict[str, Any]
) -> ConversionBatch:
    """Create conversion batch."""
    pass

async def get_batch_jobs(
    self,
    batch_id: int,
    workspace_id: int,
    page: int = 1,
    page_size: int = 50
) -> Tuple[List[ConversionJob], int]:
    """Get paginated jobs for batch."""
    pass

async def create_log(
    self,
    job_id: int,
    workspace_id: int,
    log_data: Dict[str, Any]
) -> ConversionLog:
    """Create conversion log entry."""
    pass
```



#### HistoryRepository

Data access layer for history tracking entities.

**Class Definition:**
```python
class HistoryRepository:
    """
    Repository for Copy_History and Task_History entities.
    Implements workspace isolation through migration ownership.
    """
    
    def __init__(
        self,
        db: Database,
        cache: RedisCache
    ):
        self.db = db
        self.cache = cache
```

**Key Methods:**

```python
async def create_copy_history(
    self,
    copy_data: Dict[str, Any]
) -> CopyHistory:
    """Create Copy History record."""
    pass

async def get_copy_history_by_migration(
    self,
    migration_id: int,
    workspace_id: int,
    filters: Dict[str, Any] = None,
    page: int = 1,
    page_size: int = 50
) -> Tuple[List[CopyHistory], int]:
    """Get Copy History for migration with workspace validation."""
    pass

async def create_task_history(
    self,
    task_data: Dict[str, Any]
) -> TaskHistory:
    """Create Task History record."""
    pass

async def get_task_history_by_migration(
    self,
    migration_id: int,
    workspace_id: int,
    filters: Dict[str, Any] = None,
    page: int = 1,
    page_size: int = 50
) -> Tuple[List[TaskHistory], int]:
    """Get Task History for migration with workspace validation."""
    pass
```

### API Endpoints

#### Conversion API Endpoints

**Router: `/api/conversions`**

```python
# POST /api/conversions/standalone
@router.post("/standalone", response_model=ConversionJobResponse)
async def create_standalone_conversion(
    request: StandaloneConversionRequest,
    workspace_id: int = Depends(get_workspace_id),
    user_id: int = Depends(get_current_user_id),
    conversion_service: ConversionService = Depends()
):
    """
    Create standalone SQL code conversion.
    
    Request Body:
    {
        "source_code": "SELECT * FROM table",
        "source_dialect": "bigquery",
        "target_dialect": "redshift",
        "asset_type": "view",
        "bedrock_model": "anthropic.claude-v2",
        "use_sqlglot": true,
        "prompt_template_path": null
    }
    
    Response (200):
    {
        "job_id": 123,
        "status": "completed",
        "target_code": "SELECT * FROM table",
        "sqlglot_success": true,
        "created_at": "2026-01-25T10:00:00Z"
    }
    """
    pass

# POST /api/conversions/batch
@router.post("/batch", response_model=ConversionBatchResponse)
async def create_batch_conversion(
    request: BatchConversionRequest,
    workspace_id: int = Depends(get_workspace_id),
    user_id: int = Depends(get_current_user_id),
    conversion_service: ConversionService = Depends()
):
    """
    Create batch SQL code conversion.
    
    Request Body:
    {
        "source_connection_id": 1,
        "target_connection_id": 2,
        "asset_list": [
            {"asset_type": "view", "asset_name": "customer_view", "source_code": "..."},
            {"asset_type": "stored_procedure", "asset_name": "update_customer", "source_code": "..."}
        ],
        "bedrock_model": "anthropic.claude-v2",
        "use_sqlglot": true,
        "max_retries": 3
    }
    
    Response (200):
    {
        "batch_id": 456,
        "status": "processing",
        "total_assets": 2,
        "completed_assets": 0,
        "failed_assets": 0,
        "created_at": "2026-01-25T10:00:00Z"
    }
    """
    pass

# GET /api/conversions/jobs/{job_id}
@router.get("/jobs/{job_id}", response_model=ConversionJobDetailResponse)
async def get_conversion_job(
    job_id: int,
    workspace_id: int = Depends(get_workspace_id),
    conversion_service: ConversionService = Depends()
):
    """
    Get conversion job details.
    
    Response (200):
    {
        "job_id": 123,
        "workspace_id": 1,
        "batch_id": null,
        "source_code": "SELECT * FROM table",
        "target_code": "SELECT * FROM table",
        "source_dialect": "bigquery",
        "target_dialect": "redshift",
        "asset_type": "view",
        "asset_name": "customer_view",
        "bedrock_model": "anthropic.claude-v2",
        "use_sqlglot": true,
        "sqlglot_success": true,
        "status": "completed",
        "error_message": null,
        "retry_count": 0,
        "created_at": "2026-01-25T10:00:00Z",
        "updated_at": "2026-01-25T10:00:05Z"
    }
    
    Response (404):
    {
        "detail": "Conversion job not found or access denied"
    }
    """
    pass

# GET /api/conversions/batches/{batch_id}
@router.get("/batches/{batch_id}", response_model=ConversionBatchDetailResponse)
async def get_conversion_batch(
    batch_id: int,
    workspace_id: int = Depends(get_workspace_id),
    conversion_service: ConversionService = Depends()
):
    """Get conversion batch details with progress."""
    pass

# GET /api/conversions/batches/{batch_id}/jobs
@router.get("/batches/{batch_id}/jobs", response_model=ConversionJobListResponse)
async def get_batch_jobs(
    batch_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    workspace_id: int = Depends(get_workspace_id),
    conversion_service: ConversionService = Depends()
):
    """Get paginated list of jobs for batch."""
    pass

# GET /api/conversions/jobs/{job_id}/logs
@router.get("/jobs/{job_id}/logs", response_model=ConversionLogListResponse)
async def get_job_logs(
    job_id: int,
    workspace_id: int = Depends(get_workspace_id),
    conversion_service: ConversionService = Depends()
):
    """Get conversion logs for debugging."""
    pass

# POST /api/conversions/jobs/{job_id}/export
@router.post("/jobs/{job_id}/export")
async def export_conversion(
    job_id: int,
    export_format: str = Query("sql", regex="^(sql|zip)$"),
    workspace_id: int = Depends(get_workspace_id),
    conversion_service: ConversionService = Depends()
):
    """
    Export converted SQL code to file.
    
    Response (200):
    Returns file download with appropriate Content-Type
    """
    pass

# POST /api/conversions/jobs/{job_id}/deploy
@router.post("/jobs/{job_id}/deploy", response_model=DeploymentResultResponse)
async def deploy_conversion(
    job_id: int,
    request: DeploymentRequest,
    workspace_id: int = Depends(get_workspace_id),
    conversion_service: ConversionService = Depends()
):
    """
    Deploy converted code to target database.
    
    Request Body:
    {
        "target_connection_id": 2,
        "dry_run": false
    }
    
    Response (200):
    {
        "success": true,
        "message": "Deployment completed successfully",
        "execution_time_ms": 1234
    }
    """
    pass

# GET /api/conversions/jobs
@router.get("/jobs", response_model=ConversionJobListResponse)
async def list_conversion_jobs(
    workspace_id: int = Depends(get_workspace_id),
    status: Optional[str] = Query(None),
    asset_type: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    conversion_service: ConversionService = Depends()
):
    """List conversion jobs with filters and pagination."""
    pass
```



#### History API Endpoints

**Router: `/api/copy-history`**

```python
# GET /api/copy-history
@router.get("", response_model=CopyHistoryListResponse)
async def list_copy_history(
    workspace_id: int = Depends(get_workspace_id),
    migration_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    sort_by: str = Query("started_at", regex="^(started_at|completed_at|duration_seconds|rows_loaded|bytes_loaded)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    history_service: HistoryService = Depends()
):
    """
    List Copy History records with filters.
    
    Response (200):
    {
        "items": [
            {
                "id": 1,
                "migration_id": 10,
                "migration_name": "BigQuery to Redshift",
                "schema_name": "public",
                "table_name": "customers",
                "status": "completed",
                "started_at": "2026-01-25T10:00:00Z",
                "completed_at": "2026-01-25T10:05:00Z",
                "duration_seconds": 300,
                "rows_loaded": 1000000,
                "bytes_loaded": 52428800
            }
        ],
        "total": 100,
        "page": 1,
        "page_size": 50,
        "summary": {
            "total_rows_loaded": 5000000,
            "total_bytes_loaded": 262144000,
            "success_count": 95,
            "failure_count": 5
        }
    }
    """
    pass

# GET /api/copy-history/{id}
@router.get("/{id}", response_model=CopyHistoryDetailResponse)
async def get_copy_history(
    id: int,
    workspace_id: int = Depends(get_workspace_id),
    history_service: HistoryService = Depends()
):
    """
    Get detailed Copy History record.
    
    Response (200):
    {
        "id": 1,
        "migration_id": 10,
        "migration_name": "BigQuery to Redshift",
        "schema_name": "public",
        "table_name": "customers",
        "copy_command": "COPY public.customers FROM 's3://...' ...",
        "source_uri": "s3://bucket/path/customers.csv",
        "file_format": "CSV",
        "compression": "GZIP",
        "iam_role_arn": "arn:aws:iam::123456789012:role/RedshiftRole",
        "status": "completed",
        "started_at": "2026-01-25T10:00:00Z",
        "completed_at": "2026-01-25T10:05:00Z",
        "duration_seconds": 300,
        "rows_loaded": 1000000,
        "bytes_loaded": 52428800,
        "error_message": null,
        "error_details": null,
        "created_at": "2026-01-25T10:00:00Z"
    }
    """
    pass

# GET /api/migrations/{migration_id}/copy-history
@router.get("/migrations/{migration_id}/copy-history", response_model=CopyHistoryListResponse)
async def get_migration_copy_history(
    migration_id: int,
    workspace_id: int = Depends(get_workspace_id),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    history_service: HistoryService = Depends()
):
    """Get all Copy History for specific migration."""
    pass
```

**Router: `/api/task-history`**

```python
# GET /api/task-history
@router.get("", response_model=TaskHistoryListResponse)
async def list_task_history(
    workspace_id: int = Depends(get_workspace_id),
    migration_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    agent_ip: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    sort_by: str = Query("started_at"),
    sort_order: str = Query("desc"),
    history_service: HistoryService = Depends()
):
    """
    List Task History records with filters.
    
    Response (200):
    {
        "items": [
            {
                "id": 1,
                "migration_id": 10,
                "task_name": "GCS to S3 Transfer",
                "agent_ip": "10.0.1.100",
                "status": "completed",
                "started_at": "2026-01-25T10:00:00Z",
                "completed_at": "2026-01-25T10:10:00Z",
                "duration_seconds": 600,
                "files_transferred": 100,
                "bytes_transferred": 104857600
            }
        ],
        "total": 50,
        "page": 1,
        "page_size": 50,
        "summary": {
            "total_files_transferred": 500,
            "total_bytes_transferred": 524288000,
            "success_count": 45,
            "failure_count": 3,
            "agent_offline_count": 2
        }
    }
    """
    pass

# GET /api/task-history/{id}
@router.get("/{id}", response_model=TaskHistoryDetailResponse)
async def get_task_history(
    id: int,
    workspace_id: int = Depends(get_workspace_id),
    history_service: HistoryService = Depends()
):
    """Get detailed Task History record including raw_result."""
    pass

# GET /api/task-history/agents
@router.get("/agents", response_model=AgentSummaryResponse)
async def get_agent_summary(
    workspace_id: int = Depends(get_workspace_id),
    history_service: HistoryService = Depends()
):
    """
    Get unique agent IPs with latest status.
    
    Response (200):
    {
        "agents": [
            {
                "agent_ip": "10.0.1.100",
                "status": "online",
                "last_used_at": "2026-01-25T10:00:00Z",
                "total_tasks": 50,
                "success_count": 48,
                "failure_count": 2
            }
        ]
    }
    """
    pass
```

**Router: `/api/datasync-agents`**

```python
# POST /api/datasync-agents
@router.post("", response_model=DataSyncAgentResponse)
async def register_datasync_agent(
    request: RegisterAgentRequest,
    workspace_id: int = Depends(get_workspace_id),
    history_service: HistoryService = Depends()
):
    """
    Register new DataSync agent or retrieve existing.
    
    Request Body:
    {
        "vm_ip": "10.0.1.100",
        "aws_region": "us-east-1"
    }
    
    Response (200):
    {
        "id": 1,
        "vm_ip": "10.0.1.100",
        "agent_arn": "arn:aws:datasync:us-east-1:123456789012:agent/agent-abc123",
        "aws_region": "us-east-1",
        "status": "online",
        "last_used_at": null,
        "created_at": "2026-01-25T10:00:00Z"
    }
    """
    pass

# GET /api/datasync-agents
@router.get("", response_model=DataSyncAgentListResponse)
async def list_datasync_agents(
    workspace_id: int = Depends(get_workspace_id),
    status: Optional[str] = Query(None),
    history_service: HistoryService = Depends()
):
    """List all registered DataSync agents."""
    pass

# GET /api/datasync-agents/{id}
@router.get("/{id}", response_model=DataSyncAgentDetailResponse)
async def get_datasync_agent(
    id: int,
    workspace_id: int = Depends(get_workspace_id),
    history_service: HistoryService = Depends()
):
    """Get detailed agent information."""
    pass

# PUT /api/datasync-agents/{id}/health-check
@router.put("/{id}/health-check", response_model=DataSyncAgentResponse)
async def check_agent_health(
    id: int,
    workspace_id: int = Depends(get_workspace_id),
    history_service: HistoryService = Depends()
):
    """Refresh agent health status from AWS DataSync."""
    pass

# DELETE /api/datasync-agents/{id}
@router.delete("/{id}", status_code=204)
async def delete_datasync_agent(
    id: int,
    workspace_id: int = Depends(get_workspace_id),
    history_service: HistoryService = Depends()
):
    """
    Delete agent registration.
    
    Response (204): No content
    Response (409): Conflict - agent in use by active migrations
    """
    pass
```

## Data Models

### Database Schema



#### Entity Relationship Diagram

```mermaid
erDiagram
    WORKSPACES ||--o{ CONVERSION_BATCHES : "owns"
    WORKSPACES ||--o{ CONVERSION_JOBS : "owns"
    WORKSPACES ||--o{ DATASYNC_AGENTS : "owns"
    
    CONVERSION_BATCHES ||--o{ CONVERSION_JOBS : "contains"
    CONVERSION_JOBS ||--o{ CONVERSION_LOGS : "generates"
    
    CONNECTIONS ||--o{ CONVERSION_BATCHES : "source"
    CONNECTIONS ||--o{ CONVERSION_BATCHES : "target"
    
    MIGRATION_PROJECTS ||--o{ CONVERSION_BATCHES : "associated"
    MIGRATION_PROJECTS ||--o{ COPY_HISTORY : "tracks"
    MIGRATION_PROJECTS ||--o{ TASK_HISTORY : "tracks"
    
    DATASYNC_AGENTS ||--o{ TASK_HISTORY : "executes"
    
    WORKSPACES {
        int id PK
        string name
        string slug
        int organization_id FK
    }
    
    CONVERSION_JOBS {
        int id PK
        int workspace_id FK
        int batch_id FK
        text source_code
        text target_code
        string source_dialect
        string target_dialect
        string asset_type
        string asset_name
        string bedrock_model
        string aws_region
        string prompt_template_path
        boolean use_sqlglot
        boolean sqlglot_success
        string status
        text error_message
        int retry_count
        int created_by FK
        timestamp created_at
        timestamp updated_at
    }
    
    CONVERSION_BATCHES {
        int id PK
        int workspace_id FK
        int migration_project_id FK
        int source_connection_id FK
        int target_connection_id FK
        string bedrock_model
        string aws_region
        string prompt_template_path
        boolean use_sqlglot
        int max_retries
        string status
        int total_assets
        int completed_assets
        int failed_assets
        int created_by FK
        timestamp created_at
        timestamp updated_at
    }
    
    CONVERSION_LOGS {
        int id PK
        int job_id FK
        int workspace_id FK
        timestamp timestamp
        string log_level
        string step_name
        text message
        int duration_ms
    }
    
    COPY_HISTORY {
        int id PK
        int migration_id FK
        string migration_name
        string schema_name
        string table_name
        text copy_command
        string source_uri
        string file_format
        string compression
        string iam_role_arn
        string status
        timestamp started_at
        timestamp completed_at
        int duration_seconds
        bigint rows_loaded
        bigint bytes_loaded
        text error_message
        jsonb error_details
        timestamp created_at
    }
    
    TASK_HISTORY {
        int id PK
        int migration_id FK
        string migration_name
        string task_arn
        string execution_arn
        string task_name
        string task_type
        string agent_arn
        string agent_ip
        string source_location_arn
        string source_uri
        string dest_location_arn
        string dest_uri
        string table_name
        string status
        timestamp started_at
        timestamp completed_at
        int duration_seconds
        bigint files_transferred
        bigint bytes_transferred
        text error_message
        string error_code
        jsonb error_details
        jsonb raw_result
        timestamp created_at
    }
    
    DATASYNC_AGENTS {
        int id PK
        string vm_ip UNIQUE
        string agent_arn
        string aws_region
        string status
        timestamp last_used_at
        timestamp created_at
        timestamp updated_at
    }
```

#### Table Definitions

**conversion_jobs**

```sql
CREATE TABLE conversion_jobs (
    id SERIAL PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    batch_id INTEGER REFERENCES conversion_batches(id) ON DELETE SET NULL,
    source_code TEXT NOT NULL,
    target_code TEXT,
    source_dialect VARCHAR(50) NOT NULL,
    target_dialect VARCHAR(50) NOT NULL,
    asset_type VARCHAR(50) NOT NULL,
    asset_name VARCHAR(255),
    bedrock_model VARCHAR(100),
    aws_region VARCHAR(50) DEFAULT 'us-east-1',
    prompt_template_path VARCHAR(500),
    use_sqlglot BOOLEAN DEFAULT TRUE,
    sqlglot_success BOOLEAN DEFAULT FALSE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_status CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    CONSTRAINT chk_asset_type CHECK (asset_type IN ('view', 'stored_procedure', 'function', 'trigger', 'table_ddl'))
);

CREATE INDEX idx_conversion_jobs_workspace_id ON conversion_jobs(workspace_id);
CREATE INDEX idx_conversion_jobs_batch_id ON conversion_jobs(batch_id);
CREATE INDEX idx_conversion_jobs_status ON conversion_jobs(status);
CREATE INDEX idx_conversion_jobs_asset_type ON conversion_jobs(asset_type);
CREATE INDEX idx_conversion_jobs_created_at ON conversion_jobs(created_at DESC);
CREATE INDEX idx_conversion_jobs_workspace_status ON conversion_jobs(workspace_id, status);
```

**conversion_batches**

```sql
CREATE TABLE conversion_batches (
    id SERIAL PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    migration_project_id INTEGER REFERENCES migration_projects(id) ON DELETE SET NULL,
    source_connection_id INTEGER NOT NULL REFERENCES connections(id) ON DELETE RESTRICT,
    target_connection_id INTEGER NOT NULL REFERENCES connections(id) ON DELETE RESTRICT,
    bedrock_model VARCHAR(100),
    aws_region VARCHAR(50) DEFAULT 'us-east-1',
    prompt_template_path VARCHAR(500),
    use_sqlglot BOOLEAN DEFAULT TRUE,
    max_retries INTEGER DEFAULT 3,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    total_assets INTEGER DEFAULT 0,
    completed_assets INTEGER DEFAULT 0,
    failed_assets INTEGER DEFAULT 0,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_batch_status CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    CONSTRAINT chk_asset_counts CHECK (completed_assets + failed_assets <= total_assets)
);

CREATE INDEX idx_conversion_batches_workspace_id ON conversion_batches(workspace_id);
CREATE INDEX idx_conversion_batches_status ON conversion_batches(status);
CREATE INDEX idx_conversion_batches_migration_project ON conversion_batches(migration_project_id);
CREATE INDEX idx_conversion_batches_created_at ON conversion_batches(created_at DESC);
```

**conversion_logs**

```sql
CREATE TABLE conversion_logs (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES conversion_jobs(id) ON DELETE CASCADE,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    log_level VARCHAR(20) NOT NULL DEFAULT 'INFO',
    step_name VARCHAR(100) NOT NULL,
    message TEXT NOT NULL,
    duration_ms INTEGER,
    
    CONSTRAINT chk_log_level CHECK (log_level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'))
);

CREATE INDEX idx_conversion_logs_job_id ON conversion_logs(job_id);
CREATE INDEX idx_conversion_logs_workspace_id ON conversion_logs(workspace_id);
CREATE INDEX idx_conversion_logs_timestamp ON conversion_logs(timestamp DESC);
CREATE INDEX idx_conversion_logs_log_level ON conversion_logs(log_level);
```



**copy_history**

```sql
CREATE TABLE copy_history (
    id SERIAL PRIMARY KEY,
    migration_id INTEGER NOT NULL REFERENCES migration_projects(id) ON DELETE CASCADE,
    migration_name VARCHAR(255) NOT NULL,
    schema_name VARCHAR(255),
    table_name VARCHAR(255) NOT NULL,
    copy_command TEXT NOT NULL,
    source_uri TEXT NOT NULL,
    file_format VARCHAR(50),
    compression VARCHAR(50),
    iam_role_arn VARCHAR(500),
    status VARCHAR(50) NOT NULL DEFAULT 'running',
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    rows_loaded BIGINT,
    bytes_loaded BIGINT,
    error_message TEXT,
    error_details JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_copy_status CHECK (status IN ('running', 'completed', 'failed'))
);

CREATE INDEX idx_copy_history_migration_id ON copy_history(migration_id);
CREATE INDEX idx_copy_history_status ON copy_history(status);
CREATE INDEX idx_copy_history_started_at ON copy_history(started_at DESC);
CREATE INDEX idx_copy_history_schema_table ON copy_history(schema_name, table_name);
CREATE INDEX idx_copy_history_migration_status ON copy_history(migration_id, status);
```

**task_history**

```sql
CREATE TABLE task_history (
    id SERIAL PRIMARY KEY,
    migration_id INTEGER NOT NULL REFERENCES migration_projects(id) ON DELETE CASCADE,
    migration_name VARCHAR(255) NOT NULL,
    task_arn VARCHAR(500) NOT NULL,
    execution_arn VARCHAR(500),
    task_name VARCHAR(255) NOT NULL,
    task_type VARCHAR(50) DEFAULT 'TRANSFER',
    agent_arn VARCHAR(500) NOT NULL,
    agent_ip VARCHAR(50) NOT NULL,
    source_location_arn VARCHAR(500),
    source_uri TEXT NOT NULL,
    dest_location_arn VARCHAR(500),
    dest_uri TEXT NOT NULL,
    table_name VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'running',
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    files_transferred BIGINT,
    bytes_transferred BIGINT,
    error_message TEXT,
    error_code VARCHAR(100),
    error_details JSONB,
    raw_result JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_task_status CHECK (status IN ('running', 'completed', 'failed', 'agent_offline'))
);

CREATE INDEX idx_task_history_migration_id ON task_history(migration_id);
CREATE INDEX idx_task_history_status ON task_history(status);
CREATE INDEX idx_task_history_started_at ON task_history(started_at DESC);
CREATE INDEX idx_task_history_agent_ip ON task_history(agent_ip);
CREATE INDEX idx_task_history_task_type ON task_history(task_type);
CREATE INDEX idx_task_history_migration_status ON task_history(migration_id, status);
```

**datasync_agents**

```sql
CREATE TABLE datasync_agents (
    id SERIAL PRIMARY KEY,
    vm_ip VARCHAR(50) NOT NULL UNIQUE,
    agent_arn VARCHAR(500) NOT NULL,
    aws_region VARCHAR(50) NOT NULL DEFAULT 'us-east-1',
    status VARCHAR(50) NOT NULL DEFAULT 'unknown',
    last_used_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_agent_status CHECK (status IN ('online', 'offline', 'unknown'))
);

CREATE UNIQUE INDEX idx_datasync_agents_vm_ip ON datasync_agents(vm_ip);
CREATE INDEX idx_datasync_agents_status ON datasync_agents(status);
CREATE INDEX idx_datasync_agents_last_used ON datasync_agents(last_used_at DESC);
```

### Caching Strategy

#### Cache Key Patterns

**Conversion Data:**
```
conversion:job:{job_id}                                    # TTL: 1 hour
conversion:job:{job_id}:active                             # TTL: 1 minute (status=processing)
conversion:batch:{batch_id}                                # TTL: 1 hour
conversion:batch:{batch_id}:active                         # TTL: 1 minute (status=processing)
conversion:jobs:workspace:{workspace_id}:page:{page}       # TTL: 5 minutes
conversion:logs:job:{job_id}                               # TTL: 30 minutes
```

**History Data:**
```
copy_history:active:{migration_id}                         # TTL: 1 minute (status=running)
copy_history:list:workspace:{workspace_id}:filters:{hash}  # TTL: 5 minutes
task_history:active:{migration_id}                         # TTL: 1 minute (status=running)
task_history:list:workspace:{workspace_id}:filters:{hash}  # TTL: 5 minutes
datasync:agents:workspace:{workspace_id}                   # TTL: 1 hour
datasync:agent:{vm_ip}                                     # TTL: 1 hour
```

#### Cache Implementation Pattern

```python
class ConversionCache:
    """Cache manager for conversion data with Redis fallback."""
    
    def __init__(self, redis_client: Redis, db: Database):
        self.redis = redis_client
        self.db = db
    
    async def get_job(self, job_id: int, workspace_id: int) -> Optional[ConversionJob]:
        """Get job with cache-aside pattern."""
        cache_key = f"conversion:job:{job_id}"
        
        try:
            # Try Redis first
            cached = await self.redis.get(cache_key)
            if cached:
                job_data = json.loads(cached)
                # Validate workspace_id
                if job_data.get('workspace_id') == workspace_id:
                    return ConversionJob(**job_data)
        except (RedisError, ConnectionError) as e:
            logger.warning(f"Redis unavailable: {e}, falling back to database")
        
        # Fallback to database
        job = await self.db.query(ConversionJob).filter(
            ConversionJob.id == job_id,
            ConversionJob.workspace_id == workspace_id
        ).first()
        
        if job:
            # Try to cache for next time (best effort)
            try:
                ttl = 60 if job.status == 'processing' else 3600
                await self.redis.setex(
                    cache_key,
                    ttl,
                    json.dumps(job.dict())
                )
            except Exception as e:
                logger.warning(f"Failed to cache job: {e}")
        
        return job
    
    async def invalidate_job(self, job_id: int):
        """Invalidate job cache on status change."""
        try:
            await self.redis.delete(f"conversion:job:{job_id}")
            await self.redis.delete(f"conversion:job:{job_id}:active")
        except Exception as e:
            logger.warning(f"Failed to invalidate cache: {e}")
```



## Error Handling

### Error Categories

**Transient Errors (Retry with Exponential Backoff):**
- AWS Bedrock throttling (429)
- AWS Bedrock service unavailable (503)
- Database connection timeouts
- Redis connection failures
- Network timeouts

**Permanent Errors (Fail Immediately):**
- AWS Bedrock validation errors (400)
- Invalid SQL syntax
- Missing permissions
- Invalid configuration
- Workspace isolation violations

### Retry Strategy

```python
class RetryStrategy:
    """Exponential backoff retry strategy for transient failures."""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 5.0,
        max_delay: float = 60.0
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
    
    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Execute function with exponential backoff retry."""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except (BedrockThrottlingError, BedrockServiceError) as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = min(
                        self.base_delay * (2 ** attempt),
                        self.max_delay
                    )
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"All {self.max_retries} retry attempts failed"
                    )
            except BedrockValidationError as e:
                # Don't retry validation errors
                logger.error(f"Validation error, not retrying: {e}")
                raise
        
        raise last_exception
```

### Error Response Format

```python
class ErrorResponse(BaseModel):
    """Standardized error response format."""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# Example error responses
{
    "error": "ConversionError",
    "message": "Failed to convert SQL code after 3 retry attempts",
    "details": {
        "job_id": 123,
        "source_dialect": "bigquery",
        "target_dialect": "redshift",
        "retry_count": 3,
        "last_error": "Bedrock API throttling"
    },
    "request_id": "req-abc123",
    "timestamp": "2026-01-25T10:00:00Z"
}
```

## Testing Strategy

### Unit Testing

**Coverage Targets:**
- Backend services: 80% minimum
- Frontend components: 70% minimum
- Critical paths: 100% (conversion logic, workspace isolation)

**Test Organization:**
```
backend/tests/
├── unit/
│   ├── services/
│   │   ├── test_conversion_service.py
│   │   ├── test_bedrock_client.py
│   │   ├── test_sqlglot_parser.py
│   │   ├── test_export_service.py
│   │   └── test_history_service.py
│   ├── repositories/
│   │   ├── test_conversion_repository.py
│   │   └── test_history_repository.py
│   └── utils/
│       └── test_unescape.py
├── integration/
│   ├── test_conversion_api.py
│   ├── test_history_api.py
│   └── test_agent_api.py
├── property/
│   ├── test_sqlglot_roundtrip.py
│   └── test_conversion_properties.py
└── fixtures/
    ├── sample_payloads.py
    └── mock_responses.py
```

**Sample Unit Test:**
```python
# backend/tests/unit/services/test_conversion_service.py

import pytest
from unittest.mock import Mock, AsyncMock
from backend.services.conversion_service import ConversionService

@pytest.fixture
def conversion_service(mock_repo, mock_bedrock, mock_sqlglot):
    return ConversionService(
        conversion_repo=mock_repo,
        bedrock_client=mock_bedrock,
        sqlglot_parser=mock_sqlglot,
        export_service=Mock(),
        deploy_service=Mock(),
        cache=Mock()
    )

@pytest.mark.asyncio
async def test_standalone_conversion_with_sqlglot_success(conversion_service):
    """Test standalone conversion using SQLGlot successfully."""
    # Arrange
    source_code = "SELECT * FROM `project.dataset.table`"
    source_dialect = "bigquery"
    target_dialect = "redshift"
    
    conversion_service.sqlglot_parser.parse_and_transpile = Mock(
        return_value=TranspileResult(
            success=True,
            code='SELECT * FROM "project"."dataset"."table"',
            error=None
        )
    )
    
    # Act
    result = await conversion_service.convert_standalone(
        workspace_id=1,
        user_id=1,
        source_code=source_code,
        source_dialect=source_dialect,
        target_dialect=target_dialect,
        asset_type="view",
        use_sqlglot=True
    )
    
    # Assert
    assert result.status == "completed"
    assert result.sqlglot_success is True
    assert result.target_code == 'SELECT * FROM "project"."dataset"."table"'
    conversion_service.bedrock_client.invoke_model.assert_not_called()

@pytest.mark.asyncio
async def test_standalone_conversion_sqlglot_fallback_to_bedrock(conversion_service):
    """Test fallback to Bedrock when SQLGlot parsing fails."""
    # Arrange
    source_code = "INVALID SQL SYNTAX"
    
    conversion_service.sqlglot_parser.parse_and_transpile = Mock(
        return_value=TranspileResult(
            success=False,
            code=None,
            error="Parse error at line 1"
        )
    )
    
    conversion_service.bedrock_client.invoke_model = AsyncMock(
        return_value=BedrockResponse(
            text="```sql\nSELECT * FROM table\n```",
            model_id="anthropic.claude-v2"
        )
    )
    
    # Act
    result = await conversion_service.convert_standalone(
        workspace_id=1,
        user_id=1,
        source_code=source_code,
        source_dialect="bigquery",
        target_dialect="redshift",
        asset_type="view",
        use_sqlglot=True
    )
    
    # Assert
    assert result.status == "completed"
    assert result.sqlglot_success is False
    assert result.target_code == "SELECT * FROM table"
    conversion_service.bedrock_client.invoke_model.assert_called_once()

@pytest.mark.asyncio
async def test_workspace_isolation_validation(conversion_service):
    """Test workspace isolation prevents cross-workspace access."""
    # Arrange
    conversion_service.conversion_repo.get_job = AsyncMock(return_value=None)
    
    # Act & Assert
    with pytest.raises(NotFoundError):
        await conversion_service.get_job(
            job_id=999,
            workspace_id=1  # Job belongs to different workspace
        )
```



### Integration Testing

**Sample Integration Test:**
```python
# backend/tests/integration/test_conversion_api.py

import pytest
from httpx import AsyncClient
from backend.main import app

@pytest.mark.asyncio
async def test_create_standalone_conversion_success(
    async_client: AsyncClient,
    auth_headers: dict,
    mock_bedrock_api
):
    """Test POST /api/conversions/standalone with valid payload."""
    # Arrange
    payload = {
        "source_code": "SELECT * FROM customers",
        "source_dialect": "bigquery",
        "target_dialect": "redshift",
        "asset_type": "view",
        "bedrock_model": "anthropic.claude-v2",
        "use_sqlglot": True
    }
    
    # Act
    response = await async_client.post(
        "/api/conversions/standalone",
        json=payload,
        headers=auth_headers
    )
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] in ["pending", "processing", "completed"]
    assert data["source_dialect"] == "bigquery"
    assert data["target_dialect"] == "redshift"

@pytest.mark.asyncio
async def test_create_standalone_conversion_invalid_dialect(
    async_client: AsyncClient,
    auth_headers: dict
):
    """Test POST /api/conversions/standalone with invalid dialect."""
    # Arrange
    payload = {
        "source_code": "SELECT * FROM customers",
        "source_dialect": "invalid_dialect",
        "target_dialect": "redshift",
        "asset_type": "view"
    }
    
    # Act
    response = await async_client.post(
        "/api/conversions/standalone",
        json=payload,
        headers=auth_headers
    )
    
    # Assert
    assert response.status_code == 400
    assert "error" in response.json()

@pytest.mark.asyncio
async def test_workspace_isolation_prevents_cross_workspace_access(
    async_client: AsyncClient,
    workspace1_auth_headers: dict,
    workspace2_job_id: int
):
    """Test workspace isolation returns 404 for cross-workspace access."""
    # Act
    response = await async_client.get(
        f"/api/conversions/jobs/{workspace2_job_id}",
        headers=workspace1_auth_headers
    )
    
    # Assert
    assert response.status_code == 404
    assert "not found or access denied" in response.json()["detail"].lower()
```

### Property-Based Testing

Now I need to perform the prework analysis before writing the Correctness Properties section.



**Property Reflection:**

After reviewing all testable properties from the prework analysis, I've identified the following consolidations:

- Properties 1.1 and 2.1 (job/batch creation) can be combined into a single property about entity creation with correct initial state
- Properties 6.4 and 7.4 (completion field updates) are similar patterns and can be generalized
- Properties 23.1, 23.7, and 9.10 (workspace isolation) can be consolidated into comprehensive workspace isolation properties
- Properties 1.10, 6.9, and 28.5 (caching behavior) can be combined into general caching properties
- Property 5.8 (round-trip) is unique and valuable - keep as-is
- Property 8.2 (idempotence) is unique - keep as-is
- Properties 41.1 and 41.3 (retry logic) can be combined into a single retry behavior property

The consolidated properties will provide comprehensive coverage without redundancy.

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: SQLGlot Round-Trip Preservation

*For any* valid SQL statement in a supported dialect, parsing then printing then parsing again SHALL produce an equivalent abstract syntax tree.

**Validates: Requirements 5.8**

**Rationale:** This round-trip property ensures that SQLGlot parsing and printing operations are lossless and preserve semantic meaning. It's a fundamental correctness guarantee for the transpilation pipeline.

### Property 2: Workspace Isolation in Queries

*For any* database query operation (read or write), the query SHALL include a workspace_id filter matching the authenticated user's workspace.

**Validates: Requirements 1.9, 9.10, 23.1, 24.1, 24.2**

**Rationale:** This is a critical security invariant. Every database operation must enforce workspace boundaries to prevent data leakage between tenants.

### Property 3: Workspace Isolation in Cache Keys

*For any* Redis cache operation, the cache key SHALL include the workspace_id to prevent cross-workspace cache pollution.

**Validates: Requirements 23.7, 24.8**

**Rationale:** Cache keys must be workspace-scoped to maintain data isolation at the caching layer.

### Property 4: Conversion Job Creation

*For any* valid conversion request (standalone or batch), a Conversion_Job record SHALL be created with status='pending' and all required fields populated.

**Validates: Requirements 1.1, 2.1**

**Rationale:** Ensures consistent job creation across all conversion workflows with proper initial state.

### Property 5: Batch Job Count Consistency

*For any* batch conversion with N assets, exactly N Conversion_Job records SHALL be created with the batch_id reference.

**Validates: Requirements 2.2**

**Rationale:** Maintains referential integrity between batches and their constituent jobs.

### Property 6: Batch Counter Invariant

*For any* Conversion_Batch, the invariant (completed_assets + failed_assets ≤ total_assets) SHALL hold at all times.

**Validates: Requirements 2.5, 2.6**

**Rationale:** Ensures counter consistency and prevents invalid state where processed assets exceed total.

### Property 7: SQLGlot Precedence

*For any* conversion request with use_sqlglot=true and supported dialect pair, SQLGlot parsing SHALL be attempted before Bedrock invocation.

**Validates: Requirements 1.2, 1.3, 1.4**

**Rationale:** Ensures cost optimization by using free SQLGlot transpilation before expensive AI model calls.

### Property 8: Markdown Code Extraction

*For any* Bedrock response containing markdown code blocks, the extracted target_code SHALL contain only the code content without markdown formatting characters.

**Validates: Requirements 1.5, 36.1**

**Rationale:** Ensures clean code extraction from AI model responses regardless of formatting.

### Property 9: Duration Calculation Accuracy

*For any* completed Copy_History or Task_History record, duration_seconds SHALL equal the difference between completed_at and started_at timestamps (within 1 second tolerance).

**Validates: Requirements 6.6**

**Rationale:** Ensures accurate duration tracking for performance monitoring and reporting.

### Property 10: Completion Field Population

*For any* Copy_History or Task_History record with status='completed', all completion fields (completed_at, duration_seconds, rows_loaded/files_transferred, bytes_loaded/bytes_transferred) SHALL be non-null.

**Validates: Requirements 6.4, 7.4**

**Rationale:** Ensures complete audit trail data for successful operations.

### Property 11: Agent Registration Idempotence

*For any* DataSync agent VM IP, registering the same IP multiple times SHALL return the same agent_arn without creating duplicate records.

**Validates: Requirements 8.2, 8.4**

**Rationale:** Prevents duplicate agent registrations and ensures efficient resource reuse.

### Property 12: Cache Invalidation on Status Change

*For any* Conversion_Job, when status changes from 'processing' to 'completed' or 'failed', the Redis cache entry SHALL be invalidated.

**Validates: Requirements 28.5**

**Rationale:** Ensures cache consistency by removing stale data when job state changes.

### Property 13: Rate Limiting Enforcement

*For any* workspace, when Bedrock API call count exceeds the configured hourly limit, subsequent calls SHALL return HTTP 429 with retry-after header.

**Validates: Requirements 25.3**

**Rationale:** Prevents runaway costs and ensures fair resource allocation across workspaces.

### Property 14: Retry Logic for Transient Errors

*For any* Bedrock API call that returns a throttling error (429) or service unavailable (503), the system SHALL retry with exponential backoff delays (5s, 10s, 20s) up to max_retries.

**Validates: Requirements 41.1, 41.2**

**Rationale:** Handles transient failures gracefully without overwhelming the service.

### Property 15: No Retry for Validation Errors

*For any* Bedrock API call that returns a validation error (400), the system SHALL NOT retry and SHALL immediately mark the job as failed with retry_count=0.

**Validates: Requirements 41.3**

**Rationale:** Avoids wasting resources retrying requests that will never succeed.

### Property 16: Batch Concurrency Limit

*For any* batch conversion, the number of jobs in 'processing' status SHALL never exceed the configured parallelism limit.

**Validates: Requirements 42.1**

**Rationale:** Prevents resource exhaustion and ensures controlled concurrent execution.

### Property 17: Compression Round-Trip

*For any* target_code value exceeding the compression threshold, compressing then decompressing SHALL produce the original value.

**Validates: Requirements 42.6**

**Rationale:** Ensures lossless compression for large SQL code values.

### Property 18: Cache TTL Correctness

*For any* cached entity, the Redis TTL SHALL match the configured value for that entity type (1 hour for jobs, 5 minutes for lists, 1 minute for active items).

**Validates: Requirements 1.10, 6.9, 28.1, 29.1**

**Rationale:** Ensures consistent caching behavior and prevents stale data.



**Sample Property-Based Test:**

```python
# backend/tests/property/test_sqlglot_roundtrip.py

from hypothesis import given, strategies as st, settings
import sqlglot
from backend.services.sqlglot_parser import SQLGlotParser

# Strategy for generating SQL SELECT statements
@st.composite
def sql_select_statement(draw):
    """Generate random SQL SELECT statements."""
    table_name = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll')),
        min_size=3,
        max_size=20
    ))
    column_count = draw(st.integers(min_value=1, max_value=5))
    columns = [f"col{i}" for i in range(column_count)]
    
    return f"SELECT {', '.join(columns)} FROM {table_name}"

@given(
    sql=sql_select_statement(),
    dialect=st.sampled_from(['postgres', 'mysql', 'bigquery', 'redshift'])
)
@settings(max_examples=100)
def test_sqlglot_roundtrip_property(sql: str, dialect: str):
    """
    Property: For all valid SQL statements, parse→print→parse produces equivalent AST.
    
    Feature: coworker-features-integration, Property 1: SQLGlot Round-Trip Preservation
    """
    parser = SQLGlotParser()
    
    # First parse
    ast1 = sqlglot.parse_one(sql, read=dialect)
    
    # Print to SQL
    printed_sql = ast1.sql(dialect=dialect, pretty=True)
    
    # Second parse
    ast2 = sqlglot.parse_one(printed_sql, read=dialect)
    
    # Assert equivalence
    assert ast1.sql(dialect=dialect) == ast2.sql(dialect=dialect), \
        f"Round-trip failed for SQL: {sql}"

@given(
    workspace_id=st.integers(min_value=1, max_value=1000),
    job_id=st.integers(min_value=1, max_value=100000)
)
@settings(max_examples=100)
def test_workspace_isolation_in_cache_keys(workspace_id: int, job_id: int):
    """
    Property: For all cache operations, keys include workspace_id.
    
    Feature: coworker-features-integration, Property 3: Workspace Isolation in Cache Keys
    """
    from backend.services.conversion_cache import ConversionCache
    
    cache = ConversionCache(redis_client=Mock(), db=Mock())
    cache_key = cache.get_job_cache_key(job_id, workspace_id)
    
    # Assert workspace_id is in the key
    assert f"workspace:{workspace_id}" in cache_key or \
           f":{workspace_id}:" in cache_key, \
        f"Cache key missing workspace_id: {cache_key}"

@given(
    total_assets=st.integers(min_value=1, max_value=100),
    completed=st.integers(min_value=0, max_value=100),
    failed=st.integers(min_value=0, max_value=100)
)
@settings(max_examples=100)
def test_batch_counter_invariant(total_assets: int, completed: int, failed: int):
    """
    Property: For all batches, completed + failed <= total_assets.
    
    Feature: coworker-features-integration, Property 6: Batch Counter Invariant
    """
    from backend.models.conversion_batch import ConversionBatch
    
    # Only test valid combinations
    if completed + failed > total_assets:
        # This should be rejected by database constraint
        with pytest.raises(IntegrityError):
            batch = ConversionBatch(
                workspace_id=1,
                source_connection_id=1,
                target_connection_id=2,
                total_assets=total_assets,
                completed_assets=completed,
                failed_assets=failed
            )
            db.add(batch)
            db.commit()
    else:
        # This should succeed
        batch = ConversionBatch(
            workspace_id=1,
            source_connection_id=1,
            target_connection_id=2,
            total_assets=total_assets,
            completed_assets=completed,
            failed_assets=failed
        )
        assert batch.completed_assets + batch.failed_assets <= batch.total_assets
```

## Frontend Architecture

### Component Hierarchy

```
App
├── Layout
│   ├── Navigation
│   └── Sidebar
├── Routes
│   ├── StandaloneConverterPage
│   │   ├── CodeEditor (source)
│   │   ├── DialectSelector
│   │   ├── AssetTypeSelector
│   │   ├── ConfigurationPanel
│   │   ├── ConvertButton
│   │   └── CodeEditor (target)
│   ├── BatchConverterPage
│   │   ├── ConnectionSelector
│   │   ├── AssetTypeFilter
│   │   ├── AssetList
│   │   ├── ConfigurationPanel
│   │   ├── BatchProgressBar
│   │   └── JobStatusTable
│   ├── CopyHistoryPage
│   │   ├── FilterPanel
│   │   ├── SummaryStatistics
│   │   ├── CopyHistoryTable
│   │   ├── Pagination
│   │   └── DetailModal
│   └── TaskHistoryPage
│       ├── FilterPanel
│       ├── AgentStatusDashboard
│       ├── SummaryStatistics
│       ├── TaskHistoryTable
│       ├── Pagination
│       └── DetailModal
```

### State Management

**Conversion State (Zustand Store):**

```typescript
// frontend/src/stores/conversionStore.ts

interface ConversionState {
  // Standalone conversion
  standaloneJob: ConversionJob | null;
  standaloneLoading: boolean;
  standaloneError: string | null;
  
  // Batch conversion
  currentBatch: ConversionBatch | null;
  batchJobs: ConversionJob[];
  batchLoading: boolean;
  batchError: string | null;
  
  // Actions
  createStandaloneConversion: (request: StandaloneConversionRequest) => Promise<void>;
  createBatchConversion: (request: BatchConversionRequest) => Promise<void>;
  fetchBatchProgress: (batchId: number) => Promise<void>;
  exportConversion: (jobId: number) => Promise<void>;
  deployConversion: (jobId: number, targetConnectionId: number) => Promise<void>;
}

export const useConversionStore = create<ConversionState>((set, get) => ({
  standaloneJob: null,
  standaloneLoading: false,
  standaloneError: null,
  currentBatch: null,
  batchJobs: [],
  batchLoading: false,
  batchError: null,
  
  createStandaloneConversion: async (request) => {
    set({ standaloneLoading: true, standaloneError: null });
    try {
      const response = await conversionApi.createStandalone(request);
      set({ standaloneJob: response, standaloneLoading: false });
    } catch (error) {
      set({ standaloneError: error.message, standaloneLoading: false });
    }
  },
  
  createBatchConversion: async (request) => {
    set({ batchLoading: true, batchError: null });
    try {
      const response = await conversionApi.createBatch(request);
      set({ currentBatch: response, batchLoading: false });
      // Start polling for progress
      get().startBatchPolling(response.batch_id);
    } catch (error) {
      set({ batchError: error.message, batchLoading: false });
    }
  },
  
  fetchBatchProgress: async (batchId) => {
    try {
      const [batch, jobs] = await Promise.all([
        conversionApi.getBatch(batchId),
        conversionApi.getBatchJobs(batchId)
      ]);
      set({ currentBatch: batch, batchJobs: jobs.items });
    } catch (error) {
      console.error('Failed to fetch batch progress:', error);
    }
  }
}));
```

**History State (Zustand Store):**

```typescript
// frontend/src/stores/historyStore.ts

interface HistoryState {
  // Copy History
  copyHistory: CopyHistory[];
  copyHistoryTotal: number;
  copyHistorySummary: CopyHistorySummary | null;
  copyHistoryLoading: boolean;
  
  // Task History
  taskHistory: TaskHistory[];
  taskHistoryTotal: number;
  taskHistorySummary: TaskHistorySummary | null;
  taskHistoryLoading: boolean;
  
  // Filters
  filters: HistoryFilters;
  
  // Actions
  fetchCopyHistory: (filters: HistoryFilters) => Promise<void>;
  fetchTaskHistory: (filters: HistoryFilters) => Promise<void>;
  setFilters: (filters: Partial<HistoryFilters>) => void;
}
```

### API Integration

**Conversion API Service:**

```typescript
// frontend/src/services/conversionApi.ts

import axios from 'axios';

const API_BASE = '/api/conversions';

export const conversionApi = {
  createStandalone: async (request: StandaloneConversionRequest): Promise<ConversionJob> => {
    const response = await axios.post(`${API_BASE}/standalone`, request);
    return response.data;
  },
  
  createBatch: async (request: BatchConversionRequest): Promise<ConversionBatch> => {
    const response = await axios.post(`${API_BASE}/batch`, request);
    return response.data;
  },
  
  getJob: async (jobId: number): Promise<ConversionJob> => {
    const response = await axios.get(`${API_BASE}/jobs/${jobId}`);
    return response.data;
  },
  
  getBatch: async (batchId: number): Promise<ConversionBatch> => {
    const response = await axios.get(`${API_BASE}/batches/${batchId}`);
    return response.data;
  },
  
  getBatchJobs: async (
    batchId: number,
    page: number = 1,
    pageSize: number = 50
  ): Promise<ConversionJobListResponse> => {
    const response = await axios.get(
      `${API_BASE}/batches/${batchId}/jobs`,
      { params: { page, page_size: pageSize } }
    );
    return response.data;
  },
  
  exportJob: async (jobId: number): Promise<Blob> => {
    const response = await axios.post(
      `${API_BASE}/jobs/${jobId}/export`,
      {},
      { responseType: 'blob' }
    );
    return response.data;
  },
  
  deployJob: async (
    jobId: number,
    targetConnectionId: number,
    dryRun: boolean = false
  ): Promise<DeploymentResult> => {
    const response = await axios.post(`${API_BASE}/jobs/${jobId}/deploy`, {
      target_connection_id: targetConnectionId,
      dry_run: dryRun
    });
    return response.data;
  }
};
```



### Key UI Components

**StandaloneConverterPage:**

```typescript
// frontend/src/pages/StandaloneConverterPage.tsx

import React, { useState } from 'react';
import { useConversionStore } from '@/stores/conversionStore';
import { CodeEditor } from '@/components/CodeEditor';
import { Button } from '@/components/ui/Button';

export const StandaloneConverterPage: React.FC = () => {
  const [sourceCode, setSourceCode] = useState('');
  const [sourceDialect, setSourceDialect] = useState('bigquery');
  const [targetDialect, setTargetDialect] = useState('redshift');
  const [assetType, setAssetType] = useState('view');
  const [useSqlglot, setUseSqlglot] = useState(true);
  
  const {
    standaloneJob,
    standaloneLoading,
    standaloneError,
    createStandaloneConversion
  } = useConversionStore();
  
  const handleConvert = async () => {
    await createStandaloneConversion({
      source_code: sourceCode,
      source_dialect: sourceDialect,
      target_dialect: targetDialect,
      asset_type: assetType,
      use_sqlglot: useSqlglot
    });
  };
  
  return (
    <div className="converter-page">
      <div className="converter-header">
        <h1>SQL Code Converter</h1>
        <p>Convert SQL code between database dialects</p>
      </div>
      
      <div className="converter-grid">
        <div className="source-panel">
          <h2>Source Code</h2>
          <select value={sourceDialect} onChange={(e) => setSourceDialect(e.target.value)}>
            <option value="bigquery">BigQuery</option>
            <option value="redshift">Redshift</option>
            <option value="postgres">PostgreSQL</option>
            <option value="mysql">MySQL</option>
            <option value="snowflake">Snowflake</option>
          </select>
          
          <CodeEditor
            value={sourceCode}
            onChange={setSourceCode}
            language="sql"
            placeholder="Enter SQL code to convert..."
          />
        </div>
        
        <div className="config-panel">
          <h3>Configuration</h3>
          
          <label>
            Asset Type:
            <select value={assetType} onChange={(e) => setAssetType(e.target.value)}>
              <option value="view">View</option>
              <option value="stored_procedure">Stored Procedure</option>
              <option value="function">Function</option>
              <option value="trigger">Trigger</option>
              <option value="table_ddl">Table DDL</option>
            </select>
          </label>
          
          <label>
            <input
              type="checkbox"
              checked={useSqlglot}
              onChange={(e) => setUseSqlglot(e.target.checked)}
            />
            Use SQLGlot (faster, free)
          </label>
          
          <Button
            onClick={handleConvert}
            disabled={!sourceCode || standaloneLoading}
            variant="primary"
            fullWidth
          >
            {standaloneLoading ? 'Converting...' : 'Convert'}
          </Button>
          
          {standaloneError && (
            <div className="error-message">{standaloneError}</div>
          )}
        </div>
        
        <div className="target-panel">
          <h2>Converted Code</h2>
          <select value={targetDialect} onChange={(e) => setTargetDialect(e.target.value)}>
            <option value="redshift">Redshift</option>
            <option value="postgres">PostgreSQL</option>
            <option value="bigquery">BigQuery</option>
            <option value="snowflake">Snowflake</option>
          </select>
          
          <CodeEditor
            value={standaloneJob?.target_code || ''}
            language="sql"
            readOnly
            placeholder="Converted code will appear here..."
          />
          
          {standaloneJob && (
            <div className="conversion-metadata">
              <span>Status: {standaloneJob.status}</span>
              <span>SQLGlot: {standaloneJob.sqlglot_success ? 'Yes' : 'No'}</span>
              <span>Model: {standaloneJob.bedrock_model || 'N/A'}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
```

## Security Design

### Workspace Isolation Implementation

**Middleware Layer:**

```python
# backend/middleware/workspace_middleware.py

from fastapi import Request, HTTPException
from backend.utils.jwt import decode_jwt_token

async def validate_workspace_access(request: Request):
    """
    Middleware to extract and validate workspace_id from JWT token.
    Attaches workspace_id to request state for downstream use.
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    token = auth_header.split(' ')[1]
    try:
        payload = decode_jwt_token(token)
        workspace_id = payload.get('workspace_id')
        user_id = payload.get('user_id')
        
        if not workspace_id or not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        
        # Attach to request state
        request.state.workspace_id = workspace_id
        request.state.user_id = user_id
        
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token validation failed: {str(e)}")
```

**Repository Layer Enforcement:**

```python
# backend/repositories/conversion_repository.py

class ConversionRepository:
    """Repository with built-in workspace isolation."""
    
    async def get_job(self, job_id: int, workspace_id: int) -> Optional[ConversionJob]:
        """Get job with workspace validation."""
        job = await self.db.query(ConversionJob).filter(
            ConversionJob.id == job_id,
            ConversionJob.workspace_id == workspace_id  # CRITICAL: Always filter by workspace_id
        ).first()
        
        if not job:
            # Log potential workspace isolation violation attempt
            logger.warning(
                f"Workspace isolation: Job {job_id} not found or access denied for workspace {workspace_id}",
                extra={
                    'job_id': job_id,
                    'workspace_id': workspace_id,
                    'event': 'workspace_isolation_violation_attempt'
                }
            )
        
        return job
    
    async def list_jobs(
        self,
        workspace_id: int,
        filters: Dict[str, Any] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Tuple[List[ConversionJob], int]:
        """List jobs with mandatory workspace filter."""
        query = self.db.query(ConversionJob).filter(
            ConversionJob.workspace_id == workspace_id  # CRITICAL: Always filter
        )
        
        # Apply additional filters
        if filters:
            if filters.get('status'):
                query = query.filter(ConversionJob.status == filters['status'])
            if filters.get('asset_type'):
                query = query.filter(ConversionJob.asset_type == filters['asset_type'])
        
        total = await query.count()
        jobs = await query.offset((page - 1) * page_size).limit(page_size).all()
        
        return jobs, total
```

### AWS IAM Policies

**Bedrock Access Policy:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BedrockModelInvocation",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-v2",
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-instant-v1"
      ]
    },
    {
      "Sid": "BedrockModelListing",
      "Effect": "Allow",
      "Action": [
        "bedrock:ListFoundationModels",
        "bedrock:GetFoundationModel"
      ],
      "Resource": "*"
    }
  ]
}
```

**DataSync Access Policy:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DataSyncAgentManagement",
      "Effect": "Allow",
      "Action": [
        "datasync:CreateAgent",
        "datasync:DescribeAgent",
        "datasync:ListAgents",
        "datasync:DeleteAgent"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DataSyncTaskExecution",
      "Effect": "Allow",
      "Action": [
        "datasync:CreateTask",
        "datasync:StartTaskExecution",
        "datasync:DescribeTaskExecution",
        "datasync:CancelTaskExecution"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DataSyncLocationManagement",
      "Effect": "Allow",
      "Action": [
        "datasync:CreateLocationS3",
        "datasync:CreateLocationObjectStorage",
        "datasync:DescribeLocation*"
      ],
      "Resource": "*"
    }
  ]
}
```

### Rate Limiting Implementation

```python
# backend/services/rate_limiter.py

from datetime import datetime, timedelta
from typing import Optional
import redis

class RateLimiter:
    """Rate limiter for Bedrock API calls per workspace."""
    
    def __init__(self, redis_client: redis.Redis, config: RateLimitConfig):
        self.redis = redis_client
        self.config = config
    
    async def check_rate_limit(
        self,
        workspace_id: int,
        operation: str = 'bedrock_invoke'
    ) -> tuple[bool, Optional[int]]:
        """
        Check if workspace has exceeded rate limit.
        
        Returns:
            (allowed, retry_after_seconds)
        """
        key = f"rate_limit:{operation}:workspace:{workspace_id}"
        window_key = f"{key}:window"
        
        try:
            # Get current count
            current_count = await self.redis.get(key)
            current_count = int(current_count) if current_count else 0
            
            # Check limit
            limit = self.config.get_limit(operation)
            if current_count >= limit:
                # Get TTL for retry-after
                ttl = await self.redis.ttl(key)
                return False, ttl if ttl > 0 else 3600
            
            # Increment counter
            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, 3600)  # 1 hour window
            await pipe.execute()
            
            return True, None
            
        except redis.RedisError as e:
            # If Redis fails, allow the request (fail open)
            logger.warning(f"Rate limiter Redis error: {e}, allowing request")
            return True, None
    
    async def record_usage(
        self,
        workspace_id: int,
        operation: str,
        tokens_used: int = 0,
        cost_estimate: float = 0.0
    ):
        """Record API usage for cost tracking."""
        usage_key = f"usage:{operation}:workspace:{workspace_id}:{datetime.utcnow().strftime('%Y-%m-%d')}"
        
        try:
            pipe = self.redis.pipeline()
            pipe.hincrby(usage_key, 'count', 1)
            pipe.hincrby(usage_key, 'tokens', tokens_used)
            pipe.hincrbyfloat(usage_key, 'cost', cost_estimate)
            pipe.expire(usage_key, 86400 * 90)  # 90 days retention
            await pipe.execute()
        except redis.RedisError as e:
            logger.warning(f"Failed to record usage: {e}")
```



## Deployment Architecture

### Environment Configuration

**Required Environment Variables (.env):**

```bash
# AWS Bedrock Configuration
AWS_BEDROCK_REGION=us-east-1
AWS_BEDROCK_DEFAULT_MODEL=anthropic.claude-v2
BEDROCK_RATE_LIMIT_PER_WORKSPACE_HOUR=100
BEDROCK_ALLOWED_MODELS=anthropic.claude-v2,anthropic.claude-instant-v1,amazon.titan-text-express-v1

# AWS DataSync Configuration
AWS_DATASYNC_REGION=us-east-1
DATASYNC_AGENT_HEALTH_CHECK_INTERVAL_SECONDS=300
DATASYNC_TASK_TIMEOUT_SECONDS=3600

# Conversion Configuration
CONVERSION_PROMPT_TEMPLATES_DIR=backend/prompts
CONVERSION_MAX_RETRIES=3
CONVERSION_RETRY_DELAY_SECONDS=5
CONVERSION_BATCH_PARALLELISM=5
CONVERSION_CACHE_TTL_SECONDS=3600

# History Configuration
COPY_HISTORY_CACHE_TTL_SECONDS=300
TASK_HISTORY_CACHE_TTL_SECONDS=60
HISTORY_DEFAULT_PAGE_SIZE=50
HISTORY_MAX_PAGE_SIZE=200
HISTORY_AUTO_REFRESH_INTERVAL_SECONDS=30
COPY_COMMAND_TIMEOUT_SECONDS=7200

# Database Configuration (existing)
DATABASE_URL=postgresql://user:password@localhost:5432/datamiq
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# Redis Configuration (existing)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_redis_password
REDIS_SSL=true
REDIS_MAX_CONNECTIONS=50

# AWS General Configuration (existing)
AWS_REGION=us-east-1
KMS_KEY_ID=arn:aws:kms:us-east-1:123456789012:key/abc-123
SECRET_MANAGER_SECRET_NAME=datamiq-secrets
S3_EXPORT_BUCKET=datamiq-exports

# CloudWatch Configuration
CLOUDWATCH_LOG_GROUP=/aws/datamiq/application
CLOUDWATCH_METRICS_NAMESPACE=DataMIQ/Conversions
```

### Database Migration Execution

**Alembic Migration Script:**

```python
# backend/alembic/versions/001_add_conversion_tables.py

"""Add conversion tables

Revision ID: 001_conversion_tables
Revises: previous_revision
Create Date: 2026-01-25 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001_conversion_tables'
down_revision = 'previous_revision'
branch_labels = None
depends_on = None

def upgrade():
    # Create conversion_jobs table
    op.create_table(
        'conversion_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('batch_id', sa.Integer(), nullable=True),
        sa.Column('source_code', sa.Text(), nullable=False),
        sa.Column('target_code', sa.Text(), nullable=True),
        sa.Column('source_dialect', sa.String(50), nullable=False),
        sa.Column('target_dialect', sa.String(50), nullable=False),
        sa.Column('asset_type', sa.String(50), nullable=False),
        sa.Column('asset_name', sa.String(255), nullable=True),
        sa.Column('bedrock_model', sa.String(100), nullable=True),
        sa.Column('aws_region', sa.String(50), server_default='us-east-1'),
        sa.Column('prompt_template_path', sa.String(500), nullable=True),
        sa.Column('use_sqlglot', sa.Boolean(), server_default='true'),
        sa.Column('sqlglot_success', sa.Boolean(), server_default='false'),
        sa.Column('status', sa.String(50), server_default='pending', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), server_default='0'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['batch_id'], ['conversion_batches.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed')", name='chk_status'),
        sa.CheckConstraint("asset_type IN ('view', 'stored_procedure', 'function', 'trigger', 'table_ddl')", name='chk_asset_type')
    )
    
    # Create indexes
    op.create_index('idx_conversion_jobs_workspace_id', 'conversion_jobs', ['workspace_id'])
    op.create_index('idx_conversion_jobs_batch_id', 'conversion_jobs', ['batch_id'])
    op.create_index('idx_conversion_jobs_status', 'conversion_jobs', ['status'])
    op.create_index('idx_conversion_jobs_asset_type', 'conversion_jobs', ['asset_type'])
    op.create_index('idx_conversion_jobs_created_at', 'conversion_jobs', [sa.text('created_at DESC')])
    op.create_index('idx_conversion_jobs_workspace_status', 'conversion_jobs', ['workspace_id', 'status'])
    
    # Create conversion_batches table
    op.create_table(
        'conversion_batches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('migration_project_id', sa.Integer(), nullable=True),
        sa.Column('source_connection_id', sa.Integer(), nullable=False),
        sa.Column('target_connection_id', sa.Integer(), nullable=False),
        sa.Column('bedrock_model', sa.String(100), nullable=True),
        sa.Column('aws_region', sa.String(50), server_default='us-east-1'),
        sa.Column('prompt_template_path', sa.String(500), nullable=True),
        sa.Column('use_sqlglot', sa.Boolean(), server_default='true'),
        sa.Column('max_retries', sa.Integer(), server_default='3'),
        sa.Column('status', sa.String(50), server_default='pending', nullable=False),
        sa.Column('total_assets', sa.Integer(), server_default='0'),
        sa.Column('completed_assets', sa.Integer(), server_default='0'),
        sa.Column('failed_assets', sa.Integer(), server_default='0'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['migration_project_id'], ['migration_projects.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['source_connection_id'], ['connections.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['target_connection_id'], ['connections.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed')", name='chk_batch_status'),
        sa.CheckConstraint('completed_assets + failed_assets <= total_assets', name='chk_asset_counts')
    )
    
    # Create indexes for conversion_batches
    op.create_index('idx_conversion_batches_workspace_id', 'conversion_batches', ['workspace_id'])
    op.create_index('idx_conversion_batches_status', 'conversion_batches', ['status'])
    op.create_index('idx_conversion_batches_migration_project', 'conversion_batches', ['migration_project_id'])
    op.create_index('idx_conversion_batches_created_at', 'conversion_batches', [sa.text('created_at DESC')])
    
    # Create conversion_logs table
    op.create_table(
        'conversion_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('log_level', sa.String(20), server_default='INFO', nullable=False),
        sa.Column('step_name', sa.String(100), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['job_id'], ['conversion_jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.CheckConstraint("log_level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')", name='chk_log_level')
    )
    
    # Create indexes for conversion_logs
    op.create_index('idx_conversion_logs_job_id', 'conversion_logs', ['job_id'])
    op.create_index('idx_conversion_logs_workspace_id', 'conversion_logs', ['workspace_id'])
    op.create_index('idx_conversion_logs_timestamp', 'conversion_logs', [sa.text('timestamp DESC')])
    op.create_index('idx_conversion_logs_log_level', 'conversion_logs', ['log_level'])

def downgrade():
    op.drop_table('conversion_logs')
    op.drop_table('conversion_jobs')
    op.drop_table('conversion_batches')
```

**Migration Execution Commands:**

```bash
# Run migrations
cd backend
alembic upgrade head

# Verify migration
alembic current

# Rollback if needed
alembic downgrade -1
```

### Service Deployment Order

1. **Database Migration**: Run Alembic migrations first
2. **Backend Services**: Deploy updated backend with new services
3. **Frontend Build**: Build and deploy updated frontend
4. **Smoke Tests**: Run verification tests
5. **Monitoring Setup**: Configure CloudWatch dashboards and alarms

### Rollback Plan

**If deployment fails:**

1. **Database Rollback**: `alembic downgrade -1`
2. **Service Rollback**: Revert to previous backend version
3. **Frontend Rollback**: Revert to previous frontend build
4. **Verification**: Run smoke tests on rolled-back version
5. **Investigation**: Review logs and error reports

## Monitoring and Observability

### CloudWatch Metrics

**Conversion Metrics:**
```
DataMIQ/Conversions/JobsCreated (Count, per workspace)
DataMIQ/Conversions/JobsCompleted (Count, per workspace)
DataMIQ/Conversions/JobsFailed (Count, per workspace)
DataMIQ/Conversions/BedrockAPICalls (Count, per workspace)
DataMIQ/Conversions/BedrockAPIErrors (Count, per workspace)
DataMIQ/Conversions/BedrockAPILatency (Milliseconds, per workspace)
DataMIQ/Conversions/SQLGlotParseSuccess (Count, per dialect pair)
DataMIQ/Conversions/SQLGlotParseFailure (Count, per dialect pair)
DataMIQ/Conversions/CacheHitRatio (Percent)
```

**History Metrics:**
```
DataMIQ/History/CopyCommandsExecuted (Count, per migration)
DataMIQ/History/CopyCommandsSucceeded (Count, per migration)
DataMIQ/History/CopyCommandsFailed (Count, per migration)
DataMIQ/History/DataSyncTasksExecuted (Count, per migration)
DataMIQ/History/DataSyncTasksSucceeded (Count, per migration)
DataMIQ/History/DataSyncTasksFailed (Count, per migration)
DataMIQ/History/DataSyncAgentOffline (Count, per agent)
DataMIQ/History/TotalRowsLoaded (Count, per migration)
DataMIQ/History/TotalBytesLoaded (Bytes, per migration)
```

### CloudWatch Alarms

**Critical Alarms:**
```
ConversionFailureRateHigh: Conversion failure rate > 20% in 5 minutes
BedrockThrottlingErrors: Bedrock throttling errors > 10 in 5 minutes
CopyCommandFailureRateHigh: COPY failure rate > 10% in 10 minutes
DataSyncAgentOffline: Agent offline for > 5 minutes
DatabaseConnectionPoolExhausted: Available connections < 5
RedisConnectionFailures: Redis connection failures > 5 in 1 minute
```

### Logging Strategy

**Log Levels:**
- **DEBUG**: Detailed diagnostic information (SQLGlot parsing details, cache operations)
- **INFO**: General informational messages (job creation, completion, API calls)
- **WARNING**: Warning messages (Redis unavailable, retry attempts, cache misses)
- **ERROR**: Error messages (conversion failures, API errors, validation errors)
- **CRITICAL**: Critical issues (database connection loss, service unavailable)

**Structured Logging Format:**
```json
{
  "timestamp": "2026-01-25T10:00:00.000Z",
  "level": "INFO",
  "service": "conversion-service",
  "event": "conversion_job_created",
  "workspace_id": 1,
  "user_id": 123,
  "job_id": 456,
  "source_dialect": "bigquery",
  "target_dialect": "redshift",
  "asset_type": "view",
  "use_sqlglot": true,
  "request_id": "req-abc123"
}
```

## Summary

This design document provides comprehensive technical specifications for integrating 10 major feature groups with 45 requirements into the DataMIQ platform. The design ensures:

- **Seamless Integration**: New features integrate cleanly with existing architecture
- **Workspace Isolation**: Strict security boundaries enforced at all layers
- **Performance**: Efficient caching, query optimization, and parallel processing
- **Scalability**: Designed for concurrent batch processing and high-volume operations
- **Security**: AWS IAM roles, KMS encryption, rate limiting, and comprehensive access control
- **Maintainability**: Clear separation of concerns with well-defined service boundaries
- **Testability**: Comprehensive unit, integration, and property-based test coverage with 18 correctness properties
- **Observability**: Detailed CloudWatch metrics, alarms, and structured logging

The implementation follows all existing architecture patterns, security standards, and best practices documented in the project guidelines.

