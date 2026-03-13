/**
 * Documentation Page
 * 
 * Professional AWS-style documentation for the DataMIQ platform.
 * Opens in a standalone layout (no sidebar) when accessed via /docs.
 */

import React, { useState, useEffect } from 'react';
import { useTheme } from '../contexts/ThemeContext';
import { Logo } from '../components/ui/Logo';
import { ChevronRight, Search, ExternalLink, BookOpen, Cable, Shield, BarChart3, Code, CheckCircle, Activity, Settings, Layers, ArrowRight } from 'lucide-react';
import './DocumentationPage.css';

type SectionId =
  | 'getting-started'
  | 'dashboard'
  | 'workspaces'
  | 'connections'
  | 'assessments'
  | 'migrations'
  | 'code-converter'
  | 'data-validation'
  | 'jobs'
  | 'monitoring'
  | 'admin'
  | 'security'
  | 'faq';

interface TocItem {
  id: SectionId;
  label: string;
  icon: React.ReactNode;
}

const tocItems: TocItem[] = [
  { id: 'getting-started', label: 'Getting Started', icon: <BookOpen size={16} /> },
  { id: 'dashboard', label: 'Dashboard', icon: <BarChart3 size={16} /> },
  { id: 'workspaces', label: 'Workspaces', icon: <Layers size={16} /> },
  { id: 'connections', label: 'Connections', icon: <Cable size={16} /> },
  { id: 'assessments', label: 'Assessments', icon: <Shield size={16} /> },
  { id: 'migrations', label: 'Migrations', icon: <ArrowRight size={16} /> },
  { id: 'code-converter', label: 'Code Converter', icon: <Code size={16} /> },
  { id: 'data-validation', label: 'Data Validation', icon: <CheckCircle size={16} /> },
  { id: 'jobs', label: 'Jobs', icon: <Activity size={16} /> },
  { id: 'monitoring', label: 'Monitoring', icon: <BarChart3 size={16} /> },
  { id: 'admin', label: 'Administration', icon: <Settings size={16} /> },
  { id: 'security', label: 'Security', icon: <Shield size={16} /> },
  { id: 'faq', label: 'FAQ', icon: <BookOpen size={16} /> },
];

