export interface ExchangeRate {
  base_currency: string;
  quote_currency: string;
  rate: number;
  rate_timestamp: string;
  is_estimated: boolean;
  source: string;
}

export interface ExchangeRateResponse {
  rates: ExchangeRate[];
  refreshed_count?: number;
}
