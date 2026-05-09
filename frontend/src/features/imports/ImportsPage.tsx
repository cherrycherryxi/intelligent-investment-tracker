import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import TaskAltIcon from '@mui/icons-material/TaskAlt';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  FormControlLabel,
  Grid,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from '@mui/material';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useMemo, useState } from 'react';

import { DataTable } from '../../components/common/DataTable';
import { SectionCard } from '../../components/common/SectionCard';
import { useNotification } from '../../hooks/useNotification';
import { confirmExcel, createTransaction, previewExcel, uploadScreenshots } from '../../services/transactions';
import type {
  ExcelPreviewReadyItem,
  ScreenshotPreviewEntry,
  TransactionCreatePayload,
} from '../../types/transactions';
import { DEFAULT_USER_ID } from '../../utils/constants';
import { formatDateTime, formatNumber } from '../../utils/formatting';

function previewKind(row: ExcelPreviewReadyItem): string {
  if (row.transaction) return row.transaction.asset_type;
  return row.portfolio_event?.event_type ?? '-';
}

function previewCode(row: ExcelPreviewReadyItem): string {
  if (row.transaction) return row.transaction.asset_code;
  const cashFlow = row.portfolio_event?.cash_entries
    .map((entry) => `${entry.currency} ${entry.amount_delta > 0 ? '+' : ''}${formatNumber(entry.amount_delta, 6)}`)
    .join(' / ');
  if (cashFlow) return cashFlow;
  return row.portfolio_event?.asset_entries[0]?.asset?.asset_name ?? '-';
}

function previewDirection(row: ExcelPreviewReadyItem): string {
  if (row.transaction) return row.transaction.direction;
  return row.portfolio_event?.event_type ?? '-';
}

function previewQuantity(row: ExcelPreviewReadyItem): string {
  if (row.transaction) return formatNumber(row.transaction.quantity, 6);
  const assetDelta = row.portfolio_event?.asset_entries[0]?.quantity_delta;
  if (assetDelta !== undefined) return formatNumber(assetDelta, 6);
  const cashDelta = row.portfolio_event?.cash_entries.find((entry) => entry.amount_delta > 0)?.amount_delta;
  return cashDelta !== undefined ? formatNumber(cashDelta, 6) : '-';
}

function previewUnitPrice(row: ExcelPreviewReadyItem): string {
  if (row.transaction) return formatNumber(row.transaction.unit_price, 6);
  return row.portfolio_event?.cash_entries[0]?.description ?? '-';
}

function previewTradeTime(row: ExcelPreviewReadyItem): string {
  if (row.transaction) return formatDateTime(row.transaction.trade_time);
  return formatDateTime(row.portfolio_event?.event_time);
}

function StatusBadge({ warnings, errors }: { warnings?: string[]; errors?: string[] }) {
  if (errors?.length) {
    return <Alert severity="error">{errors.join(' / ')}</Alert>;
  }
  if (warnings?.length) {
    return <Alert severity="warning">{warnings.join(' / ')}</Alert>;
  }
  return <Alert icon={<TaskAltIcon fontSize="inherit" />} severity="success">Ready</Alert>;
}

