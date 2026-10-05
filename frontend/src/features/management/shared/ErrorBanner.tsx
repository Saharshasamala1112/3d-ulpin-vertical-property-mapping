import { Alert } from '../../../components/ui/Alert';
import { ApiError } from '../../../services/api-error';

interface ErrorBannerProps {
  error: ApiError | null;
  onDismiss?: () => void;
}

/**
 * Map a Feature 12 / legacy error onto a list-level banner.
 *
 * Status-aware messaging, because the failure modes differ meaningfully:
 *  - 404: the selected parent (parcel/building/floor) no longer exists.
 *  - 409: uniqueness conflict on create/update.
 *  - 500: the opaque server error that malformed GeoJSON produces.
 */
export function describeError(error: ApiError): string {
  if (error.isValidationError) {
    const fields = Object.keys(error.fieldErrors);
    const suffix = fields.length
      ? ` (${fields.slice(0, 4).join(', ')}${fields.length > 4 ? ', ...' : ''})`
      : '';
    return `${error.displayMessage}${suffix}`;
  }
  if (error.isNotFound) return 'The requested record was not found.';
  if (error.isConflict) return error.displayMessage || 'This record conflicts with an existing one.';
  if (error.status === 0) return 'Could not reach the server. Check that the API is running.';
  if (error.isServerError) {
    return 'The server could not process the request. This can happen with malformed GeoJSON content.';
  }
  return error.displayMessage;
}

export function errorTitle(error: ApiError): string {
  if (error.isValidationError) return 'Validation failed';
  if (error.isNotFound) return 'Not found';
  if (error.isConflict) return 'Conflict';
  if (error.isServerError) return 'Server error';
  return 'Request failed';
}

export function ErrorBanner({ error, onDismiss }: ErrorBannerProps) {
  if (!error) return null;

  return (
    <Alert variant="error" title={errorTitle(error)} onDismiss={onDismiss}>
      <span data-testid="error-banner-message">{describeError(error)}</span>
    </Alert>
  );
}
