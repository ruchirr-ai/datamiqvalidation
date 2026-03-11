import React, { useState, useEffect } from 'react';
import { Activity, TrendingUp, Clock, Database, CheckCircle, XCircle } from 'lucide-react';
import './QueryInsightsSection.css';

interface QueryInsight {
  job_id: string;
  execution_time: string;
  query_text: string;
  bytes_scanned: number;
  bytes_billed: number;
  slot_milliseconds: number;
  cache_hit: boolean;
  cache_hit_status: string;
  referenced_tables: string[];
  user_email: string;
}

interface QueryInsightsSummary {
  total_query_count: number;
  active_users_count: number;
  avg_execution_time_seconds: number;
  total_bytes_scanned: number;
  total_bytes_billed: number;
  total_slot_milliseconds: number;
  cache_hit_rate: number;
  cache_hits: number;
  cache_misses: number;
  read_queries: number;
  write_queries: number;
}

interface ConcurrentQueryData {
  time: string;
  count: number;
}

interface QueryInsightsCharts {
  read_write_distribution: {
    read: number;
    write: number;
  };
  concurrent_queries: {
    hourly: ConcurrentQueryData[];
    daily: ConcurrentQueryData[];
    weekly: ConcurrentQueryData[];
  };
}

interface QueryInsightsData {
  assessment_id: number;
  timeframe: string;
  summary: QueryInsightsSummary;
  charts: QueryInsightsCharts;
  queries: QueryInsight[];
}

interface QueryInsightsSectionProps {
  assessmentId: number;
}

