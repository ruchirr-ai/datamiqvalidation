"""
ChatAgent Router
Handles AI-powered chat assistance for assessments with Claude AI
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
import logging
import os
import json
import boto3
from botocore.exceptions import ClientError

from database import get_db
from services.context_service import ContextService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chatagent", tags=["chatagent"])

# Claude AI Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
CLAUDE_MAX_TOKENS = int(os.getenv("CLAUDE_MAX_TOKENS", "4096"))
CLAUDE_TEMPERATURE = float(os.getenv("CLAUDE_TEMPERATURE", "0.7"))

# AWS Bedrock Configuration
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
CLAUDE_USE_BEDROCK = os.getenv("CLAUDE_USE_BEDROCK", "false").lower() == "true"
CLAUDE_MODEL_ID = os.getenv("CLAUDE_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")

# Initialize Claude client based on configuration priority
anthropic_client = None
bedrock_runtime = None

# Priority 1: Use Bedrock if explicitly enabled
if CLAUDE_USE_BEDROCK:
    try:
        logger.info(f"Initializing Bedrock with region={AWS_REGION}, model={CLAUDE_MODEL_ID}")
        bedrock_runtime = boto3.client(
            service_name='bedrock-runtime',
            region_name=AWS_REGION,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
        )
        logger.info("✅ AWS Bedrock client initialized successfully")
        logger.info(f"Using Claude via Bedrock: {CLAUDE_MODEL_ID}")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Bedrock client: {e}")
        bedrock_runtime = None

# Priority 2: Use Anthropic API if Bedrock not enabled and valid API key exists
elif ANTHROPIC_API_KEY and not ANTHROPIC_API_KEY.startswith("sk-ant-api03-your-key-here"):
    try:
        from anthropic import Anthropic
        anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
        logger.info("✅ Claude AI client (Anthropic API) initialized successfully")
        logger.info(f"Using Claude via Anthropic API: {CLAUDE_MODEL}")
    except Exception as e:
        logger.warning(f"❌ Failed to initialize Claude AI client: {e}")

if not anthropic_client and not bedrock_runtime:
    logger.warning("⚠️ Claude AI not configured, using fallback knowledge base")


class ChatRequest(BaseModel):
    """Chat request model"""
    message: str
    context: Optional[str] = "dashboard"
    workspaceId: Optional[str] = "default"
    conversationHistory: Optional[list] = []


class ChatResponse(BaseModel):
    """Chat response model"""
    response: str


# Knowledge base for the ChatAgent with structured responses
KNOWLEDGE_BASE = {
    "migration_risk": """## Migration Risk Analysis

### Overview
Migration risk analysis helps identify potential issues before migrating your database.

### Key Risk Categories

**1. Data Loss Risks**
- Incompatible data types
- Precision loss in numeric conversions
- Character encoding issues
- Truncation of data

**2. Schema Compatibility Risks**
- Unsupported database features
- Missing constraints or indexes
- Stored procedures incompatibility
- Trigger and function differences

**3. Performance Risks**
- Query performance degradation
- Index strategy differences
- Connection pooling changes
- Resource utilization patterns

**4. Application Risks**
- Breaking changes in SQL syntax
- Driver compatibility issues
- Connection string changes
- Transaction handling differences

### How to Perform Risk Analysis

1. **Run Schema Analysis**
   - Navigate to Assessments
   - Create new assessment
   - Select source database
   - Enable schema analysis

2. **Run Compatibility Check**
   - Select both source and target databases
   - Enable compatibility analysis
   - Review compatibility report

3. **Review Risk Report**
   - Check critical issues (red flags)
   - Review warnings (yellow flags)
   - Plan mitigation strategies

4. **Test with Sample Data**
   - Create test migration
   - Validate data integrity
   - Check application functionality

### Best Practices

