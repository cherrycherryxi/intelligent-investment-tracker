import { apiClient } from './api';
import type { AdviceResponse, RiskPreference } from '../types/advice';

export async function getAdvice(userId: number, riskPreference: RiskPreference): Promise<AdviceResponse> {
  const response = await apiClient.get<AdviceResponse>('/api/advice', {
    params: { user_id: userId, risk_preference: riskPreference },
  });
  return response.data;
}
