# Domain Pack: Supply Chain

## Scope
Use for demand planning, inventory health, procurement performance, logistics service level, and fulfillment efficiency.

## Core Metrics
- `otif`: on-time in-full deliveries / total deliveries.
- `fill_rate`: fulfilled demand units / total demand units.
- `stockout_rate`: stockout SKU-days / total SKU-days.
- `inventory_turnover`: COGS / average inventory.
- `days_of_inventory`: average inventory / average daily COGS.
- `forecast_accuracy_mape`: mean absolute percentage error by SKU/location.
- `lead_time`: receipt date - order date.
- `supplier_otd`: on-time supplier deliveries / supplier deliveries.

## Metric Semantics Guardrails
- Define service promise date source (requested vs committed date).
- Distinguish sell-in vs sell-out when interpreting inventory turns.
- Use consistent SKU hierarchy and location hierarchy.
- Separate constrained demand from unconstrained demand in forecast analysis.

## Hypothesis Tree Seeds
- OTIF drop:
  - supplier delays
  - warehouse capacity bottlenecks
  - transportation disruptions
- Stockout spike:
  - forecast bias
  - replenishment parameter mismatch
  - inbound delays
- High inventory with low service level:
  - wrong inventory placement
  - SKU mix imbalance
  - safety stock misconfiguration

## Typical Dimensions
- `sku`, `category`, `brand`
- `warehouse`, `region`, `store`
- `supplier`, `carrier`, `route`
- `order_type`, `priority_level`
- `week`, `season`, `promotion_flag`

## Audit Checks
- Reconcile inventory snapshots with movement ledger.
- Detect negative inventory or impossible in-transit balances.
- Validate lead-time calculation with timezone and holiday calendars.
- Check demand signals include order cancellations and returns logic.

## Reporting Rules
- Report service level and inventory efficiency together.
- Expose forecast error by value-weighted and volume-weighted views.
- Separate structural issues (master data, policy) from temporary disruptions.

## Action Playbook
- OTIF down + inbound delays up:
  - re-prioritize suppliers and transport lanes
  - activate contingency sourcing
- Stockouts concentrated in promoted SKUs:
  - apply event-aware forecast uplift
  - accelerate allocation and replenishment cycles
- High inventory and low turns:
  - optimize reorder points and safety stock by demand class

## Common Questions
- What drives service-level degradation this month?
- Which SKUs have the worst forecast bias and largest business impact?
- Is inventory excess caused by demand weakness or replenishment policy?
