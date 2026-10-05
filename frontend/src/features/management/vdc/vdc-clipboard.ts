/**
 * Copy-to-clipboard helper with a non-secure-context fallback.
 *
 * The async Clipboard API is unavailable in insecure contexts and can reject
 * when a permission is denied, so every copy falls back to the legacy
 * `document.execCommand('copy')` path. Adding a clipboard dependency was
 * explicitly out of scope, and this keeps the behaviour in one testable place.
 */

export type CopyOutcome = 'copied' | 'fallback-copied' | 'failed';

/** True when the async Clipboard API is usable. */
function hasAsyncClipboard(): boolean {
  return (
    typeof navigator !== 'undefined' &&
    typeof navigator.clipboard?.writeText === 'function'
  );
}

/** Last-resort copy via a hidden textarea and `execCommand`. */
function copyViaExecCommand(text: string): CopyOutcome {
  if (typeof document === 'undefined' || typeof document.execCommand !== 'function') {
    return 'failed';
  }

  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.setAttribute('readonly', '');
  textarea.style.position = 'fixed';
  textarea.style.top = '0';
  textarea.style.opacity = '0';
  document.body.appendChild(textarea);

  try {
    textarea.select();
    return document.execCommand('copy') ? 'fallback-copied' : 'failed';
  } catch {
    return 'failed';
  } finally {
    document.body.removeChild(textarea);
  }
}

/**
 * Copy `text`, preferring the async Clipboard API and falling back to
 * `execCommand` when it is unavailable or rejects.
 *
 * Reports which path was taken so the UI can still confirm the copy, and
 * `failed` when neither worked, so the caller can offer manual selection.
 */
export async function copyTextToClipboard(text: string): Promise<CopyOutcome> {
  if (!text) return 'failed';

  if (hasAsyncClipboard()) {
    try {
      await navigator.clipboard.writeText(text);
      return 'copied';
    } catch {
      return copyViaExecCommand(text);
    }
  }

  return copyViaExecCommand(text);
}
