import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Sidebar } from './Sidebar';

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Sidebar />
    </MemoryRouter>
  );
}

/** The sidebar marks the active item via inline background styling. */
function activeLabels(): string[] {
  return screen
    .getAllByRole('link')
    .filter((link) => link.style.background === 'var(--sidebar-active)')
    // The label text includes the leading icon glyph.
    .map((link) => (link.textContent ?? '').replace(/^\S/, '').trim());
}

describe('Sidebar deep-link active state', () => {
  it('marks a top-level route active', () => {
    renderAt('/app/parcels');
    expect(activeLabels()).toContain('Parcels');
  });

  it('keeps the parent active on a nested route', () => {
    renderAt('/app/buildings/parcel-123');
    expect(activeLabels()).toEqual(['Buildings']);
  });

  it('keeps Buildings active for a building deep link', () => {
    renderAt('/app/buildings/abc%2Fdef');
    expect(activeLabels()).toEqual(['Buildings']);
  });

  it('keeps Floors active for a floor deep link', () => {
    renderAt('/app/floors/building-9');
    expect(activeLabels()).toEqual(['Floors']);
  });

  it('keeps Units active for a unit deep link', () => {
    renderAt('/app/units/floor-3');
    expect(activeLabels()).toEqual(['Units']);
  });

  it('does not mark a sibling whose name merely shares a prefix', () => {
    renderAt('/app/unit-plans');
    expect(activeLabels()).not.toContain('Units');
  });

  it('marks exactly one item at a time', () => {
    renderAt('/app/units/f-1');
    expect(activeLabels()).toHaveLength(1);
  });

  it('links each management entry to its index route', () => {
    renderAt('/app/dashboard');

    expect(screen.getByRole('link', { name: /parcels/i }).getAttribute('href')).toBe('/app/parcels');
    expect(screen.getByRole('link', { name: /buildings/i }).getAttribute('href')).toBe('/app/buildings');
    expect(screen.getByRole('link', { name: /floors/i }).getAttribute('href')).toBe('/app/floors');
    expect(screen.getByRole('link', { name: /units/i }).getAttribute('href')).toBe('/app/units');
  });
});
