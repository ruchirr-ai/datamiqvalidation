/**
 * SQL Server Routines Section
 * 
 * Simplified table view for SQL Server stored procedures, functions, and triggers
 * Shows: NAME, TYPE, LANGUAGE, CREATED TIME (left-aligned)
 * Expandable rows show execution stats and dependencies
 */

import React, { useState } from 'react';
import { Code, Database, Eye, TableIcon } from 'lucide-react';
import { Badge } from '../ui';

interface SQLServerRoutinesSectionProps {
  routines: any[];
  title: string;
  formatDate: (date: string | null) => string;
}

export const SQLServerRoutinesSection: React.FC<SQLServerRoutinesSectionProps> = ({ 
  routines, 
  title, 
  formatDate 
}) => {
  const [expandedRoutine, setExpandedRoutine] = useState<number | null>(null);

  const handleRoutineClick = (index: number) => {
    setExpandedRoutine(expandedRoutine === index ? null : index);
  };

  return (
    <div className="section-content">
      <h2 className="section-heading">{title} ({routines.length})</h2>
      {routines.length === 0 ? (
        <div className="empty-state">
          <Code size={48} />
          <p>No {title.toLowerCase()} found</p>
        </div>
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ textAlign: 'left' }}>NAME</th>
                <th style={{ textAlign: 'left' }}>TYPE</th>
                <th style={{ textAlign: 'left' }}>LANGUAGE</th>
                <th style={{ textAlign: 'left' }}>CREATED TIME</th>
              </tr>
            </thead>
            <tbody>
              {routines.map((routine: any, index: number) => {
                const isExpanded = expandedRoutine === index;
                const totalDeps = (routine.dependent_tables?.length || 0) + 
                                 (routine.dependent_views?.length || 0) + 
                                 (routine.dependent_functions?.length || 0) +
                                 (routine.calls_procedures?.length || 0);
                
                // Get execution stats from routine_metadata
                const metadata = routine.routine_metadata || {};
                const totalExecutions = metadata.total_executions || routine.call_frequency || 0;
                const executionsToday = metadata.executions_today || 0;
                const executions7Days = metadata.executions_last_7_days || 0;
                const executions30Days = metadata.executions_last_30_days || 0;
                const avgDurationMs = metadata.avg_duration_ms || 0;
                const lastExecutionTime = metadata.last_execution_time;
                
                return (
                  <React.Fragment key={index}>
                    <tr>
                      <td style={{ textAlign: 'left' }}>
                        <button
                          className="table-name-link"
                          onClick={() => handleRoutineClick(index)}
                          title="Click to view details"
                          style={{ textAlign: 'left' }}
                        >
                          {routine.routine_name}
                        </button>
                      </td>
                      <td style={{ textAlign: 'left' }}>
                        <Badge variant="default">{routine.routine_type}</Badge>
                      </td>
                      <td style={{ textAlign: 'left' }}>
                        <Badge variant="info">{routine.external_language || 'SQL'}</Badge>
                      </td>
                      <td style={{ textAlign: 'left' }} className="timestamp-value">
                        {formatDate(routine.creation_time)}
                      </td>
                    </tr>
                    
                    {isExpanded && (
                      <tr className="expanded-row">
                        <td colSpan={4}>
                          <div className="dependency-details">
                            {/* Execution Statistics Section - Always show FIRST */}
                            <div className="dependency-section">
                              <h4 className="dependency-section-title">
                                <Code size={16} />
                                Execution Statistics
                              </h4>
                              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
                                <div>
                                  <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '4px', textAlign: 'left' }}>
                                    Total Executions
                                  </div>
                                  <div style={{ fontSize: '20px', fontWeight: 600, color: 'var(--color-text-primary)', textAlign: 'left' }}>
                                    {totalExecutions > 0 ? totalExecutions.toLocaleString() : '-'}
                                  </div>
                                </div>
                                <div>
                                  <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '4px', textAlign: 'left' }}>
                                    Today
                                  </div>
                                  <div style={{ fontSize: '20px', fontWeight: 600, color: 'var(--color-text-primary)', textAlign: 'left' }}>
                                    {executionsToday > 0 ? executionsToday.toLocaleString() : '-'}
                                  </div>
                                </div>
                                <div>
                                  <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '4px', textAlign: 'left' }}>
                                    Last 7 Days
                                  </div>
                                  <div style={{ fontSize: '20px', fontWeight: 600, color: 'var(--color-text-primary)', textAlign: 'left' }}>
                                    {executions7Days > 0 ? executions7Days.toLocaleString() : '-'}
                                  </div>
                                </div>
                                <div>
                                  <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '4px', textAlign: 'left' }}>
                                    Last 30 Days
                                  </div>
                                  <div style={{ fontSize: '20px', fontWeight: 600, color: 'var(--color-text-primary)', textAlign: 'left' }}>
                                    {executions30Days > 0 ? executions30Days.toLocaleString() : '-'}
                                  </div>
                                </div>
                                <div>
                                  <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '4px', textAlign: 'left' }}>
                                    Avg Duration (ms)
                                  </div>
                                  <div style={{ fontSize: '20px', fontWeight: 600, color: 'var(--color-text-primary)', textAlign: 'left' }}>
                                    {avgDurationMs > 0 ? avgDurationMs.toFixed(2) : '-'}
                                  </div>
                                </div>
                                <div>
                                  <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '4px', textAlign: 'left' }}>
                                    Last Executed
                                  </div>
                                  <div style={{ fontSize: '14px', fontWeight: 500, color: 'var(--color-text-secondary)', textAlign: 'left' }}>
                                    {lastExecutionTime ? formatDate(lastExecutionTime) : 'Never'}
                                  </div>
                                </div>
                              </div>
                            </div>
                            
                            {/* Dependencies Section */}
                            {totalDeps > 0 && (
                              <div className="dependency-section">
                                <h4 className="dependency-section-title">
                                  <Database size={16} />
                                  Dependencies ({totalDeps})
                                </h4>
                                
                                {routine.dependent_tables && routine.dependent_tables.length > 0 && (
                                  <div className="dependency-group">
                                    <h5 className="dependency-group-title">
                                      <TableIcon size={14} />
                                      Tables ({routine.dependent_tables.length})
                                    </h5>
                                    <div className="dependency-list">
                                      {routine.dependent_tables.map((table: string, idx: number) => (
                                        <Badge key={idx} variant="default" className="dependency-badge">
                                          {table}
                                        </Badge>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                
                                {routine.dependent_views && routine.dependent_views.length > 0 && (
                                  <div className="dependency-group">
                                    <h5 className="dependency-group-title">
                                      <Eye size={14} />
                                      Views ({routine.dependent_views.length})
                                    </h5>
                                    <div className="dependency-list">
                                      {routine.dependent_views.map((v: string, idx: number) => (
                                        <Badge key={idx} variant="info" className="dependency-badge">
                                          {v}
                                        </Badge>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                
                                {routine.dependent_functions && routine.dependent_functions.length > 0 && (
                                  <div className="dependency-group">
                                    <h5 className="dependency-group-title">
                                      <Code size={14} />
                                      Functions ({routine.dependent_functions.length})
                                    </h5>
                                    <div className="dependency-list">
                                      {routine.dependent_functions.map((func: string, idx: number) => (
                                        <Badge key={idx} variant="warning" className="dependency-badge">
                                          {func}
                                        </Badge>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                
                                {routine.calls_procedures && routine.calls_procedures.length > 0 && (
                                  <div className="dependency-group">
                                    <h5 className="dependency-group-title">
                                      <Code size={14} />
                                      Calls Procedures ({routine.calls_procedures.length})
                                    </h5>
                                    <div className="dependency-list">
                                      {routine.calls_procedures.map((proc: string, idx: number) => (
                                        <Badge key={idx} variant="success" className="dependency-badge">
                                          {proc}
                                        </Badge>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            )}
                            
                            {/* SQL Definition */}
                            {routine.definition && (
                              <div className="dependency-section">
                                <h4 className="dependency-section-title">
                                  <Code size={16} />
                                  Definition
                                </h4>
                                <pre className="sql-code"><code>{routine.definition}</code></pre>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
