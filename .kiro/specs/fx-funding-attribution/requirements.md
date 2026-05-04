# Requirements Document: FX Funding Attribution and Cost Penetration

## Overview

The current portfolio ledger can already explain portfolio-level `Investment PnL` and `FX PnL`, but per-product foreign-currency cost basis is still computed from each asset ledger row's own trade-date FX rate. That is sufficient for product-level bookkeeping, but it does not answer a stricter question:

> The USD used to buy this fund came from where, and how many RMB did those USD really cost at source?

This iteration introduces a funding-source allocation and cost-penetration model for foreign-currency assets. The goal is to let a single foreign product answer all of the following in a defensible way:

- how much native currency was invested into the product
- how much RMB was actually consumed to obtain that native currency
- how much of current PnL is investment return versus FX contribution
- which upstream events funded each purchase, including RMB FX buys, cross-FX swaps, prior cash balances, and redemptions from other foreign assets

## Problem Statement

Today, a foreign product such as a USD fund or USD wealth product can be purchased using mixed funding sources:

- RMB exchanged into USD on the same day
- USD exchanged from EUR, JPY, CAD, or another foreign currency
- USD redeemed from another USD-denominated fund or wealth product
- existing USD cash balance carried forward from earlier periods

The current product-level `cost_basis_cny` ignores that provenance chain. It only sums:

```text
asset_ledger_entry.native_amount × asset_ledger_entry.fx_rate_to_cny
```

This creates two gaps:

1. product-level `累计总投入 RMB` is a bookkeeping approximation, not a provenance-aware funding cost
2. product-level `Investment PnL` and `FX PnL` are directionally useful, but may be materially wrong when the product was funded by mixed-source foreign currency

## Goals

1. Build a provenance-aware funding model for foreign-currency asset purchases.
2. Preserve the existing portfolio-level performance formulas:
   - `真实总盈亏 RMB = 当前总资产 RMB - 累计总投入 RMB`
   - `汇率收益 RMB = 总收益 RMB - 投资收益 RMB`
3. Extend those formulas to per-product foreign assets with explicit traceability.
4. Make the source chain inspectable in API responses and audit surfaces.
5. Support deterministic recalculation after import, edit, delete, snapshot update, and manual adjustment.

## Non-Goals

- No tax-lot accounting for realized taxable gains in this iteration.
- No attempt to infer missing source events when the upstream ledger is incomplete.
- No silent estimation of provenance when required historical cost data is absent.
- No change to the meaning of amount-valued snapshots: snapshots still represent current holding amount, not units/NAV.

## Definitions

### Funding Source Lot

A funding source lot is a native-currency balance fragment with both:

- native amount remaining
- RMB cost basis attached to that native amount

Examples:

- `FX_BUY`: creates a USD lot funded by RMB
- `FX_SWAP`: closes one source-currency lot and creates a target-currency lot with translated RMB basis
- `FUND_SELL` or `WEALTH_REDEEM`: creates a native-currency cash lot whose RMB basis comes from the redeemed asset's carrying value rule

### Cost Penetration

Cost penetration means the system can walk from a product purchase event backward through one or more funding source lots until it reaches the upstream origin events that supplied the purchased currency.

### Attributed RMB Cost

Attributed RMB cost is the RMB basis allocated from upstream funding source lots to a specific product purchase amount.

## Requirement 1: Funding Lots Must Be Materialized

1. WHEN a foreign-currency cash balance is created by an event that contributes investable currency, THE System SHALL create or update a funding source lot for that currency.
2. WHEN a funding lot is created, THE System SHALL persist both native amount and RMB basis.
3. WHEN a lot is partially consumed, THE System SHALL persist the remaining native amount and remaining RMB basis after allocation.
4. WHEN a lot reaches zero remaining amount, THE System SHALL mark it fully consumed instead of deleting lineage.
5. WHEN a funding lot lacks sufficient RMB basis inputs, THE System SHALL mark it `BASIS_MISSING` and exclude it from provenance-complete attribution until corrected.

## Requirement 2: Eligible Source Events Must Be Classified Explicitly

1. WHEN the System processes `FX_BUY`, THE System SHALL classify the acquired foreign currency as a funding source lot with direct RMB basis.
2. WHEN the System processes `FX_SWAP`, THE System SHALL consume source-currency lots and create target-currency lots with translated RMB basis.
3. WHEN the System processes foreign-currency asset redemption or dividend income, THE System SHALL classify the resulting foreign-currency cash as a funding source lot.
4. WHEN the System processes `MANUAL_ADJUSTMENT`, THE System SHALL require the user to specify whether the adjustment carries RMB basis, zero basis, or unknown basis.
5. WHEN the System processes interest income in foreign currency, THE System SHALL classify it as a gain-origin lot, not new external principal.

## Requirement 3: Allocation Policy Must Be Deterministic and Configurable

1. WHEN a foreign-currency asset purchase consumes cash, THE System SHALL allocate native funding from existing same-currency source lots using one deterministic policy.
2. THE default allocation policy SHALL be FIFO unless the implementation explicitly exposes a different policy.
3. WHEN the configured policy changes, THE System SHALL require a full recalculation and audit log entry.
4. WHEN available source lots are insufficient for a purchase, THE System SHALL create an `UNATTRIBUTED_FUNDING` gap record instead of silently fabricating RMB basis.
5. WHEN multiple upstream lots fund one purchase, THE System SHALL record the split native amount and split RMB basis per upstream lot.

