import { type SelectHTMLAttributes, forwardRef } from 'react';

export interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'children'> {
  label?: string;
  error?: string;
  options: SelectOption[];
  placeholder?: string;
  loading?: boolean;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, options, placeholder, loading, style, id, disabled, ...props }, ref) => {
    const selectId = id || label?.toLowerCase().replace(/\s+/g, '-');
    const showPlaceholder = Boolean(placeholder) || loading || options.length === 0;
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
        {label && (
          <label
            htmlFor={selectId}
            style={{ fontSize: '0.8125rem', fontWeight: 500, color: 'var(--foreground)' }}
          >
            {label}
          </label>
        )}
        <select
          ref={ref}
          id={selectId}
          disabled={disabled || loading}
          style={{
            padding: '0.5rem 0.75rem',
            borderRadius: '6px',
            border: `1px solid ${error ? 'var(--danger)' : 'var(--input-border)'}`,
            background: 'var(--input-bg)',
            color: 'var(--foreground)',
            fontSize: '0.875rem',
            outline: 'none',
            width: '100%',
            ...style,
          }}
          {...props}
        >
          {showPlaceholder && (
            <option value="">
              {loading ? 'Loading…' : placeholder || 'No options available'}
            </option>
          )}
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        {error && <span style={{ fontSize: '0.75rem', color: 'var(--danger)' }}>{error}</span>}
      </div>
    );
  }
);

Select.displayName = 'Select';
