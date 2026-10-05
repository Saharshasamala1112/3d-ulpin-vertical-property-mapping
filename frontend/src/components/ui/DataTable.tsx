import type { ReactNode } from 'react';

export interface DataTableColumn<T> {
  key: string;
  header: string;
  /** Cell renderer. Return a string for plain text or any node for rich cells. */
  render: (row: T) => ReactNode;
  /** Optional right/left alignment override. */
  align?: 'left' | 'right' | 'center';
  style?: React.CSSProperties;
}

interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  caption?: string;
  emptyMessage?: string;
}

const cellBase: React.CSSProperties = {
  padding: '0.625rem 0.75rem',
  fontSize: '0.8125rem',
  borderBottom: '1px solid var(--border)',
  textAlign: 'left',
  verticalAlign: 'top',
};

/**
 * Minimal presentational table used by the management pages.
 *
 * Intentionally generic: it owns layout only. Loading, empty, and error states
 * are rendered by the page so each screen can decide its own feedback.
 */
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  caption,
  emptyMessage = 'No records found.',
}: DataTableProps<T>) {
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        {caption && <caption style={{ textAlign: 'left', padding: '0 0 0.5rem', fontSize: '0.75rem', color: 'var(--muted)' }}>{caption}</caption>}
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                style={{
                  ...cellBase,
                  fontWeight: 600,
                  color: 'var(--muted)',
                  whiteSpace: 'nowrap',
                  ...(column.align ? { textAlign: column.align } : null),
                  ...column.style,
                }}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                style={{ ...cellBase, color: 'var(--muted)', textAlign: 'center', padding: '1.5rem' }}
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr key={rowKey(row)}>
                {columns.map((column) => (
                  <td
                    key={column.key}
                    style={{
                      ...cellBase,
                      ...(column.align ? { textAlign: column.align } : null),
                      ...column.style,
                    }}
                  >
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
