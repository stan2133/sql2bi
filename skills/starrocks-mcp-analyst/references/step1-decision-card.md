# Step 1 Reference: Decision Card

## Purpose
Translate a broad business question into a decision-ready analysis contract before writing any SQL.

## Required Fields
Create a `decision_card` with these fields:
- `decision_question`: one sentence, explicit decision to support
- `target_metric`: metric name and formula
- `analysis_window`: start date, end date, and grain
- `comparison_mode`: `period_over_period` | `baseline` | `segment_benchmark`
- `scope`: product/channel/region/user segment
- `constraints`: budget, policy, inventory, system limits
- `assumptions`: explicit assumptions used to proceed

## Quality Rules
The card is valid only if all rules pass:
1. Decision question contains an action verb (`increase`, `decrease`, `prioritize`, `stop`, `launch`).
2. Target metric has a computable formula or clear temporary proxy.
3. Time window is bounded and aligned to grain.
4. Comparison mode is singular and explicit.
5. Scope is not ambiguous (`all users` is invalid without business reason).

## Follow-Up Trigger Rules
Ask follow-up only when one of these conditions is true:
- metric formula is missing and no safe proxy exists
- decision horizon is unknown and changes the method
- scope is too broad to run bounded SQL

Otherwise proceed with provisional assumptions and label them.

## Output Template
```json
{
  "decision_card": {
    "decision_question": "",
    "target_metric": {
      "name": "",
      "formula": ""
    },
    "analysis_window": {
      "start_date": "YYYY-MM-DD",
      "end_date": "YYYY-MM-DD",
      "grain": "day|week|month"
    },
    "comparison_mode": "period_over_period|baseline|segment_benchmark",
    "scope": {
      "product": [],
      "channel": [],
      "region": [],
      "segment": []
    },
    "constraints": [],
    "assumptions": []
  }
}
```

## Example
```json
{
  "decision_card": {
    "decision_question": "Should we increase paid social budget next month?",
    "target_metric": {
      "name": "incremental_gmv",
      "formula": "gmv_paid_social - baseline_gmv_without_paid_social"
    },
    "analysis_window": {
      "start_date": "2026-02-01",
      "end_date": "2026-02-28",
      "grain": "day"
    },
    "comparison_mode": "period_over_period",
    "scope": {
      "product": ["all"],
      "channel": ["paid_social"],
      "region": ["US"],
      "segment": ["new_users"]
    },
    "constraints": ["monthly_budget_cap=200000"],
    "assumptions": ["attribution_window=7d_click"]
  }
}
```
