import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Dialog } from './Dialog';

describe('Dialog', () => {
  it('renders its title and children when open', () => {
    render(
      <Dialog open title="Edit parcel" onClose={vi.fn()}>
        <p>Form body</p>
      </Dialog>
    );

    expect(screen.getByText('Edit parcel')).toBeInTheDocument();
    expect(screen.getByText('Form body')).toBeInTheDocument();
  });

  it('marks the native element as open via the test polyfill', () => {
    const { container } = render(
      <Dialog open title="Open" onClose={vi.fn()}>
        <p>Body</p>
      </Dialog>
    );

    expect(container.querySelector('dialog')?.open).toBe(true);
  });

  it('invokes onClose when the close button is pressed', () => {
    const onClose = vi.fn();
    render(
      <Dialog open title="Closable" onClose={onClose}>
        <p>Body</p>
      </Dialog>
    );

    fireEvent.click(screen.getByLabelText('Close dialog'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
