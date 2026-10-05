import { Dialog } from '../../../components/ui/Dialog';
import { Button } from '../../../components/ui/Button';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  /** The explicit, user-facing consequence. Must not overstate severity. */
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  /** Rendered under the message, e.g. an impact summary. */
  children?: React.ReactNode;
}

/**
 * Confirmation dialog for destructive and archiving actions.
 *
 * Copy is supplied by the caller so the wording can state the *actual* backend
 * semantics: parcels and units are archived, buildings and floors are hard
 * deleted along with their children.
 */
export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  destructive = true,
  busy = false,
  onConfirm,
  onCancel,
  children,
}: ConfirmDialogProps) {
  return (
    <Dialog open={open} onClose={onCancel} title={title} maxWidth="440px">
      <p style={{ fontSize: '0.875rem', color: 'var(--foreground)', marginBottom: children ? '0.75rem' : '1.25rem' }}>
        {message}
      </p>
      {children}
      <div
        style={{
          display: 'flex',
          justifyContent: 'flex-end',
          gap: '0.5rem',
          marginTop: '1.25rem',
        }}
      >
        <Button variant="secondary" onClick={onCancel} disabled={busy}>
          {cancelLabel}
        </Button>
        <Button
          variant={destructive ? 'danger' : 'primary'}
          onClick={onConfirm}
          loading={busy}
        >
          {confirmLabel}
        </Button>
      </div>
    </Dialog>
  );
}
