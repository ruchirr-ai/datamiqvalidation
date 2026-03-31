import React from 'react';
import { Database } from 'lucide-react';
import { SiMongodb, SiAmazondocumentdb, SiPostgresql, SiMysql, SiOracle, SiGooglecloud, SiAmazonredshift, SiSap } from 'react-icons/si';
import { DatabaseType, DatabaseTypeInfo } from '../../types/fieldConfig';
import { DATABASE_TYPES } from '../../constants/defaultFieldConfigs';
import './DatabaseTypeList.css';

interface DatabaseTypeListProps {
  selectedType: DatabaseType;
  onSelect: (type: DatabaseType) => void;
}

export const DatabaseTypeList: React.FC<DatabaseTypeListProps> = ({
  selectedType,
  onSelect,
}) => {
  const handleKeyDown = (e: React.KeyboardEvent, type: DatabaseType) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onSelect(type);
    }
  };

  // Map database types to specific icons matching CreateConnectionModal
  const getDatabaseIcon = (dbType: DatabaseType) => {
    const iconSize = 20;
    
    switch (dbType) {
      case 'mongodb':
        return <SiMongodb size={iconSize} />;
      case 'documentdb':
        return <SiAmazondocumentdb size={iconSize} />;
      case 'postgresql':
        return <SiPostgresql size={iconSize} />;
      case 'mysql':
        return <SiMysql size={iconSize} />;
      case 'oracle':
        return <SiOracle size={iconSize} />;
      case 'sqlserver':
        return <Database size={iconSize} strokeWidth={1.5} />;
      case 'bigquery':
        return <SiGooglecloud size={iconSize} />;
      case 'redshift':
        return <SiAmazonredshift size={iconSize} />;
      case 'sybase':
        return <SiSap size={iconSize} />;
      case 'db2':
        return <Database size={iconSize} strokeWidth={1.5} />;
      default:
        return <Database size={iconSize} strokeWidth={1.5} />;
    }
  };

  return (
    <div className="database-type-sidebar">
      <div className="database-type-list">
        {DATABASE_TYPES.map((dbType: DatabaseTypeInfo) => (
          <button
            key={dbType.id}
            className={`database-type-list-item ${selectedType === dbType.id ? 'active' : ''}`}
            onClick={() => onSelect(dbType.id)}
            onKeyDown={(e) => handleKeyDown(e, dbType.id)}
            role="button"
            tabIndex={0}
            aria-label={`Select ${dbType.name}`}
            aria-pressed={selectedType === dbType.id}
          >
            <span className="database-type-list-icon">
              {getDatabaseIcon(dbType.id)}
            </span>
            <span className="database-type-list-name">{dbType.name}</span>
          </button>
        ))}
      </div>
    </div>
  );
};
