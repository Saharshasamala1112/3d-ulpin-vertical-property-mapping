import { describe, it, expect, beforeEach, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { ThemeProvider } from '../../app/ThemeContext';
import { VisualizationPage } from './VisualizationPage';
import type { BuildingOption, BuildingScene } from '../../types/geometry';

vi.mock('../../services/geometry-service', () => ({
  listParcels: vi.fn(),
  listBuildings: vi.fn(),
  loadBuildingScene: vi.fn(),
  toErrorMessage: (error: unknown, fallback: string) => {
    const data = (error as { data?: { message?: string } } | undefined)?.data;
    return data?.message ?? fallback;
  },
}));

// The real viewer needs WebGL, which jsdom does not provide. The page's lazy
// boundary is exercised here; the viewer itself is covered by the pure camera
// maths in orbit.test.ts.
vi.mock('../../components/visualization/GeometryViewer', () => ({
  default: ({ units }: { units: { id: string }[] }) => (
    <div data-testid="geometry-canvas">{`units:${units.length}`}</div>
  ),
}));

import { listBuildings, listParcels, loadBuildingScene } from '../../services/geometry-service';

const mockListParcels = vi.mocked(listParcels);
const mockListBuildings = vi.mocked(listBuildings);
const mockLoadScene = vi.mocked(loadBuildingScene);

const PARCELS = [
  { id: 'p-1', identifier: 'PARCEL-1', ulpin: 'ULPIN-1' },
  { id: 'p-2', identifier: 'PARCEL-2', ulpin: 'ULPIN-2' },
];

const BUILDING: BuildingOption = {
  id: 'b-1',
  identifier: 'BLDG-1',
  name: 'Tower',
  buildingType: 'residential',
  constructionStatus: 'completed',
};

function sceneUnit(id: string, identifier: string, floorId: string, levelName: string, floorNumber: number) {
  return {
    id,
    unitIdentifier: identifier,
    unitType: 'residential',
    status: 'active',
    floor: { id: floorId, floorNumber, levelName, floorType: 'typical' },
    geometry: {
      id: `geo-${id}`,
      unitId: id,
      geometryType: 'aabb' as const,
      bounds: { min: { x: 0, y: 0, z: 0 }, max: { x: 4.530865, y: 4.75, z: 3.041593 } },
      centroid: { x: 2.2654325, y: 2.375, z: 1.5207965 },
      dimensions: { x: 4.530865, y: 4.75, z: 3.041593 },
      volume: 65.45997452273875,
      createdAt: '',
      updatedAt: '',
    },
  };
}

const SCENE: BuildingScene = {
  building: BUILDING,
  floors: [
    { id: 'f-1', floorNumber: 1, levelName: 'Ground', floorType: 'ground' },
    { id: 'f-2', floorNumber: 2, levelName: 'Typical', floorType: 'typical' },
  ],
  units: [
    sceneUnit('u-1', 'A-101', 'f-1', 'Ground', 1),
    sceneUnit('u-2', 'B-201', 'f-2', 'Typical', 2),
  ],
  unitsWithoutGeometry: [{ id: 'u-3', unitIdentifier: 'C-301', floor: { id: 'f-2', floorNumber: 2, levelName: 'Typical', floorType: 'typical' } }],
};

async function selectParcel(value: string) {
  // The options arrive asynchronously; changing the value before they exist
  // would silently leave the select empty.
  await waitFor(() => expect(screen.getByRole('option', { name: /PARCEL-1/ })).toBeInTheDocument());
  fireEvent.change(screen.getByLabelText('Parcel'), { target: { value } });
}

async function selectBuilding(value: string) {
  const select = await screen.findByLabelText('Building');
  await waitFor(() => expect(select).not.toBeDisabled());
  fireEvent.change(select, { target: { value } });
}

function renderPage() {
  return render(
    <ThemeProvider>
      <VisualizationPage />
    </ThemeProvider>,
  );
}

describe('VisualizationPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem('geosix-theme', 'light');
    mockListParcels.mockResolvedValue(PARCELS);
    mockListBuildings.mockResolvedValue([BUILDING]);
    mockLoadScene.mockResolvedValue(SCENE);
  });

  it('prompts for a building before anything is selected', async () => {
    renderPage();

    expect(await screen.findByText('Choose a building')).toBeInTheDocument();
    const buildingSelect = screen.getByLabelText('Building') as HTMLSelectElement;
    expect(buildingSelect).toBeDisabled();
  });

  it('loads buildings when a parcel is chosen', async () => {
    renderPage();

    await selectParcel('p-1');

    expect(mockListBuildings).toHaveBeenCalledWith('p-1');
    const buildingSelect = await screen.findByLabelText('Building') as HTMLSelectElement;
    await waitFor(() => expect(buildingSelect).not.toBeDisabled());
    expect(within(buildingSelect).getByText('Tower')).toBeInTheDocument();
  });

  it('auto-selects the only parcel when there is exactly one', async () => {
    mockListParcels.mockResolvedValue([PARCELS[0]]);
    renderPage();

    await waitFor(() => expect(mockListBuildings).toHaveBeenCalledWith('p-1'));
  });

  it('renders the 3D viewer and the unit list once a building is loaded', async () => {
    renderPage();

    await selectParcel('p-1');
    await selectBuilding('b-1');

    expect(await screen.findByTestId('geometry-canvas')).toHaveTextContent('units:2');
    expect(screen.getByRole('heading', { name: 'Units (2)' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /A-101/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /B-201/ })).toBeInTheDocument();
  });

  it('shows details for the selected unit and switches on click', async () => {
    renderPage();

    await selectParcel('p-1');
    await selectBuilding('b-1');

    const details = await screen.findByTestId('unit-details');
    expect(within(details).getByText('A-101')).toBeInTheDocument();
    expect(details).toHaveTextContent('4.53 x 4.75 x 3.04 m');

    fireEvent.click(screen.getByRole('button', { name: /B-201/ }));

    await waitFor(() => {
      expect(screen.getByTestId('unit-details')).toHaveTextContent('B-201');
    });
  });

  it('lists units that have no geometry separately', async () => {
    renderPage();

    await selectParcel('p-1');
    await selectBuilding('b-1');

    expect(await screen.findByRole('heading', { name: 'Without geometry (1)' })).toBeInTheDocument();
    expect(screen.getByText('C-301')).toBeInTheDocument();
  });

  it('explains an empty scene instead of rendering an empty canvas', async () => {
    mockLoadScene.mockResolvedValue({ ...SCENE, units: [], unitsWithoutGeometry: [] });
    renderPage();

    await selectParcel('p-1');
    await selectBuilding('b-1');

    expect(await screen.findByText('No unit geometry yet')).toBeInTheDocument();
    expect(screen.queryByTestId('geometry-canvas')).not.toBeInTheDocument();
  });

  it('explains when every unit is missing a bounding box', async () => {
    mockLoadScene.mockResolvedValue({ ...SCENE, units: [], unitsWithoutGeometry: SCENE.unitsWithoutGeometry });
    renderPage();

    await selectParcel('p-1');
    await selectBuilding('b-1');

    expect(await screen.findByText(/have no persisted bounding box/)).toBeInTheDocument();
  });

  it('surfaces a load failure with the API message', async () => {
    mockLoadScene.mockRejectedValue({ status: 500, data: { message: 'Geometry service unavailable' } });
    renderPage();

    await selectParcel('p-1');
    await selectBuilding('b-1');

    expect(await screen.findByText('Could not load the 3D model')).toBeInTheDocument();
    expect(screen.getByText('Geometry service unavailable')).toBeInTheDocument();
  });

  it('surfaces a failure to load parcels', async () => {
    mockListParcels.mockRejectedValue({ status: 500, data: { message: 'Database offline' } });
    renderPage();

    expect(await screen.findByText('Could not load the 3D model')).toBeInTheDocument();
    expect(screen.getByText('Database offline')).toBeInTheDocument();
  });
});
