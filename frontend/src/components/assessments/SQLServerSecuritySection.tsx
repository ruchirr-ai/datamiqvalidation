/**
 * SQL Server Security Section Component
 * 
 * Displays SQL Server security metadata:
 * - Users & Roles
 * - Object Permissions
 * - Database Roles
 * - Schema Ownership
 */

import React, { useState } from 'react';
import { Shield, Users, Lock, Database, Key, UserCheck, FileText, Link2 } from 'lucide-react';
import { Badge } from '../ui';

interface SecurityUser {
  user_name: string;
  user_type: string;
  authentication_type: string;
  default_schema: string;
  roles: string;
  create_date: string | null;
  last_login: string | null;
  is_disabled: boolean;
  is_locked: boolean;
  password_policy: string | null;
}

interface ObjectPermission {
  schema_name: string;
  object_name: string;
  object_type: string;
  user_or_role: string;
  permission_name: string;
  permission_state: string;
  grantor: string;
  is_grantable: boolean;
}

interface DatabaseRole {
  role_name: string;
  role_category: string;
  is_fixed_role: boolean;
  members_count: number;
  description: string | null;
}

interface SchemaOwnership {
  schema_name: string;
  owner_name: string;
  owner_type: string;
  created_date: string | null;
}

interface SecurityPolicy {
  policy_name: string;
  policy_type: string;
  table_schema: string;
  table_name: string;
  filter_predicate: string;
  is_enabled: boolean;
  created_date: string | null;
}

interface LoginSecurity {
  login_name: string;
  login_type: string;
  is_disabled: boolean;
  is_locked: boolean;
  password_policy_enforced: boolean;
  password_expiration_enforced: boolean;
  failed_login_attempts: number;
  last_successful_login: string | null;
  server_roles: string[];
}

interface EncryptionInfo {
  encryption_type: string;
  key_name: string;
  algorithm: string;
  key_length: number;
  encrypted_objects_count: number;
  created_date: string | null;
}

interface LinkedServer {
  server_name: string;
  product: string;
  provider_name: string;
  data_source: string;
  default_catalog: string;
  is_remote_login_enabled: boolean;
  is_rpc_out_enabled: boolean;
  is_data_access_enabled: boolean;
  mapped_logins: string;
  modified_date: string | null;
}

interface SecurityMetadata {
  users: SecurityUser[];
  permissions: ObjectPermission[];
  roles: DatabaseRole[];
  schemas: SchemaOwnership[];
  policies: SecurityPolicy[];
  logins: LoginSecurity[];
  encryption: EncryptionInfo[];
  linkedServers: LinkedServer[];
}

interface SQLServerSecuritySectionProps {
  security?: SecurityMetadata;
  formatDate: (date: string | null) => string;
}

