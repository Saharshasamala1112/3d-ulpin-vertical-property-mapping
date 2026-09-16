import { apiClient } from './api-client';

interface HealthResponse {
  status: string;
  service: string;
}

export const healthService = {
  async check(): Promise<HealthResponse> {
    return apiClient.get<HealthResponse>('/api/v1/health');
  },
};
