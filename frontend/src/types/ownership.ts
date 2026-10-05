export type OwnerKind = 'individual' | 'organization';
export type OwnershipStatus = 'active' | 'transferred' | 'revoked';
export type SubjectType = 'parcel' | 'unit';

export interface Owner {
  id: string;
  kind: OwnerKind;
  name: string;
  identifier: string | null;
  contact_metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface OwnerCreate {
  kind: OwnerKind;
  name: string;
  identifier?: string | null;
  contact_metadata?: Record<string, unknown>;
}

export interface OwnerUpdate {
  kind?: OwnerKind;
  name?: string;
  identifier?: string | null;
  contact_metadata?: Record<string, unknown>;
}

export interface OwnershipInterest {
  id: string;
  owner_id: string;
  subject_type: SubjectType;
  subject_id: string;
  share_basis_points: number;
  valid_from: string;
  valid_to: string | null;
  status: OwnershipStatus;
  created_at: string;
  updated_at: string;
}

export interface OwnershipList<T> {
  data: T[];
  meta: {
    page: number;
    per_page: number;
    total: number;
    total_pages: number;
  };
}

export interface OwnershipTransferResult {
  closed: OwnershipInterest[];
  created: OwnershipInterest[];
}

export interface OwnershipAllocation {
  owner_id: string;
  share_basis_points: number;
}

export interface OwnershipApiError {
  status?: number;
  data?: {
    error_code?: string;
    message?: string;
    details?: Record<string, string>;
  };
}
