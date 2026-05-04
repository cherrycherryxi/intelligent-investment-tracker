import type { PerformanceOverview } from './performance';

export interface CashBreakdownEntry {
  id: number;
  event_id: number;
  event_time: string | null;
  event_type: string | null;
  amount_delta: number;
  running_balance: number;
  included_in_balance: boolean;
  is_external_flow: boolean;
  fx_rate_to_cny: number | null;
  rmb_amount: number | null;
  description: string | null;
}

export interface CashBreakdown {
  currency: string;
  entries: CashBreakdownEntry[];
  subtotals: Record<string, number>;
  total_balance: number;
}

export interface AssetBreakdownEntry {
  asset_id: number;
  asset_code: string;
  asset_name: string | null;
  asset_type: string;
  current_quantity: number;
  latest_valuation_price: number | null;
  market_value: number | null;
  valuation_time: string | null;
  valuation_source: string;
  is_estimated: boolean;
}

export interface AssetBreakdown {
  currency: string;
  entries: AssetBreakdownEntry[];
  total_market_value: number;
}

export type RmbAmountSource = 'direct' | 'calculated' | 'missing';

export interface HistoricalInputEntry {
  event_id: number;
  cash_ledger_entry_id: number;
  event_time: string | null;
  event_type: string | null;
  native_amount_delta: number;
  rmb_amount: number | null;
  rmb_source: RmbAmountSource;
  fx_rate_used: number | null;
}

export interface HistoricalInputBreakdown {
  currency: string;
  entries: HistoricalInputEntry[];
  total_native_invested: number;
  total_cny_invested: number;
}

export interface CalculationStep {
  step_number: number;
  description: string;
  formula: string;
  inputs: Record<string, number | null>;
  result: number | null;
  notes: string[];
}

export interface CalculationTrail {
  native_assets: CalculationStep[];
  value_cny: CalculationStep[];
  investment_pnl: CalculationStep[];
  fx_pnl: CalculationStep[];
}

export type DiscrepancySeverity = 'error' | 'warning' | 'info';

export interface Discrepancy {
  metric: string;
  calculated_value: number;
  expected_value: number;
  absolute_difference: number;
  percentage_difference: number | null;
  severity: DiscrepancySeverity;
}

export type SuggestionLikelihood = 'high' | 'medium' | 'low';

export interface CorrectionSuggestion {
  suggestion_id: string;
  discrepancy_metric: string;
  suggested_action: string;
  likelihood: SuggestionLikelihood;
  details: string;
  affected_records: string[];
}

export interface AuditError {
  code: string;
  message: string;
  affected_metrics: string[];
}

export interface CurrencyAudit {
  currency: string;
  status: 'COMPLETE' | 'INCOMPLETE';
  errors: AuditError[];
  cash_breakdown: CashBreakdown;
  asset_breakdown: AssetBreakdown;
  historical_input_breakdown: HistoricalInputBreakdown;
  calculation_trail: CalculationTrail;
  discrepancies: Discrepancy[];
  correction_suggestions: CorrectionSuggestion[];
  performance_metrics: Record<string, unknown>;
}

export interface AuditSummary {
  total_discrepancies: number;
  currencies_with_issues: string[];
  data_quality_score: number;
}

export interface DataQuality {
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
}

export interface AuditResponse {
  audit_id: string;
  audit_log_id?: number;
  audit_time: string;
  user_id: number;
  currencies_audited: string[];
  summary: AuditSummary;
  overview: PerformanceOverview;
  by_currency: CurrencyAudit[];
  data_quality: DataQuality;
}

export interface ExpectedValues {
  cash?: number;
  assets?: number;
  valueCny?: number;
}

export interface AuditRequest {
  userId: number;
  currency?: string | null;
  valuationTime?: string;
  expectedValues?: ExpectedValues;
}

export interface AuditHistoryItem {
  id: number;
  audit_id: string;
  audit_time: string;
  currencies_audited: string[];
  discrepancies_found: number;
  summary: AuditSummary;
}

export interface AuditHistoryResponse {
  audit_logs: AuditHistoryItem[];
}
