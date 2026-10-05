import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { OwnershipPage } from './OwnershipPage';

vi.mock('../../services/ownership-service', () => ({
  ownershipService: {
    listOwners: vi.fn(),
    listSubjectInterests: vi.fn(),
    listOwnerInterests: vi.fn(),
    createOwner: vi.fn(),
    grant: vi.fn(),
    transfer: vi.fn(),
    revoke: vi.fn(),
  },
}));

import { ownershipService } from '../../services/ownership-service';

const owner = {
  id: 'owner-1',
  kind: 'individual' as const,
  name: 'Asha Rao',
  identifier: null,
  contact_metadata: {},
  created_at: '2026-09-01T00:00:00Z',
  updated_at: '2026-09-01T00:00:00Z',
};

const interest = {
  id: 'interest-1',
  owner_id: owner.id,
  subject_type: 'parcel' as const,
  subject_id: 'parcel-1',
  share_basis_points: 6250,
  valid_from: '2026-09-01T00:00:00Z',
  valid_to: null,
  status: 'active' as const,
  created_at: '2026-09-01T00:00:00Z',
  updated_at: '2026-09-01T00:00:00Z',
};

const emptyList = { data: [], meta: { page: 1, per_page: 20, total: 0, total_pages: 1 } };

describe('OwnershipPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(ownershipService.listOwners).mockResolvedValue({ ...emptyList, data: [owner] });
    vi.mocked(ownershipService.listSubjectInterests).mockResolvedValue({
      ...emptyList,
      data: [interest],
    });
    vi.mocked(ownershipService.listOwnerInterests).mockResolvedValue({
      ...emptyList,
      data: [interest],
    });
  });

  it('renders the owner registration form and registered owner', async () => {
    render(<OwnershipPage />);
    expect(await screen.findByText('Asha Rao (individual)')).toBeTruthy();
    expect(screen.getByRole('form', { name: 'Register owner' })).toBeTruthy();
  });

  it('submits owner registration and shows success', async () => {
    vi.mocked(ownershipService.createOwner).mockResolvedValueOnce(owner);
    render(<OwnershipPage />);
    fireEvent.change(await screen.findByLabelText('Name'), { target: { value: 'Asha Rao' } });
    fireEvent.click(screen.getByRole('button', { name: 'Register owner' }));
    await waitFor(() => expect(ownershipService.createOwner).toHaveBeenCalledWith({
      kind: 'individual',
      name: 'Asha Rao',
      identifier: null,
      contact_metadata: {},
    }));
    expect(await screen.findByRole('status')).toBeTruthy();
  });

  it('loads and displays parcel ownership history', async () => {
    render(<OwnershipPage />);
    fireEvent.change(await screen.findByLabelText('Parcel UUID'), {
      target: { value: 'parcel-1' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Load records' }));
    expect(await screen.findByText('62.50%')).toBeTruthy();
    expect(screen.getByText('Current').textContent).toBe('Current');
    fireEvent.click(screen.getByRole('button', { name: 'Asha Rao' }));
    expect(screen.getByRole('region', { name: 'Owner profile' }).textContent).toContain('Owner UUID');
  });

  it('renders closed ownership intervals as history', async () => {
    vi.mocked(ownershipService.listSubjectInterests).mockResolvedValueOnce({
      ...emptyList,
      data: [{ ...interest, valid_to: '2026-09-20T00:00:00Z', status: 'revoked' }],
    });
    render(<OwnershipPage />);
    fireEvent.change(await screen.findByLabelText('Parcel UUID'), {
      target: { value: 'parcel-1' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Load records' }));
    expect(await screen.findByText('Historical')).toBeTruthy();
    expect(screen.getByText('revoked')).toBeTruthy();
  });

  it('supports the grant, transfer, and revoke forms', async () => {
    render(<OwnershipPage />);
    fireEvent.click(await screen.findByRole('tab', { name: 'Grant' }));
    expect(screen.getByRole('form', { name: 'Grant ownership' })).toBeTruthy();
    fireEvent.click(screen.getByRole('tab', { name: 'Transfer' }));
    expect(screen.getByRole('form', { name: 'Transfer ownership' })).toBeTruthy();
    fireEvent.click(screen.getByRole('tab', { name: 'Revoke' }));
    expect(screen.getByRole('form', { name: 'Revoke ownership' })).toBeTruthy();
  });

  it('submits a parcel grant with basis points and an effective timestamp', async () => {
    vi.mocked(ownershipService.grant).mockResolvedValueOnce(interest);
    render(<OwnershipPage />);
    fireEvent.click(await screen.findByRole('tab', { name: 'Grant' }));
    fireEvent.change(screen.getByLabelText('Owner'), { target: { value: owner.id } });
    fireEvent.change(screen.getByLabelText('Grant Parcel UUID'), {
      target: { value: 'parcel-1' },
    });
    fireEvent.change(screen.getByLabelText('Share (basis points)'), {
      target: { value: '6250' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Grant interest' }));
    await waitFor(() => expect(ownershipService.grant).toHaveBeenCalledWith(
      expect.objectContaining({
        owner_id: owner.id,
        subject_type: 'parcel',
        subject_id: 'parcel-1',
        share_basis_points: 6250,
        valid_from: expect.any(String),
      }),
    ));
  });

  it('submits a complete replacement allocation for transfer', async () => {
    vi.mocked(ownershipService.transfer).mockResolvedValueOnce({ closed: [interest], created: [interest] });
    render(<OwnershipPage />);
    fireEvent.click(await screen.findByRole('tab', { name: 'Transfer' }));
    fireEvent.change(screen.getByLabelText('Transfer Parcel UUID'), {
      target: { value: 'parcel-1' },
    });
    fireEvent.change(screen.getByLabelText('Transfer allocations'), {
      target: { value: `${owner.id},6250\nother-owner,3750` },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Record complete transfer' }));
    await waitFor(() => expect(ownershipService.transfer).toHaveBeenCalledWith(
      expect.objectContaining({
        subject_type: 'parcel',
        subject_id: 'parcel-1',
        allocations: [
          { owner_id: owner.id, share_basis_points: 6250 },
          { owner_id: 'other-owner', share_basis_points: 3750 },
        ],
      }),
    ));
    expect(await screen.findByText(/Transfer recorded/)).toBeTruthy();
  });

  it('submits a revocation and displays its success state', async () => {
    vi.mocked(ownershipService.revoke).mockResolvedValueOnce({
      ...interest,
      valid_to: '2026-09-30T12:00:00Z',
      status: 'revoked',
    });
    render(<OwnershipPage />);
    fireEvent.click(await screen.findByRole('tab', { name: 'Revoke' }));
    fireEvent.change(screen.getByLabelText('Interest UUID'), {
      target: { value: interest.id },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Revoke interest' }));
    await waitFor(() => expect(ownershipService.revoke).toHaveBeenCalledWith(
      interest.id,
      expect.any(String),
    ));
    expect(await screen.findByRole('status')).toBeTruthy();
  });

  it('renders the empty state', async () => {
    vi.mocked(ownershipService.listOwners).mockResolvedValueOnce(emptyList);
    render(<OwnershipPage />);
    expect(await screen.findByText('No ownership records')).toBeTruthy();
  });

  it('renders an API failure state', async () => {
    vi.mocked(ownershipService.listOwners).mockRejectedValueOnce({
      status: 501,
      data: { message: 'Feature 2 authorization is unavailable' },
    });
    render(<OwnershipPage />);
    expect(await screen.findByRole('alert')).toHaveProperty(
      'textContent',
      'Feature 2 authorization is unavailable',
    );
  });
});
