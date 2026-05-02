import { apiClient } from './api';
import type { PerformanceResponse } from '../types/performance';

export async function getPerformance(userId: number): Promise<PerformanceResponse> {
  const response = await apiClient.get<PerformanceResponse>('/api/performance', {
    params: { user_id: userId },
  });
  return response.data;
}
