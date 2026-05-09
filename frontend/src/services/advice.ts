import { apiClient } from './api';
import type { AdviceChatRequest, AdviceChatResponse, AdviceResponse, RiskPreference } from '../types/advice';

export async function getAdvice(userId: number, riskPreference: RiskPreference): Promise<AdviceResponse> {
  const response = await apiClient.get<AdviceResponse>('/api/advice', {
    params: { user_id: userId, risk_preference: riskPreference },
  });
  return response.data;
}

export async function sendAdviceChat(payload: AdviceChatRequest): Promise<AdviceChatResponse> {
  const response = await apiClient.post<AdviceChatResponse>('/api/advice/chat', payload);
  return response.data;
}
