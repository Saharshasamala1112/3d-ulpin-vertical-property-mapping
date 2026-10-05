import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { authService } from '../../services/auth-service';
import { ForgotPasswordPage } from './ForgotPasswordPage';

vi.mock('../../services/auth-service', () => ({
  authService: {
    requestPasswordReset: vi.fn(),
  },
}));

describe('ForgotPasswordPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('sends the requested email to the API and shows the generic confirmation', async () => {
    vi.mocked(authService.requestPasswordReset).mockResolvedValue({
      message: 'If the email exists, a reset link has been sent',
    });

    render(
      <MemoryRouter>
        <ForgotPasswordPage />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText('Email'), {
      target: { value: 'person@example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send Reset Link' }));

    await waitFor(() => {
      expect(authService.requestPasswordReset).toHaveBeenCalledWith('person@example.com');
    });
    expect(
      await screen.findByText('If an account with that email exists, a reset link has been sent.')
    ).toBeInTheDocument();
  });

  it('shows API failures and permits retrying', async () => {
    vi.mocked(authService.requestPasswordReset).mockRejectedValueOnce(new Error('Service unavailable'));

    render(
      <MemoryRouter>
        <ForgotPasswordPage />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText('Email'), {
      target: { value: 'person@example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send Reset Link' }));

    expect(await screen.findByText('Service unavailable')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Send Reset Link' })).toBeEnabled();
  });
});
