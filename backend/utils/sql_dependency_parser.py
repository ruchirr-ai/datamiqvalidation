"""
SQL Dependency Parser for BigQuery SQL
Extracts table, view, and function dependencies from SQL queries
"""

import re
from typing import List, Dict, Set, Tuple


class SQLDependencyParser:
    """Parse SQL queries to extract dependencies"""
    
    def __init__(self):
        # Improved patterns for different SQL object types
        # These patterns capture the full table reference including dataset.table
        self.table_patterns = [
            # FROM/JOIN/INTO with optional backticks and full qualified names
            r'(?:FROM|JOIN|INTO)\s+`?([a-zA-Z0-9_-]+(?:\.[a-zA-Z0-9_-]+)+)`?',  # Multi-part names (dataset.table)
            r'(?:FROM|JOIN|INTO)\s+`?([a-zA-Z0-9_-]+)`?(?:\s+(?:AS\s+)?[a-zA-Z0-9_]+)?',  # Single names with optional alias
        ]
        
        self.function_patterns = [
            # Function calls
            r'([a-zA-Z0-9_]+)\s*\(',
        ]
        
        # BigQuery system functions to exclude
        self.system_functions = {
            # Aggregate functions
            'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'ANY_VALUE', 'ARRAY_AGG',
            'ARRAY_CONCAT_AGG', 'STRING_AGG', 'APPROX_COUNT_DISTINCT', 'APPROX_QUANTILES',
            'COUNTIF', 'LOGICAL_AND', 'LOGICAL_OR', 'BIT_AND', 'BIT_OR', 'BIT_XOR',
            # String functions
            'CONCAT', 'SUBSTR', 'SUBSTRING', 'LENGTH', 'UPPER', 'LOWER', 'TRIM',
            'LTRIM', 'RTRIM', 'LPAD', 'RPAD', 'REPLACE', 'REGEXP_EXTRACT',
            'REGEXP_REPLACE', 'REGEXP_CONTAINS', 'SPLIT', 'STRPOS', 'STARTS_WITH',
            'ENDS_WITH', 'FORMAT', 'REPEAT', 'REVERSE', 'CHAR_LENGTH', 'BYTE_LENGTH',
            'LEFT', 'RIGHT', 'INITCAP', 'NORMALIZE', 'TO_CODE_POINTS', 'CODE_POINTS_TO_STRING',
            # Casting and conversion
            'CAST', 'SAFE_CAST', 'COALESCE', 'IFNULL', 'NULLIF', 'IF', 'IIF',
            'PARSE_DATE', 'PARSE_TIMESTAMP', 'PARSE_DATETIME', 'PARSE_TIME',
            'PARSE_NUMERIC', 'PARSE_BIGNUMERIC', 'PARSE_JSON',
            # Date/time functions
            'DATE', 'TIMESTAMP', 'DATETIME', 'TIME', 'EXTRACT', 'DATE_ADD', 'DATE_SUB',
            'DATE_DIFF', 'DATE_TRUNC', 'DATETIME_ADD', 'DATETIME_SUB', 'DATETIME_DIFF',
            'DATETIME_TRUNC', 'TIMESTAMP_ADD', 'TIMESTAMP_SUB', 'TIMESTAMP_DIFF',
            'TIMESTAMP_TRUNC', 'TIME_ADD', 'TIME_SUB', 'TIME_DIFF', 'TIME_TRUNC',
            'FORMAT_DATE', 'FORMAT_TIMESTAMP', 'FORMAT_DATETIME', 'FORMAT_TIME',
            'CURRENT_DATE', 'CURRENT_TIMESTAMP', 'CURRENT_TIME', 'CURRENT_DATETIME',
            'UNIX_DATE', 'UNIX_SECONDS', 'UNIX_MILLIS', 'UNIX_MICROS',
            'TIMESTAMP_SECONDS', 'TIMESTAMP_MILLIS', 'TIMESTAMP_MICROS',
            'LAST_DAY', 'GENERATE_DATE_ARRAY', 'GENERATE_TIMESTAMP_ARRAY',
            # Array functions
            'ARRAY', 'ARRAY_LENGTH', 'ARRAY_CONCAT', 'ARRAY_TO_STRING',
            'ARRAY_REVERSE', 'GENERATE_ARRAY', 'UNNEST', 'OFFSET', 'ORDINAL',
            'SAFE_OFFSET', 'SAFE_ORDINAL',
            # Struct and JSON
            'STRUCT', 'JSON_EXTRACT', 'JSON_EXTRACT_SCALAR', 'JSON_EXTRACT_ARRAY',
            'JSON_VALUE', 'JSON_QUERY', 'JSON_QUERY_ARRAY', 'TO_JSON_STRING', 'TO_JSON',
            # Math functions
            'ROUND', 'CEIL', 'CEILING', 'FLOOR', 'ABS', 'SIGN', 'MOD', 'DIV',
            'POWER', 'POW', 'SQRT', 'LOG', 'LOG10', 'LN', 'EXP', 'GREATEST', 'LEAST',
            'SAFE_DIVIDE', 'SAFE_SUBTRACT', 'SAFE_ADD', 'SAFE_MULTIPLY', 'SAFE_NEGATE',
            'IEEE_DIVIDE', 'RAND', 'TRUNC',
            # Window functions
            'ROW_NUMBER', 'RANK', 'DENSE_RANK', 'NTILE', 'LAG', 'LEAD',
            'FIRST_VALUE', 'LAST_VALUE', 'NTH_VALUE', 'PERCENT_RANK', 'CUME_DIST',
            'PERCENTILE_CONT', 'PERCENTILE_DISC',
            # SQL keywords that match function pattern (word followed by parenthesis)
            'OVER', 'PARTITION', 'AS', 'WITH', 'WITHIN', 'RESPECT', 'IGNORE',
            'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'AND', 'OR', 'NOT', 'IN',
            'EXISTS', 'BETWEEN', 'LIKE', 'IS', 'HAVING', 'WHERE', 'FROM',
            'GROUP', 'ORDER', 'BY', 'LIMIT', 'UNION', 'INTERSECT', 'EXCEPT',
            'VALUES', 'INSERT', 'UPDATE', 'DELETE', 'SELECT', 'CREATE', 'DROP',
            'ALTER', 'TRUNCATE', 'MERGE', 'DECLARE', 'SET', 'BEGIN', 'CALL',
            'RETURNS', 'LANGUAGE', 'OPTIONS', 'USING', 'ON', 'INTO', 'TABLE',
            # Conditional / type functions
            'TYPEOF', 'HASH', 'FARM_FINGERPRINT', 'MD5', 'SHA1', 'SHA256', 'SHA512',
            'TO_HEX', 'FROM_HEX', 'TO_BASE64', 'FROM_BASE64',
            # Geography
            'ST_GEOGPOINT', 'ST_MAKELINE', 'ST_MAKEPOLYGON', 'ST_DISTANCE',
            'ST_AREA', 'ST_LENGTH', 'ST_INTERSECTS', 'ST_CONTAINS', 'ST_WITHIN',
            'ST_ASTEXT', 'ST_GEOGFROMTEXT', 'ST_ASGEOJSON', 'ST_GEOGFROMGEOJSON',
            # Net functions
            'NET', 'ERROR', 'RAISE',
        }
    
    def parse_dependencies(self, sql: str) -> Dict[str, List[str]]:
        """
        Parse SQL and extract all dependencies
        
        Returns:
            Dict with keys: 'tables', 'views', 'functions'
        """
        if not sql:
            return {'tables': [], 'views': [], 'functions': []}
        
        # Normalize SQL
        sql_upper = sql.upper()
        
        # Extract tables/views
        tables = self._extract_tables(sql)
        
        # Extract functions
        functions = self._extract_functions(sql)
        
        # For now, we can't distinguish between tables and views without metadata
        # So we return them all as tables, and the caller can cross-reference
        return {
            'tables': sorted(list(tables)),
            'views': [],  # Will be populated by cross-referencing with known views
            'functions': sorted(list(functions))
        }
    
    def _extract_tables(self, sql: str) -> Set[str]:
        """Extract table/view references from SQL"""
        tables = set()
        
        # Remove comments
        sql = self._remove_comments(sql)
        
        # Remove string literals to avoid false matches
        sql = re.sub(r"'[^']*'", "''", sql)
        sql = re.sub(r'"[^"]*"', '""', sql)
        
        # Pattern to match table references after FROM, JOIN (all types), INTO keywords
        # Handles multiple formats:
        # 1. `dataset`.`table` or dataset.table (backticks around each part or none)
        # 2. `dataset.table` (backticks around full name)
        # 3. project.dataset.table (three-part names)
        table_pattern = r'(?:FROM|INTO|(?:(?:LEFT|RIGHT|INNER|OUTER|CROSS|FULL)\s+)?JOIN)\s+`?([a-zA-Z0-9_-]+)`?(?:\.`?([a-zA-Z0-9_-]+)`?(?:\.`?([a-zA-Z0-9_-]+)`?)?)?'
        
        matches = re.finditer(table_pattern, sql, re.IGNORECASE)
        for match in matches:
            # Build the full table name from captured groups
            parts = [g for g in match.groups() if g]
            
            if parts:
                table_ref = '.'.join(parts)
                
                # Remove any remaining backticks
                table_ref = table_ref.replace('`', '').strip()
                
                # Skip if empty or contains SQL keywords
                if table_ref and not re.match(r'^(SELECT|WHERE|GROUP|ORDER|HAVING|LIMIT|CASE|WHEN|ON)', table_ref, re.IGNORECASE):
                    tables.add(table_ref)
        
        # Also look for WITH clause (CTEs) and exclude them
        cte_pattern = r'WITH\s+([a-zA-Z0-9_]+)\s+AS'
        ctes = set(re.findall(cte_pattern, sql, re.IGNORECASE))
        
        # Remove CTEs from tables list
        tables = tables - ctes
        
        return tables
    
    def _extract_functions(self, sql: str) -> Set[str]:
        """Extract user-defined function references from SQL"""
        functions = set()
        
        # Remove comments
        sql = self._remove_comments(sql)
        
        # Remove string literals
        sql = re.sub(r"'[^']*'", "''", sql)
        sql = re.sub(r'"[^"]*"', '""', sql)
        
        for pattern in self.function_patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            for match in matches:
                func_name = match.upper()
                # Exclude system functions
                if func_name not in self.system_functions:
                    functions.add(match)
        
        return functions
    
    def _remove_comments(self, sql: str) -> str:
        """Remove SQL comments"""
        # Remove single-line comments
        sql = re.sub(r'--[^\n]*', '', sql)
        # Remove multi-line comments
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
        return sql
    
    def analyze_nested_dependencies(
        self, 
        object_name: str, 
        object_sql: str, 
        all_objects: Dict[str, str],
        visited: Set[str] = None,
        level: int = 0
    ) -> List[Dict]:
        """
        Recursively analyze dependencies with nesting levels
        
        Args:
            object_name: Name of the current object
            object_sql: SQL definition of the current object
            all_objects: Dict of all available objects {name: sql}
            visited: Set of already visited objects (to prevent cycles)
            level: Current nesting level
            
        Returns:
            List of dependency dicts with structure:
            {
                'name': str,
                'type': str,  # 'table', 'view', 'function'
                'level': int,
                'dependencies': List[Dict]  # Nested dependencies
            }
        """
        if visited is None:
            visited = set()
        
        if object_name in visited or level > 10:  # Prevent infinite recursion
            return []
        
        visited.add(object_name)
        
        # Parse direct dependencies
        deps = self.parse_dependencies(object_sql)
        
        result = []
        
        # Process table/view dependencies
        for dep_name in deps['tables']:
            dep_info = {
                'name': dep_name,
                'type': 'view' if dep_name in all_objects else 'table',
                'level': level + 1,
                'dependencies': []
            }
            
            # If it's a view, recursively analyze its dependencies
            if dep_name in all_objects:
                dep_info['dependencies'] = self.analyze_nested_dependencies(
                    dep_name,
                    all_objects[dep_name],
                    all_objects,
                    visited.copy(),
                    level + 1
                )
            
            result.append(dep_info)
        
        # Process function dependencies
        for func_name in deps['functions']:
            func_info = {
                'name': func_name,
                'type': 'function',
                'level': level + 1,
                'dependencies': []
            }
            
            # If it's a stored procedure/function, recursively analyze
            if func_name in all_objects:
                func_info['dependencies'] = self.analyze_nested_dependencies(
                    func_name,
                    all_objects[func_name],
                    all_objects,
                    visited.copy(),
                    level + 1
                )
            
            result.append(func_info)
        
        return result


# Singleton instance
sql_parser = SQLDependencyParser()
