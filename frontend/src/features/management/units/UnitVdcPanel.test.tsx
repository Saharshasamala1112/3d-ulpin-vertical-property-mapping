import { describe, it, expect, beforeEach, vi } from 'vitest';
import type { ComponentProps } from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { UnitVdcPanel } from './UnitVdcPanel';
import { ApiError } from '../../../services/api-error';
import type { UnitVdc, VdcStatus } from '../vdc/vdc-types';

vi.mock('../vdc/vdc-service', () => ({
  getUnitVdc: vi.fn(),
  generateUnitVdc: vi.fn(),
  validateVdc: vi.fn(),
}));

vi.mock('../vdc/vdc-clipboard', () => ({
  copyTextToClipboard: vi.fn(),
}));

import { generateUnitVdc, getUnitVdc, validateVdc } from '../vdc/vdc-service';
import { copyTextToClipboard } from '../vdc/vdc-clipboard';

const mockGet = vi.mocked(getUnitVdc);
const mockGenerate = vi.mocked(generateUnitVdc);
const mockValidate = vi.mocked(validateVdc);
const mockCopy = vi.mocked(copyTextToClipboard);

function unitVdc(overrides: Partial<UnitVdc> = {}): UnitVdc {
  return {
    unit_id: 'u-1',
    vdc_code: 'GEOSX00001-A-G-1-ZY',
    status: 'present',
    ulpin: 'GEOSX00001',
    domain: 'A',
    level: 'G',
    unit: '1',
    checksum: 'ZY',
    ...overrides,
  };
}

function missing(): UnitVdc {
  return {
    unit_id: 'u-1',
    vdc_code: null,
    status: 'missing',
    ulpin: null,
    domain: null,
    level: null,
    unit: null,
    checksum: null,
  };
}

async function renderPanel(props: Partial<ComponentProps<typeof UnitVdcPanel>> = {}) {
  render(<UnitVdcPanel unitId="u-1" {...props} />);
  // Wait for the initial read to settle so assertions are not racing it.
  await waitFor(() => expect(mockGet).toHaveBeenCalled());
}

