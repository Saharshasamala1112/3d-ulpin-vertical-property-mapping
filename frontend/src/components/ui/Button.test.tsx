import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Button } from './Button';

describe('Button', () => {
  it('renders with text', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole('button', { name: /click me/i })).toBeInTheDocument();
  });

  it('is not disabled by default', () => {
    render(<Button>Test</Button>);
    expect(screen.getByRole('button')).not.toBeDisabled();
  });

  it('is disabled when loading', () => {
    render(<Button loading>Submit</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('is disabled when disabled prop is true', () => {
    render(<Button disabled>Submit</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('renders loading spinner when loading', () => {
    render(<Button loading>Submit</Button>);
    const button = screen.getByRole('button');
    // The loading spinner is a span with animation
    expect(button.querySelector('span')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    render(<Button className="custom">Test</Button>);
    expect(screen.getByRole('button')).toHaveClass('custom');
  });

  it('renders with type submit', () => {
    render(<Button type="submit">Submit</Button>);
    expect(screen.getByRole('button')).toHaveAttribute('type', 'submit');
  });
});
