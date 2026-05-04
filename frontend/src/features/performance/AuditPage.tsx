import AssessmentIcon from '@mui/icons-material/Assessment';
import DownloadIcon from '@mui/icons-material/Download';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import HistoryIcon from '@mui/icons-material/History';
import RefreshIcon from '@mui/icons-material/Refresh';
import SearchIcon from '@mui/icons-material/Search';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Chip,
  Divider,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useMemo, useState } from 'react';

import { DataTable } from '../../components/common/DataTable';
import { LoadingSpinner } from '../../components/common/LoadingSpinner';
import { SectionCard } from '../../components/common/SectionCard';
import { useNotification } from '../../hooks/useNotification';
import { getAudit, getAuditDetail, getAuditHistory } from '../../services/audit';
import { refreshRates } from '../../services/exchangeRates';
import type {
  AssetBreakdownEntry,
  AuditHistoryItem,
  AuditResponse,
  CalculationStep,
  CashBreakdownEntry,
  CorrectionSuggestion,
  CurrencyAudit,
  Discrepancy,
  ExpectedValues,
  HistoricalInputEntry,
} from '../../types/audit';
import { DEFAULT_USER_ID } from '../../utils/constants';
import { formatCurrency, formatDateTime, formatNumber } from '../../utils/formatting';

type ExpectedDraft = Record<keyof ExpectedValues, string>;

const initialExpectedDraft: ExpectedDraft = {
  cash: '',
  assets: '',
  valueCny: '',
};

function toNumberOrUndefined(value: string): number | undefined {
  if (value.trim() === '') return undefined;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : undefined;
}

