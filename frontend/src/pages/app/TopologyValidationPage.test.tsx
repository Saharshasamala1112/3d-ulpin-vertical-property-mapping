import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { TopologyValidationPage } from './TopologyValidationPage';

vi.mock('../../services/topology-service', () => ({
  topologyService: {
    validateBuilding: vi.fn(),
    validateUnit: vi.fn(),
  },
}));

vi.mock('../../services/hierarchy-service', () => ({
  hierarchyService: {
    listParcels: vi.fn(),
    listBuildings: vi.fn(),
    listFloors: vi.fn(),
    listUnits: vi.fn(),
    listBuildingUnitIds: vi.fn(),
  },
}));

import { topologyService } from '../../services/topology-service';
import { hierarchyService } from '../../services/hierarchy-service';
import { UNIT_VALIDATION_STATUS_KEY } from '../../lib/unit-validation-status';
import type { TopologyValidationReport } from '../../types/topology';

const mockValidateBuilding = vi.mocked(topologyService.validateBuilding);
const mockValidateUnit = vi.mocked(topologyService.validateUnit);
const mockListParcels = vi.mocked(hierarchyService.listParcels);
const mockListBuildings = vi.mocked(hierarchyService.listBuildings);
const mockListFloors = vi.mocked(hierarchyService.listFloors);
const mockListUnits = vi.mocked(hierarchyService.listUnits);
const mockListBuildingUnitIds = vi.mocked(hierarchyService.listBuildingUnitIds);

const UNIT_A = 'aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa';
const UNIT_B = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb';

function failedReport(): TopologyValidationReport {
  return {
    summary: {
      status: 'failed',
      valid: false,
      geometry_error_count: 0,
      overlap_count: 1,
      gap_count: 0,
      elevation_error_count: 0,
    },
    geometry_errors: [],
    overlap_results: [
      {
        unit_a_id: UNIT_A,
        unit_b_id: UNIT_B,
        overlap_volume: '4.5',
        overlap_geometry: {
          x_min: '0',
          x_max: '2',
          y_min: '0',
          y_max: '2',
          z_min: '0',
          z_max: '1',
        },
      },
    ],
    gap_results: [],
    elevation_errors: [],
  };
}

function passedReport(): TopologyValidationReport {
  return {
    summary: {
      status: 'passed',
      valid: true,
      geometry_error_count: 0,
      overlap_count: 0,
      gap_count: 0,
      elevation_error_count: 0,
    },
    geometry_errors: [],
    overlap_results: [],
    gap_results: [],
    elevation_errors: [],
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <TopologyValidationPage />
    </MemoryRouter>
  );
}

async function selectBuildingScope() {
  await screen.findByRole('option', { name: 'ULPIN-1' });
  fireEvent.change(screen.getByLabelText('Parcel'), {
    target: { value: 'parcel-1' },
  });
  await screen.findByRole('option', { name: 'Tower A' });
  fireEvent.change(screen.getByLabelText('Building'), {
    target: { value: 'building-1' },
  });
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'Run validation' })).toBeEnabled()
  );
}

