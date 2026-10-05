import { apiClient } from './api-client';
import type { HealthResponse } from '../types';

export const healthService = {
  async check(): Promise<HealthResponse> {
    return apiClient.get<HealthResponse>('/api/health');
  },
};