function saveTextFile(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function csvValue(value: unknown): string {
  if (value === null || value === undefined) return '';
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function buildAuditCsv(audit: AuditResponse): string {
  const rows = [
    ['section', 'currency', 'metric', 'value', 'detail'],
    ['summary', '', 'total_discrepancies', audit.summary.total_discrepancies, ''],
    ['summary', '', 'data_quality_score', audit.summary.data_quality_score, ''],
    ...audit.by_currency.flatMap((item) => [
      ['currency', item.currency, 'cash_balance', item.cash_breakdown.total_balance, ''],
      ['currency', item.currency, 'asset_market_value_native', item.asset_breakdown.total_market_value, ''],
      ['currency', item.currency, 'historical_native_input', item.historical_input_breakdown.total_native_invested, ''],
      ...item.discrepancies.map((discrepancy) => [
        'discrepancy',
        item.currency,
        discrepancy.metric,
        discrepancy.absolute_difference,
        discrepancy.severity,
      ]),
    ]),
  ];
  return rows.map((row) => row.map(csvValue).join(',')).join('\n');
}

function severityColor(severity: Discrepancy['severity']): 'error' | 'warning' | 'info' {
  if (severity === 'error') return 'error';
  if (severity === 'warning') return 'warning';
  return 'info';
}

function likelihoodColor(likelihood: CorrectionSuggestion['likelihood']): 'error' | 'warning' | 'info' {
  if (likelihood === 'high') return 'error';
  if (likelihood === 'medium') return 'warning';
  return 'info';
}

export default function AuditPage() {
  const queryClient = useQueryClient();
  const notifications = useNotification();
  const [selectedCurrency, setSelectedCurrency] = useState<string>('');
  const [expectedDraft, setExpectedDraft] = useState<ExpectedDraft>(initialExpectedDraft);
  const [expectedValues, setExpectedValues] = useState<ExpectedValues>({});
  const [historyAuditId, setHistoryAuditId] = useState<number | null>(null);

  const auditQuery = useQuery({
    queryKey: ['performance-audit', DEFAULT_USER_ID, selectedCurrency || null, expectedValues],
    queryFn: () =>
      getAudit({
        userId: DEFAULT_USER_ID,
        currency: selectedCurrency || null,
        expectedValues,
      }),
  });

  const historyQuery = useQuery({
    queryKey: ['performance-audit-history', DEFAULT_USER_ID],
    queryFn: () => getAuditHistory(DEFAULT_USER_ID),
  });

  const historyDetailQuery = useQuery({
    queryKey: ['performance-audit-detail', DEFAULT_USER_ID, historyAuditId],
    queryFn: () => getAuditDetail(historyAuditId ?? 0, DEFAULT_USER_ID),
    enabled: historyAuditId !== null,
  });

  const report = historyDetailQuery.data ?? auditQuery.data;
  const currencies = useMemo(() => {
    const values = new Set<string>(auditQuery.data?.currencies_audited ?? report?.currencies_audited ?? []);
    report?.by_currency.forEach((item) => values.add(item.currency));
    return [...values].sort();
  }, [auditQuery.data, report]);
  const refreshableCurrencies = useMemo(
    () => (selectedCurrency ? [selectedCurrency] : currencies.filter((item) => item !== 'CNY')),
    [currencies, selectedCurrency],
  );

  const refreshRatesMutation = useMutation({
    mutationFn: () => refreshRates(refreshableCurrencies),
    onSuccess: async (result) => {
      notifications.success(`汇率已刷新：${result.refreshed_count ?? result.rates.length} 条`);
      setHistoryAuditId(null);
      await queryClient.invalidateQueries({ queryKey: ['performance-audit'] });
      await queryClient.invalidateQueries({ queryKey: ['performance'] });
      await queryClient.invalidateQueries({ queryKey: ['exchange-rates'] });
    },
    onError: (error: { message: string }) => notifications.error(error.message),
  });

  const applyExpectedValues = () => {
    setExpectedValues({
      cash: toNumberOrUndefined(expectedDraft.cash),
      assets: toNumberOrUndefined(expectedDraft.assets),
      valueCny: toNumberOrUndefined(expectedDraft.valueCny),
    });
    setHistoryAuditId(null);
  };

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4">Performance Audit</Typography>
        <Typography color="text.secondary">
          数据审计按币种资产池展示现金流水、资产估值、历史投入、计算链路和差异定位。
        </Typography>
      </Box>

      <SectionCard
        title="Audit Controls"
        action={
          <Stack direction="row" spacing={1}>
            <Button
              startIcon={<DownloadIcon />}
              disabled={!report}
              onClick={() => report && saveTextFile(`performance-audit-${report.audit_id}.json`, JSON.stringify(report, null, 2), 'application/json')}
            >
              JSON
            </Button>
            <Button
              startIcon={<DownloadIcon />}
              disabled={!report}
              onClick={() => report && saveTextFile(`performance-audit-${report.audit_id}.csv`, buildAuditCsv(report), 'text/csv')}
            >
              CSV
            </Button>
            <Button
              startIcon={<RefreshIcon />}
              onClick={() => {
                setHistoryAuditId(null);
                void queryClient.invalidateQueries({ queryKey: ['performance-audit'] });
                void queryClient.invalidateQueries({ queryKey: ['performance-audit-history'] });
              }}
            >
              Refresh
            </Button>
            <Button
              startIcon={<RefreshIcon />}
              disabled={!refreshableCurrencies.length || refreshRatesMutation.isPending}
              onClick={() => refreshRatesMutation.mutate()}
            >
              Refresh FX Rates
            </Button>
          </Stack>
        }
      >
        <Stack spacing={2}>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
            <CurrencySelector
              currencies={currencies}
              value={selectedCurrency}
              onChange={(value) => {
                setSelectedCurrency(value);
                setHistoryAuditId(null);
              }}
            />
            <ExpectedValuesForm
              value={expectedDraft}
              onChange={setExpectedDraft}
              onSubmit={applyExpectedValues}
            />
          </Stack>
          {historyAuditId !== null ? (
            <Alert severity="info" icon={<HistoryIcon />}>
              Showing historical audit #{historyAuditId}
            </Alert>
          ) : null}
        </Stack>
      </SectionCard>

      {auditQuery.isLoading ? <LoadingSpinner message="Loading audit..." /> : null}
      {auditQuery.error ? <Alert severity="error">{auditQuery.error.message}</Alert> : null}
      {historyDetailQuery.error ? <Alert severity="error">{historyDetailQuery.error.message}</Alert> : null}

      {report ? (
        <>
          <AuditSummarySection audit={report} />
          {report.by_currency.map((currencyAudit) => (
            <CurrencyAuditSection key={currencyAudit.currency} audit={currencyAudit} />
          ))}
        </>
      ) : null}

      <AuditHistorySection
        rows={historyQuery.data?.audit_logs ?? []}
        isLoading={historyQuery.isLoading}
        onOpen={(id) => setHistoryAuditId(id)}
      />
    </Stack>
  );
}

function CurrencySelector({
  currencies,
  value,
  onChange,
}: {
  currencies: string[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <FormControl sx={{ minWidth: 220 }}>
      <InputLabel id="audit-currency-label">Currency</InputLabel>
      <Select
        labelId="audit-currency-label"
        value={value}
        label="Currency"
        onChange={(event) => onChange(event.target.value)}
      >
        <MenuItem value="">All Currencies</MenuItem>
        {currencies.map((currency) => (
          <MenuItem key={currency} value={currency}>
            {currency}
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );
}

function ExpectedValuesForm({
  value,
  onChange,
  onSubmit,
}: {
  value: ExpectedDraft;
  onChange: (value: ExpectedDraft) => void;
  onSubmit: () => void;
}) {
  const fieldProps = [
    { key: 'cash' as const, label: 'Expected Cash' },
    { key: 'assets' as const, label: 'Expected Assets' },
    { key: 'valueCny' as const, label: 'Expected Value CNY' },
  ];
  const hasInvalid = fieldProps.some(({ key }) => value[key].trim() !== '' && !Number.isFinite(Number(value[key])));

  return (
    <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ flex: 1 }}>
      {fieldProps.map((field) => (
        <TextField
          key={field.key}
          label={field.label}
          value={value[field.key]}
          type="number"
          error={value[field.key].trim() !== '' && !Number.isFinite(Number(value[field.key]))}
          onChange={(event) => onChange({ ...value, [field.key]: event.target.value })}
          sx={{ minWidth: 180 }}
        />
      ))}
      <Button
        variant="contained"
        startIcon={<SearchIcon />}
        onClick={onSubmit}
        disabled={hasInvalid}
        sx={{ alignSelf: { xs: 'stretch', md: 'center' }, minHeight: 40 }}
      >
        Compare
      </Button>
    </Stack>
  );
}

function AuditSummarySection({ audit }: { audit: AuditResponse }) {
  const quality = audit.data_quality;
  const hasQualityWarnings =
    quality.missing_rates.length > 0 ||
    quality.missing_valuations.length > 0 ||
    quality.estimated_values.length > 0;

  return (
    <SectionCard title="Audit Summary">
      <Stack spacing={2}>
        <Grid container spacing={2}>
          {[
            { label: 'Discrepancies', value: audit.summary.total_discrepancies, tone: audit.summary.total_discrepancies ? 'error.main' : 'success.main' },
            { label: 'Currencies With Issues', value: audit.summary.currencies_with_issues.length, tone: audit.summary.currencies_with_issues.length ? 'warning.main' : 'success.main' },
            { label: 'Data Quality', value: `${formatNumber(audit.summary.data_quality_score, 2)}%`, tone: audit.summary.data_quality_score >= 95 ? 'success.main' : 'warning.main' },
            { label: 'Current Assets', value: formatCurrency(audit.overview.current_total_assets_cny), tone: 'text.primary' },
          ].map((item) => (
            <Grid key={item.label} item xs={12} sm={6} lg={3}>
              <Box sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  {item.label}
                </Typography>
                <Typography variant="h6" sx={{ mt: 0.5, color: item.tone, fontWeight: 700 }}>
                  {item.value}
                </Typography>
              </Box>
            </Grid>
          ))}
        </Grid>
        {hasQualityWarnings ? (
          <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
            <Chip icon={<WarningAmberIcon />} color="warning" label={`Missing rates: ${quality.missing_rates.join(', ') || 0}`} />
            <Chip icon={<WarningAmberIcon />} color="warning" label={`Missing valuations: ${quality.missing_valuations.length}`} />
            <Chip color="info" label={`Estimated values: ${quality.estimated_values.length}`} />
          </Stack>
        ) : (
          <Chip color="success" label="Data quality verified" sx={{ alignSelf: 'flex-start' }} />
        )}
      </Stack>
    </SectionCard>
  );
}

function CurrencyAuditSection({ audit }: { audit: CurrencyAudit }) {
  return (
    <SectionCard
      title={`${audit.currency} Audit`}
      action={
        <Stack direction="row" spacing={1}>
          <Chip
            size="small"
            color={audit.status === 'COMPLETE' ? 'success' : 'warning'}
            label={audit.status}
          />
          {audit.discrepancies.length ? (
            <Chip size="small" color="error" label={`${audit.discrepancies.length} issues`} />
          ) : null}
        </Stack>
      }
    >
      <Stack spacing={2}>
        {audit.errors.map((error) => (
          <Alert key={error.code} severity="warning" icon={<ErrorOutlineIcon />}>
            {error.message}
          </Alert>
        ))}
        <CashBreakdownSection audit={audit} />
        <AssetBreakdownSection audit={audit} />
        <HistoricalInputSection audit={audit} />
        <CalculationTrailSection audit={audit} />
        <DiscrepanciesSection rows={audit.discrepancies} />
        <CorrectionSuggestionsSection rows={audit.correction_suggestions} />
      </Stack>
    </SectionCard>
  );
}

function CashBreakdownSection({ audit }: { audit: CurrencyAudit }) {
  const columns = [
    { key: 'event_time', header: 'Time', render: (row: CashBreakdownEntry) => formatDateTime(row.event_time) },
    { key: 'event_type', header: 'Type', render: (row: CashBreakdownEntry) => row.event_type ?? '-' },
    { key: 'amount_delta', header: 'Delta', align: 'right' as const, render: (row: CashBreakdownEntry) => formatNumber(row.amount_delta, 6) },
    { key: 'running_balance', header: 'Running', align: 'right' as const, render: (row: CashBreakdownEntry) => formatNumber(row.running_balance, 6) },
    { key: 'rmb_amount', header: 'RMB', align: 'right' as const, render: (row: CashBreakdownEntry) => formatCurrency(row.rmb_amount) },
    { key: 'flags', header: 'Flags', render: (row: CashBreakdownEntry) => (
      <Stack direction="row" spacing={0.5}>
        {row.is_external_flow ? <Chip size="small" label="External" /> : null}
        {!row.included_in_balance ? <Chip size="small" color="warning" label="Excluded" /> : null}
      </Stack>
    ) },
  ];
  return (
    <AuditAccordion title="Cash Breakdown" summary={formatNumber(audit.cash_breakdown.total_balance, 6)}>
      <Stack spacing={2}>
        <SubtotalChips subtotals={audit.cash_breakdown.subtotals} />
        <DataTable columns={columns} rows={audit.cash_breakdown.entries} />
      </Stack>
    </AuditAccordion>
  );
}

function AssetBreakdownSection({ audit }: { audit: CurrencyAudit }) {
  const columns = [
    { key: 'asset_code', header: 'Code', render: (row: AssetBreakdownEntry) => row.asset_code },
    { key: 'asset_name', header: 'Name', render: (row: AssetBreakdownEntry) => row.asset_name ?? '-' },
    { key: 'asset_type', header: 'Type', render: (row: AssetBreakdownEntry) => row.asset_type },
    { key: 'current_quantity', header: 'Quantity', align: 'right' as const, render: (row: AssetBreakdownEntry) => formatNumber(row.current_quantity, 6) },
    { key: 'latest_valuation_price', header: 'Price', align: 'right' as const, render: (row: AssetBreakdownEntry) => formatNumber(row.latest_valuation_price, 6) },
    { key: 'market_value', header: 'Market Value', align: 'right' as const, render: (row: AssetBreakdownEntry) => formatNumber(row.market_value, 2) },
    { key: 'source', header: 'Source', render: (row: AssetBreakdownEntry) => (
      <Stack direction="row" spacing={0.5}>
        <Chip size="small" label={row.valuation_source} />
        {row.is_estimated ? <Chip size="small" color="info" label="Estimated" /> : null}
      </Stack>
    ) },
  ];
  return (
    <AuditAccordion title="Asset Breakdown" summary={formatNumber(audit.asset_breakdown.total_market_value, 2)}>
      <DataTable columns={columns} rows={audit.asset_breakdown.entries} />
    </AuditAccordion>
  );
}

function HistoricalInputSection({ audit }: { audit: CurrencyAudit }) {
  const columns = [
    { key: 'event_time', header: 'Time', render: (row: HistoricalInputEntry) => formatDateTime(row.event_time) },
    { key: 'event_type', header: 'Type', render: (row: HistoricalInputEntry) => row.event_type ?? '-' },
    { key: 'native_amount_delta', header: 'Native Delta', align: 'right' as const, render: (row: HistoricalInputEntry) => formatNumber(row.native_amount_delta, 6) },
    { key: 'rmb_amount', header: 'RMB', align: 'right' as const, render: (row: HistoricalInputEntry) => formatCurrency(row.rmb_amount) },
    { key: 'rmb_source', header: 'RMB Source', render: (row: HistoricalInputEntry) => <Chip size="small" label={row.rmb_source} /> },
    { key: 'fx_rate_used', header: 'FX Rate', align: 'right' as const, render: (row: HistoricalInputEntry) => formatNumber(row.fx_rate_used, 6) },
  ];
  return (
    <AuditAccordion title="Historical Input" summary={formatNumber(audit.historical_input_breakdown.total_native_invested, 6)}>
      <DataTable columns={columns} rows={audit.historical_input_breakdown.entries} />
    </AuditAccordion>
  );
}

function CalculationTrailSection({ audit }: { audit: CurrencyAudit }) {
  const rows = [
    ...audit.calculation_trail.native_assets,
    ...audit.calculation_trail.value_cny,
    ...audit.calculation_trail.investment_pnl,
    ...audit.calculation_trail.fx_pnl,
  ];
  const columns = [
    { key: 'description', header: 'Metric', render: (row: CalculationStep) => row.description },
    { key: 'formula', header: 'Formula', render: (row: CalculationStep) => row.formula },
    { key: 'inputs', header: 'Inputs', render: (row: CalculationStep) => Object.entries(row.inputs).map(([key, value]) => `${key}: ${formatNumber(value, 6)}`).join(' | ') },
    { key: 'result', header: 'Result', align: 'right' as const, render: (row: CalculationStep) => formatNumber(row.result, 6) },
    { key: 'notes', header: 'Notes', render: (row: CalculationStep) => row.notes.join(' | ') },
  ];
  return (
    <AuditAccordion title="Calculation Trail" summary={`${rows.length} steps`}>
      <DataTable columns={columns} rows={rows} />
    </AuditAccordion>
  );
}

function DiscrepanciesSection({ rows }: { rows: Discrepancy[] }) {
  const columns = [
    { key: 'metric', header: 'Metric', render: (row: Discrepancy) => row.metric },
    { key: 'calculated_value', header: 'Calculated', align: 'right' as const, render: (row: Discrepancy) => formatNumber(row.calculated_value, 6) },
    { key: 'expected_value', header: 'Expected', align: 'right' as const, render: (row: Discrepancy) => formatNumber(row.expected_value, 6) },
    { key: 'absolute_difference', header: 'Difference', align: 'right' as const, render: (row: Discrepancy) => formatNumber(row.absolute_difference, 6) },
    { key: 'percentage_difference', header: 'Percent', align: 'right' as const, render: (row: Discrepancy) => row.percentage_difference === null ? '-' : `${formatNumber(row.percentage_difference, 4)}%` },
    { key: 'severity', header: 'Severity', render: (row: Discrepancy) => <Chip size="small" color={severityColor(row.severity)} label={row.severity} /> },
  ];
  if (!rows.length) return null;
  return (
    <AuditAccordion title="Discrepancies" summary={`${rows.length} issues`} defaultExpanded>
      <DataTable columns={columns} rows={rows} />
    </AuditAccordion>
  );
}

function CorrectionSuggestionsSection({ rows }: { rows: CorrectionSuggestion[] }) {
  const columns = [
    { key: 'suggested_action', header: 'Action', render: (row: CorrectionSuggestion) => row.suggested_action },
    { key: 'discrepancy_metric', header: 'Metric', render: (row: CorrectionSuggestion) => row.discrepancy_metric },
    { key: 'likelihood', header: 'Likelihood', render: (row: CorrectionSuggestion) => <Chip size="small" color={likelihoodColor(row.likelihood)} label={row.likelihood} /> },
    { key: 'details', header: 'Details', render: (row: CorrectionSuggestion) => row.details },
    { key: 'affected_records', header: 'Records', render: (row: CorrectionSuggestion) => row.affected_records.slice(0, 4).join(', ') || '-' },
  ];
  if (!rows.length) return null;
  return (
    <AuditAccordion title="Correction Suggestions" summary={`${rows.length} suggestions`} defaultExpanded>
      <DataTable columns={columns} rows={rows} />
    </AuditAccordion>
  );
}

function AuditHistorySection({
  rows,
  isLoading,
  onOpen,
}: {
  rows: AuditHistoryItem[];
  isLoading: boolean;
  onOpen: (id: number) => void;
}) {
  const columns = [
    { key: 'audit_time', header: 'Time', render: (row: AuditHistoryItem) => formatDateTime(row.audit_time) },
    { key: 'currencies_audited', header: 'Currencies', render: (row: AuditHistoryItem) => row.currencies_audited.join(', ') },
    { key: 'discrepancies_found', header: 'Issues', align: 'right' as const, render: (row: AuditHistoryItem) => formatNumber(row.discrepancies_found, 0) },
    { key: 'data_quality_score', header: 'Quality', align: 'right' as const, render: (row: AuditHistoryItem) => `${formatNumber(row.summary.data_quality_score, 2)}%` },
    { key: 'action', header: 'Action', render: (row: AuditHistoryItem) => (
      <Button size="small" startIcon={<AssessmentIcon />} onClick={() => onOpen(row.id)}>
        Open
      </Button>
    ) },
  ];
  return (
    <SectionCard title="Audit History">
      {isLoading ? <LoadingSpinner message="Loading audit history..." /> : <DataTable columns={columns} rows={rows} />}
    </SectionCard>
  );
}

function AuditAccordion({
  title,
  summary,
  children,
  defaultExpanded = false,
}: {
  title: string;
  summary: string;
  children: ReactNode;
  defaultExpanded?: boolean;
}) {
  return (
    <Accordion defaultExpanded={defaultExpanded} disableGutters sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2, '&:before': { display: 'none' } }}>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Stack direction="row" spacing={1.5} alignItems="center" sx={{ width: '100%', pr: 2 }}>
          <Typography fontWeight={700}>{title}</Typography>
          <Divider flexItem orientation="vertical" />
          <Typography variant="body2" color="text.secondary">
            {summary}
          </Typography>
        </Stack>
      </AccordionSummary>
      <AccordionDetails>{children}</AccordionDetails>
    </Accordion>
  );
}

function SubtotalChips({ subtotals }: { subtotals: Record<string, number> }) {
  const entries = Object.entries(subtotals);
  if (!entries.length) return null;
  return (
    <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
      {entries.map(([key, value]) => (
        <Chip key={key} label={`${key}: ${formatNumber(value, 6)}`} />
      ))}
    </Stack>
  );
}