- Always run risk analysis before production migration
- Address critical issues first
- Test with representative data samples
- Document all identified risks
- Create rollback plan""",

    "schema_compatibility": """## Schema Compatibility Analysis

### What It Checks

**Data Type Compatibility**
- VARCHAR vs TEXT
- INTEGER vs BIGINT
- DATETIME vs TIMESTAMP
- DECIMAL precision and scale
- ENUM vs VARCHAR
- JSON vs TEXT

**Database Features**
- Stored procedures
- Triggers
- Views and materialized views
- Functions (built-in and custom)
- Sequences and auto-increment
- Partitioning strategies

**Constraints**
- Primary keys
- Foreign keys
- Unique constraints
- Check constraints
- Default values
- NOT NULL constraints

**Indexes**
- B-tree indexes
- Hash indexes
- Full-text indexes
- Spatial indexes
- Partial indexes

### Running Compatibility Check

1. **Create Assessment**
   - Go to Assessments page
   - Click "New Assessment"
   - Enter assessment name

2. **Select Databases**
   - Source: Your current database
   - Target: Destination database
   - Both connections must be active

3. **Configure Options**
   - Enable "Schema Compatibility Check"
   - Enable "Data Type Mapping"
   - Set sampling rate (optional)

4. **Review Results**
   - Green: Fully compatible
   - Yellow: Compatible with warnings
   - Red: Incompatible, requires changes

### Common Compatibility Issues

**PostgreSQL → BigQuery**
- Sequences → Auto-increment columns
- Triggers → Cloud Functions
- Stored procedures → BigQuery UDFs

**MySQL → PostgreSQL**
- ENUM → VARCHAR with CHECK constraint
- AUTO_INCREMENT → SERIAL
- TINYINT → SMALLINT

**Oracle → PostgreSQL**
- NUMBER → NUMERIC
- VARCHAR2 → VARCHAR
- ROWNUM → ROW_NUMBER()

### Resolution Strategies

1. **Modify Source Schema**
   - Change incompatible data types
   - Remove unsupported features
   - Simplify complex structures

2. **Use Data Type Mapping**
   - Configure automatic conversions
   - Handle special cases
   - Validate transformations

3. **Refactor Application**
   - Update SQL queries
   - Replace database-specific functions
   - Adjust connection handling"""
}


def get_ai_response(message: str, context: str, conversation_history: list = [], user_context: dict = None) -> str:
    """
    Generate AI response using Claude AI or fallback to knowledge base
    """
    
    # Try Bedrock first if available
    if bedrock_runtime:
        try:
            return get_bedrock_response(message, context, conversation_history, user_context)
        except Exception as e:
            logger.error(f"Bedrock error: {e}, falling back to knowledge base")
    
    # Try Anthropic API if available
    elif anthropic_client:
        try:
            return get_claude_response(message, context, conversation_history, user_context)
        except Exception as e:
            logger.error(f"Claude AI error: {e}, falling back to knowledge base")
    
    # Fallback to knowledge base
    return get_knowledge_base_response(message, context)


def get_claude_response(message: str, context: str, conversation_history: list = [], user_context: dict = None) -> str:
    """
    Get response from Claude AI (Anthropic API) with user context
    """
    # Build system prompt with user context
    context_info = ""
    if user_context:
        context_info = f"""

## User's Current Workspace Data

**Assessments:** {len(user_context.get('assessments', []))} assessment(s)
{_format_assessments(user_context.get('assessments', []))}

**Connections:** {len(user_context.get('connections', []))} connection(s)
{_format_connections(user_context.get('connections', []))}

**Status:** {user_context.get('error_summary', 'All systems operational')}

