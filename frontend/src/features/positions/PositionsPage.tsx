import RefreshIcon from '@mui/icons-material/Refresh';
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import Select from '@mui/material/Select';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { DataTable } from '../../components/common/DataTable';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { SectionCard } from '../../components/common/SectionCard';
import { useNotification } from '../../hooks/useNotification';
import { createValuation, listPositions } from '../../services/positions';
import type { Position } from '../../types/positions';
import { DEFAULT_USER_ID } from '../../utils/constants';
import { formatCurrency, formatNumber, formatPercentage, toDatetimeLocalValue } from '../../utils/formatting';

function valueColor(value?: number | null) {
  if (value === null || value === undefined) return 'text.secondary';
  return value >= 0 ? 'success.main' : 'error.main';
}

function statusColor(status?: Position['valuation_status']) {
  if (status === 'OK') return 'success';
  if (status === 'ESTIMATED') return 'info';
  return 'warning';
}

function attributionColor(status?: Position['attribution_status']) {
  if (status === 'COMPLETE' || status === 'NOT_APPLICABLE') return 'success';
  if (status === 'BASIS_MISSING') return 'error';
  return 'warning';
}

function formatPositionCost(row: Position): string {
  if (row.currency && row.currency !== 'CNY' && row.native_cost !== null && row.native_cost !== undefined) {
    return `${formatNumber(row.native_cost, 6)} ${row.currency}`;
  }
  if (row.cost_basis_cny !== null && row.cost_basis_cny !== undefined) {
    return formatCurrency(row.cost_basis_cny);
  }
  if (row.native_cost !== null && row.native_cost !== undefined && row.currency) {
    return `${formatNumber(row.native_cost, 6)} ${row.currency}`;
  }
  return '-';
}

function formatAttributionCost(row: Position): string {
  if (row.attributed_cost_basis_cny !== null && row.attributed_cost_basis_cny !== undefined) {
    return formatCurrency(row.attributed_cost_basis_cny);
  }
  return '-';
}

function formatLegacyCost(row: Position): string {
  if (row.legacy_cost_basis_cny !== null && row.legacy_cost_basis_cny !== undefined) {
    return formatCurrency(row.legacy_cost_basis_cny);
  }
  if (row.cost_basis_cny !== null && row.cost_basis_cny !== undefined) {
    return formatCurrency(row.cost_basis_cny);
  }
  return '-';
}

function formatCostDiff(row: Position): string {
  if (row.attributed_cost_basis_cny === null || row.attributed_cost_basis_cny === undefined) return '-';
  if (row.legacy_cost_basis_cny === null || row.legacy_cost_basis_cny === undefined) return '-';
  return formatCurrency(row.attributed_cost_basis_cny - row.legacy_cost_basis_cny);
}

function formatHoldingAmount(row: Position): string {
  const amount = row.current_value_native ?? row.quantity;
  const formatted = formatNumber(amount, 6);
  return row.currency ? `${formatted} ${row.currency}` : formatted;
}

function isAmountValuedPosition(row: Position): boolean {
  return row.asset_type === 'BOND' || row.asset_type === 'FUND' || row.asset_type === 'WEALTH_PRODUCT';
}

