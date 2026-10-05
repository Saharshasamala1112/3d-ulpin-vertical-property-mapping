import { useAuth } from '../../../app/AuthContext';

export type ManagementAction = 'create' | 'edit' | 'delete' | 'archive' | 'import' | 'view';

export interface ActionGrants {
  can: (action: ManagementAction) => boolean;
  readonly hasBackendAuthorization: boolean;
}

/** Keep management actions aligned with the backend reader/editor/admin tiers. */
export function useManagementPermissions(): ActionGrants {
  const { user } = useAuth();
  const role = user?.role;

  return {
    can: (action) => {
      if (action === 'view') return role === 'reader' || role === 'editor' || role === 'admin';
      if (action === 'delete' || action === 'archive') return role === 'admin';
      return role === 'editor' || role === 'admin';
    },
    hasBackendAuthorization: role !== undefined,
  };
}
