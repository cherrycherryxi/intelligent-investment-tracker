import {
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TableSortLabel,
} from '@mui/material';
import type { ReactNode } from 'react';

export interface ColumnDef<T> {
  key: string;
  header: string;
  sortable?: boolean;
  align?: 'left' | 'right' | 'center';
  render: (row: T) => ReactNode;
}

interface DataTableProps<T> {
  columns: ColumnDef<T>[];
  rows: T[];
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
  onSort?: (key: string) => void;
  onRowClick?: (row: T) => void;
  page?: number;
  rowsPerPage?: number;
  totalCount?: number;
  onPageChange?: (_: unknown, page: number) => void;
}

export function DataTable<T>({
  columns,
  rows,
  sortBy,
  sortOrder,
  onSort,
  onRowClick,
  page = 0,
  rowsPerPage = rows.length || 1,
  totalCount = rows.length,
  onPageChange,
}: DataTableProps<T>) {
  return (
    <Paper variant="outlined" sx={{ overflow: 'hidden', borderRadius: 3 }}>
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              {columns.map((column) => (
                <TableCell key={column.key} align={column.align}>
                  {column.sortable && onSort ? (
                    <TableSortLabel
                      active={sortBy === column.key}
                      direction={sortBy === column.key ? sortOrder : 'asc'}
                      onClick={() => onSort(column.key)}
                    >
                      {column.header}
                    </TableSortLabel>
                  ) : (
                    column.header
                  )}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((row, index) => (
              <TableRow
                key={index}
                hover={Boolean(onRowClick)}
                onClick={() => onRowClick?.(row)}
                sx={onRowClick ? { cursor: 'pointer' } : undefined}
              >
                {columns.map((column) => (
                  <TableCell key={column.key} align={column.align}>
                    {column.render(row)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      {onPageChange ? (
        <TablePagination
          component="div"
          count={totalCount}
          page={page}
          onPageChange={onPageChange}
          rowsPerPage={rowsPerPage}
          rowsPerPageOptions={[rowsPerPage]}
        />
      ) : null}
    </Paper>
  );
}