## Requirement 4: Product-Level RMB Cost Must Be Provenance-Aware

1. WHEN a foreign-currency `FUND_BUY`, `WEALTH_BUY`, or `BOND_BUY` event is recorded, THE System SHALL compute the product purchase's RMB cost from allocated upstream funding lots, not only from the asset ledger row's own FX rate.
2. WHEN a product has multiple purchase events, THE System SHALL accumulate per-purchase attributed RMB basis into the product's cumulative invested RMB.
3. WHEN a product is partially redeemed, THE System SHALL reduce native cost and attributed RMB cost using the same deterministic lot policy applied to the product's own carrying lots.
4. WHEN a product purchase is funded by redemption proceeds from another foreign asset, THE downstream product's attributed RMB cost SHALL inherit the carrying RMB basis of the redeemed proceeds rather than resetting to the current spot rate.
5. WHEN no provenance-complete RMB basis exists for a purchase, THE System SHALL show the product as `ATTRIBUTION_INCOMPLETE`.

## Requirement 5: Investment PnL and FX PnL Must Follow the Existing Core Formula

1. WHEN the System calculates product-level total PnL in RMB, THE formula SHALL remain:

```text
Total PnL RMB = Current Value RMB - Attributed Cumulative Invested RMB
```

2. WHEN the System calculates product-level investment PnL, THE formula SHALL use the native-currency delta first:

```text
Investment PnL RMB = (Current Native Value - Native Cost) × Current FX Rate
```

3. WHEN the System calculates product-level FX PnL, THE formula SHALL be:

```text
FX PnL RMB = Total PnL RMB - Investment PnL RMB
```

4. WHEN the System calculates product-level return, THE denominator SHALL be native cost for foreign amount-valued assets unless a user-facing page explicitly states a different denominator.
5. WHEN attribution is incomplete, THE System SHALL still compute native investment PnL if possible, but SHALL flag FX PnL and total attributed RMB cost as incomplete.

## Requirement 6: Audit and Explainability Must Expose the Funding Chain

1. WHEN a user inspects a foreign product, THE System SHALL expose the list of upstream funding lots that contributed to its current cost basis.
2. FOR each upstream lot, THE System SHALL show:
   - source event id
   - source event type
   - source currency
   - native amount allocated
   - RMB basis allocated
   - remaining unconsumed amount on the source lot after allocation
3. WHEN a source lot itself came from another source lot, THE System SHALL support recursive drill-down to the terminal origin.
4. WHEN the audit page shows `Historical Input` or `Calculation Trail`, THE System SHALL be able to distinguish:
   - external principal
   - investment gains recycled as funding
   - FX-translated basis inherited from another currency
5. WHEN attribution gaps exist, THE System SHALL surface actionable correction suggestions instead of silently falling back to row FX rates.

## Requirement 7: Import, Edit, Delete, and Rebuild Must Keep Attribution Consistent

1. WHEN new Excel rows are confirmed, THE System SHALL recompute affected funding lots and downstream allocations for the impacted user and currencies.
2. WHEN a portfolio event is edited or deleted, THE System SHALL invalidate and rebuild all affected downstream attribution records.
3. WHEN a valuation snapshot changes, THE System SHALL not rebuild funding provenance, because snapshots affect current value but not historical funding source.
4. WHEN historical FX rows are corrected, THE System SHALL rebuild all affected lots whose RMB basis depended on those rates.
5. WHEN a rebuild changes attributed RMB cost materially, THE System SHALL create an audit log entry describing the impacted products.

## Requirement 8: Surfaces and APIs Must Make the Attribution Status Visible

1. WHEN `GET /api/positions` returns a foreign product, THE payload SHALL include attribution status and provenance-aware `cost_basis_cny` when available.
2. WHEN attribution is complete, THE Positions page SHALL show the provenance-aware cost basis without requiring the user to infer it from other screens.
3. WHEN attribution is incomplete, THE Positions page SHALL display a status such as `ATTRIBUTION_INCOMPLETE` rather than mixing partial data into a normal `OK` row.
4. WHEN `GET /api/performance/audit` is called for a foreign-currency pool, THE response SHALL be able to include funding-attribution diagnostics for products in that currency.
5. WHEN exported audit JSON/CSV is generated, THE export SHALL preserve attribution status and provenance identifiers.

## Requirement 9: Migration and Backfill Must Be Explicit

1. WHEN this feature is introduced on an existing database, THE System SHALL provide a rebuild/backfill path for attribution records derived from historical ledger data.
2. WHEN historical data lacks enough information to produce provenance-complete attribution, THE backfill SHALL mark the affected products as incomplete rather than fabricating lineage.
3. WHEN a user chooses not to backfill immediately, THE System SHALL keep current portfolio-level performance available while clearly labeling product-level attribution as legacy.
4. THE migration plan SHALL document which pages continue to use old logic during rollout and which pages switch to the new model first.

## Success Criteria

- A foreign product funded by mixed RMB FX, cross-FX swaps, and prior redemptions can show a defensible `累计总投入 RMB`.
- Product-level `Investment PnL + FX PnL = Total PnL` remains closed after provenance-aware cost allocation.
- Users can inspect the funding chain instead of guessing where a product's foreign currency came from.
- Missing lineage becomes a visible data-quality state, not a silent accounting approximation.