IMPORTANT: When answering questions, reference the user's ACTUAL data above. Be specific about their assessments and connections by name."""
    
    system_prompt = """You are an expert AI assistant for DataMIQ, a database migration and assessment platform.

Your expertise includes:
- Database migration planning and execution
- Schema analysis and compatibility checking
- Migration risk assessment
- Data profiling and quality analysis
- BigQuery, PostgreSQL, Redshift, and other databases
- Assessment report generation and interpretation
- Troubleshooting migration issues

Guidelines:
- Always respond in structured markdown format with headings (##, ###), bullet points, and numbered lists
- Be concise but comprehensive
- Provide actionable advice and step-by-step instructions
- Use professional technical language
- Focus on practical solutions
- Include code examples when relevant
- Highlight potential risks and best practices
- ALWAYS reference the user's actual data when available (their specific assessments, connections, etc.)
- Be personalized - mention their specific assessment names, connection names, and statuses

Current context: User is on the {context} page of the platform.{context_info}""".format(context=context, context_info=context_info)

    # Build conversation messages
    messages = []
    
    # Add conversation history
    for msg in conversation_history[-5:]:
        messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", "")
        })
    
    # Add current message
    messages.append({
        "role": "user",
        "content": message
    })
    
    # Call Claude API
    response = anthropic_client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=CLAUDE_MAX_TOKENS,
        temperature=CLAUDE_TEMPERATURE,
        system=system_prompt,
        messages=messages
    )
    
    # Extract text from response
    if response.content and len(response.content) > 0:
        return response.content[0].text
    
    return "I apologize, but I couldn't generate a response. Please try again."


def get_bedrock_response(message: str, context: str, conversation_history: list = [], user_context: dict = None) -> str:
    """
    Get response from Claude AI via AWS Bedrock with user context
    """
    # Build system prompt with user context
    context_info = ""
    if user_context:
        context_info = f"""

## User's Current Workspace Data

**Assessments:** {len(user_context.get('assessments', []))} assessment(s)
{_format_assessments(user_context.get('assessments', []))}

**Connections:** {len(user_context.get('connections', []))} connection(s)
{_format_connections(user_context.get('connections', []))}

**Status:** {user_context.get('error_summary', 'All systems operational')}

IMPORTANT: When answering questions, reference the user's ACTUAL data above. Be specific about their assessments and connections by name."""
    
    system_prompt = """You are an expert AI assistant for DataMIQ, a database migration and assessment platform.

Your expertise includes:
- Database migration planning and execution
- Schema analysis and compatibility checking
- Migration risk assessment
- Data profiling and quality analysis
- BigQuery, PostgreSQL, Redshift, and other databases
- Assessment report generation and interpretation
- Troubleshooting migration issues

Guidelines:
- Always respond in structured markdown format with headings (##, ###), bullet points, and numbered lists
- Be concise but comprehensive
- Provide actionable advice and step-by-step instructions
- Use professional technical language
- Focus on practical solutions
- Include code examples when relevant
- Highlight potential risks and best practices
- ALWAYS reference the user's actual data when available (their specific assessments, connections, etc.)
- Be personalized - mention their specific assessment names, connection names, and statuses

Current context: User is on the {context} page of the platform.{context_info}""".format(context=context, context_info=context_info)

    # Build conversation messages
    messages = []
    
    # Add conversation history
    for msg in conversation_history[-5:]:
        messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", "")
        })
    
    # Add current message
    messages.append({
        "role": "user",
        "content": message
    })
    
    # Prepare request body for Bedrock
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": CLAUDE_MAX_TOKENS,
        "temperature": CLAUDE_TEMPERATURE,
        "system": system_prompt,
        "messages": messages
    }
    
    # Call Bedrock API
    response = bedrock_runtime.invoke_model(
        modelId=CLAUDE_MODEL_ID,
        body=json.dumps(request_body)
    )
    
    # Parse response
    response_body = json.loads(response['body'].read())
    
    if response_body.get('content') and len(response_body['content']) > 0:
        return response_body['content'][0]['text']
    
    return "I apologize, but I couldn't generate a response. Please try again."


