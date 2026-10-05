import { apiClient } from './api-client';
import type { TopologyValidationReport } from '../types/topology';

export const topologyService = {
  validateBuilding(buildingId: string): Promise<TopologyValidationReport> {
    return apiClient.post<TopologyValidationReport>(
      `/api/v1/topology/validate/building/${buildingId}`
    );
  },

  validateUnit(unitId: string): Promise<TopologyValidationReport> {
    return apiClient.post<TopologyValidationReport>(
      `/api/v1/topology/validate/unit/${unitId}`
    );
  },
};
