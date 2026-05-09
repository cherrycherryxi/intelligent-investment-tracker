import { apiClient } from './api';
import type { NaturalLanguageParseResponse, RiskAssessmentResponse } from '../types/agents';

export async function parseNaturalLanguageTransaction(text: string): Promise<NaturalLanguageParseResponse> {
  const response = await apiClient.post<NaturalLanguageParseResponse>('/api/advice/parse-transaction', { text });
  return response.data;
}

export async function getRiskAssessment(userId: number): Promise<RiskAssessmentResponse> {
  const response = await apiClient.get<RiskAssessmentResponse>('/api/advice/risk-assessment', {
    params: { user_id: userId },
  });
  return response.data;
}
