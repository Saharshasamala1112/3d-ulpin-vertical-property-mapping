import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { copyTextToClipboard } from './vdc-clipboard';

const originalExecCommand = document.execCommand;

/** Install (or remove) the async Clipboard API for one test. */
function setAsyncClipboard(writeText: (() => Promise<void>) | undefined) {
  Object.defineProperty(navigator, 'clipboard', {
    value: writeText ? { writeText } : undefined,
    configurable: true,
    writable: true,
  });
}

describe('copyTextToClipboard', () => {
  beforeEach(() => {
    setAsyncClipboard(undefined);
  });

  afterEach(() => {
    Object.defineProperty(document, 'execCommand', {
      value: originalExecCommand,
      configurable: true,
      writable: true,
    });
    vi.restoreAllMocks();
  });

  it('uses the async clipboard when it is available', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    setAsyncClipboard(writeText);

    await expect(copyTextToClipboard('GEOSX00001-A-G-1-ZY')).resolves.toBe('copied');
    expect(writeText).toHaveBeenCalledWith('GEOSX00001-A-G-1-ZY');
  });

  it('falls back to execCommand when the clipboard API is unavailable', async () => {
    setAsyncClipboard(undefined);
    const execCommand = vi.fn().mockReturnValue(true);
    Object.defineProperty(document, 'execCommand', {
      value: execCommand,
      configurable: true,
      writable: true,
    });

    await expect(copyTextToClipboard('GEOSX00001-A-G-1-ZY')).resolves.toBe('fallback-copied');
    expect(execCommand).toHaveBeenCalledWith('copy');
  });

  it('falls back when the clipboard API rejects, e.g. a denied permission', async () => {
    setAsyncClipboard(vi.fn().mockRejectedValue(new Error('NotAllowedError')));
    const execCommand = vi.fn().mockReturnValue(true);
    Object.defineProperty(document, 'execCommand', {
      value: execCommand,
      configurable: true,
      writable: true,
    });

    await expect(copyTextToClipboard('GEOSX00001-A-G-1-ZY')).resolves.toBe('fallback-copied');
    expect(execCommand).toHaveBeenCalledWith('copy');
  });

  it('reports failure when neither path works', async () => {
    setAsyncClipboard(undefined);
    Object.defineProperty(document, 'execCommand', {
      value: vi.fn().mockReturnValue(false),
      configurable: true,
      writable: true,
    });

    await expect(copyTextToClipboard('GEOSX00001-A-G-1-ZY')).resolves.toBe('failed');
  });

  it('reports failure when execCommand throws', async () => {
    setAsyncClipboard(undefined);
    Object.defineProperty(document, 'execCommand', {
      value: vi.fn(() => {
        throw new Error('boom');
      }),
      configurable: true,
      writable: true,
    });

    await expect(copyTextToClipboard('GEOSX00001-A-G-1-ZY')).resolves.toBe('failed');
  });

  it('never attempts to copy an empty string', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    setAsyncClipboard(writeText);
    const execCommand = vi.fn().mockReturnValue(true);
    Object.defineProperty(document, 'execCommand', {
      value: execCommand,
      configurable: true,
      writable: true,
    });

    await expect(copyTextToClipboard('')).resolves.toBe('failed');
    expect(writeText).not.toHaveBeenCalled();
    expect(execCommand).not.toHaveBeenCalled();
  });

  it('cleans up the temporary textarea it uses for the fallback', async () => {
    setAsyncClipboard(undefined);
    Object.defineProperty(document, 'execCommand', {
      value: vi.fn().mockReturnValue(true),
      configurable: true,
      writable: true,
    });

    await copyTextToClipboard('GEOSX00001-A-G-1-ZY');

    expect(document.querySelectorAll('textarea')).toHaveLength(0);
  });
});
