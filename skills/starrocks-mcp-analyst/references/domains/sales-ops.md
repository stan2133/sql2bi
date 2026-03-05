# Domain Pack: Sales Operations

## Scope
Use for pipeline health, forecast accuracy, conversion stages, quota attainment, and sales productivity analysis.

## Core Metrics
- `pipeline_coverage`: pipeline value for period / quota for period.
- `win_rate`: won opportunities / closed opportunities.
- `stage_conversion_rate`: opportunities moved to next stage / opportunities in current stage.
- `average_sales_cycle_days`: average close date - created date.
- `average_deal_size`: booked amount / won deals.
- `quota_attainment`: booked or recognized revenue / quota.
- `forecast_accuracy`: `1 - abs(forecast - actual) / actual`.

## Metric Semantics Guardrails
- Distinguish `bookings`, `billings`, and `recognized_revenue`.
- Align analysis with fiscal calendar, not only natural month.
- Define opportunity ownership and split-credit rules.
- Control for duplicate opportunities and late CRM updates.

## Hypothesis Tree Seeds
- Win rate decline:
  - poor lead quality
  - pricing pressure
  - competitor displacement
  - stage qualification drift
- Pipeline coverage decline:
  - top-of-funnel shortage
  - low conversion from MQL to SQL
  - increased deal slippage
- Forecast miss:
  - stage aging under-estimated
  - optimistic commit behavior
  - concentration risk in few large deals

## Typical Dimensions
- `region`, `segment`, `industry`
- `sales_rep`, `team`, `manager`
- `lead_source`, `campaign`
- `product_family`, `deal_size_bucket`
- `opportunity_stage`, `stage_age_bucket`

## Audit Checks
- Check stage history integrity (no impossible stage jumps).
- Reconcile CRM opportunity totals vs finance recognized revenue.
- Validate close-date changes and slippage rates.
- Split analysis by new logo vs expansion deals.

## Reporting Rules
- Always separate volume effects (deal count) from price/mix effects (deal size).
- Show pipeline by aging bucket to expose hidden risk.
- When discussing forecast, include confidence by commit category.

## Action Playbook
- Low stage conversion at discovery:
  - tighten qualification criteria
  - improve discovery enablement
- High slippage near quarter end:
  - add deal inspection cadence and risk scoring
- Strong pipeline but weak attainment:
  - isolate pricing discounting and late-stage loss reasons

## Common Questions
- Why did we miss quarter forecast despite high pipeline coverage?
- Which stages leak most opportunities?
- Which reps or segments have the largest cycle-time inflation?
