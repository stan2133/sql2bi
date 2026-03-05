# Step 2 Reference: Business Knowledge And Metric Semantics

## Purpose
Resolve business meaning before SQL generation.
Ensure every metric, dimension, and comparison uses a documented semantic contract and domain playbook.

## Knowledge Pack Layout
Use this file as control logic and load detailed domain knowledge from:
- `references/knowledge-router.md`
- `references/domains/growth-hacking.md`
- `references/domains/fraud-risk.md`
- `references/domains/nps-cx.md`
- `references/domains/sales-ops.md`
- `references/domains/manufacturing-ops.md`
- `references/domains/supply-chain.md`
- `references/domains/corporate-finance.md`
- `references/domains/hr-people-ops.md`

## Required Inputs
Load available knowledge in this order:
1. `metric dictionary`: metric names, formulas, exclusions, and owner.
2. `business glossary`: entity and event definitions.
3. `data contracts`: freshness, latency, and quality constraints.
4. `domain pack`: load from router based on analysis intent.

If multiple definitions conflict, prefer the newest approved definition and record the conflict.

## Domain Routing Procedure
1. Parse the user ask and decision card into `intent_tags`.
2. Use `references/knowledge-router.md` to map tags to one or two primary domains.
3. Load only relevant domain files (minimum context rule).
4. Produce a `domain_hypothesis_seed` from the selected domains.
5. Carry unresolved conflicts into `semantic_risks`.

## Semantic Resolution Rules
Apply these rules for each target metric:
1. Define numerator and denominator explicitly.
2. Define counting unit (`user_id`, `order_id`, `session_id`, etc.).
3. Define attribution window and timezone.
4. Define inclusion and exclusion conditions.
5. Define valid breakdown dimensions and forbidden cuts.

If any critical item is missing:
- create a provisional definition
- mark confidence ceiling to `low`
- add a caveat entry in final report

## Knowledge Quality Gates
A semantic contract is valid only if all checks pass:
1. Formula can be mapped to existing columns and tables.
2. Grain is compatible with the decision card (`day|week|month`, etc.).
3. Comparison mode is semantically valid for that domain.
4. Dimension definitions match business glossary.
5. At least one metric owner or approved source doc is identified.

## Cross-Domain Conflict Rules
When multiple domains are loaded, resolve by priority:
1. Governance and compliance constraints (highest priority)
2. Official finance definitions
3. Domain operational definitions
4. Experimental growth definitions (lowest priority)

Examples:
- Fraud risk overrides growth uplift if risk policy thresholds are breached.
- Corporate finance revenue recognition overrides sales pipeline booking numbers.

## Output Template
```json
{
  "business_semantic_contract": {
    "loaded_knowledge_files": [],
    "intent_tags": [],
    "metric": {
      "name": "",
      "formula_sql_expression": "",
      "unit": "",
      "owner": "",
      "definition_status": "official|provisional"
    },
    "time": {
      "event_time_column": "",
      "timezone": "",
      "grain": "day|week|month",
      "attribution_window": ""
    },
    "scope_rules": {
      "allowed_dimensions": [],
      "forbidden_dimensions": [],
      "required_filters": [],
      "exclusion_rules": []
    },
    "comparison_rules": {
      "mode": "period_over_period|baseline|segment_benchmark",
      "baseline_definition": ""
    },
    "domain_hypothesis_seed": [],
    "data_contract": {
      "freshness_sla": "",
      "latency_note": "",
      "known_quality_risks": []
    },
    "semantic_risks": []
  }
}
```

## Example
```json
{
  "business_semantic_contract": {
    "loaded_knowledge_files": [
      "references/domains/growth-hacking.md",
      "references/domains/nps-cx.md"
    ],
    "intent_tags": ["acquisition", "retention", "nps_drop"],
    "metric": {
      "name": "activation_rate",
      "formula_sql_expression": "activated_users / new_users",
      "unit": "ratio",
      "owner": "growth_analytics",
      "definition_status": "official"
    },
    "time": {
      "event_time_column": "event_time",
      "timezone": "America/Los_Angeles",
      "grain": "day",
      "attribution_window": "7d"
    },
    "scope_rules": {
      "allowed_dimensions": ["channel", "country", "device_type"],
      "forbidden_dimensions": ["raw_user_agent"],
      "required_filters": ["is_internal_user = 0"],
      "exclusion_rules": ["exclude_refunded_orders = 1"]
    },
    "comparison_rules": {
      "mode": "period_over_period",
      "baseline_definition": "previous_28d"
    },
    "domain_hypothesis_seed": [
      "nps_drop_from_slow_onboarding",
      "activation_fall_from_channel_mix_shift"
    ],
    "data_contract": {
      "freshness_sla": "T+1 07:00 UTC",
      "latency_note": "support tickets table may lag by 3 hours",
      "known_quality_risks": ["survey_response_rate under 8% in some regions"]
    },
    "semantic_risks": []
  }
}
```
