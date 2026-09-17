import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Card } from './Card';

describe('Card', () => {
  it('renders children', () => {
    render(<Card><p>Card content</p></Card>);
    expect(screen.getByText(/card content/i)).toBeInTheDocument();
  });

  it('renders as a div element', () => {
    render(<Card>Content</Card>);
    const card = screen.getByText('Content').parentElement;
    expect(card?.tagName).toBe('DIV');
  });

  it('applies custom style prop', () => {
    render(<Card style={{ backgroundColor: 'red' }}>Content</Card>);
    const card = screen.getByText('Content').closest('div');
    expect(card).not.toBeNull();
    expect(card?.style.backgroundColor).toBe('red');
  });
});
