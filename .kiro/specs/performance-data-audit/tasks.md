# Implementation Plan: Performance Data Audit

## Overview

This implementation plan breaks down the Performance Data Audit feature into discrete coding tasks. The feature provides comprehensive data verification and auditing capabilities for portfolio performance metrics, including data traceability, calculation trails, discrepancy detection, and correction suggestions.

**Implementation Order:** Backend services → API endpoints → Frontend types → Frontend services → Frontend UI components → Testing

**Key Technologies:**
- Backend: Python (FastAPI, SQLAlchemy)
- Frontend: TypeScript (React, Material-UI, TanStack Query)
- Database: Existing schema (no new tables required)

## Post-MVP Iteration Notes

The original audit MVP tasks below are complete. Since that delivery, the same code path has also been extended with:

- current-rate refresh wiring on the audit page and backend provider fixes, so Calculation Trail uses refreshed latest FX rates instead of stale fallback rows
- positions overview alignment with `/api/performance`, so `Total Value - Total Cost = Total PnL`
- row-level `Investment PnL` and `FX PnL` columns on Positions
- native-cost display for non-CNY cash and amount-valued assets

Still deferred:

- per-product funding-source allocation / provenance-aware RMB cost basis for foreign assets
- per-account cash decomposition; current foreign cash rows are pooled by currency
- historical-rate backfill migration for old imported rows that predate the trade-date FX enrichment logic

## Tasks

- [x] 1. Implement AuditService backend class
  - [x] 1.1 Create AuditService class structure and initialization
    - Add `AuditService` class to `src/investment_tracker/data/services.py`
    - Initialize with `session`, `performance_service`, and `exchange_rate_service`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_
  
  - [x] 1.2 Implement cash breakdown method
    - Implement `get_cash_breakdown()` method
    - Query all `CashLedgerEntry` records for user and currency
    - Group entries by event type and calculate subtotals
    - Calculate running balances after each transaction
    - Exclude CNY external flows per business logic
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
  
  - [x]* 1.3 Write unit tests for cash breakdown
    - Test cash entries retrieval and grouping
    - Test CNY external flow exclusion
    - Test running balance calculations
    - Test subtotal calculations by event type
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
  
  - [x] 1.4 Implement asset breakdown method
    - Implement `get_asset_breakdown()` method
    - Query asset quantities from `AssetLedgerEntry`
    - Retrieve latest `ValuationSnapshot` for each asset
    - Handle amount-valued assets (BOND, FUND, WEALTH_PRODUCT) without snapshots
    - Flag estimated valuations with indicator
    - Calculate total asset market value
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_
  
  - [x]* 1.5 Write unit tests for asset breakdown
    - Test asset breakdown with ValuationSnapshot
    - Test amount-valued assets without snapshots
    - Test estimated valuation flagging
    - Test total market value calculation
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_
  
  - [x] 1.6 Implement historical input breakdown method
    - Implement `get_historical_input_breakdown()` method
    - Filter portfolio events by INVESTMENT_POOL_EVENTS types
    - Extract native amount deltas and RMB amounts
    - Show RMB amount source (direct field vs calculated from FX rate)
    - Calculate total native invested and total CNY invested
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
  
  - [x]* 1.7 Write unit tests for historical input breakdown
    - Test INVESTMENT_POOL_EVENTS filtering
    - Test RMB amount source determination
    - Test native and CNY total calculations
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 2. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Implement calculation and discrepancy detection methods
  - [x] 3.1 Implement calculation trail generation
    - Implement `generate_calculation_trail()` method
    - Generate step-by-step calculations for Native Assets (cash + assets)
    - Generate calculations for Value CNY (native_assets × fx_rate)
    - Generate calculations for Investment PnL
    - Generate calculations for FX PnL
    - Display intermediate values and formulas with actual values
    - Highlight exchange rates used in each step
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_
  
  - [x]* 3.2 Write unit tests for calculation trail
    - Test calculation trail generation for all metrics
    - Test formula formatting with actual values
    - Test exchange rate highlighting
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_
  
  - [x] 3.3 Implement discrepancy detection
    - Implement `detect_discrepancies()` method
    - Compare calculated values against expected values
    - Calculate absolute and percentage differences
    - Flag discrepancies exceeding configurable threshold (default 0.01)
    - Assign severity levels (error, warning, info)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
  
  - [x]* 3.4 Write unit tests for discrepancy detection
    - Test discrepancies within threshold (not flagged)
    - Test discrepancies above threshold (flagged)
    - Test severity level assignment
    - Test absolute and percentage difference calculations
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
  
  - [x] 3.5 Implement correction suggestions
    - Implement `generate_correction_suggestions()` method
    - Generate suggestions for cash balance discrepancies
    - Generate suggestions for asset valuation discrepancies
    - Generate suggestions for historical input discrepancies
    - Rank suggestions by likelihood (high, medium, low)
    - Include affected record identifiers
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_
  
  - [x]* 3.6 Write unit tests for correction suggestions
    - Test cash discrepancy suggestions
    - Test asset discrepancy suggestions
    - Test historical input discrepancy suggestions
    - Test likelihood ranking
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement audit orchestration and logging
  - [x] 5.1 Implement main audit generation method
    - Implement `generate_audit()` method
    - Orchestrate calls to cash, asset, and historical input breakdown methods
    - Generate calculation trails for each currency
    - Perform discrepancy detection when expected values provided
    - Generate correction suggestions for identified discrepancies
    - Handle multi-currency audits (all currencies when currency param is None)
    - Compile data quality report (missing rates, missing valuations, estimated values)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 7.1, 7.2, 7.3, 7.4_
  
  - [x] 5.2 Implement audit logging
    - Implement `create_audit_log()` method
    - Create `AuditLog` record with entity_type='performance_audit'
    - Store complete audit report in details_json field
    - Include currencies_audited, discrepancies_found, and summary
    - _Requirements: 12.1_
  
  - [x] 5.3 Implement audit history retrieval
    - Implement `get_audit_history()` method
    - Query `AuditLog` records for user with entity_type='performance_audit'
    - Return audit logs with timestamps and summary statistics
    - Support limit parameter (default 50)
    - _Requirements: 12.2, 12.3, 12.4_
  
  - [x]* 5.4 Write unit tests for audit orchestration
    - Test single currency audit generation
    - Test multi-currency audit generation
    - Test audit with expected values (discrepancy detection)
    - Test data quality report compilation
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 7.1, 7.2, 7.3, 7.4_
  
  - [x]* 5.5 Write unit tests for audit logging
    - Test audit log creation
    - Test audit history retrieval
    - Test details_json structure
    - _Requirements: 12.1, 12.2, 12.3, 12.4_

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement API endpoints
  - [x] 7.1 Implement GET /api/performance/audit endpoint
    - Add endpoint to `src/investment_tracker/api/routes/performance.py`
    - Accept query parameters: user_id, currency, valuation_time, expected_cash, expected_assets, expected_value_cny
    - Parse valuation_time from ISO 8601 format
    - Build expected_values dict from query parameters
    - Call `AuditService.generate_audit()` with parameters
    - Call `AuditService.create_audit_log()` to record audit
    - Return audit report in JSON format
    - Handle validation errors (400), missing data (404), system errors (500)
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_
  
  - [x] 7.2 Implement GET /api/performance/audit-history endpoint
    - Add endpoint to `src/investment_tracker/api/routes/performance.py`
    - Accept query parameters: user_id, limit (default 50)
    - Call `AuditService.get_audit_history()` with parameters
    - Return audit logs in JSON format
    - _Requirements: 12.2_
  
  - [x] 7.3 Implement GET /api/performance/audit/{audit_id} endpoint
    - Add endpoint to `src/investment_tracker/api/routes/performance.py`
    - Accept path parameter: audit_id
    - Accept query parameter: user_id
    - Query `AuditLog` by id and user_id
    - Return audit report from details_json field
    - Handle not found errors (404)
    - _Requirements: 12.4_
  
  - [x]* 7.4 Write API endpoint tests
    - Test GET /api/performance/audit with single currency
    - Test GET /api/performance/audit with all currencies
    - Test GET /api/performance/audit with expected values
    - Test GET /api/performance/audit with invalid currency (400 error)
    - Test GET /api/performance/audit-history
    - Test GET /api/performance/audit/{audit_id}
    - Test error handling for all endpoints
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 12.2, 12.4_

