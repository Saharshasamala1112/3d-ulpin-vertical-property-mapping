import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Input } from './Input';

describe('Input', () => {
  it('renders with label', () => {
    render(<Input label="Email" />);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
  });

  it('renders without label', () => {
    render(<Input placeholder="Type here" />);
    expect(screen.getByPlaceholderText(/type here/i)).toBeInTheDocument();
  });

  it('shows error message', () => {
    render(<Input label="Email" error="Required field" />);
    expect(screen.getByText(/required field/i)).toBeInTheDocument();
  });

  it('has correct type', () => {
    render(<Input label="Password" type="password" />);
    const input = screen.getByLabelText(/password/i);
    expect(input).toHaveAttribute('type', 'password');
  });

  it('forwards ref', () => {
    const ref = { current: null };
    render(<Input ref={ref} label="Test" />);
    expect(ref.current).toBeInstanceOf(HTMLInputElement);
  });
});
