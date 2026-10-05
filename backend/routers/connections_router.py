"""
Connections Router
Handles database connection management and testing
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# Database clients
try:
    from google.cloud import bigquery
    from google.oauth2 import service_account
    BIGQUERY_AVAILABLE = True
except ImportError:
    BIGQUERY_AVAILABLE = False

try:
    import pymongo
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False

try:
    import psycopg2
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False

try:
    import pymysql
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False

try:
    import pyodbc
    SQLSERVER_AVAILABLE = True
except ImportError:
    SQLSERVER_AVAILABLE = False

try:
    import clickhouse_connect
    CLICKHOUSE_AVAILABLE = True
except ImportError:
    CLICKHOUSE_AVAILABLE = False

from database import get_db
from models.connection import Connection, Base
from services.kms_encryption_service import get_kms_encryption_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/connections", tags=["connections"])


# Helper function to get decrypted connection params
def get_decrypted_connection_params(connection: Connection) -> Dict[str, Any]:
    """
    Get decrypted connection parameters.
    
    Tries encrypted params first, falls back to unencrypted for backward compatibility.
    """
    # Try encrypted params first (new method)
    if connection.connection_params_encrypted:
        try:
            kms_service = get_kms_encryption_service()
            encryption_context = {
                'connection_id': str(connection.id),
                'field': 'connection_params'
            }
            params_json = kms_service.decrypt(
                connection.connection_params_encrypted,
                encryption_context
            )
            return json.loads(params_json)
        except Exception as e:
            logger.error(f"Failed to decrypt connection params for connection {connection.id}: {e}")
            # Fall through to unencrypted params
    
    # Fall back to unencrypted params (backward compatibility)
    if connection.connection_params:
        return connection.connection_params
    
    return {}


# Request Models
class TestConnectionRequest(BaseModel):
    """Request model for testing database connections"""
    database: str = Field(..., description="Database type (bigquery, mongodb, postgresql, etc.)")
    connection_params: Dict[str, Any] = Field(..., description="Connection parameters")

    class Config:
        json_schema_extra = {
            "example": {
                "database": "bigquery",
                "connection_params": {
                    "project_id": "my-gcp-project",
                    "region": "us-central1",
                    "service_account_key": "{...json key...}"
                }
            }
        }


class CreateConnectionRequest(BaseModel):
    """Request model for creating a connection"""
    name: str = Field(..., description="Connection name")
    type: str = Field(..., description="Connection type (source or target)")
    database: str = Field(..., description="Database type")
    connection_params: Dict[str, Any] = Field(..., description="Connection parameters")
    created_by: str = Field(default="system", description="User who created the connection")
    status: str = Field(default="disconnected", description="Initial connection status")
    last_tested_at: Optional[str] = Field(default=None, description="Last tested timestamp")


class ConnectionResponse(BaseModel):
    """Response model for connection operations"""
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None


class ConnectionListResponse(BaseModel):
    """Response model for connection list"""
    id: int
    name: str
    type: str
    database: str
    created_by: str
    status: str
    last_tested_at: Optional[str]
    created_at: str
    updated_at: str


# Connection Testing Functions
def test_bigquery_connection(params: Dict[str, Any]) -> ConnectionResponse:
    """Test BigQuery connection"""
    if not BIGQUERY_AVAILABLE:
        return ConnectionResponse(
            success=False,
            message="BigQuery client library not installed. Install with: pip install google-cloud-bigquery"
        )
    
    try:
        # Extract parameters - handle multiple field name variations
        project_id = params.get('project_id') or params.get('projectId')
        service_account_key = (
            params.get('service_account_key') or 
            params.get('serviceAccountKey') or 
            params.get('credentials_json') or
            params.get('credentialsJson')
        )
        region = params.get('region') or params.get('location', 'us-central1')
        
        logger.info(f"Testing BigQuery connection for project: {project_id}")
        
        if not project_id:
            return ConnectionResponse(
                success=False,
                message="Project ID is required"
            )
        
        if not service_account_key:
            return ConnectionResponse(
                success=False,
                message="Service Account Key is required"
            )
        
        # Parse service account JSON
        try:
            if isinstance(service_account_key, str):
                sa_info = json.loads(service_account_key)
            else:
                sa_info = service_account_key
        except json.JSONDecodeError as e:
            logger.error(f"Invalid service account JSON: {str(e)}")
            return ConnectionResponse(
                success=False,
                message=f"Invalid service account JSON: {str(e)}"
            )
        
        # Validate required fields in service account JSON
        required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
        missing_fields = [field for field in required_fields if field not in sa_info]
        if missing_fields:
            logger.error(f"Missing required fields in service account JSON: {missing_fields}")
            return ConnectionResponse(
                success=False,
                message=f"Service account JSON is missing required fields: {', '.join(missing_fields)}"
            )
        
        # Create credentials
        logger.info("Creating BigQuery credentials...")
        credentials = service_account.Credentials.from_service_account_info(sa_info)
        
        # Create BigQuery client
        logger.info(f"Creating BigQuery client for project {project_id} in region {region}...")
        client = bigquery.Client(
            credentials=credentials,
            project=project_id,
            location=region
        )
        
        # Test connection with a simple query
        logger.info("Testing BigQuery connection with test query...")
        query = "SELECT 1 as test"
        query_job = client.query(query)
        results = list(query_job.result())
        
        if results and results[0].test == 1:
            logger.info("BigQuery connection test successful")
            return ConnectionResponse(
                success=True,
                message="Successfully connected to BigQuery",
                details={
                    "project_id": project_id,
                    "region": region,
                    "service_account_email": sa_info.get('client_email', 'N/A')
                }
            )
        else:
            logger.error("BigQuery connection test query failed")
            return ConnectionResponse(
                success=False,
                message="Connection test query failed"
            )
            
    except Exception as e:
        logger.error(f"BigQuery connection test failed: {str(e)}", exc_info=True)
        return ConnectionResponse(
            success=False,
            message=f"Connection failed: {str(e)}"
        )


def test_mongodb_connection(params: Dict[str, Any]) -> ConnectionResponse:
    """Test MongoDB connection"""
    if not MONGODB_AVAILABLE:
        return ConnectionResponse(
            success=False,
            message="MongoDB client library not installed. Install with: pip install pymongo"
        )
    
    try:
        # Extract parameters
        host = params.get('host', 'localhost')
        port = params.get('port', 27017)
        database = params.get('database', 'test')
        username = params.get('username')
        password = params.get('password')
        auth_source = params.get('auth_source', 'admin')
        use_ssl = params.get('use_ssl', False)
        
        # Build connection string
        if username and password:
            connection_string = f"mongodb://{username}:{password}@{host}:{port}/{database}?authSource={auth_source}"
        else:
            connection_string = f"mongodb://{host}:{port}/{database}"
        
        if use_ssl:
            connection_string += "&ssl=true"
        
        # Create client with timeout
        client = pymongo.MongoClient(
            connection_string,
            serverSelectionTimeoutMS=5000
        )
        
        # Test connection
        client.admin.command('ping')
        
        # Get server info
        server_info = client.server_info()
        
        client.close()
        
        return ConnectionResponse(
            success=True,
            message="Successfully connected to MongoDB",
            details={
                "host": host,
                "port": port,
                "database": database,
                "version": server_info.get('version', 'Unknown')
            }
        )
        
    except Exception as e:
        logger.error(f"MongoDB connection test failed: {str(e)}")
        return ConnectionResponse(
            success=False,
            message=f"Connection failed: {str(e)}"
        )


def test_postgresql_connection(params: Dict[str, Any]) -> ConnectionResponse:
    """Test PostgreSQL connection"""
    if not POSTGRESQL_AVAILABLE:
        return ConnectionResponse(
            success=False,
            message="PostgreSQL client library not installed. Install with: pip install psycopg2-binary"
        )
    
    try:
        # Extract parameters - handle multiple field name variations
        host = params.get('host') or params.get('server_name')
        port = params.get('port', 5432)
        database = params.get('database') or params.get('database_name')
        username = params.get('username') or params.get('user')
        password = params.get('password', '')
        
        logger.info(f"Testing PostgreSQL/Redshift connection to {host}:{port}/{database}")
        
        # Validate required parameters
        if not host:
            return ConnectionResponse(
                success=False,
                message="Server name/host is required"
            )
        
        if not database:
            return ConnectionResponse(
                success=False,
                message="Database name is required"
            )
        
        if not username:
            return ConnectionResponse(
                success=False,
                message="Username is required"
            )
        
        # Create connection
        logger.info(f"Attempting connection to {host}:{port} as user {username}")
        conn = psycopg2.connect(
            host=host,
            port=int(port),
            database=database,
            user=username,
            password=password,
            connect_timeout=10
        )
        
        # Test query
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        logger.info(f"PostgreSQL/Redshift connection successful: {version}")
        
        return ConnectionResponse(
            success=True,
            message="Successfully connected to database",
            details={
                "host": host,
                "port": port,
                "database": database,
                "username": username,
                "version": version.split()[0] if version else "Unknown"
            }
        )
        
    except psycopg2.OperationalError as e:
        error_msg = str(e).strip()
        logger.error(f"PostgreSQL/Redshift connection failed (OperationalError): {error_msg}")
        
        # Provide more specific error messages
        if "could not connect to server" in error_msg.lower():
            return ConnectionResponse(
                success=False,
                message=f"Could not connect to server. Please check:\n• Server name/host is correct\n• Port is correct (default: 5432 for PostgreSQL, 5439 for Redshift)\n• Network connectivity\n• Firewall rules\n\nError: {error_msg}"
            )
        elif "password authentication failed" in error_msg.lower():
            return ConnectionResponse(
                success=False,
                message=f"Authentication failed. Please check:\n• Username is correct\n• Password is correct\n• User has permission to access the database\n\nError: {error_msg}"
            )
        elif "database" in error_msg.lower() and "does not exist" in error_msg.lower():
            return ConnectionResponse(
                success=False,
                message=f"Database does not exist. Please check:\n• Database name is correct\n• Database exists on the server\n\nError: {error_msg}"
            )
        elif "timeout" in error_msg.lower():
            return ConnectionResponse(
                success=False,
                message=f"Connection timeout. Please check:\n• Server is reachable\n• Network connectivity\n• Firewall rules\n• Server is running\n\nError: {error_msg}"
            )
        else:
            return ConnectionResponse(
                success=False,
                message=f"Connection failed: {error_msg}"
            )
    
    except psycopg2.DatabaseError as e:
        error_msg = str(e).strip()
        logger.error(f"PostgreSQL/Redshift database error: {error_msg}")
        return ConnectionResponse(
            success=False,
            message=f"Database error: {error_msg}"
        )
    
    except Exception as e:
        error_msg = str(e).strip()
        logger.error(f"PostgreSQL/Redshift connection test failed: {error_msg}", exc_info=True)
        return ConnectionResponse(
            success=False,
            message=f"Connection failed: {error_msg}"
        )


def test_mysql_connection(params: Dict[str, Any]) -> ConnectionResponse:
    """Test MySQL connection"""
    if not MYSQL_AVAILABLE:
        return ConnectionResponse(
            success=False,
            message="MySQL client library not installed. Install with: pip install pymysql"
        )
    
    try:
        # Extract parameters
        host = params.get('host', 'localhost')
        port = params.get('port', 3306)
        database = params.get('database', 'mysql')
        username = params.get('username', 'root')
        password = params.get('password', '')
        
        # Create connection
        conn = pymysql.connect(
            host=host,
            port=port,
            database=database,
            user=username,
            password=password,
            connect_timeout=5
        )
        
        # Test query
        cursor = conn.cursor()
        cursor.execute("SELECT VERSION();")
        version = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return ConnectionResponse(
            success=True,
            message="Successfully connected to MySQL",
            details={
                "host": host,
                "port": port,
                "database": database,
                "version": version
            }
        )
        
    except Exception as e:
        logger.error(f"MySQL connection test failed: {str(e)}")
        return ConnectionResponse(
            success=False,
            message=f"Connection failed: {str(e)}"
        )


def test_sqlserver_connection(params: Dict[str, Any]) -> ConnectionResponse:
    """Test SQL Server connection"""
    if not SQLSERVER_AVAILABLE:
        return ConnectionResponse(
            success=False,
            message="SQL Server client library not installed. Install with: pip install pyodbc"
        )

    try:
        # Extract parameters
        host = params.get('host', 'localhost')
        port = params.get('port', 1433)
        database = params.get('database_name') or params.get('database', 'master')
        instance_name = params.get('instance_name', '')
        username = params.get('username', '')
        password = params.get('password', '')

        # Convert windows_auth to boolean (handle string "true"/"false" and boolean values)
        windows_auth_value = params.get('windows_auth', False)
        if isinstance(windows_auth_value, str):
            windows_auth = windows_auth_value.lower() in ('true', '1', 'yes')
        else:
            windows_auth = bool(windows_auth_value)

        driver = params.get('driver', 'ODBC Driver 17 for SQL Server')

        logger.info(f"Testing SQL Server connection to {host}:{port}/{database}")

        # Build server string
        if instance_name:
            server = f"{host}\\{instance_name}"
        else:
            if host.lower() in ['localhost', '127.0.0.1', '.'] and port == 1433:
                server = host
            else:
                server = f"{host},{port}"

        # Build connection string based on authentication type
        if windows_auth:
            connection_string = (
                f"DRIVER={{{driver}}};"
                f"SERVER={server};"
                f"DATABASE={database};"
                f"Trusted_Connection=yes;"
                f"TrustServerCertificate=yes;"
            )
            logger.info(f"Using Windows Authentication for {server}")
        else:
            if not username:
                return ConnectionResponse(
                    success=False,
                    message="Username is required for SQL Server authentication"
                )
            connection_string = (
                f"DRIVER={{{driver}}};"
                f"SERVER={server};"
                f"DATABASE={database};"
                f"UID={username};"
                f"PWD={password};"
                f"TrustServerCertificate=yes;"
            )
            logger.info(f"Using SQL Server Authentication for {server} as user {username}")

        # Create connection
        conn = pyodbc.connect(connection_string, timeout=10)

        # Test query
        cursor = conn.cursor()
        cursor.execute("SELECT @@VERSION;")
        version = cursor.fetchone()[0]

        cursor.execute("SELECT @@SERVERNAME;")
        server_name = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        logger.info(f"SQL Server connection successful: {server_name}")
        version_line = version.split('\n')[0] if version else "Unknown"

        return ConnectionResponse(
            success=True,
            message="Successfully connected to SQL Server",
            details={
                "host": host,
                "port": port,
                "database": database,
                "server_name": server_name,
                "version": version_line,
                "authentication": "Windows Authentication" if windows_auth else "SQL Server Authentication"
            }
        )

    except pyodbc.Error as e:
        error_msg = str(e).strip()
        logger.error(f"SQL Server connection failed (pyodbc.Error): {error_msg}")

        if "driver" in error_msg.lower() and "not found" in error_msg.lower():
            return ConnectionResponse(
                success=False,
                message=f"ODBC driver not found. Please install the ODBC driver. Error: {error_msg}"
            )
        elif "login failed" in error_msg.lower() or "authentication failed" in error_msg.lower():
            return ConnectionResponse(
                success=False,
                message=f"Authentication failed. Please check username, password, and permissions. Error: {error_msg}"
            )
        elif "could not open" in error_msg.lower() or "cannot open" in error_msg.lower():
            return ConnectionResponse(
                success=False,
                message=f"Could not connect to server. Check host, port, and network connectivity. Error: {error_msg}"
            )
        elif "timeout" in error_msg.lower():
            return ConnectionResponse(
                success=False,
                message=f"Connection timeout. Check server reachability and firewall rules. Error: {error_msg}"
            )
        else:
            return ConnectionResponse(
                success=False,
                message=f"Connection failed: {error_msg}"
            )

    except Exception as e:
        error_msg = str(e).strip()
        logger.error(f"SQL Server connection test failed: {error_msg}", exc_info=True)
        return ConnectionResponse(
            success=False,
            message=f"Connection failed: {error_msg}"
        )


def test_clickhouse_connection(params: Dict[str, Any]) -> ConnectionResponse:
    """Test ClickHouse connection"""
    if not CLICKHOUSE_AVAILABLE:
        return ConnectionResponse(
            success=False,
            message="ClickHouse client library not installed. Install with: pip install clickhouse-connect"
        )

    try:
        host = params.get('host', '')
        port = int(params.get('port', 8443))
        database = params.get('database') or params.get('database_name', 'default')
        username = params.get('username', 'default')
        password = params.get('password', '')
        secure = str(params.get('secure', 'false')).lower() in ('true', '1', 'yes')

        if not host:
            return ConnectionResponse(success=False, message="Host is required")

        logger.info(f"Testing ClickHouse connection to {host}:{port}/{database} (secure={secure})")

        client = clickhouse_connect.get_client(
            host=host,
            port=port,
            database=database,
            username=username,
            password=password,
            secure=secure,
            connect_timeout=10,
        )

        # Test with a simple query
        result = client.query('SELECT version() AS version, currentDatabase() AS db')
        version = result.result_rows[0][0] if result.result_rows else 'unknown'
        db_name = result.result_rows[0][1] if result.result_rows else database

        client.close()

        logger.info(f"ClickHouse connection successful: version={version}, database={db_name}")
        return ConnectionResponse(
            success=True,
            message=f"Successfully connected to ClickHouse",
            details={
                "host": host,
                "port": port,
                "database": db_name,
                "version": version,
                "secure": secure,
            }
        )

    except Exception as e:
        error_msg = str(e).strip()
        logger.error(f"ClickHouse connection failed: {error_msg}")
        return ConnectionResponse(
            success=False,
            message=f"ClickHouse connection failed: {error_msg}"
        )


class UpdateStatusRequest(BaseModel):
    """Request model for updating connection status"""
    status: str = Field(..., description="Connection status")
    last_tested_at: str = Field(..., description="Last tested timestamp")


# API Endpoints
@router.post("/test", response_model=ConnectionResponse)
async def test_connection(request: TestConnectionRequest):
    """
    Test database connection
    
    Supports: BigQuery, MongoDB, PostgreSQL, MySQL, DocumentDB, Redshift, Oracle, SQL Server, ClickHouse
    """
    logger.info(f"Testing {request.database} connection")
    
    database_type = request.database.lower()
    
    # Route to appropriate test function
    if database_type == 'bigquery':
        return test_bigquery_connection(request.connection_params)
    
    elif database_type in ['mongodb', 'documentdb']:
        return test_mongodb_connection(request.connection_params)
    
    elif database_type == 'postgresql':
        return test_postgresql_connection(request.connection_params)
    
    elif database_type == 'mysql':
        return test_mysql_connection(request.connection_params)
    
    elif database_type == 'redshift':
        # Redshift uses PostgreSQL protocol
        return test_postgresql_connection(request.connection_params)
    
    elif database_type == 'clickhouse':
        return test_clickhouse_connection(request.connection_params)
    
    elif database_type == 'oracle':
        return ConnectionResponse(
            success=False,
            message="Oracle connection testing not yet implemented. Install cx_Oracle library."
        )
    
    elif database_type == 'sqlserver':
        return test_sqlserver_connection(request.connection_params)
    
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported database type: {database_type}"
        )


@router.post("/{connection_id}/test", response_model=ConnectionResponse)
async def test_connection_by_id(connection_id: int, db: Session = Depends(get_db)):
    """
    Test an existing database connection by ID.

    Decrypts stored credentials server-side and runs the appropriate
    connectivity check.  Updates the connection status and last_tested_at
    in the database so the UI reflects the result on next fetch.
    """
    connection = db.query(Connection).filter(
        Connection.id == connection_id,
        Connection.is_active == True,
    ).first()

    if not connection:
        raise HTTPException(status_code=404, detail=f"Connection {connection_id} not found")

    # Get decrypted params
    params = get_decrypted_connection_params(connection)
    database_type = connection.database.lower()

    logger.info(f"Testing existing connection {connection_id} ({database_type})")

    # Route to the right test function
    if database_type == 'bigquery':
        result = test_bigquery_connection(params)
    elif database_type in ('mongodb', 'documentdb'):
        result = test_mongodb_connection(params)
    elif database_type == 'postgresql':
        result = test_postgresql_connection(params)
    elif database_type == 'mysql':
        result = test_mysql_connection(params)
    elif database_type == 'redshift':
        result = test_postgresql_connection(params)
    elif database_type == 'clickhouse':
        result = test_clickhouse_connection(params)
    elif database_type == 'sqlserver':
        result = test_sqlserver_connection(params)
    else:
        result = ConnectionResponse(success=False, message=f"Unsupported database type: {database_type}")

    # Persist the new status
    try:
        connection.status = 'connected' if result.success else 'disconnected'
        connection.last_tested_at = datetime.utcnow()
        connection.updated_at = datetime.utcnow()
        db.commit()
    except Exception as e:
        logger.error(f"Failed to update connection status after test: {e}")
        db.rollback()

    return result


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "connections",
        "available_databases": {
            "bigquery": BIGQUERY_AVAILABLE,
            "mongodb": MONGODB_AVAILABLE,
            "postgresql": POSTGRESQL_AVAILABLE,
            "mysql": MYSQL_AVAILABLE,
            "sqlserver": SQLSERVER_AVAILABLE,
            "clickhouse": CLICKHOUSE_AVAILABLE
        }
    }


@router.post("/", response_model=Dict[str, Any])
async def create_connection(request: CreateConnectionRequest, db: Session = Depends(get_db)):
    """
    Create a new database connection
    
    Stores connection metadata in the database.
    Note: Connection parameters should be encrypted before storage in production.
    """
    try:
        logger.info(f"Creating {request.type} connection: {request.name}")
        
        # Parse last_tested_at if provided
        last_tested_at = None
        if request.last_tested_at:
            try:
                last_tested_at = datetime.fromisoformat(request.last_tested_at.replace('Z', '+00:00'))
            except Exception as e:
                logger.warning(f"Failed to parse last_tested_at: {e}")
        
        # Create connection record
        connection = Connection(
            name=request.name,
            type=request.type,
            database=request.database,
            connection_params=request.connection_params,  # Store unencrypted for now (backward compatibility)
            created_by=request.created_by,
            status=request.status,
            last_tested_at=last_tested_at,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(connection)
        db.flush()  # Get the connection ID
        
        # Encrypt connection parameters with KMS
        try:
            logger.info(f"Encrypting connection parameters for connection {connection.id}")
            kms_service = get_kms_encryption_service()
            encryption_context = {
                'connection_id': str(connection.id),
                'field': 'connection_params',
                'created_at': datetime.utcnow().isoformat()
            }
            params_json = json.dumps(request.connection_params)
            connection.connection_params_encrypted = kms_service.encrypt(params_json, encryption_context)
            logger.info(f"✓ Connection parameters encrypted successfully")
        except Exception as e:
            logger.error(f"Failed to encrypt connection parameters: {e}")
            # Continue without encryption for backward compatibility
            logger.warning("Connection created without encrypted parameters")
        
        db.commit()
        db.refresh(connection)
        
        logger.info(f"Connection created successfully: {connection.id}")
        
        return {
            "success": True,
            "message": "Connection created successfully",
            "connection": connection.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Failed to create connection: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create connection: {str(e)}"
        )


@router.get("/", response_model=List[ConnectionListResponse])
async def list_connections(db: Session = Depends(get_db)):
    """
    List all database connections
    
    Returns all active connections from the database.
    """
    try:
        logger.info("Fetching all connections")
        
        connections = db.query(Connection).filter(
            Connection.is_active == True
        ).order_by(Connection.created_at.desc()).all()
        
        logger.info(f"Found {len(connections)} connections")
        
        return [
            ConnectionListResponse(
                id=conn.id,
                name=conn.name,
                type=conn.type,
                database=conn.database,
                created_by=conn.created_by,
                status=conn.status,
                last_tested_at=conn.last_tested_at.isoformat() if conn.last_tested_at else None,
                created_at=conn.created_at.isoformat() if conn.created_at else None,
                updated_at=conn.updated_at.isoformat() if conn.updated_at else None
            )
            for conn in connections
        ]
        
    except Exception as e:
        logger.error(f"Failed to fetch connections: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch connections: {str(e)}"
        )


@router.delete("/{connection_id}")
async def delete_connection(connection_id: int, db: Session = Depends(get_db)):
    """
    Delete a database connection
    
    Soft delete by setting is_active to False.
    """
    try:
        logger.info(f"Deleting connection: {connection_id}")
        
        connection = db.query(Connection).filter(
            Connection.id == connection_id
        ).first()
        
        if not connection:
            raise HTTPException(
                status_code=404,
                detail=f"Connection not found: {connection_id}"
            )
        
        # Soft delete
        connection.is_active = False
        connection.updated_at = datetime.utcnow()
        
        db.commit()
        
        logger.info(f"Connection deleted: {connection_id}")
        
        return {"success": True, "message": "Connection deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete connection: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete connection: {str(e)}"
        )


@router.put("/{connection_id}/status")
async def update_connection_status(
    connection_id: int,
    request: UpdateStatusRequest,
    db: Session = Depends(get_db)
):
    """
    Update connection status and last tested timestamp
    """
    try:
        logger.info(f"Updating connection status: {connection_id} -> {request.status}")
        
        connection = db.query(Connection).filter(
            Connection.id == connection_id
        ).first()
        
        if not connection:
            raise HTTPException(
                status_code=404,
                detail=f"Connection not found: {connection_id}"
            )
        
        connection.status = request.status
        connection.last_tested_at = datetime.fromisoformat(request.last_tested_at.replace('Z', '+00:00'))
        connection.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(connection)
        
        logger.info(f"Connection status updated: {connection_id}")
        
        return connection.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update connection status: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update connection status: {str(e)}"
        )


class UpdateConnectionRequest(BaseModel):
    """Request model for updating a connection"""
    name: str = Field(..., description="Connection name")
    type: str = Field(..., description="Connection type (source or target)")
    database: str = Field(..., description="Database type")
    connection_params: Dict[str, Any] = Field(..., description="Connection parameters")
    status: str = Field(default="disconnected", description="Connection status")
    last_tested_at: Optional[str] = Field(default=None, description="Last tested timestamp")


@router.put("/{connection_id}")
async def update_connection(
    connection_id: int,
    request: UpdateConnectionRequest,
    db: Session = Depends(get_db)
):
    """
    Update a database connection
    
    Updates connection metadata including name, type, database, and connection parameters.
    """
    try:
        logger.info(f"Updating connection: {connection_id}")
        
        connection = db.query(Connection).filter(
            Connection.id == connection_id
        ).first()
        
        if not connection:
            raise HTTPException(
                status_code=404,
                detail=f"Connection not found: {connection_id}"
            )
        
        # Parse last_tested_at if provided
        last_tested_at = None
        if request.last_tested_at:
            try:
                last_tested_at = datetime.fromisoformat(request.last_tested_at.replace('Z', '+00:00'))
            except Exception as e:
                logger.warning(f"Failed to parse last_tested_at: {e}")
        
        # Update connection fields
        connection.name = request.name
        connection.type = request.type
        connection.database = request.database
        connection.connection_params = request.connection_params  # Store unencrypted for backward compatibility
        connection.status = request.status
        if last_tested_at:
            connection.last_tested_at = last_tested_at
        connection.updated_at = datetime.utcnow()
        
        # Encrypt connection parameters with KMS
        try:
            logger.info(f"Encrypting connection parameters for connection {connection_id}")
            kms_service = get_kms_encryption_service()
            encryption_context = {
                'connection_id': str(connection_id),
                'field': 'connection_params',
                'updated_at': datetime.utcnow().isoformat()
            }
            params_json = json.dumps(request.connection_params)
            connection.connection_params_encrypted = kms_service.encrypt(params_json, encryption_context)
            logger.info(f"✓ Connection parameters encrypted successfully")
        except Exception as e:
            logger.error(f"Failed to encrypt connection parameters: {e}")
            # Continue without encryption for backward compatibility
            logger.warning("Connection updated without encrypted parameters")
        
        db.commit()
        db.refresh(connection)
        
        logger.info(f"Connection updated successfully: {connection_id}")
        
        return connection.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update connection: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update connection: {str(e)}"
        )

