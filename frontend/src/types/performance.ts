export interface PerformanceOverview {
  current_total_assets_cny: number;
  net_invested_cny: number;
  total_pnl_cny: number;
  total_return_pct: number;
  investment_pnl_cny: number;
  realized_investment_pnl_cny?: number;
  unrealized_investment_pnl_cny?: number;
  fx_pnl_cny: number;
  investment_pnl_ratio: number;
  fx_pnl_ratio: number;
}

export interface CurrencyPerformance {
  currency: string;
  cash_balance: number;
  cash_value_cny: number | null;
  asset_market_value_native: number;
  asset_market_value_cny: number | null;
  current_total_assets_native: number;
  current_total_assets_cny: number | null;
  historical_net_invested_native: number;
  investment_pnl_native: number | null;
  investment_pnl_cny: number | null;
  fx_pnl_cny: number | null;
  current_fx_rate_to_cny: number | null;
}

export interface AssetTypePerformance {
  asset_type: string;
  current_value_cny: number;
  investment_pnl_cny: number | null;
  fx_pnl_cny: number | null;
  weight_pct: number;
}

export interface PerformanceDataQuality {
  missing_rates: string[];
  missing_valuations: Array<{
    asset_id: number;
    asset_code?: string | null;
    asset_type?: string | null;
    quantity: number;
  }>;
  estimated_values: Array<{
    asset_id: number;
    currency: string;
    market_value: number;
  }>;
  realized_closed_positions?: RealizedClosedPosition[];
}

export interface RealizedClosedPosition {
  asset_id: number;
  asset_code: string;
  asset_name?: string | null;
  currency: string;
  buy_native: number;
  sell_native: number;
  realized_investment_pnl_native: number;
  realized_investment_pnl_cny: number;
  fx_rate_to_cny: number;
}

export interface PerformanceResponse {
  overview: PerformanceOverview;
  by_currency: CurrencyPerformance[];
  by_asset_type: AssetTypePerformance[];
  data_quality: PerformanceDataQuality;
}
