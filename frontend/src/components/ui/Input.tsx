import { type InputHTMLAttributes, forwardRef } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, style, id, ...props }, ref) => {
    const inputId = id || label?.toLowerCase().replace(/\s+/g, '-');
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
        {label && (
          <label
            htmlFor={inputId}
            style={{
              fontSize: '0.8125rem',
              fontWeight: 500,
              color: 'var(--foreground)',
            }}
          >
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          style={{
            padding: '0.5rem 0.75rem',
            borderRadius: '6px',
            border: `1px solid ${error ? 'var(--danger)' : 'var(--input-border)'}`,
            background: 'var(--input-bg)',
            color: 'var(--foreground)',
            fontSize: '0.875rem',
            outline: 'none',
            transition: 'border-color 150ms ease',
            width: '100%',
            ...style,
          }}
          onFocus={(e) => {
            e.currentTarget.style.borderColor = 'var(--input-focus)';
          }}
          onBlur={(e) => {
            e.currentTarget.style.borderColor = error ? 'var(--danger)' : 'var(--input-border)';
          }}
          {...props}
        />
        {error && (
          <span style={{ fontSize: '0.75rem', color: 'var(--danger)' }}>{error}</span>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';
