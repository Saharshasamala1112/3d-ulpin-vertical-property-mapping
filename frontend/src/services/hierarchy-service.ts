import { apiClient } from './api-client';

export interface HierarchyOption {
  id: string;
  label: string;
}

interface ParcelFeature {
  id?: string;
  properties?: {
    id?: string;
    parcel_identifier?: string;
    ulpin?: string | null;
  };
}

interface ParcelListResponse {
  data?: ParcelFeature[];
}

interface BuildingResponse {
  id: string;
  building_identifier: string;
  name?: string | null;
}

interface FloorResponse {
  id: string;
  floor_number: number;
  level_name?: string | null;
}

interface UnitResponse {
  id: string;
  unit_identifier: string;
}

export const hierarchyService = {
  async listParcels(): Promise<HierarchyOption[]> {
    const response = await apiClient.get<ParcelListResponse>(
      '/api/v1/parcels?page=1&per_page=100'
    );
    return (response.data ?? []).map((feature) => {
      const properties = feature.properties;
      const id = properties?.id ?? feature.id ?? '';
      const label =
        properties?.ulpin || properties?.parcel_identifier || id || 'Unnamed parcel';
      return { id, label };
    });
  },

  async listBuildings(parcelId: string): Promise<HierarchyOption[]> {
    const response = await apiClient.get<BuildingResponse[]>(
      `/api/v1/parcels/${parcelId}/buildings`
    );
    return response.map((building) => ({
      id: building.id,
      label: building.name || building.building_identifier,
    }));
  },

  async listFloors(buildingId: string): Promise<HierarchyOption[]> {
    const response = await apiClient.get<FloorResponse[]>(
      `/api/v1/buildings/${buildingId}/floors`
    );
    return response.map((floor) => ({
      id: floor.id,
      label: floor.level_name || `Floor ${floor.floor_number}`,
    }));
  },

  async listUnits(floorId: string): Promise<HierarchyOption[]> {
    const response = await apiClient.get<UnitResponse[]>(
      `/api/v1/floors/${floorId}/units`
    );
    return response.map((unit) => ({
      id: unit.id,
      label: unit.unit_identifier,
    }));
  },

  async listBuildingUnitIds(buildingId: string): Promise<string[]> {
    const floors = await this.listFloors(buildingId);
    const unitsPerFloor = await Promise.all(
      floors.map((floor) => this.listUnits(floor.id))
    );
    return unitsPerFloor.flat().map((unit) => unit.id);
  },
};
