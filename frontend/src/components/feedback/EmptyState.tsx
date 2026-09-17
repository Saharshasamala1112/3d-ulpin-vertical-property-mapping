import type { ReactNode } from 'react';

interface EmptyStateProps {
  icon?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '3rem 1.5rem',
        textAlign: 'center',
      }}
    >
      {icon && (
        <div style={{ fontSize: '2rem', marginBottom: '1rem', opacity: 0.5 }}>{icon}</div>
      )}
      <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.5rem' }}>{title}</h3>
      {description && (
        <p style={{ fontSize: '0.875rem', color: 'var(--muted)', maxWidth: '320px', marginBottom: '1rem' }}>
          {description}
        </p>
      )}
      {action}
    </div>
  );
}
