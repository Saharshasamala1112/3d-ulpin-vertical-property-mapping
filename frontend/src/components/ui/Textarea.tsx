import { type TextareaHTMLAttributes, forwardRef } from 'react';

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  /** Optional helper text rendered under the control. */
  hint?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, error, hint, style, id, ...props }, ref) => {
    const textareaId = id || label?.toLowerCase().replace(/\s+/g, '-');
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
        {label && (
          <label
            htmlFor={textareaId}
            style={{ fontSize: '0.8125rem', fontWeight: 500, color: 'var(--foreground)' }}
          >
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          id={textareaId}
          style={{
            padding: '0.5rem 0.75rem',
            borderRadius: '6px',
            border: `1px solid ${error ? 'var(--danger)' : 'var(--input-border)'}`,
            background: 'var(--input-bg)',
            color: 'var(--foreground)',
            fontSize: '0.875rem',
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
            outline: 'none',
            width: '100%',
            minHeight: '8rem',
            resize: 'vertical',
            ...style,
          }}
          {...props}
        />
        {hint && !error && (
          <span style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>{hint}</span>
        )}
        {error && <span style={{ fontSize: '0.75rem', color: 'var(--danger)' }}>{error}</span>}
      </div>
    );
  }
);

Textarea.displayName = 'Textarea';
