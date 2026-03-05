# Domain Pack: HR And People Operations

## Scope
Use for headcount planning, hiring funnel, attrition diagnostics, workforce productivity, and people-cost analysis.

## Core Metrics
- `headcount`: active employees at period end.
- `net_headcount_change`: hires - exits.
- `attrition_rate`: exits / average headcount.
- `voluntary_attrition_rate`: voluntary exits / average headcount.
- `new_hire_90d_attrition`: exits within 90 days / hires in period.
- `time_to_fill`: median days from requisition open to accepted offer.
- `offer_accept_rate`: accepted offers / total offers.
- `ramp_time_days`: days from hire date to target productivity threshold.
- `revenue_per_fte`: revenue / average FTE.
- `people_cost_ratio`: people costs / revenue.

## Metric Semantics Guardrails
- Define employee status snapshot logic (`active`, `leave`, `terminated`).
- Separate voluntary and involuntary exits.
- Normalize contractor and intern treatment before cross-team comparisons.
- Use effective-dated org hierarchy to avoid historical manager/team mismatch.
- Use HR-approved definitions for diversity and performance metrics.

## Hypothesis Tree Seeds
- Attrition increase:
  - compensation competitiveness decline
  - manager/team-level engagement issues
  - workload imbalance or role ambiguity
- Hiring slowdown:
  - requisition approval delays
  - candidate funnel drop at interview or offer stages
  - compensation band misalignment with market
- Productivity dip:
  - long ramp time for new hires
  - skill mix mismatch
  - high absenteeism in critical teams

## Typical Dimensions
- `department`, `business_unit`, `cost_center`
- `job_family`, `job_level`, `location`
- `manager`, `tenure_bucket`, `employment_type`
- `recruiter`, `source_channel`, `interview_stage`
- `gender`, `age_band`, `diversity_segment` (only when policy allows)

## Audit And Compliance Checks
- Enforce minimum cohort size before segment-level reporting.
- Mask or aggregate PII; avoid exposing employee-level sensitive data.
- Validate effective date logic for org and compensation changes.
- Reconcile HRIS events (`hire`, `transfer`, `termination`) with payroll roster.
- Flag policy restrictions for protected attributes.

## Reporting Rules
- Report attrition with both count and rate.
- Separate structural trends from one-off reorg effects.
- Attach confidence downgrade when data is censored or late.
- For sensitive segments, present only approved aggregated outputs.

## Action Playbook
- High voluntary attrition in critical teams:
  - launch retention interviews and compensation benchmarking
  - prioritize manager coaching in affected org units
- Long time-to-fill in key roles:
  - rebalance sourcing channels and refine job requirements
  - tighten requisition approval SLA
- Low revenue per FTE with hiring growth:
  - inspect ramp-time bottlenecks and role allocation efficiency

## Common Questions
- Which teams drive the recent attrition spike?
- Why is time-to-fill increasing for critical roles?
- Is headcount growth translating into productivity and revenue gains?