def get_knowledge_base_response(message: str, context: str) -> str:
    """
    Fallback response using local knowledge base
    """
    message_lower = message.lower()
    
    # Check for greetings
    if any(word in message_lower for word in ["hello", "hi", "hey", "greetings"]):
        return """Hello! I'm your Assessment AI Assistant powered by Claude AI. 

I can help you with:
- Migration risk analysis and assessment
- Schema compatibility checking
- Creating and managing assessments
- Understanding schema analysis
- Running compatibility checks
- Viewing and exporting reports
- Data profiling insights
- Database connections
- Scheduling jobs
- Troubleshooting issues

What would you like to know?"""
    
    # Check for migration risk analysis
    if any(word in message_lower for word in ["migration risk", "risk analysis", "analyze risk", "risks of migrating"]):
        return KNOWLEDGE_BASE["migration_risk"]
    
    # Check for schema compatibility
    if any(word in message_lower for word in ["schema compatibility", "compatibility check", "compatible"]):
        return KNOWLEDGE_BASE["schema_compatibility"]
    
    # Check for thanks
    if any(word in message_lower for word in ["thank", "thanks", "appreciate"]):
        return "You're welcome! Feel free to ask if you have any other questions about assessments or migrations."
    
    # Default response
    return """I'm not sure I understand your question. 

## I Can Help With

**Assessments**
- Creating and running assessments
- Understanding results
- Troubleshooting failures

**Analysis**
- Schema analysis
- Compatibility checks
- Data profiling

**Operations**
- Connecting databases
- Scheduling jobs
- Exporting reports

Could you please rephrase your question or choose from one of the suggested topics?"""


def _format_assessments(assessments: list) -> str:
    """Format assessments for context"""
    if not assessments:
        return "- No assessments created yet"
    
    lines = []
    for assessment in assessments[:5]:  # Show top 5
        status_emoji = "✅" if assessment['status'] == 'completed' else "❌" if assessment['status'] == 'failed' else "🔄"
        lines.append(f"- {status_emoji} **{assessment['name']}** ({assessment['status']}) - {assessment['total_tables']} tables, {assessment['total_size_mb']}MB")
    
    if len(assessments) > 5:
        lines.append(f"- ... and {len(assessments) - 5} more")
    
    return "\n".join(lines)


def _format_connections(connections: list) -> str:
    """Format connections for context"""
    if not connections:
        return "- No connections configured yet"
    
    lines = []
    for conn in connections[:5]:  # Show top 5
        status_emoji = "✅" if conn['status'] == 'connected' else "❌" if conn['status'] == 'error' else "⚪"
        lines.append(f"- {status_emoji} **{conn['name']}** ({conn['db_type']}) - {conn['database']}")
    
    if len(connections) > 5:
        lines.append(f"- ... and {len(connections) - 5} more")
    
    return "\n".join(lines)


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Handle chat messages from the ChatAgent with context awareness
    """
    try:
        logger.info(f"ChatAgent request: {request.message} (context: {request.context})")
        
        if not request.message or not request.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")
        
        # Gather user context (workspace_id=1, user_id=1 for now - should come from auth)
        user_context_data = None
        try:
            context_service = ContextService(db, redis_client=None)  # Redis not configured yet
            user_context = context_service.gather_context(
                user_id=1,  # TODO: Get from authenticated user
                workspace_id=1,  # TODO: Get from authenticated user
                page_context=request.context
            )
            user_context_data = user_context.dict()
            logger.info(f"Gathered context: {len(user_context.assessments)} assessments, {len(user_context.connections)} connections")
        except Exception as e:
            logger.warning(f"Failed to gather context: {e}, continuing without context")
        
        # Generate response with context
        response_text = get_ai_response(request.message, request.context, request.conversationHistory, user_context_data)
        
        logger.info(f"ChatAgent response generated successfully")
        
        return ChatResponse(response=response_text)
        
    except Exception as e:
        logger.error(f"ChatAgent error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process chat message")
