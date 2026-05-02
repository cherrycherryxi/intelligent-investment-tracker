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
