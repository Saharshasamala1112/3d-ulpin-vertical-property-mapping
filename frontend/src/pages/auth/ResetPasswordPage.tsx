import { useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Alert } from '../../components/ui/Alert';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { toApiError } from '../../services/api-error';
import { authService } from '../../services/auth-service';

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token')?.trim() ?? '';
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    try {
      await authService.resetPassword({ token, new_password: password });
      setSubmitted(true);
    } catch (failure) {
      setError(toApiError(failure).displayMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--background)',
        padding: '1rem',
      }}
    >
      <div style={{ width: '100%', maxWidth: '400px' }}>
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, letterSpacing: '-0.02em' }}>GEOSIX</h1>
          <p style={{ fontSize: '0.875rem', color: 'var(--muted)', marginTop: '0.25rem' }}>
            Choose a new password
          </p>
        </div>

        {submitted ? (
          <div style={{ textAlign: 'center' }}>
            <Alert variant="success">Your password has been reset.</Alert>
            <Link to="/login" style={{ display: 'inline-block', marginTop: '1.5rem' }}>
              Sign in
            </Link>
          </div>
        ) : !token ? (
          <div style={{ textAlign: 'center' }}>
            <Alert>The password reset link is missing its token.</Alert>
            <Link to="/forgot-password" style={{ display: 'inline-block', marginTop: '1.5rem' }}>
              Request a new reset link
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {error && <Alert>{error}</Alert>}
              <Input
                label="New password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="new-password"
                minLength={8}
                required
              />
              <Input
                label="Confirm new password"
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                autoComplete="new-password"
                minLength={8}
                required
              />
              <Button type="submit" loading={loading} style={{ width: '100%' }}>
                Reset Password
              </Button>
            </div>
          </form>
        )}

        <div style={{ textAlign: 'center', marginTop: '1.5rem', fontSize: '0.8125rem' }}>
          <Link to="/login">Back to sign in</Link>
        </div>
      </div>
    </div>
  );
}
