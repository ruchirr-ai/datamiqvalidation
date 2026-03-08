"""
SQLGlot Parser Service

Provides SQL parsing and transpilation using SQLGlot library.
Supports fast, deterministic conversions for supported dialect pairs.
"""

import logging
from typing import Optional, Dict, Any
import sqlglot
from sqlglot import parse_one, transpile
from sqlglot.errors import ParseError, TokenError

logger = logging.getLogger(__name__)


class TranspileResult:
    """Result of SQL transpilation operation"""
    
    def __init__(
        self,
        success: bool,
        transpiled_code: Optional[str] = None,
        error_message: Optional[str] = None,
        error_line: Optional[int] = None,
        error_position: Optional[int] = None
    ):
        self.success = success
        self.transpiled_code = transpiled_code
        self.error_message = error_message
        self.error_line = error_line
        self.error_position = error_position
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary"""
        return {
            'success': self.success,
            'transpiled_code': self.transpiled_code,
            'error_message': self.error_message,
            'error_line': self.error_line,
            'error_position': self.error_position
        }


class SQLGlotParseError(Exception):
    """Exception raised for SQLGlot parsing errors"""
    pass


class SQLGlotDialectError(Exception):
    """Exception raised for unsupported dialect errors"""
    pass


class SQLGlotParser:
    """
    SQL parser and transpiler using SQLGlot library.
    Provides fast, deterministic conversions for supported dialect pairs.
    """
    
    SUPPORTED_DIALECTS = [
        'bigquery',
        'redshift',
        'postgres',
        'mysql',
        'snowflake',
        'oracle',
        'mssql'
    ]
    
    def __init__(self):
        """Initialize SQLGlot parser"""
        self.logger = logger
    
    def validate_dialects(
        self,
        source_dialect: str,
        target_dialect: str
    ) -> bool:
        """
        Validate dialect pair is supported.
        
        Args:
            source_dialect: Source database dialect
            target_dialect: Target database dialect
            
        Returns:
            True if both dialects supported
            
        Raises:
            SQLGlotDialectError: If dialect not supported
        """
        source_lower = source_dialect.lower()
        target_lower = target_dialect.lower()
        
        if source_lower not in self.SUPPORTED_DIALECTS:
            raise SQLGlotDialectError(
                f"Source dialect '{source_dialect}' not supported. "
                f"Supported dialects: {', '.join(self.SUPPORTED_DIALECTS)}"
            )
        
        if target_lower not in self.SUPPORTED_DIALECTS:
            raise SQLGlotDialectError(
                f"Target dialect '{target_dialect}' not supported. "
                f"Supported dialects: {', '.join(self.SUPPORTED_DIALECTS)}"
            )
        
        if source_lower == target_lower:
            raise SQLGlotDialectError(
                "Source and target dialects must be different"
            )
        
        return True
    
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
        try:
            # Validate dialects
            self.validate_dialects(source_dialect, target_dialect)
            
            # Normalize dialect names
            source_lower = source_dialect.lower()
            target_lower = target_dialect.lower()
            
            self.logger.info(
                f"Transpiling SQL from {source_lower} to {target_lower}"
            )
            
            # Transpile SQL
            transpiled = transpile(
                source_code,
                read=source_lower,
                write=target_lower,
                pretty=pretty
            )
            
            # SQLGlot returns a list of transpiled statements
            if not transpiled:
                return TranspileResult(
                    success=False,
                    error_message="Transpilation produced no output"
                )
            
            # Join multiple statements with semicolons
            transpiled_code = ';\n'.join(transpiled)
            
            self.logger.info(
                f"Successfully transpiled SQL ({len(source_code)} -> "
                f"{len(transpiled_code)} chars)"
            )
            
            return TranspileResult(
                success=True,
                transpiled_code=transpiled_code
            )
            
        except (ParseError, TokenError) as e:
            # Extract error details
            error_msg = str(e)
            error_line = None
            error_position = None
            
            # Try to extract line and position from error message
            if hasattr(e, 'errors') and e.errors:
                first_error = e.errors[0]
                if hasattr(first_error, 'line'):
                    error_line = first_error.line
                if hasattr(first_error, 'col'):
                    error_position = first_error.col
            
            self.logger.warning(
                f"SQLGlot parsing failed: {error_msg}",
                extra={
                    'source_dialect': source_dialect,
                    'target_dialect': target_dialect,
                    'error_line': error_line,
                    'error_position': error_position
                }
            )
            
            return TranspileResult(
                success=False,
                error_message=error_msg,
                error_line=error_line,
                error_position=error_position
            )
            
        except SQLGlotDialectError as e:
            self.logger.error(f"Dialect error: {str(e)}")
            return TranspileResult(
                success=False,
                error_message=str(e)
            )
            
        except Exception as e:
            self.logger.error(
                f"Unexpected error during transpilation: {str(e)}",
                exc_info=True
            )
            return TranspileResult(
                success=False,
                error_message=f"Unexpected error: {str(e)}"
            )
    
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
        try:
            # Validate dialect
            dialect_lower = dialect.lower()
            if dialect_lower not in self.SUPPORTED_DIALECTS:
                self.logger.warning(
                    f"Dialect '{dialect}' not supported for formatting, "
                    "returning original code"
                )
                return sql_code
            
            # Parse and pretty-print
            parsed = parse_one(sql_code, read=dialect_lower)
            formatted = parsed.sql(dialect=dialect_lower, pretty=True)
            
            # Adjust indentation if needed
            if indent_width != 2:
                lines = formatted.split('\n')
                adjusted_lines = []
                for line in lines:
                    # Count leading spaces
                    leading_spaces = len(line) - len(line.lstrip())
                    if leading_spaces > 0:
                        # Adjust indentation
                        indent_level = leading_spaces // 2
                        new_indent = ' ' * (indent_level * indent_width)
                        adjusted_lines.append(new_indent + line.lstrip())
                    else:
                        adjusted_lines.append(line)
                formatted = '\n'.join(adjusted_lines)
            
            return formatted
            
        except Exception as e:
            self.logger.warning(
                f"Failed to format SQL: {str(e)}, returning original code"
            )
            return sql_code
    
    def parse_sql(
        self,
        sql_code: str,
        dialect: str
    ) -> Optional[Any]:
        """
        Parse SQL and return AST.
        
        Args:
            sql_code: SQL code to parse
            dialect: SQL dialect
            
        Returns:
            Parsed AST or None if parsing fails
        """
        try:
            dialect_lower = dialect.lower()
            if dialect_lower not in self.SUPPORTED_DIALECTS:
                raise SQLGlotDialectError(
                    f"Dialect '{dialect}' not supported"
                )
            
            parsed = parse_one(sql_code, read=dialect_lower)
            return parsed
            
        except Exception as e:
            self.logger.error(f"Failed to parse SQL: {str(e)}")
            return None