export const DocumentationPage: React.FC = () => {
  const { theme, toggleTheme } = useTheme();
  const [activeSection, setActiveSection] = useState<SectionId>('getting-started');
  const [searchQuery, setSearchQuery] = useState('');
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);

  useEffect(() => {
    const hash = window.location.hash.replace('#', '') as SectionId;
    if (hash && tocItems.some(t => t.id === hash)) {
      setActiveSection(hash);
    }
  }, []);

  const scrollToSection = (id: SectionId) => {
    setActiveSection(id);
    setIsMobileNavOpen(false);
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    window.history.replaceState(null, '', `#${id}`);
  };

  // Track active section on scroll
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id as SectionId);
          }
        }
      },
      { rootMargin: '-80px 0px -60% 0px', threshold: 0.1 }
    );

    tocItems.forEach(item => {
      const el = document.getElementById(item.id);
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, []);

  const filteredToc = searchQuery
    ? tocItems.filter(t => t.label.toLowerCase().includes(searchQuery.toLowerCase()))
    : tocItems;

  return (
    <div className="docs-page" data-theme={theme}>
      {/* Top Bar */}
      <header className="docs-topbar">
        <div className="docs-topbar-left">
          <Logo size={24} showText animate={false} />
          <span className="docs-topbar-divider" />
          <span className="docs-topbar-title">Documentation</span>
        </div>
        <div className="docs-topbar-right">
          <button className="docs-theme-btn" onClick={toggleTheme} aria-label="Toggle theme">
            {theme === 'light' ? '🌙' : '☀️'}
          </button>
          <a href="/dashboard" className="docs-back-link">
            Back to Console <ExternalLink size={14} />
          </a>
        </div>
      </header>

      <div className="docs-layout">
        {/* Left Navigation */}
        <nav className={`docs-sidebar ${isMobileNavOpen ? 'open' : ''}`}>
          <div className="docs-search">
            <Search size={16} className="docs-search-icon" />
            <input
              type="text"
              placeholder="Search documentation..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="docs-search-input"
            />
          </div>
          <ul className="docs-toc">
            {filteredToc.map(item => (
              <li key={item.id}>
                <button
                  className={`docs-toc-item ${activeSection === item.id ? 'active' : ''}`}
                  onClick={() => scrollToSection(item.id)}
                >
                  <span className="docs-toc-icon">{item.icon}</span>
                  <span>{item.label}</span>
                </button>
              </li>
            ))}
          </ul>
          <div className="docs-sidebar-footer">
            <span className="docs-version">DataMIQ v1.0.0</span>
          </div>
        </nav>

        {/* Mobile nav toggle */}
        <button
          className="docs-mobile-nav-toggle"
          onClick={() => setIsMobileNavOpen(!isMobileNavOpen)}
          aria-label="Toggle navigation"
        >
          ☰ Navigation
        </button>

        {/* Main Content */}
        <main className="docs-content">

          {/* Getting Started */}
          <section id="getting-started" className="docs-section">
            <div className="docs-breadcrumb">
              <span>Documentation</span> <ChevronRight size={14} /> <span>Getting Started</span>
            </div>
            <h1>Welcome to DataMIQ</h1>
            <p className="docs-lead">
              DataMIQ is an enterprise-grade database migration platform that enables organizations to assess, plan, and execute
              database migrations with comprehensive monitoring and validation. This guide covers every feature available in the platform.
            </p>

            <div className="docs-callout info">
              <strong>Quick start:</strong> To begin migrating data, follow these steps: create a <strong>Connection</strong> to your source and target databases,
              run an <strong>Assessment</strong> to analyze your source, then create and execute a <strong>Migration</strong>.
            </div>

            <h2>Platform overview</h2>
            <p>DataMIQ provides an end-to-end migration workflow:</p>
            <table className="docs-table">
              <thead>
                <tr><th>Step</th><th>Feature</th><th>Description</th></tr>
              </thead>
              <tbody>
                <tr><td>1</td><td>Connections</td><td>Register source and target database credentials</td></tr>
                <tr><td>2</td><td>Assessments</td><td>Analyze source database structure, queries, and security policies</td></tr>
                <tr><td>3</td><td>Migrations</td><td>Configure and execute data migration with multiple pathway options</td></tr>
                <tr><td>4</td><td>Validation</td><td>Verify data integrity between source and target post-migration</td></tr>
                <tr><td>5</td><td>Monitoring</td><td>Track progress, query history, and copy operations in real time</td></tr>
              </tbody>
            </table>

            <h2>Supported databases</h2>
            <div className="docs-grid-2">
              <div className="docs-card">
                <h3>Source databases</h3>
                <ul>
                  <li>Google BigQuery</li>
                  <li>PostgreSQL</li>
                  <li>MySQL</li>
                  <li>Oracle</li>
                  <li>MongoDB</li>
                </ul>
              </div>
              <div className="docs-card">
                <h3>Target databases</h3>
                <ul>
                  <li>Amazon Redshift</li>
                  <li>PostgreSQL</li>
                  <li>Amazon DocumentDB</li>
                </ul>
              </div>
            </div>
          </section>

          {/* Dashboard */}
          <section id="dashboard" className="docs-section">
            <div className="docs-breadcrumb">
              <span>Documentation</span> <ChevronRight size={14} /> <span>Dashboard</span>
            </div>
            <h1>Dashboard</h1>
            <p>
              The Dashboard provides a centralized overview of your entire migration platform. It displays real-time summary
              cards and recent activity across all modules.
            </p>

            <h2>Summary cards</h2>
            <table className="docs-table">
              <thead><tr><th>Card</th><th>Metrics shown</th></tr></thead>
              <tbody>
                <tr><td>Connections</td><td>Total connections, source vs. target count, connected status</td></tr>
                <tr><td>Assessments</td><td>Total assessments, completed count</td></tr>
                <tr><td>Migrations</td><td>Total migrations, completed, done count</td></tr>
                <tr><td>Code Conversions</td><td>Total conversions, done count, failed, batches</td></tr>
              </tbody>
            </table>

            <h2>Assessment discovery</h2>
            <p>
              Displays aggregate metadata discovered across all completed assessments: total tables, views, and routines found,
              along with the combined data volume.
            </p>

            <h2>Migration status</h2>
            <p>
              A visual breakdown of migration statuses — completed, running, failed, and scheduled — shown as horizontal progress bars
              for quick status assessment.
            </p>

            <h2>Recent activity</h2>
            <p>
              Tabbed view showing the most recent assessments, migrations, and copy history entries. Each row is clickable
              to navigate directly to the detailed view.
            </p>
          </section>

          {/* Workspaces */}
          <section id="workspaces" className="docs-section">
            <div className="docs-breadcrumb">
              <span>Documentation</span> <ChevronRight size={14} /> <span>Workspaces</span>
            </div>
            <h1>Workspaces</h1>
            <p>
              Workspaces provide multi-tenant data isolation. Each workspace acts as an independent environment with its own
              connections, assessments, migrations, and user access controls.
            </p>

            <h2>Key concepts</h2>
            <ul>
              <li>Each user can belong to multiple workspaces</li>
              <li>Data is fully isolated between workspaces</li>
              <li>Workspace selection is available in the top bar of relevant pages</li>
              <li>Admins can create and manage workspaces from the Administration page</li>
            </ul>

            <div className="docs-callout warning">
              <strong>Note:</strong> Switching workspaces changes the context for all data-related pages. Ensure you have selected
              the correct workspace before creating connections or running assessments.
            </div>
          </section>

          {/* Connections */}
          <section id="connections" className="docs-section">
            <div className="docs-breadcrumb">
              <span>Documentation</span> <ChevronRight size={14} /> <span>Connections</span>
            </div>
            <h1>Connections</h1>
            <p>
              The Connections module manages database credentials for both source and target systems. All credentials are
              encrypted at rest using AWS KMS.
            </p>

            <h2>Creating a connection</h2>
            <ol>
              <li>Navigate to <strong>Connections</strong> in the sidebar</li>
              <li>Click <strong>+ New</strong> and select <strong>Source</strong> or <strong>Target</strong></li>
              <li>Choose the database type (BigQuery, Redshift, PostgreSQL, etc.)</li>
              <li>Fill in the required connection parameters</li>
              <li>Click <strong>Test Connection</strong> to verify connectivity</li>
              <li>Save the connection</li>
            </ol>

            <h2>Connection parameters</h2>
            <table className="docs-table">
              <thead><tr><th>Database</th><th>Required fields</th></tr></thead>
              <tbody>
                <tr><td>BigQuery</td><td>Project ID, Service Account JSON, Dataset (optional)</td></tr>
                <tr><td>Redshift</td><td>Host, Port, Database, Username, Password, IAM Role ARN</td></tr>
                <tr><td>PostgreSQL</td><td>Host, Port, Database, Username, Password</td></tr>
                <tr><td>MySQL</td><td>Host, Port, Database, Username, Password</td></tr>
              </tbody>
            </table>

            <h2>Connection testing</h2>
            <p>
              Use the <strong>Test</strong> action from the connection row menu to verify that DataMIQ can reach the database
              with the provided credentials. The status badge updates to reflect the result.
            </p>

            <h2>Managing connections</h2>
            <p>
              From the three-dot menu on each connection row you can edit, test, or delete a connection. Deleting a connection
              that is referenced by an active migration is not permitted.
            </p>
          </section>

          {/* Assessments */}
          <section id="assessments" className="docs-section">
            <div className="docs-breadcrumb">
              <span>Documentation</span> <ChevronRight size={14} /> <span>Assessments</span>
            </div>
            <h1>Assessments</h1>
            <p>
              Assessments perform a comprehensive analysis of your source database to help plan migrations. The assessment
              engine collects metadata, query statistics, security policies, and dependency information.
            </p>

            <h2>Creating an assessment</h2>
            <ol>
              <li>Navigate to <strong>Assessments</strong> in the sidebar</li>
              <li>Click <strong>+ New</strong></li>
              <li>Select a source connection (BigQuery) and a target connection (Redshift)</li>
              <li>Provide a name for the assessment</li>
              <li>Click <strong>Create</strong> — the assessment runs in the background</li>
            </ol>

            <h2>Assessment report</h2>
            <p>Once completed, the assessment report includes the following tabs:</p>
            <table className="docs-table">
              <thead><tr><th>Tab</th><th>Contents</th></tr></thead>
              <tbody>
                <tr><td>Summary</td><td>High-level metrics: dataset count, table count, total size, view count, routine count</td></tr>
                <tr><td>Datasets</td><td>List of discovered datasets with table counts and sizes</td></tr>
                <tr><td>Tables</td><td>Detailed table metadata including columns, data types, row counts, and sizes</td></tr>
                <tr><td>Views</td><td>View definitions, SQL, and dependency information</td></tr>
                <tr><td>Routines</td><td>Stored procedures and functions with source code</td></tr>
                <tr><td>ML Models</td><td>BigQuery ML model inventory</td></tr>
                <tr><td>Query Insights</td><td>Query patterns, frequency, and performance over the last 180 days</td></tr>
                <tr><td>User Insights</td><td>User activity analysis and query patterns per user</td></tr>
                <tr><td>Security</td><td>Row-level security (RLS) and column-level security (CLS) policies</td></tr>
                <tr><td>TCO</td><td>Total cost of ownership analysis and recommendations</td></tr>
                <tr><td>Recommendations</td><td>Migration recommendations based on the analysis</td></tr>
              </tbody>
            </table>

            <h2>Sub-pages</h2>
            <ul>
              <li><strong>Schema Analysis</strong> — Deep-dive into schema structure and data types</li>
              <li><strong>Compatibility Check</strong> — Identifies compatibility issues between source and target</li>
              <li><strong>Assessment Reports</strong> — Browse and download completed assessment reports as PDF</li>
              <li><strong>Data Profiling</strong> — Statistical profiling of data distributions and quality</li>
            </ul>

            <div className="docs-callout info">
              <strong>Tip:</strong> Assessment data is a point-in-time snapshot. Run a new assessment to capture the latest state of your source database.
            </div>
          </section>

          {/* Migrations */}
          <section id="migrations" className="docs-section">
            <div className="docs-breadcrumb">
              <span>Documentation</span> <ChevronRight size={14} /> <span>Migrations</span>
            </div>
            <h1>Migrations</h1>
            <p>
              The Migrations module orchestrates data movement from source to target databases. DataMIQ supports multiple
              migration pathways optimized for different use cases.
            </p>

            <h2>Migration pathways</h2>
            <table className="docs-table">
              <thead><tr><th>Pathway</th><th>Method</th><th>Best for</th></tr></thead>
              <tbody>
                <tr><td>Pathway A</td><td>AWS SCT + DMS</td><td>Standard migrations using AWS-native tooling</td></tr>
                <tr><td>Pathway B</td><td>AWS DataSync</td><td>Large-scale GCS-to-S3 data transfers</td></tr>
                <tr><td>Pathway C</td><td>Direct Download/Upload</td><td>Custom transfer requirements with full control</td></tr>
              </tbody>
            </table>

            <h2>Creating a migration</h2>
            <ol>
              <li>Navigate to <strong>Migrations</strong> and click <strong>Create Migration</strong></li>
              <li>Select source and target connections</li>
              <li>Choose a migration pathway</li>
              <li>Configure settings (batch size, parallel workers, timeouts)</li>
              <li>Review and confirm</li>
            </ol>

            <h2>Migration lifecycle</h2>
            <p>Migrations support the following actions:</p>
            <ul>
              <li><strong>Start</strong> — Begin execution</li>
              <li><strong>Pause</strong> — Temporarily halt execution (resumable)</li>
              <li><strong>Resume</strong> — Continue a paused migration</li>
              <li><strong>Cancel</strong> — Permanently stop the migration</li>
              <li><strong>Restart</strong> — Re-run a completed or failed migration</li>
            </ul>

            <h2>Progress tracking</h2>
            <p>
              Each migration displays a progress bar with percentage completion, current stage, tables completed,
              rows transferred, and any errors encountered.
            </p>
          </section>

          {/* Code Converter */}
          <section id="code-converter" className="docs-section">
            <div className="docs-breadcrumb">
              <span>Documentation</span> <ChevronRight size={14} /> <span>Code Converter</span>
            </div>
            <h1>Code Converter</h1>
            <p>
              The Code Converter translates SQL queries between database dialects. It supports converting BigQuery SQL
              to Redshift-compatible SQL and other dialect combinations.
            </p>

            <h2>Quick Convert</h2>
            <p>
              Paste a single SQL query, select the source and target dialects, and click <strong>Convert</strong>.
              The converted output is displayed side-by-side with syntax highlighting.
            </p>

            <h2>Batch Convert</h2>
            <p>
              Upload multiple SQL files or paste multiple queries for bulk conversion. Results can be downloaded
              as a batch or reviewed individually.
            </p>
          </section>

          {/* Data Validation */}
          <section id="data-validation" className="docs-section">
            <div className="docs-breadcrumb">
              <span>Documentation</span> <ChevronRight size={14} /> <span>Data Validation</span>
            </div>
            <h1>Data Validation</h1>
            <p>
              Data Validation verifies that data migrated to the target database matches the source. It performs
              row count comparisons, schema checks, and data sampling.
            </p>

            <h2>Creating a validation run</h2>
            <ol>
              <li>Navigate to <strong>Data Validation</strong></li>
              <li>Click <strong>Create Validation</strong></li>
              <li>Select the migration, source connection, and target connection</li>
              <li>Optionally specify individual tables to validate</li>
              <li>Click <strong>Create</strong> — validation runs in the background</li>
            </ol>

            <h2>Validation results</h2>
            <p>
              Each validation run shows a summary with passed, failed, and error counts. Click into a run to see
              per-table results with detailed comparison metrics.
            </p>

            <div className="docs-callout warning">
              <strong>Important:</strong> Run validation after migration completes to ensure data integrity before
              decommissioning the source database.
            </div>
          </section>

          {/* Jobs */}
          <section id="jobs" className="docs-section">
            <div className="docs-breadcrumb">
              <span>Documentation</span> <ChevronRight size={14} /> <span>Jobs</span>
            </div>
            <h1>Jobs</h1>
            <p>
              The Jobs page provides a unified view of all background operations — assessments, migrations, and
              code conversions. Jobs auto-refresh every 10 seconds when active tasks are running.
            </p>

            <h2>Job statuses</h2>
            <table className="docs-table">
              <thead><tr><th>Status</th><th>Description</th></tr></thead>
              <tbody>
                <tr><td><code>pending</code></td><td>Job is queued and waiting to start</td></tr>
                <tr><td><code>running</code></td><td>Job is currently executing</td></tr>
                <tr><td><code>completed</code></td><td>Job finished successfully</td></tr>
                <tr><td><code>failed</code></td><td>Job encountered an error</td></tr>
              </tbody>
            </table>

            <h2>Filtering</h2>
            <p>
              Use the status tabs (All, Running, Completed, Failed, Pending) to filter the job list.
              A search bar allows filtering by job name or type.
            </p>
          </section>

          {/* Monitoring */}
          <section id="monitoring" className="docs-section">
            <div className="docs-breadcrumb">
              <span>Documentation</span> <ChevronRight size={14} /> <span>Monitoring</span>
            </div>
            <h1>Monitoring</h1>
            <p>
              The Monitoring section provides historical tracking of platform operations across multiple sub-pages.
            </p>

            <h2>Sub-pages</h2>
            <table className="docs-table">
              <thead><tr><th>Page</th><th>Description</th></tr></thead>
              <tbody>
                <tr><td>Query History</td><td>Historical log of all queries executed against source and target databases</td></tr>
                <tr><td>Copy History</td><td>Record of all data copy operations with row counts, byte counts, and durations</td></tr>
                <tr><td>Task History</td><td>Individual task execution logs with status and timing</td></tr>
                <tr><td>Dynamic Tables</td><td>Monitor dynamically created tables during migration</td></tr>
                <tr><td>Governance</td><td>Audit trail of platform actions for compliance</td></tr>
              </tbody>
            </table>
          </section>

          {/* Administration */}
          <section id="admin" className="docs-section">
            <div className="docs-breadcrumb">
              <span>Documentation</span> <ChevronRight size={14} /> <span>Administration</span>
            </div>
            <h1>Administration</h1>
            <p>
              Administration pages are available to users with the <code>admin</code> or <code>owner</code> role.
              They provide workspace management, user management, and system configuration.
            </p>

            <h2>Workspace management</h2>
            <p>Create, edit, and delete workspaces. Assign users to workspaces with specific roles.</p>

            <h2>User management</h2>
            <table className="docs-table">
              <thead><tr><th>Role</th><th>Permissions</th></tr></thead>
              <tbody>
                <tr><td>Owner</td><td>Full access including workspace and user management</td></tr>
                <tr><td>Admin</td><td>Manage connections, assessments, migrations, and view admin pages</td></tr>
                <tr><td>Member</td><td>View and execute operations within assigned workspaces</td></tr>
              </tbody>
            </table>

            <h2>Database field configuration</h2>
            <p>
              Admins can customize the connection form fields for each database type via
              <strong> Admin → Data Connections → Sources</strong>. This controls which fields appear when users create connections.
            </p>
          </section>

          {/* Security */}
          <section id="security" className="docs-section">
            <div className="docs-breadcrumb">
              <span>Documentation</span> <ChevronRight size={14} /> <span>Security</span>
            </div>
            <h1>Security</h1>
            <p>DataMIQ implements multiple layers of security to protect your data and credentials.</p>

            <h2>Authentication</h2>
            <ul>
              <li>JWT-based authentication with 8-hour token expiration</li>
              <li>Automatic token refresh</li>
              <li>Token blacklisting on logout</li>
              <li>Account locking after repeated failed login attempts</li>
            </ul>

            <h2>Data protection</h2>
            <ul>
              <li>All database credentials encrypted at rest using AWS KMS</li>
              <li>Workspace-level data isolation (multi-tenancy)</li>
              <li>Role-based access control (RBAC)</li>
              <li>Audit logging for all operations</li>
              <li>Credentials are never written to application logs</li>
            </ul>
          </section>

          {/* FAQ */}
          <section id="faq" className="docs-section">
            <div className="docs-breadcrumb">
              <span>Documentation</span> <ChevronRight size={14} /> <span>FAQ</span>
            </div>
            <h1>Frequently Asked Questions</h1>

            <div className="docs-faq-item">
              <h3>How do I re-run an assessment?</h3>
              <p>Open the assessment row menu (three dots) and select <strong>Run Assessment</strong>. A new assessment run will be queued.</p>
            </div>

            <div className="docs-faq-item">
              <h3>Can I migrate multiple tables at once?</h3>
              <p>Yes. When creating a migration, you can select multiple tables or entire datasets. The migration engine processes them in parallel based on your configured worker count.</p>
            </div>

            <div className="docs-faq-item">
              <h3>What happens if a migration fails midway?</h3>
              <p>Failed migrations can be restarted. DataMIQ tracks which tables completed successfully and resumes from the point of failure.</p>
            </div>

            <div className="docs-faq-item">
              <h3>How do I change my password?</h3>
              <p>Navigate to <strong>My Profile</strong> from the user menu in the sidebar footer. Password changes take effect immediately.</p>
            </div>

            <div className="docs-faq-item">
              <h3>Is my data encrypted?</h3>
              <p>Yes. All database credentials are encrypted using AWS KMS. Data in transit uses TLS encryption. Workspace isolation ensures data separation between tenants.</p>
            </div>

            <div className="docs-faq-item">
              <h3>How do I download an assessment report?</h3>
              <p>From the assessment row menu, select <strong>Download Report</strong> to generate and download a PDF report of the assessment results.</p>
            </div>
          </section>

          <footer className="docs-footer">
            <p>© 2026 DataMIQ. All rights reserved.</p>
          </footer>
        </main>
      </div>
    </div>
  );
};