export default function PositionsPage() {
  const [assetType, setAssetType] = useState('');
  const [sortBy, setSortBy] = useState('asset_code');
  const [snapshotTarget, setSnapshotTarget] = useState<Position | null>(null);
  const [snapshotValue, setSnapshotValue] = useState('');
  const [snapshotQuantity, setSnapshotQuantity] = useState('');
  const [snapshotTime, setSnapshotTime] = useState(toDatetimeLocalValue(new Date().toISOString()));
  const [savingSnapshot, setSavingSnapshot] = useState(false);
  const queryClient = useQueryClient();
  const notification = useNotification();

  const query = useQuery({
    queryKey: ['positions', assetType, sortBy],
    queryFn: () =>
      listPositions({
        user_id: DEFAULT_USER_ID,
        asset_type: assetType || undefined,
        sort_by: sortBy,
      }),
  });

  const openSnapshotDialog = (row: Position) => {
    setSnapshotTarget(row);
    setSnapshotValue(row.current_value_native?.toString() ?? row.quantity.toString());
    setSnapshotQuantity((row.ledger_quantity ?? row.quantity).toString());
    setSnapshotTime(toDatetimeLocalValue(new Date().toISOString()));
  };

  const submitSnapshot = async () => {
    if (!snapshotTarget?.asset_id) return;
    const marketValue = Number(snapshotValue);
    const quantity = Number(snapshotQuantity);
    if (!Number.isFinite(marketValue) || marketValue < 0) {
      notification.error('当前市值必须是有效的非负数字。');
      return;
    }
    if (!Number.isFinite(quantity) || quantity < 0) {
      notification.error('持仓份额必须是有效的非负数字。');
      return;
    }
    setSavingSnapshot(true);
    try {
      await createValuation({
        user_id: DEFAULT_USER_ID,
        asset_id: snapshotTarget.asset_id,
        valuation_time: new Date(snapshotTime).toISOString(),
        quantity,
        price: quantity > 0 ? marketValue / quantity : null,
        market_value: marketValue,
        currency: snapshotTarget.currency,
        source: 'manual',
        is_estimated: false,
      });
      notification.success('持仓快照已保存。');
      setSnapshotTarget(null);
      await queryClient.invalidateQueries({ queryKey: ['positions'] });
      await queryClient.invalidateQueries({ queryKey: ['performance'] });
      await queryClient.invalidateQueries({ queryKey: ['performance-audit'] });
    } catch (error) {
      notification.error(error instanceof Error ? error.message : '保存持仓快照失败。');
    } finally {
      setSavingSnapshot(false);
    }
  };

  const columns = [
    {
      key: 'asset_name',
      header: '产品',
      sortable: true,
      render: (row: Position) => (
        <Stack spacing={0.25}>
          <Typography>{row.asset_name || row.asset_code}</Typography>
          <Typography variant="caption" color="text.secondary">
            {row.asset_code}
          </Typography>
        </Stack>
      ),
    },
    { key: 'asset_type', header: '资产类型', render: (row: Position) => row.asset_type },
    { key: 'currency', header: '币种', render: (row: Position) => row.currency ?? '-' },
    { key: 'quantity', header: '持仓份额/数量', align: 'right' as const, render: (row: Position) => formatNumber(row.quantity, 6) },
    { key: 'current_value_native', header: '持仓金额', align: 'right' as const, render: (row: Position) => formatHoldingAmount(row) },
    { key: 'native_cost', header: '原币成本', align: 'right' as const, render: (row: Position) => formatPositionCost(row) },
    { key: 'attributed_cost_basis_cny', header: '归因成本(人民币)', align: 'right' as const, render: (row: Position) => formatAttributionCost(row) },
    { key: 'legacy_cost_basis_cny', header: '旧口径成本(人民币)', align: 'right' as const, render: (row: Position) => formatLegacyCost(row) },
    {
      key: 'cost_diff',
      header: '成本差异',
      align: 'right' as const,
      render: (row: Position) => (
        <Typography color={valueColor((row.attributed_cost_basis_cny ?? 0) - (row.legacy_cost_basis_cny ?? 0))}>
          {formatCostDiff(row)}
        </Typography>
      ),
    },
    { key: 'current_price', header: '价格/汇率', align: 'right' as const, render: (row: Position) => formatNumber(row.current_price, 6) },
    { key: 'current_value_cny', header: '当前市值', align: 'right' as const, render: (row: Position) => formatCurrency(row.current_value_cny) },
    {
      key: 'investment_pnl_cny',
      header: '投资收益',
      align: 'right' as const,
      render: (row: Position) => (
        <Typography color={valueColor(row.investment_pnl_cny)}>
          {formatCurrency(row.investment_pnl_cny)}
        </Typography>
      ),
    },
    {
      key: 'fx_pnl_cny',
      header: '汇率收益',
      align: 'right' as const,
      render: (row: Position) => (
        <Typography color={valueColor(row.fx_pnl_cny)}>
          {formatCurrency(row.fx_pnl_cny)}
        </Typography>
      ),
    },
    {
      key: 'unrealized_pnl_cny',
      header: '总收益',
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
      header: '收益率',
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
      header: '估值状态',
      render: (row: Position) => <Chip size="small" color={statusColor(row.valuation_status)} label={row.valuation_status ?? 'OK'} />,
    },
    {
      key: 'attribution_status',
      header: '资金归因',
      render: (row: Position) => (
        <Stack spacing={0.5}>
          <Chip size="small" color={attributionColor(row.attribution_status)} label={row.attribution_status ?? '-'} />
          {row.attribution_summary ? (
            <Typography variant="caption" color="text.secondary">
              {row.attribution_summary.total_lots_used} lots · {row.attribution_summary.gap_count} gaps
            </Typography>
          ) : null}
        </Stack>
      ),
    },
    {
      key: 'actions',
      header: '操作',
      render: (row: Position) =>
        isAmountValuedPosition(row) && row.asset_id ? (
          <Button size="small" onClick={() => openSnapshotDialog(row)}>
            Snapshot
          </Button>
        ) : null,
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
                { label: 'Investment PnL', value: formatCurrency(query.data?.totals.total_investment_pnl_cny), tone: (query.data?.totals.total_investment_pnl_cny ?? 0) >= 0 ? 'success' : 'error' },
                { label: 'FX PnL', value: formatCurrency(query.data?.totals.total_fx_pnl_cny), tone: (query.data?.totals.total_fx_pnl_cny ?? 0) >= 0 ? 'success' : 'error' },
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
                    <MenuItem value="asset_code">Product</MenuItem>
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

            <DataTable columns={columns} rows={query.data?.positions ?? []} stickyHeader maxHeight={640} />
          </Stack>
        )}
      </SectionCard>

      <Dialog open={Boolean(snapshotTarget)} onClose={() => setSnapshotTarget(null)} fullWidth maxWidth="sm">
        <DialogTitle>补充持仓快照</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <Box>
              <Typography fontWeight={700}>{snapshotTarget?.asset_name || snapshotTarget?.asset_code}</Typography>
              <Typography variant="body2" color="text.secondary">
                {snapshotTarget?.asset_code} · {snapshotTarget?.currency}
              </Typography>
            </Box>
            <TextField
              label="持仓份额"
              type="number"
              value={snapshotQuantity}
              onChange={(event) => setSnapshotQuantity(event.target.value)}
              helperText="基金/理财页面展示的当前份额；没有份额时可先填当前持仓金额。"
              fullWidth
            />
            <TextField
              label="当前市值"
              type="number"
              value={snapshotValue}
              onChange={(event) => setSnapshotValue(event.target.value)}
              helperText={`以 ${snapshotTarget?.currency ?? '原币'} 计价的当前持仓金额。`}
              fullWidth
            />
            <TextField
              label="快照时间"
              type="datetime-local"
              value={snapshotTime}
              onChange={(event) => setSnapshotTime(event.target.value)}
              InputLabelProps={{ shrink: true }}
              fullWidth
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSnapshotTarget(null)}>取消</Button>
          <Button variant="contained" disabled={savingSnapshot} onClick={() => void submitSnapshot()}>
            保存
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
