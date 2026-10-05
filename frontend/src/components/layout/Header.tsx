import { useAuth } from '../../app/AuthContext';
import { useTheme } from '../../app/ThemeContext';

export function Header() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();

  return (
    <header
      style={{
        height: '56px',
        background: 'var(--surface)',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'flex-end',
        padding: '0 1.5rem',
        gap: '1rem',
        flexShrink: 0,
      }}
    >
      {/* Theme toggle */}
      <button
        onClick={toggleTheme}
        aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
        style={{
          background: 'var(--surface-muted)',
          border: '1px solid var(--border)',
          borderRadius: '6px',
          padding: '0.375rem 0.625rem',
          color: 'var(--foreground)',
          cursor: 'pointer',
          fontSize: '0.875rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.375rem',
        }}
      >
        {theme === 'light' ? '◼' : '◻'}
        <span style={{ fontSize: '0.8125rem' }}>{theme === 'light' ? 'Dark' : 'Light'}</span>
      </button>

      {/* User menu */}
      {user && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '50%',
              background: 'var(--primary)',
              color: 'var(--primary-foreground)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '0.8125rem',
              fontWeight: 600,
            }}
          >
            {user.full_name.charAt(0).toUpperCase()}
          </div>
          <span style={{ fontSize: '0.8125rem', color: 'var(--foreground)' }}>
            {user.full_name}
          </span>
          <button
            onClick={logout}
            style={{
              background: 'none',
              border: '1px solid var(--border)',
              borderRadius: '6px',
              padding: '0.375rem 0.75rem',
              color: 'var(--muted)',
              cursor: 'pointer',
              fontSize: '0.8125rem',
            }}
          >
            Logout
          </button>
        </div>
      )}
    </header>
  );
}
