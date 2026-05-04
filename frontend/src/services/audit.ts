import { apiClient } from './api';
import type { AuditHistoryResponse, AuditRequest, AuditResponse } from '../types/audit';

function buildAuditParams(request: AuditRequest): Record<string, string | number> {
  const params: Record<string, string | number> = {
    user_id: request.userId,
  };
  if (request.currency) {
    params.currency = request.currency;
  }
  if (request.valuationTime) {
    params.valuation_time = request.valuationTime;
  }
  if (request.expectedValues?.cash !== undefined) {
    params.expected_cash = request.expectedValues.cash;
  }
  if (request.expectedValues?.assets !== undefined) {
    params.expected_assets = request.expectedValues.assets;
  }
  if (request.expectedValues?.valueCny !== undefined) {
    params.expected_value_cny = request.expectedValues.valueCny;
  }
  return params;
}

export async function getAudit(request: AuditRequest): Promise<AuditResponse> {
  const response = await apiClient.get<AuditResponse>('/api/performance/audit', {
    params: buildAuditParams(request),
  });
  return response.data;
}

export async function getAuditHistory(
  userId: number,
  limit: number = 50,
): Promise<AuditHistoryResponse> {
  const response = await apiClient.get<AuditHistoryResponse>('/api/performance/audit-history', {
    params: { user_id: userId, limit },
  });
  return response.data;
}

export async function getAuditDetail(auditId: number, userId: number): Promise<AuditResponse> {
  const response = await apiClient.get<AuditResponse>(`/api/performance/audit/${auditId}`, {
    params: { user_id: userId },
  });
  return response.data;
}