function ExcelImportPanel() {
  const notifications = useNotification();
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [includePending, setIncludePending] = useState(false);
  const [preview, setPreview] = useState<Awaited<ReturnType<typeof previewExcel>> | null>(null);

  const previewMutation = useMutation({
    mutationFn: previewExcel,
    onSuccess: (data) => setPreview(data),
    onError: (error: { message: string }) => notifications.error(error.message),
  });

  const confirmMutation = useMutation({
    mutationFn: ({ workbook, pending }: { workbook: File; pending: boolean }) => confirmExcel(workbook, pending),
    onSuccess: (data) => {
      const duplicateText = data.skipped_duplicate_count ? `，跳过 ${data.skipped_duplicate_count} 条重复记录` : '';
      const patchedText = data.patched_event_count ? `，补充 ${data.patched_event_count} 条事件` : '';
      notifications.success(`导入完成，写入 ${data.imported_count} 条交易、${data.imported_event_count ?? 0} 个事件${patchedText}${duplicateText}`);
      void queryClient.invalidateQueries({ queryKey: ['transactions'] });
      void queryClient.invalidateQueries({ queryKey: ['positions'] });
      void queryClient.invalidateQueries({ queryKey: ['performance'] });
    },
    onError: (error: { message: string }) => notifications.error(error.message),
  });

  const previewRows = useMemo(() => {
    const ready = (preview?.ready_to_import ?? []).map((item) => ({ ...item, bucket: 'ready' as const }));
    const pending = (preview?.pending_review ?? []).map((item) => ({ ...item, bucket: 'pending' as const }));
    return [...ready, ...pending];
  }, [preview]);

  return (
    <Stack spacing={2.5}>
      <Alert severity="info">Excel 导入直接复用后端已有工作流，前端只负责上传、预览和确认。</Alert>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
        <Button component="label" variant="contained" startIcon={<CloudUploadIcon />}>
          Select .xlsx
          <input
            hidden
            type="file"
            accept=".xlsx"
            onChange={(event) => {
              const nextFile = event.target.files?.[0] ?? null;
              setFile(nextFile);
              setPreview(null);
            }}
          />
        </Button>
        <Button
          variant="outlined"
          disabled={!file || previewMutation.isPending}
          onClick={() => file && previewMutation.mutate(file)}
        >
          Preview Import
        </Button>
        <FormControlLabel
          control={<Checkbox checked={includePending} onChange={(event) => setIncludePending(event.target.checked)} />}
          label="Include pending rows"
        />
      </Stack>

      {file ? <Typography color="text.secondary">当前文件: {file.name}</Typography> : null}

      {preview ? (
        <Grid container spacing={2}>
          <Grid item xs={12} md={4}>
            <Alert severity="success">Ready: {preview.summary.ready_count}</Alert>
          </Grid>
          <Grid item xs={12} md={4}>
            <Alert severity="warning">Pending: {preview.summary.pending_count}</Alert>
          </Grid>
          <Grid item xs={12} md={4}>
            <Alert severity="error">Failed: {preview.summary.failed_count}</Alert>
          </Grid>
        </Grid>
      ) : null}

      {previewRows.length ? (
        <DataTable
          columns={[
            {
              key: 'status',
              header: 'Status',
              render: (row: ExcelPreviewReadyItem & { bucket: 'ready' | 'pending' }) => (
                <StatusBadge warnings={row.warnings} />
              ),
            },
            { key: 'row_number', header: 'Row', render: (row: ExcelPreviewReadyItem) => row.row_number },
            { key: 'kind', header: 'Kind', render: (row: ExcelPreviewReadyItem) => previewKind(row) },
            { key: 'asset_code', header: 'Code / Flow', render: (row: ExcelPreviewReadyItem) => previewCode(row) },
            { key: 'direction', header: 'Direction', render: (row: ExcelPreviewReadyItem) => previewDirection(row) },
            { key: 'quantity', header: 'Quantity', render: (row: ExcelPreviewReadyItem) => previewQuantity(row) },
            { key: 'unit_price', header: 'Price / Note', render: (row: ExcelPreviewReadyItem) => previewUnitPrice(row) },
            { key: 'trade_time', header: 'Trade Time', render: (row: ExcelPreviewReadyItem) => previewTradeTime(row) },
          ]}
          rows={previewRows}
        />
      ) : null}

      {(preview?.failed ?? []).map((item) => (
        <Alert key={`failed-${item.row_number}`} severity="error">
          Row {item.row_number}: {item.errors.join(' / ')}
        </Alert>
      ))}

      <Button
        variant="contained"
        disabled={!file || !preview || confirmMutation.isPending}
        onClick={() => file && confirmMutation.mutate({ workbook: file, pending: includePending })}
      >
        Confirm Import
      </Button>
    </Stack>
  );
}

type EditableScreenshot = {
  id: string;
  filename: string;
  confidence: number;
  missingFields: string[];
  payload: TransactionCreatePayload;
};

