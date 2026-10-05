import type { ReactNode } from 'react';

type AlertVariant = 'error' | 'warning' | 'info' | 'success';

interface AlertProps {
  variant?: AlertVariant;
  title?: string;
  children?: ReactNode;
  onDismiss?: () => void;
}

const variantStyles: Record<AlertVariant, { background: string; color: string; border: string }> = {
  error: { background: 'var(--danger-bg)', color: 'var(--danger)', border: 'var(--danger)' },
  warning: { background: 'var(--warning-bg)', color: 'var(--warning)', border: 'var(--warning)' },
  info: { background: 'var(--surface-muted)', color: 'var(--foreground)', border: 'var(--border)' },
  success: { background: 'var(--success-bg)', color: 'var(--success)', border: 'var(--success)' },
};

/**
 * Inline banner for list-level and form-level feedback.
 *
 * Used both for Feature 12 error envelopes (see `ErrorBanner`) and for
 * non-error notices such as the archive semantics of a parcel/unit delete.
 */
export function Alert({ variant = 'error', title, children, onDismiss }: AlertProps) {
  const tone = variantStyles[variant];
  return (
    <div
      role={variant === 'error' ? 'alert' : 'status'}
      style={{
        background: tone.background,
        color: tone.color,
        border: `1px solid ${tone.border}`,
        borderRadius: '6px',
        padding: '0.75rem 1rem',
        fontSize: '0.8125rem',
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        gap: '0.75rem',
      }}
    >
      <div>
        {title && <div style={{ fontWeight: 600, marginBottom: children ? '0.25rem' : 0 }}>{title}</div>}
        {children}
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss"
          style={{
            background: 'none',
            border: 'none',
            color: 'inherit',
            cursor: 'pointer',
            fontSize: '1rem',
            lineHeight: 1,
            padding: '0.125rem',
          }}
        >
          &times;
        </button>
      )}
    </div>
  );
}