const QueryInsightsSection: React.FC<QueryInsightsSectionProps> = ({ assessmentId }) => {
  const [data, setData] = useState<QueryInsightsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [timeframe, setTimeframe] = useState('all');
  const [expandedQuery, setExpandedQuery] = useState<number | null>(null);
  const [concurrentInterval, setConcurrentInterval] = useState<'hourly' | 'daily' | 'weekly'>('daily');
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [sortBy, setSortBy] = useState('bytes_scanned');
  const [page, setPage] = useState(1);
  const [pagination, setPagination] = useState<{ total_filtered: number; total_pages: number } | null>(null);

  useEffect(() => {
    fetchQueryInsights();
  }, [assessmentId, timeframe, search, sortBy, page]);

  const fetchQueryInsights = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({ timeframe, sort_by: sortBy, page: String(page), page_size: '50' });
      if (search) params.set('search', search);
      const response = await fetch(`/api/assessments/${assessmentId}/query-insights?${params}`);
      if (!response.ok) throw new Error('Failed to fetch query insights');
      const result = await response.json();
      setData(result);
      setPagination(result.pagination || null);
    } catch (error) {
      // silently fail
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    setPage(1);
    setSearch(searchInput);
  };

  const handleSearchKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch();
  };

  const formatTime = (seconds: number): string => {
    if (seconds < 1) {
      return `${(seconds * 1000).toFixed(0)}ms`;
    } else if (seconds < 60) {
      return `${seconds.toFixed(2)}s`;
    } else {
      const minutes = Math.floor(seconds / 60);
      const remainingSeconds = seconds % 60;
      return `${minutes}m ${remainingSeconds.toFixed(0)}s`;
    }
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
  };

  const formatNumber = (num: number): string => {
    return num.toLocaleString();
  };

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  const truncateQuery = (query: string, maxLength: number = 100): string => {
    if (!query) return '';
    return query.length > maxLength ? query.substring(0, maxLength) + '...' : query;
  };

  const renderPieChart = () => {
    if (!data?.charts?.read_write_distribution) return null;

    const { read, write } = data.charts.read_write_distribution;
    const total = read + write;
    
    if (total === 0) return null;

    const readPercentage = (read / total) * 100;
    const writePercentage = (write / total) * 100;

    // Calculate pie slice paths
    const createPieSlice = (startAngle: number, endAngle: number) => {
      const cx = 100;
      const cy = 100;
      const radius = 80;
      
      const startRad = (startAngle - 90) * Math.PI / 180;
      const endRad = (endAngle - 90) * Math.PI / 180;
      
      const x1 = cx + radius * Math.cos(startRad);
      const y1 = cy + radius * Math.sin(startRad);
      const x2 = cx + radius * Math.cos(endRad);
      const y2 = cy + radius * Math.sin(endRad);
      
      const largeArc = endAngle - startAngle > 180 ? 1 : 0;
      
      return `M ${cx} ${cy} L ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2} Z`;
    };

    const readAngle = (readPercentage / 100) * 360;
    const writeAngle = (writePercentage / 100) * 360;

    return (
      <div className="chart-card pie-chart-card">
        <h3 className="chart-title">Query Type Distribution</h3>
        <div className="pie-chart-container">
          <div className="pie-chart-wrapper">
            <svg viewBox="0 0 200 200" className="pie-chart">
              {/* Read slice (blue) - starts at 0 degrees */}
              {read > 0 && (
                <path
                  d={createPieSlice(0, readAngle)}
                  fill="#0070E0"
                  className="pie-segment"
                  opacity="0.9"
                >
                  <title>Read Queries: {read} ({readPercentage.toFixed(1)}%)</title>
                </path>
              )}
              
              {/* Write slice (gold) - starts where read ends */}
              {write > 0 && (
                <path
                  d={createPieSlice(readAngle, 360)}
                  fill="#FFD140"
                  className="pie-segment"
                  opacity="0.9"
                >
                  <title>Write Queries: {write} ({writePercentage.toFixed(1)}%)</title>
                </path>
              )}
              
              {/* Center circle for donut effect */}
              <circle
                cx="100"
                cy="100"
                r="50"
                fill="white"
              />
              
              {/* Center text - Total */}
              <text
                x="100"
                y="95"
                textAnchor="middle"
                fontSize="28"
                fontWeight="700"
                fill="#001435"
                fontFamily="Inter, sans-serif"
              >
                {total}
              </text>
              <text
                x="100"
                y="115"
                textAnchor="middle"
                fontSize="12"
                fill="#666"
                fontFamily="Inter, sans-serif"
              >
                Total Queries
              </text>
            </svg>
          </div>
          
          <div className="pie-chart-legend">
            <div className="legend-item">
              <div className="legend-marker">
                <span className="legend-color" style={{ backgroundColor: '#0070E0' }}></span>
                <span className="legend-label">Read Queries</span>
              </div>
              <div className="legend-stats">
                <span className="legend-value">{formatNumber(read)}</span>
                <span className="legend-percentage">{readPercentage.toFixed(1)}%</span>
              </div>
            </div>
            
            <div className="legend-item">
              <div className="legend-marker">
                <span className="legend-color" style={{ backgroundColor: '#FFD140' }}></span>
                <span className="legend-label">Write Queries</span>
              </div>
              <div className="legend-stats">
                <span className="legend-value">{formatNumber(write)}</span>
                <span className="legend-percentage">{writePercentage.toFixed(1)}%</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderLineChart = () => {
    if (!data?.charts?.concurrent_queries) return null;

    const chartData = data.charts.concurrent_queries[concurrentInterval];
    
    if (!chartData || chartData.length === 0) return null;

    // Find max value for scaling
    const maxCount = Math.max(...chartData.map(d => d.count));
    
    // Fixed dimensions for proper rendering
    const width = 900;
    const height = 300;
    const padding = { top: 30, right: 30, bottom: 70, left: 60 };
    const innerWidth = width - padding.left - padding.right;
    const innerHeight = height - padding.top - padding.bottom;

    // Calculate points for the line
    const points = chartData.map((d, i) => {
      const x = padding.left + (i / Math.max(chartData.length - 1, 1)) * innerWidth;
      const y = padding.top + innerHeight - (d.count / maxCount) * innerHeight;
      return { x, y, count: d.count, time: d.time };
    });

    // Create path for line
    const linePath = points.map((p, i) => 
      `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`
    ).join(' ');

    // Create area path
    const areaPath = `${linePath} L ${points[points.length - 1].x} ${height - padding.bottom} L ${padding.left} ${height - padding.bottom} Z`;

    // Format time labels
    const formatTimeLabel = (time: string) => {
      if (concurrentInterval === 'hourly') {
        const parts = time.split(' ');
        if (parts.length === 2) {
          const timeParts = parts[1].split(':');
          const hour = parseInt(timeParts[0]);
          const ampm = hour >= 12 ? 'pm' : 'am';
          const displayHour = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour;
          return `${displayHour}${ampm}`;
        }
        return time;
      } else if (concurrentInterval === 'daily') {
        const parts = time.split('-');
        if (parts.length === 3) {
          const month = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][parseInt(parts[1]) - 1];
          const day = parseInt(parts[2]);
          return `${month} ${day}`;
        }
        return time;
      } else {
        const parts = time.split('-W');
        return parts.length === 2 ? `W${parseInt(parts[1])}` : time;
      }
    };

    // Determine label step
    let labelStep = 1;
    if (chartData.length > 30) labelStep = Math.ceil(chartData.length / 10);
    else if (chartData.length > 15) labelStep = Math.ceil(chartData.length / 8);
    else if (chartData.length > 8) labelStep = 2;

    // Y-axis ticks
    const yTicks = 6;
    const yStep = maxCount / (yTicks - 1);

    // Count label visibility
    const shouldShowCountLabel = (index: number) => {
      if (chartData.length <= 10) return true;
      if (chartData.length <= 20) return index % 2 === 0;
      if (chartData.length <= 40) return index % 4 === 0;
      return index % 6 === 0;
    };

    return (
      <div className="chart-card line-chart-card">
        <div className="chart-header">
          <h3 className="chart-title">Concurrent Queries Over Time</h3>
          <div className="interval-filter">
            <button
              className={`interval-btn ${concurrentInterval === 'hourly' ? 'active' : ''}`}
              onClick={() => setConcurrentInterval('hourly')}
            >
              Hourly
            </button>
            <button
              className={`interval-btn ${concurrentInterval === 'daily' ? 'active' : ''}`}
              onClick={() => setConcurrentInterval('daily')}
            >
              Daily
            </button>
            <button
              className={`interval-btn ${concurrentInterval === 'weekly' ? 'active' : ''}`}
              onClick={() => setConcurrentInterval('weekly')}
            >
              Weekly
            </button>
          </div>
        </div>
        <div className="line-chart-container">
          <svg viewBox={`0 0 ${width} ${height}`} className="line-chart" preserveAspectRatio="xMidYMid meet">
            <defs>
              <linearGradient id="lineGradient" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="#0070E0" stopOpacity="0.2" />
                <stop offset="100%" stopColor="#0070E0" stopOpacity="0.02" />
              </linearGradient>
            </defs>

            {/* Grid lines and Y-axis */}
            {Array.from({ length: yTicks }).map((_, i) => {
              const value = Math.round(maxCount - (i * yStep));
              const y = padding.top + (i / (yTicks - 1)) * innerHeight;
              return (
                <g key={i}>
                  <line
                    x1={padding.left}
                    y1={y}
                    x2={width - padding.right}
                    y2={y}
                    stroke="#e5e7eb"
                    strokeWidth="1"
                    strokeDasharray="4 4"
                  />
                  <text
                    x={padding.left - 10}
                    y={y + 4}
                    textAnchor="end"
                    fontSize="11"
                    fill="#666"
                    fontFamily="Inter, sans-serif"
                  >
                    {value}
                  </text>
                </g>
              );
            })}

            {/* Area */}
            <path d={areaPath} fill="url(#lineGradient)" />

            {/* Line */}
            <path
              d={linePath}
              fill="none"
              stroke="#0070E0"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            {/* Points and labels */}
            {points.map((p, i) => (
              <g key={i}>
                <circle
                  cx={p.x}
                  cy={p.y}
                  r="4"
                  fill="#0070E0"
                  stroke="white"
                  strokeWidth="2"
                  className="chart-point"
                >
                  <title>{`${formatTimeLabel(p.time)}: ${p.count} queries`}</title>
                </circle>
                {shouldShowCountLabel(i) && (
                  <text
                    x={p.x}
                    y={p.y - 10}
                    textAnchor="middle"
                    fontSize="10"
                    fill="#0070E0"
                    fontWeight="600"
                    fontFamily="Inter, sans-serif"
                  >
                    {p.count}
                  </text>
                )}
              </g>
            ))}

            {/* X-axis labels */}
            {chartData.map((d, i) => {
              const shouldShow = i === 0 || i === chartData.length - 1 || i % labelStep === 0;
              if (!shouldShow) return null;
              
              const x = padding.left + (i / Math.max(chartData.length - 1, 1)) * innerWidth;
              return (
                <text
                  key={i}
                  x={x}
                  y={height - padding.bottom + 15}
                  textAnchor="end"
                  fontSize="10"
                  fill="#666"
                  fontFamily="Inter, sans-serif"
                  transform={`rotate(-45 ${x} ${height - padding.bottom + 15})`}
                >
                  {formatTimeLabel(d.time)}
                </text>
              );
            })}

            {/* Axis labels */}
            <text
              x={20}
              y={height / 2}
              textAnchor="middle"
              fontSize="12"
              fill="#666"
              fontWeight="500"
              fontFamily="Inter, sans-serif"
              transform={`rotate(-90 20 ${height / 2})`}
            >
              Queries
            </text>
          </svg>
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="query-insights-loading">
        <Activity className="spinner" size={48} />
        <p>Loading query insights...</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="query-insights-error">
        <p>Failed to load query insights</p>
      </div>
    );
  }

  return (
    <div className="query-insights-container">
      {/* Timeframe Filter */}
      <div className="query-insights-header">
        <h2 className="section-heading">Query Insights</h2>
        <div className="timeframe-filter">
          <button
            className={`filter-btn ${timeframe === 'all' ? 'active' : ''}`}
            onClick={() => setTimeframe('all')}
          >
            All Time
          </button>
          <button
            className={`filter-btn ${timeframe === '24h' ? 'active' : ''}`}
            onClick={() => setTimeframe('24h')}
          >
            Last 24 Hours
          </button>
          <button
            className={`filter-btn ${timeframe === '7d' ? 'active' : ''}`}
            onClick={() => setTimeframe('7d')}
          >
            Last 7 Days
          </button>
          <button
            className={`filter-btn ${timeframe === '30d' ? 'active' : ''}`}
            onClick={() => setTimeframe('30d')}
          >
            Last 30 Days
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="query-insights-summary">
        <div className="summary-card">
          <div className="summary-icon">
            <Activity size={24} />
          </div>
          <div className="summary-content">
            <div className="summary-value">{formatNumber(data.summary.total_query_count)}</div>
            <div className="summary-label">Total Queries</div>
          </div>
        </div>

        <div className="summary-card">
          <div className="summary-icon">
            <Clock size={24} />
          </div>
          <div className="summary-content">
            <div className="summary-value">{formatTime(data.summary.avg_execution_time_seconds)}</div>
            <div className="summary-label">Avg Execution Time</div>
          </div>
        </div>

        <div className="summary-card">
          <div className="summary-icon">
            <Database size={24} />
          </div>
          <div className="summary-content">
            <div className="summary-value">{formatBytes(data.summary.total_bytes_scanned)}</div>
            <div className="summary-label">Bytes Scanned</div>
          </div>
        </div>

        <div className="summary-card">
          <div className="summary-icon">
            <TrendingUp size={24} />
          </div>
          <div className="summary-content">
            <div className="summary-value">{data.summary.cache_hit_rate.toFixed(1)}%</div>
            <div className="summary-label">Cache Hit Rate</div>
          </div>
        </div>
      </div>

      {/* Charts Section */}
      <div className="charts-section">
        {renderPieChart()}
        {renderLineChart()}
      </div>

      {/* Query Table */}
      <div className="query-insights-table-container">
        {/* Search & Sort Controls */}
        <div className="query-table-controls">
          <div className="query-search-box">
            <input
              type="text"
              placeholder="Search by query, user, or job ID..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={handleSearchKeyDown}
              className="query-search-input"
            />
            <button className="query-search-btn" onClick={handleSearch}>Search</button>
            {search && (
              <button className="query-search-clear" onClick={() => { setSearchInput(''); setSearch(''); setPage(1); }}>Clear</button>
            )}
          </div>
          <div className="query-sort-box">
            <span className="query-sort-label">Sort by:</span>
            <select
              value={sortBy}
              onChange={(e) => { setSortBy(e.target.value); setPage(1); }}
              className="query-sort-select"
            >
              <option value="bytes_scanned">Bytes Scanned (highest)</option>
              <option value="slot_milliseconds">Slot Time (highest)</option>
              <option value="execution_time">Most Recent</option>
            </select>
          </div>
        </div>

        {pagination && (
          <div className="query-table-info">
            Showing {Math.min((page - 1) * 50 + 1, pagination.total_filtered)}–{Math.min(page * 50, pagination.total_filtered)} of {pagination.total_filtered.toLocaleString()} queries
            {search && <span className="query-search-tag"> matching "{search}"</span>}
          </div>
        )}

        <table className="query-insights-table">
          <thead>
            <tr>
              <th>Job ID</th>
              <th>Execution Time</th>
              <th>Query Text</th>
              <th>Bytes Scanned</th>
              <th>Bytes Billed</th>
              <th>Slot ms</th>
              <th>Cache Hit</th>
              <th>User Email</th>
            </tr>
          </thead>
          <tbody>
            {data.queries.length === 0 ? (
              <tr>
                <td colSpan={8} className="empty-state-cell">
                  <div className="empty-state">
                    <Activity size={48} />
                    <p>{search ? `No queries matching "${search}"` : 'No query data available for the selected timeframe'}</p>
                  </div>
                </td>
              </tr>
            ) : (
              data.queries.map((query, index) => {
                const isExpanded = expandedQuery === index;
                return (
                  <React.Fragment key={index}>
                    <tr className="query-row">
                      <td className="job-id-cell">
                        <code>{query.job_id}</code>
                      </td>
                      <td>
                        <Clock size={14} style={{ marginRight: '4px', verticalAlign: 'middle' }} />
                        {formatDate(query.execution_time)}
                      </td>
                      <td className="query-text-cell">
                        <div
                          className="query-text-preview"
                          onClick={() => setExpandedQuery(isExpanded ? null : index)}
                          title="Click to expand"
                        >
                          {truncateQuery(query.query_text, 80)}
                        </div>
                      </td>
                      <td>{formatBytes(query.bytes_scanned)}</td>
                      <td>{formatBytes(query.bytes_billed)}</td>
                      <td>{formatNumber(query.slot_milliseconds)}</td>
                      <td>
                        <span className={`cache-status ${query.cache_hit ? 'hit' : 'miss'}`}>
                          {query.cache_hit ? (
                            <><CheckCircle size={14} /> Hit</>
                          ) : (
                            <><XCircle size={14} /> Miss</>
                          )}
                        </span>
                      </td>
                      <td className="user-email-cell">{query.user_email}</td>
                    </tr>
                    {isExpanded && (
                      <tr className="expanded-row">
                        <td colSpan={8}>
                          <div className="expanded-content">
                            <div className="expanded-section">
                              <h4>Full Query</h4>
                              <pre className="query-text-full">{query.query_text}</pre>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })
            )}
          </tbody>
        </table>

        {/* Pagination */}
        {pagination && pagination.total_pages > 1 && (
          <div className="query-pagination">
            <button
              className="query-page-btn"
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
            >
              ← Previous
            </button>
            <span className="query-page-info">
              Page {page} of {pagination.total_pages}
            </span>
            <button
              className="query-page-btn"
              disabled={page >= pagination.total_pages}
              onClick={() => setPage(page + 1)}
            >
              Next →
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default QueryInsightsSection;
