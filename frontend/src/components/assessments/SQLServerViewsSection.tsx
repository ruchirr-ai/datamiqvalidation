/**
 * SQL Server Views Section Component
 * 
 * Displays views with SQL Server-specific features:
 * - View definition
 * - Dependencies (tables, views, functions) — shown on expand
 * - Indexes on indexed views — shown on expand
 */

import React, { useState } from 'react';
import { Eye, Code, Database, Table as TableIcon, HardDrive } from 'lucide-react';
import { Badge } from '../ui';

interface SQLServerViewsSectionProps {
  views: any[];
  indexes: any[];
  formatDate: (dateString: string | null) => string;
  formatSize: (sizeMb: number) => string;
}

export const SQLServerViewsSection: React.FC<SQLServerViewsSectionProps> = ({
  views,
  indexes,
  formatDate,
  formatSize
}) => {
  const [expandedView, setExpandedView] = useState<number | null>(null);
  const [activeDetailTab, setActiveDetailTab] = useState<'definition' | 'dependencies' | 'indexes'>('definition');

  const handleViewClick = (index: number) => {
    if (expandedView === index) {
      setExpandedView(null);
    } else {
      setExpandedView(index);
      setActiveDetailTab('definition');
    }
  };

  const getIndexesForView = (viewName: string) => {
    return indexes?.filter((idx: any) =>
      idx.object_type === 'VIEW' && idx.table_name === viewName
    ) || [];
  };

  return (
    <div className="section-content">
      <h2 className="section-heading">Views ({views.length})</h2>
      {views.length === 0 ? (
        <div className="empty-state">
          <Eye size={48} />
          <p>No views found</p>
        </div>
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {views.map((view: any, index: number) => {
                const isExpanded = expandedView === index;
                const totalDeps = (view.dependent_tables?.length || 0) +
                                 (view.dependent_views?.length || 0) +
                                 (view.dependent_functions?.length || 0);
                const viewIndexes = getIndexesForView(view.view_name);

                return (
                  <React.Fragment key={index}>
                    <tr style={{ cursor: 'pointer' }} onClick={() => handleViewClick(index)}>
                      <td>
                        <span className="table-name-link">
                          {view.view_name}
                        </span>
                      </td>
                      <td>
                        <Badge variant={view.view_type === 'MATERIALIZED_VIEW' ? 'info' : 'default'}>
                          {view.view_type}
                        </Badge>
                      </td>
                      <td className="timestamp-value">{formatDate(view.creation_time)}</td>
                    </tr>

                    {isExpanded && (
                      <tr className="expanded-row">
                        <td colSpan={3}>
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
                              onClick={() => setActiveDetailTab('indexes')}
                              style={{
                                display: 'flex', alignItems: 'center', gap: '6px',
                                padding: '6px 14px', border: 'none', background: 'none', cursor: 'pointer',
                                fontSize: '13px', fontWeight: 500,
                                color: activeDetailTab === 'indexes' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
                                borderBottom: activeDetailTab === 'indexes' ? '2px solid var(--color-primary)' : '2px solid transparent'
                              }}
                            >
                              <HardDrive size={14} /> Indexes ({viewIndexes.length})
                            </button>
                          </div>

                          <div style={{ padding: '16px 0' }}>
                            {/* Definition Tab */}
                            {activeDetailTab === 'definition' && view.view_definition && (
                              <pre className="sql-code"><code>{view.view_definition}</code></pre>
                            )}
                            {activeDetailTab === 'definition' && !view.view_definition && (
                              <p className="text-muted">No definition available</p>
                            )}

                            {/* Dependencies Tab */}
                            {activeDetailTab === 'dependencies' && (
                              <div>
                                {totalDeps === 0 ? (
                                  <p className="text-muted">No dependencies found</p>
                                ) : (
                                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                    {view.dependent_tables?.length > 0 && (
                                      <div>
                                        <h5 style={{ fontSize: '13px', fontWeight: 500, marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                          <TableIcon size={14} /> Tables ({view.dependent_tables.length})
                                        </h5>
                                        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                                          {view.dependent_tables.map((t: string, i: number) => (
                                            <Badge key={i} variant="default">{t}</Badge>
                                          ))}
                                        </div>
                                      </div>
                                    )}
                                    {view.dependent_views?.length > 0 && (
                                      <div>
                                        <h5 style={{ fontSize: '13px', fontWeight: 500, marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                          <Eye size={14} /> Views ({view.dependent_views.length})
                                        </h5>
                                        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                                          {view.dependent_views.map((v: string, i: number) => (
                                            <Badge key={i} variant="info">{v}</Badge>
                                          ))}
                                        </div>
                                      </div>
                                    )}
                                    {view.dependent_functions?.length > 0 && (
                                      <div>
                                        <h5 style={{ fontSize: '13px', fontWeight: 500, marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                          <Code size={14} /> Functions ({view.dependent_functions.length})
                                        </h5>
                                        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                                          {view.dependent_functions.map((f: string, i: number) => (
                                            <Badge key={i} variant="warning">{f}</Badge>
                                          ))}
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            )}

                            {/* Indexes Tab */}
                            {activeDetailTab === 'indexes' && (
                              <div>
                                {viewIndexes.length === 0 ? (
                                  <div className="empty-state" style={{ padding: '24px' }}>
                                    <HardDrive size={36} />
                                    <p>No indexes on this view</p>
                                  </div>
                                ) : (
                                  <table className="data-table compact">
                                    <thead>
                                      <tr>
                                        <th>Index Name</th>
                                        <th>Type</th>
                                        <th>Columns</th>
                                        <th>Unique</th>
                                        <th>Clustered</th>
                                        <th>Size</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {viewIndexes.map((idx: any, i: number) => (
                                        <tr key={i}>
                                          <td className="font-medium">{idx.index_name}</td>
                                          <td>
                                            <Badge variant={idx.index_type === 'CLUSTERED' ? 'success' : 'info'}>
                                              {idx.index_type}
                                            </Badge>
                                          </td>
                                          <td className="text-sm">{idx.key_columns}</td>
                                          <td>
                                            <Badge variant={idx.is_unique ? 'success' : 'default'}>
                                              {idx.is_unique ? 'Yes' : 'No'}
                                            </Badge>
                                          </td>
                                          <td>
                                            <Badge variant={idx.is_clustered ? 'warning' : 'default'}>
                                              {idx.is_clustered ? 'Yes' : 'No'}
                                            </Badge>
                                          </td>
                                          <td className="numeric-value">{formatSize(idx.size_mb || 0)}</td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                )}
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