- [x] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement frontend type definitions
  - [x] 9.1 Create audit type definitions
    - Create `frontend/src/types/audit.ts` file
    - Define `CashBreakdownEntry` interface
    - Define `AssetBreakdownEntry` interface
    - Define `HistoricalInputEntry` interface
    - Define `CalculationStep` interface
    - Define `Discrepancy` interface
    - Define `CorrectionSuggestion` interface
    - Define `CurrencyAudit` interface
    - Define `AuditSummary` interface
    - Define `DataQuality` interface
    - Define `AuditResponse` interface
    - Define `AuditRequest` interface
    - Define `ExpectedValues` interface
    - Define `AuditHistoryResponse` interface
    - _Requirements: 9.4, 10.1_

- [x] 10. Implement frontend audit service
  - [x] 10.1 Create audit API client
    - Create `frontend/src/services/audit.ts` file
    - Implement `getAudit()` function with query parameters
    - Implement `getAuditHistory()` function
    - Implement `getAuditDetail()` function
    - Use existing `api` client from `services/api.ts`
    - Construct URLSearchParams for query parameters
    - Handle API responses and errors
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_
  
  - [ ]* 10.2 Write unit tests for audit service
    - Test getAudit constructs correct URL with parameters
    - Test getAudit handles error responses
    - Test getAuditHistory returns logs
    - Test getAuditDetail retrieves specific audit
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 11. Implement frontend audit UI components
  - [x] 11.1 Create AuditPage main component
    - Create `frontend/src/features/performance/AuditPage.tsx` file
    - Set up state management for selectedCurrency, expectedValues, expandedSections
    - Implement useQuery hook for audit data fetching
    - Create main layout with Stack spacing
    - Integrate all sub-components
    - Handle loading and error states
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_
  
  - [x] 11.2 Create CurrencySelector component
    - Create currency selector dropdown
    - Include "All Currencies" option
    - Update selectedCurrency state on change
    - _Requirements: 10.2_
  
  - [x] 11.3 Create ExpectedValuesForm component
    - Create input form for expected_cash, expected_assets, expected_value_cny
    - Use Material-UI TextField components
    - Update expectedValues state on change
    - Validate numeric inputs
    - _Requirements: 10.5_
  
  - [x] 11.4 Create AuditSummary component
    - Display total_discrepancies, currencies_with_issues, data_quality_score
    - Use color-coded indicators (red for errors, yellow for warnings, green for verified)
    - Show data quality warnings (missing rates, missing valuations, estimated values)
    - _Requirements: 10.4, 7.3_
  
  - [x] 11.5 Create CashBreakdownSection component
    - Display all CashLedgerEntry records for currency
    - Group entries by event type with subtotals
    - Show running balances after each transaction
    - Highlight external flows
    - Use expandable/collapsible sections
    - Use DataTable component for entries
    - _Requirements: 10.3, 3.1, 3.2, 3.3, 3.4_
  
  - [x] 11.6 Create AssetBreakdownSection component
    - Display all assets in currency with non-zero quantities
    - Show asset_code, asset_name, asset_type, quantity, price, market_value
    - Indicate valuation source and timestamp
    - Flag estimated valuations with indicator
    - Use DataTable component for assets
    - _Requirements: 10.3, 4.1, 4.2, 4.3, 4.4, 4.5_
  
  - [x] 11.7 Create CalculationTrailSection component
    - Display step-by-step calculations for each metric
    - Show formulas with actual values substituted
    - Highlight exchange rates used
    - Use expandable sections for intermediate steps
    - Format numbers with appropriate precision
    - _Requirements: 10.3, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_
  
  - [x] 11.8 Create DiscrepanciesSection component
    - Display discrepancies with color coding (red/yellow/green)
    - Show metric name, calculated value, expected value
    - Show absolute and percentage differences
    - Provide drill-down links to relevant data sources
    - Only display when discrepancies exist
    - _Requirements: 10.4, 6.1, 6.2, 6.3, 6.4_
  
  - [x] 11.9 Create CorrectionSuggestionsSection component
    - Display suggested correction actions
    - Show likelihood ranking (high, medium, low)
    - Display affected record identifiers
    - Provide links to correction workflows (if applicable)
    - Only display when suggestions exist
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_
  
  - [x] 11.10 Create AuditHistorySection component
    - Display past audit logs with timestamps
    - Show summary statistics for each audit
    - Provide links to view detailed results from past audits
    - Use DataTable component for history
    - _Requirements: 12.3, 12.4_
  
  - [ ]* 11.11 Write component tests for AuditPage
    - Test currency selector renders and updates state
    - Test expected values form renders and validates input
    - Test cash breakdown section displays entries correctly
    - Test asset breakdown section displays assets correctly
    - Test calculation trail section displays steps correctly
    - Test discrepancies section highlights issues with color coding
    - Test correction suggestions section displays actions
    - Test audit history section displays logs
    - Test expandable sections functionality
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 12. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Integration and wiring
  - [x] 13.1 Add navigation to AuditPage from PerformancePage
    - Add "Audit Data" button to PerformancePage header
    - Link to AuditPage route or open as modal
    - Update routing configuration if needed
    - _Requirements: 10.1_
  
  - [x] 13.2 Add exchange rate verification display
    - Enhance calculation trail to show exchange rate details
    - Display rate_timestamp and source for each rate
    - Mark estimated rates with "ESTIMATED" indicator
    - Mark missing rates with "MISSING RATE" indicator
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_
  
  - [x] 13.3 Add export functionality
    - Implement JSON export for audit report
    - Implement CSV export for audit report
    - Add export buttons to AuditPage
    - _Requirements: 7.5_
  
  - [ ]* 13.4 Write integration tests
    - Test full audit workflow for single currency (USD)
    - Test full audit workflow for all currencies
    - Test audit with missing exchange rates
    - Test audit with missing valuations
    - Test audit with expected values (discrepancy detection)
    - Test audit log creation and retrieval workflow
    - Test frontend audit page full workflow
    - Test discrepancy highlighting in UI
    - Test correction suggestions interaction
    - Test audit history navigation
    - _Requirements: All requirements_

- [x] 14. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at logical breaks
- Backend implementation uses existing database schema (no migrations needed)
- Frontend components follow existing patterns from PerformancePage
- All numeric values use appropriate precision (6 decimals for quantities, 2 for currency)
- Error handling follows existing patterns in the codebase
- The feature leverages existing PerformanceService for metric calculations
