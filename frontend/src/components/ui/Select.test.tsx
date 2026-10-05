import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Select } from './Select';

const options = [
  { value: 'a', label: 'Alpha' },
  { value: 'b', label: 'Beta' },
];

describe('Select', () => {
  it('renders a labelled control with options', () => {
    render(<Select label="Building" options={options} value="" onChange={() => {}} />);
    const select = screen.getByLabelText('Building');
    expect(select).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Alpha' })).toBeInTheDocument();
  });

  it('shows a placeholder option when provided', () => {
    render(
      <Select label="Parcel" placeholder="Select a parcel" options={options} value="" onChange={() => {}} />
    );
    expect(screen.getByRole('option', { name: 'Select a parcel' })).toBeInTheDocument();
  });

  it('shows a loading state that disables the control', () => {
    render(<Select label="Floors" options={[]} loading value="" onChange={() => {}} />);
    const select = screen.getByLabelText('Floors') as HTMLSelectElement;
    expect(select).toBeDisabled();
    expect(screen.getByRole('option', { name: 'Loading…' })).toBeInTheDocument();
  });

  it('reports changes through onChange', () => {
    const onChange = vi.fn();
    render(<Select label="Building" options={options} value="" onChange={onChange} />);
    fireEvent.change(screen.getByLabelText('Building'), { target: { value: 'b' } });
    expect(onChange).toHaveBeenCalled();
  });

  it('renders an error message', () => {
    render(
      <Select label="Unit" options={[]} error="Units failed to load" value="" onChange={() => {}} />
    );
    expect(screen.getByText('Units failed to load')).toBeInTheDocument();
  });
});
