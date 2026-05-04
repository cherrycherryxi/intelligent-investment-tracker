import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import {
  Alert,
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
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMemo, useState } from 'react';

import { DataTable } from '../../components/common/DataTable';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { SectionCard } from '../../components/common/SectionCard';
import { useDebounce } from '../../hooks/useDebounce';
import { useNotification } from '../../hooks/useNotification';
import {
  createPortfolioEvent,
  createTransaction,
  deleteTransactionRecord,
  listTransactions,
  updateHistoricalRate,
  updateTransactionRecord,
} from '../../services/transactions';
import type {
  AssetType,
  ManualAssetType,
  PortfolioAssetEntryPayload,
  Transaction,
  TransactionDirection,
} from '../../types/transactions';
import { DEFAULT_USER_ID, FILTER_DEBOUNCE_MS, PAGE_SIZE } from '../../utils/constants';
import {
  formatCurrency,
  formatDateTime,
  formatNumber,
  formatRelativeTime,
  toDatetimeLocalValue,
} from '../../utils/formatting';
import { transactionSchema, type TransactionFormValues } from '../../utils/validation';

type SortField = 'trade_time' | 'asset_code' | 'total_cost_cny';

const MANUAL_ASSET_TYPES: ManualAssetType[] = ['FOREX', 'FX_SWAP', 'BOND', 'FUND', 'WEALTH_PRODUCT', 'INTEREST_INCOME'];
const HISTORY_DIRECTIONS: Array<TransactionDirection | ''> = ['', 'BUY', 'SELL', 'SWAP', 'INCOME', 'REINVEST'];
const PORTFOLIO_ASSET_TYPES = new Set<ManualAssetType>(['FUND', 'WEALTH_PRODUCT']);

function portfolioEventType(assetType: ManualAssetType, direction: 'BUY' | 'SELL'): string {
  if (assetType === 'FUND') {
    return direction === 'BUY' ? 'FUND_BUY' : 'FUND_SELL';
  }
  if (assetType === 'WEALTH_PRODUCT') {
    return direction === 'BUY' ? 'WEALTH_BUY' : 'WEALTH_REDEEM';
  }
  return direction === 'BUY' ? `${assetType}_BUY` : `${assetType}_SELL`;
}

function signedTotalCost(row: Transaction): number | null | undefined {
  if (row.signed_total_cost_cny !== null && row.signed_total_cost_cny !== undefined) {
    return row.signed_total_cost_cny;
  }
  if (row.total_cost_cny === null || row.total_cost_cny === undefined) {
    return row.total_cost_cny;
  }
  return row.direction === 'SELL' ? -Math.abs(row.total_cost_cny) : row.total_cost_cny;
}

function signedTradeAmount(row: Transaction): number | null | undefined {
  if (row.signed_trade_amount !== null && row.signed_trade_amount !== undefined) {
    return row.signed_trade_amount;
  }
  if (row.trade_amount !== null && row.trade_amount !== undefined) {
    return row.direction === 'SELL' ? -Math.abs(row.trade_amount) : row.trade_amount;
  }
  if (row.quantity !== null && row.quantity !== undefined && row.unit_price !== null && row.unit_price !== undefined) {
    const value = row.quantity * row.unit_price;
    return row.direction === 'SELL' ? -Math.abs(value) : value;
  }
  return null;
}

function formatTradeValue(row: Transaction): string {
  const costCny = signedTotalCost(row);
  if (costCny !== null && costCny !== undefined) {
    return formatCurrency(costCny);
  }
  const amount = signedTradeAmount(row);
  if (amount === null || amount === undefined) {
    return '-';
  }
  const currency = row.trade_amount_currency || row.trade_currency;
  if (currency === 'CNY') {
    return formatCurrency(amount);
  }
  return `${formatNumber(amount, 6)} ${currency}`;
}

function directionColor(direction: TransactionDirection) {
  if (direction === 'BUY') return 'success';
  if (direction === 'SELL') return 'warning';
  if (direction === 'INCOME') return 'info';
  return 'default';
}

