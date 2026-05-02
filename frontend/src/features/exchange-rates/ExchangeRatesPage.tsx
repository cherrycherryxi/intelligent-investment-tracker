import RefreshIcon from '@mui/icons-material/Refresh';
import {
  Alert,
  Box,
  Button,
  Chip,
  Grid,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { DataTable } from '../../components/common/DataTable';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { SectionCard } from '../../components/common/SectionCard';
import { useNotification } from '../../hooks/useNotification';
import { getLatestRates, refreshRates } from '../../services/exchangeRates';
import type { ExchangeRate } from '../../types/exchangeRates';
import { DEFAULT_RATE_CURRENCIES } from '../../utils/constants';
import { formatDateTime, formatNumber, formatRelativeTime } from '../../utils/formatting';

export default function ExchangeRatesPage() {
  const notifications = useNotification();
  const queryClient = useQueryClient();
  const [currencyInput, setCurrencyInput] = useState(DEFAULT_RATE_CURRENCIES.join(','));

  const currencies = currencyInput
    .split(',')
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean);

  const query = useQuery({
    queryKey: ['exchange-rates', currencies.join(',')],
    queryFn: () => getLatestRates(currencies),
  });

  const refreshMutation = useMutation({
    mutationFn: () => refreshRates(currencies),
    onSuccess: (data) => {
      notifications.success(`已刷新 ${data.refreshed_count ?? 0} 条汇率`);
      void queryClient.invalidateQueries({ queryKey: ['exchange-rates'] });
    },
    onError: (error: { message: string }) => notifications.error(error.message),
  });

  const columns = [
    { key: 'base_currency', header: 'Base', render: (row: ExchangeRate) => row.base_currency },
    { key: 'quote_currency', header: 'Quote', render: (row: ExchangeRate) => row.quote_currency },
    { key: 'rate', header: 'Rate', align: 'right' as const, render: (row: ExchangeRate) => formatNumber(row.rate, 6) },
    { key: 'rate_timestamp', header: 'Timestamp', render: (row: ExchangeRate) => formatDateTime(row.rate_timestamp) },
    { key: 'relative', header: 'Relative', render: (row: ExchangeRate) => formatRelativeTime(row.rate_timestamp) },
    {
      key: 'is_estimated',
      header: 'Flag',
      render: (row: ExchangeRate) => (
        <Chip size="small" color={row.is_estimated ? 'warning' : 'success'} label={row.is_estimated ? 'Estimated' : 'Direct'} />
      ),
    },
  ];

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4">Exchange Rates</Typography>
        <Typography color="text.secondary">汇率数据统一经 `/api/exchange-rates/*` 获取，前端不直接访问任何外部行情源。</Typography>
      </Box>

      <SectionCard title="Rates">
        <Stack spacing={3}>
          <Grid container spacing={2}>
            <Grid item xs={12} md={8}>
              <TextField
                fullWidth
                label="Currencies"
                helperText="Comma separated, e.g. USD,EUR,JPY"
                value={currencyInput}
                onChange={(event) => setCurrencyInput(event.target.value)}
              />
            </Grid>
            <Grid item xs={12} md={4} sx={{ display: 'flex', alignItems: 'center' }}>
              <Button
                variant="contained"
                startIcon={<RefreshIcon />}
                onClick={() => refreshMutation.mutate()}
                disabled={!currencies.length || refreshMutation.isPending}
              >
                Refresh Rates
              </Button>
            </Grid>
          </Grid>

          <Alert severity="info">Estimated 标签表示后端使用了 fallback 汇率来源。</Alert>

          {query.isLoading ? <LoadingSpinner message="Loading rates..." /> : <DataTable columns={columns} rows={query.data?.rates ?? []} />}
        </Stack>
      </SectionCard>
    </Stack>
  );
}
