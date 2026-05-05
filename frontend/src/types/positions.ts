import type { AssetType } from './transactions';

export interface Position {
  asset_id?: number;
  asset_code: string;
  asset_type: AssetType;
  asset_name?: string;
  currency?: string;
  quantity: number;
  average_cost_cny?: number | null;
  cost_basis_cny?: number | null;
  legacy_cost_basis_cny?: number | null;
  attributed_cost_basis_cny?: number | null;
  attribution_status?: 'COMPLETE' | 'INCOMPLETE' | 'BASIS_MISSING' | 'NOT_APPLICABLE';
  attribution_summary?: {
    total_lots_used: number;
    oldest_lot_date?: string | null;
    newest_lot_date?: string | null;
    gap_count: number;
  };
  native_cost?: number | null;
  current_price?: number | null;
  current_value_native?: number | null;
  current_value_cny?: number | null;
  unrealized_pnl_cny?: number | null;
  investment_pnl_cny?: number | null;
  fx_pnl_cny?: number | null;
  return_pct?: number | null;
  valuation_status?: 'OK' | 'RATE_MISSING' | 'VALUATION_MISSING' | 'ESTIMATED';
}

export interface PositionSummary {
  total_cost_cny?: number | null;
  total_value_cny?: number | null;
  total_pnl_cny?: number | null;
  total_investment_pnl_cny?: number | null;
  total_fx_pnl_cny?: number | null;
  total_return_pct: number;
  missing_rates?: string[];
  missing_valuations?: string[];
}

export interface PositionResponse {
  positions: Position[];
  totals: PositionSummary;
}

export interface ValuationCreatePayload {
  user_id: number;
  asset_id: number;
  valuation_time: string;
  quantity: number;
  price?: number | null;
  market_value: number;
  currency?: string;
  fx_rate_to_cny?: number | null;
  source?: string;
  is_estimated?: boolean;
}