function TransactionForm() {
  const notifications = useNotification();
  const queryClient = useQueryClient();
  const form = useForm<TransactionFormValues>({
    resolver: zodResolver(transactionSchema),
    defaultValues: {
      asset_type: 'FOREX',
      asset_code: '',
      asset_name: '',
      direction: 'BUY',
      quantity: 0,
      unit_price: 0,
      trade_currency: 'CNY',
      trade_time: toDatetimeLocalValue(new Date().toISOString()),
      notes: '',
    },
  });

  const quantity = form.watch('quantity');
  const unitPrice = form.watch('unit_price');
  const assetType = form.watch('asset_type');
  const tradeCurrency = form.watch('trade_currency');
  const assetCode = form.watch('asset_code');
  const totalCost = (quantity || 0) * (unitPrice || 0);
  const isFxSwap = assetType === 'FX_SWAP';
  const isInterestIncome = assetType === 'INTEREST_INCOME';
  const isPortfolioAsset = PORTFOLIO_ASSET_TYPES.has(assetType);
  const nativeAmountLabel = `${formatNumber(totalCost || 0, 6)} ${tradeCurrency || '-'}`;

  const mutation = useMutation({
    mutationFn: async (values: TransactionFormValues) => {
      const tradeTime = values.trade_time;
      const currency = values.trade_currency.toUpperCase();
      if (values.asset_type === 'FX_SWAP') {
        const buyCurrency = values.asset_code.toUpperCase();
        const buyAmount = values.quantity;
        const sellAmount = values.unit_price;
        return createPortfolioEvent({
          user_id: DEFAULT_USER_ID,
          event_type: 'FX_SWAP',
          event_time: tradeTime,
          source: 'manual',
          status: 'CONFIRMED',
          notes: values.notes?.trim() || undefined,
          cash_entries: [
            {
              currency,
              amount_delta: -sellAmount,
              is_external_flow: false,
              description: `Manual FX swap out ${currency}`,
            },
            {
              currency: buyCurrency,
              amount_delta: buyAmount,
              is_external_flow: false,
              description: `Manual FX swap in ${buyCurrency}`,
            },
          ],
        });
      }
      if (values.asset_type === 'INTEREST_INCOME') {
        return createPortfolioEvent({
          user_id: DEFAULT_USER_ID,
          event_type: 'INTEREST_INCOME',
          event_time: tradeTime,
          source: 'manual',
          status: 'CONFIRMED',
          notes: values.notes?.trim() || values.asset_name?.trim() || undefined,
          cash_entries: [
            {
              currency,
              amount_delta: values.quantity,
              is_external_flow: false,
              description: values.notes?.trim() || values.asset_name?.trim() || 'Manual interest income',
            },
          ],
          asset_entries: [],
        });
      }
      if (PORTFOLIO_ASSET_TYPES.has(values.asset_type)) {
        const nativeAmount = values.quantity * values.unit_price;
        const isBuy = values.direction === 'BUY';
        const assetEntry: PortfolioAssetEntryPayload = {
          asset: {
            asset_type: values.asset_type as AssetType,
            asset_code: values.asset_code,
            asset_name: values.asset_name?.trim() || undefined,
            currency,
          },
          quantity_delta: isBuy ? values.quantity : -values.quantity,
          cash_currency: currency,
          cash_amount: nativeAmount,
          unit_price: values.unit_price,
          description: values.notes?.trim() || undefined,
        };
        return createPortfolioEvent({
          user_id: DEFAULT_USER_ID,
          event_type: portfolioEventType(values.asset_type, values.direction),
          event_time: tradeTime,
          source: 'manual',
          status: 'CONFIRMED',
          notes: values.notes?.trim() || undefined,
          cash_entries: [
            {
              currency,
              amount_delta: isBuy ? -nativeAmount : nativeAmount,
              is_external_flow: false,
              description: values.notes?.trim() || `${values.asset_type} ${isBuy ? 'purchase' : 'redemption'} cash flow`,
            },
          ],
          asset_entries: [assetEntry],
        });
      }
      return createTransaction({
        user_id: DEFAULT_USER_ID,
        ...values,
        asset_type: values.asset_type as Exclude<TransactionFormValues['asset_type'], 'FX_SWAP' | 'INTEREST_INCOME'>,
        asset_name: values.asset_name?.trim() || undefined,
        notes: values.notes?.trim() || undefined,
        trade_time: tradeTime,
        total_cost_cny: totalCost || undefined,
        exchange_rate_to_cny: values.trade_currency.toUpperCase() === 'CNY' ? 1 : values.exchange_rate_to_cny,
        source: 'manual',
      });
    },
    onSuccess: () => {
      notifications.success('交易创建成功');
      form.reset({
        asset_type: 'FOREX',
        asset_code: '',
        asset_name: '',
        direction: 'BUY',
        quantity: 0,
        unit_price: 0,
        trade_currency: 'CNY',
        trade_time: toDatetimeLocalValue(new Date().toISOString()),
        notes: '',
      });
      void queryClient.invalidateQueries({ queryKey: ['transactions'] });
      void queryClient.invalidateQueries({ queryKey: ['positions'] });
      void queryClient.invalidateQueries({ queryKey: ['performance'] });
    },
    onError: (error: { message: string }) => notifications.error(error.message),
  });

  return (
    <SectionCard title="Manual Entry">
      <Box
        component="form"
        onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
      >
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6}>
            <Controller
              name="asset_type"
              control={form.control}
              render={({ field }) => (
                <FormControl fullWidth>
                  <InputLabel>Asset Type</InputLabel>
                  <Select
                    {...field}
                    label="Asset Type"
                    onChange={(event) => {
                      const nextAssetType = event.target.value as ManualAssetType;
                      field.onChange(nextAssetType);
                      if (nextAssetType === 'INTEREST_INCOME') {
                        form.setValue('direction', 'BUY');
                        form.setValue('unit_price', 1);
                        if (!form.getValues('asset_code')) {
                          form.setValue('asset_code', form.getValues('trade_currency') || 'USD');
                        }
                      }
                      if (PORTFOLIO_ASSET_TYPES.has(nextAssetType) && !form.getValues('unit_price')) {
                        form.setValue('unit_price', 1);
                      }
                    }}
                  >
                    {MANUAL_ASSET_TYPES.map((assetType) => (
                      <MenuItem key={assetType} value={assetType}>
                        {assetType}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              )}
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label={isFxSwap ? 'Buy Currency' : isInterestIncome ? 'Income Currency' : 'Asset Code'}
              {...form.register('asset_code')}
              error={Boolean(form.formState.errors.asset_code)}
              helperText={form.formState.errors.asset_code?.message}
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField fullWidth label={isInterestIncome ? 'Income Name' : 'Asset Name'} {...form.register('asset_name')} />
          </Grid>
          <Grid item xs={12} sm={6}>
            <Controller
              name="direction"
              control={form.control}
              render={({ field }) => (
                <FormControl fullWidth>
                  <InputLabel>Direction</InputLabel>
                  <Select {...field} label="Direction" disabled={isInterestIncome}>
                    <MenuItem value="BUY">BUY</MenuItem>
                    <MenuItem value="SELL">SELL</MenuItem>
                  </Select>
                </FormControl>
              )}
            />
          </Grid>
          <Grid item xs={12} sm={4}>
            <TextField
              fullWidth
              label={isFxSwap ? 'Buy Amount' : isInterestIncome ? 'Income Amount' : 'Quantity'}
              type="number"
              inputProps={{ step: '0.000001' }}
              {...form.register('quantity', { valueAsNumber: true })}
              error={Boolean(form.formState.errors.quantity)}
              helperText={form.formState.errors.quantity?.message}
            />
          </Grid>
          <Grid item xs={12} sm={4}>
            <TextField
              fullWidth
              label={isFxSwap ? 'Sell Amount' : isInterestIncome ? 'Fixed At 1' : 'Unit Price'}
              type="number"
              inputProps={{ step: '0.000001' }}
              disabled={isInterestIncome}
              {...form.register('unit_price', { valueAsNumber: true })}
              error={Boolean(form.formState.errors.unit_price)}
              helperText={form.formState.errors.unit_price?.message}
            />
          </Grid>
          <Grid item xs={12} sm={4}>
            <TextField
              fullWidth
              label={isFxSwap ? 'Sell Currency' : isInterestIncome ? 'Income Currency' : 'Trade Currency'}
              {...form.register('trade_currency')}
              error={Boolean(form.formState.errors.trade_currency)}
              helperText={form.formState.errors.trade_currency?.message}
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="Trade Time"
              type="datetime-local"
              InputLabelProps={{ shrink: true }}
              {...form.register('trade_time')}
              error={Boolean(form.formState.errors.trade_time)}
              helperText={form.formState.errors.trade_time?.message}
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label={isFxSwap ? 'Not required for FX_SWAP' : 'Exchange Rate To CNY'}
              type="number"
              inputProps={{ step: '0.000001' }}
              disabled={isFxSwap || isInterestIncome || isPortfolioAsset}
              {...form.register('exchange_rate_to_cny', { valueAsNumber: true })}
              error={Boolean(form.formState.errors.exchange_rate_to_cny)}
              helperText={
                isFxSwap || isInterestIncome || isPortfolioAsset
                  ? '该类型按原币现金流入账，不在这里填写人民币成本'
                  : form.formState.errors.exchange_rate_to_cny?.message
              }
            />
          </Grid>
          <Grid item xs={12}>
            <TextField fullWidth label="Notes" multiline minRows={3} {...form.register('notes')} />
          </Grid>
          <Grid item xs={12}>
            <Alert severity="info" icon={<InfoOutlinedIcon fontSize="inherit" />}>
              {isFxSwap
                ? `Swap: ${(unitPrice || 0).toLocaleString()} ${tradeCurrency || '-'} -> ${(quantity || 0).toLocaleString()} ${assetCode || '-'}`
                : isInterestIncome
                  ? `Interest Income: ${(quantity || 0).toLocaleString()} ${tradeCurrency || '-'}`
                  : isPortfolioAsset
                    ? `Native Amount: ${nativeAmountLabel}`
                : `Total Cost: ${formatCurrency(totalCost || 0)}`}
            </Alert>
          </Grid>
          <Grid item xs={12}>
            <Button type="submit" variant="contained" disabled={mutation.isPending}>
              Create Transaction
            </Button>
          </Grid>
        </Grid>
      </Box>
    </SectionCard>
  );
}

export default function TransactionsPage() {
  const notifications = useNotification();
  const queryClient = useQueryClient();
  const [assetCode, setAssetCode] = useState('');
  const [direction, setDirection] = useState('');
  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');
  const [page, setPage] = useState(0);
  const [sortBy, setSortBy] = useState<SortField>('trade_time');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [selectedTransaction, setSelectedTransaction] = useState<Transaction | null>(null);
  const [editTradeTime, setEditTradeTime] = useState('');
  const [editNotes, setEditNotes] = useState('');

  const debouncedAssetCode = useDebounce(assetCode, FILTER_DEBOUNCE_MS);
  const debouncedStartTime = useDebounce(startTime, FILTER_DEBOUNCE_MS);
  const debouncedEndTime = useDebounce(endTime, FILTER_DEBOUNCE_MS);

  const query = useQuery({
    queryKey: ['transactions', debouncedAssetCode, direction, debouncedStartTime, debouncedEndTime],
    queryFn: () =>
      listTransactions({
        user_id: DEFAULT_USER_ID,
        asset_code: debouncedAssetCode.trim() || undefined,
        direction: (direction as TransactionDirection | '') || undefined,
        start_time: debouncedStartTime ? new Date(debouncedStartTime).toISOString() : undefined,
        end_time: debouncedEndTime ? new Date(debouncedEndTime).toISOString() : undefined,
        limit: 500,
      }),
  });

  const invalidateTransactionViews = () => {
    void queryClient.invalidateQueries({ queryKey: ['transactions'] });
    void queryClient.invalidateQueries({ queryKey: ['positions'] });
    void queryClient.invalidateQueries({ queryKey: ['performance'] });
  };

  const updateMutation = useMutation({
    mutationFn: (row: Transaction) =>
      updateTransactionRecord(row.record_type ?? 'TRANSACTION', row.id, {
        trade_time: editTradeTime,
        notes: editNotes,
      }),
    onSuccess: (row) => {
      notifications.success('记录已更新');
      setSelectedTransaction(row);
      setEditTradeTime(toDatetimeLocalValue(row.trade_time));
      setEditNotes(row.notes ?? '');
      invalidateTransactionViews();
    },
    onError: (error: { message: string }) => notifications.error(error.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (row: Transaction) => deleteTransactionRecord(row.record_type ?? 'TRANSACTION', row.id),
    onSuccess: () => {
      notifications.success('记录已删除');
      setSelectedTransaction(null);
      invalidateTransactionViews();
    },
    onError: (error: { message: string }) => notifications.error(error.message),
  });

  const rateMutation = useMutation({
    mutationFn: (row: Transaction) => updateHistoricalRate(row.record_type ?? 'TRANSACTION', row.id),
    onSuccess: (row) => {
      notifications.success('历史汇率已更新');
      setSelectedTransaction(row);
      invalidateTransactionViews();
    },
    onError: (error: { message: string }) => notifications.error(error.message),
  });

  const sortedRows = useMemo(() => {
    const rows = [...(query.data ?? [])];
    rows.sort((left, right) => {
      const factor = sortOrder === 'asc' ? 1 : -1;
      if (sortBy === 'asset_code') {
        return left.asset_code.localeCompare(right.asset_code) * factor;
      }
      if (sortBy === 'total_cost_cny') {
        return ((signedTotalCost(left) ?? signedTradeAmount(left) ?? 0) - (signedTotalCost(right) ?? signedTradeAmount(right) ?? 0)) * factor;
      }
      return (new Date(left.trade_time).getTime() - new Date(right.trade_time).getTime()) * factor;
    });
    return rows;
  }, [query.data, sortBy, sortOrder]);

  const pagedRows = useMemo(
    () => sortedRows.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE),
    [page, sortedRows],
  );

  const columns = [
    { key: 'asset_type', header: 'Asset', render: (row: Transaction) => row.asset_type },
    { key: 'asset_code', header: 'Code', sortable: true, render: (row: Transaction) => row.asset_code },
    {
      key: 'direction',
      header: 'Direction',
      render: (row: Transaction) => (
        <Chip size="small" label={row.direction} color={directionColor(row.direction)} />
      ),
    },
    { key: 'quantity', header: 'Quantity', align: 'right' as const, render: (row: Transaction) => formatNumber(row.quantity, 6) },
    { key: 'unit_price', header: 'Unit Price', align: 'right' as const, render: (row: Transaction) => formatNumber(row.unit_price, 6) },
    { key: 'trade_time', header: 'Trade Time', sortable: true, render: (row: Transaction) => formatDateTime(row.trade_time) },
    {
      key: 'total_cost_cny',
      header: 'Total Cost',
      sortable: true,
      align: 'right' as const,
      render: (row: Transaction) => formatTradeValue(row),
    },
  ];

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4">Transactions</Typography>
        <Typography color="text.secondary">
          Frontend pagination and sorting are kept inside the SPA, while the backend remains a pure API.
        </Typography>
      </Box>

      <Grid container spacing={3}>
        <Grid item xs={12} xl={8}>
          <SectionCard title="Transaction History">
            <Stack spacing={2}>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    label="Asset Code"
                    value={assetCode}
                    onChange={(event) => {
                      setAssetCode(event.target.value);
                      setPage(0);
                    }}
                  />
                </Grid>
                <Grid item xs={12} sm={3}>
                  <FormControl fullWidth>
                    <InputLabel>Direction</InputLabel>
                    <Select
                      value={direction}
                      label="Direction"
                      onChange={(event) => {
                        setDirection(event.target.value);
                        setPage(0);
                      }}
                    >
                      {HISTORY_DIRECTIONS.map((item) => (
                        <MenuItem key={item || 'ALL'} value={item}>
                          {item || 'All'}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={12} sm={2}>
                  <TextField
                    fullWidth
                    label="Start"
                    type="date"
                    InputLabelProps={{ shrink: true }}
                    value={startTime}
                    onChange={(event) => {
                      setStartTime(event.target.value);
                      setPage(0);
                    }}
                  />
                </Grid>
                <Grid item xs={12} sm={3}>
                  <TextField
                    fullWidth
                    label="End"
                    type="date"
                    InputLabelProps={{ shrink: true }}
                    value={endTime}
                    onChange={(event) => {
                      setEndTime(event.target.value);
                      setPage(0);
                    }}
                  />
                </Grid>
              </Grid>

              {query.isLoading ? (
                <LoadingSpinner message="Loading transactions..." />
              ) : (
                <DataTable
                  columns={columns}
                  rows={pagedRows}
                  sortBy={sortBy}
                  sortOrder={sortOrder}
                  onSort={(key) => {
                    const target = key as SortField;
                    if (sortBy === target) {
                      setSortOrder((value) => (value === 'asc' ? 'desc' : 'asc'));
                    } else {
                      setSortBy(target);
                      setSortOrder(target === 'asset_code' ? 'asc' : 'desc');
                    }
                  }}
                  onRowClick={(row) => {
                    setSelectedTransaction(row);
                    setEditTradeTime(toDatetimeLocalValue(row.trade_time));
                    setEditNotes(row.notes ?? '');
                  }}
                  page={page}
                  rowsPerPage={PAGE_SIZE}
                  totalCount={sortedRows.length}
                  onPageChange={(_, nextPage) => setPage(nextPage)}
                />
              )}
            </Stack>
          </SectionCard>
        </Grid>

        <Grid item xs={12} xl={4}>
          <TransactionForm />
        </Grid>
      </Grid>

      <Dialog open={Boolean(selectedTransaction)} onClose={() => setSelectedTransaction(null)} fullWidth maxWidth="sm">
        <DialogTitle>Transaction Detail</DialogTitle>
        <DialogContent>
          {selectedTransaction ? (
            <Stack spacing={1.2} sx={{ pt: 1 }}>
              <Typography><strong>Asset:</strong> {selectedTransaction.asset_type} / {selectedTransaction.asset_code}</Typography>
              <Typography><strong>Direction:</strong> {selectedTransaction.direction}</Typography>
              <Typography><strong>Quantity:</strong> {formatNumber(selectedTransaction.quantity, 6)}</Typography>
              <Typography><strong>Unit Price:</strong> {formatNumber(selectedTransaction.unit_price, 6)} {selectedTransaction.trade_currency}</Typography>
              <Typography><strong>Trade Amount:</strong> {formatTradeValue(selectedTransaction)}</Typography>
              <Typography><strong>Total Cost CNY:</strong> {formatCurrency(signedTotalCost(selectedTransaction))}</Typography>
              <Typography><strong>Record Type:</strong> {selectedTransaction.record_type ?? 'TRANSACTION'}</Typography>
              {selectedTransaction.event_type ? (
                <Typography><strong>Event Type:</strong> {selectedTransaction.event_type}</Typography>
              ) : null}
              <Typography><strong>Trade Time:</strong> {formatDateTime(selectedTransaction.trade_time)}</Typography>
              <Typography><strong>Relative:</strong> {formatRelativeTime(selectedTransaction.trade_time)}</Typography>
              <Typography><strong>Rate To CNY:</strong> {formatNumber(selectedTransaction.exchange_rate_to_cny, 6)}</Typography>
              <Typography><strong>Status:</strong> {selectedTransaction.status}</Typography>
              <Typography><strong>Source:</strong> {selectedTransaction.source ?? '-'}</Typography>
              <TextField
                label="Trade Time"
                type="datetime-local"
                InputLabelProps={{ shrink: true }}
                value={editTradeTime}
                onChange={(event) => setEditTradeTime(event.target.value)}
                fullWidth
              />
              <TextField
                label="Notes"
                value={editNotes}
                onChange={(event) => setEditNotes(event.target.value)}
                multiline
                minRows={2}
                fullWidth
              />
            </Stack>
          ) : null}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSelectedTransaction(null)}>Close</Button>
          {selectedTransaction ? (
            <>
              <Button
                color="error"
                disabled={deleteMutation.isPending}
                onClick={() => {
                  if (window.confirm('Delete this record? This will also remove related ledger entries.')) {
                    deleteMutation.mutate(selectedTransaction);
                  }
                }}
              >
                Delete
              </Button>
              <Button
                disabled={rateMutation.isPending}
                onClick={() => rateMutation.mutate(selectedTransaction)}
              >
                Update Rate
              </Button>
              <Button
                variant="contained"
                disabled={updateMutation.isPending || !editTradeTime}
                onClick={() => updateMutation.mutate(selectedTransaction)}
              >
                Save
              </Button>
            </>
          ) : null}
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
