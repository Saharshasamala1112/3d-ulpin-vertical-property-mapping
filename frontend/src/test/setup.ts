import '@testing-library/jest-dom/vitest';

/**
 * Minimal, test-only `<dialog>` polyfill.
 *
 * jsdom does not implement `HTMLDialogElement.showModal` / `.close`, so the
 * shared `Dialog` primitive throws `TypeError: dialog.showModal is not a
 * function` the moment it is opened in a test. These stubs are intentionally
 * minimal: they only flip the `open` attribute so component behaviour (mount,
 * escape handling, conditional content) can be asserted. No layout, focus
 * trapping, or backdrop behaviour is emulated, and nothing here ships to the
 * browser bundle.
 */
if (typeof window !== 'undefined') {
  if (typeof window.HTMLDialogElement !== 'undefined') {
    const proto = window.HTMLDialogElement.prototype as HTMLDialogElement & {
      showModal?: () => void;
      close?: (returnValue?: string) => void;
      show?: () => void;
    };

    if (typeof proto.showModal !== 'function') {
      proto.showModal = function showModal(this: HTMLDialogElement) {
        this.open = true;
      };
    }

    if (typeof proto.show !== 'function') {
      proto.show = function show(this: HTMLDialogElement) {
        this.open = true;
      };
    }

    if (typeof proto.close !== 'function') {
      proto.close = function close(this: HTMLDialogElement) {
        this.open = false;
        this.dispatchEvent(new Event('close'));
      };
    }
  }
}
