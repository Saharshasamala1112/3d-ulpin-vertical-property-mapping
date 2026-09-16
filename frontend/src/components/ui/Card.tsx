import type { ReactNode } from 'react';

interface CardProps {
  children: ReactNode;
  padding?: string;
  style?: React.CSSProperties;
}

export function Card({ children, padding = '1.5rem', style }: CardProps) {
  return (
    <div
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: '8px',
        boxShadow: 'var(--shadow-sm)',
        padding,
        ...style,
      }}
    >
      {children}
    </div>
  );
}
