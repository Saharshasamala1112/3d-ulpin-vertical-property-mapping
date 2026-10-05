interface PaginationProps {
  page: number;
  perPage: number;
  total: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onPerPageChange?: (perPage: number) => void;
  /** Per-page options exposed in the selector. */
  perPageOptions?: number[];
  disabled?: boolean;
  /** Describes what is being paginated, e.g. "parcels". */
  itemLabel?: string;
}

/**
 * Pagination control for the only paginated management resource (parcels).
 *
 * The API enforces `per_page` between 1 and 100, so options are clamped to that
 * range rather than offering values the backend would reject.
 */
export function Pagination({
  page,
  perPage,
  total,
  totalPages,
  onPageChange,
  onPerPageChange,
  perPageOptions = [10, 20, 50, 100],
  disabled = false,
  itemLabel = 'records',
}: PaginationProps) {
  const safeTotalPages = Math.max(totalPages, 1);
  const firstShown = total === 0 ? 0 : (page - 1) * perPage + 1;
  const lastShown = Math.min(page * perPage, total);

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '0.75rem',
        padding: '0.75rem 0',
        fontSize: '0.8125rem',
        color: 'var(--muted)',
      }}
    >
      <span>
        {total === 0
          ? `No ${itemLabel}`
          : `Showing ${firstShown}-${lastShown} of ${total} ${itemLabel}`}
      </span>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        {onPerPageChange && (
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
            <span>Per page</span>
            <select
              aria-label="Items per page"
              value={perPage}
              disabled={disabled}
              onChange={(event) => onPerPageChange(Number(event.target.value))}
              style={{
                padding: '0.25rem 0.5rem',
                borderRadius: '6px',
                border: '1px solid var(--input-border)',
                background: 'var(--input-bg)',
                color: 'var(--foreground)',
                fontSize: '0.8125rem',
              }}
            >
              {perPageOptions
                .filter((option) => option >= 1 && option <= 100)
                .map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
            </select>
          </label>
        )}

        <button
          type="button"
          onClick={() => onPageChange(page - 1)}
          disabled={disabled || page <= 1}
          style={navButtonStyle}
        >
          Previous
        </button>
        <span>
          Page {page} of {safeTotalPages}
        </span>
        <button
          type="button"
          onClick={() => onPageChange(page + 1)}
          disabled={disabled || page >= safeTotalPages}
          style={navButtonStyle}
        >
          Next
        </button>
      </div>
    </div>
  );
}

const navButtonStyle: React.CSSProperties = {
  padding: '0.25rem 0.625rem',
  borderRadius: '6px',
  border: '1px solid var(--border)',
  background: 'var(--surface-muted)',
  color: 'var(--foreground)',
  fontSize: '0.8125rem',
  cursor: 'pointer',
};
