/**
 * SQL Server Routines Section
 * 
 * Simplified table view for SQL Server stored procedures, functions, and triggers
 * Shows: NAME, TYPE, LANGUAGE, CREATED TIME (left-aligned)
 * Expandable rows show tabs: Definition, Dependencies, Execution Statistics
 */

import React, { useState } from 'react';
import { Code, Database, Eye, TableIcon, BarChart3 } from 'lucide-react';
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
  const [activeDetailTab, setActiveDetailTab] = useState<'definition' | 'dependencies' | 'execution'>('definition');

  const handleRoutineClick = (index: number) => {
    if (expandedRoutine === index) {
      setExpandedRoutine(null);
    } else {
      setExpandedRoutine(index);
      setActiveDetailTab('definition');
    }
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
                
                const metadata = routine.routine_metadata || {};
                const totalExecutions = metadata.total_executions || routine.call_frequency || 0;
                const executionsToday = metadata.executions_today || 0;
                const executions7Days = metadata.executions_last_7_days || 0;
                const executions30Days = metadata.executions_last_30_days || 0;
                const avgDurationMs = metadata.avg_duration_ms || 0;
                const lastExecutionTime = metadata.last_execution_time;
                
                return (
                  <React.Fragment key={index}>
                    <tr style={{ cursor: 'pointer' }} onClick={() => handleRoutineClick(index)}>
                      <td style={{ textAlign: 'left' }}>
                        <span className="table-name-link" style={{ textAlign: 'left' }}>
                          {routine.routine_name}
                        </span>
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
                          {/* Detail Tabs */}
                          <div style={{ display: 'flex', gap: '8px', padding: '12px 0', borderBottom: '1px solid var(--color-divider)' }}>
                            <button
                              onClick={() => setActiveDetailTab('definition')}
                              style={{
                                display: 'flex', alignItems: 'center', gap: '6px',
                                padding: '6px 14px', border: 'none', background: 'none', cursor: 'pointer',
                                fontSize: '13px', fontWeight: 500,
                                color: activeDetailTab === 'definition' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
                                borderBottom: activeDetailTab === 'definition' ? '2px solid var(--color-primary)' : '2px solid transparent'
                              }}
                            >
                              <Code size={14} /> Definition
                            </button>
                            <button
                              onClick={() => setActiveDetailTab('dependencies')}
                              style={{
                                display: 'flex', alignItems: 'center', gap: '6px',
                                padding: '6px 14px', border: 'none', background: 'none', cursor: 'pointer',
                                fontSize: '13px', fontWeight: 500,
                                color: activeDetailTab === 'dependencies' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
                                borderBottom: activeDetailTab === 'dependencies' ? '2px solid var(--color-primary)' : '2px solid transparent'
                              }}
                            >
                              <Database size={14} /> Dependencies ({totalDeps})
                            </button>
                            <button
                              onClick={() => setActiveDetailTab('execution')}
                              style={{
                                display: 'flex', alignItems: 'center', gap: '6px',
                                padding: '6px 14px', border: 'none', background: 'none', cursor: 'pointer',
                                fontSize: '13px', fontWeight: 500,
                                color: activeDetailTab === 'execution' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
                                borderBottom: activeDetailTab === 'execution' ? '2px solid var(--color-primary)' : '2px solid transparent'
                              }}
                            >
                              <BarChart3 size={14} /> Execution Statistics
                            </button>
                          </div>

                          <div style={{ padding: '16px 0' }}>
                            {/* Definition Tab */}
                            {activeDetailTab === 'definition' && routine.definition && (
                              <pre className="sql-code"><code>{routine.definition}</code></pre>
                            )}
                            {activeDetailTab === 'definition' && !routine.definition && (
                              <p className="text-muted">No definition available</p>
                            )}

                            {/* Dependencies Tab */}
                            {activeDetailTab === 'dependencies' && (
                              <div>
                                {totalDeps === 0 ? (
                                  <p className="text-muted">No dependencies found</p>
                                ) : (
                                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                    {routine.dependent_tables?.length > 0 && (
                                      <div>
                                        <h5 style={{ fontSize: '13px', fontWeight: 500, marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                          <TableIcon size={14} /> Tables ({routine.dependent_tables.length})
                                        </h5>
                                        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                                          {routine.dependent_tables.map((table: string, idx: number) => (
                                            <Badge key={idx} variant="default">{table}</Badge>
                                          ))}
                                        </div>
                                      </div>
                                    )}
                                    {routine.dependent_views?.length > 0 && (
                                      <div>
                                        <h5 style={{ fontSize: '13px', fontWeight: 500, marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                          <Eye size={14} /> Views ({routine.dependent_views.length})
                                        </h5>
                                        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                                          {routine.dependent_views.map((v: string, idx: number) => (
                                            <Badge key={idx} variant="info">{v}</Badge>
                                          ))}
                                        </div>
                                      </div>
                                    )}
                                    {routine.dependent_functions?.length > 0 && (
                                      <div>
                                        <h5 style={{ fontSize: '13px', fontWeight: 500, marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                          <Code size={14} /> Functions ({routine.dependent_functions.length})
                                        </h5>
                                        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                                          {routine.dependent_functions.map((func: string, idx: number) => (
                                            <Badge key={idx} variant="warning">{func}</Badge>
                                          ))}
                                        </div>
                                      </div>
                                    )}
                                    {routine.calls_procedures?.length > 0 && (
                                      <div>
                                        <h5 style={{ fontSize: '13px', fontWeight: 500, marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                          <Code size={14} /> Calls Procedures ({routine.calls_procedures.length})
                                        </h5>
                                        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                                          {routine.calls_procedures.map((proc: string, idx: number) => (
                                            <Badge key={idx} variant="success">{proc}</Badge>
                                          ))}
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            )}

                            {/* Execution Statistics Tab */}
                            {activeDetailTab === 'execution' && (
                              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px', marginTop: '4px' }}>
                                {[
                                  { label: 'Total Executions', value: totalExecutions > 0 ? totalExecutions.toLocaleString() : '-' },
                                  { label: 'Today', value: executionsToday > 0 ? executionsToday.toLocaleString() : '-' },
                                  { label: 'Last 7 Days', value: executions7Days > 0 ? executions7Days.toLocaleString() : '-' },
                                  { label: 'Last 30 Days', value: executions30Days > 0 ? executions30Days.toLocaleString() : '-' },
                                  { label: 'Avg Duration (ms)', value: avgDurationMs > 0 ? avgDurationMs.toFixed(2) : '-' },
                                  { label: 'Last Executed', value: lastExecutionTime ? formatDate(lastExecutionTime) : 'Never', small: true },
                                ].map((stat, i) => (
                                  <div key={i} style={{ background: '#f9fafb', borderRadius: '6px', padding: '12px 14px' }}>
                                    <div style={{ fontSize: '11px', color: 'var(--color-text-secondary)', marginBottom: '6px', textAlign: 'left' }}>
                                      {stat.label}
                                    </div>
                                    <div style={{ fontSize: stat.small ? '13px' : '18px', fontWeight: stat.small ? 500 : 600, color: 'var(--color-text-primary)', textAlign: 'left' }}>
                                      {stat.value}
                                    </div>
                                  </div>
                                ))}
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
