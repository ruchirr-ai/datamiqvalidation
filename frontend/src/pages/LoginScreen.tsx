import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Card } from '../components/ui/Card';
import { Alert } from '../components/ui/Alert';
import { Logo } from '../components/ui/Logo';
import './LoginScreen.css';

export const LoginScreen: React.FC = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!username || !password) {
      setError('Please enter both username and password');
      return;
    }

    setLoading(true);

    try {
      await login(username, password);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-screen">
      <div className="login-screen__container">
        <Card padding="lg" shadow="lg" className="login-screen__card">
          {/* Logo */}
          <div className="login-screen__logo">
            <Logo size={28} showText={true} animate={true} />
            <p className="login-screen__subtitle">Database Migration Platform</p>
          </div>

          {/* Error Alert */}
          {error && (
            <Alert variant="error" onClose={() => setError('')}>
              {error}
            </Alert>
          )}

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="login-screen__form">
            <Input
              label="Username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter your username"
              fullWidth
              autoComplete="username"
              disabled={loading}
            />

            <Input
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              fullWidth
              autoComplete="current-password"
              disabled={loading}
            />

            <Button
              type="submit"
              variant="primary"
              size="lg"
              fullWidth
              loading={loading}
              disabled={loading}
            >
              {loading ? 'Signing in...' : 'Sign In'}
            </Button>
          </form>

          {/* Footer */}
          <div className="login-screen__footer">
            <p className="login-screen__footer-text">
              Secure database migration platform
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
};
