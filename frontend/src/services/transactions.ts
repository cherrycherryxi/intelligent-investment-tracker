import { apiClient } from './api';
import type {
  ExcelConfirmResponse,
  ExcelPreviewResponse,
  ScreenshotPreviewResponse,
  ScreenshotUploadItem,
  Transaction,
  TransactionCreatePayload,
  TransactionFilters,
  PortfolioEventCreatePayload,
} from '../types/transactions';

export async function listTransactions(filters: TransactionFilters): Promise<Transaction[]> {
  const response = await apiClient.get<{ transactions: Transaction[] }>('/api/transactions', {
    params: filters,
  });
  return response.data.transactions;
}

export async function createTransaction(payload: TransactionCreatePayload): Promise<Transaction> {
  const response = await apiClient.post<{ transaction: Transaction }>('/api/transactions', payload);
  return response.data.transaction;
}

export async function createPortfolioEvent(payload: PortfolioEventCreatePayload): Promise<{ id: number }> {
  const response = await apiClient.post<{ event: { id: number } }>('/api/portfolio-events', payload);
  return { id: response.data.event.id };
}

export async function updateTransactionRecord(
  recordType: 'TRANSACTION' | 'EVENT',
  id: number,
  payload: { trade_time?: string; notes?: string },
): Promise<Transaction> {
  const response = await apiClient.patch<{ record: Transaction }>(`/api/transactions/${recordType}/${id}`, payload);
  return response.data.record;
}

export async function deleteTransactionRecord(recordType: 'TRANSACTION' | 'EVENT', id: number): Promise<void> {
  await apiClient.delete(`/api/transactions/${recordType}/${id}`);
}

export async function uploadScreenshots(files: ScreenshotUploadItem[]): Promise<ScreenshotPreviewResponse> {
  const response = await apiClient.post<ScreenshotPreviewResponse>('/api/transactions/upload', {
    files,
  });
  return response.data;
}

export async function previewExcel(file: File): Promise<ExcelPreviewResponse> {
  const buffer = await file.arrayBuffer();
  const response = await apiClient.post<ExcelPreviewResponse>(
    '/api/transactions/import-excel-preview',
    buffer,
    {
      params: { filename: file.name },
      headers: { 'Content-Type': 'application/octet-stream' },
    },
  );
  return response.data;
}

export async function confirmExcel(file: File, includePending: boolean): Promise<ExcelConfirmResponse> {
  const buffer = await file.arrayBuffer();
  const response = await apiClient.post<ExcelConfirmResponse>(
    '/api/transactions/import-excel-confirm',
    buffer,
    {
      params: { filename: file.name, user_id: 1, include_pending: includePending },
      headers: { 'Content-Type': 'application/octet-stream' },
    },
  );
  return response.data;
}
