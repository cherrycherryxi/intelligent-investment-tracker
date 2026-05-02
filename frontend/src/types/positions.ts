import type { AssetType } from './transactions';

export interface Position {
  asset_code: string;
  asset_type: AssetType;
  asset_name?: string;
  currency?: string;
  quantity: number;
  average_cost_cny?: number | null;
  cost_basis_cny?: number | null;
  native_cost?: number | null;
  current_price?: number | null;
  current_value_native?: number | null;
  current_value_cny?: number | null;
  unrealized_pnl_cny?: number | null;
  return_pct?: number | null;
  valuation_status?: 'OK' | 'RATE_MISSING' | 'VALUATION_MISSING' | 'ESTIMATED';
}

export interface PositionSummary {
  total_cost_cny?: number | null;
  total_value_cny?: number | null;
  total_pnl_cny?: number | null;
  total_return_pct: number;
  missing_rates?: string[];
  missing_valuations?: string[];
}

export interface PositionResponse {
  positions: Position[];
  totals: PositionSummary;
}
