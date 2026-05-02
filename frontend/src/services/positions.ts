import { apiClient } from './api';
import type { PositionResponse } from '../types/positions';

export async function listPositions(params: {
  user_id: number;
  asset_type?: string;
  sort_by?: string;
}): Promise<PositionResponse> {
  const response = await apiClient.get<PositionResponse>('/api/positions', { params });
  return response.data;
}
