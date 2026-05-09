export type RiskPreference = 'conservative' | 'balanced' | 'aggressive';

export interface AdviceAction {
  asset_code: string;
  action: string;
  rationale?: string;
}

export interface AdvicePayload {
  summary: string;
  risk_level: string;
  actions: AdviceAction[];
  reasoning: string;
  warnings: string[];
}

export interface AdviceResponse {
  ok: boolean;
  result: {
    portfolio_summary: {
      total_cost_cny: number;
      total_value_cny: number;
      total_pnl_cny: number;
      total_return_pct: number;
      exposure_pct: Record<string, number>;
      positions_count: number;
    };
    advice: AdvicePayload;
    ai_provider: string;
    model: string;
    token_usage: {
      input_tokens: number;
      output_tokens: number;
    };
  };
}

export type AdviceChatMode = 'chat' | 'generate_advice' | 'position_analysis' | 'transaction_analysis';

export interface AdviceChatRequest {
  user_id: number;
  mode: AdviceChatMode;
  message: string;
  risk_preference: RiskPreference;
}

export interface AdviceChatResponse {
  ok: boolean;
  mode: AdviceChatMode;
  result?: unknown;
  portfolio_summary?: {
    total_cost_cny?: number | null;
    total_value_cny?: number | null;
    total_pnl_cny?: number | null;
    total_return_pct?: number | null;
    positions_count?: number | null;
  };
  error?: {
    message: string;
    code?: string;
    details?: Record<string, unknown>;
  };
}