function buildScreenshotPayload(item: ScreenshotPreviewEntry): EditableScreenshot | null {
  const parsed = item.transaction_summary?.parsed_transaction;
  if (!parsed?.asset_type || !parsed.asset_code || !parsed.direction || !parsed.trade_time || !parsed.quantity || !parsed.unit_price) {
    return null;
  }
  return {
    id: `${item.filename}-${parsed.trade_time}`,
    filename: item.filename,
    confidence: item.transaction_summary?.confidence ?? 0,
    missingFields: item.transaction_summary?.missing_fields ?? [],
    payload: {
      user_id: DEFAULT_USER_ID,
      asset_type: parsed.asset_type,
      asset_code: parsed.asset_code,
      asset_name: parsed.asset_name,
      direction: parsed.direction,
      quantity: Number(parsed.quantity),
      unit_price: Number(parsed.unit_price),
      trade_currency: 'CNY',
      trade_time: parsed.trade_time,
      exchange_rate_to_cny: 1,
      total_cost_cny: Number(parsed.quantity) * Number(parsed.unit_price),
      source: 'screenshot_upload',
      raw_text: item.ocr?.text,
      notes: item.ocr?.text,
    },
  };
}

async function toBase64(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  let binary = '';
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return window.btoa(binary);
}

function ScreenshotImportPanel() {
  const notifications = useNotification();
  const queryClient = useQueryClient();
  const [rows, setRows] = useState<EditableScreenshot[]>([]);
  const [failed, setFailed] = useState<Array<{ filename?: string | null; errors: string[] }>>([]);

  const previewMutation = useMutation({
    mutationFn: async (files: File[]) => {
      const payload = await Promise.all(
        files.map(async (file) => ({
          filename: file.name,
          content_base64: await toBase64(file),
          language: 'zh-CN',
        })),
      );
      return uploadScreenshots(payload);
    },
    onSuccess: (data) => {
      const mapped = [...data.parsed_transactions, ...data.pending_review]
        .map(buildScreenshotPayload)
        .filter((item): item is EditableScreenshot => Boolean(item));
      setRows(mapped);
      setFailed(data.failed);
      notifications.success(`OCR 预览完成，生成 ${mapped.length} 条候选交易`);
    },
    onError: (error: { message: string }) => notifications.error(error.message),
  });

  const confirmMutation = useMutation({
    mutationFn: async (payloads: TransactionCreatePayload[]) => Promise.all(payloads.map((payload) => createTransaction(payload))),
    onSuccess: (created) => {
      notifications.success(`已创建 ${created.length} 条交易`);
      void queryClient.invalidateQueries({ queryKey: ['transactions'] });
      void queryClient.invalidateQueries({ queryKey: ['positions'] });
    },
    onError: (error: { message: string }) => notifications.error(error.message),
  });

  return (
    <Stack spacing={2.5}>
      <Alert severity="info">截图 OCR 预览结果可编辑，确认时逐条调用交易创建接口，不与后端代码耦合。</Alert>
      <Button component="label" variant="contained" startIcon={<CloudUploadIcon />}>
        Upload screenshots
        <input
          hidden
          multiple
          type="file"
          accept="image/png,image/jpeg,image/jpg"
          onChange={async (event) => {
            const files = Array.from(event.target.files ?? []);
            const oversize = files.find((file) => file.size > 5 * 1024 * 1024);
            if (oversize) {
              notifications.error(`${oversize.name} 超过 5MB 限制`);
              return;
            }
            if (files.length) {
              previewMutation.mutate(files);
            }
          }}
        />
      </Button>

      {rows.map((row) => (
        <Box
          key={row.id}
          sx={{ p: 2, borderRadius: 3, border: '1px solid', borderColor: 'divider', bgcolor: 'background.paper' }}
        >
          <Stack spacing={2}>
            <Stack direction={{ xs: 'column', md: 'row' }} justifyContent="space-between">
              <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>{row.filename}</Typography>
              <Stack direction="row" spacing={1}>
                <Alert severity={row.missingFields.length ? 'warning' : 'success'} sx={{ py: 0 }}>
                  Confidence {row.confidence.toFixed(2)}
                </Alert>
              </Stack>
            </Stack>
            <Grid container spacing={2}>
              <Grid item xs={12} md={2}>
                <TextField
                  fullWidth
                  label="Code"
                  value={row.payload.asset_code}
                  onChange={(event) =>
                    setRows((items) =>
                      items.map((item) =>
                        item.id === row.id ? { ...item, payload: { ...item.payload, asset_code: event.target.value.toUpperCase() } } : item,
                      ),
                    )
                  }
                />
              </Grid>
              <Grid item xs={12} md={2}>
                <TextField
                  fullWidth
                  label="Type"
                  value={row.payload.asset_type}
                  onChange={(event) =>
                    setRows((items) =>
                      items.map((item) =>
                        item.id === row.id ? { ...item, payload: { ...item.payload, asset_type: event.target.value as 'FOREX' | 'BOND' } } : item,
                      ),
                    )
                  }
                />
              </Grid>
              <Grid item xs={12} md={2}>
                <TextField
                  fullWidth
                  label="Direction"
                  value={row.payload.direction}
                  onChange={(event) =>
                    setRows((items) =>
                      items.map((item) =>
                        item.id === row.id ? { ...item, payload: { ...item.payload, direction: event.target.value as 'BUY' | 'SELL' } } : item,
                      ),
                    )
                  }
                />
              </Grid>
              <Grid item xs={12} md={2}>
                <TextField
                  fullWidth
                  label="Quantity"
                  type="number"
                  value={row.payload.quantity}
                  onChange={(event) =>
                    setRows((items) =>
                      items.map((item) =>
                        item.id === row.id
                          ? {
                              ...item,
                              payload: {
                                ...item.payload,
                                quantity: Number(event.target.value),
                                total_cost_cny: Number(event.target.value) * item.payload.unit_price,
                              },
                            }
                          : item,
                      ),
                    )
                  }
                />
              </Grid>
              <Grid item xs={12} md={2}>
                <TextField
                  fullWidth
                  label="Unit Price"
                  type="number"
                  value={row.payload.unit_price}
                  onChange={(event) =>
                    setRows((items) =>
                      items.map((item) =>
                        item.id === row.id
                          ? {
                              ...item,
                              payload: {
                                ...item.payload,
                                unit_price: Number(event.target.value),
                                total_cost_cny: item.payload.quantity * Number(event.target.value),
                              },
                            }
                          : item,
                      ),
                    )
                  }
                />
              </Grid>
              <Grid item xs={12} md={2}>
                <TextField
                  fullWidth
                  label="Currency"
                  value={row.payload.trade_currency}
                  onChange={(event) =>
                    setRows((items) =>
                      items.map((item) =>
                        item.id === row.id ? { ...item, payload: { ...item.payload, trade_currency: event.target.value.toUpperCase() } } : item,
                      ),
                    )
                  }
                />
              </Grid>
            </Grid>
            {row.missingFields.length ? (
              <Alert icon={<WarningAmberIcon fontSize="inherit" />} severity="warning">
                Missing fields: {row.missingFields.join(', ')}
              </Alert>
            ) : null}
          </Stack>
        </Box>
      ))}

      {failed.map((item, index) => (
        <Alert key={`${item.filename}-${index}`} severity="error">
          {item.filename ?? 'unknown'}: {item.errors.join(' / ')}
        </Alert>
      ))}

      <Button
        variant="contained"
        disabled={!rows.length || confirmMutation.isPending}
        onClick={() => confirmMutation.mutate(rows.map((item) => item.payload))}
      >
        Confirm Transactions
      </Button>
    </Stack>
  );
}

export default function ImportsPage() {
  const [tab, setTab] = useState(0);

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4">Import Center</Typography>
        <Typography color="text.secondary">Excel 和截图都通过前端上传到 API，界面层与 Python 业务实现完全分离。</Typography>
      </Box>

      <SectionCard title="Import Workflows">
        <Tabs value={tab} onChange={(_, nextTab) => setTab(nextTab)} sx={{ mb: 3 }}>
          <Tab label="Excel Preview" />
          <Tab label="Screenshot OCR" />
        </Tabs>
        {tab === 0 ? <ExcelImportPanel /> : <ScreenshotImportPanel />}
      </SectionCard>
    </Stack>
  );
}
