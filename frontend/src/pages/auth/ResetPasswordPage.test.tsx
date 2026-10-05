import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { authService } from '../../services/auth-service';
import { ResetPasswordPage } from './ResetPasswordPage';

vi.mock('../../services/auth-service', () => ({
  authService: {
    resetPassword: vi.fn(),
  },
}));

function renderPage(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ResetPasswordPage />
    </MemoryRouter>
  );
}

describe('ResetPasswordPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('asks for a new token when the link has none', () => {
    renderPage('/reset-password');

    expect(screen.getByText('The password reset link is missing its token.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Request a new reset link' })).toHaveAttribute(
      'href',
      '/forgot-password'
    );
  });

  it('checks matching passwords and submits the reset token to the API', async () => {
    vi.mocked(authService.resetPassword).mockResolvedValue({
      message: 'Password has been reset successfully',
    });
    renderPage('/reset-password?token=reset-token');

    fireEvent.change(screen.getByLabelText('New password'), {
      target: { value: 'a-new-password' },
    });
    fireEvent.change(screen.getByLabelText('Confirm new password'), {
      target: { value: 'different-password' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Reset Password' }));

    expect(await screen.findByText('Passwords do not match.')).toBeInTheDocument();
    expect(authService.resetPassword).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText('Confirm new password'), {
      target: { value: 'a-new-password' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Reset Password' }));

    await waitFor(() => {
      expect(authService.resetPassword).toHaveBeenCalledWith({
        token: 'reset-token',
        new_password: 'a-new-password',
      });
    });
    expect(await screen.findByText('Your password has been reset.')).toBeInTheDocument();
  });
});
