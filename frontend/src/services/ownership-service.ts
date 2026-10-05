import { apiClient } from './api-client';
import type {
  Owner,
  OwnerCreate,
  OwnerUpdate,
  OwnershipAllocation,
  OwnershipInterest,
  OwnershipList,
  OwnershipTransferResult,
  SubjectType,
} from '../types/ownership';

const BASE = '/api/v1/ownership';

export const ownershipService = {
  listOwners(search = ''): Promise<OwnershipList<Owner>> {
    const query = search ? `?search=${encodeURIComponent(search)}` : '';
    return apiClient.get(`${BASE}/owners${query}`);
  },

  getOwner(ownerId: string): Promise<Owner> {
    return apiClient.get(`${BASE}/owners/${ownerId}`);
  },

  createOwner(payload: OwnerCreate): Promise<Owner> {
    return apiClient.post(`${BASE}/owners`, payload);
  },

  updateOwner(ownerId: string, payload: OwnerUpdate): Promise<Owner> {
    return apiClient.request(`${BASE}/owners/${ownerId}`, {
      method: 'PATCH',
      body: payload,
    });
  },

  deleteOwner(ownerId: string): Promise<void> {
    return apiClient.delete(`${BASE}/owners/${ownerId}`);
  },

  listSubjectInterests(
    subjectType: SubjectType,
    subjectId: string,
    history = false,
  ): Promise<OwnershipList<OwnershipInterest>> {
    const query = history ? '?history=true' : '';
    return apiClient.get(`${BASE}/${subjectType}s/${subjectId}/interests${query}`);
  },

  listOwnerInterests(ownerId: string, history = true): Promise<OwnershipList<OwnershipInterest>> {
    const query = history ? '?history=true' : '';
    return apiClient.get(`${BASE}/owners/${ownerId}/interests${query}`);
  },

  grant(payload: {
    owner_id: string;
    subject_type: SubjectType;
    subject_id: string;
    share_basis_points: number;
    valid_from: string;
  }): Promise<OwnershipInterest> {
    return apiClient.post(`${BASE}/interests`, payload);
  },

  transfer(payload: {
    subject_type: SubjectType;
    subject_id: string;
    effective_at: string;
    allocations: OwnershipAllocation[];
  }): Promise<OwnershipTransferResult> {
    return apiClient.post(`${BASE}/transfers`, payload);
  },

  revoke(interestId: string, effective_at: string): Promise<OwnershipInterest> {
    return apiClient.post(`${BASE}/interests/${interestId}/revocations`, { effective_at });
  },
};
