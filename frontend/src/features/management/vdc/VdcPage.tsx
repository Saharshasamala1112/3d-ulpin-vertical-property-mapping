import { useState } from 'react';
import { Alert } from '../../../components/ui/Alert';
import { Button } from '../../../components/ui/Button';
import { Card } from '../../../components/ui/Card';
import { Input } from '../../../components/ui/Input';
import { ApiError, toApiError } from '../../../services/api-error';
import { ErrorBanner } from '../shared/ErrorBanner';
import { VdcErrorList } from './VdcErrorList';
import { copyTextToClipboard } from './vdc-clipboard';
import { parseVdc, validateVdc } from './vdc-service';
import { canonicalVdc, VDC_SEGMENT_NAMES, type VdcParsed, type VdcValidationError } from './vdc-types';
import { extractVdcErrors } from './vdc-validation';

/**
 * Standalone VDC workbench: paste a code, decompose it, and verify it.
 *
 * All VDC grammar and checksum decisions come from the backend. This page only
 * presents the results, so a VDC that is malformed or fails its checksum is
 * reported with the server's own per-segment errors rather than a local guess.
 */
export function VdcPage() {
  const [vdc, setVdc] = useState('');
  const [busy, setBusy] = useState<'parse' | 'validate' | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [parsed, setParsed] = useState<VdcParsed | null>(null);
  const [parseErrors, setParseErrors] = useState<VdcValidationError[]>([]);
  const [parseError, setParseError] = useState<ApiError | null>(null);

  const [validated, setValidated] = useState<boolean | null>(null);
  const [validationErrors, setValidationErrors] = useState<VdcValidationError[]>([]);
  const [validationError, setValidationError] = useState<ApiError | null>(null);

  /** Editing the code invalidates any result still on screen. */
  function handleChange(next: string) {
    setVdc(next);
    setParsed(null);
    setParseErrors([]);
    setParseError(null);
    setValidated(null);
    setValidationErrors([]);
    setValidationError(null);
    setNotice(null);
  }

  async function handleCopy(text: string) {
    const outcome = await copyTextToClipboard(text);
    if (outcome === 'copied' || outcome === 'fallback-copied') {
      setNotice('Copied to clipboard.');
    } else {
      setNotice('Could not copy automatically. Select the code and copy it manually.');
    }
  }

  async function handleParse() {
    setBusy('parse');
    setNotice(null);
    setParsed(null);
    setParseErrors([]);
    setParseError(null);
    setValidated(null);
    setValidationErrors([]);
    try {
      setParsed(await parseVdc(vdc));
    } catch (error) {
      const apiError = toApiError(error);
      const structured = extractVdcErrors(apiError);
      // A 422 carries per-segment errors; anything else is a request failure.
      if (structured.length > 0) setParseErrors(structured);
      else setParseError(apiError);
    } finally {
      setBusy(null);
    }
  }

  async function handleValidate() {
    setBusy('validate');
    setNotice(null);
    setParsed(null);
    setParseErrors([]);
    setParseError(null);
    setValidationErrors([]);
    setValidationError(null);
    try {
      const result = await validateVdc(vdc);
      setValidated(result.valid);
      setValidationErrors(result.errors ?? []);
    } catch (error) {
      setValidationError(toApiError(error));
    } finally {
      setBusy(null);
    }
  }

  const canSubmit = vdc.trim().length > 0 && busy === null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 600, marginBottom: '0.25rem' }}>VDC</h1>
        <p style={{ fontSize: '0.875rem', color: 'var(--muted)' }}>
          Paste a VDC to see its five segments and confirm its checksum.
        </p>
      </div>

      <Card>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void handleParse();
          }}
          style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}
        >
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-end', flexWrap: 'wrap' }}>
            <div style={{ flex: '1 1 20rem' }}>
              <Input
                label="VDC code"
                value={vdc}
                onChange={(event) => handleChange(event.target.value)}
                placeholder="GEOSX00001-A-G-1-ZY"
                autoComplete="off"
                spellCheck={false}
              />
            </div>
            <Button type="submit" variant="primary" loading={busy === 'parse'} disabled={!canSubmit}>
              Parse
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => void handleValidate()}
              loading={busy === 'validate'}
              disabled={!canSubmit}
            >
              Validate
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => void handleCopy(vdc.trim())}
              disabled={vdc.trim().length === 0}
            >
              Copy
            </Button>
          </div>

          {notice && (
            <span role="status" style={{ fontSize: '0.8125rem', color: 'var(--muted)' }}>
              {notice}
            </span>
          )}
        </form>
      </Card>

      {parseError && <ErrorBanner error={parseError} onDismiss={() => setParseError(null)} />}

      {parseErrors.length > 0 && (
        <Alert variant="error" title="This VDC is not valid">
          <VdcErrorList errors={parseErrors} />
        </Alert>
      )}

      {validationError && (
        <ErrorBanner error={validationError} onDismiss={() => setValidationError(null)} />
      )}

      {validated === true && validationErrors.length === 0 && (
        <Alert variant="success" title="Valid VDC">
          Every segment is well formed and the checksum matches.
        </Alert>
      )}

      {validated === false && (
        <Alert
          variant="error"
          title="This VDC is not valid"
          onDismiss={() => {
            setValidated(null);
            setValidationErrors([]);
          }}
        >
          <VdcErrorList errors={validationErrors} />
        </Alert>
      )}

      {parsed && (
        <Card>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: '0.75rem',
                flexWrap: 'wrap',
              }}
            >
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>Canonical VDC</div>
                <code data-testid="vdc-canonical" style={{ fontSize: '1rem', fontWeight: 600 }}>
                  {canonicalVdc(parsed)}
                </code>
              </div>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => void handleCopy(canonicalVdc(parsed))}
              >
                Copy
              </Button>
            </div>

            <Alert variant="success" title="Parsed successfully">
              The code is well formed and its checksum matches.
            </Alert>

            <dl style={{ margin: 0, display: 'grid', gap: '0.5rem' }}>
              {VDC_SEGMENT_NAMES.map((segment) => (
                <div
                  key={segment}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    gap: '1rem',
                    borderBottom: '1px solid var(--border)',
                    paddingBottom: '0.5rem',
                  }}
                >
                  <dt style={{ fontSize: '0.8125rem', color: 'var(--muted)', textTransform: 'uppercase' }}>
                    {segment}
                  </dt>
                  <dd data-testid={`vdc-segment-${segment}`} style={{ margin: 0, fontSize: '0.875rem' }}>
                    {parsed[segment]}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        </Card>
      )}
    </div>
  );
}

export default VdcPage;
