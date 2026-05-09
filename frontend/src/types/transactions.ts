export type AssetType = 'CASH' | 'FOREX' | 'BOND' | 'FUND' | 'WEALTH_PRODUCT';
export type ManualAssetType = AssetType | 'FX_SWAP' | 'INTEREST_INCOME';
export type TradeDirection = 'BUY' | 'SELL';
export type TransactionDirection = TradeDirection | 'SWAP' | 'INCOME' | 'REINVEST';

export interface Transaction {
  id: number;
  user_id: number;
  asset_type: AssetType;
  asset_code: string;
  asset_name?: string | null;
  direction: TransactionDirection;
  quantity: number;
  unit_price: number;
  trade_currency: string;
  trade_time: string;
  exchange_rate_to_cny?: number | null;
  total_cost_cny?: number | null;
  signed_total_cost_cny?: number | null;
  trade_amount?: number | null;
  signed_trade_amount?: number | null;
  trade_amount_currency?: string | null;
  status: string;
  record_type?: 'TRANSACTION' | 'EVENT';
  event_type?: string;
  source?: string;
  notes?: string | null;
}

export interface TransactionCreatePayload {
  user_id: number;
  asset_type: AssetType;
  asset_code: string;
  asset_name?: string;
  direction: TradeDirection;
  quantity: number;
  unit_price: number;
  trade_currency: string;
  trade_time: string;
  exchange_rate_to_cny?: number;
  total_cost_cny?: number;
  source?: string;
  raw_text?: string;
  notes?: string;
}

export interface PortfolioEventCreatePayload {
  user_id: number;
  event_type: string;
  event_time: string;
  source?: string;
  status?: string;
  raw_text?: string;
  notes?: string;
  cash_entries: Array<{
    currency: string;
    amount_delta: number;
    rmb_amount?: number | null;
    fx_rate_to_cny?: number | null;
    is_external_flow: boolean;
    description?: string | null;
  }>;
  asset_entries?: PortfolioAssetEntryPayload[];
}

export interface PortfolioAssetEntryPayload {
  asset?: {
    asset_type: AssetType;
    asset_code: string;
    asset_name?: string | null;
    currency: string;
  };
  asset_id?: number;
  quantity_delta: number;
  cash_currency: string;
  cash_amount?: number | null;
  unit_price?: number | null;
  fx_rate_to_cny?: number | null;
  description?: string | null;
}

export interface TransactionFilters {
  user_id: number;
  asset_code?: string;
  direction?: TransactionDirection | '';
  start_time?: string;
  end_time?: string;
  limit?: number;
}

export interface ScreenshotUploadItem {
  filename: string;
  content_base64: string;
  language: string;
  provider?: string;
}

export interface ScreenshotPreviewEntry {
  filename: string;
  ocr?: {
    text: string;
    requires_manual_review?: boolean;
  };
  transaction_summary?: {
    transaction_type: AssetType;
    missing_fields: string[];
    confidence: number;
    parsed_transaction: Partial<TransactionCreatePayload>;
  };
}

export interface ScreenshotPreviewResponse {
  summary: {
    total_files: number;
    parsed_count: number;
    pending_count: number;
    failed_count: number;
  };
  parsed_transactions: ScreenshotPreviewEntry[];
  pending_review: ScreenshotPreviewEntry[];
  failed: Array<{
    filename?: string | null;
    errors: string[];
    stage?: string;
    ocr_text?: string;
  }>;
}

export interface ExcelPreviewReadyItem {
  row_number: number;
  source_transaction_id?: string | null;
  warnings: string[];
  transaction?: (TransactionCreatePayload & { status?: string }) | null;
  portfolio_event?: {
    event_type: string;
    event_time: string;
    source: string;
    status: string;
    raw_text?: string | null;
    notes?: string | null;
    cash_entries: Array<{
      currency: string;
      amount_delta: number;
      rmb_amount?: number | null;
      fx_rate_to_cny?: number | null;
      is_external_flow: boolean;
      description?: string | null;
    }>;
    asset_entries: Array<{
      asset?: {
        asset_type: AssetType;
        asset_code: string;
        asset_name?: string | null;
        currency: string;
      };
      quantity_delta: number;
      cash_currency: string;
      cash_amount?: number | null;
      unit_price?: number | null;
      description?: string | null;
    }>;
  } | null;
}

export interface ExcelPreviewFailedItem {
  row_number: number;
  row?: Record<string, unknown>;
  warnings?: string[];
  errors: string[];
}

export interface ExcelPreviewResponse {
  source_name: string;
  summary: {
    total_rows: number;
    ready_count: number;
    pending_count: number;
    failed_count: number;
  };
  ready_to_import: ExcelPreviewReadyItem[];
  pending_review: ExcelPreviewReadyItem[];
  failed: ExcelPreviewFailedItem[];
}

export interface ExcelConfirmResponse {
  source_name: string;
  imported_count: number;
  imported_event_count?: number;
  patched_event_count?: number;
  skipped_pending_count: number;
  skipped_duplicate_count?: number;
  failed_count: number;
  created_transaction_ids: number[];
  created_event_ids?: number[];
  preview_summary: ExcelPreviewResponse['summary'];
}
