import { useCallback, useEffect, useEffectEvent, useState } from 'react';
import { ApiError, toApiError } from '../../../services/api-error';

interface UseResourceListResult<T> {
  data: T | null;
  loading: boolean;
  error: ApiError | null;
  reload: () => void;
  /** Optimistically replace the loaded payload (used after create/update). */
  setData: (value: T) => void;
}

/**
 * Generic async list loader shared by the four management pages.
 *
 * `depsKey` is a primitive string describing the request parameters (page,
 * filter, parent id, ...). Keeping it a string avoids a non-memoized loader
 * closure being treated as a dependency on every render.
 *
 * `enabled` supports hierarchical pages that cannot load until a parent
 * selection exists (for example buildings without a chosen parcel).
 */
export function useResourceList<T>(
  loader: () => Promise<T>,
  depsKey: string,
  enabled = true
): UseResourceListResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(enabled);
  const [error, setError] = useState<ApiError | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  // Latest loader without making it an effect dependency. `useEffectEvent`
  // keeps this out of render, which a plain `ref.current = loader` write
  // during render would not.
  const load = useEffectEvent(loader);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    load().then(
      (result) => {
        if (cancelled) return;
        setData(result);
        setLoading(false);
      },
      (failure: unknown) => {
        if (cancelled) return;
        setError(toApiError(failure));
        setLoading(false);
      }
    );

    return () => {
      cancelled = true;
    };
  }, [depsKey, reloadToken, enabled]);

  const reload = useCallback(() => {
    setReloadToken((token) => token + 1);
  }, []);

  return { data, loading, error, reload, setData };
}