describe('TopologyValidationPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    mockListParcels.mockResolvedValue([{ id: 'parcel-1', label: 'ULPIN-1' }]);
    mockListBuildings.mockResolvedValue([{ id: 'building-1', label: 'Tower A' }]);
    mockListFloors.mockResolvedValue([{ id: 'floor-1', label: 'Floor 1' }]);
    mockListUnits.mockResolvedValue([{ id: 'unit-1', label: 'A-101' }]);
    mockListBuildingUnitIds.mockResolvedValue([UNIT_A, UNIT_B]);
  });

  it('shows the empty state before any run', async () => {
    renderPage();
    expect(await screen.findByText('No validation run yet')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Run validation' })).toBeDisabled();
  });

  it('renders pass/fail counts and expandable details after a building run', async () => {
    mockValidateBuilding.mockResolvedValue(failedReport());

    renderPage();
    await selectBuildingScope();

    fireEvent.click(screen.getByRole('button', { name: 'Run validation' }));

    expect(await screen.findByText('Failed')).toBeInTheDocument();
    expect(mockValidateBuilding).toHaveBeenCalledWith('building-1');
    expect(screen.getByText('1 issue found')).toBeInTheDocument();

    const overlapSection = await screen.findByRole('button', {
      name: /Volumetric overlap/i,
    });
    expect(overlapSection).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText(/overlap with volume 4\.5/)).toBeInTheDocument();

    const unitLinks = screen.getAllByRole('link');
    expect(unitLinks[0]).toHaveAttribute(
      'href',
      `/app/units?unit=${encodeURIComponent(UNIT_A)}`
    );
  });

  it('publishes the unit status handoff for the 3D view', async () => {
    mockValidateBuilding.mockResolvedValue(failedReport());

    renderPage();
    await selectBuildingScope();
    fireEvent.click(screen.getByRole('button', { name: 'Run validation' }));

    await waitFor(() => {
      expect(sessionStorage.getItem(UNIT_VALIDATION_STATUS_KEY)).toBeTruthy();
    });

    const stored = JSON.parse(sessionStorage.getItem(UNIT_VALIDATION_STATUS_KEY) as string);
    expect(stored.scope).toBe('building');
    expect(stored.target_id).toBe('building-1');
    expect(stored.statuses[UNIT_A]).toBe('overlap');
    expect(stored.statuses[UNIT_B]).toBe('overlap');
  });

  it('shows the success state when every check passes', async () => {
    mockValidateBuilding.mockResolvedValue(passedReport());

    renderPage();
    await selectBuildingScope();
    fireEvent.click(screen.getByRole('button', { name: 'Run validation' }));

    expect(await screen.findByText('All topology checks passed')).toBeInTheDocument();
    expect(screen.getByText('Passed')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Re-run validation' })).toBeInTheDocument();
  });

  it('runs unit validation when the unit scope is selected', async () => {
    mockValidateUnit.mockResolvedValue(passedReport());

    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Single unit' }));
    await screen.findByRole('option', { name: 'ULPIN-1' });
    fireEvent.change(screen.getByLabelText('Parcel'), {
      target: { value: 'parcel-1' },
    });
    await screen.findByRole('option', { name: 'Tower A' });
    fireEvent.change(screen.getByLabelText('Building'), {
      target: { value: 'building-1' },
    });
    await screen.findByRole('option', { name: 'Floor 1' });
    fireEvent.change(screen.getByLabelText('Floor'), {
      target: { value: 'floor-1' },
    });
    await screen.findByRole('option', { name: 'A-101' });
    fireEvent.change(screen.getByLabelText('Unit'), {
      target: { value: 'unit-1' },
    });
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Run validation' })).toBeEnabled()
    );

    fireEvent.click(screen.getByRole('button', { name: 'Run validation' }));

    expect(await screen.findByText('All topology checks passed')).toBeInTheDocument();
    expect(mockValidateUnit).toHaveBeenCalledWith('unit-1');
    expect(mockValidateBuilding).not.toHaveBeenCalled();
  });

  it('shows a not-found message when the target no longer exists', async () => {
    mockValidateBuilding.mockRejectedValue({
      status: 404,
      data: { error: { code: 'NOT_FOUND', message: 'Building not found' } },
    });

    renderPage();
    await selectBuildingScope();
    fireEvent.click(screen.getByRole('button', { name: 'Run validation' }));

    expect(await screen.findByText('Target not found')).toBeInTheDocument();
    expect(screen.getByText('Building not found')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
  });

  it('degrades gracefully when the validation API is missing', async () => {
    mockValidateBuilding.mockRejectedValue({ status: 404, data: null });

    renderPage();
    await selectBuildingScope();
    fireEvent.click(screen.getByRole('button', { name: 'Run validation' }));

    expect(await screen.findByText('Validation API not available')).toBeInTheDocument();
    expect(screen.getByText('Degraded')).toBeInTheDocument();
    expect(
      screen.getByText(/Other modules keep working/i)
    ).toBeInTheDocument();
  });

  it('surfaces network failures with a retry action', async () => {
    mockValidateBuilding.mockRejectedValue(new TypeError('Failed to fetch'));

    renderPage();
    await selectBuildingScope();
    fireEvent.click(screen.getByRole('button', { name: 'Run validation' }));

    expect(await screen.findByText('Cannot reach the server')).toBeInTheDocument();
  });
});
