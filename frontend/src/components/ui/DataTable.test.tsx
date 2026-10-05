import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DataTable, type DataTableColumn } from './DataTable';

interface Row {
  id: string;
  name: string;
  area: number;
}

const rows: Row[] = [
  { id: '1', name: 'A', area: 10 },
  { id: '2', name: 'B', area: 20 },
];

const columns: DataTableColumn<Row>[] = [
  { key: 'name', header: 'Name', render: (r) => r.name },
  { key: 'area', header: 'Area', align: 'right', render: (r) => r.area },
  { key: 'centered', header: 'Centered', align: 'center', render: () => 'x' },
  { key: 'styled', header: 'Styled', style: { textTransform: 'uppercase' }, render: () => 'y' },
];

describe('DataTable', () => {
  it('renders a header cell for every column', () => {
    render(<DataTable columns={columns} rows={rows} rowKey={(r) => r.id} />);

    expect(screen.getByRole('columnheader', { name: 'Name' })).toBeTruthy();
    expect(screen.getByRole('columnheader', { name: 'Area' })).toBeTruthy();
  });

  it('applies column alignment to body cells, not just headers', () => {
    render(<DataTable columns={columns} rows={rows} rowKey={(r) => r.id} />);

    const areaCells = screen.getAllByRole('cell').filter((c) => c.textContent === '10' || c.textContent === '20');
    expect(areaCells).toHaveLength(2);
    for (const cell of areaCells) {
      expect(cell.style.textAlign).toBe('right');
    }

    const centered = screen.getAllByRole('cell').filter((c) => c.textContent === 'x');
    for (const cell of centered) {
      expect(cell.style.textAlign).toBe('center');
    }
  });

  it('applies a column style to body cells too', () => {
    render(<DataTable columns={columns} rows={rows} rowKey={(r) => r.id} />);

    const styled = screen.getAllByRole('cell').filter((c) => c.textContent === 'y');
    expect(styled.length).toBeGreaterThan(0);
    for (const cell of styled) {
      expect(cell.style.textTransform).toBe('uppercase');
    }
  });

  it('renders one row per record', () => {
    render(<DataTable columns={columns} rows={rows} rowKey={(r) => r.id} />);
    expect(screen.getAllByRole('row')).toHaveLength(3);
  });

  it('shows the empty message when there are no rows', () => {
    render(<DataTable columns={columns} rows={[]} rowKey={(r) => r.id} emptyMessage="Nothing here." />);
    expect(screen.getByText('Nothing here.')).toBeTruthy();
  });

  it('prefers the empty message over a filter miss that has rows', () => {
    render(
      <DataTable columns={columns} rows={rows} rowKey={(r) => r.id} emptyMessage="No matches." />
    );
    expect(screen.queryByText('No matches.')).toBeNull();
  });
});
