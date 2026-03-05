# Domain Pack: Corporate Finance

## Scope
Use for management reporting, profitability analysis, cash conversion diagnostics, budget variance, and finance-backed decision support.
This pack also covers requests phrased as "cooperate finance" in user text.

## Core Metrics
- `revenue`: recognized revenue under accounting policy.
- `gross_margin`: `(revenue - cogs) / revenue`.
- `contribution_margin`: `(revenue - variable_cost) / revenue`.
- `ebitda`: earnings before interest, taxes, depreciation, and amortization.
- `operating_margin`: operating income / revenue.
- `free_cash_flow`: operating cash flow - capex.
- `dso`: accounts receivable / average daily revenue.
- `dpo`: accounts payable / average daily COGS.
- `dio`: inventory / average daily COGS.
- `cash_conversion_cycle`: `dso + dio - dpo`.

## Metric Semantics Guardrails
- Distinguish bookings, billings, and recognized revenue.
- Lock fiscal calendar and close version (`actual`, `flash`, `forecast`).
- Use consistent currency conversion rules and fx rate dates.
- Respect accounting policy for accruals, deferrals, and write-offs.
- Separate GAAP and non-GAAP views when both exist.

## Hypothesis Tree Seeds
- Margin decline:
  - product mix shift to low-margin items
  - discount or promo pressure
  - logistics or input cost inflation
- Cash conversion cycle deterioration:
  - slower collections (DSO up)
  - higher inventory days (DIO up)
  - faster supplier payments (DPO down)
- Forecast variance:
  - volume miss
  - price/mix miss
  - cost absorption miss

## Typical Dimensions
- `business_unit`, `product_line`, `cost_center`
- `region`, `legal_entity`
- `customer_segment`, `channel`
- `fiscal_period`, `scenario` (`actual`, `budget`, `forecast`)
- `currency`, `fx_rate_version`

## Audit Checks
- Reconcile P&L views to finance source-of-truth totals.
- Validate intercompany elimination logic where relevant.
- Check one-time adjustments are not mixed into recurring run-rate.
- Reconcile revenue and cash movement timing differences.

## Reporting Rules
- Separate operational KPI story from accounting policy effects.
- Quantify bridge analysis explicitly (volume, price, mix, cost, FX).
- Do not compare unmatched scenario versions (actual vs stale budget).
- Mark preliminary closes as lower confidence.

## Action Playbook
- Gross margin compression:
  - isolate price/mix impact by segment
  - prioritize margin recovery actions by contribution size
- FCF shortfall with revenue growth:
  - examine AR aging and inventory buildup
  - tighten working-capital controls
- Forecast inaccuracy:
  - improve driver-based forecasting at lowest stable grain

## Common Questions
- Why did EBITDA miss despite revenue growth?
- What is driving cash conversion cycle deterioration?
- Which business units contribute most to margin variance?
