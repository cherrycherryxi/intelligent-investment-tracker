import RefreshIcon from '@mui/icons-material/Refresh';
import {
  Box,
  Button,
  Chip,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Stack,
  Typography,
} from '@mui/material';
import Select from '@mui/material/Select';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { DataTable } from '../../components/common/DataTable';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { SectionCard } from '../../components/common/SectionCard';
import { listPositions } from '../../services/positions';
import type { Position } from '../../types/positions';
import { DEFAULT_USER_ID } from '../../utils/constants';
import { formatCurrency, formatNumber, formatPercentage } from '../../utils/formatting';

function valueColor(value?: number | null) {
  if (value === null || value === undefined) return 'text.secondary';
  return value >= 0 ? 'success.main' : 'error.main';
}

function statusColor(status?: Position['valuation_status']) {
  if (status === 'OK') return 'success';
  if (status === 'ESTIMATED') return 'info';
  return 'warning';
}

export default function PositionsPage() {
  const [assetType, setAssetType] = useState('');
  const [sortBy, setSortBy] = useState('asset_code');
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ['positions', assetType, sortBy],
    queryFn: () =>
      listPositions({
        user_id: DEFAULT_USER_ID,
        asset_type: assetType || undefined,
        sort_by: sortBy,
      }),
  });

  const columns = [
    { key: 'asset_code', header: 'Code', sortable: true, render: (row: Position) => row.asset_code },
    { key: 'asset_type', header: 'Type', render: (row: Position) => row.asset_type },
    { key: 'currency', header: 'Currency', render: (row: Position) => row.currency ?? '-' },
    { key: 'quantity', header: 'Quantity', align: 'right' as const, render: (row: Position) => formatNumber(row.quantity, 6) },
    { key: 'cost_basis_cny', header: 'Cost', align: 'right' as const, render: (row: Position) => formatCurrency(row.cost_basis_cny) },
    { key: 'current_price', header: 'Price/Rate', align: 'right' as const, render: (row: Position) => formatNumber(row.current_price, 6) },
    { key: 'current_value_cny', header: 'Value', align: 'right' as const, render: (row: Position) => formatCurrency(row.current_value_cny) },
    {
      key: 'unrealized_pnl_cny',
      header: 'PnL',
      sortable: true,
      align: 'right' as const,
      render: (row: Position) => (
        <Typography color={valueColor(row.unrealized_pnl_cny)}>
          {formatCurrency(row.unrealized_pnl_cny)}
        </Typography>
      ),
    },
    {
      key: 'return_pct',
      header: 'Return',
      sortable: true,
      align: 'right' as const,
      render: (row: Position) => (
        <Typography color={valueColor(row.return_pct)}>
          {formatPercentage(row.return_pct)}
        </Typography>
      ),
    },
    {
      key: 'valuation_status',
      header: 'Status',
      render: (row: Position) => <Chip size="small" color={statusColor(row.valuation_status)} label={row.valuation_status ?? 'OK'} />,
    },
  ];

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4">Positions</Typography>
        <Typography color="text.secondary">实时持仓由现有 FastAPI 接口聚合，前端只负责展示、筛选和刷新。</Typography>
      </Box>

      <SectionCard
        title="Portfolio Overview"
        action={
          <Button
            startIcon={<RefreshIcon />}
            onClick={() => void queryClient.invalidateQueries({ queryKey: ['positions'] })}
          >
            Refresh
          </Button>
        }
      >
        {query.isLoading ? (
          <LoadingSpinner message="Loading positions..." />
        ) : (
          <Stack spacing={3}>
            <Grid container spacing={2}>
              {[
                { label: 'Total Cost', value: formatCurrency(query.data?.totals.total_cost_cny) },
                { label: 'Total Value', value: formatCurrency(query.data?.totals.total_value_cny) },
                { label: 'Total PnL', value: formatCurrency(query.data?.totals.total_pnl_cny), tone: (query.data?.totals.total_pnl_cny ?? 0) >= 0 ? 'success' : 'error' },
                { label: 'Total Return', value: formatPercentage(query.data?.totals.total_return_pct), tone: (query.data?.totals.total_return_pct ?? 0) >= 0 ? 'success' : 'error' },
              ].map((item) => (
                <Grid key={item.label} item xs={12} sm={6} lg={3}>
                  <Box sx={{ p: 2.5, borderRadius: 3, bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider' }}>
                    <Typography color="text.secondary" variant="body2">{item.label}</Typography>
                    <Typography variant="h5" color={item.tone ? `${item.tone}.main` : 'text.primary'} sx={{ mt: 1, fontWeight: 700 }}>
                      {item.value}
                    </Typography>
                  </Box>
                </Grid>
              ))}
            </Grid>

            <Grid container spacing={2}>
              <Grid item xs={12} sm={3}>
                <FormControl fullWidth>
                  <InputLabel>Asset Type</InputLabel>
                  <Select value={assetType} label="Asset Type" onChange={(event) => setAssetType(event.target.value)}>
                    <MenuItem value="">All</MenuItem>
                    <MenuItem value="CASH">CASH</MenuItem>
                    <MenuItem value="FOREX">FOREX</MenuItem>
                    <MenuItem value="BOND">BOND</MenuItem>
                    <MenuItem value="FUND">FUND</MenuItem>
                    <MenuItem value="WEALTH_PRODUCT">WEALTH_PRODUCT</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} sm={3}>
                <FormControl fullWidth>
                  <InputLabel>Sort By</InputLabel>
                  <Select value={sortBy} label="Sort By" onChange={(event) => setSortBy(event.target.value)}>
                    <MenuItem value="asset_code">Asset Code</MenuItem>
                    <MenuItem value="pnl">PnL</MenuItem>
                    <MenuItem value="return_pct">Return %</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} sm={6} sx={{ display: 'flex', alignItems: 'center' }}>
                <Stack direction="row" spacing={1}>
                  <Chip label={`${query.data?.positions.length ?? 0} positions`} />
                  <Chip color="success" label="Green = gain" />
                  <Chip color="error" label="Red = loss" />
                  <Chip color="warning" label={`Missing rates: ${query.data?.totals.missing_rates?.length ?? 0}`} />
                  <Chip color="warning" label={`Missing valuations: ${query.data?.totals.missing_valuations?.length ?? 0}`} />
                </Stack>
              </Grid>
            </Grid>

            <DataTable columns={columns} rows={query.data?.positions ?? []} />
          </Stack>
        )}
      </SectionCard>
    </Stack>
  );
}
