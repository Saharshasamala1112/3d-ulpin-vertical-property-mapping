import { describe, it, expect, beforeEach, vi } from 'vitest';
import { getInitialTheme, setStoredTheme, applyTheme } from './theme';

describe('theme utilities', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
    // Mock matchMedia for jsdom
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: query.includes('dark'),
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
  });

  it('returns stored theme when available', () => {
    setStoredTheme('dark');
    expect(getInitialTheme()).toBe('dark');
  });

  it('persists theme to localStorage', () => {
    setStoredTheme('light');
    expect(localStorage.getItem('geosix-theme')).toBe('light');
  });

  it('applyTheme sets data-theme attribute', () => {
    applyTheme('dark');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    applyTheme('light');
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
  });

  it('getInitialTheme returns system theme when nothing stored', () => {
    // jsdom mock returns matches=true for 'dark' query
    expect(getInitialTheme()).toBe('dark');
  });
});
