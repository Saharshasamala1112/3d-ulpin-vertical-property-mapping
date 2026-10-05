import { useCallback, useEffect, useState } from 'react';
import { Button } from '../../../components/ui/Button';
import { LoadingSpinner } from '../../../components/feedback/LoadingSpinner';
import { ApiError, toApiError } from '../../../services/api-error';
import { ConfirmDialog } from '../shared/ConfirmDialog';
import { ErrorBanner } from '../shared/ErrorBanner';
import { VdcErrorList } from '../vdc/VdcErrorList';
import { VdcStatusBadge } from '../vdc/VdcStatusBadge';
import { copyTextToClipboard } from '../vdc/vdc-clipboard';
import { generateUnitVdc, getUnitVdc, validateVdc } from '../vdc/vdc-service';
import type { UnitVdc, VdcValidationError } from '../vdc/vdc-types';
import { extractVdcErrors } from '../vdc/vdc-validation';

interface UnitVdcPanelProps {
  unitId: string;
  /** Re-read the VDC sub-resource when this changes (e.g. after an edit). */
  revision?: number;
  /** Notifies the parent so it can refresh `vdc_status` in the list. */
  onChanged?: (vdc: UnitVdc) => void;
  /**
   * Whether the viewer may derive a code. Generation and regeneration persist,
   * so they are gated on the same `edit` permission the unit form uses; reading,
   * copying, and verifying stay available to everyone.
   */
  canEdit?: boolean;
}

const SEGMENT_LABELS: Array<[keyof UnitVdc, string]> = [
  ['ulpin', 'ULPIN'],
  ['domain', 'Domain'],
  ['level', 'Level'],
  ['unit', 'Unit'],
  ['checksum', 'Checksum'],
];

/**
 * Per-unit VDC actions: read, copy, generate/regenerate, and verify.
 *
 * The panel never judges a VDC itself. Status comes from the backend's
 * `GET /units/{id}/vdc`, and verification calls the shared validate endpoint so
 * the same rules apply here and on the standalone page.
 */
export function UnitVdcPanel({ unitId, revision = 0, onChanged, canEdit = true }: UnitVdcPanelProps) {
  const [vdc, setVdc] = useState<UnitVdc | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<ApiError | null>(null);

  const [busy, setBusy] = useState<'generate' | 'verify' | null>(null);
  const [actionError, setActionError] = useState<ApiError | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const [verified, setVerified] = useState<boolean | null>(null);
  const [verifyErrors, setVerifyErrors] = useState<VdcValidationError[]>([]);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      setVdc(await getUnitVdc(unitId));
    } catch (error) {
      setLoadError(toApiError(error));
    } finally {
      setLoading(false);
    }
  }, [unitId]);

  useEffect(() => {
    void load();
  }, [load, revision]);

  function resetActionState() {
    setVerified(null);
    setVerifyErrors([]);
    setActionError(null);
    setNotice(null);
  }

  async function handleCopy() {
    if (!vdc?.vdc_code) return;
    const outcome = await copyTextToClipboard(vdc.vdc_code);
    setNotice(
      outcome === 'copied' || outcome === 'fallback-copied'
        ? 'Copied to clipboard.'
        : 'Could not copy automatically. Select the code and copy it manually.',
    );
  }

  async function runGenerate() {
    setBusy('generate');
    setActionError(null);
    setNotice(null);
    setVerified(null);
    setVerifyErrors([]);
    try {
      const updated = await generateUnitVdc(unitId);
      setVdc(updated);
      onChanged?.(updated);
      setNotice(updated.vdc_code ? 'VDC generated.' : 'No VDC could be generated.');
    } catch (error) {
      setActionError(toApiError(error));
    } finally {
      setBusy(null);
      setConfirmOpen(false);
    }
  }

  /** Regenerating replaces a stored code, so it asks first. */
  function handleGenerateClick() {
    resetActionState();
    if (vdc?.vdc_code) setConfirmOpen(true);
    else void runGenerate();
  }
  async function handleVerify() {
    if (!vdc?.vdc_code) return;
    setBusy('verify');
    setActionError(null);
    setNotice(null);
    try {
      const result = await validateVdc(vdc.vdc_code);
      setVerified(result.valid);
      setVerifyErrors(result.errors ?? []);
    } catch (error) {
      const apiError = toApiError(error);
      const structured = extractVdcErrors(apiError);
      if (structured.length > 0) {
        setVerified(false);
        setVerifyErrors(structured);
      } else {
        setActionError(apiError);
      }
    } finally {
      setBusy(null);
    }
  }

  if (loading) return <LoadingSpinner size={20} />;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      {loadError && <ErrorBanner error={loadError} onDismiss={() => void load()} />}

      {vdc && (
        <>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: '0.75rem',
              flexWrap: 'wrap',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <code data-testid="unit-vdc-code" style={{ fontSize: '0.9375rem' }}>
                {vdc.vdc_code ?? 'No VDC code'}
              </code>
              <VdcStatusBadge status={vdc.status} />
            </div>

            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={() => void handleCopy()}
                disabled={!vdc.vdc_code}
              >
                Copy
              </Button>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={() => void handleVerify()}
                loading={busy === 'verify'}
                disabled={!vdc.vdc_code || busy !== null}
              >
                Verify
              </Button>
              {canEdit && (
                <Button
                  type="button"
                  size="sm"
                  variant={vdc.vdc_code ? 'secondary' : 'primary'}
                  onClick={handleGenerateClick}
                  loading={busy === 'generate'}
                  disabled={busy !== null}
                >
                  {vdc.vdc_code ? 'Regenerate' : 'Generate'}
                </Button>
              )}
            </div>
          </div>

          {vdc.vdc_code && (
            <dl
              style={{
                margin: 0,
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(8rem, 1fr))',
                gap: '0.5rem',
              }}
            >
              {SEGMENT_LABELS.map(([key, label]) => (
                <div key={key as string}>
                  <dt style={{ fontSize: '0.6875rem', color: 'var(--muted)', textTransform: 'uppercase' }}>
                    {label}
                  </dt>
                  <dd data-testid={`unit-vdc-segment-${key as string}`} style={{ margin: 0, fontSize: '0.8125rem' }}>
                    {vdc[key] ?? '—'}
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </>
      )}

      {notice && (
        <span role="status" style={{ fontSize: '0.8125rem', color: 'var(--muted)' }}>
          {notice}
        </span>
      )}

      {actionError && <ErrorBanner error={actionError} onDismiss={() => setActionError(null)} />}

      {verified === true && (
        <span role="status" style={{ fontSize: '0.8125rem', color: 'var(--success)' }}>
          Checksum verified.
        </span>
      )}

      {verified === false && <VdcErrorList errors={verifyErrors} />}

      <ConfirmDialog
        open={confirmOpen}
        title="Regenerate VDC?"
        message="This unit already has a VDC code. Regenerating replaces the stored code with one derived from the current parcel, building, floor, and unit identifier."
        confirmLabel="Regenerate"
        busy={busy === 'generate'}
        onConfirm={() => void runGenerate()}
        onCancel={() => setConfirmOpen(false)}
      />
    </div>
  );
}

export default UnitVdcPanel;
