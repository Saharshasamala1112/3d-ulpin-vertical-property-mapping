import { useEffect, useState, type FormEvent } from 'react';
import { Button } from '../../components/ui/Button';
import { EmptyState } from '../../components/feedback/EmptyState';
import { LoadingSpinner } from '../../components/feedback/LoadingSpinner';
import { PageContainer } from '../../components/layout/PageContainer';
import { Input } from '../../components/ui/Input';
import { ownershipService } from '../../services/ownership-service';
import type {
  Owner,
  OwnerKind,
  OwnershipApiError,
  OwnershipInterest,
  OwnershipTransferResult,
  SubjectType,
} from '../../types/ownership';

type Action = 'register' | 'grant' | 'transfer' | 'revoke';

function errorMessage(error: unknown): string {
  const apiError = error as OwnershipApiError;
  return apiError?.data?.message ?? 'The request could not be completed. Try again.';
}

function formatDate(value: string | null): string {
  if (!value) return 'Open';
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(
    new Date(value),
  );
}

function dateTimeInput(value = new Date()): string {
  const local = new Date(value.getTime() - value.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function toIso(value: string): string {
  return new Date(value).toISOString();
}

export function OwnershipPage() {
  const [owners, setOwners] = useState<Owner[]>([]);
  const [interests, setInterests] = useState<OwnershipInterest[]>([]);
  const [loading, setLoading] = useState(true);
  const [interestsLoading, setInterestsLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [action, setAction] = useState<Action>('register');
  const [subjectType, setSubjectType] = useState<SubjectType>('parcel');
  const [subjectId, setSubjectId] = useState('');
  const [history, setHistory] = useState(true);
  const [selectedOwner, setSelectedOwner] = useState('');

  const [ownerKind, setOwnerKind] = useState<OwnerKind>('individual');
  const [ownerName, setOwnerName] = useState('');
  const [ownerIdentifier, setOwnerIdentifier] = useState('');
  const [ownerContact, setOwnerContact] = useState('');

  const [grantOwner, setGrantOwner] = useState('');
  const [grantShare, setGrantShare] = useState('10000');
  const [grantDate, setGrantDate] = useState(dateTimeInput());
  const [transferAllocations, setTransferAllocations] = useState('');
  const [transferDate, setTransferDate] = useState(dateTimeInput());
  const [revokeInterest, setRevokeInterest] = useState('');
  const [revokeDate, setRevokeDate] = useState(dateTimeInput());

  async function loadOwners() {
    const result = await ownershipService.listOwners();
    setOwners(result.data);
  }

  async function loadInterests() {
    if (!subjectId.trim() && !selectedOwner) {
      setInterests([]);
      return;
    }
    setError('');
    setInterestsLoading(true);
    try {
      const result = selectedOwner
        ? await ownershipService.listOwnerInterests(selectedOwner, history)
        : await ownershipService.listSubjectInterests(subjectType, subjectId.trim(), history);
      setInterests(result.data);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setInterestsLoading(false);
    }
  }

  useEffect(() => {
    let mounted = true;
    ownershipService
      .listOwners()
      .then((result) => {
        if (mounted) setOwners(result.data);
      })
      .catch((requestError: unknown) => {
        if (mounted) setError(errorMessage(requestError));
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  async function refresh() {
    setError('');
    await loadOwners();
    if (subjectId.trim()) await loadInterests();
  }

  async function submit(event: FormEvent<HTMLFormElement>, operation: () => Promise<unknown>) {
    event.preventDefault();
    setError('');
    setNotice('');
    setBusy(true);
    try {
      const result = await operation();
      if (result && typeof result === 'object' && 'created' in result) {
        const transferResult = result as OwnershipTransferResult;
        setNotice(
          `Transfer recorded: ${transferResult.closed.length} prior interests closed and ${transferResult.created.length} new interests created.`,
        );
      } else {
        setNotice('Ownership record updated.');
      }
      await refresh();
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setBusy(false);
    }
  }

  function interestOwnerName(interest: OwnershipInterest): string {
    return owners.find((owner) => owner.id === interest.owner_id)?.name ?? interest.owner_id;
  }

  return (
    <PageContainer
      title="Ownership"
      description="Owners, allocations, and effective-dated history"
      actions={
        <Button variant="secondary" onClick={() => void refresh()} disabled={loading || busy}>
          Refresh
        </Button>
      }
    >
      {error && (
        <div role="alert" style={{ padding: '0.75rem 1rem', background: 'var(--danger-bg)', color: 'var(--danger)', marginBottom: '1rem' }}>
          {error}
        </div>
      )}
      {notice && (
        <div role="status" style={{ padding: '0.75rem 1rem', background: 'var(--success-bg)', color: 'var(--success)', marginBottom: '1rem' }}>
          {notice}
        </div>
      )}

      <section aria-label="Ownership actions" style={{ borderBottom: '1px solid var(--border)', marginBottom: '1.25rem' }}>
        <div role="tablist" aria-label="Ownership actions" style={{ display: 'flex', gap: '0.25rem', flexWrap: 'wrap' }}>
          {(['register', 'grant', 'transfer', 'revoke'] as const).map((item) => (
            <button
              key={item}
              type="button"
              role="tab"
              aria-selected={action === item}
              onClick={() => setAction(item)}
              style={{
                padding: '0.65rem 0.9rem',
                color: action === item ? 'var(--foreground)' : 'var(--muted)',
                background: 'transparent',
                border: 0,
                borderBottom: `2px solid ${action === item ? 'var(--primary)' : 'transparent'}`,
                textTransform: 'capitalize',
              }}
            >
              {item === 'register'
                ? 'Register owner'
                : item === 'grant'
                  ? 'Grant'
                  : item[0].toUpperCase() + item.slice(1)}
            </button>
          ))}
        </div>

        <div style={{ maxWidth: '760px', padding: '1.25rem 0' }}>
          {action === 'register' && (
            <form aria-label="Register owner" onSubmit={(event) => void submit(event, async () => {
              const owner = await ownershipService.createOwner({
                kind: ownerKind,
                name: ownerName.trim(),
                identifier: ownerIdentifier.trim() || null,
                contact_metadata: ownerContact.trim() ? { contact: ownerContact.trim() } : {},
              });
              setSelectedOwner(owner.id);
              setOwnerName('');
              setOwnerIdentifier('');
              setOwnerContact('');
              return owner;
            })}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: '0.9rem', alignItems: 'end' }}>
                <label style={{ display: 'grid', gap: '0.35rem', fontSize: '0.8125rem' }}>
                  Kind
                  <select aria-label="Owner kind" value={ownerKind} onChange={(event) => setOwnerKind(event.target.value as OwnerKind)}>
                    <option value="individual">Individual</option>
                    <option value="organization">Organization</option>
                  </select>
                </label>
                <Input label="Name" value={ownerName} onChange={(event) => setOwnerName(event.target.value)} required maxLength={255} />
                <Input label="Identifier (optional)" value={ownerIdentifier} onChange={(event) => setOwnerIdentifier(event.target.value)} maxLength={255} />
                <Input label="Contact (optional)" value={ownerContact} onChange={(event) => setOwnerContact(event.target.value)} />
                <Button type="submit" loading={busy}>Register owner</Button>
              </div>
            </form>
          )}

          {action === 'grant' && (
            <form aria-label="Grant ownership" onSubmit={(event) => void submit(event, () => ownershipService.grant({
              owner_id: grantOwner,
              subject_type: subjectType,
              subject_id: subjectId.trim(),
              share_basis_points: Number(grantShare),
              valid_from: toIso(grantDate),
            }))}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: '0.9rem', alignItems: 'end' }}>
                <OwnerSelect owners={owners} value={grantOwner} onChange={setGrantOwner} />
                <SubjectFields subjectType={subjectType} subjectId={subjectId} setSubjectType={setSubjectType} setSubjectId={setSubjectId} contextLabel="Grant" />
                <Input label="Share (basis points)" type="number" min={1} max={10000} value={grantShare} onChange={(event) => setGrantShare(event.target.value)} required />
                <Input label="Effective from" type="datetime-local" value={grantDate} onChange={(event) => setGrantDate(event.target.value)} required />
                <Button type="submit" loading={busy} disabled={!grantOwner || !subjectId}>Grant interest</Button>
              </div>
            </form>
          )}

          {action === 'transfer' && (
            <form aria-label="Transfer ownership" onSubmit={(event) => void submit(event, () => {
              const allocations = transferAllocations.split('\n').filter(Boolean).map((line) => {
                const [owner_id, basisPoints] = line.split(',').map((part) => part.trim());
                return { owner_id, share_basis_points: Number(basisPoints) };
              });
              return ownershipService.transfer({
                subject_type: subjectType,
                subject_id: subjectId.trim(),
                effective_at: toIso(transferDate),
                allocations,
              });
            })}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: '0.9rem', alignItems: 'end' }}>
                <SubjectFields subjectType={subjectType} subjectId={subjectId} setSubjectType={setSubjectType} setSubjectId={setSubjectId} contextLabel="Transfer" />
                <Input label="Effective at" type="datetime-local" value={transferDate} onChange={(event) => setTransferDate(event.target.value)} required />
                <label style={{ display: 'grid', gap: '0.35rem', fontSize: '0.8125rem', gridColumn: '1 / -1' }}>
                  Complete replacement allocation (one owner UUID,basis-points pair per line)
                  <textarea aria-label="Transfer allocations" rows={4} value={transferAllocations} onChange={(event) => setTransferAllocations(event.target.value)} required />
                </label>
                <Button type="submit" loading={busy} disabled={!subjectId}>Record complete transfer</Button>
              </div>
            </form>
          )}

          {action === 'revoke' && (
            <form aria-label="Revoke ownership" onSubmit={(event) => void submit(event, () => ownershipService.revoke(revokeInterest, toIso(revokeDate)))}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: '0.9rem', alignItems: 'end' }}>
                <Input label="Interest UUID" value={revokeInterest} onChange={(event) => setRevokeInterest(event.target.value)} required />
                <Input label="Effective at" type="datetime-local" value={revokeDate} onChange={(event) => setRevokeDate(event.target.value)} required />
                <Button type="submit" variant="danger" loading={busy} disabled={!revokeInterest}>Revoke interest</Button>
              </div>
            </form>
          )}
          <p style={{ color: 'var(--muted)', fontSize: '0.75rem', marginTop: '0.8rem' }}>
            Ownership writes remain unavailable until Feature 2 supplies a real authorization policy.
          </p>
        </div>
      </section>

      <section aria-label="Ownership records">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'end', marginBottom: '1rem' }}>
          <SubjectFields subjectType={subjectType} subjectId={subjectId} setSubjectType={setSubjectType} setSubjectId={setSubjectId} />
          <OwnerSelect owners={owners} value={selectedOwner} onChange={setSelectedOwner} includeAll />
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', fontSize: '0.875rem' }}>
            <input type="checkbox" checked={history} onChange={(event) => setHistory(event.target.checked)} />
            Include history
          </label>
          <Button variant="secondary" loading={interestsLoading} disabled={loading || busy || (!subjectId && !selectedOwner)} onClick={() => void loadInterests()}>
            Load records
          </Button>
        </div>

        {loading || interestsLoading ? <LoadingSpinner /> : interests.length === 0 ? (
          <EmptyState title="No ownership records" description="Choose an owner or enter a parcel/unit UUID to view allocations and history." />
        ) : (
          <div style={{ overflowX: 'auto', borderTop: '1px solid var(--border)' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '760px', textAlign: 'left' }}>
              <thead>
                <tr>{['Subject', 'Owner', 'Share', 'Valid from', 'Valid to', 'Status', 'History', 'Actions'].map((heading) => <th key={heading} style={{ padding: '0.75rem', borderBottom: '1px solid var(--border)', fontSize: '0.75rem', color: 'var(--muted)' }}>{heading}</th>)}</tr>
              </thead>
              <tbody>
                {interests.map((interest) => (
                  <tr key={interest.id}>
                    <td style={cellStyle}>{interest.subject_type} · {interest.subject_id}</td>
                    <td style={cellStyle}><button type="button" onClick={() => setSelectedOwner(interest.owner_id)} style={linkButtonStyle}>{interestOwnerName(interest)}</button></td>
                    <td style={cellStyle}>{(interest.share_basis_points / 100).toFixed(2)}%</td>
                    <td style={cellStyle}>{formatDate(interest.valid_from)}</td>
                    <td style={cellStyle}>{formatDate(interest.valid_to)}</td>
                    <td style={cellStyle}>{interest.status}</td>
                    <td style={cellStyle}>{interest.valid_to ? 'Historical' : 'Current'}</td>
                    <td style={cellStyle}>
                      {interest.valid_to === null && (
                        <Button size="sm" variant="danger" disabled={busy} onClick={() => {
                          setRevokeInterest(interest.id);
                          setAction('revoke');
                        }}>Revoke</Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {selectedOwner && (
        <section aria-label="Owner profile" style={{ marginTop: '1.5rem', paddingTop: '1rem', borderTop: '1px solid var(--border)' }}>
          <h2 style={{ fontSize: '1rem', marginBottom: '0.5rem' }}>Owner profile</h2>
          {owners.find((owner) => owner.id === selectedOwner) ? (
            <OwnerProfile owner={owners.find((owner) => owner.id === selectedOwner)!} />
          ) : <p style={{ color: 'var(--muted)' }}>Selected owner details are not in the current page of results.</p>}
        </section>
      )}
    </PageContainer>
  );
}

function OwnerSelect({
  owners,
  value,
  onChange,
  includeAll = false,
}: {
  owners: Owner[];
  value: string;
  onChange: (value: string) => void;
  includeAll?: boolean;
}) {
  return (
    <label style={{ display: 'grid', gap: '0.35rem', fontSize: '0.8125rem' }}>
      {includeAll ? 'Owner profile / filter' : 'Owner'}
      <select aria-label={includeAll ? 'Filter owner' : 'Owner'} value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">{includeAll ? 'All owners' : 'Select owner'}</option>
        {owners.map((owner) => <option key={owner.id} value={owner.id}>{owner.name} ({owner.kind})</option>)}
      </select>
    </label>
  );
}

function SubjectFields({
  subjectType,
  subjectId,
  setSubjectType,
  setSubjectId,
  contextLabel,
}: {
  subjectType: SubjectType;
  subjectId: string;
  setSubjectType: (value: SubjectType) => void;
  setSubjectId: (value: string) => void;
  contextLabel?: string;
}) {
  const prefix = contextLabel ? `${contextLabel} ` : '';
  return (
    <>
      <label style={{ display: 'grid', gap: '0.35rem', fontSize: '0.8125rem' }}>
        {prefix}Subject type
        <select aria-label={`${prefix}Subject type`} value={subjectType} onChange={(event) => setSubjectType(event.target.value as SubjectType)}>
          <option value="parcel">Parcel</option>
          <option value="unit">Unit</option>
        </select>
      </label>
      <Input label={`${prefix}${subjectType === 'parcel' ? 'Parcel' : 'Unit'} UUID`} id={`${contextLabel ?? 'filter'}-${subjectType}-uuid`} value={subjectId} onChange={(event) => setSubjectId(event.target.value)} required />
    </>
  );
}

function OwnerProfile({ owner }: { owner: Owner }) {
  return (
    <dl style={{ display: 'grid', gridTemplateColumns: 'max-content 1fr', gap: '0.35rem 1rem', fontSize: '0.875rem' }}>
      <dt style={{ color: 'var(--muted)' }}>Name</dt><dd>{owner.name}</dd>
      <dt style={{ color: 'var(--muted)' }}>Kind</dt><dd>{owner.kind}</dd>
      <dt style={{ color: 'var(--muted)' }}>Identifier</dt><dd>{owner.identifier || 'Not provided'}</dd>
      <dt style={{ color: 'var(--muted)' }}>Contact metadata</dt><dd>{Object.keys(owner.contact_metadata).length ? JSON.stringify(owner.contact_metadata) : 'Not provided'}</dd>
      <dt style={{ color: 'var(--muted)' }}>Registered</dt><dd>{formatDate(owner.created_at)}</dd>
      <dt style={{ color: 'var(--muted)' }}>Owner UUID</dt><dd>{owner.id}</dd>
    </dl>
  );
}

const cellStyle = { padding: '0.75rem', borderBottom: '1px solid var(--border)', fontSize: '0.8125rem' };
const linkButtonStyle = { background: 'none', border: 0, color: 'var(--primary)', padding: 0, textAlign: 'left' as const };