describe('UnitVdcPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockResolvedValue(unitVdc());
    mockCopy.mockResolvedValue('copied');
  });

  it('reads the unit VDC sub-resource on mount', async () => {
    await renderPanel();
    expect(mockGet).toHaveBeenCalledWith('u-1');
    expect(await screen.findByTestId('unit-vdc-code')).toHaveTextContent('GEOSX00001-A-G-1-ZY');
  });

  it('shows a loading state while the read is in flight', async () => {
    let release: (value: UnitVdc) => void = () => {};
    mockGet.mockReturnValueOnce(
      new Promise<UnitVdc>((resolve) => {
        release = resolve;
      }),
    );

    render(<UnitVdcPanel unitId="u-1" />);
    expect(screen.queryByRole('button', { name: 'Copy' })).toBeNull();

    release(unitVdc());
    expect(await screen.findByRole('button', { name: 'Copy' })).toBeTruthy();
  });

  it('renders the parsed segments the backend returned', async () => {
    await renderPanel();
    for (const [segment, value] of Object.entries({
      ulpin: 'GEOSX00001',
      domain: 'A',
      level: 'G',
      unit: '1',
      checksum: 'ZY',
    })) {
      expect(screen.getByTestId(`unit-vdc-segment-${segment}`)).toHaveTextContent(value);
    }
  });

  it.each([
    ['present', 'Present'],
    ['missing', 'Missing'],
    ['stale', 'Stale'],
    ['invalid', 'Invalid'],
  ] as Array<[VdcStatus, string]>)('renders the %s status', async (status, label) => {
    mockGet.mockResolvedValueOnce(unitVdc({ status }));
    await renderPanel();
    expect(await screen.findByText(label)).toBeTruthy();
  });

  it('offers Generate and hides Copy/Verify when no code is stored', async () => {
    mockGet.mockResolvedValueOnce(missing());
    await renderPanel();

    expect(await screen.findByRole('button', { name: 'Generate' })).toBeTruthy();
    expect(screen.getByTestId('unit-vdc-code')).toHaveTextContent('No VDC code');
    expect(screen.getByRole('button', { name: 'Copy' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Verify' })).toBeDisabled();
  });

  it('generates without confirmation when the unit has no code', async () => {
    mockGet.mockResolvedValueOnce(missing());
    mockGenerate.mockResolvedValueOnce(unitVdc());
    await renderPanel();

    fireEvent.click(await screen.findByRole('button', { name: 'Generate' }));

    await waitFor(() => expect(mockGenerate).toHaveBeenCalledWith('u-1'));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(await screen.findByText('VDC generated.')).toBeTruthy();
  });

  it('displays the newly generated code and its segments', async () => {
    mockGet.mockResolvedValueOnce(missing());
    mockGenerate.mockResolvedValueOnce(unitVdc());
    await renderPanel();

    fireEvent.click(await screen.findByRole('button', { name: 'Generate' }));

    expect(await screen.findByTestId('unit-vdc-code')).toHaveTextContent('GEOSX00001-A-G-1-ZY');
    expect(screen.getByTestId('unit-vdc-segment-checksum')).toHaveTextContent('ZY');
  });

  it('notifies the parent so the list can refresh vdc_status', async () => {
    mockGet.mockResolvedValueOnce(missing());
    mockGenerate.mockResolvedValueOnce(unitVdc());
    const onChanged = vi.fn();
    await renderPanel({ onChanged });

    fireEvent.click(await screen.findByRole('button', { name: 'Generate' }));

    await waitFor(() => expect(onChanged).toHaveBeenCalledWith(unitVdc()));
  });

  it('surfaces a generation failure as an error banner', async () => {
    mockGet.mockResolvedValueOnce(missing());
    mockGenerate.mockRejectedValueOnce(
      new ApiError({
        status: 422,
        errorCode: 'VALIDATION_ERROR',
        message: 'Unit hierarchy does not produce a valid VDC',
      }),
    );
    await renderPanel();

    fireEvent.click(await screen.findByRole('button', { name: 'Generate' }));

    expect(await screen.findByTestId('error-banner-message')).toBeTruthy();
  });

  it('confirms before regenerating, and does not call the API first', async () => {
    await renderPanel();

    fireEvent.click(await screen.findByRole('button', { name: 'Regenerate' }));

    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveTextContent(/Regenerate VDC\?/);
    expect(mockGenerate).not.toHaveBeenCalled();
  });

  it('regenerates once the confirmation is accepted', async () => {
    mockGenerate.mockResolvedValueOnce(unitVdc());
    await renderPanel();

    fireEvent.click(await screen.findByRole('button', { name: 'Regenerate' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Regenerate' }));

    await waitFor(() => expect(mockGenerate).toHaveBeenCalledWith('u-1'));
  });

  it('cancels regeneration without calling the API', async () => {
    await renderPanel();

    fireEvent.click(await screen.findByRole('button', { name: 'Regenerate' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(mockGenerate).not.toHaveBeenCalled();
  });

  it('verifies the stored code and confirms the checksum', async () => {
    mockValidate.mockResolvedValueOnce({ valid: true, errors: [] });
    await renderPanel();

    fireEvent.click(await screen.findByRole('button', { name: 'Verify' }));

    expect(await screen.findByText('Checksum verified.')).toBeTruthy();
    expect(mockValidate).toHaveBeenCalledWith('GEOSX00001-A-G-1-ZY');
  });

  it('lists the segment failures when verification reports an invalid code', async () => {
    mockValidate.mockResolvedValueOnce({
      valid: false,
      errors: [{ segment: 'checksum', code: 'checksum_mismatch', message: 'Checksum mismatch' }],
    });
    await renderPanel();

    fireEvent.click(await screen.findByRole('button', { name: 'Verify' }));

    const errors = await screen.findByLabelText('VDC validation errors');
    expect(errors.textContent).toContain('Checksum mismatch');
    expect(errors.textContent).toContain('checksum_mismatch');
  });

  it('reads structured errors off a rejected verify request', async () => {
    mockValidate.mockRejectedValueOnce(
      new ApiError({
        status: 422,
        errorCode: 'VALIDATION_ERROR',
        message: 'Request validation failed',
        details: {
          vdc_errors: [{ segment: 'domain', code: 'invalid_domain', message: 'Domain must be A-D' }],
        },
      }),
    );
    await renderPanel();

    fireEvent.click(await screen.findByRole('button', { name: 'Verify' }));

    const errors = await screen.findByLabelText('VDC validation errors');
    expect(errors.textContent).toContain('Invalid domain');
  });

  it('copies the stored code and confirms it', async () => {
    await renderPanel();

    fireEvent.click(await screen.findByRole('button', { name: 'Copy' }));

    expect(await screen.findByText('Copied to clipboard.')).toBeTruthy();
    expect(mockCopy).toHaveBeenCalledWith('GEOSX00001-A-G-1-ZY');
  });

  it('confirms the copy when only the fallback path worked', async () => {
    mockCopy.mockResolvedValue('fallback-copied');
    await renderPanel();

    fireEvent.click(await screen.findByRole('button', { name: 'Copy' }));

    expect(await screen.findByText('Copied to clipboard.')).toBeTruthy();
  });

  it('asks the user to copy manually when copying is impossible', async () => {
    mockCopy.mockResolvedValue('failed');
    await renderPanel();

    fireEvent.click(await screen.findByRole('button', { name: 'Copy' }));

    expect(await screen.findByText(/copy it manually/i)).toBeTruthy();
  });

  it('hides the generating actions from a viewer without edit permission', async () => {
    await renderPanel({ canEdit: false });

    expect(await screen.findByRole('button', { name: 'Copy' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Regenerate' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Generate' })).toBeNull();
  });

  it('surfaces a read failure as an error banner', async () => {
    mockGet.mockRejectedValueOnce(
      new ApiError({ status: 404, errorCode: 'NOT_FOUND', message: 'Unit not found' }),
    );

    render(<UnitVdcPanel unitId="nope" />);

    expect(await screen.findByTestId('error-banner-message')).toBeTruthy();
  });
});