export const SQLServerSecuritySection: React.FC<SQLServerSecuritySectionProps> = ({ security, formatDate }) => {
  const [activeSubTab, setActiveSubTab] = useState<'users' | 'permissions' | 'roles' | 'schemas' | 'policies' | 'logins' | 'encryption' | 'linkedServers'>('users');

  if (!security || (!security.users && !security.permissions && !security.roles && !security.schemas && !security.policies && !security.logins && !security.encryption && !security.linkedServers)) {
    return (
      <div className="section-content">
        <div className="empty-state">
          <Shield size={48} />
          <p>No security metadata available</p>
        </div>
      </div>
    );
  }

  const users = security.users || [];
  const permissions = security.permissions || [];
  const roles = security.roles || [];
  const schemas = security.schemas || [];
  const policies = security.policies || [];
  const logins = security.logins || [];
  const encryption = security.encryption || [];
  const linkedServers = security.linkedServers || [];

  return (
    <div className="section-content">
      <h2 className="section-heading">Security</h2>
      
      {/* Sub-tabs */}
      <div className="sub-tabs" style={{ display: 'flex', gap: '8px', marginBottom: '24px', borderBottom: '1px solid var(--color-divider)', paddingBottom: '0', flexWrap: 'wrap' }}>
        <button
          className={`sub-tab ${activeSubTab === 'users' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('users')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '12px 16px',
            border: 'none',
            background: 'none',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: 500,
            color: activeSubTab === 'users' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
            borderBottom: activeSubTab === 'users' ? '2px solid var(--color-primary)' : '2px solid transparent',
            transition: 'all 0.2s ease'
          }}
        >
          <Users size={16} />
          Users ({users.length})
        </button>
        <button
          className={`sub-tab ${activeSubTab === 'logins' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('logins')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '12px 16px',
            border: 'none',
            background: 'none',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: 500,
            color: activeSubTab === 'logins' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
            borderBottom: activeSubTab === 'logins' ? '2px solid var(--color-primary)' : '2px solid transparent',
            transition: 'all 0.2s ease'
          }}
        >
          <UserCheck size={16} />
          Logins ({logins.length})
        </button>
        <button
          className={`sub-tab ${activeSubTab === 'roles' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('roles')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '12px 16px',
            border: 'none',
            background: 'none',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: 500,
            color: activeSubTab === 'roles' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
            borderBottom: activeSubTab === 'roles' ? '2px solid var(--color-primary)' : '2px solid transparent',
            transition: 'all 0.2s ease'
          }}
        >
          <Shield size={16} />
          Roles ({roles.length})
        </button>
        <button
          className={`sub-tab ${activeSubTab === 'permissions' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('permissions')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '12px 16px',
            border: 'none',
            background: 'none',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: 500,
            color: activeSubTab === 'permissions' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
            borderBottom: activeSubTab === 'permissions' ? '2px solid var(--color-primary)' : '2px solid transparent',
            transition: 'all 0.2s ease'
          }}
        >
          <Lock size={16} />
          Permissions ({permissions.length})
        </button>
        <button
          className={`sub-tab ${activeSubTab === 'policies' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('policies')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '12px 16px',
            border: 'none',
            background: 'none',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: 500,
            color: activeSubTab === 'policies' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
            borderBottom: activeSubTab === 'policies' ? '2px solid var(--color-primary)' : '2px solid transparent',
            transition: 'all 0.2s ease'
          }}
        >
          <FileText size={16} />
          Policies ({policies.length})
        </button>
        <button
          className={`sub-tab ${activeSubTab === 'schemas' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('schemas')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '12px 16px',
            border: 'none',
            background: 'none',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: 500,
            color: activeSubTab === 'schemas' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
            borderBottom: activeSubTab === 'schemas' ? '2px solid var(--color-primary)' : '2px solid transparent',
            transition: 'all 0.2s ease'
          }}
        >
          <Database size={16} />
          Schemas ({schemas.length})
        </button>
        <button
          className={`sub-tab ${activeSubTab === 'encryption' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('encryption')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '12px 16px',
            border: 'none',
            background: 'none',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: 500,
            color: activeSubTab === 'encryption' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
            borderBottom: activeSubTab === 'encryption' ? '2px solid var(--color-primary)' : '2px solid transparent',
            transition: 'all 0.2s ease'
          }}
        >
          <Key size={16} />
          Encryption ({encryption.length})
        </button>
        <button
          className={`sub-tab ${activeSubTab === 'linkedServers' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('linkedServers')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '12px 16px',
            border: 'none',
            background: 'none',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: 500,
            color: activeSubTab === 'linkedServers' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
            borderBottom: activeSubTab === 'linkedServers' ? '2px solid var(--color-primary)' : '2px solid transparent',
            transition: 'all 0.2s ease'
          }}
        >
          <Link2 size={16} />
          Linked Servers ({linkedServers.length})
        </button>
      </div>

      {/* Users Tab */}
      {activeSubTab === 'users' && (
        <div className="table-container">
          {users.length === 0 ? (
            <div className="empty-state">
              <Users size={48} />
              <p>No users found</p>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ textAlign: 'left' }}>User Name</th>
                  <th style={{ textAlign: 'left' }}>Type</th>
                  <th style={{ textAlign: 'left' }}>Authentication</th>
                  <th style={{ textAlign: 'left' }}>Default Schema</th>
                  <th style={{ textAlign: 'left' }}>Roles</th>
                  <th style={{ textAlign: 'left' }}>Status</th>
                  <th style={{ textAlign: 'left' }}>Created Date</th>
                  <th style={{ textAlign: 'left' }}>Last Login</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user, idx) => (
                  <tr key={idx}>
                    <td style={{ textAlign: 'left' }}>{user.user_name}</td>
                    <td style={{ textAlign: 'left' }}>
                      <Badge variant="default">{user.user_type}</Badge>
                    </td>
                    <td style={{ textAlign: 'left' }}>
                      <Badge variant={user.authentication_type === 'WINDOWS' ? 'info' : 'default'}>
                        {user.authentication_type}
                      </Badge>
                    </td>
                    <td style={{ textAlign: 'left' }}>{user.default_schema || 'dbo'}</td>
                    <td style={{ textAlign: 'left' }}>{user.roles || 'None'}</td>
                    <td style={{ textAlign: 'left' }}>
                      {user.is_disabled ? (
                        <Badge variant="error">Disabled</Badge>
                      ) : user.is_locked ? (
                        <Badge variant="warning">Locked</Badge>
                      ) : (
                        <Badge variant="success">Active</Badge>
                      )}
                    </td>
                    <td style={{ textAlign: 'left' }} className="timestamp-value">
                      {formatDate(user.create_date)}
                    </td>
                    <td style={{ textAlign: 'left' }} className="timestamp-value">
                      {formatDate(user.last_login)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Permissions Tab */}
      {activeSubTab === 'permissions' && (
        <div className="table-container">
          {permissions.length === 0 ? (
            <div className="empty-state">
              <Lock size={48} />
              <p>No permissions found</p>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ textAlign: 'left' }}>Schema</th>
                  <th style={{ textAlign: 'left' }}>Object</th>
                  <th style={{ textAlign: 'left' }}>Type</th>
                  <th style={{ textAlign: 'left' }}>User/Role</th>
                  <th style={{ textAlign: 'left' }}>Permission</th>
                  <th style={{ textAlign: 'left' }}>State</th>
                  <th style={{ textAlign: 'left' }}>Grantor</th>
                  <th style={{ textAlign: 'left' }}>Grantable</th>
                </tr>
              </thead>
              <tbody>
                {permissions.map((perm, idx) => (
                  <tr key={idx}>
                    <td style={{ textAlign: 'left' }}>{perm.schema_name}</td>
                    <td style={{ textAlign: 'left' }}>{perm.object_name}</td>
                    <td style={{ textAlign: 'left' }}>
                      <Badge variant="info">{perm.object_type}</Badge>
                    </td>
                    <td style={{ textAlign: 'left' }}>{perm.user_or_role}</td>
                    <td style={{ textAlign: 'left' }}>{perm.permission_name}</td>
                    <td style={{ textAlign: 'left' }}>
                      <Badge variant={perm.permission_state === 'GRANT' ? 'success' : perm.permission_state === 'DENY' ? 'error' : 'warning'}>
                        {perm.permission_state}
                      </Badge>
                    </td>
                    <td style={{ textAlign: 'left' }}>{perm.grantor}</td>
                    <td style={{ textAlign: 'left' }}>
                      {perm.is_grantable ? (
                        <Badge variant="success">Yes</Badge>
                      ) : (
                        <Badge variant="default">No</Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Roles Tab */}
      {activeSubTab === 'roles' && (
        <div className="table-container">
          {roles.length === 0 ? (
            <div className="empty-state">
              <Shield size={48} />
              <p>No roles found</p>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ textAlign: 'left' }}>Role Name</th>
                  <th style={{ textAlign: 'left' }}>Category</th>
                  <th style={{ textAlign: 'left' }}>Type</th>
                  <th style={{ textAlign: 'left' }}>Members</th>
                  <th style={{ textAlign: 'left' }}>Description</th>
                </tr>
              </thead>
              <tbody>
                {roles.map((role, idx) => (
                  <tr key={idx}>
                    <td style={{ textAlign: 'left' }}>{role.role_name}</td>
                    <td style={{ textAlign: 'left' }}>
                      <Badge variant={role.role_category === 'Fixed Role' ? 'default' : 'info'}>
                        {role.role_category}
                      </Badge>
                    </td>
                    <td style={{ textAlign: 'left' }}>
                      <Badge variant={role.is_fixed_role ? 'warning' : 'success'}>
                        {role.is_fixed_role ? 'Fixed' : 'Custom'}
                      </Badge>
                    </td>
                    <td style={{ textAlign: 'left' }}>{role.members_count}</td>
                    <td style={{ textAlign: 'left' }}>{role.description || 'No description'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Schemas Tab */}
      {activeSubTab === 'schemas' && (
        <div className="table-container">
          {schemas.length === 0 ? (
            <div className="empty-state">
              <Database size={48} />
              <p>No schemas found</p>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ textAlign: 'left' }}>Schema Name</th>
                  <th style={{ textAlign: 'left' }}>Owner</th>
                  <th style={{ textAlign: 'left' }}>Owner Type</th>
                  <th style={{ textAlign: 'left' }}>Created Date</th>
                </tr>
              </thead>
              <tbody>
                {schemas.map((schema, idx) => (
                  <tr key={idx}>
                    <td style={{ textAlign: 'left' }}>{schema.schema_name}</td>
                    <td style={{ textAlign: 'left' }}>{schema.owner_name}</td>
                    <td style={{ textAlign: 'left' }}>
                      <Badge variant="default">{schema.owner_type}</Badge>
                    </td>
                    <td style={{ textAlign: 'left' }} className="timestamp-value">
                      {formatDate(schema.created_date)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Security Policies Tab */}
      {activeSubTab === 'policies' && (
        <div className="table-container">
          {policies.length === 0 ? (
            <div className="empty-state">
              <FileText size={48} />
              <p>No security policies found</p>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ textAlign: 'left' }}>Policy Name</th>
                  <th style={{ textAlign: 'left' }}>Type</th>
                  <th style={{ textAlign: 'left' }}>Schema</th>
                  <th style={{ textAlign: 'left' }}>Table</th>
                  <th style={{ textAlign: 'left' }}>Filter Predicate</th>
                  <th style={{ textAlign: 'left' }}>Status</th>
                  <th style={{ textAlign: 'left' }}>Created Date</th>
                </tr>
              </thead>
              <tbody>
                {policies.map((policy, idx) => (
                  <tr key={idx}>
                    <td style={{ textAlign: 'left' }}>{policy.policy_name}</td>
                    <td style={{ textAlign: 'left' }}>
                      <Badge variant={policy.policy_type === 'SECURITY' ? 'warning' : 'info'}>
                        {policy.policy_type}
                      </Badge>
                    </td>
                    <td style={{ textAlign: 'left' }}>{policy.table_schema}</td>
                    <td style={{ textAlign: 'left' }}>{policy.table_name}</td>
                    <td style={{ textAlign: 'left', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={policy.filter_predicate}>
                      {policy.filter_predicate}
                    </td>
                    <td style={{ textAlign: 'left' }}>
                      <Badge variant={policy.is_enabled ? 'success' : 'error'}>
                        {policy.is_enabled ? 'Enabled' : 'Disabled'}
                      </Badge>
                    </td>
                    <td style={{ textAlign: 'left' }} className="timestamp-value">
                      {formatDate(policy.created_date)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Logins Tab */}
      {activeSubTab === 'logins' && (
        <div className="table-container">
          {logins.length === 0 ? (
            <div className="empty-state">
              <UserCheck size={48} />
              <p>No logins found</p>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ textAlign: 'left' }}>Login Name</th>
                  <th style={{ textAlign: 'left' }}>Type</th>
                  <th style={{ textAlign: 'left' }}>Status</th>
                  <th style={{ textAlign: 'left' }}>Password Policy</th>
                  <th style={{ textAlign: 'left' }}>Failed Attempts</th>
                  <th style={{ textAlign: 'left' }}>Server Roles</th>
                  <th style={{ textAlign: 'left' }}>Last Login</th>
                </tr>
              </thead>
              <tbody>
                {logins.map((login, idx) => (
                  <tr key={idx}>
                    <td style={{ textAlign: 'left' }}>{login.login_name}</td>
                    <td style={{ textAlign: 'left' }}>
                      <Badge variant={login.login_type === 'WINDOWS_LOGIN' ? 'info' : 'default'}>
                        {login.login_type}
                      </Badge>
                    </td>
                    <td style={{ textAlign: 'left' }}>
                      {login.is_disabled ? (
                        <Badge variant="error">Disabled</Badge>
                      ) : login.is_locked ? (
                        <Badge variant="warning">Locked</Badge>
                      ) : (
                        <Badge variant="success">Active</Badge>
                      )}
                    </td>
                    <td style={{ textAlign: 'left' }}>
                      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                        {login.password_policy_enforced && (
                          <Badge variant="success">Policy</Badge>
                        )}
                        {login.password_expiration_enforced && (
                          <Badge variant="warning">Expiry</Badge>
                        )}
                      </div>
                    </td>
                    <td style={{ textAlign: 'left' }}>
                      <Badge variant={login.failed_login_attempts > 0 ? 'error' : 'success'}>
                        {login.failed_login_attempts}
                      </Badge>
                    </td>
                    <td style={{ textAlign: 'left' }}>
                      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                        {login.server_roles.map((role, roleIdx) => (
                          <Badge key={roleIdx} variant="info">
                            {role}
                          </Badge>
                        ))}
                      </div>
                    </td>
                    <td style={{ textAlign: 'left' }} className="timestamp-value">
                      {formatDate(login.last_successful_login)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Encryption Tab */}
      {activeSubTab === 'encryption' && (
        <div className="table-container">
          {encryption.length === 0 ? (
            <div className="empty-state">
              <Key size={48} />
              <p>No encryption information found</p>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ textAlign: 'left' }}>Encryption Type</th>
                  <th style={{ textAlign: 'left' }}>Key Name</th>
                  <th style={{ textAlign: 'left' }}>Algorithm</th>
                  <th style={{ textAlign: 'left' }}>Key Length</th>
                  <th style={{ textAlign: 'left' }}>Encrypted Objects</th>
                  <th style={{ textAlign: 'left' }}>Created Date</th>
                </tr>
              </thead>
              <tbody>
                {encryption.map((enc, idx) => (
                  <tr key={idx}>
                    <td style={{ textAlign: 'left' }}>
                      <Badge variant="warning">{enc.encryption_type}</Badge>
                    </td>
                    <td style={{ textAlign: 'left' }}>{enc.key_name}</td>
                    <td style={{ textAlign: 'left' }}>
                      <Badge variant="info">{enc.algorithm}</Badge>
                    </td>
                    <td style={{ textAlign: 'left' }}>{enc.key_length} bits</td>
                    <td style={{ textAlign: 'left' }}>
                      <Badge variant="default">{enc.encrypted_objects_count}</Badge>
                    </td>
                    <td style={{ textAlign: 'left' }} className="timestamp-value">
                      {formatDate(enc.created_date)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Linked Servers Tab */}
      {activeSubTab === 'linkedServers' && (
        <div className="table-container">
          {linkedServers.length === 0 ? (
            <div className="empty-state">
              <Link2 size={48} />
              <p>No linked servers found</p>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ textAlign: 'left' }}>Server Name</th>
                  <th style={{ textAlign: 'left' }}>Product</th>
                  <th style={{ textAlign: 'left' }}>Provider</th>
                  <th style={{ textAlign: 'left' }}>Data Source</th>
                  <th style={{ textAlign: 'left' }}>Default Catalog</th>
                  <th style={{ textAlign: 'left' }}>Remote Login</th>
                  <th style={{ textAlign: 'left' }}>RPC Out</th>
                  <th style={{ textAlign: 'left' }}>Data Access</th>
                  <th style={{ textAlign: 'left' }}>Mapped Logins</th>
                  <th style={{ textAlign: 'left' }}>Modified Date</th>
                </tr>
              </thead>
              <tbody>
                {linkedServers.map((ls, idx) => (
                  <tr key={idx}>
                    <td style={{ textAlign: 'left' }}>{ls.server_name}</td>
                    <td style={{ textAlign: 'left' }}>{ls.product || '-'}</td>
                    <td style={{ textAlign: 'left' }}>
                      <Badge variant="default">{ls.provider_name || '-'}</Badge>
                    </td>
                    <td style={{ textAlign: 'left' }}>{ls.data_source || '-'}</td>
                    <td style={{ textAlign: 'left' }}>{ls.default_catalog || '-'}</td>
                    <td style={{ textAlign: 'left' }}>
                      <Badge variant={ls.is_remote_login_enabled ? 'success' : 'default'}>
                        {ls.is_remote_login_enabled ? 'Enabled' : 'Disabled'}
                      </Badge>
                    </td>
                    <td style={{ textAlign: 'left' }}>
                      <Badge variant={ls.is_rpc_out_enabled ? 'success' : 'default'}>
                        {ls.is_rpc_out_enabled ? 'Enabled' : 'Disabled'}
                      </Badge>
                    </td>
                    <td style={{ textAlign: 'left' }}>
                      <Badge variant={ls.is_data_access_enabled ? 'success' : 'default'}>
                        {ls.is_data_access_enabled ? 'Enabled' : 'Disabled'}
                      </Badge>
                    </td>
                    <td style={{ textAlign: 'left' }}>{ls.mapped_logins || '-'}</td>
                    <td style={{ textAlign: 'left' }} className="timestamp-value">
                      {formatDate(ls.modified_date)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
};
