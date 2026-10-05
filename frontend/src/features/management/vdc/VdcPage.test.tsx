import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { VdcPage } from './VdcPage';
import { ApiError } from '../../../services/api-error';

vi.mock('./vdc-service', () => ({
  parseVdc: vi.fn(),
  validateVdc: vi.fn(),
  generateVdc: vi.fn(),
  getUnitVdc: vi.fn(),
  generateUnitVdc: vi.fn(),
}));

vi.mock('./vdc-clipboard', () => ({
  copyTextToClipboard: vi.fn(),
}));

import { parseVdc, validateVdc } from './vdc-service';
import { copyTextToClipboard } from './vdc-clipboard';

const mockParse = vi.mocked(parseVdc);
const mockValidate = vi.mocked(validateVdc);
const mockCopy = vi.mocked(copyTextToClipboard);

const PARSED = { ulpin: 'GEOSX00001', domain: 'A', level: 'G', unit: '1', checksum: 'ZY' };

function typeAndParse(vdc: string) {
  render(<VdcPage />);
  fireEvent.change(screen.getByLabelText('VDC code'), { target: { value: vdc } });
  fireEvent.click(screen.getByRole('button', { name: 'Parse' }));
}

describe('VdcPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCopy.mockResolvedValue('copied');
  });

  it('keeps the actions disabled until a code is entered', () => {
    render(<VdcPage />);
    expect(screen.getByRole('button', { name: 'Parse' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Validate' })).toBeDisabled();
  });

  it('renders all five segments and the canonical form', async () => {
    mockParse.mockResolvedValueOnce(PARSED);
    typeAndParse('GEOSX00001-A-G-1-ZY');

    expect(await screen.findByTestId('vdc-canonical')).toHaveTextContent('GEOSX00001-A-G-1-ZY');

    for (const [segment, value] of Object.entries(PARSED)) {
      expect(screen.getByTestId(`vdc-segment-${segment}`)).toHaveTextContent(value);
    }
  });

  it('confirms a successful parse, which implies the checksum matched', async () => {
    mockParse.mockResolvedValueOnce(PARSED);
    typeAndParse('GEOSX00001-A-G-1-ZY');

    expect(await screen.findByText('Parsed successfully')).toBeTruthy();
  });

  it('shows a known validator error with its segment and code', async () => {
    mockParse.mockRejectedValueOnce(
      new ApiError({
        status: 422,
        errorCode: 'VALIDATION_ERROR',
        message: 'Request validation failed',
        details: {
          vdc_errors: [
            { segment: 'checksum', code: 'checksum_mismatch', message: 'Checksum mismatch' },
          ],
        },
      }),
    );
    typeAndParse('GEOSX00001-A-G-1-QQ');

    const errors = await screen.findByLabelText('VDC validation errors');
    expect(errors.textContent).toContain('CHECKSUM');
    expect(errors.textContent).toContain('Checksum mismatch');
    expect(errors.textContent).toContain('checksum_mismatch');
  });

  it('keeps an unknown validator code visible', async () => {
    mockParse.mockRejectedValueOnce(
      new ApiError({
        status: 422,
        errorCode: 'VALIDATION_ERROR',
        message: 'Request validation failed',
        details: {
          vdc_errors: [{ segment: 'ulpin', code: 'brand_new_check', message: 'Something new' }],
        },
      }),
    );
    typeAndParse('GEOSX00001-A-G-1-ZY');

    const errors = await screen.findByLabelText('VDC validation errors');
    expect(errors.textContent).toContain('brand_new_check');
  });

  it('falls back to the error banner when the 422 carries no structured errors', async () => {
    mockParse.mockRejectedValueOnce(
      new ApiError({ status: 500, errorCode: 'INTERNAL_ERROR', message: 'Boom' }),
    );
    typeAndParse('GEOSX00001-A-G-1-ZY');

    expect(await screen.findByTestId('error-banner-message')).toBeTruthy();
    expect(screen.queryByLabelText('VDC validation errors')).toBeNull();
  });

  it('reports a valid checksum from the validate endpoint', async () => {
    mockValidate.mockResolvedValueOnce({ valid: true, errors: [] });
    render(<VdcPage />);
    fireEvent.change(screen.getByLabelText('VDC code'), { target: { value: 'GEOSX00001-A-G-1-ZY' } });
    fireEvent.click(screen.getByRole('button', { name: 'Validate' }));

    expect(await screen.findByText('Valid VDC')).toBeTruthy();
    expect(screen.getByText(/checksum matches/i)).toBeTruthy();
  });

  it('lists the failures from an invalid VDC without treating it as a request error', async () => {
    mockValidate.mockResolvedValueOnce({
      valid: false,
      errors: [
        { segment: 'level', code: 'invalid_level', message: 'Level must be G, Fn or Bn' },
        { segment: 'unit', code: 'invalid_unit', message: 'Unit segment is malformed' },
      ],
    });
    render(<VdcPage />);
    fireEvent.change(screen.getByLabelText('VDC code'), { target: { value: 'GEOSX00001-A-X-1-ZY' } });
    fireEvent.click(screen.getByRole('button', { name: 'Validate' }));

    const errors = await screen.findByLabelText('VDC validation errors');
    expect(errors.textContent).toContain('Invalid level');
    expect(errors.textContent).toContain('Invalid unit number');
    expect(screen.queryByTestId('error-banner-message')).toBeNull();
  });

  it('copies the entered code and confirms it', async () => {
    render(<VdcPage />);
    fireEvent.change(screen.getByLabelText('VDC code'), { target: { value: 'GEOSX00001-A-G-1-ZY' } });
    fireEvent.click(screen.getByRole('button', { name: 'Copy' }));

    expect(await screen.findByText('Copied to clipboard.')).toBeTruthy();
    expect(mockCopy).toHaveBeenCalledWith('GEOSX00001-A-G-1-ZY');
  });

  it('still confirms the copy when only the fallback path worked', async () => {
    mockCopy.mockResolvedValue('fallback-copied');
    render(<VdcPage />);
    fireEvent.change(screen.getByLabelText('VDC code'), { target: { value: 'GEOSX00001-A-G-1-ZY' } });
    fireEvent.click(screen.getByRole('button', { name: 'Copy' }));

    expect(await screen.findByText('Copied to clipboard.')).toBeTruthy();
  });

  it('tells the user to copy manually when copying is impossible', async () => {
    mockCopy.mockResolvedValue('failed');
    render(<VdcPage />);
    fireEvent.change(screen.getByLabelText('VDC code'), { target: { value: 'GEOSX00001-A-G-1-ZY' } });
    fireEvent.click(screen.getByRole('button', { name: 'Copy' }));

    expect(await screen.findByText(/copy it manually/i)).toBeTruthy();
  });

  it('discards a stale result once the code is edited', async () => {
    mockParse.mockResolvedValueOnce(PARSED);
    render(<VdcPage />);
    const input = screen.getByLabelText('VDC code');
    fireEvent.change(input, { target: { value: 'GEOSX00001-A-G-1-ZY' } });
    fireEvent.click(screen.getByRole('button', { name: 'Parse' }));
    await screen.findByTestId('vdc-canonical');

    fireEvent.change(input, { target: { value: 'GEOSX00002-A-G-1-ZY' } });

    await waitFor(() => expect(screen.queryByTestId('vdc-canonical')).toBeNull());
  });
});
