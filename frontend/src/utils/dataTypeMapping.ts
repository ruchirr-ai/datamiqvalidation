/**
 * SQL Server to Redshift Data Type Mapping
 * 
 * Maps SQL Server data types to their Redshift equivalents
 * and provides compatibility information
 */

export interface DataTypeMapping {
  compatible: boolean;
  redshiftType: string;
  notes?: string;
}

export const sqlServerToRedshiftMapping: Record<string, DataTypeMapping> = {
  // Exact numeric types
  'bigint': { compatible: true, redshiftType: 'BIGINT' },
  'int': { compatible: true, redshiftType: 'INTEGER' },
  'smallint': { compatible: true, redshiftType: 'SMALLINT' },
  'tinyint': { compatible: true, redshiftType: 'SMALLINT', notes: 'Use SMALLINT (no TINYINT in Redshift)' },
  'bit': { compatible: true, redshiftType: 'BOOLEAN' },
  'decimal': { compatible: true, redshiftType: 'DECIMAL' },
  'numeric': { compatible: true, redshiftType: 'NUMERIC' },
  'money': { compatible: true, redshiftType: 'DECIMAL(19,4)', notes: 'Convert to DECIMAL(19,4)' },
  'smallmoney': { compatible: true, redshiftType: 'DECIMAL(10,4)', notes: 'Convert to DECIMAL(10,4)' },
  
  // Approximate numeric types
  'float': { compatible: true, redshiftType: 'DOUBLE PRECISION' },
  'real': { compatible: true, redshiftType: 'REAL' },
  
  // Date and time types
  'date': { compatible: true, redshiftType: 'DATE' },
  'datetime': { compatible: true, redshiftType: 'TIMESTAMP', notes: 'Convert to TIMESTAMP' },
  'datetime2': { compatible: true, redshiftType: 'TIMESTAMP' },
  'smalldatetime': { compatible: true, redshiftType: 'TIMESTAMP', notes: 'Convert to TIMESTAMP' },
  'time': { compatible: true, redshiftType: 'TIME', notes: 'Redshift TIME has limited precision' },
  'datetimeoffset': { compatible: true, redshiftType: 'TIMESTAMPTZ', notes: 'Convert to TIMESTAMPTZ' },
  
  // Character strings
  'char': { compatible: true, redshiftType: 'CHAR' },
  'varchar': { compatible: true, redshiftType: 'VARCHAR' },
  'text': { compatible: true, redshiftType: 'VARCHAR(MAX)', notes: 'Convert to VARCHAR(MAX) or VARCHAR(65535)' },
  'nchar': { compatible: true, redshiftType: 'CHAR', notes: 'Redshift uses UTF-8, no separate NCHAR' },
  'nvarchar': { compatible: true, redshiftType: 'VARCHAR', notes: 'Redshift uses UTF-8, no separate NVARCHAR' },
  'ntext': { compatible: true, redshiftType: 'VARCHAR(MAX)', notes: 'Convert to VARCHAR(MAX)' },
  
  // Binary types
  'binary': { compatible: true, redshiftType: 'VARBYTE', notes: 'Convert to VARBYTE' },
  'varbinary': { compatible: true, redshiftType: 'VARBYTE' },
  'image': { compatible: false, redshiftType: 'VARBYTE', notes: 'Not recommended - use external storage (S3)' },
  
  // Other types
  'uniqueidentifier': { compatible: true, redshiftType: 'CHAR(36)', notes: 'Store as CHAR(36) or VARCHAR(36)' },
  'xml': { compatible: true, redshiftType: 'VARCHAR(MAX)', notes: 'Store as VARCHAR, parse in application' },
  'json': { compatible: true, redshiftType: 'SUPER', notes: 'Use SUPER data type for JSON' },
  
  // Unsupported types
  'geography': { compatible: false, redshiftType: 'VARCHAR', notes: 'Store as WKT/WKB in VARCHAR or use GEOMETRY' },
  'geometry': { compatible: true, redshiftType: 'GEOMETRY', notes: 'Redshift supports GEOMETRY type' },
  'hierarchyid': { compatible: false, redshiftType: 'VARCHAR', notes: 'Store as VARCHAR, handle hierarchy in application' },
  'sql_variant': { compatible: false, redshiftType: 'VARCHAR', notes: 'Not supported - redesign schema' },
  'timestamp': { compatible: false, redshiftType: 'BIGINT', notes: 'SQL Server rowversion - use BIGINT or remove' },
  'rowversion': { compatible: false, redshiftType: 'BIGINT', notes: 'Use BIGINT or application-level versioning' },
};

/**
 * Get Redshift compatibility info for a SQL Server data type
 */
export function getRedshiftCompatibility(sqlServerType: string): DataTypeMapping {
  // Normalize the type (remove size, precision, etc.)
  const baseType = sqlServerType.toLowerCase().split('(')[0].trim();
  
  // Check if we have a mapping
  if (sqlServerToRedshiftMapping[baseType]) {
    return sqlServerToRedshiftMapping[baseType];
  }
  
  // Default for unknown types
  return {
    compatible: false,
    redshiftType: 'VARCHAR',
    notes: 'Unknown type - review manually'
  };
}

/**
 * Check if this is a SQL Server assessment (vs BigQuery)
 */
export function isSQLServerAssessment(report: any): boolean {
  if (!report) return false;
  // SQL Server assessments have no ML models and routines have routine_metadata
  const hasMLModels = report.ml_models && report.ml_models.length > 0;
  const hasRoutineMetadata = report.routines && report.routines.length > 0 && 
                             report.routines.some((r: any) => r.routine_metadata);
  return !hasMLModels && hasRoutineMetadata;
}


/**
 * Get recommended Redshift auto compression encoding for a data type
 */
export function getRedshiftCompression(dataType: string): string {
  const baseType = (dataType || '').toLowerCase().split('(')[0].trim();
  
  switch (baseType) {
    // Integer types → AZ64
    case 'bigint': case 'int': case 'integer': case 'smallint': case 'tinyint':
    case 'int64': case 'int32':
      return 'AZ64';
    
    // Decimal/numeric → AZ64
    case 'decimal': case 'numeric': case 'money': case 'smallmoney':
    case 'bignumeric':
      return 'AZ64';
    
    // Date/time → AZ64
    case 'date': case 'datetime': case 'datetime2': case 'smalldatetime':
    case 'timestamp': case 'datetimeoffset': case 'timestamptz':
      return 'AZ64';
    
    // Float/real → RAW (compression doesn't help much)
    case 'float': case 'real': case 'double': case 'float64':
      return 'RAW';
    
    // Boolean → RAW
    case 'boolean': case 'bool': case 'bit':
      return 'RAW';
    
    // String types → LZO
    case 'varchar': case 'nvarchar': case 'char': case 'nchar':
    case 'text': case 'ntext': case 'string':
    case 'uniqueidentifier': case 'xml':
      return 'LZO';
    
    // Binary → LZO
    case 'binary': case 'varbinary': case 'image': case 'bytes':
      return 'LZO';
    
    // JSON/SUPER → ZSTD
    case 'json': case 'super':
      return 'ZSTD';
    
    // Complex types → ZSTD
    case 'array': case 'struct': case 'record':
      return 'ZSTD';
    
    // Geometry → RAW
    case 'geometry': case 'geography':
      return 'RAW';
    
    // Time → LZO (stored as VARCHAR in Redshift)
    case 'time':
      return 'LZO';
    
    default:
      return 'LZO';
  }
}
