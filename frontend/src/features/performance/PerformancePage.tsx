import RefreshIcon from '@mui/icons-material/Refresh';
import RuleIcon from '@mui/icons-material/Rule';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import { Box, Button, Chip, Grid, Stack, Typography } from '@mui/material';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link as RouterLink } from 'react-router-dom';

import { DataTable } from '../../components/common/DataTable';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { SectionCard } from '../../components/common/SectionCard';
import { getPerformance } from '../../services/performance';
import type { AssetTypePerformance, CurrencyPerformance, RealizedClosedPosition } from '../../types/performance';
import { DEFAULT_USER_ID } from '../../utils/constants';
import { formatCurrency, formatNumber, formatPercentage } from '../../utils/formatting';

export default function PerformancePage() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ['performance', DEFAULT_USER_ID],
    queryFn: () => getPerformance(DEFAULT_USER_ID),
  });

  const overview = query.data?.overview;
  const dataQuality = query.data?.data_quality;
  const hasWarnings =
    Boolean(dataQuality?.missing_rates.length) ||
    Boolean(dataQuality?.missing_valuations.length) ||
    Boolean(dataQuality?.estimated_values.length);

  const currencyColumns = [
    { key: 'currency', header: 'Currency', render: (row: CurrencyPerformance) => row.currency },
    { key: 'cash_balance', header: 'Cash', align: 'right' as const, render: (row: CurrencyPerformance) => formatNumber(row.cash_balance, 6) },
    { key: 'current_total_assets_native', header: 'Native Assets', align: 'right' as const, render: (row: CurrencyPerformance) => formatNumber(row.current_total_assets_native, 6) },
    { key: 'current_total_assets_cny', header: 'Value CNY', align: 'right' as const, render: (row: CurrencyPerformance) => formatCurrency(row.current_total_assets_cny) },
    { key: 'historical_net_invested_native', header: 'Native Net Input', align: 'right' as const, render: (row: CurrencyPerformance) => formatNumber(row.historical_net_invested_native, 6) },
    { key: 'investment_pnl_cny', header: 'Investment PnL', align: 'right' as const, render: (row: CurrencyPerformance) => formatCurrency(row.investment_pnl_cny) },
    { key: 'fx_pnl_cny', header: 'FX PnL', align: 'right' as const, render: (row: CurrencyPerformance) => formatCurrency(row.fx_pnl_cny) },
    { key: 'current_fx_rate_to_cny', header: 'FX Rate', align: 'right' as const, render: (row: CurrencyPerformance) => formatNumber(row.current_fx_rate_to_cny, 6) },
  ];

  const assetTypeColumns = [
    { key: 'asset_type', header: 'Asset Type', render: (row: AssetTypePerformance) => row.asset_type },
    { key: 'current_value_cny', header: 'Current Value', align: 'right' as const, render: (row: AssetTypePerformance) => formatCurrency(row.current_value_cny) },
    { key: 'weight_pct', header: 'Weight', align: 'right' as const, render: (row: AssetTypePerformance) => formatPercentage(row.weight_pct) },
  ];

  const realizedColumns = [
    { key: 'asset_name', header: '产品', render: (row: RealizedClosedPosition) => row.asset_name || row.asset_code },
    { key: 'asset_code', header: '代码', render: (row: RealizedClosedPosition) => row.asset_code },
    { key: 'currency', header: '币种', render: (row: RealizedClosedPosition) => row.currency },
    { key: 'buy_native', header: '累计买入', align: 'right' as const, render: (row: RealizedClosedPosition) => formatNumber(row.buy_native, 6) },
    { key: 'sell_native', header: '累计赎回', align: 'right' as const, render: (row: RealizedClosedPosition) => formatNumber(row.sell_native, 6) },
    {
      key: 'realized_investment_pnl_native',
      header: '已实现收益(原币)',
      align: 'right' as const,
      render: (row: RealizedClosedPosition) => formatNumber(row.realized_investment_pnl_native, 6),
    },
    {
      key: 'realized_investment_pnl_cny',
      header: '已实现收益(人民币)',
      align: 'right' as const,
      render: (row: RealizedClosedPosition) => formatCurrency(row.realized_investment_pnl_cny),
    },
    { key: 'fx_rate_to_cny', header: '折算汇率', align: 'right' as const, render: (row: RealizedClosedPosition) => formatNumber(row.fx_rate_to_cny, 6) },
  ];

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4">Performance</Typography>
        <Typography color="text.secondary">组合盈亏按币种资产池计算，外币现金、估值资产和汇率影响统一折算为人民币。</Typography>
      </Box>

      <SectionCard
        title="Portfolio Performance"
        action={
          <Stack direction="row" spacing={1}>
            <Button component={RouterLink} to="/performance/audit" startIcon={<RuleIcon />}>
              Audit Data
            </Button>
            <Button startIcon={<RefreshIcon />} onClick={() => void queryClient.invalidateQueries({ queryKey: ['performance'] })}>
              Refresh
            </Button>
          </Stack>
        }
      >
        {query.isLoading ? (
          <LoadingSpinner message="Loading performance..." />
        ) : (
          <Stack spacing={3}>
            <Grid container spacing={2}>
              {[
                { label: 'Current Assets', value: formatCurrency(overview?.current_total_assets_cny) },
                { label: 'Net Invested', value: formatCurrency(overview?.net_invested_cny) },
                { label: 'Total PnL', value: formatCurrency(overview?.total_pnl_cny), tone: (overview?.total_pnl_cny ?? 0) >= 0 ? 'success' : 'error' },
                { label: 'Total Return', value: formatPercentage(overview?.total_return_pct), tone: (overview?.total_return_pct ?? 0) >= 0 ? 'success' : 'error' },
                { label: 'Investment PnL', value: formatCurrency(overview?.investment_pnl_cny), tone: (overview?.investment_pnl_cny ?? 0) >= 0 ? 'success' : 'error' },
                { label: 'Realized Investment PnL', value: formatCurrency(overview?.realized_investment_pnl_cny), tone: (overview?.realized_investment_pnl_cny ?? 0) >= 0 ? 'success' : 'error' },
                { label: 'Unrealized Investment PnL', value: formatCurrency(overview?.unrealized_investment_pnl_cny), tone: (overview?.unrealized_investment_pnl_cny ?? 0) >= 0 ? 'success' : 'error' },
                { label: 'FX PnL', value: formatCurrency(overview?.fx_pnl_cny), tone: (overview?.fx_pnl_cny ?? 0) >= 0 ? 'success' : 'error' },
              ].map((item) => (
                <Grid key={item.label} item xs={12} sm={6} lg={4}>
                  <Box sx={{ p: 2.5, borderRadius: 2, bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider' }}>
                    <Typography color="text.secondary" variant="body2">{item.label}</Typography>
                    <Typography variant="h5" color={item.tone ? `${item.tone}.main` : 'text.primary'} sx={{ mt: 1, fontWeight: 700 }}>
                      {item.value}
                    </Typography>
                  </Box>
                </Grid>
              ))}
            </Grid>

            {hasWarnings ? (
              <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
                <Chip icon={<WarningAmberIcon />} color="warning" label={`Missing rates: ${dataQuality?.missing_rates.join(', ') || 0}`} />
                <Chip icon={<WarningAmberIcon />} color="warning" label={`Missing valuations: ${dataQuality?.missing_valuations.length ?? 0}`} />
                <Chip color="info" label={`Estimated values: ${dataQuality?.estimated_values.length ?? 0}`} />
                <Chip color="info" label={`Closed realized positions: ${dataQuality?.realized_closed_positions?.length ?? 0}`} />
              </Stack>
            ) : null}

            <DataTable columns={currencyColumns} rows={query.data?.by_currency ?? []} />
            <DataTable columns={assetTypeColumns} rows={query.data?.by_asset_type ?? []} />
            <Box>
              <Typography variant="h6" sx={{ mb: 1 }}>
                已清仓产品已实现投资收益
              </Typography>
              <DataTable columns={realizedColumns} rows={query.data?.data_quality.realized_closed_positions ?? []} />
            </Box>
          </Stack>
        )}
      </SectionCard>
    </Stack>
  );
}
