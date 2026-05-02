import { apiClient } from './api';
import type { ExchangeRateResponse } from '../types/exchangeRates';

export async function getLatestRates(currencies?: string[]): Promise<ExchangeRateResponse> {
  const response = await apiClient.get<ExchangeRateResponse>('/api/exchange-rates/latest', {
    params: currencies?.length ? { currencies: currencies.join(',') } : undefined,
  });
  return response.data;
}

export async function refreshRates(currencies: string[]): Promise<ExchangeRateResponse> {
  const response = await apiClient.post<ExchangeRateResponse>('/api/exchange-rates/refresh', {
    currencies,
  });
  return response.data;
}
