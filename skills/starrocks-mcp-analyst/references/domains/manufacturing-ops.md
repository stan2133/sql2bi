# Domain Pack: Manufacturing Operations

## Scope
Use for plant and line performance, yield, downtime, quality loss, throughput, and production planning diagnostics.

## Core Metrics
- `oee`: `availability * performance * quality`.
- `availability`: run time / planned production time.
- `performance`: ideal cycle time * total count / run time.
- `quality`: good count / total count.
- `first_pass_yield`: good units without rework / total units processed.
- `scrap_rate`: scrap units / total units produced.
- `downtime_rate`: downtime minutes / planned minutes.
- `schedule_adherence`: actual production / planned production.

## Metric Semantics Guardrails
- Define shift calendar and planned downtime exclusions.
- Separate planned maintenance from unplanned downtime.
- Keep unit-of-measure consistent across lines/plants.
- Include rework logic explicitly in quality metrics.

## Hypothesis Tree Seeds
- OEE decline:
  - unplanned downtime increase
  - cycle-time slowdown
  - rising defect rate
- Yield drop:
  - raw material quality issue
  - process parameter drift
  - operator or line change effects
- Throughput shortfall:
  - bottleneck station capacity limit
  - changeover inefficiency
  - labor coverage gaps

## Typical Dimensions
- `plant`, `line`, `work_center`
- `shift`, `crew`, `operator`
- `product_sku`, `product_family`
- `machine_id`, `downtime_reason_code`
- `batch_id`, `supplier_lot`

## Audit Checks
- Validate event sequencing for machine states (run/idle/down).
- Check that produced count equals good + scrap + rework where applicable.
- Reconcile MES logs with ERP production postings.
- Detect impossible cycle-time values and negative durations.

## Reporting Rules
- Show OEE decomposition; do not report only aggregate OEE.
- Quantify loss tree contribution (availability vs performance vs quality).
- Flag if quality data is sampled rather than full inspection.

## Action Playbook
- Downtime-driven OEE loss:
  - prioritize top downtime codes
  - target preventive maintenance actions
- Quality-driven OEE loss:
  - isolate defects by station and supplier lot
  - tighten process control windows
- Performance-driven OEE loss:
  - focus on changeover and micro-stop reduction

## Common Questions
- Which plants or lines drive the largest OEE loss?
- Is yield drop linked to specific supplier lots?
- What are the top bottlenecks reducing schedule adherence?
