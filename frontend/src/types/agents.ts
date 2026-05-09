export interface NaturalLanguageParseResponse {
  ok: boolean;
  result: {
    intent: string;
    language: string;
    transaction_type: string;
    parameters: {
      asset_type: string;
      asset_code?: string | null;
      direction?: string | null;
      quantity?: number | null;
      unit_price?: number | null;
      trade_currency?: string | null;
      trade_time?: string | null;
    };
    missing_fields: string[];
  } | null;
  error?: {
    code: string;
    message: string;
    details?: unknown;
  } | null;
}

export interface RiskAssessmentResponse {
  ok: boolean;
  result: {
    risk_level: string;
    factors: string[];
    diversification_suggestions: string[];
    exposures: Array<{
      asset_code: string;
      asset_name?: string | null;
      asset_type?: string | null;
      weight_pct: number;
    }>;
  };
}
