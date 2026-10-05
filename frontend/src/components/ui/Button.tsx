import { type ButtonHTMLAttributes, forwardRef } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
}

const styles: Record<string, React.CSSProperties> = {
  base: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '0.5rem',
    borderRadius: '6px',
    fontWeight: 500,
    border: '1px solid transparent',
    transition: 'all 150ms ease',
    whiteSpace: 'nowrap',
  },
  primary: {
    background: 'var(--primary)',
    color: 'var(--primary-foreground)',
  },
  secondary: {
    background: 'var(--surface-muted)',
    color: 'var(--foreground)',
    borderColor: 'var(--border)',
  },
  danger: {
    background: 'var(--danger)',
    color: '#ffffff',
  },
  ghost: {
    background: 'transparent',
    color: 'var(--foreground)',
  },
  sm: { padding: '0.375rem 0.75rem', fontSize: '0.8125rem' },
  md: { padding: '0.5rem 1rem', fontSize: '0.875rem' },
  lg: { padding: '0.625rem 1.25rem', fontSize: '0.9375rem' },
  disabled: { opacity: 0.5, cursor: 'not-allowed' },
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', loading, disabled, style, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        style={{
          ...styles.base,
          ...styles[variant],
          ...styles[size],
          ...(disabled || loading ? styles.disabled : {}),
          ...style,
        }}
        {...props}
      >
        {loading && (
          <span
            style={{
              width: '1em',
              height: '1em',
              border: '2px solid currentColor',
              borderTopColor: 'transparent',
              borderRadius: '50%',
              animation: 'spin 0.6s linear infinite',
            }}
          />
        )}
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';
